"""Subjects CRUD."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Subject, User
from app.services.access import PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource

router = APIRouter()

class SubjectIn(BaseModel):
    name: str
    room_type: str = "classroom"
    color: str = "#8b5cf6"
    lessons_per_week: int = 4
    allow_double: bool = False

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    room_type: Optional[str] = None
    color: Optional[str] = None
    lessons_per_week: Optional[int] = None
    allow_double: Optional[bool] = None

def _s(s: Subject) -> dict:
    return {"id": s.id, "institution_id": s.institution_id,
            "name": s.name, "room_type": s.room_type,
            "color": s.color, "lessons_per_week": s.lessons_per_week,
            "allow_double": s.allow_double}

@router.get("")
def list_subjects(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_s(s) for s in db.query(Subject).filter(Subject.institution_id == institution_id).all()]

@router.post("", status_code=201)
def create_subject(institution_id: str, body: SubjectIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    s = Subject(institution_id=institution_id, **body.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return _s(s)

@router.get("/{subject_id}")
def get_subject(subject_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    s = tenant_resource(db, Subject, subject_id, institution_for(current_user), "Subject not found")
    return _s(s)

@router.patch("/{subject_id}")
def update_subject(subject_id: str, body: SubjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    s = tenant_resource(db, Subject, subject_id, institution_for(current_user), "Subject not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return _s(s)

@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    s = tenant_resource(db, Subject, subject_id, institution_for(current_user), "Subject not found")
    db.delete(s); db.commit()
