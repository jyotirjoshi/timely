"""Classes CRUD."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Class, User
from app.services.access import PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource

router = APIRouter()

class ClassIn(BaseModel):
    name: str
    grade: str = ""
    size: int = 30

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    grade: Optional[str] = None
    size: Optional[int] = None

def _s(c: Class) -> dict:
    return {"id": c.id, "institution_id": c.institution_id,
            "name": c.name, "grade": c.grade, "size": c.size}

@router.get("")
def list_classes(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_s(c) for c in db.query(Class).filter(Class.institution_id == institution_id).all()]

@router.post("", status_code=201)
def create_class(institution_id: str, body: ClassIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    c = Class(institution_id=institution_id, **body.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return _s(c)

@router.get("/{class_id}")
def get_class(class_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = tenant_resource(db, Class, class_id, institution_for(current_user), "Class not found")
    return _s(c)

@router.patch("/{class_id}")
def update_class(class_id: str, body: ClassUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    c = tenant_resource(db, Class, class_id, institution_for(current_user), "Class not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return _s(c)

@router.delete("/{class_id}", status_code=204)
def delete_class(class_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    c = tenant_resource(db, Class, class_id, institution_for(current_user), "Class not found")
    db.delete(c); db.commit()
