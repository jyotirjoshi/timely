from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    AcademicTerm, Batch, CurriculumRequirement, Department, Division, Institution,
    Program, School, SchedulingActivity, Subject, SubjectComponent,
)
from app.services.activity_expansion import expand_requirements


@pytest.fixture()
def curriculum_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = Session()
    institution = Institution(id="inst", name="University")
    school = School(id="school", institution_id="inst", name="Engineering", code="ENG")
    department = Department(id="dept", institution_id="inst", school_id="school", name="CSE", code="CSE")
    program = Program(id="program", institution_id="inst", department_id="dept", name="B.Tech", code="BT")
    division = Division(
        id="division", institution_id="inst", program_id="program",
        name="FY-A", academic_year=1, semester=1,
    )
    batch_a = Batch(id="batch-a", institution_id="inst", division_id="division", name="A")
    batch_b = Batch(id="batch-b", institution_id="inst", division_id="division", name="B")
    term = AcademicTerm(
        id="term", institution_id="inst", name="Odd 2026",
        starts_on=date(2026, 7, 1), ends_on=date(2026, 12, 15),
    )
    subject = Subject(id="subject", institution_id="inst", name="Programming")
    theory = SubjectComponent(
        id="theory", institution_id="inst", department_id="dept", subject_id="subject",
        component_type="theory", weekly_hours=3, duration_minutes=60,
    )
    lab = SubjectComponent(
        id="lab", institution_id="inst", department_id="dept", subject_id="subject",
        component_type="practical", weekly_hours=4, duration_minutes=120, room_type="lab",
    )
    db.add_all([
        institution, school, department, program, division, batch_a, batch_b,
        term, subject, theory, lab,
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_theory_expands_to_single_period_activities_and_lab_stays_fixed(curriculum_db):
    curriculum_db.add_all([
        CurriculumRequirement(
            id="req-theory", institution_id="inst", term_id="term", division_id="division",
            subject_component_id="theory", weekly_count=3, duration_minutes=60,
            faculty_pool=["teacher-a"], room_type="classroom",
        ),
        CurriculumRequirement(
            id="req-lab", institution_id="inst", term_id="term", division_id="division",
            batch_id="batch-a", subject_component_id="lab", weekly_count=2,
            duration_minutes=120, faculty_pool=["teacher-a"], room_type="lab",
        ),
    ])
    curriculum_db.commit()

    result = expand_requirements(curriculum_db, "inst", "term")
    activities = curriculum_db.query(SchedulingActivity).all()

    assert result.created == 5
    assert [a.duration_minutes for a in activities if a.requirement_id == "req-theory"] == [60, 60, 60]
    assert [a.duration_minutes for a in activities if a.requirement_id == "req-lab"] == [120, 120]


def test_parallel_batch_labs_keep_shared_parallel_group(curriculum_db):
    for requirement_id, batch_id in (("req-a", "batch-a"), ("req-b", "batch-b")):
        curriculum_db.add(CurriculumRequirement(
            id=requirement_id, institution_id="inst", term_id="term", division_id="division",
            batch_id=batch_id, subject_component_id="lab", weekly_count=1,
            duration_minutes=120, faculty_pool=[f"teacher-{batch_id}"], room_type="lab",
            parallel_group="programming-lab",
        ))
    curriculum_db.commit()

    expand_requirements(curriculum_db, "inst", "term")
    activities = curriculum_db.query(SchedulingActivity).order_by(SchedulingActivity.batch_id).all()

    assert len(activities) == 2
    assert {activity.parallel_group for activity in activities} == {"programming-lab"}
    assert {activity.batch_id for activity in activities} == {"batch-a", "batch-b"}


def test_reexpansion_is_idempotent_and_preserves_pinned_activity(curriculum_db):
    requirement = CurriculumRequirement(
        id="req", institution_id="inst", term_id="term", division_id="division",
        subject_component_id="theory", weekly_count=2, duration_minutes=60,
        faculty_pool=["teacher-a"], room_type="classroom",
    )
    curriculum_db.add(requirement)
    curriculum_db.commit()
    expand_requirements(curriculum_db, "inst", "term")
    pinned = curriculum_db.query(SchedulingActivity).filter_by(requirement_id="req", occurrence_index=1).one()
    pinned.pinned = {"day": 2, "start_time": "10:00:00", "room_id": "room-a"}
    curriculum_db.commit()

    second = expand_requirements(curriculum_db, "inst", "term")
    activities = curriculum_db.query(SchedulingActivity).filter_by(requirement_id="req").all()

    assert second.created == 0
    assert second.updated == 2
    assert len(activities) == 2
    assert next(a for a in activities if a.occurrence_index == 1).pinned["day"] == 2
