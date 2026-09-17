"""Programs, divisions, batches, students, enrollments, and roster imports."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    Batch, Department, DepartmentCalendar, Division, Enrollment, Program, Student, User,
)
from app.services.access import (
    PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource,
)
from app.services.roster_import import RosterError, parse_roster_csv

router = APIRouter()


class ProgramIn(BaseModel):
    department_id: str
    name: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=24)
    duration_years: int = Field(default=4, ge=1, le=10)


class DivisionIn(BaseModel):
    program_id: str
    name: str = Field(min_length=1)
    academic_year: int = Field(ge=1, le=10)
    semester: int = Field(ge=1, le=20)
    size: int = Field(default=0, ge=0)
    calendar_id: str | None = None


class BatchIn(BaseModel):
    division_id: str
    name: str = Field(min_length=1)


class StudentIn(BaseModel):
    student_number: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    email: str = ""


class EnrollmentIn(BaseModel):
    student_id: str
    division_id: str
    batch_id: str | None = None


def _commit(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail) from exc


def _serialize(value) -> dict:
    fields = {
        Program: ("id", "institution_id", "department_id", "name", "code", "duration_years"),
        Division: ("id", "institution_id", "program_id", "calendar_id", "name", "academic_year", "semester", "size"),
        Batch: ("id", "institution_id", "division_id", "name"),
        Student: ("id", "institution_id", "student_number", "name", "email", "is_active"),
        Enrollment: ("id", "institution_id", "student_id", "division_id", "batch_id"),
    }[type(value)]
    return {field: getattr(value, field) for field in fields}


def _tenant_list(db: Session, model, institution_id: str) -> list[dict]:
    return [_serialize(value) for value in db.query(model).filter(model.institution_id == institution_id).all()]


@router.get("/programs")
def list_programs(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _tenant_list(db, Program, institution_for(current_user, institution_id))


@router.post("/programs", status_code=201)
def create_program(institution_id: str, body: ProgramIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, Department, body.department_id, institution_id, "Department not found")
    value = Program(
        institution_id=institution_id, department_id=body.department_id,
        name=body.name.strip(), code=body.code.strip().upper(),
        duration_years=body.duration_years,
    )
    db.add(value)
    _commit(db, "Program code already exists")
    db.refresh(value)
    return _serialize(value)


@router.get("/divisions")
def list_divisions(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _tenant_list(db, Division, institution_for(current_user, institution_id))


@router.post("/divisions", status_code=201)
def create_division(institution_id: str, body: DivisionIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    program = tenant_resource(db, Program, body.program_id, institution_id, "Program not found")
    if body.calendar_id:
        calendar = tenant_resource(db, DepartmentCalendar, body.calendar_id, institution_id, "Calendar not found")
        if calendar.department_id != program.department_id:
            raise HTTPException(422, "Calendar must belong to the program department")
    value = Division(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Division already exists for this program and term")
    db.refresh(value)
    return _serialize(value)


@router.get("/batches")
def list_batches(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _tenant_list(db, Batch, institution_for(current_user, institution_id))


@router.post("/batches", status_code=201)
def create_batch(institution_id: str, body: BatchIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, Division, body.division_id, institution_id, "Division not found")
    value = Batch(institution_id=institution_id, division_id=body.division_id, name=body.name.strip())
    db.add(value)
    _commit(db, "Batch name already exists in this division")
    db.refresh(value)
    return _serialize(value)


@router.get("/students")
def list_students(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _tenant_list(db, Student, institution_for(current_user, institution_id))


@router.post("/students", status_code=201)
def create_student(institution_id: str, body: StudentIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    email = body.email.strip().lower()
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        raise HTTPException(422, "Invalid email address")
    value = Student(
        institution_id=institution_id, student_number=body.student_number.strip(),
        name=body.name.strip(), email=email,
    )
    db.add(value)
    _commit(db, "Student number already exists")
    db.refresh(value)
    return _serialize(value)


@router.get("/enrollments")
def list_enrollments(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _tenant_list(db, Enrollment, institution_for(current_user, institution_id))


@router.post("/enrollments", status_code=201)
def create_enrollment(institution_id: str, body: EnrollmentIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, Student, body.student_id, institution_id, "Student not found")
    tenant_resource(db, Division, body.division_id, institution_id, "Division not found")
    if body.batch_id:
        batch = tenant_resource(db, Batch, body.batch_id, institution_id, "Batch not found")
        if batch.division_id != body.division_id:
            raise HTTPException(422, "Batch must belong to the selected division")
    value = Enrollment(institution_id=institution_id, **body.model_dump())
    db.add(value)
    _commit(db, "Student is already enrolled in this division")
    db.refresh(value)
    return _serialize(value)


@router.post("/rosters/import", status_code=201)
def import_roster(institution_id: str, division_id: str, file: UploadFile, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    tenant_resource(db, Division, division_id, institution_id, "Division not found")
    try:
        content = file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, {"errors": [{"row": 1, "field": "file", "message": "CSV must be UTF-8"}]}) from exc

    result = parse_roster_csv(content, division_id)
    batches = db.query(Batch).filter(
        Batch.institution_id == institution_id, Batch.division_id == division_id,
    ).all()
    batch_by_name = {batch.name.casefold(): batch for batch in batches}
    errors = list(result.errors)
    identifiers = [row.student_number for row in result.rows]
    existing = {
        value.student_number.casefold()
        for value in db.query(Student).filter(
            Student.institution_id == institution_id,
            Student.student_number.in_(identifiers),
        ).all()
    }
    for row in result.rows:
        if row.student_number.casefold() in existing:
            errors.append(RosterError(row.row, "student_number", "Student number already exists"))
        if row.batch and row.batch.casefold() not in batch_by_name:
            errors.append(RosterError(row.row, "batch", "Batch does not exist in this division"))
    if errors:
        raise HTTPException(422, {"errors": [asdict(error) for error in errors]})

    created = []
    try:
        for row in result.rows:
            student = Student(
                institution_id=institution_id, student_number=row.student_number,
                name=row.name, email=row.email,
            )
            db.add(student)
            db.flush()
            enrollment = Enrollment(
                institution_id=institution_id, student_id=student.id,
                division_id=division_id,
                batch_id=batch_by_name[row.batch.casefold()].id if row.batch else None,
            )
            db.add(enrollment)
            created.append(_serialize(student))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"created": len(created), "students": created, "errors": []}
