"""
Timely Backend — FastAPI application entry point.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth, institutions, teachers, rooms, classes, subjects,
    lessons, timetables, solver_jobs, agent,
    holidays, absences, presets,
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    from app.db import init_db
    init_db()
    yield


app = FastAPI(
    title="Timely API",
    description="Automated & Agentic Timetabling Platform — College Edition",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        os.getenv("FRONTEND_URL", ""),
        # Allow all Vercel preview URLs
        "https://*.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,         prefix="/api/auth",         tags=["auth"])
app.include_router(institutions.router, prefix="/api/institutions", tags=["institutions"])
app.include_router(teachers.router,     prefix="/api/teachers",     tags=["teachers"])
app.include_router(rooms.router,        prefix="/api/rooms",        tags=["rooms"])
app.include_router(classes.router,      prefix="/api/classes",      tags=["classes"])
app.include_router(subjects.router,     prefix="/api/subjects",     tags=["subjects"])
app.include_router(lessons.router,      prefix="/api/lessons",      tags=["lessons"])
app.include_router(timetables.router,   prefix="/api/timetables",   tags=["timetables"])
app.include_router(solver_jobs.router,  prefix="/api/solve",        tags=["solve"])
app.include_router(agent.router,        prefix="/api/agent",        tags=["agent"])
app.include_router(holidays.router,     prefix="/api/holidays",     tags=["holidays"])
app.include_router(absences.router,     prefix="/api/absences",     tags=["absences"])
app.include_router(presets.router,      prefix="/api/presets",      tags=["presets"])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "timely-api", "version": "1.0.0"}
