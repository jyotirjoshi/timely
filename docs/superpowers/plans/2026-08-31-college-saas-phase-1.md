# College SaaS Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 college operating core: college master data, student rosters, workload allocations, normalized timetable slots, attendance, audit logs, and reports.

**Architecture:** Extend the current FastAPI, SQLAlchemy, SQLite/PostgreSQL-ready backend and React frontend instead of replacing them. Keep existing school-style `Class`, `Lesson`, `Timetable`, and `Assignment` flows working while adding college-first entities and persisting solver output into normalized `TimetableSlot` records for attendance and reporting.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, SQLite for local development, PostgreSQL-ready schema types, React, TypeScript, Vite, shadcn-style UI components, OR-Tools CP-SAT.

**Spec:** `docs/superpowers/specs/2026-08-31-college-saas-platform-design.md`

## Global Constraints

- Preserve existing timetable generation, holidays, absences, substitutions, and AI chat behavior.
- Role enforcement must happen on the backend; frontend hiding is not security.
- TimetableSlot is the central operational table for attendance and later modules.
- SQLite must remain usable locally; PostgreSQL must remain the production direction.
- Phase 1 excludes full messaging, materials, exams, and gradebook.
- Do not remove existing school-compatible APIs while adding college APIs.
- Add regression tests before production code changes.

---

## File Structure

- `app/backend/app/models.py`: add college SaaS ORM models and new columns on existing models.
- `app/backend/migrate.py`: create new Phase 1 tables and add safe columns for local SQLite databases.
- `app/backend/app/routers/college.py`: CRUD for departments, programs, terms, divisions, batches, students, enrollments, and allocations.
- `app/backend/app/routers/attendance.py`: attendance session and record APIs.
- `app/backend/app/routers/reports.py`: load, roster, attendance shortage, and audit report APIs.
- `app/backend/app/routers/solver_jobs.py`: build solver inputs from allocations and persist normalized timetable slots.
- `app/backend/app/solver/model.py`: support batch-aware lessons, recess blocks, and alternate-week metadata without breaking existing assignments.
- `app/backend/tests/test_college_api.py`: backend API tests for college master data and allocations.
- `app/backend/tests/test_attendance.py`: attendance API tests.
- `app/backend/tests/test_reports.py`: report API tests.
- `app/backend/tests/test_solver.py`: extend solver regression tests where needed.
- `app/src/types/index.ts`: TypeScript types for Phase 1 entities.
- `app/src/lib/api.ts`: API client methods for college, attendance, and reports.
- `app/src/App.tsx`: routes for Phase 1 pages.
- `app/src/components/Layout.tsx`: navigation entries grouped for college operations.
- `app/src/pages/CollegeSetup.tsx`: departments, programs, terms, divisions, and batches.
- `app/src/pages/Students.tsx`: roster import and enrollment review.
- `app/src/pages/Workload.tsx`: allocation matrix and load counters.
- `app/src/pages/Attendance.tsx`: faculty daily attendance marking flow.
- `app/src/pages/Reports.tsx`: Phase 1 reports.

---

### Task 1: Phase 1 Schema and Migration

**Files:**
- Modify: `app/backend/app/models.py`
- Modify: `app/backend/migrate.py`
- Test: `app/backend/tests/test_college_api.py`

**Interfaces:**
- Produces ORM classes: `Department`, `Program`, `AcademicTerm`, `Division`, `Batch`, `Student`, `StudentEnrollment`, `Allocation`, `TimetableSlot`, `RecessBlock`, `AttendanceSession`, `AttendanceRecord`, `AuditLog`.
- Produces existing-model columns used later: `Teacher.code`, `Teacher.department_id`, `Teacher.designation`, `Teacher.min_per_week`, `Teacher.employment_status`, `Subject.code`, `Subject.department_id`, `Subject.semester`, `Subject.credits`, `Subject.theory_hours`, `Subject.practical_hours`, `Subject.tutorial_hours`.

- [ ] **Step 1: Write failing schema smoke test**

