"""
Database setup — SQLAlchemy.
Uses DATABASE_URL env var. Defaults to SQLite for local dev,
PostgreSQL (Supabase) for production.
"""
from __future__ import annotations

import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./timely.db")

# SQLite needs check_same_thread=False; PostgreSQL does not
is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    # PostgreSQL connection pool settings
    pool_pre_ping=True,       # test connection before use
    pool_recycle=300,         # recycle connections every 5 min
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
    """SQLite-only: ALTER TABLE … ADD COLUMN — safe to call on every startup."""
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
    """Add columns that were added after initial DB creation (SQLite only)."""
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
    """Create all tables. For PostgreSQL, SQLAlchemy handles schema creation automatically."""
    # SQLite-only migration for existing local DBs
    _auto_migrate_sqlite()

    # Register all models with Base.metadata
    from app.models import (  # noqa: F401
        User, Institution, Teacher, Room, Class, Subject,
        Lesson, Timetable, Assignment, SolveJob,
        Holiday, TeacherAbsence, SubstituteAssignment,
    )

    # create_all: creates tables that don't exist (safe on PostgreSQL too)
    Base.metadata.create_all(bind=engine)
