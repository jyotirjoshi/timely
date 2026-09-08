"""Lessons CRUD — the curriculum mapping (what needs scheduling)."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Class, Lesson, Room, Subject, Teacher, User
from app.services.access import (
    PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource,
)

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


def _validate_lesson_refs(db: Session, institution_id: str, body: LessonIn) -> None:
    tenant_resource(db, Class, body.class_id, institution_id, "Class not found")
    tenant_resource(db, Subject, body.subject_id, institution_id, "Subject not found")
    tenant_resource(db, Teacher, body.teacher_id, institution_id, "Teacher not found")
    if body.pinned and body.pinned.get("room_id"):
        tenant_resource(db, Room, body.pinned["room_id"], institution_id, "Room not found")

@router.get("")
def list_lessons(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_s(l) for l in db.query(Lesson).filter(Lesson.institution_id == institution_id).all()]

@router.post("", status_code=201)
def create_lesson(institution_id: str, body: LessonIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    _validate_lesson_refs(db, institution_id, body)
    l = Lesson(institution_id=institution_id, **body.model_dump())
    db.add(l); db.commit(); db.refresh(l)
    return _s(l)

@router.post("/bulk", status_code=201)
def bulk_create_lessons(institution_id: str, body: list[LessonIn],
                         db: Session = Depends(get_db),
                         current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    for item in body:
        _validate_lesson_refs(db, institution_id, item)
    lessons = [Lesson(institution_id=institution_id, **item.model_dump()) for item in body]
    db.add_all(lessons); db.commit()
    return [_s(l) for l in lessons]

@router.patch("/{lesson_id}")
def update_lesson(lesson_id: str, body: LessonUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user)
    l = tenant_resource(db, Lesson, lesson_id, institution_id, "Lesson not found")
    if body.teacher_id is not None:
        tenant_resource(db, Teacher, body.teacher_id, institution_id, "Teacher not found")
    if body.pinned and body.pinned.get("room_id"):
        tenant_resource(db, Room, body.pinned["room_id"], institution_id, "Room not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(l, k, v)
    db.commit(); db.refresh(l)
    return _s(l)

@router.delete("/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    l = tenant_resource(db, Lesson, lesson_id, institution_for(current_user), "Lesson not found")
    db.delete(l); db.commit()

@router.delete("", status_code=204)
def delete_all_lessons(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    db.query(Lesson).filter(Lesson.institution_id == institution_id).delete()
    db.commit()
