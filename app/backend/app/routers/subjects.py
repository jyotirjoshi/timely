"""Subjects CRUD."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Subject, User

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
def list_subjects(institution_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_s(s) for s in db.query(Subject).filter(Subject.institution_id == institution_id).all()]

@router.post("", status_code=201)
def create_subject(institution_id: str, body: SubjectIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = Subject(institution_id=institution_id, **body.model_dump())
    db.add(s); db.commit(); db.refresh(s)
    return _s(s)

@router.get("/{subject_id}")
def get_subject(subject_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s: raise HTTPException(404, "Subject not found")
    return _s(s)

@router.patch("/{subject_id}")
def update_subject(subject_id: str, body: SubjectUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s: raise HTTPException(404, "Subject not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return _s(s)

@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s: raise HTTPException(404, "Subject not found")
    db.delete(s); db.commit()
