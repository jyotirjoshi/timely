import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import (
    Department, Division, Institution, Program, School, Subject, SubjectComponent,
    Teacher, FacultyPreference, User, WorkloadAllocation,
)
from app.services.workload import suggest_allocations, summarize_workload


@pytest.fixture()
def workload_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = Session()
    institution = Institution(id="inst", name="University")
    school = School(id="school", institution_id="inst", name="Engineering", code="ENG")
    department = Department(
        id="dept", institution_id="inst", school_id="school", name="Computer Science", code="CSE"
    )
    other_department = Department(
        id="dept-other", institution_id="inst", school_id="school", name="Electronics", code="ECE"
    )
    program = Program(
        id="program", institution_id="inst", department_id="dept", name="B.Tech", code="BTECH"
    )
    division = Division(
        id="division", institution_id="inst", program_id="program",
        name="FY-A", academic_year=1, semester=1,
    )
    subject = Subject(id="subject", institution_id="inst", name="Algorithms")
    component = SubjectComponent(
        id="component", institution_id="inst", department_id="dept", subject_id="subject",
        component_type="theory", weekly_hours=4, duration_minutes=60,
    )
    practical = SubjectComponent(
        id="practical", institution_id="inst", department_id="dept", subject_id="subject",
        component_type="practical", weekly_hours=2, duration_minutes=120, room_type="lab",
    )
    preferred = Teacher(
        id="preferred", institution_id="inst", name="Preferred", subjects=["subject"]
    )
    lower_rank = Teacher(
        id="lower-rank", institution_id="inst", name="Lower Rank", subjects=["subject"]
    )
    unqualified = Teacher(
        id="unqualified", institution_id="inst", name="Unqualified", subjects=[]
    )
    db.add_all([
        institution, school, department, other_department, program, division, subject,
        component, practical, preferred, lower_rank, unqualified,
    ])
    db.flush()
    db.add_all([
        FacultyPreference(
            institution_id="inst", teacher_id="preferred", subject_component_id="component", rank=1
        ),
        FacultyPreference(
            institution_id="inst", teacher_id="lower-rank", subject_component_id="component", rank=2
        ),
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def workload_api(workload_db):
    owner = User(
        id="owner", email="owner@test", hashed_password="unused",
        role="owner", institution_id="inst",
    )
    workload_db.add(owner)
    workload_db.commit()

    def override_db():
        yield workload_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_suggestions_rank_qualification_preference_and_current_load_without_writing(workload_db):
    workload_db.add(WorkloadAllocation(
        institution_id="inst", teacher_id="preferred", subject_component_id="practical",
        division_id="division", weekly_hours=23,
    ))
    workload_db.commit()

    proposal = suggest_allocations(workload_db, "inst", "component", "division", 4)

    assert [candidate.teacher_id for candidate in proposal.candidates] == ["lower-rank", "preferred"]
    assert "unqualified" not in [candidate.teacher_id for candidate in proposal.candidates]
    assert workload_db.query(WorkloadAllocation).count() == 1


def test_workload_summary_uses_default_22_to_24_hour_band(workload_db):
    workload_db.add_all([
        WorkloadAllocation(
            institution_id="inst", teacher_id="preferred", subject_component_id="component",
            division_id="division", weekly_hours=23,
        ),
        WorkloadAllocation(
            institution_id="inst", teacher_id="lower-rank", subject_component_id="component",
            division_id="division", weekly_hours=25,
        ),
    ])
    workload_db.commit()

    summaries = {summary.teacher_id: summary for summary in summarize_workload(workload_db, "inst")}

    assert summaries["preferred"].status == "balanced"
    assert summaries["lower-rank"].status == "overloaded"
    assert summaries["unqualified"].status == "underloaded"


def test_cross_department_qualified_faculty_remain_eligible(workload_db):
    proposal = suggest_allocations(workload_db, "inst", "component", "division", 4)
    assert {candidate.teacher_id for candidate in proposal.candidates} == {"preferred", "lower-rank"}


def test_unqualified_override_requires_an_audited_reason(workload_db):
    allocation = WorkloadAllocation(
        institution_id="inst", teacher_id="unqualified", subject_component_id="component",
        division_id="division", weekly_hours=4, is_override=True,
        override_reason="Approved industry specialist", created_by="owner-id",
    )
    workload_db.add(allocation)
    workload_db.commit()

    assert allocation.is_override
    assert allocation.override_reason
    assert allocation.created_by == "owner-id"


def test_allocation_api_rejects_silent_override_and_audits_explicit_override(workload_api):
    payload = {
        "teacher_id": "unqualified", "subject_component_id": "component",
        "division_id": "division", "weekly_hours": 4,
    }
    assert workload_api.post(
        "/api/workloads/allocations", params={"institution_id": "inst"}, json=payload,
    ).status_code == 422
    assert workload_api.post(
        "/api/workloads/allocations", params={"institution_id": "inst"},
        json={**payload, "is_override": True},
    ).status_code == 422

    created = workload_api.post(
        "/api/workloads/allocations", params={"institution_id": "inst"},
        json={**payload, "is_override": True, "override_reason": "Industry specialist"},
    )
    assert created.status_code == 201
    assert created.json()["created_by"] == "owner"


def test_suggestion_api_is_read_only(workload_api):
    response = workload_api.post(
        "/api/workloads/suggestions", params={"institution_id": "inst"},
        json={"subject_component_id": "component", "division_id": "division", "weekly_hours": 4},
    )
    assert response.status_code == 200
    assert {item["teacher_id"] for item in response.json()["candidates"]} == {"preferred", "lower-rank"}
    assert workload_api.get(
        "/api/workloads/allocations", params={"institution_id": "inst"}
    ).json() == []
