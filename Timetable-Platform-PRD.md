# Product Requirements Document (PRD)
# "Timely" — Automated & Agentic Timetabling Platform

**Version:** 1.0 (Draft)
**Date:** 2026-08-17
**Status:** For review
**Author:** Product / Engineering

---

## 1. Executive Summary

**Timely** is a web-based platform that automatically creates, optimizes, and manages timetables for schools, colleges, universities, and offices (shift/room scheduling). Users enter their resources (teachers, classes, rooms, subjects, constraints), and a constraint-solving engine generates conflict-free timetables in minutes. An AI agent layer lets users manage schedules through natural language ("move all of Mr. Sharma's Friday classes to the morning"), explains conflicts, and suggests fixes.

**One-liner:** *"Google Calendar + an optimization engine + an AI assistant, purpose-built for institutional timetabling."*

---

## 2. Problem Statement

Creating timetables manually is one of the most painful recurring tasks in education and workforce management:

- **Time-consuming:** School administrators spend 2–6 weeks per term building timetables in Excel or on paper.
- **Error-prone:** Double-booked teachers, room clashes, and unbalanced workloads slip through constantly.
- **Rigid:** A single teacher falling sick triggers hours of manual reshuffling.
- **Hard to satisfy constraints:** "No more than 3 consecutive periods," "PE needs the field," "part-time teachers only on Tue/Thu," "Math in the morning" — hundreds of interacting rules that humans can't optimize simultaneously.
- **Existing tools fail:** Desktop tools (e.g., FET) have steep learning curves and no collaboration; enterprise tools (Untis, aSc, Scientia) are expensive; none offer AI-assisted management.

**Target market gap:** A modern, multi-tenant, web-based, AI-assisted timetabling SaaS that is affordable for a single school but scales to districts/universities.

---

## 3. Goals & Success Metrics

### 3.1 Product Goals

| # | Goal | Metric |
|---|------|--------|
| G1 | Generate a feasible timetable automatically | ≥ 95% of well-formed datasets produce a fully hard-constraint-satisfying timetable within 10 min |
| G2 | Reduce timetable creation effort | Admin time from ~2 weeks → < 1 day |
| G3 | Make edits effortless | Any single change (swap, move, substitution) completed in < 30 seconds with conflict checking |
| G4 | AI-assisted management | ≥ 60% of post-generation edits performed via natural language within 6 months of launch |
| G5 | Multi-institution support | One deployment serves schools, colleges, and office shift-scheduling use cases |

### 3.2 Non-Goals (V1)

- Student elective/course-request-based individual scheduling (V2+)
- Exam timetabling (V2)
- Payroll / attendance management
- Mobile native apps (responsive web first)

---

## 4. Personas

| Persona | Role | Needs |
|---------|------|-------|
| **Admin / Timetable Planner** | School principal's office, scheduler | Bulk data entry, constraint definition, generation, editing, publishing |
| **Teacher / Staff** | Views own schedule | Personal timetable, availability input, substitution notifications |
| **Student / Parent** | Views class schedule | Read-only class timetable, change notifications |
| **Office Manager** | Corporate use case | Shift/roster scheduling, meeting-room allocation |
| **Institution Owner** | Multi-campus admin | Cross-campus resources, analytics |

---

## 5. Core Domain Model

```
Institution
 ├── AcademicYear / Term
 ├── Buildings & Rooms (capacity, type: lab/classroom/field, features)
 ├── Teachers (subjects qualified, max hours/day & week, availability windows)
 ├── Classes / Student Groups (size, grade, curriculum)
 ├── Subjects (lessons/week per class, preferred room type, 
 │             allowed double-periods, max per day)
 ├── Timeslots (days/week, periods/day, breaks, assembly slots)
 └── Constraints (hard & soft, scoped: global / teacher / class / subject / room)

Lesson (the unit to be scheduled):
  { class, subject, teacher(s), duration, required room type, lessons_per_week }

Timetable (a solved assignment):
  Lesson → { timeslot, room }  + Score (hard/soft) + Version
```

