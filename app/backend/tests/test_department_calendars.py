from datetime import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import Institution, Teacher, User
from app.services.calendars import (
    CalendarValidationError,
    ranges_overlap,
    valid_activity_windows,
    validate_periods,
    window_within_shift,
)


class Period:
    def __init__(self, period_id, day, ordinal, start, end, kind="teaching"):
        self.id = period_id
        self.day = day
        self.ordinal = ordinal
        self.start_time = start
        self.end_time = end
        self.kind = kind


class Calendar:
    def __init__(self, periods):
        self.periods = periods


@pytest.fixture()
def calendar_api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = Session()
    own = Institution(id="inst-own", name="Own University")
    foreign = Institution(id="inst-foreign", name="Foreign University")
    owner = User(
        id="owner", email="owner@own.test", hashed_password="unused",
        role="owner", institution_id=own.id,
    )
    teacher = Teacher(id="teacher-own", institution_id=own.id, name="Own Teacher")
    foreign_teacher = Teacher(
        id="teacher-foreign", institution_id=foreign.id, name="Foreign Teacher"
    )
    db.add_all([own, foreign, owner, teacher, foreign_teacher])
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_half_open_time_ranges_only_overlap_when_time_is_shared():
    assert ranges_overlap(time(9), time(10), time(9, 30), time(10, 30))
    assert not ranges_overlap(time(9), time(10), time(10), time(11))


def test_department_calendars_can_have_different_period_times():
    engineering = Calendar([
        Period("eng-1", 0, 0, time(8), time(9)),
        Period("eng-2", 0, 1, time(9), time(10)),
    ])
    arts = Calendar([
        Period("arts-1", 0, 0, time(9, 30), time(10, 30)),
        Period("arts-2", 0, 1, time(10, 30), time(11, 30)),
    ])

    assert valid_activity_windows(engineering, 120)[0].start == time(8)
    assert valid_activity_windows(arts, 120)[0].start == time(9, 30)


def test_breaks_split_windows_and_cannot_be_scheduled_through():
    calendar = Calendar([
        Period("p1", 0, 0, time(9), time(10)),
        Period("break", 0, 1, time(10), time(10, 15), "break"),
        Period("p2", 0, 2, time(10, 15), time(11, 15)),
        Period("p3", 0, 3, time(11, 15), time(12, 15)),
    ])

    windows = valid_activity_windows(calendar, 120)

    assert [(window.start, window.end) for window in windows] == [
        (time(10, 15), time(12, 15))
    ]


def test_non_monotonic_or_overlapping_periods_are_rejected():
    periods = [
        Period("p1", 0, 0, time(10), time(11)),
        Period("p2", 0, 1, time(9), time(10)),
    ]

    with pytest.raises(CalendarValidationError, match="chronological"):
        validate_periods(periods)


def test_activity_window_must_be_contained_in_faculty_shift():
    assert window_within_shift(time(9), time(11), time(8, 30), time(12))
    assert not window_within_shift(time(8), time(10), time(8, 30), time(12))
    assert not window_within_shift(time(11), time(12, 30), time(8, 30), time(12))


def test_department_calendar_crud_preserves_real_local_times(calendar_api):
    school = calendar_api.post(
        "/api/departments/schools",
        params={"institution_id": "inst-own"},
        json={"name": "School of Engineering", "code": "ENG"},
    )
    assert school.status_code == 201
    department = calendar_api.post(
        "/api/departments",
        params={"institution_id": "inst-own"},
        json={"school_id": school.json()["id"], "name": "Computer Science", "code": "CSE"},
    )
    assert department.status_code == 201

    created = calendar_api.post(
        f"/api/departments/{department.json()['id']}/calendars",
        json={
            "name": "Morning shift",
            "timezone": "Asia/Kolkata",
            "periods": [
                {"day": 0, "ordinal": 0, "name": "P1", "start_time": "08:30", "end_time": "09:30"},
                {"day": 0, "ordinal": 1, "name": "Break", "kind": "break", "start_time": "09:30", "end_time": "09:45"},
                {"day": 0, "ordinal": 2, "name": "P2", "start_time": "09:45", "end_time": "10:45"},
            ],
        },
    )

    assert created.status_code == 201
    assert created.json()["periods"][0]["start_time"] == "08:30:00"
    fetched = calendar_api.get(f"/api/departments/calendars/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["timezone"] == "Asia/Kolkata"


def test_calendar_api_rejects_foreign_scope_invalid_periods_and_foreign_shift_teacher(calendar_api):
    assert calendar_api.post(
        "/api/departments/schools",
        params={"institution_id": "inst-foreign"},
        json={"name": "Injected", "code": "BAD"},
    ).status_code == 403

    school = calendar_api.post(
        "/api/departments/schools",
        params={"institution_id": "inst-own"},
        json={"name": "Science", "code": "SCI"},
    ).json()
    department = calendar_api.post(
        "/api/departments",
        params={"institution_id": "inst-own"},
        json={"school_id": school["id"], "name": "Physics", "code": "PHY"},
    ).json()
    invalid = calendar_api.post(
        f"/api/departments/{department['id']}/calendars",
        json={
            "name": "Broken",
            "periods": [
                {"day": 0, "ordinal": 0, "name": "P1", "start_time": "10:00", "end_time": "11:00"},
                {"day": 0, "ordinal": 1, "name": "P2", "start_time": "09:00", "end_time": "10:00"},
            ],
        },
    )
    assert invalid.status_code == 422

    shift = calendar_api.post(
        "/api/departments/faculty-shifts",
        params={"institution_id": "inst-own"},
        json={
            "teacher_id": "teacher-foreign", "department_id": department["id"],
            "day": 0, "start_time": "08:00", "end_time": "13:00",
        },
    )
    assert shift.status_code == 404