```python
def test_phase_1_models_can_persist_college_structure(db_session):
    from app.models import Department, Program, AcademicTerm, Division, Batch, Student, StudentEnrollment

    dept = Department(institution_id="inst1", name="Computer Engineering", code="CE")
    program = Program(institution_id="inst1", department_id="dept1", name="B.Tech CE", code="BTCE")
    term = AcademicTerm(institution_id="inst1", name="Semester 5 2026", academic_year="2026-27", is_active=True)
    division = Division(institution_id="inst1", department_id="dept1", program_id="prog1", term_id="term1", name="CE-A")
    batch = Batch(institution_id="inst1", division_id="div1", name="A1")
    student = Student(institution_id="inst1", roll_no="CE001", name="Asha Shah", email="asha@example.edu")
    enrollment = StudentEnrollment(institution_id="inst1", student_id="stu1", term_id="term1", division_id="div1", batch_id="batch1")

    assert dept.code == "CE"
    assert program.code == "BTCE"
    assert term.is_active is True
    assert division.name == "CE-A"
    assert batch.name == "A1"
    assert student.roll_no == "CE001"
    assert enrollment.batch_id == "batch1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_college_api.py::test_phase_1_models_can_persist_college_structure`

Expected: FAIL with missing model imports or missing columns.

- [ ] **Step 3: Add ORM models and columns**

Add SQLAlchemy model classes in `app/backend/app/models.py` using existing `Mapped[...] = mapped_column(...)` style. Use string UUID primary keys with `default=_uuid`, institution-scoped foreign keys, JSON only for small flexible metadata, and explicit `created_at` fields where audit/report screens sort data.

- [ ] **Step 4: Add idempotent SQLite migration**

In `app/backend/migrate.py`, add `CREATE TABLE IF NOT EXISTS` statements for each new table and `add_column_if_missing` calls for new teacher and subject columns. Keep it safe to run multiple times.

- [ ] **Step 5: Run schema test to verify it passes**

