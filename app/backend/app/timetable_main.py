"""Standalone Timely timetable product API.

Run with:
    uvicorn app.timetable_main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    absences,
    academics,
    agent,
    auth,
    classes,
    curriculum_requirements,
    departments,
    holidays,
    institutions,
    lessons,
    presets,
    rooms,
    solver_jobs,
    subjects,
    teachers,
    timetables,
    workloads,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    from app.db import init_db

    init_db()
    yield


app = FastAPI(
    title="Timely Standalone Timetable API",
    description="Independent college and university timetable planning product",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROUTERS = (
    (auth.router, "/api/auth", "auth"),
    (institutions.router, "/api/institutions", "institutions"),
    (departments.router, "/api/departments", "departments"),
    (academics.router, "/api/academics", "academics"),
    (teachers.router, "/api/teachers", "teachers"),
    (rooms.router, "/api/rooms", "rooms"),
    (classes.router, "/api/classes", "legacy classes"),
    (subjects.router, "/api/subjects", "subjects"),
    (workloads.router, "/api/workloads", "workloads"),
    (lessons.router, "/api/lessons", "legacy curriculum"),
    (curriculum_requirements.router, "/api/curriculum-requirements", "curriculum"),
    (timetables.router, "/api/timetables", "timetables"),
    (solver_jobs.router, "/api/solve", "solve"),
    (agent.router, "/api/agent", "agent"),
    (holidays.router, "/api/holidays", "holidays"),
    (absences.router, "/api/absences", "absences"),
    (presets.router, "/api/presets", "presets"),
)

for router, prefix, tag in ROUTERS:
    app.include_router(router, prefix=prefix, tags=[tag])


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "timely-timetable-api",
        "product": "timetable",
        "version": "1.0.0",
    }
