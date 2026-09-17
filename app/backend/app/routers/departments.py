"""Tenant-scoped academic organization and department calendar APIs."""
from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    CalendarPeriod, Department, DepartmentCalendar, FacultyShift, School, Teacher, User,
)
from app.services.access import (
    PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource,
)
from app.services.calendars import CalendarValidationError, validate_periods

router = APIRouter()


class SchoolIn(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=24)


class DepartmentIn(BaseModel):
    school_id: str
    name: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=24)


class PeriodIn(BaseModel):
    day: int = Field(ge=0, le=6)
    ordinal: int = Field(ge=0)
    name: str = Field(min_length=1)
    kind: str = "teaching"
    start_time: time
    end_time: time


class CalendarIn(BaseModel):
    name: str = Field(min_length=1)
    timezone: str = "Asia/Kolkata"
    is_active: bool = True
    periods: list[PeriodIn]


class FacultyShiftIn(BaseModel):
    teacher_id: str
    department_id: str
    day: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


def _commit(db: Session, duplicate_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, duplicate_detail) from exc


def _school(value: School) -> dict:
    return {"id": value.id, "institution_id": value.institution_id, "name": value.name, "code": value.code}


def _department(value: Department) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id,
        "school_id": value.school_id, "name": value.name, "code": value.code,
    }


def _period(value: CalendarPeriod) -> dict:
    return {
        "id": value.id, "day": value.day, "ordinal": value.ordinal,
        "name": value.name, "kind": value.kind,
        "start_time": value.start_time.isoformat(), "end_time": value.end_time.isoformat(),
    }


def _calendar(value: DepartmentCalendar) -> dict:
    return {
        "id": value.id, "institution_id": value.institution_id,
        "department_id": value.department_id, "name": value.name,
        "timezone": value.timezone, "is_active": value.is_active,
        "periods": [_period(period) for period in value.periods],
    }


@router.get("/schools")
def list_schools(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_school(value) for value in db.query(School).filter(School.institution_id == institution_id).all()]


@router.post("/schools", status_code=201)
def create_school(institution_id: str, body: SchoolIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    value = School(institution_id=institution_id, name=body.name.strip(), code=body.code.strip().upper())
    db.add(value)
    _commit(db, "School code already exists")
    db.refresh(value)
    return _school(value)


@router.get("/faculty-shifts")
def list_faculty_shifts(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [{
        "id": value.id, "teacher_id": value.teacher_id, "department_id": value.department_id,
        "day": value.day, "start_time": value.start_time.isoformat(), "end_time": value.end_time.isoformat(),
    } for value in db.query(FacultyShift).filter(FacultyShift.institution_id == institution_id).all()]


@router.post("/faculty-shifts", status_code=201)
def create_faculty_shift(institution_id: str, body: FacultyShiftIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, Teacher, body.teacher_id, institution_id, "Teacher not found")
    tenant_resource(db, Department, body.department_id, institution_id, "Department not found")
    if body.start_time >= body.end_time:
        raise HTTPException(422, "Shift start must be before its end")
    value = FacultyShift(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Faculty shift already exists")
    db.refresh(value)
    return {
        "id": value.id, "teacher_id": value.teacher_id, "department_id": value.department_id,
        "day": value.day, "start_time": value.start_time.isoformat(), "end_time": value.end_time.isoformat(),
    }


@router.get("/calendars/{calendar_id}")
def get_calendar(calendar_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    value = tenant_resource(db, DepartmentCalendar, calendar_id, institution_for(current_user), "Calendar not found")
    return _calendar(value)


@router.get("")
def list_departments(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_department(value) for value in db.query(Department).filter(Department.institution_id == institution_id).all()]


@router.post("", status_code=201)
def create_department(institution_id: str, body: DepartmentIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, School, body.school_id, institution_id, "School not found")
    value = Department(
        institution_id=institution_id, school_id=body.school_id,
        name=body.name.strip(), code=body.code.strip().upper(),
    )
    db.add(value)
    _commit(db, "Department code already exists")
    db.refresh(value)
    return _department(value)


@router.post("/{department_id}/calendars", status_code=201)
def create_calendar(department_id: str, body: CalendarIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user)
    tenant_resource(db, Department, department_id, institution_id, "Department not found")
    try:
        ZoneInfo(body.timezone)
        validate_periods(body.periods)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Unknown timezone") from exc
    except CalendarValidationError as exc:
        raise HTTPException(422, str(exc)) from exc

    value = DepartmentCalendar(
        institution_id=institution_id, department_id=department_id,
        name=body.name.strip(), timezone=body.timezone, is_active=body.is_active,
    )
    value.periods = [
        CalendarPeriod(institution_id=institution_id, **period.model_dump())
        for period in body.periods
    ]
    db.add(value)
    _commit(db, "Calendar contains duplicate periods")
    db.refresh(value)
    return _calendar(value)
