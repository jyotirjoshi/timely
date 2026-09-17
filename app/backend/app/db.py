"""
Database setup — SQLAlchemy.
Uses DATABASE_URL env var. Defaults to SQLite for local dev,
PostgreSQL (Supabase/Railway) for production.
"""
from __future__ import annotations

import logging
import os
import sqlite3

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(override=True)

log = logging.getLogger("timely.db")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./timely.db")
is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5 if not is_sqlite else 1,
    max_overflow=10 if not is_sqlite else 0,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_add_column_if_missing(db_path: str, table: str, column: str, definition: str):
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cur.fetchall()}
        if column not in cols and cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _auto_migrate_sqlite():
    if not is_sqlite:
        return
    db_path = DATABASE_URL.replace("sqlite:///", "").lstrip("./")
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)
    if not os.path.exists(db_path):
        return
    _sqlite_add_column_if_missing(db_path, "institutions", "academic_year_start", "DATE")
    _sqlite_add_column_if_missing(db_path, "institutions", "board", "VARCHAR DEFAULT ''")


def init_db():
    """
    Create all tables on startup.
    If the database is unreachable (e.g. Supabase DNS not yet resolved),
    log a warning but don't crash — tables will be created on first real request.
    """
    _auto_migrate_sqlite()

    # Import all models so SQLAlchemy registers them with Base.metadata
    from app.models import (  # noqa: F401
        User, Institution, Teacher, Room, Class, Subject,
        Lesson, Timetable, Assignment, SolveJob,
        Holiday, TeacherAbsence, SubstituteAssignment,
    )

    try:
        Base.metadata.create_all(bind=engine)
        log.info("Database tables created/verified OK")
    except Exception as exc:
        log.warning(
            f"Could not connect to database on startup (will retry on first request): {exc}"
        )
