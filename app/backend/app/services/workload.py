"""Deterministic faculty workload summaries and allocation suggestions."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import FacultyPreference, SubjectComponent, Teacher, WorkloadAllocation


@dataclass(frozen=True)
class FacultyLoadSummary:
    teacher_id: str
    teacher_name: str
    allocated_hours: float
    minimum_hours: float
    maximum_hours: float
    status: str


@dataclass(frozen=True)
class AllocationCandidate:
    teacher_id: str
    teacher_name: str
    preference_rank: int | None
    current_hours: float
    projected_hours: float


@dataclass(frozen=True)
class AllocationProposal:
    component_id: str
    division_id: str
    weekly_hours: float
    candidates: tuple[AllocationCandidate, ...]


def _loads(db: Session, institution_id: str) -> dict[str, float]:
    rows = db.query(
        WorkloadAllocation.teacher_id,
        func.coalesce(func.sum(WorkloadAllocation.weekly_hours), 0.0),
    ).filter(WorkloadAllocation.institution_id == institution_id).group_by(
        WorkloadAllocation.teacher_id
    ).all()
    return {teacher_id: float(hours) for teacher_id, hours in rows}


def summarize_workload(
    db: Session,
    institution_id: str,
    minimum_hours: float = 22.0,
    maximum_hours: float = 24.0,
) -> list[FacultyLoadSummary]:
    loads = _loads(db, institution_id)
    summaries = []
    for teacher in db.query(Teacher).filter(Teacher.institution_id == institution_id).all():
        allocated = loads.get(teacher.id, 0.0)
        status = "underloaded" if allocated < minimum_hours else "overloaded" if allocated > maximum_hours else "balanced"
        summaries.append(FacultyLoadSummary(
            teacher_id=teacher.id,
            teacher_name=teacher.name,
            allocated_hours=allocated,
            minimum_hours=minimum_hours,
            maximum_hours=maximum_hours,
            status=status,
        ))
    return summaries


def suggest_allocations(
    db: Session,
    institution_id: str,
    component_id: str,
    division_id: str,
    weekly_hours: float,
    maximum_hours: float = 24.0,
) -> AllocationProposal:
    component = db.query(SubjectComponent).filter(
        SubjectComponent.id == component_id,
        SubjectComponent.institution_id == institution_id,
    ).first()
    if component is None:
        raise ValueError("Subject component not found")

    preferences = {
        preference.teacher_id: preference.rank
        for preference in db.query(FacultyPreference).filter(
            FacultyPreference.institution_id == institution_id,
            FacultyPreference.subject_component_id == component_id,
        ).all()
    }
    loads = _loads(db, institution_id)
    candidates = []
    for teacher in db.query(Teacher).filter(Teacher.institution_id == institution_id).all():
        if component.subject_id not in (teacher.subjects or []):
            continue
        current = loads.get(teacher.id, 0.0)
        candidates.append(AllocationCandidate(
            teacher_id=teacher.id,
            teacher_name=teacher.name,
            preference_rank=preferences.get(teacher.id),
            current_hours=current,
            projected_hours=current + weekly_hours,
        ))
    candidates.sort(key=lambda candidate: (
        candidate.projected_hours > maximum_hours,
        candidate.preference_rank if candidate.preference_rank is not None else 10_000,
        candidate.current_hours,
        candidate.teacher_name.casefold(),
    ))
    return AllocationProposal(component_id, division_id, weekly_hours, tuple(candidates))
