"""Timetables & Assignments CRUD."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Assignment, Timetable, User

router = APIRouter()


class AssignmentUpdate(BaseModel):
    day: int
    period: int
    room_id: str


def _sa(a: Assignment) -> dict:
    return {"id": a.id, "timetable_id": a.timetable_id,
            "lesson_id": a.lesson_id, "class_id": a.class_id,
            "subject_id": a.subject_id, "teacher_id": a.teacher_id,
            "room_id": a.room_id, "day": a.day, "period": a.period}


def _st(t: Timetable, include_assignments: bool = False) -> dict:
    data = {
        "id": t.id, "institution_id": t.institution_id,
        "name": t.name, "status": t.status,
        "soft_score": t.soft_score, "violations": t.violations or [],
        "solve_time_s": t.solve_time_s,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "published_at": t.published_at.isoformat() if t.published_at else None,
    }
    if include_assignments:
        data["assignments"] = [_sa(a) for a in t.assignments]
    return data


@router.get("")
def list_timetables(institution_id: str, db: Session = Depends(get_db),
                    _: User = Depends(get_current_user)):
    return [_st(t) for t in
            db.query(Timetable).filter(Timetable.institution_id == institution_id)
              .order_by(Timetable.created_at.desc()).all()]


@router.get("/{timetable_id}")
def get_timetable(timetable_id: str, db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    t = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not t: raise HTTPException(404, "Timetable not found")
    return _st(t, include_assignments=True)


@router.patch("/{timetable_id}/publish")
def publish_timetable(timetable_id: str, db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    t = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not t: raise HTTPException(404, "Timetable not found")
    t.status = "published"
    t.published_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(t)
    return _st(t)


@router.patch("/{timetable_id}/unpublish")
def unpublish_timetable(timetable_id: str, db: Session = Depends(get_db),
                        _: User = Depends(get_current_user)):
    t = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not t: raise HTTPException(404, "Timetable not found")
    t.status = "solved"
    t.published_at = None
    db.commit(); db.refresh(t)
    return _st(t)


@router.delete("/{timetable_id}", status_code=204)
def delete_timetable(timetable_id: str, db: Session = Depends(get_db),
                     _: User = Depends(get_current_user)):
    t = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not t: raise HTTPException(404, "Timetable not found")
    db.delete(t); db.commit()


@router.patch("/{timetable_id}/assignments/{assignment_id}")
def update_assignment(timetable_id: str, assignment_id: str,
                      body: AssignmentUpdate,
                      db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    """Move a single assignment — used for drag-and-drop editing."""
    t = db.query(Timetable).filter(Timetable.id == timetable_id).first()
    if not t: raise HTTPException(404, "Timetable not found")
    if t.status == "published":
        raise HTTPException(400, "Cannot edit a published timetable")

    a = db.query(Assignment).filter(
        Assignment.id == assignment_id,
        Assignment.timetable_id == timetable_id
    ).first()
    if not a: raise HTTPException(404, "Assignment not found")

    # Conflict check: same class, teacher, or room in the target slot
    conflicts = db.query(Assignment).filter(
        Assignment.timetable_id == timetable_id,
        Assignment.day == body.day,
        Assignment.period == body.period,
        Assignment.id != assignment_id
    ).all()
    clash_reasons = []
    for c in conflicts:
        if c.class_id == a.class_id:
            clash_reasons.append(f"Class already has a lesson in this slot")
        if c.teacher_id == a.teacher_id:
            clash_reasons.append(f"Teacher already has a lesson in this slot")
        if c.room_id == body.room_id:
            clash_reasons.append(f"Room is already occupied in this slot")
    if clash_reasons:
        raise HTTPException(409, {"conflicts": list(set(clash_reasons))})

    a.day = body.day
    a.period = body.period
    a.room_id = body.room_id
    db.commit(); db.refresh(a)
    return _sa(a)
