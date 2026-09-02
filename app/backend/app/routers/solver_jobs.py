"""
Solver jobs router.
Runs the OR-Tools CP-SAT solver in a background thread (no Celery/Redis needed
for single-server dev; swap to Celery for production scale).
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import SessionLocal, get_db
from app.models import Assignment, Lesson, SolveJob, Timetable, User
from app.models import Teacher, Room, Class, Subject, Institution
from app.solver import solve_timetable

router = APIRouter()


class SolveRequest(BaseModel):
    institution_id: str
    timetable_name: str = "Generated Timetable"
    time_limit_s: int = 60
    seed: int = 42
    soft_constraints: Optional[dict] = None


def _build_dataset(institution_id: str, db: Session) -> dict:
    """Assemble the solver's input dict from the DB."""
    inst: Optional[Institution] = db.query(Institution).filter(
        Institution.id == institution_id).first()
    if not inst:
        raise ValueError(f"Institution {institution_id} not found")

    teachers = db.query(Teacher).filter(Teacher.institution_id == institution_id).all()
    rooms = db.query(Room).filter(Room.institution_id == institution_id).all()
    classes = db.query(Class).filter(Class.institution_id == institution_id).all()
    subjects = db.query(Subject).filter(Subject.institution_id == institution_id).all()
    lessons = db.query(Lesson).filter(Lesson.institution_id == institution_id).all()

    return {
        "days": inst.day_labels or [f"D{i}" for i in range(inst.days_per_week)],
        "periods_per_day": inst.periods_per_day,
        "teachers": [
            {"id": t.id, "name": t.name,
             "max_per_day": t.max_per_day,
             "unavailable": t.unavailable or []}
            for t in teachers
        ],
        "rooms": [
            {"id": r.id, "name": r.name,
             "type": r.type or "classroom",
             "capacity": r.capacity}
            for r in rooms
        ],
        "classes": [
            {"id": c.id, "name": c.name, "size": c.size}
            for c in classes
        ],
        "subjects": [
            {
                "id": s.id,
                "name": s.name,
                "room_type": s.room_type or "classroom",
                "allow_double": s.allow_double,
            }
            for s in subjects
        ],
        "lessons": [
            {"id": l.id, "class_id": l.class_id,
             "subject_id": l.subject_id, "teacher_id": l.teacher_id,
             "pinned": l.pinned}
            for l in lessons
        ],
        "soft_constraints": {
            "teacher_max_consecutive": {"weight": 5, "max": 3},
            "subject_spread": {"weight": 3},
            "minimize_teacher_gaps": {"weight": 1},
        },
    }


def _run_solve(job_id: str, institution_id: str, timetable_name: str,
               time_limit_s: int, seed: int):
    """Background thread: solve and persist the result."""
    db = SessionLocal()
    try:
        job = db.query(SolveJob).filter(SolveJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        job.progress = 5
        db.commit()

        dataset = _build_dataset(institution_id, db)
        job.progress = 20
        db.commit()

        result = solve_timetable(dataset, time_limit_s=time_limit_s, seed=seed)

        job.result_status = result.status
        job.soft_score = result.soft_score
        job.violations = result.violations
        job.progress = 90

        # Create / persist timetable
        timetable = Timetable(
            institution_id=institution_id,
            name=timetable_name,
            status="solved" if result.status in ("OPTIMAL", "FEASIBLE") else "failed",
            soft_score=result.soft_score,
            violations=result.violations,
            solve_time_s=result.solve_time_s,
        )
        db.add(timetable)
        db.flush()

        for a in result.assignments:
            db.add(Assignment(
                timetable_id=timetable.id,
                lesson_id=a["lesson_id"],
                class_id=a["class_id"],
                subject_id=a["subject_id"],
                teacher_id=a["teacher_id"],
                room_id=a["room_id"],
                day=a["day"],
                period=a["period"],
            ))

        job.timetable_id = timetable.id
        job.status = "done"
        job.progress = 100
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db = SessionLocal()
        job = db.query(SolveJob).filter(SolveJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


@router.post("")
def start_solve(body: SolveRequest, db: Session = Depends(get_db),
                _: User = Depends(get_current_user)):
    """Kick off an async solve job."""
    job = SolveJob(
        id=str(uuid.uuid4()),
        institution_id=body.institution_id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    t = threading.Thread(
        target=_run_solve,
        args=(job.id, body.institution_id, body.timetable_name,
              body.time_limit_s, body.seed),
        daemon=True,
    )
    t.start()

    return {"job_id": job.id, "status": "queued"}


@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db),
            _: User = Depends(get_current_user)):
    job = db.query(SolveJob).filter(SolveJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "result_status": job.result_status,
        "soft_score": job.soft_score,
        "violations": job.violations or [],
        "timetable_id": job.timetable_id,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.post("/demo")
def start_demo_solve(db: Session = Depends(get_db),
                     _: User = Depends(get_current_user)):
    """Solve the built-in sample dataset (no DB required). Returns job_id."""
    from app.solver.sample_data import build_sample_dataset

    job = SolveJob(id=str(uuid.uuid4()), institution_id="demo", status="queued")
    db.add(job); db.commit(); db.refresh(job)

    def _run():
        _db = SessionLocal()
        try:
            j = _db.query(SolveJob).filter(SolveJob.id == job.id).first()
            j.status = "running"; j.progress = 20; _db.commit()
            ds = build_sample_dataset()
            result = solve_timetable(ds, time_limit_s=45)
            j.result_status = result.status
            j.soft_score = result.soft_score
            j.violations = result.violations
            j.status = "done"; j.progress = 100
            j.finished_at = datetime.now(timezone.utc)
            _db.commit()
        finally:
            _db.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job.id, "status": "queued"}