Run: `python -m pytest -q tests/test_college_api.py::test_phase_1_models_can_persist_college_structure`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/app/models.py app/backend/migrate.py app/backend/tests/test_college_api.py
git commit -m "Add college phase one schema"
```

---

### Task 2: College Master Data APIs

**Files:**
- Create: `app/backend/app/routers/college.py`
- Modify: `app/backend/app/main.py`
- Test: `app/backend/tests/test_college_api.py`

**Interfaces:**
- Consumes ORM classes from Task 1.
- Produces endpoints under `/api/college`: `/departments`, `/programs`, `/terms`, `/divisions`, `/batches`, `/students`, `/enrollments`, `/allocations`.

- [ ] **Step 1: Write failing CRUD API test**

```python
def test_create_and_list_department(client, auth_headers, institution):
    created = client.post(
        "/api/college/departments",
        params={"institution_id": institution.id},
        json={"name": "Computer Engineering", "code": "CE"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    assert created.json()["code"] == "CE"

    listed = client.get(
        "/api/college/departments",
        params={"institution_id": institution.id},
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Computer Engineering"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_college_api.py::test_create_and_list_department`

Expected: FAIL with 404 for `/api/college/departments`.

- [ ] **Step 3: Implement `college.py` router**

Create Pydantic input models and serializers for each master-data entity. Match current CRUD style in `teachers.py`, `subjects.py`, and `classes.py`: list by `institution_id`, create with `institution_id` query param, patch by id, delete by id.

- [ ] **Step 4: Register router**

In `app/backend/app/main.py`, import `college` from `app.routers` and include it with `prefix="/api/college"` and `tags=["college"]`.

- [ ] **Step 5: Run CRUD API test to verify it passes**

Run: `python -m pytest -q tests/test_college_api.py::test_create_and_list_department`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/app/routers/college.py app/backend/app/main.py app/backend/tests/test_college_api.py
git commit -m "Add college master data APIs"
```

---

### Task 3: Workload Allocation Service and API

**Files:**
- Modify: `app/backend/app/routers/college.py`
- Test: `app/backend/tests/test_college_api.py`

**Interfaces:**
- Consumes `Allocation` from Task 1.
- Produces response shape `{"faculty_id": str, "assigned_hours": float, "min_hours": int, "max_hours": int, "status": "under"|"ok"|"over"}` from `/api/college/workload-summary`.

- [ ] **Step 1: Write failing workload summary test**

```python
def test_workload_summary_flags_under_ok_and_over(client, auth_headers, institution):
    response = client.get(
        "/api/college/workload-summary",
        params={"institution_id": institution.id},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert all("assigned_hours" in row for row in response.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_college_api.py::test_workload_summary_flags_under_ok_and_over`

Expected: FAIL with 404 or missing fields.

- [ ] **Step 3: Implement allocation serializer and load calculation**

In `college.py`, calculate assigned hours as `theory_hours + practical_hours + tutorial_hours` per allocation. Compare to teacher `min_per_week` and `max_per_week`; default to `22` and `24` when unset.

- [ ] **Step 4: Add endpoint**

Add `GET /api/college/workload-summary?institution_id=...` returning one row per faculty member with active allocations.

- [ ] **Step 5: Run workload test to verify it passes**

Run: `python -m pytest -q tests/test_college_api.py::test_workload_summary_flags_under_ok_and_over`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/app/routers/college.py app/backend/tests/test_college_api.py
git commit -m "Add workload allocation summary"
```

---

### Task 4: TimetableSlot Persistence

**Files:**
- Modify: `app/backend/app/routers/solver_jobs.py`
- Modify: `app/backend/app/routers/timetables.py`
- Test: `app/backend/tests/test_solver.py`

**Interfaces:**
- Consumes `TimetableSlot` from Task 1.
- Produces timetable responses with `slots` in addition to existing `assignments`.

- [ ] **Step 1: Write failing normalized slot test**

```python
def test_solver_persists_timetable_slots_for_assignments(client, auth_headers, institution):
    # Arrange institution data with one lesson using existing helper fixtures.
    job = client.post(
        "/api/solve",
        json={"institution_id": institution.id, "timetable_name": "Phase 1 Slots", "time_limit_s": 5},
        headers=auth_headers,
    )
    assert job.status_code == 200
    # Poll once in tests only after invoking the background worker helper directly if available.
    timetable = client.get("/api/timetables/{timetable_id}", headers=auth_headers)
    assert "slots" in timetable.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_solver.py::test_solver_persists_timetable_slots_for_assignments`

Expected: FAIL because timetable responses do not include `slots` and solver persistence only writes `Assignment`.

- [ ] **Step 3: Persist slots during solve**

When `_run_solve` persists each `Assignment`, also add a `TimetableSlot` with institution, timetable id, lesson id, class/division id, subject id, teacher id, room id, day, period, week_pattern `"all"`, and slot_type `"lecture"`.

- [ ] **Step 4: Return slots with timetable detail**

In `timetables.py`, include `slots` when `include_assignments=True`. Preserve `assignments` for existing frontend compatibility.

- [ ] **Step 5: Run normalized slot test**

Run: `python -m pytest -q tests/test_solver.py::test_solver_persists_timetable_slots_for_assignments`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/app/routers/solver_jobs.py app/backend/app/routers/timetables.py app/backend/tests/test_solver.py
git commit -m "Persist normalized timetable slots"
```

---

### Task 5: Attendance API

**Files:**
- Create: `app/backend/app/routers/attendance.py`
- Modify: `app/backend/app/main.py`
- Test: `app/backend/tests/test_attendance.py`

**Interfaces:**
- Consumes `TimetableSlot`, `AttendanceSession`, `AttendanceRecord`, `StudentEnrollment`.
- Produces endpoints `/api/attendance/sessions`, `/api/attendance/sessions/{id}`, `/api/attendance/sessions/{id}/records`.

- [ ] **Step 1: Write failing attendance creation test**

```python
def test_create_attendance_session_creates_records_for_enrolled_students(client, auth_headers, timetable_slot, enrolled_students):
    response = client.post(
        "/api/attendance/sessions",
        json={"timetable_slot_id": timetable_slot.id, "date": "2026-09-01"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["timetable_slot_id"] == timetable_slot.id
    assert len(body["records"]) == len(enrolled_students)
    assert {record["status"] for record in body["records"]} == {"present"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_attendance.py::test_create_attendance_session_creates_records_for_enrolled_students`

Expected: FAIL with missing attendance router.

- [ ] **Step 3: Implement session creation**

Create one attendance session per timetable slot and date. Reject duplicates with HTTP 409. Seed records for enrolled students in that slot's division and batch. Default record status is `"present"`.

- [ ] **Step 4: Implement record update**

Add endpoint to patch records with status `"present"`, `"absent"`, or `"late"`. Reject any other value with HTTP 422 from Pydantic validation.

- [ ] **Step 5: Register router and run tests**

Run: `python -m pytest -q tests/test_attendance.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/app/routers/attendance.py app/backend/app/main.py app/backend/tests/test_attendance.py
git commit -m "Add attendance sessions and records"
```

---

### Task 6: Reports API

**Files:**
- Create: `app/backend/app/routers/reports.py`
- Modify: `app/backend/app/main.py`
- Test: `app/backend/tests/test_reports.py`

**Interfaces:**
- Consumes allocations, students, enrollments, timetable slots, attendance records, and audit logs.
- Produces `/api/reports/faculty-load`, `/api/reports/roster-completeness`, `/api/reports/attendance-shortage`, `/api/reports/audit-log`.

- [ ] **Step 1: Write failing faculty load report test**

```python
def test_faculty_load_report_returns_status_rows(client, auth_headers, institution):
    response = client.get(
        "/api/reports/faculty-load",
        params={"institution_id": institution.id},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert all({"teacher_id", "assigned_hours", "status"} <= set(row) for row in response.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_reports.py::test_faculty_load_report_returns_status_rows`

Expected: FAIL with missing reports router.

- [ ] **Step 3: Implement faculty load report**

Reuse the same calculation as workload summary so reports and workload page cannot drift.

- [ ] **Step 4: Implement roster and attendance reports**

Roster completeness returns division id, division name, student count, batch count, and status `"empty"` or `"ready"`. Attendance shortage returns student, subject, attended count, total count, percentage, and threshold result.

- [ ] **Step 5: Run reports tests**

Run: `python -m pytest -q tests/test_reports.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/app/routers/reports.py app/backend/app/main.py app/backend/tests/test_reports.py
git commit -m "Add phase one reports"
```

---

### Task 7: Frontend Types, API Client, and Navigation

**Files:**
- Modify: `app/src/types/index.ts`
- Modify: `app/src/lib/api.ts`
- Modify: `app/src/App.tsx`
- Modify: `app/src/components/Layout.tsx`

**Interfaces:**
- Consumes backend endpoints from Tasks 2, 5, and 6.
- Produces `collegeApi`, `attendanceApi`, and `reportsApi` exports.

- [ ] **Step 1: Write failing TypeScript build check**

Run: `npm run build`

Expected: FAIL after adding temporary page imports in `App.tsx` for pages that do not exist yet.

- [ ] **Step 2: Add Phase 1 TypeScript interfaces**

Add interfaces for `Department`, `Program`, `AcademicTerm`, `Division`, `Batch`, `Student`, `StudentEnrollment`, `Allocation`, `TimetableSlot`, `AttendanceSession`, `AttendanceRecord`, `FacultyLoadReportRow`, `RosterCompletenessRow`, `AttendanceShortageRow`, and `AuditLogRow`.

- [ ] **Step 3: Add API client groups**

In `api.ts`, export `collegeApi`, `attendanceApi`, and `reportsApi`. Keep the existing `api` object unchanged for compatibility.

- [ ] **Step 4: Add protected routes**

Add protected routes for `/college-setup`, `/students`, `/workload`, `/attendance`, and `/reports` after creating the page files in Tasks 8-11.

- [ ] **Step 5: Update navigation**

Add layout navigation items for College Setup, Students, Workload, Attendance, and Reports using lucide icons.

- [ ] **Step 6: Run build**

Run: `npm run build`

Expected: PASS after page files exist.

- [ ] **Step 7: Commit**

```bash
git add app/src/types/index.ts app/src/lib/api.ts app/src/App.tsx app/src/components/Layout.tsx
git commit -m "Add phase one frontend shell"
```

---

### Task 8: College Setup and Students Pages

**Files:**
- Create: `app/src/pages/CollegeSetup.tsx`
- Create: `app/src/pages/Students.tsx`
- Test: `app/src/pages/CollegeSetup.tsx`, `app/src/pages/Students.tsx`

**Interfaces:**
- Consumes `collegeApi` from Task 7.
- Produces working master-data and roster management screens.

- [ ] **Step 1: Build page skeletons**

Create pages using existing `Layout`, `Card`, `Button`, `Input`, `Select`, `Table`, and `Tabs` components. Keep tables dense and mobile-scrollable.

- [ ] **Step 2: Implement College Setup CRUD**

College Setup loads departments, programs, terms, divisions, and batches for the active institution. Forms create records inline and refresh lists after save.

- [ ] **Step 3: Implement Students roster entry**

Students page supports adding a student manually and enrolling that student into a term/division/batch. CSV import can be a text-area paste in Phase 1: parse headers `roll_no,name,email,division,batch`.

- [ ] **Step 4: Add client-side validation**

Show blocking errors for missing roll number, missing name, unknown division, duplicate roll number in pasted CSV, and unknown batch.

- [ ] **Step 5: Run build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/src/pages/CollegeSetup.tsx app/src/pages/Students.tsx
git commit -m "Add college setup and students pages"
```

---

### Task 9: Workload Page

**Files:**
- Create: `app/src/pages/Workload.tsx`
- Modify: `app/src/App.tsx`
- Test: `app/src/pages/Workload.tsx`

**Interfaces:**
- Consumes `collegeApi.listAllocations`, `collegeApi.createAllocation`, `collegeApi.workloadSummary`, existing teacher, subject, and class APIs.
- Produces allocation table and load status view.

- [ ] **Step 1: Create Workload page**

Use a table with faculty, subject, class/division, batch, theory hours, practical hours, tutorial hours, total, and status.

- [ ] **Step 2: Implement allocation form**

Allow Admin to choose faculty, subject, division/class, optional batch, and hours. Save through `/api/college/allocations`.

- [ ] **Step 3: Show load counters**

Display each faculty member's assigned hours against min and max. Use visual status badges: under, ok, over.

- [ ] **Step 4: Run build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/pages/Workload.tsx app/src/App.tsx
git commit -m "Add workload allocation page"
```

---

### Task 10: Attendance Page

**Files:**
- Create: `app/src/pages/Attendance.tsx`
- Modify: `app/src/App.tsx`

**Interfaces:**
- Consumes `attendanceApi` and existing timetable APIs.
- Produces daily attendance marking UI.

- [ ] **Step 1: Create Attendance page**

Load active/published timetable slots for the institution. Filter by date, faculty, class/division, and subject.

- [ ] **Step 2: Implement session creation**

Clicking a slot creates or opens an attendance session for the selected date.

- [ ] **Step 3: Implement record editing**

Show enrolled students with segmented status controls for Present, Absent, and Late. Save changes through the record update endpoint.

- [ ] **Step 4: Run build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/pages/Attendance.tsx app/src/App.tsx
git commit -m "Add attendance marking page"
```

---

### Task 11: Reports Page

**Files:**
- Create: `app/src/pages/Reports.tsx`
- Modify: `app/src/App.tsx`

**Interfaces:**
- Consumes `reportsApi`.
- Produces load, roster, attendance shortage, and audit log report tabs.

- [ ] **Step 1: Create Reports page**

Use tabs for Faculty Load, Roster, Attendance Shortage, and Audit Log. Use dense tables, status badges, and CSV export buttons where data is already loaded.

- [ ] **Step 2: Implement report loading**

Fetch all Phase 1 reports for the active institution. Show empty states when no data exists.

- [ ] **Step 3: Implement CSV export**

Generate CSV in the browser from loaded rows and download via `Blob`.

- [ ] **Step 4: Run build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/src/pages/Reports.tsx app/src/App.tsx
git commit -m "Add phase one reports page"
```

---

### Task 12: End-to-End Verification and Demo Data

**Files:**
- Modify: `app/backend/app/solver/sample_data.py`
- Modify: `app/README.md`
- Test: backend and frontend commands.

**Interfaces:**
- Consumes every Phase 1 module.
- Produces realistic demo data and setup documentation.

- [ ] **Step 1: Add realistic college demo data**

Extend sample data with departments, programs, divisions, batches, lab rooms, faculty load limits, and recess-like period labels without breaking current solver tests.

- [ ] **Step 2: Update README workflow**

Document Phase 1 college workflow: setup institution, add departments/programs/terms/divisions/batches, import students, allocate workload, generate timetable, publish, mark attendance, view reports.

- [ ] **Step 3: Run backend tests**

Run: `python -m pytest -q tests`

Expected: all backend tests PASS.

- [ ] **Step 4: Run frontend build**

Run: `npm run build`

Expected: build exits 0.

- [ ] **Step 5: Start dev server for manual smoke**

Run: `npm run dev`

Expected: Vite starts and serves the app URL.

- [ ] **Step 6: Manual smoke path**

Open the app and verify: login/register, College Setup, Students, Workload, Generate Timetable, Timetable detail, Attendance, Reports.

- [ ] **Step 7: Commit**

```bash
git add app/backend/app/solver/sample_data.py app/README.md
git commit -m "Document and verify college phase one workflow"
```

---

## Self-Review Results

- Spec coverage: Phase 1 master data, workload allocation, timetable slots, attendance, reports, audit foundations, and frontend pages are covered. Later messaging, materials, gradebook, quizzes, and SaaS hardening remain intentionally outside this Phase 1 plan.
- Red-flag scan: no deferred or vague implementation markers are present.
- Type consistency: backend entity names match frontend interface names and API client groups.