---

## 6. Functional Requirements

### 6.1 Phase 1 — MVP (Months 1–3)

**A. Onboarding & Data Management**
- A1. Institution signup, org profile (days/week, periods/day, term dates).
- A2. CRUD for teachers, rooms, classes, subjects with CSV/Excel bulk import + validation errors shown per row.
- A3. Teacher availability grid (click-to-toggle unavailable slots).
- A4. Curriculum mapping: "Class 8-A needs Math 5×/week, English 4×/week…" with assigned teacher pools.
- A5. Pre-solve validation: warn when demand exceeds supply (e.g., "Physics needs 12 lab slots/week but the lab only has 10 free slots").

**B. Constraint Configuration**
- B1. Hard constraints (must hold): no teacher/room/class double-booking; room capacity; teacher availability; pinned (fixed) lessons.
- B2. Soft constraints (scored & optimized): teacher max consecutive periods, preferred slots, subject spread across week, minimize teacher idle gaps, balance daily load, room-type preference.
- B3. Per-constraint weight sliders (low/medium/high).

**C. Generation Engine**
- C1. One-click "Generate Timetable" → async job → result with score breakdown (which soft constraints were violated, where, and by how much).
- C2. Solve progress indicator + ability to stop and keep best solution so far.
- C3. Multiple timetable versions per term; compare two versions side by side.

**D. Viewing & Manual Editing**
- D1. Grid views: by class, by teacher, by room. Weekly grid, color-coded by subject.
- D2. Drag-and-drop editing with **live conflict detection** (red highlight + reason tooltip).
- D3. Undo/redo, change history with author and timestamp.
- D4. Print-friendly export: PDF, Excel, CSV; per-class and per-teacher printouts.

**E. Publishing & Access**
- E1. "Publish" a timetable version → read-only links for teachers/students.
- E2. Role-based access: Owner, Planner, Teacher, Viewer.

### 6.2 Phase 2 — Intelligence & Agentic Layer (Months 4–6)

- F1. **AI Chat Assistant** (agentic): natural-language commands with tool use —
  - "Move all of Class 9-B's PE to the afternoon" → agent calls solver/edit tools, shows diff preview, user confirms.
  - "Why can't I place Chemistry on Monday P2?" → agent explains the violated constraints in plain English.
  - "Ms. Rao is sick tomorrow, arrange substitutes" → agent proposes substitute assignments minimizing disruption.
- F2. **Natural-language constraint creation**: "No teacher should have more than 2 consecutive classes" → agent converts to a formal soft constraint, shows interpretation for confirmation.
- F3. **Substitution management**: teacher absence → auto-suggest qualified free teachers, notify them.
- F4. **What-if scenarios**: duplicate a timetable, apply changes, compare scores.
- F5. Notifications: email/in-app when published schedule changes affect you.

### 6.3 Phase 3 — Scale & Ecosystem (Months 7–12)

- G1. Multi-campus support, shared teacher pools across campuses.
- G2. Office/shift-scheduling mode (rosters, meeting rooms) — the same engine, different vocabulary.
- G3. Exam timetabling module.
- G4. Calendar integrations (Google Calendar, Outlook, ICS feeds).
- G5. Public REST API + webhooks.
- G6. Analytics: teacher workload distribution, room utilization heatmaps.
- G7. Localization (multi-language UI).

---

## 7. The Scheduling Engine (Technical Core)

### 7.1 Approach

The problem is a **Constraint Satisfaction & Optimization Problem** (NP-hard). Use a dedicated open-source solver — do NOT write your own heuristic from scratch.

**Recommended: Google OR-Tools CP-SAT (Python)** — Apache 2.0, battle-tested, excellent Python API, strong at proving feasibility/infeasibility.
**Alternative: Timefold Solver (Java/Kotlin)** — Apache 2.0 community edition, object-oriented domain modeling (constraints written as streams over your own classes), ships an official *school timetabling quickstart*, better incremental/delta scoring for interactive re-solve. Best choice if the team is JVM-based.

