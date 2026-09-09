from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    AcademicTerm, CalendarPeriod, Department, DepartmentCalendar, Division,
    FacultyShift, Institution, Program, Room, School, SchedulingActivity,
    Subject, SubjectComponent, Teacher,
)
from app.services.solve_preflight import preflight
from app.solver.dataset import build_solver_dataset


@pytest.fixture()
def preflight_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = Session()
    institution = Institution(id="inst", name="University")
    school = School(id="school", institution_id="inst", name="Engineering", code="ENG")
    department = Department(id="dept", institution_id="inst", school_id="school", name="CSE", code="CSE")
    calendar = DepartmentCalendar(
        id="calendar", institution_id="inst", department_id="dept", name="Regular"
    )
    for day in range(5):
        for ordinal, hour in enumerate(range(9, 13)):
            calendar.periods.append(CalendarPeriod(
                institution_id="inst", day=day, ordinal=ordinal, name=f"P{ordinal + 1}",
                start_time=time(hour), end_time=time(hour + 1), kind="teaching",
            ))
    program = Program(id="program", institution_id="inst", department_id="dept", name="B.Tech", code="BT")
    division = Division(
        id="division", institution_id="inst", program_id="program", calendar_id="calendar",
        name="FY-A", academic_year=1, semester=1, size=30,
    )
    term = AcademicTerm(
        id="term", institution_id="inst", name="Odd",
        starts_on=date(2026, 7, 1), ends_on=date(2026, 12, 1),
    )
    subject = Subject(id="subject", institution_id="inst", name="Programming")
    theory = SubjectComponent(
        id="theory", institution_id="inst", department_id="dept", subject_id="subject",
        component_type="theory", weekly_hours=1, duration_minutes=60,
    )
    lab = SubjectComponent(
        id="lab", institution_id="inst", department_id="dept", subject_id="subject",
        component_type="practical", weekly_hours=2, duration_minutes=120, room_type="lab",
    )
    teacher = Teacher(
        id="teacher", institution_id="inst", name="Qualified", subjects=["subject"], max_per_week=25,
    )
    room = Room(id="lab-room", institution_id="inst", name="Lab 1", type="lab", capacity=40)
    classroom = Room(id="classroom", institution_id="inst", name="Room 1", type="classroom", capacity=40)
    db.add_all([
        institution, school, department, calendar, program, division, term,
        subject, theory, lab, teacher, room, classroom,
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_activity(db, activity_id="activity", component="theory", duration=60, room_type="classroom"):
    db.add(SchedulingActivity(
        id=activity_id, institution_id="inst", term_id="term", requirement_id=f"req-{activity_id}",
        occurrence_index=0, division_id="division", subject_component_id=component,
        duration_minutes=duration, faculty_pool=["teacher"], room_type=room_type,
    ))
    db.commit()


def issue_codes(db):
    return {issue.code for issue in preflight(db, "inst", "term").issues}


def test_preflight_accepts_a_feasible_activity(preflight_db):
    add_activity(preflight_db)
    assert preflight(preflight_db, "inst", "term").hard_feasible

    dataset = build_solver_dataset(preflight_db, "inst", "term")
    assert dataset["format"] == "multi_calendar"
    assert dataset["activities"][0]["candidates"][0]["start_minute"] == 540
    assert dataset["activities"][0]["candidates"][0]["end_minute"] == 600


def test_preflight_reports_missing_calendar(preflight_db):
    preflight_db.query(Division).filter_by(id="division").one().calendar_id = None
    add_activity(preflight_db)
    assert "MISSING_CALENDAR" in issue_codes(preflight_db)


def test_preflight_reports_no_qualified_faculty(preflight_db):
    preflight_db.query(Teacher).filter_by(id="teacher").one().subjects = []
    add_activity(preflight_db)
    assert "NO_QUALIFIED_FACULTY" in issue_codes(preflight_db)


def test_preflight_reports_missing_or_undersized_lab(preflight_db):
    preflight_db.query(Room).filter_by(id="lab-room").one().capacity = 20
    add_activity(preflight_db, component="lab", duration=120, room_type="lab")
    assert "LAB_CAPACITY_SHORTAGE" in issue_codes(preflight_db)
    preflight_db.query(Room).delete()
    preflight_db.commit()
    assert "NO_COMPATIBLE_ROOM" in issue_codes(preflight_db)


def test_preflight_reports_contiguous_duration_and_shift_exclusion(preflight_db):
    add_activity(preflight_db, component="lab", duration=300, room_type="lab")
    preflight_db.add(FacultyShift(
        institution_id="inst", teacher_id="teacher", department_id="dept",
        day=0, start_time=time(14), end_time=time(17),
    ))
    preflight_db.commit()
    codes = issue_codes(preflight_db)
    assert "NO_CONTIGUOUS_WINDOW" in codes
    assert "FACULTY_SHIFT_EXCLUSION" in codes


def test_preflight_reports_faculty_and_division_overload(preflight_db):
    teacher = preflight_db.query(Teacher).filter_by(id="teacher").one()
    teacher.max_per_week = 2
    for index in range(5):
        add_activity(preflight_db, f"a-{index}")
    codes = issue_codes(preflight_db)
    assert "FACULTY_POOL_OVERLOAD" in codes

    for index in range(16):
        add_activity(preflight_db, f"extra-{index}")
    assert "DIVISION_HOURS_OVERFLOW" in issue_codes(preflight_db)


def test_preflight_reports_unavoidable_daily_lab_limit(preflight_db):
    for index in range(11):
        add_activity(preflight_db, f"lab-{index}", component="lab", duration=120, room_type="lab")
    assert "DAILY_LAB_LIMIT" in issue_codes(preflight_db)
