"""Academic terms and typed curriculum requirements."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    AcademicTerm, Batch, CurriculumRequirement, Division, Program,
    SchedulingActivity, SubjectComponent, Teacher, User,
)
from app.services.access import (
    PLANNING_MUTATOR_ROLES, institution_for, require_roles,
    tenant_resource, tenant_resources,
)
from app.services.activity_expansion import expand_requirements

router = APIRouter()


class TermIn(BaseModel):
    name: str = Field(min_length=1)
    starts_on: date
    ends_on: date
    is_active: bool = True


class RequirementIn(BaseModel):
    term_id: str
    division_id: str
    batch_id: str | None = None
    subject_component_id: str
    weekly_count: int = Field(ge=1, le=20)
    duration_minutes: int = Field(gt=0, le=360)
    faculty_pool: list[str] = []
    room_type: str = "classroom"
    alternate_week_pattern: str = "every"
    parallel_group: str | None = None


def _commit(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail) from exc


def _term(value: AcademicTerm) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id, "name": value.name,
        "starts_on": value.starts_on.isoformat(), "ends_on": value.ends_on.isoformat(),
        "is_active": value.is_active,
    }


def _requirement(value: CurriculumRequirement) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id,
        "term_id": value.term_id, "division_id": value.division_id,
        "batch_id": value.batch_id, "subject_component_id": value.subject_component_id,
        "weekly_count": value.weekly_count, "duration_minutes": value.duration_minutes,
        "faculty_pool": value.faculty_pool or [], "room_type": value.room_type,
        "alternate_week_pattern": value.alternate_week_pattern,
        "parallel_group": value.parallel_group,
    }


def _activity(value: SchedulingActivity) -> dict:
    return {
        "id": value.id, "requirement_id": value.requirement_id,
        "occurrence_index": value.occurrence_index, "division_id": value.division_id,
        "batch_id": value.batch_id, "subject_component_id": value.subject_component_id,
        "duration_minutes": value.duration_minutes, "faculty_pool": value.faculty_pool or [],
        "room_type": value.room_type, "alternate_week_pattern": value.alternate_week_pattern,
        "parallel_group": value.parallel_group, "pinned": value.pinned,
    }


@router.get("/terms")
def list_terms(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_term(value) for value in db.query(AcademicTerm).filter(AcademicTerm.institution_id == institution_id).all()]


@router.post("/terms", status_code=201)
def create_term(institution_id: str, body: TermIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    if body.starts_on >= body.ends_on:
        raise HTTPException(422, "Term start must be before its end")
    value = AcademicTerm(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Academic term name already exists")
    db.refresh(value)
    return _term(value)


@router.get("")
def list_requirements(institution_id: str, term_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, AcademicTerm, term_id, institution_id, "Academic term not found")
    values = db.query(CurriculumRequirement).filter(
        CurriculumRequirement.institution_id == institution_id,
        CurriculumRequirement.term_id == term_id,
    ).all()
    return [_requirement(value) for value in values]


@router.post("", status_code=201)
def create_requirement(institution_id: str, body: RequirementIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, AcademicTerm, body.term_id, institution_id, "Academic term not found")
    division = tenant_resource(db, Division, body.division_id, institution_id, "Division not found")
    component = tenant_resource(db, SubjectComponent, body.subject_component_id, institution_id, "Subject component not found")
    program = tenant_resource(db, Program, division.program_id, institution_id, "Program not found")
    if component.department_id != program.department_id:
        raise HTTPException(422, "Subject component and division must belong to the same department")
    if body.batch_id:
        batch = tenant_resource(db, Batch, body.batch_id, institution_id, "Batch not found")
        if batch.division_id != body.division_id:
            raise HTTPException(422, "Batch must belong to the selected division")
    tenant_resources(db, Teacher, body.faculty_pool, institution_id, "Faculty member not found")
    if body.alternate_week_pattern not in {"every", "odd", "even"}:
        raise HTTPException(422, "Alternate-week pattern must be every, odd, or even")
    if component.component_type == "practical" and body.duration_minutes != component.duration_minutes:
        raise HTTPException(422, "Lab duration must match the fixed subject-component duration")
    value = CurriculumRequirement(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Could not create curriculum requirement")
    db.refresh(value)
    return _requirement(value)


@router.post("/expand/{term_id}")
def expand_term(term_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user)
    tenant_resource(db, AcademicTerm, term_id, institution_id, "Academic term not found")
    return asdict(expand_requirements(db, institution_id, term_id))


@router.get("/activities/{term_id}")
def list_activities(term_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user)
    tenant_resource(db, AcademicTerm, term_id, institution_id, "Academic term not found")
    values = db.query(SchedulingActivity).filter(
        SchedulingActivity.institution_id == institution_id,
        SchedulingActivity.term_id == term_id,
    ).order_by(SchedulingActivity.requirement_id, SchedulingActivity.occurrence_index).all()
    return [_activity(value) for value in values]
