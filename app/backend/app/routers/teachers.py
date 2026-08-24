"""Teachers CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.auth import get_current_user
from app.db import get_db
from app.models import Teacher, User

router = APIRouter()


class TeacherIn(BaseModel):
    name: str
    email: str = ""
    subjects: list[str] = []
    max_per_day: int = 5
    max_per_week: int = 25
    unavailable: list[list[int]] = []
    color: str = "#6366f1"


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    subjects: Optional[list[str]] = None
    max_per_day: Optional[int] = None
    max_per_week: Optional[int] = None
    unavailable: Optional[list[list[int]]] = None
    color: Optional[str] = None


def _s(t: Teacher) -> dict:
    return {
        "id": t.id, "institution_id": t.institution_id,
        "name": t.name, "email": t.email,
        "subjects": t.subjects or [], "max_per_day": t.max_per_day,
        "max_per_week": t.max_per_week, "unavailable": t.unavailable or [],
        "color": t.color,
    }


@router.get("")
def list_teachers(institution_id: str, db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    return [_s(t) for t in db.query(Teacher).filter(Teacher.institution_id == institution_id).all()]


@router.post("", status_code=201)
def create_teacher(institution_id: str, body: TeacherIn,
                   db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = Teacher(institution_id=institution_id, **body.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    return _s(t)


@router.get("/{teacher_id}")
def get_teacher(teacher_id: str, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t: raise HTTPException(404, "Teacher not found")
    return _s(t)


@router.patch("/{teacher_id}")
def update_teacher(teacher_id: str, body: TeacherUpdate,
                   db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t: raise HTTPException(404, "Teacher not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    db.commit(); db.refresh(t)
    return _s(t)


@router.delete("/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: str, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t: raise HTTPException(404, "Teacher not found")
    db.delete(t); db.commit()