### 7.2 Constraint Catalog (minimum viable set)

| Type | Constraint | Hard/Soft |
|------|-----------|-----------|
| Resource | Teacher teaches ≤ 1 lesson per slot | Hard |
| Resource | Room hosts ≤ 1 lesson per slot | Hard |
| Resource | Class attends ≤ 1 lesson per slot | Hard |
| Availability | Teacher unavailable slots respected | Hard |
| Capacity | Room capacity ≥ class size | Hard |
| Room type | Lab subjects → lab rooms only | Hard |
| Fixed | Pinned lessons stay put | Hard |
| Workload | Teacher ≤ N periods/day, ≤ M/week | Hard or Soft |
| Continuity | ≤ K consecutive periods per teacher | Soft |
| Distribution | Subject spread across days (not 3× Math same day) | Soft |
| Preference | Preferred/avoided slots for subjects (e.g., PE not first period) | Soft |
| Gaps | Minimize teacher idle gaps | Soft |
| Balance | Even daily load per class | Soft |

### 7.3 Engine Service Interface

```
POST /solve
  input:  { problem_dataset (JSON), constraints, time_limit_s, seed? }
  output: { job_id }

GET /solve/{job_id}
  output: { status, score: {hard, soft}, violations[], assignment[] }
```

- Solves run in a **background job queue** (Celery/Redis or BullMQ) — never in the request path.
- Time-boxed (default 5–10 min), returns best solution found.
- Deterministic mode (fixed seed) for reproducibility.
- **Incremental re-solve**: when the user edits, re-solve only affected lessons, pinning the rest.

---

## 8. The Agentic Layer (AI Assistant)

### 8.1 Architecture

```
User message → LLM (tool-calling) → Tools:
   ├── query_timetable(entities, filters)
   ├── explain_conflict(lesson, slot)
   ├── propose_move(lesson, slot) → returns diff + new score
   ├── apply_change(change_set)  ← requires user confirmation
   ├── create_constraint(natural_language → formal DSL)
   ├── find_substitute(teacher, date)
   └── run_partial_solve(scope)
```

### 8.2 Safety Rules

- Agent **never mutates a published timetable without explicit confirmation**; always shows a diff preview.
- All agent actions go through the same validation/service layer as UI actions (single source of truth for rules).
- Agent actions are logged in the audit trail.
- If a request is infeasible, the agent must explain *which constraints conflict* rather than silently relaxing hard constraints.

### 8.3 Tech

- Any function-calling-capable LLM via provider API; abstracted behind an interface so providers are swappable.
- Constraint DSL (JSON schema) as the bridge between natural language and the solver.

---

## 9. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Performance | Solve 500-lesson school dataset ≤ 10 min; UI interactions < 200 ms p95 |
| Scale | 10k lessons/dataset; 1k concurrent read users |
| Multi-tenancy | Full data isolation per institution; row-level tenant scoping |
| Security | RBAC, encrypted at rest/in transit, audit log of all timetable mutations |
| Reliability | 99.5% uptime; solve jobs survive restarts (queued & resumable) |
| Data | Daily backups; export-all-data anytime (no lock-in) |
| Accessibility | WCAG 2.1 AA for the planner UI |
| Browser | Modern Chrome/Edge/Firefox/Safari; responsive down to tablet |

---

## 10. Technical Architecture (Recommended Stack)

```
┌─────────────────────────────────────────────────────┐
│  Frontend: Next.js (React + TypeScript)             │
│  - Timetable grid: custom or dnd-kit + FullCalendar │
│  - Tailwind + shadcn/ui, TanStack Query             │
├─────────────────────────────────────────────────────┤
│  API Layer: FastAPI (Python) or NestJS (Node)       │
│  - REST + WebSocket (solve progress, notifications) │
│  - Auth: JWT + RBAC (Clerk/Auth0 or self-hosted)    │
├──────────────┬──────────────────┬───────────────────┤
│ Solver Svc   │ AI Agent Svc     │ Notification Svc  │
│ OR-Tools     │ LLM tool-calling │ Email (SES)       │
│ CP-SAT       │ + constraint DSL │ In-app            │
├──────────────┴──────────────────┴───────────────────┤
│  Job Queue: Celery + Redis (solve jobs, emails)     │
│  DB: PostgreSQL  |  Cache: Redis  |  Storage: S3    │
└─────────────────────────────────────────────────────┘
```

