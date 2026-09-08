from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import (
    Assignment,
    Class,
    Holiday,
    Institution,
    Lesson,
    Room,
    SolveJob,
    Subject,
    Teacher,
    TeacherAbsence,
    Timetable,
    User,
)


@pytest.fixture()
def tenant_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    db = TestingSession()
    own_inst = Institution(id="inst-own", name="Own College")
    foreign_inst = Institution(id="inst-foreign", name="Foreign College")
    owner = User(
        id="user-owner",
        email="owner@example.com",
        hashed_password="unused",
        role="owner",
        institution_id=own_inst.id,
    )
    db.add_all([own_inst, foreign_inst, owner])
    db.flush()

    own_teacher = Teacher(id="teacher-own", institution_id=own_inst.id, name="Own Teacher")
    foreign_teacher = Teacher(id="teacher-foreign", institution_id=foreign_inst.id, name="Foreign Teacher")
    own_room = Room(id="room-own", institution_id=own_inst.id, name="Own Room")
    foreign_room = Room(id="room-foreign", institution_id=foreign_inst.id, name="Foreign Room")
    own_class = Class(id="class-own", institution_id=own_inst.id, name="Own Class")
    foreign_class = Class(id="class-foreign", institution_id=foreign_inst.id, name="Foreign Class")
    own_subject = Subject(id="subject-own", institution_id=own_inst.id, name="Own Subject")
    foreign_subject = Subject(id="subject-foreign", institution_id=foreign_inst.id, name="Foreign Subject")
    db.add_all([
        own_teacher, foreign_teacher, own_room, foreign_room,
        own_class, foreign_class, own_subject, foreign_subject,
    ])
    db.flush()

    own_lesson = Lesson(
        id="lesson-own", institution_id=own_inst.id, class_id=own_class.id,
        subject_id=own_subject.id, teacher_id=own_teacher.id,
    )
    foreign_lesson = Lesson(
        id="lesson-foreign", institution_id=foreign_inst.id, class_id=foreign_class.id,
        subject_id=foreign_subject.id, teacher_id=foreign_teacher.id,
    )
    own_timetable = Timetable(id="timetable-own", institution_id=own_inst.id, name="Own Timetable")
    foreign_timetable = Timetable(id="timetable-foreign", institution_id=foreign_inst.id, name="Foreign Timetable")
    own_holiday = Holiday(id="holiday-own", institution_id=own_inst.id, date=date(2026, 1, 1), name="Own Holiday")
    foreign_holiday = Holiday(id="holiday-foreign", institution_id=foreign_inst.id, date=date(2026, 1, 2), name="Foreign Holiday")
    own_absence = TeacherAbsence(
        id="absence-own", institution_id=own_inst.id, teacher_id=own_teacher.id, date=date(2026, 9, 8),
    )
    foreign_absence = TeacherAbsence(
        id="absence-foreign", institution_id=foreign_inst.id, teacher_id=foreign_teacher.id, date=date(2026, 9, 8),
    )
    own_job = SolveJob(id="job-own", institution_id=own_inst.id)
    foreign_job = SolveJob(id="job-foreign", institution_id=foreign_inst.id)
    db.add_all([
        own_lesson, foreign_lesson, own_timetable, foreign_timetable,
        own_holiday, foreign_holiday, own_absence, foreign_absence,
        own_job, foreign_job,
    ])
    db.flush()
    db.add_all([
        Assignment(
            id="assignment-own", timetable_id=own_timetable.id, lesson_id=own_lesson.id,
            class_id=own_class.id, subject_id=own_subject.id, teacher_id=own_teacher.id,
            room_id=own_room.id, day=0, period=0,
        ),
        Assignment(
            id="assignment-foreign", timetable_id=foreign_timetable.id, lesson_id=foreign_lesson.id,
            class_id=foreign_class.id, subject_id=foreign_subject.id, teacher_id=foreign_teacher.id,
            room_id=foreign_room.id, day=0, period=0,
        ),
    ])
    db.commit()

    current_user = {"value": owner}

    def override_db():
        yield db

    def override_user():
        return current_user["value"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)
    try:
        yield client, db, current_user
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.parametrize("path", [
    "/api/teachers", "/api/rooms", "/api/classes", "/api/subjects",
    "/api/lessons", "/api/timetables", "/api/absences", "/api/holidays",
])
def test_cross_institution_lists_are_forbidden(tenant_api, path):
    client, _, _ = tenant_api
    response = client.get(path, params={"institution_id": "inst-foreign"})
    assert response.status_code == 403


