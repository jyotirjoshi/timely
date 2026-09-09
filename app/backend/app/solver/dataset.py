"""Build multi-calendar solver candidates from persisted academic planning data."""
from __future__ import annotations

from collections import defaultdict
from datetime import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AcademicTerm, Batch, DepartmentCalendar, Division, Enrollment, FacultyPreference,
    FacultyShift, Program, Room, SchedulingActivity, SubjectComponent, Teacher,
    WorkloadAllocation,
)
from app.services.calendars import valid_activity_windows, window_within_shift


def _minute(value: time) -> int:
    return value.hour * 60 + value.minute


def _pinned_minute(value: str | None) -> int | None:
    if not value:
        return None
    parsed = time.fromisoformat(value)
    return _minute(parsed)


def build_solver_dataset(db: Session, institution_id: str, term_id: str) -> dict:
    term = db.query(AcademicTerm).filter(
        AcademicTerm.id == term_id, AcademicTerm.institution_id == institution_id,
    ).first()
    if term is None:
        raise ValueError("Academic term not found")

    activities = db.query(SchedulingActivity).filter(
        SchedulingActivity.institution_id == institution_id,
        SchedulingActivity.term_id == term_id,
    ).all()
    divisions = {value.id: value for value in db.query(Division).filter(
        Division.institution_id == institution_id,
    ).all()}
    programs = {value.id: value for value in db.query(Program).filter(
        Program.institution_id == institution_id,
    ).all()}
    calendars = {value.id: value for value in db.query(DepartmentCalendar).filter(
        DepartmentCalendar.institution_id == institution_id,
    ).all()}
    components = {value.id: value for value in db.query(SubjectComponent).filter(
        SubjectComponent.institution_id == institution_id,
    ).all()}
    teachers = {value.id: value for value in db.query(Teacher).filter(
        Teacher.institution_id == institution_id,
    ).all()}
    rooms = db.query(Room).filter(Room.institution_id == institution_id).all()
    preferences = {
        (value.teacher_id, value.subject_component_id): value.rank
        for value in db.query(FacultyPreference).filter(
            FacultyPreference.institution_id == institution_id,
        ).all()
    }
    allocations: dict[tuple[str, str], list[str]] = defaultdict(list)
    for value in db.query(WorkloadAllocation).filter(
        WorkloadAllocation.institution_id == institution_id,
    ).all():
        allocations[(value.subject_component_id, value.division_id)].append(value.teacher_id)
    shifts: dict[str, list[FacultyShift]] = defaultdict(list)
    for value in db.query(FacultyShift).filter(FacultyShift.institution_id == institution_id).all():
        shifts[value.teacher_id].append(value)
    batch_counts = dict(db.query(
        Enrollment.batch_id, func.count(Enrollment.id),
    ).filter(
        Enrollment.institution_id == institution_id,
        Enrollment.batch_id.is_not(None),
    ).group_by(Enrollment.batch_id).all())

    output_activities = []
    for activity in activities:
        division = divisions[activity.division_id]
        calendar = calendars.get(division.calendar_id)
        component = components[activity.subject_component_id]
        if calendar is None:
            candidate_windows = []
        else:
            candidate_windows = valid_activity_windows(calendar, activity.duration_minutes)

        if component.component_type == "library" and candidate_windows:
            teaching_by_day: dict[int, list] = defaultdict(list)
            for period in calendar.periods:
                if period.kind == "teaching":
                    teaching_by_day[period.day].append(period)
            candidate_windows = [
                window for window in candidate_windows
                if window.start == min(p.start_time for p in teaching_by_day[window.day])
                or window.end == max(p.end_time for p in teaching_by_day[window.day])
            ]

        faculty_ids = list(activity.faculty_pool or [])
        if not faculty_ids:
            faculty_ids = allocations.get((activity.subject_component_id, activity.division_id), [])
        if not faculty_ids:
            faculty_ids = [
                teacher.id for teacher in teachers.values()
                if component.subject_id in (teacher.subjects or [])
            ]
        faculty = [
            teachers[teacher_id] for teacher_id in faculty_ids
            if teacher_id in teachers and component.subject_id in (teachers[teacher_id].subjects or [])
        ]

        required_capacity = batch_counts.get(activity.batch_id, division.size)
        compatible_rooms = [
            room for room in rooms
            if room.type == activity.room_type and room.capacity >= required_capacity
        ]
        pin = activity.pinned or {}
        pinned_start = _pinned_minute(pin.get("start_time"))
        candidates = []
        for window in candidate_windows:
            if pin.get("day") is not None and pin["day"] != window.day:
                continue
            if pinned_start is not None and pinned_start != _minute(window.start):
                continue
            for teacher in faculty:
                if pin.get("teacher_id") and pin["teacher_id"] != teacher.id:
                    continue
                teacher_shifts = shifts.get(teacher.id, [])
                if teacher_shifts and not any(
                    shift.day == window.day
                    and window_within_shift(window.start, window.end, shift.start_time, shift.end_time)
                    for shift in teacher_shifts
                ):
                    continue
                for room in compatible_rooms:
                    if pin.get("room_id") and pin["room_id"] != room.id:
                        continue
                    candidates.append({
                        "day": window.day,
                        "start_minute": _minute(window.start),
                        "end_minute": _minute(window.end),
                        "teacher_id": teacher.id,
                        "room_id": room.id,
                        "period_ids": list(window.period_ids),
                        "preference_rank": preferences.get(
                            (teacher.id, activity.subject_component_id), 100
                        ),
                    })
        output_activities.append({
            "id": activity.id,
            "division_id": activity.division_id,
            "batch_id": activity.batch_id,
            "subject_id": component.subject_id,
            "component_id": component.id,
            "kind": component.component_type,
            "room_type": activity.room_type,
            "duration_minutes": activity.duration_minutes,
            "alternate_week_pattern": activity.alternate_week_pattern,
            "parallel_group": activity.parallel_group,
            "candidates": candidates,
        })

    return {
        "format": "multi_calendar",
        "institution_id": institution_id,
        "term_id": term_id,
        "activities": output_activities,
        "teacher_max_per_day": {
            teacher.id: teacher.max_per_day for teacher in teachers.values()
        },
        "teacher_max_consecutive": 3,
    }
