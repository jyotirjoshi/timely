"""
SQLAlchemy ORM models for Timely.
"""
from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON,
    String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User / Auth
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="planner")  # owner|planner|teacher|viewer
    institution_id: Mapped[Optional[str]] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    institution: Mapped[Optional["Institution"]] = relationship("Institution", back_populates="users")


# ---------------------------------------------------------------------------
# Institution
# ---------------------------------------------------------------------------

class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, default="school")  # school|college|office
    days_per_week: Mapped[int] = mapped_column(Integer, default=5)
    periods_per_day: Mapped[int] = mapped_column(Integer, default=7)
    day_labels: Mapped[list] = mapped_column(JSON, default=lambda: ["Mon","Tue","Wed","Thu","Fri"])
    period_labels: Mapped[list] = mapped_column(JSON, default=list)
    term_name: Mapped[str] = mapped_column(String, default="Term 1 2026")
    academic_year_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # e.g. 2026-06-01
    board: Mapped[str] = mapped_column(String, default="")  # CBSE | ICSE | State | ""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    users: Mapped[list["User"]] = relationship("User", back_populates="institution")
    teachers: Mapped[list["Teacher"]] = relationship("Teacher", back_populates="institution", cascade="all, delete-orphan")
    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="institution", cascade="all, delete-orphan")
    classes: Mapped[list["Class"]] = relationship("Class", back_populates="institution", cascade="all, delete-orphan")
    subjects: Mapped[list["Subject"]] = relationship("Subject", back_populates="institution", cascade="all, delete-orphan")
    timetables: Mapped[list["Timetable"]] = relationship("Timetable", back_populates="institution", cascade="all, delete-orphan")
    holidays: Mapped[list["Holiday"]] = relationship("Holiday", back_populates="institution", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, default="")
    subjects: Mapped[list] = mapped_column(JSON, default=list)       # list of subject ids
    max_per_day: Mapped[int] = mapped_column(Integer, default=5)
    max_per_week: Mapped[int] = mapped_column(Integer, default=25)
    unavailable: Mapped[list] = mapped_column(JSON, default=list)    # [[day, period], ...]
    color: Mapped[str] = mapped_column(String, default="#6366f1")

    institution: Mapped["Institution"] = relationship("Institution", back_populates="teachers")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, default="classroom")   # classroom|lab|field|hall
    capacity: Mapped[int] = mapped_column(Integer, default=35)
    features: Mapped[list] = mapped_column(JSON, default=list)        # ["projector", "ac", ...]

    institution: Mapped["Institution"] = relationship("Institution", back_populates="rooms")


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    grade: Mapped[str] = mapped_column(String, default="")
    size: Mapped[int] = mapped_column(Integer, default=30)

    institution: Mapped["Institution"] = relationship("Institution", back_populates="classes")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    room_type: Mapped[str] = mapped_column(String, default="classroom")
    color: Mapped[str] = mapped_column(String, default="#8b5cf6")
    lessons_per_week: Mapped[int] = mapped_column(Integer, default=4)
    allow_double: Mapped[bool] = mapped_column(Boolean, default=False)

    institution: Mapped["Institution"] = relationship("Institution", back_populates="subjects")


# ---------------------------------------------------------------------------
# Lessons (curriculum mapping — what needs to be scheduled)
# ---------------------------------------------------------------------------

class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    pinned: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {day, period, room_id}

    class_: Mapped["Class"] = relationship("Class")
    subject: Mapped["Subject"] = relationship("Subject")
    teacher: Mapped["Teacher"] = relationship("Teacher")


# ---------------------------------------------------------------------------
# Timetable & Assignments
# ---------------------------------------------------------------------------

class Timetable(Base):
    __tablename__ = "timetables"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, default="Timetable v1")
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|solving|solved|published
    soft_score: Mapped[int] = mapped_column(Integer, default=0)
    violations: Mapped[list] = mapped_column(JSON, default=list)
    solve_time_s: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    institution: Mapped["Institution"] = relationship("Institution", back_populates="timetables")
    assignments: Mapped[list["Assignment"]] = relationship("Assignment", back_populates="timetable", cascade="all, delete-orphan")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    timetable_id: Mapped[str] = mapped_column(ForeignKey("timetables.id"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String, nullable=False)
    class_id: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False)
    teacher_id: Mapped[str] = mapped_column(String, nullable=False)
    room_id: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)

    timetable: Mapped["Timetable"] = relationship("Timetable", back_populates="assignments")


# ---------------------------------------------------------------------------
# Solve Job
# ---------------------------------------------------------------------------

class SolveJob(Base):
    __tablename__ = "solve_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(String, nullable=False)
    timetable_id: Mapped[str] = mapped_column(ForeignKey("timetables.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, default="queued")  # queued|running|done|failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_status: Mapped[str] = mapped_column(String, default="")
    soft_score: Mapped[int] = mapped_column(Integer, default=0)
    violations: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------

class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, default="national")  # national|state|school|optional

    institution: Mapped["Institution"] = relationship("Institution", back_populates="holidays")


# ---------------------------------------------------------------------------
# Teacher Absences
# ---------------------------------------------------------------------------

class TeacherAbsence(Base):
    __tablename__ = "teacher_absences"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), nullable=False)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String, default="sick leave")
    # substitute_teacher_id is resolved per-assignment, stored in SubstituteAssignment
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    teacher: Mapped["Teacher"] = relationship("Teacher")


class SubstituteAssignment(Base):
    """Tracks which substitute teacher covers which assignment on an absence day."""
    __tablename__ = "substitute_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    absence_id: Mapped[str] = mapped_column(ForeignKey("teacher_absences.id"), nullable=False)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    original_teacher_id: Mapped[str] = mapped_column(String, nullable=False)
    substitute_teacher_id: Mapped[str] = mapped_column(String, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    absence: Mapped["TeacherAbsence"] = relationship("TeacherAbsence")
    assignment: Mapped["Assignment"] = relationship("Assignment")
