# Timely Standalone Timetable

This package runs the timetable product independently from the wider academic
platform. It includes institution setup, departments and calendars, programs,
divisions and batches, faculty and rooms, workload allocation, curriculum
requirements, feasibility checks, generation, publishing, holidays, absences,
and the timetable assistant. Attendance, messaging, exams, gradebooks, and
other platform modules are intentionally not loaded.

## Windows Quick Start

From this directory:

```powershell
.\start.ps1
```

The launcher uses a separate SQLite database, starts the API at
`http://127.0.0.1:8000`, and starts the web app at `http://127.0.0.1:5173`.
Stopping the frontend with `Ctrl+C` also stops the backend process started by
the launcher.

To run each process separately:

```powershell
.\start-backend.ps1
.\start-frontend.ps1
```

## Docker

Copy `.env.example` to `.env` and set a strong `SECRET_KEY`, then run:

```powershell
docker compose up --build
```

Open `http://localhost:5173`. The API is available at
`http://localhost:8000`; interactive API documentation is at
`http://localhost:8000/docs`.

## Verification

```powershell
.\verify.ps1
```

The verification script runs the standalone API tests, timetable solver tests,
and the production frontend build.
