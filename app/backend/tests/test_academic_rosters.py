import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import Department, Institution, School, User
from app.services.roster_import import parse_roster_csv


@pytest.fixture()
def academic_api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = Session()
    own = Institution(id="inst-own", name="Own University")
    foreign = Institution(id="inst-foreign", name="Foreign University")
    owner = User(
        id="owner", email="owner@test", hashed_password="unused",
        role="owner", institution_id=own.id,
    )
    own_school = School(id="school-own", institution_id=own.id, name="Engineering", code="ENG")
    foreign_school = School(id="school-foreign", institution_id=foreign.id, name="Arts", code="ART")
    own_department = Department(
        id="department-own", institution_id=own.id, school_id=own_school.id,
        name="Computer Science", code="CSE",
    )
    foreign_department = Department(
        id="department-foreign", institution_id=foreign.id, school_id=foreign_school.id,
        name="History", code="HIS",
    )
    db.add_all([own, foreign, owner, own_school, foreign_school, own_department, foreign_department])
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_roster_parser_reports_rows_and_duplicate_identifiers():
    result = parse_roster_csv(
        "student_number,name,email,batch\nS001,Asha,asha@test,A\nS001,Ravi,ravi@test,B\n",
        "division-1",
    )

    assert not result.valid
    assert result.rows[0].student_number == "S001"
    assert result.errors[0].row == 3
    assert "duplicate" in result.errors[0].message.lower()


def test_program_division_batch_and_cross_department_rules(academic_api):
    client, _ = academic_api
    program = client.post(
        "/api/academics/programs", params={"institution_id": "inst-own"},
        json={"department_id": "department-own", "name": "B.Tech CSE", "code": "BTCSE"},
    )
    assert program.status_code == 201
    assert client.post(
        "/api/academics/programs", params={"institution_id": "inst-own"},
        json={"department_id": "department-foreign", "name": "Injected", "code": "BAD"},
    ).status_code == 404

    division = client.post(
        "/api/academics/divisions", params={"institution_id": "inst-own"},
        json={"program_id": program.json()["id"], "name": "FY-A", "academic_year": 1, "semester": 1},
    )
    assert division.status_code == 201
    batch = client.post(
        "/api/academics/batches", params={"institution_id": "inst-own"},
        json={"division_id": division.json()["id"], "name": "Lab A"},
    )
    assert batch.status_code == 201
    assert batch.json()["division_id"] == division.json()["id"]


def test_student_numbers_are_unique_per_institution_and_enrollment_validates_batch(academic_api):
    client, _ = academic_api
    program = client.post(
        "/api/academics/programs", params={"institution_id": "inst-own"},
        json={"department_id": "department-own", "name": "BSc CS", "code": "BSCS"},
    ).json()
    division = client.post(
        "/api/academics/divisions", params={"institution_id": "inst-own"},
        json={"program_id": program["id"], "name": "SY-A", "academic_year": 2, "semester": 3},
    ).json()
    other_division = client.post(
        "/api/academics/divisions", params={"institution_id": "inst-own"},
        json={"program_id": program["id"], "name": "SY-B", "academic_year": 2, "semester": 3},
    ).json()
    wrong_batch = client.post(
        "/api/academics/batches", params={"institution_id": "inst-own"},
        json={"division_id": other_division["id"], "name": "Wrong Lab"},
    ).json()
    student = client.post(
        "/api/academics/students", params={"institution_id": "inst-own"},
        json={"student_number": "S001", "name": "Asha", "email": "asha@test"},
    )
    assert student.status_code == 201
    assert client.post(
        "/api/academics/students", params={"institution_id": "inst-own"},
        json={"student_number": "S001", "name": "Duplicate"},
    ).status_code == 409
    enrollment = client.post(
        "/api/academics/enrollments", params={"institution_id": "inst-own"},
        json={"student_id": student.json()["id"], "division_id": division["id"], "batch_id": wrong_batch["id"]},
    )
    assert enrollment.status_code == 422


def test_roster_import_is_atomic_when_any_row_is_invalid(academic_api):
    client, _ = academic_api
    program = client.post(
        "/api/academics/programs", params={"institution_id": "inst-own"},
        json={"department_id": "department-own", "name": "MCA", "code": "MCA"},
    ).json()
    division = client.post(
        "/api/academics/divisions", params={"institution_id": "inst-own"},
        json={"program_id": program["id"], "name": "MCA-A", "academic_year": 1, "semester": 1},
    ).json()
    content = b"student_number,name,email,batch\nS101,Valid,valid@test,\n,Missing Id,bad@test,\n"

    response = client.post(
        "/api/academics/rosters/import",
        params={"institution_id": "inst-own", "division_id": division["id"]},
        files={"file": ("roster.csv", content, "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["errors"][0]["row"] == 3
    assert client.get(
        "/api/academics/students", params={"institution_id": "inst-own"}
    ).json() == []
