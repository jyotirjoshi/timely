"""
Teacher Absence router — mark absent, auto-find substitutes, apply to timetable.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    Assignment, Institution, SubstituteAssignment,
    Teacher, TeacherAbsence, Timetable, User
)

router = APIRouter()


class AbsenceIn(BaseModel):
    teacher_id: str
    date: date
    reason: str = "sick leave"
    institution_id: str


class SubstituteConfirm(BaseModel):
    """Map of assignment_id → substitute_teacher_id chosen by the admin."""
    substitutes: dict[str, str]  # {assignment_id: teacher_id}


def _s_absence(a: TeacherAbsence) -> dict:
    return {
        "id": a.id, "teacher_id": a.teacher_id,
        "date": a.date.isoformat(), "reason": a.reason,
        "institution_id": a.institution_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _day_index(absence_date: date, inst: Institution) -> Optional[int]:
    """
    Convert a calendar date to the day-of-week index used in the timetable grid.
    Returns 0=Mon, 1=Tue, ... 4=Fri  (or None if it's a weekend).
    """
    # Python weekday(): 0=Monday, 6=Sunday
    wd = absence_date.weekday()
    if wd >= inst.days_per_week:
        return None
    return wd


def _find_substitutes_for_absence(
    absence: TeacherAbsence,
    timetable: Timetable,
    db: Session,
) -> list[dict]:
    """
    For each assignment the absent teacher has on the affected day,
    find free qualified teachers and return suggestions.
    """
    inst = db.query(Institution).filter(
        Institution.id == absence.institution_id).first()
    if not inst:
        return []

    day_idx = _day_index(absence.date, inst)
    if day_idx is None:
        return []  # weekend

    # All teachers in this institution
    all_teachers = db.query(Teacher).filter(
        Teacher.institution_id == absence.institution_id).all()
    teacher_map = {t.id: t for t in all_teachers}

    # Assignments the absent teacher has on that day-of-week
    affected = [a for a in timetable.assignments
                if a.teacher_id == absence.teacher_id and a.day == day_idx]

    # Build busy-at-slot lookup for all teachers
    busy: dict[str, set] = defaultdict(set)
    for a in timetable.assignments:
        if a.day == day_idx:
            busy[a.teacher_id].add(a.period)

    results = []
    for a in sorted(affected, key=lambda x: x.period):
        candidates = []
        for tid, teacher in teacher_map.items():
            if tid == absence.teacher_id:
                continue
            # Skip if busy at this period
            if a.period in busy[tid]:
                continue
            # Skip if teacher marked unavailable for this recurring slot
            unavail = set(map(tuple, teacher.unavailable or []))
            if (day_idx, a.period) in unavail:
                continue
            # Check if teacher is absent on this date too
            already_absent = db.query(TeacherAbsence).filter(
                TeacherAbsence.teacher_id == tid,
                TeacherAbsence.date == absence.date
            ).first()
            if already_absent:
                continue
            candidates.append({
                "teacher_id": tid,
                "teacher_name": teacher.name,
                "subjects": teacher.subjects,
            })

        results.append({
            "assignment_id": a.id,
            "period": a.period,
            "subject_id": a.subject_id,
            "class_id": a.class_id,
            "room_id": a.room_id,
            "candidates": candidates[:5],  # top 5
        })

    return results


@router.get("")
def list_absences(institution_id: str, db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    return [_s_absence(a) for a in
            db.query(TeacherAbsence)
              .filter(TeacherAbsence.institution_id == institution_id)
              .order_by(TeacherAbsence.date.desc())
              .all()]


@router.post("", status_code=201)
def create_absence(body: AbsenceIn, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    # Prevent duplicate
    existing = db.query(TeacherAbsence).filter(
        TeacherAbsence.teacher_id == body.teacher_id,
        TeacherAbsence.date == body.date
    ).first()
    if existing:
        return _s_absence(existing)

    absence = TeacherAbsence(
        institution_id=body.institution_id,
        teacher_id=body.teacher_id,
        date=body.date,
        reason=body.reason,
    )
    db.add(absence); db.commit(); db.refresh(absence)
    return _s_absence(absence)


@router.delete("/{absence_id}", status_code=204)
def delete_absence(absence_id: str, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    a = db.query(TeacherAbsence).filter(TeacherAbsence.id == absence_id).first()
    if not a: raise HTTPException(404, "Absence not found")
    # Also remove substitute assignments
    db.query(SubstituteAssignment).filter(
        SubstituteAssignment.absence_id == absence_id).delete()
    db.delete(a); db.commit()


@router.get("/{absence_id}/substitutes")
def get_substitute_suggestions(
    absence_id: str, timetable_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """
    For a given absence, return per-period substitute suggestions
    based on the active published/solved timetable.
    """
    absence = db.query(TeacherAbsence).filter(TeacherAbsence.id == absence_id).first()
    if not absence: raise HTTPException(404, "Absence not found")

    timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not timetable: raise HTTPException(404, "Timetable not found")

    suggestions = _find_substitutes_for_absence(absence, timetable, db)

    absent_teacher = db.query(Teacher).filter(Teacher.id == absence.teacher_id).first()

    return {
        "absence_id": absence_id,
        "teacher_name": absent_teacher.name if absent_teacher else absence.teacher_id,
        "date": absence.date.isoformat(),
        "reason": absence.reason,
        "affected_periods": len(suggestions),
        "suggestions": suggestions,
    }


@router.post("/{absence_id}/apply-substitutes")
def apply_substitutes(
    absence_id: str, timetable_id: str,
    body: SubstituteConfirm,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """
    Apply confirmed substitute assignments.
    This does NOT modify the base timetable permanently —
    it records substitute overrides for that specific date.
    """
    absence = db.query(TeacherAbsence).filter(TeacherAbsence.id == absence_id).first()
    if not absence: raise HTTPException(404, "Absence not found")

    timetable = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not timetable: raise HTTPException(404, "Timetable not found")

    applied = []
    for assignment_id, sub_teacher_id in body.substitutes.items():
        a = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not a:
            continue

        # Remove old substitute if exists
        db.query(SubstituteAssignment).filter(
            SubstituteAssignment.absence_id == absence_id,
            SubstituteAssignment.assignment_id == assignment_id
        ).delete()

        sub = SubstituteAssignment(
            absence_id=absence_id,
            assignment_id=assignment_id,
            original_teacher_id=absence.teacher_id,
            substitute_teacher_id=sub_teacher_id,
            confirmed=True,
        )
        db.add(sub)
        applied.append({
            "assignment_id": assignment_id,
            "substitute_teacher_id": sub_teacher_id,
            "period": a.period,
        })

    db.commit()
    return {
        "message": f"Applied {len(applied)} substitute assignment(s)",
        "applied": applied,
    }


@router.get("/{absence_id}/confirmed-substitutes")
def get_confirmed_substitutes(
    absence_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    subs = db.query(SubstituteAssignment).filter(
        SubstituteAssignment.absence_id == absence_id,
        SubstituteAssignment.confirmed == True
    ).all()
    return [
        {
            "assignment_id": s.assignment_id,
            "original_teacher_id": s.original_teacher_id,
            "substitute_teacher_id": s.substitute_teacher_id,
        }
        for s in subs
    ]
