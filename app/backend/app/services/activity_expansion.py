"""Expand persisted curriculum requirements into atomic solver activities."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AcademicTerm, CurriculumRequirement, SchedulingActivity


@dataclass(frozen=True)
class ExpansionResult:
    created: int
    updated: int
    deleted: int
    preserved_pinned: int


def expand_requirements(db: Session, institution_id: str, term_id: str) -> ExpansionResult:
    term = db.query(AcademicTerm).filter(
        AcademicTerm.id == term_id,
        AcademicTerm.institution_id == institution_id,
    ).first()
    if term is None:
        raise ValueError("Academic term not found")

    requirements = db.query(CurriculumRequirement).filter(
        CurriculumRequirement.term_id == term_id,
        CurriculumRequirement.institution_id == institution_id,
    ).all()
    existing = db.query(SchedulingActivity).filter(
        SchedulingActivity.term_id == term_id,
        SchedulingActivity.institution_id == institution_id,
    ).all()
    by_key = {(activity.requirement_id, activity.occurrence_index): activity for activity in existing}
    created = updated = deleted = preserved_pinned = 0

    for requirement in requirements:
        if requirement.weekly_count < 0 or requirement.duration_minutes <= 0:
            raise ValueError("Curriculum requirement has invalid count or duration")
        for occurrence_index in range(requirement.weekly_count):
            key = (requirement.id, occurrence_index)
            activity = by_key.get(key)
            if activity is None:
                activity = SchedulingActivity(
                    institution_id=institution_id,
                    term_id=term_id,
                    requirement_id=requirement.id,
                    occurrence_index=occurrence_index,
                    division_id=requirement.division_id,
                    batch_id=requirement.batch_id,
                    subject_component_id=requirement.subject_component_id,
                    duration_minutes=requirement.duration_minutes,
                    faculty_pool=list(requirement.faculty_pool or []),
                    room_type=requirement.room_type,
                    alternate_week_pattern=requirement.alternate_week_pattern,
                    parallel_group=requirement.parallel_group,
                )
                db.add(activity)
                created += 1
            else:
                activity.division_id = requirement.division_id
                activity.batch_id = requirement.batch_id
                activity.subject_component_id = requirement.subject_component_id
                activity.duration_minutes = requirement.duration_minutes
                activity.faculty_pool = list(requirement.faculty_pool or [])
                activity.room_type = requirement.room_type
                activity.alternate_week_pattern = requirement.alternate_week_pattern
                activity.parallel_group = requirement.parallel_group
                updated += 1

    desired = {
        (requirement.id, index)
        for requirement in requirements
        for index in range(requirement.weekly_count)
    }
    for activity in existing:
        key = (activity.requirement_id, activity.occurrence_index)
        if key in desired:
            continue
        if activity.pinned:
            preserved_pinned += 1
            continue
        db.delete(activity)
        deleted += 1

    db.commit()
    return ExpansionResult(created, updated, deleted, preserved_pinned)
