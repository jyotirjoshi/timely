"""
Holidays router — Indian national holidays + custom school holidays.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Holiday, User

router = APIRouter()


# ── Indian national & commonly observed holidays (year-agnostic, month/day) ─
# Format: (month, day, name, type)
INDIA_HOLIDAYS_2026 = [
    # National holidays (Gazetted)
    (1,  1,  "New Year's Day",           "national"),
    (1,  26, "Republic Day",              "national"),
    (3,  14, "Holi",                      "national"),
    (3,  31, "Id-ul-Fitr (Eid)",          "national"),  # approximate
    (4,  14, "Dr. Ambedkar Jayanti",      "national"),
    (4,  18, "Good Friday",               "national"),
    (5,  1,  "Maharashtra Day / Labour Day", "state"),
    (6,  7,  "Bakrid / Eid ul-Adha",      "national"),  # approximate
    (8,  15, "Independence Day",          "national"),
    (8,  27, "Janmashtami",               "national"),  # approximate
    (9,  5,  "Teacher's Day",             "school"),
    (10, 2,  "Gandhi Jayanti",            "national"),
    (10, 2,  "Dussehra",                  "national"),  # approximate
    (10, 20, "Diwali",                    "national"),  # approximate
    (10, 21, "Diwali (2nd day)",          "national"),
    (11, 5,  "Guru Nanak Jayanti",        "national"),  # approximate
    (11, 14, "Children's Day",            "school"),
    (12, 25, "Christmas Day",             "national"),
]

# Indian school academic calendar (approximate summer & winter breaks)
INDIA_SCHOOL_BREAKS_2026 = [
    # Summer vacation: May to mid-June (most CBSE schools)
    *[(5, d, "Summer Vacation", "school") for d in range(2, 32) if d <= 31],
    *[(6, d, "Summer Vacation", "school") for d in range(1, 16)],
    # Diwali break: 3 days around Diwali
    (10, 22, "Diwali Break",  "school"),
    (10, 23, "Diwali Break",  "school"),
    # Winter / Christmas break
    (12, 26, "Winter Break",  "school"),
    (12, 27, "Winter Break",  "school"),
    (12, 28, "Winter Break",  "school"),
    (12, 29, "Winter Break",  "school"),
    (12, 30, "Winter Break",  "school"),
    (12, 31, "Winter Break",  "school"),
    (1,  2,  "Winter Break",  "school"),
]


class HolidayIn(BaseModel):
    date: date
    name: str
    type: str = "school"  # national|state|school|optional


def _s(h: Holiday) -> dict:
    return {
        "id": h.id, "institution_id": h.institution_id,
        "date": h.date.isoformat(), "name": h.name, "type": h.type,
    }


@router.get("")
def list_holidays(institution_id: str, db: Session = Depends(get_db),
                  _: User = Depends(get_current_user)):
    return [_s(h) for h in
            db.query(Holiday)
              .filter(Holiday.institution_id == institution_id)
              .order_by(Holiday.date)
              .all()]


@router.post("", status_code=201)
def create_holiday(institution_id: str, body: HolidayIn,
                   db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    h = Holiday(institution_id=institution_id,
                date=body.date, name=body.name, type=body.type)
    db.add(h); db.commit(); db.refresh(h)
    return _s(h)


@router.delete("/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: str, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    h = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not h: raise HTTPException(404, "Holiday not found")
    db.delete(h); db.commit()


@router.post("/seed-india")
def seed_india_holidays(institution_id: str, year: int = 2026,
                        include_school_breaks: bool = True,
                        db: Session = Depends(get_db),
                        _: User = Depends(get_current_user)):
    """
    Seed all Indian national holidays + school calendar breaks for a given year.
    Skips dates that already exist (idempotent).
    """
    existing_dates = {h.date for h in
                      db.query(Holiday).filter(Holiday.institution_id == institution_id).all()}

    entries = list(INDIA_HOLIDAYS_2026)
    if include_school_breaks:
        entries += INDIA_SCHOOL_BREAKS_2026

    added = 0
    for month, day, name, htype in entries:
        try:
            d = date(year, month, day)
        except ValueError:
            continue  # e.g. Feb 30
        if d not in existing_dates:
            db.add(Holiday(institution_id=institution_id, date=d, name=name, type=htype))
            existing_dates.add(d)
            added += 1

    db.commit()
    return {"added": added, "message": f"Added {added} holiday entries for {year}"}


@router.delete("")
def clear_holidays(institution_id: str, db: Session = Depends(get_db),
                   _: User = Depends(get_current_user)):
    """Clear all holidays for an institution."""
    db.query(Holiday).filter(Holiday.institution_id == institution_id).delete()
    db.commit()
    return {"message": "All holidays cleared"}
