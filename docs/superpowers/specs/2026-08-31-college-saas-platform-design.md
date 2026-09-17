# College SaaS Platform Design

Date: 2026-08-31

## Purpose

Timely will evolve from a timetable-focused app into a college academic operations SaaS. The platform should replace disconnected attendance, timetable, classroom-material, workload-allocation, messaging, exam, and marks-entry workflows with one role-based system.

The product must stay practical for real colleges: reliable under daily attendance load, clear for non-technical faculty, auditable for academic administrators, and phased so useful modules ship before the entire ERP-sized surface is complete.

## Current Baseline

The existing app already includes:

- Authentication and institution setup.
- Teacher, room, class, subject, lesson, timetable, holiday, absence, and substitution models.
- OR-Tools timetable solving.
- Timetable publishing and manual assignment movement.
- A React admin UI and FastAPI backend.

The current data model is school-style and timetable-centric. The college SaaS needs richer academic structure, student rosters, workload allocation, attendance records, materials, messaging, assessments, marks, reports, and auditability.

## Product Roles

- Super Admin: platform-wide institution, user, master data, timetable, roster, report, and audit access.
- HOD or Coordinator: department-scoped admin access, allocation review, leave-driven timetable changes, and reports.
- Faculty: preference submission, workload/timetable view, attendance, materials, messaging, quizzes, exams, and marks for assigned classes.
- Student: own timetable, attendance, materials, messages, quiz/exam attempts, and published marks.

Role enforcement must happen on the backend. The frontend may hide unavailable actions, but API authorization is the source of truth.

## Phased Delivery

### Phase 1: College Foundation and Daily Operations

Phase 1 turns the existing timetable app into a usable college operating core.

Build:

- Department, program, semester, division, batch, and student roster data.
- Faculty master fields needed by colleges: code, department, designation, max weekly load, min weekly load, and employment status.
- Subject master fields: code, department, semester, credits, theory hours, practical hours, tutorial hours, and double-period eligibility.
- Workload allocation: assign faculty to subject/class/division/batch units and calculate weekly load against the configured band.
- Timetable upgrades: divisions, batch-split labs, recess blocks, alternate-week slots, online/industry sessions, and versioned publish/lock.
- Attendance from timetable slots with present/absent/late and mark-all-present with exceptions.
- Basic reports: faculty load, roster completeness, timetable clashes, and attendance shortage.
- Audit log for timetable, allocation, attendance, and roster changes.

Phase 1 deliberately excludes full messaging, materials, exams, and gradebook so the system can ship a strong operational foundation first.

### Phase 2: Communication

Build announcements, file/material links, acknowledgements, and scoped 1:1 faculty-student messaging. Messaging eligibility is derived from active timetable/allocation relationships so students cannot message unrelated faculty.

### Phase 3: Gradebook

Build configurable mark heads, marks entry by assigned faculty, publish controls, student marks view, audit history, and export formats for exam-cell submission.

### Phase 4: Online Quizzes and Exams

Build quiz/exam authoring, question banks, timed attempts, objective auto-grading, subjective grading queues, and optional gradebook sync.

### Phase 5: SaaS Hardening

Build multi-tenant admin operations, institution settings, billing-ready tenant boundaries if needed later, backup/export tooling, notification delivery, monitoring, and production deployment posture.

## Phase 1 Architecture

### Backend

FastAPI remains the backend framework. SQLAlchemy models will be extended rather than replaced, with migrations generated through the existing migration pattern.

Core additions:

- Department: institution-scoped academic unit.
- Program: degree/school grouping such as B.Tech CE or SOCET/ASOIT.
- AcademicTerm: year, term name, active flag, start/end dates.
- Division: replaces the school-only class concept for college use while preserving existing Class compatibility.
- Batch: subdivision of a division for lab/practical/tutorial scheduling.
- Student: roster identity and enrollment state.
- StudentEnrollment: student to term/division/batch mapping.
- Allocation: faculty to subject/division/batch with weekly theory/practical/tutorial hours.
- TimetableVersion: version metadata, status, publish lock, and active flag.
- TimetableSlot: normalized scheduled slot used by attendance and later modules.
- RecessBlock: institution or term scoped blocked periods.
- AttendanceSession and AttendanceRecord.
- AuditLog.

Existing Timetable and Assignment tables can continue as compatibility surfaces while TimetableSlot becomes the central operational table for new modules. Solver output should be persisted into both Assignment and TimetableSlot during the transition.

### Frontend

React stays. The navigation should grow into college modules without becoming cluttered:

