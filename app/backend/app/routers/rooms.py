"""Rooms CRUD."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from app.auth import get_current_user
from app.db import get_db
from app.models import Room, User
from app.services.access import PLANNING_MUTATOR_ROLES, institution_for, require_roles, tenant_resource

router = APIRouter()

class RoomIn(BaseModel):
    name: str
    type: str = "classroom"
    capacity: int = 35
    features: list[str] = []

class RoomUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    capacity: Optional[int] = None
    features: Optional[list[str]] = None

def _s(r: Room) -> dict:
    return {"id": r.id, "institution_id": r.institution_id,
            "name": r.name, "type": r.type,
            "capacity": r.capacity, "features": r.features or []}

@router.get("")
def list_rooms(institution_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    institution_id = institution_for(current_user, institution_id)
    return [_s(r) for r in db.query(Room).filter(Room.institution_id == institution_id).all()]

@router.post("", status_code=201)
def create_room(institution_id: str, body: RoomIn, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    institution_id = institution_for(current_user, institution_id)
    r = Room(institution_id=institution_id, **body.model_dump())
    db.add(r); db.commit(); db.refresh(r)
    return _s(r)

@router.get("/{room_id}")
def get_room(room_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = tenant_resource(db, Room, room_id, institution_for(current_user), "Room not found")
    return _s(r)

@router.patch("/{room_id}")
def update_room(room_id: str, body: RoomUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    r = tenant_resource(db, Room, room_id, institution_for(current_user), "Room not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(r, k, v)
    db.commit(); db.refresh(r)
    return _s(r)

@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(*PLANNING_MUTATOR_ROLES))):
    r = tenant_resource(db, Room, room_id, institution_for(current_user), "Room not found")
    db.delete(r); db.commit()
