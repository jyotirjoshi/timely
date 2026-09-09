"""Subject components, faculty preferences, and audited workload allocation."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    Department, Division, FacultyPreference, Program, Subject, SubjectComponent,
    Teacher, User, WorkloadAllocation,
)
from app.services.access import (
    PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource,
)
from app.services.workload import suggest_allocations, summarize_workload

router = APIRouter()


class ComponentIn(BaseModel):
    department_id: str
    subject_id: str
    component_type: str
    weekly_hours: float = Field(gt=0, le=40)
    duration_minutes: int = Field(gt=0, le=360)
    room_type: str = "classroom"


class PreferenceIn(BaseModel):
    teacher_id: str
    subject_component_id: str
    rank: int = Field(ge=1, le=100)


class AllocationIn(BaseModel):
    teacher_id: str
    subject_component_id: str
    division_id: str
    weekly_hours: float = Field(gt=0, le=40)
    is_override: bool = False
    override_reason: str = ""


class SuggestionIn(BaseModel):
    subject_component_id: str
    division_id: str
    weekly_hours: float = Field(gt=0, le=40)


def _commit(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail) from exc


def _component(value: SubjectComponent) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id,
        "department_id": value.department_id, "subject_id": value.subject_id,
        "component_type": value.component_type, "weekly_hours": value.weekly_hours,
        "duration_minutes": value.duration_minutes, "room_type": value.room_type,
    }


def _preference(value: FacultyPreference) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id,
        "teacher_id": value.teacher_id, "subject_component_id": value.subject_component_id,
        "rank": value.rank,
    }


def _allocation(value: WorkloadAllocation) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id,
        "teacher_id": value.teacher_id, "subject_component_id": value.subject_component_id,
        "division_id": value.division_id, "weekly_hours": value.weekly_hours,
        "is_override": value.is_override, "override_reason": value.override_reason,
        "created_by": value.created_by,
    }


def _validate_component_division(
    db: Session, component: SubjectComponent, division: Division, institution_id: str,
) -> None:
    program = tenant_resource(db, Program, division.program_id, institution_id, "Program not found")
    if program.department_id != component.department_id:
        raise HTTPException(422, "Subject component and division must belong to the same department")


@router.get("/components")
def list_components(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_component(value) for value in db.query(SubjectComponent).filter(SubjectComponent.institution_id == institution_id).all()]


@router.post("/components", status_code=201)
def create_component(institution_id: str, body: ComponentIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, Department, body.department_id, institution_id, "Department not found")
    tenant_resource(db, Subject, body.subject_id, institution_id, "Subject not found")
    if body.component_type not in {"theory", "practical", "tutorial", "library", "activity"}:
        raise HTTPException(422, "Unsupported subject component type")
    value = SubjectComponent(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Subject component already exists")
    db.refresh(value)
    return _component(value)


@router.get("/preferences")
def list_preferences(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_preference(value) for value in db.query(FacultyPreference).filter(FacultyPreference.institution_id == institution_id).all()]


@router.post("/preferences", status_code=201)
def create_preference(institution_id: str, body: PreferenceIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    teacher = tenant_resource(db, Teacher, body.teacher_id, institution_id, "Teacher not found")
    component = tenant_resource(db, SubjectComponent, body.subject_component_id, institution_id, "Subject component not found")
    if component.subject_id not in (teacher.subjects or []):
        raise HTTPException(422, "Faculty member is not qualified for this subject")
    value = FacultyPreference(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Faculty preference already exists")
    db.refresh(value)
    return _preference(value)


@router.get("/allocations")
def list_allocations(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_allocation(value) for value in db.query(WorkloadAllocation).filter(WorkloadAllocation.institution_id == institution_id).all()]


@router.post("/allocations", status_code=201)
def create_allocation(institution_id: str, body: AllocationIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    teacher = tenant_resource(db, Teacher, body.teacher_id, institution_id, "Teacher not found")
    component = tenant_resource(db, SubjectComponent, body.subject_component_id, institution_id, "Subject component not found")
    division = tenant_resource(db, Division, body.division_id, institution_id, "Division not found")
    _validate_component_division(db, component, division, institution_id)
    qualified = component.subject_id in (teacher.subjects or [])
    if not qualified and not body.is_override:
        raise HTTPException(422, "Faculty member is not qualified; an explicit override is required")
    if body.is_override and not body.override_reason.strip():
        raise HTTPException(422, "Override reason is required")
    value = WorkloadAllocation(
        institution_id=institution_id,
        teacher_id=body.teacher_id,
        subject_component_id=body.subject_component_id,
        division_id=body.division_id,
        weekly_hours=body.weekly_hours,
        is_override=body.is_override,
        override_reason=body.override_reason.strip(),
        created_by=current_user.id,
    )
    db.add(value)
    _commit(db, "Workload allocation already exists")
    db.refresh(value)
    return _allocation(value)


@router.get("/summary")
def workload_summary(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [asdict(summary) for summary in summarize_workload(db, institution_id)]


@router.post("/suggestions")
def allocation_suggestions(institution_id: str, body: SuggestionIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    component = tenant_resource(db, SubjectComponent, body.subject_component_id, institution_id, "Subject component not found")
    division = tenant_resource(db, Division, body.division_id, institution_id, "Division not found")
    _validate_component_division(db, component, division, institution_id)
    proposal = suggest_allocations(
        db, institution_id, body.subject_component_id, body.division_id, body.weekly_hours
    )
    return {
        "component_id": proposal.component_id,
        "division_id": proposal.division_id,
        "weekly_hours": proposal.weekly_hours,
        "candidates": [asdict(candidate) for candidate in proposal.candidates],
    }