- Dashboard
- Master Data
- Workload
- Timetable
- Attendance
- Reports
- Settings

Phase 1 pages:

- College Setup: departments, programs, terms, divisions, and batches.
- Students: roster import, validation, and enrollment view.
- Workload: allocation matrix with load counters and under/over warnings.
- Timetable: upgraded grid with division/batch filters, recess, alternate-week labels, and publish history.
- Attendance: faculty daily marking flow and admin review.
- Reports: load, shortage, roster completeness, and audit log.

The UI should be dense, calm, and operational, not a marketing layout. It should work well on mobile for attendance marking.

## Timetable Solver Requirements

Hard rules:

- No teacher, room, division, or batch clash in the same slot.
- No teacher scheduled during unavailable slots.
- No room capacity/type mismatch.
- Recess blocks cannot contain classes.
- Library periods must be first or last period of the day.
- Non-double subjects cannot be scheduled in consecutive periods for the same division.
- Teachers must receive breaks through a maximum consecutive teaching-period rule.
- Batch-split lab slots may run in parallel only when each batch has a different compatible room and teacher.

Soft rules:

- Spread repeated subjects across the week.
- Prefer theory earlier in the day where configured.
- Minimize teacher idle gaps without removing necessary breaks.
- Balance faculty daily load.
- Prefer labs in contiguous double periods when the subject allows it.

## Data Flow

1. Admin configures term, departments, programs, divisions, batches, subjects, rooms, faculty, and students.
2. Admin imports or edits student rosters.
3. Faculty preferences may be collected, then Admin creates allocations.
4. Solver builds timetable input from allocations, rooms, availability, recess blocks, and subject rules.
5. Solver writes a TimetableVersion with Assignments and TimetableSlots.
6. Admin publishes the version, locking it for daily operations.
7. Faculty marks attendance from the active TimetableSlots.
8. Reports read from allocations, slots, attendance, and audit logs.

## Permissions

Super Admin can manage all institution data.

HOD/Coordinator can manage department-scoped faculty, subjects, allocations, timetable views, attendance reports, and approvals.

Faculty can only act on assigned allocations, timetable slots, attendance sessions, materials, assessments, and mark heads for their teaching relationships.

Students can only read their own timetable, attendance, materials, messages, attempts, and published marks.

## Error Handling and Validation

Imports must validate required columns, duplicate roll numbers, unknown division/batch references, and malformed emails before writing any rows.

Allocation saves must warn on missing faculty, missing subject hours, and load outside configured min/max limits.

Timetable generation must return structured infeasibility reasons where possible: no compatible room, pinned conflict, overload, recess conflict, or impossible consecutive-period rules.

Attendance must prevent duplicate sessions for the same timetable slot and date.

Published timetable and mark changes must require explicit edit actions and write audit logs.

## Testing Strategy

Backend:

- Unit tests for solver hard rules and allocation load calculation.
- API tests for role permissions, roster import validation, attendance marking, and publish locks.
- Integration tests from allocation to generated timetable slots to attendance sessions.

Frontend:

- Component tests for allocation counters, import validation states, and attendance marking.
- End-to-end smoke test for Admin setup -> allocation -> generate timetable -> publish -> faculty attendance.

Operational:

- Seed data for a realistic college department with divisions, batches, labs, faculty load limits, recess, and alternate-week slots.
- Migration tests for existing school-style data.

## Implementation Order

1. Add Phase 1 schema and migrations.
2. Add backend services and APIs for departments, programs, terms, divisions, batches, students, enrollments, allocations, timetable slots, attendance, reports, and audit logs.
3. Upgrade solver dataset building and persistence for allocations, batches, recess, alternate weeks, and TimetableSlot.
4. Add Phase 1 frontend routes and navigation.
5. Add roster import and workload allocation UI.
6. Add upgraded timetable grid and publish history.
7. Add attendance marking and reports.
8. Add seed/demo data and full verification.

## Deployment Direction

Use PostgreSQL for production. SQLite can remain for local development.

Target managed hosting in an India region when deployed for real colleges. File uploads in later phases should use object storage, not database blobs.

Daily backups, audit logs, and tenant-scoped access checks are required before production rollout.

## Open Decisions

The implementation will assume one institution instance can contain multiple departments/schools such as SOCET and ASOIT, filtered by department/program. This matches the current single-workbook operating model.

The implementation will assume separate email/password login for v1. SSO can be added later without blocking Phase 1.

The implementation will make timetable rules configurable in data where practical, but solver-level hard constraints will remain coded and tested for safety.

Exact university marksheet and attendance export templates will be added when the required format is available.
