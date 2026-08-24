"""Institutions CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date as DateType

from app.auth import get_current_user
from app.db import get_db
from app.models import Institution, User

router = APIRouter()


class InstitutionUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    days_per_week: Optional[int] = None
    periods_per_day: Optional[int] = None
    day_labels: Optional[list[str]] = None
    period_labels: Optional[list[str]] = None
    term_name: Optional[str] = None
    academic_year_start: Optional[DateType] = None
    board: Optional[str] = None


def _serialize(inst: Institution) -> dict:
    return {
        "id": inst.id,
        "name": inst.name,
        "type": inst.type,
        "days_per_week": inst.days_per_week,
        "periods_per_day": inst.periods_per_day,
        "day_labels": inst.day_labels or ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "period_labels": inst.period_labels or [f"P{i+1}" for i in range(inst.periods_per_day)],
        "term_name": inst.term_name,
        "academic_year_start": inst.academic_year_start.isoformat() if inst.academic_year_start else None,
        "board": inst.board or "",
        "created_at": inst.created_at.isoformat() if inst.created_at else None,
    }


@router.get("/{institution_id}")
def get_institution(institution_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(404, "Institution not found")
    return _serialize(inst)


@router.patch("/{institution_id}")
def update_institution(institution_id: str, body: InstitutionUpdate,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(404, "Institution not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(inst, k, v)
    db.commit()
    db.refresh(inst)
    return _serialize(inst)
