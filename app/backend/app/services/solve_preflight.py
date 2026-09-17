"""Feasibility checks that run before the CP-SAT solver is submitted."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import (
    AcademicTerm, DepartmentCalendar, Division, FacultyShift, Program, Room,
    SchedulingActivity, SubjectComponent, Teacher,
)
from app.services.calendars import valid_activity_windows, window_within_shift


@dataclass(frozen=True)
class PreflightIssue:
    code: str
    entities: tuple[str, ...]
    demand: float | None
    capacity: float | None
    message: str


@dataclass(frozen=True)
class PreflightReport:
    term_id: str
    hard_feasible: bool
    issues: tuple[PreflightIssue, ...]


def preflight(db: Session, institution_id: str, term_id: str) -> PreflightReport:
    term = db.query(AcademicTerm).filter(
        AcademicTerm.id == term_id, AcademicTerm.institution_id == institution_id,
    ).first()
    if term is None:
        raise ValueError("Academic term not found")

    activities = db.query(SchedulingActivity).filter(
        SchedulingActivity.institution_id == institution_id,
        SchedulingActivity.term_id == term_id,
    ).all()
    division_ids = {activity.division_id for activity in activities}
    component_ids = {activity.subject_component_id for activity in activities}
    divisions = {value.id: value for value in db.query(Division).filter(
        Division.institution_id == institution_id, Division.id.in_(division_ids),
    ).all()} if division_ids else {}
    programs = {value.id: value for value in db.query(Program).filter(
        Program.institution_id == institution_id,
    ).all()}
    calendars = {value.id: value for value in db.query(DepartmentCalendar).filter(
        DepartmentCalendar.institution_id == institution_id,
    ).all()}
    components = {value.id: value for value in db.query(SubjectComponent).filter(
        SubjectComponent.institution_id == institution_id,
        SubjectComponent.id.in_(component_ids),
    ).all()} if component_ids else {}
    teachers = {value.id: value for value in db.query(Teacher).filter(
        Teacher.institution_id == institution_id,
    ).all()}
    rooms = db.query(Room).filter(Room.institution_id == institution_id).all()
    shifts_by_teacher: dict[str, list[FacultyShift]] = defaultdict(list)
    for shift in db.query(FacultyShift).filter(FacultyShift.institution_id == institution_id).all():
        shifts_by_teacher[shift.teacher_id].append(shift)

    issues: list[PreflightIssue] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def add(code: str, entities: list[str], message: str, demand=None, capacity=None):
        key = (code, tuple(entities))
        if key in seen:
            return
        seen.add(key)
        issues.append(PreflightIssue(code, tuple(entities), demand, capacity, message))

    by_division: dict[str, list[SchedulingActivity]] = defaultdict(list)
    forced_teacher_minutes: dict[str, int] = defaultdict(int)
    for activity in activities:
        by_division[activity.division_id].append(activity)
        division = divisions.get(activity.division_id)
        if division is None or not division.calendar_id or division.calendar_id not in calendars:
            add("MISSING_CALENDAR", [activity.division_id], "Division has no active department calendar")
            continue
        calendar = calendars[division.calendar_id]
        windows = valid_activity_windows(calendar, activity.duration_minutes)
        if not windows:
            add(
                "NO_CONTIGUOUS_WINDOW", [activity.id, calendar.id],
                "Calendar has no contiguous teaching window for this activity duration",
                activity.duration_minutes, 0,
            )

        component = components.get(activity.subject_component_id)
        qualified = [
            teachers[teacher_id]
            for teacher_id in activity.faculty_pool or []
            if teacher_id in teachers
            and component is not None
            and component.subject_id in (teachers[teacher_id].subjects or [])
        ]
        if not qualified:
            add(
                "NO_QUALIFIED_FACULTY", [activity.id],
                "Activity has no qualified faculty member in its pool",
                1, 0,
            )
        else:
            if len(qualified) == 1:
                forced_teacher_minutes[qualified[0].id] += activity.duration_minutes
            faculty_has_window = False
            for teacher in qualified:
                shifts = shifts_by_teacher.get(teacher.id, [])
                if not shifts:
                    faculty_has_window = True
                    break
                if any(
                    shift.day == window.day
                    and window_within_shift(
                        window.start, window.end, shift.start_time, shift.end_time
                    )
                    for shift in shifts for window in windows
                ):
                    faculty_has_window = True
                    break
            if not faculty_has_window:
                add(
                    "FACULTY_SHIFT_EXCLUSION", [activity.id],
                    "No qualified faculty shift contains a valid activity window",
                    activity.duration_minutes, 0,
                )

        compatible = [room for room in rooms if room.type == activity.room_type]
        if not compatible:
            add(
                "NO_COMPATIBLE_ROOM", [activity.id],
                f"No room matches required type {activity.room_type}", 1, 0,
            )
        else:
            required_capacity = division.size
            largest = max(room.capacity for room in compatible)
            if largest < required_capacity:
                code = "LAB_CAPACITY_SHORTAGE" if activity.room_type == "lab" else "ROOM_CAPACITY_SHORTAGE"
                add(
                    code, [activity.id], "No compatible room has enough capacity",
                    required_capacity, largest,
                )

    for teacher_id, demand_minutes in forced_teacher_minutes.items():
        capacity_minutes = teachers[teacher_id].max_per_week * 60
        if demand_minutes > capacity_minutes:
            add(
                "FACULTY_POOL_OVERLOAD", [teacher_id],
                "Activities forced to this faculty member exceed weekly workload capacity",
                demand_minutes, capacity_minutes,
            )

    for division_id, division_activities in by_division.items():
        division = divisions.get(division_id)
        calendar = calendars.get(division.calendar_id) if division else None
        if calendar is None:
            continue
        teaching_periods = [period for period in calendar.periods if period.kind == "teaching"]
        capacity_minutes = sum(
            (period.end_time.hour * 60 + period.end_time.minute)
            - (period.start_time.hour * 60 + period.start_time.minute)
            for period in teaching_periods
        )
        demand_minutes = sum(activity.duration_minutes for activity in division_activities)
        if demand_minutes > capacity_minutes:
            add(
                "DIVISION_HOURS_OVERFLOW", [division_id],
                "Division requires more teaching time than its calendar provides",
                demand_minutes, capacity_minutes,
            )
        teaching_days = {period.day for period in teaching_periods}
        lab_count = sum(
            1 for activity in division_activities
            if activity.room_type == "lab"
            or components.get(activity.subject_component_id, None)
            and components[activity.subject_component_id].component_type == "practical"
        )
        lab_capacity = len(teaching_days) * 2
        if lab_count > lab_capacity:
            add(
                "DAILY_LAB_LIMIT", [division_id],
                "More than two labs per day would be unavoidable for this division",
                lab_count, lab_capacity,
            )

    return PreflightReport(term_id, not issues, tuple(issues))
