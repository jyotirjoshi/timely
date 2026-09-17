"""Tenant and role access-control helpers for academic planning routes."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.models import Assignment, Timetable, User


PLANNING_MUTATOR_ROLES = ("owner", "admin", "planner")

ModelT = TypeVar("ModelT")


def institution_for(user: User, requested_id: str | None = None) -> str:
    """Return the authenticated tenant, rejecting caller-selected tenants."""
    if not user.institution_id:
        raise HTTPException(status_code=403, detail="Institution access required")
    if requested_id is not None and requested_id != user.institution_id:
        raise HTTPException(status_code=403, detail="Institution access denied")
    return user.institution_id


def require_roles(*roles: str):
    """FastAPI dependency requiring one of the supplied user roles."""
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return checker


def tenant_resource(
    db: Session,
    model: type[ModelT],
    resource_id: str,
    institution_id: str,
    not_found: str,
) -> ModelT:
    resource = db.query(model).filter(
        model.id == resource_id,
        model.institution_id == institution_id,
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail=not_found)
    return resource


def tenant_resources(
    db: Session,
    model: type[ModelT],
    resource_ids: Iterable[str],
    institution_id: str,
    not_found: str,
) -> list[ModelT]:
    ids = set(resource_ids)
    if not ids:
        return []
    resources = db.query(model).filter(
        model.id.in_(ids),
        model.institution_id == institution_id,
    ).all()
    if {resource.id for resource in resources} != ids:
        raise HTTPException(status_code=404, detail=not_found)
    return resources


def tenant_assignment(
    db: Session,
    assignment_id: str,
    timetable_id: str,
    institution_id: str,
) -> Assignment:
    assignment = db.query(Assignment).join(Timetable).filter(
        Assignment.id == assignment_id,
        Assignment.timetable_id == timetable_id,
        Timetable.institution_id == institution_id,
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment
