"""Lessons CRUD — the curriculum mapping (what needs scheduling)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Lesson, User

router = APIRouter()

class LessonIn(BaseModel):
    class_id: str
    subject_id: str
    teacher_id: str
    pinned: Optional[dict] = None

class LessonUpdate(BaseModel):
    teacher_id: Optional[str] = None
    pinned: Optional[dict] = None

def _s(l: Lesson) -> dict:
    return {"id": l.id, "institution_id": l.institution_id,
            "class_id": l.class_id, "subject_id": l.subject_id,
            "teacher_id": l.teacher_id, "pinned": l.pinned}

@router.get("")
def list_lessons(institution_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_s(l) for l in db.query(Lesson).filter(Lesson.institution_id == institution_id).all()]

@router.post("", status_code=201)
def create_lesson(institution_id: str, body: LessonIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    l = Lesson(institution_id=institution_id, **body.model_dump())
    db.add(l); db.commit(); db.refresh(l)
    return _s(l)

@router.post("/bulk", status_code=201)
def bulk_create_lessons(institution_id: str, body: list[LessonIn],
                         db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    lessons = [Lesson(institution_id=institution_id, **item.model_dump()) for item in body]
    db.add_all(lessons); db.commit()
    return [_s(l) for l in lessons]

@router.patch("/{lesson_id}")
def update_lesson(lesson_id: str, body: LessonUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    l = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not l: raise HTTPException(404, "Lesson not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(l, k, v)
    db.commit(); db.refresh(l)
    return _s(l)

@router.delete("/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    l = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not l: raise HTTPException(404, "Lesson not found")
    db.delete(l); db.commit()

@router.delete("", status_code=204)
def delete_all_lessons(institution_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    db.query(Lesson).filter(Lesson.institution_id == institution_id).delete()
    db.commit()
