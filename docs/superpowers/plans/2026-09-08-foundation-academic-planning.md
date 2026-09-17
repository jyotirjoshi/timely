# Foundation and Academic Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the secure master-data, workload-allocation, curriculum, and multi-calendar timetable foundation required by every later academic module.

**Architecture:** Extend the existing FastAPI and React modular monolith with tenant-scoped academic entities and a global OR-Tools CP-SAT model. Department calendars supply real time ranges; shared faculty and rooms are protected globally. The AI remains a proposal/explanation layer over deterministic services.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2, PostgreSQL/SQLite, Pydantic 2, OR-Tools CP-SAT, React 19, TypeScript, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-multi-calendar-university-solver-design.md`; product requirements: `Timetable-Platform-PRD.md` and `C:/Users/spars/Downloads/Unified_Academic_Platform_Requirements.docx`.

## Global Constraints

- All tenant-owned queries derive institution scope from the authenticated user.
- Only admin/owner/planner roles mutate academic planning data.
- Department periods use actual local start/end times; overlap is based on time ranges, not period numbers.
- Shared faculty, rooms, and labs cannot overlap across departments.
- Labs are fixed contiguous blocks and each division has at most two labs per day.
- Published timetables must have zero hard violations and complete required weekly hours.
- The LLM never writes assignments or relaxes hard constraints.
- OR-Tools remains the scheduling engine under Apache 2.0; no GPL code is embedded.

---

### Task 1: Tenant Access and Planning Roles

**Files:** Create `app/backend/app/services/access.py`; modify planning routers; create `app/backend/tests/test_tenant_access.py`.

**Interfaces:** Produce `institution_for(user, requested_id=None) -> str`, `require_roles(*roles)`, and tenant-scoped resource lookup helpers.

- [ ] Write failing tests proving cross-institution list/create/get/update/delete access is rejected and faculty/student users cannot mutate planning data.
- [ ] Run `python -m pytest -q tests/test_tenant_access.py`; verify expected 403/404 failures.
- [ ] Implement current-user tenant derivation and admin/owner/planner mutation guards across institution, faculty, room, class, subject, curriculum, timetable, solve, absence, holiday, and agent routes.
- [ ] Re-run the focused test and full backend suite; commit `feat: enforce academic planning access boundaries`.

### Task 2: Academic Organization and Department Calendars

**Files:** Modify `app/backend/app/models.py` and `app/backend/migrate.py`; create `app/backend/app/routers/departments.py`, `app/backend/app/services/calendars.py`, and `app/backend/tests/test_department_calendars.py`.

**Interfaces:** Add `School`, `Department`, `DepartmentCalendar`, `CalendarPeriod`, and `FacultyShift`; produce `ranges_overlap(start_a, end_a, start_b, end_b) -> bool` and `valid_activity_windows(calendar, duration_minutes) -> list[TimeWindow]`.

- [ ] Write failing tests for two departments with different periods, break exclusion, non-monotonic period rejection, shift-window containment, and half-open overlap behavior.
- [ ] Run focused tests and verify failures occur because the entities/services are absent.
- [ ] Implement models, migration, tenant-scoped CRUD, and calendar validation using `datetime.time` values plus institution timezone.
- [ ] Re-run focused and full tests; commit `feat: add department calendars and faculty shifts`.

### Task 3: Programs, Divisions, Batches, Students, and Rosters

**Files:** Modify `app/backend/app/models.py` and migration; create `app/backend/app/routers/academics.py`, `app/backend/app/services/roster_import.py`, `app/backend/tests/test_academic_rosters.py`.

**Interfaces:** Add `Program`, `Division`, `Batch`, `Student`, and `Enrollment`; produce `parse_roster_csv(content, division_id) -> RosterImportResult` with row-level errors.

- [ ] Write failing tests for tenant ownership, unique student identifiers per institution, batch membership, CSV validation, duplicate rows, and atomic import.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement models, APIs, and import service; reject cross-department relationships.
- [ ] Re-run focused/full tests; commit `feat: add academic rosters and batch structure`.

### Task 4: Subject Scheme, Faculty Preferences, and Workload Allocation

**Files:** Modify models/migration; create `app/backend/app/routers/workloads.py`, `app/backend/app/services/workload.py`, `app/backend/tests/test_workload_allocation.py`; add React pages and API types for workload allocation.

**Interfaces:** Add `SubjectComponent`, `FacultyPreference`, and `WorkloadAllocation`; produce `summarize_workload(institution_id) -> list[FacultyLoadSummary]` and `suggest_allocations(...) -> AllocationProposal`.

- [ ] Write failing tests for theory/practical/tutorial hours, ranked preferences, qualification, cross-department faculty, 22-24 hour default band, under/over-load flags, and audited admin override.
- [ ] Run focused tests and verify failures.
- [ ] Implement allocation service and APIs; suggestions rank qualification, preference, current load, and department fit without silently overriding admin choices.
- [ ] Build the workload UI with assignment table and visible load status; run tests/build; commit `feat: add faculty workload allocation`.

### Task 5: Curriculum Requirements and Activity Expansion

**Files:** Modify models/migration; create `app/backend/app/routers/curriculum_requirements.py`, `app/backend/app/services/activity_expansion.py`, `app/backend/tests/test_activity_expansion.py`; update curriculum UI.

**Interfaces:** Add `CurriculumRequirement` and `SchedulingActivity`; produce `expand_requirements(term_id) -> ExpansionResult` idempotently.

- [ ] Write failing tests that lecture hours become single-period activities, labs become one fixed-duration block, batches can run parallel lab activities, and re-expansion neither duplicates nor loses pinned activities.
- [ ] Run focused tests and verify failures.
- [ ] Implement typed requirements for division/batch, subject component, weekly count, duration, faculty pool, room type, and alternate-week pattern.
- [ ] Update curriculum UI to collect these fields and preview generated activities; run tests/build; commit `feat: expand curriculum into scheduling activities`.

### Task 6: Preflight Feasibility Service

**Files:** Create `app/backend/app/services/solve_preflight.py`, `app/backend/tests/test_solve_preflight.py`; modify solve API and generation UI.

**Interfaces:** Produce `preflight(term_id) -> PreflightReport` with `code`, `entities`, `demand`, `capacity`, and `message` per issue.

- [ ] Write failing tests for missing calendars, no qualified faculty, no compatible lab, shift exclusion, contiguous-duration failure, faculty-pool overload, lab-capacity shortage, division-hours overflow, and unavoidable daily lab-limit failure.
- [ ] Run focused tests and verify each expected issue is missing.
- [ ] Implement preflight from persisted activities and calendars; block solve submission when any hard issue exists.
- [ ] Show the report before generation with links to affected setup pages; run tests/build; commit `feat: add timetable feasibility preflight`.

### Task 7: Global Multi-Calendar CP-SAT Solver

**Files:** Refactor `app/backend/app/solver/model.py`; create `app/backend/app/solver/dataset.py`, `app/backend/tests/test_multi_calendar_solver.py`; update `solver_jobs.py`.

**Interfaces:** Produce `build_solver_dataset(term_id) -> SolverDataset` and `solve_timetable(dataset, time_limit_s, seed) -> SolveResult` with assignments carrying real start/end times.

- [ ] Write failing tests for cross-department faculty/room overlap, local break exclusion, shift boundaries, room capacity/type, fixed contiguous labs, two-labs-per-division/day, complete weekly requirements, pinned activities, workload limits, and deterministic seeded results.
- [ ] Run focused tests and verify failures against the legacy period-index solver.
- [ ] Implement candidate-window variables and no-overlap constraints globally; solve hard feasibility before weighted optimization for gaps, theory streaks, subject spread, and preferences.
- [ ] Re-run focused/full tests; commit `feat: generate global multi-calendar timetables`.

### Task 8: Final Validation, Views, Versions, and Publishing

**Files:** Create `app/backend/app/services/timetable_validation.py`, `app/backend/app/routers/timetable_views.py`, `app/backend/tests/test_timetable_publish.py`; update timetable React pages and types.

**Interfaces:** Produce `validate_timetable(timetable_id) -> ValidationReport`; expose division, faculty, room, and lab views; add immutable published versions and audit entries.

- [ ] Write failing tests proving publish rejects incomplete hours or any clash, reports required-versus-allocated totals, protects published versions, and renders all four views from the same assignments.
- [ ] Run focused tests and verify failures.
- [ ] Implement validation, version snapshots, audit log, publish gate, filters, and exports-ready view payloads.
- [ ] Update UI with validation results and view tabs; run backend tests and frontend build; commit `feat: validate version and publish academic timetables`.

### Task 9: Safe AI Planning Tools

**Files:** Refactor `app/backend/app/routers/agent.py`; create `app/backend/app/services/agent_tools.py`, `app/backend/tests/test_agent_tools.py`; update `AIChat.tsx`.

**Interfaces:** AI tools can query workload/timetable, explain preflight, and create server-side proposals; application requires proposal ID, current timetable revision, planner role, and fresh validation.

- [ ] Write failing tests for malformed tool arguments, cross-tenant requests, hallucinated IDs, stale proposals, unqualified substitutes, invalid moves, and published-timetable protection.
- [ ] Run focused tests and verify failures.
- [ ] Implement typed read/propose tools with short-lived proposals and audit records; never accept browser-supplied change lists during apply.
- [ ] Update proposal preview UI; run backend tests/frontend build; commit `feat: add validated academic planning agent tools`.

### Task 10: End-to-End College Regression

**Files:** Create `app/backend/tests/fixtures/university_term.py`, `app/backend/tests/test_university_term_e2e.py`; update `app/README.md`.

- [ ] Build a realistic two-school, multi-department fixture with different calendars, shared faculty/rooms, batch labs, shifts, preferences, and 22-24 hour workloads.
- [ ] Test setup through allocation, activity expansion, preflight, solve, validation, all timetable views, version publication, and one safe AI proposal.
- [ ] Run `python -m pytest -q tests` and `npm run build`; fix only failures proven by the end-to-end test.
- [ ] Document setup, constraints, open-source attribution, migrations, and production job-runner requirements; commit `test: add university planning regression suite`.

## Deferred Plans

- Attendance and shortage alerts based on published timetable slots and roster.
- Announcements, materials, and scoped faculty-student messaging.
- Quizzes, exams, mark heads, gradebook, and publication.
- Cross-module reporting, exports, notifications, backups, and optional Moodle LTI integration.