@pytest.mark.parametrize(("path", "payload"), [
    ("/api/teachers", {"name": "Injected Teacher"}),
    ("/api/rooms", {"name": "Injected Room"}),
    ("/api/classes", {"name": "Injected Class"}),
    ("/api/subjects", {"name": "Injected Subject"}),
    ("/api/lessons", {"class_id": "class-foreign", "subject_id": "subject-foreign", "teacher_id": "teacher-foreign"}),
    ("/api/holidays", {"date": "2026-09-09", "name": "Injected Holiday"}),
])
def test_cross_institution_creates_are_forbidden(tenant_api, path, payload):
    client, _, _ = tenant_api
    response = client.post(path, params={"institution_id": "inst-foreign"}, json=payload)
    assert response.status_code == 403


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/api/teachers/teacher-foreign", None),
    ("patch", "/api/teachers/teacher-foreign", {"name": "Stolen"}),
    ("delete", "/api/teachers/teacher-foreign", None),
    ("get", "/api/rooms/room-foreign", None),
    ("patch", "/api/rooms/room-foreign", {"name": "Stolen"}),
    ("delete", "/api/rooms/room-foreign", None),
    ("get", "/api/classes/class-foreign", None),
    ("patch", "/api/classes/class-foreign", {"name": "Stolen"}),
    ("delete", "/api/classes/class-foreign", None),
    ("get", "/api/subjects/subject-foreign", None),
    ("patch", "/api/subjects/subject-foreign", {"name": "Stolen"}),
    ("delete", "/api/subjects/subject-foreign", None),
    ("patch", "/api/lessons/lesson-foreign", {"pinned": {"day": 0, "period": 1}}),
    ("delete", "/api/lessons/lesson-foreign", None),
    ("get", "/api/timetables/timetable-foreign", None),
    ("patch", "/api/timetables/timetable-foreign/publish", None),
    ("delete", "/api/timetables/timetable-foreign", None),
    ("delete", "/api/holidays/holiday-foreign", None),
    ("delete", "/api/absences/absence-foreign", None),
    ("get", "/api/solve/job-foreign", None),
])
def test_direct_foreign_resource_ids_are_not_found(tenant_api, method, path, payload):
    client, _, _ = tenant_api
    response = client.request(method, path, json=payload)
    assert response.status_code == 404


@pytest.mark.parametrize("method,payload", [
    ("get", None),
    ("patch", {"name": "Stolen"}),
])
def test_cross_institution_institution_path_is_forbidden(tenant_api, method, payload):
    client, _, _ = tenant_api
    response = client.request(method, "/api/institutions/inst-foreign", json=payload)
    assert response.status_code == 403


def test_related_foreign_ids_are_rejected(tenant_api):
    client, _, _ = tenant_api

    lesson = client.post(
        "/api/lessons",
        params={"institution_id": "inst-own"},
        json={"class_id": "class-foreign", "subject_id": "subject-own", "teacher_id": "teacher-own"},
    )
    absence = client.post(
        "/api/absences",
        json={"institution_id": "inst-own", "teacher_id": "teacher-foreign", "date": "2026-09-09"},
    )
    assignment = client.patch(
        "/api/timetables/timetable-own/assignments/assignment-own",
        json={"day": 1, "period": 1, "room_id": "room-foreign"},
    )

    assert lesson.status_code == 404
    assert absence.status_code == 404
    assert assignment.status_code == 404


@pytest.mark.parametrize("role", ["faculty", "student", "teacher"])
@pytest.mark.parametrize(("method", "path", "payload"), [
    ("post", "/api/teachers?institution_id=inst-own", {"name": "Nope"}),
    ("patch", "/api/institutions/inst-own", {"name": "Nope"}),
    ("post", "/api/solve", {"institution_id": "inst-own", "time_limit_s": 1}),
    ("post", "/api/agent/apply-plan", {"timetable_id": "timetable-own", "changes": []}),
])
def test_non_planning_roles_cannot_mutate_or_solve(tenant_api, role, method, path, payload):
    client, db, current_user = tenant_api
    user = current_user["value"]
    user.role = role
    db.commit()

    response = client.request(method, path, json=payload)
    assert response.status_code == 403


def test_same_tenant_owner_crud_remains_compatible(tenant_api):
    client, _, _ = tenant_api

    created = client.post(
        "/api/teachers", params={"institution_id": "inst-own"}, json={"name": "New Teacher"}
    )
    assert created.status_code == 201
    teacher_id = created.json()["id"]
    assert client.get(f"/api/teachers/{teacher_id}").status_code == 200
    assert client.patch(f"/api/teachers/{teacher_id}", json={"name": "Renamed"}).json()["name"] == "Renamed"
    assert client.delete(f"/api/teachers/{teacher_id}").status_code == 204