**Why this stack:**
- Python end-to-end (FastAPI + OR-Tools + LLM SDKs) = one language for app, solver, and AI.
- PostgreSQL handles the relational domain model naturally; JSONB for constraint DSL storage.
- Solver as a separate service → scale workers independently; heavy solves never block the API.
- Start as a **modular monolith** (one repo, solver imported as a package), split into services only when load demands it.

---

## 11. Open-Source Landscape (Build vs. Leverage)

| Project | What it is | License | How to use it |
|---------|-----------|---------|---------------|
| **Google OR-Tools (CP-SAT)** | Constraint solver library | Apache 2.0 | ⭐ Recommended engine (Python) |
| **Timefold Solver** (ex-OptaPlanner) | Optimization solver w/ school-timetabling quickstart | Apache 2.0 (community) | ⭐ Recommended engine (Java/Kotlin) |
| **FET** | Complete desktop timetabling app (C++/Qt) | AGPLv3 | Reference for constraint catalog & UX ideas; ⚠️ AGPL — don't embed in proprietary SaaS |
| **UniTime** | Full university timetabling system (Java) | Open source | Fork/reference for higher-ed features (course requests, exam scheduling) |
| **Gibbon / openSIS / Fedena CE** | School management systems with basic timetable modules | GPL / varies | Reference only — their timetabling is manual, not auto-generated |
| **FullCalendar / dnd-kit** | Calendar UI & drag-drop | MIT | Frontend building blocks |

**Strategy:** Build the product, borrow the engine. Your moat is the UX + agentic layer, not the solver.

---

## 12. Roadmap

| Phase | Timeline | Deliverable | Exit criteria |
|-------|----------|-------------|---------------|
| 0. Spike | Weeks 1–2 | Solver prototype: load sample dataset, generate clash-free timetable | 200-lesson school solved < 5 min |
| 1. MVP | Months 1–3 | Data mgmt, constraints, generation, grid edit, publish, PDF export | Pilot with 1 real school end-to-end |
| 2. Agentic | Months 4–6 | AI assistant (explain/edit/substitute), notifications | 3–5 pilot institutions, NPS ≥ 30 |
| 3. Scale | Months 7–12 | Multi-campus, office mode, exam module, API, integrations | 20+ paying institutions |

**Pilot plan:** Run one term in parallel with the school's existing process before switching the published source of truth. Clean data first — bad input data is the #1 cause of solver failure.

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Infeasible datasets frustrate users | Pre-solve validation + typed infeasibility reports ("which constraints conflict") |
| Solver too slow on large datasets | Time-boxed solve, incremental re-solve, horizontal solver workers |
| Every school has unique rules | Extensible constraint DSL + natural-language constraint creation |
| AI agent makes destructive changes | Confirmation gates, diff previews, audit log, published-version protection |
| AGPL contamination (FET) | Use Apache 2.0 solvers (OR-Tools/Timefold); FET for ideas only |
| Adoption resistance from admins | CSV import from Excel, familiar grid UX, parallel-run pilot |

---

## 14. Open Questions

1. Primary beachhead market: K-12 schools, colleges, or offices? (Recommendation: K-12 — biggest pain, clearest ROI.)
2. Pricing model: per-institution flat vs. per-student? (Recommendation: flat annual per institution, tiered by size.)
3. Which LLM provider(s) for the agent layer, and self-host vs. API?
4. Offline support needs (low-connectivity regions)?
5. Regional calendar/localization requirements for launch market?

---

*End of PRD — v1.0 Draft*
