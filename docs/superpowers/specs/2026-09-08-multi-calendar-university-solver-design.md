# Multi-Calendar University Timetable Solver Design

**Date:** 2026-09-08

## Goal

Generate a complete, clash-free university timetable from master data and
weekly requirements even when departments use different teaching calendars.
The generator must protect shared faculty, rooms, labs, student divisions,
faculty shifts, fixed lab durations, and student workload rules.

## Scheduling Model

### Department Calendars

Each department owns a calendar with Monday-Friday teaching days, exact
period start/end times, and breaks. A period is not globally identified by
its ordinal (for example, `P3`); it has a real local time range. A department
may schedule activities only in its own non-break periods.

### Global Resource Conflicts

Faculty, classrooms, and laboratories can be shared across departments. Two
activities conflict when their half-open time ranges overlap on the same day:
`start_a < end_b and start_b < end_a`. This allows different local calendars
without allowing a faculty member or room to be double-booked.

Divisions conflict only with their own activities, since a division belongs to
one department calendar.

### Activity Requirements

The input is a curriculum allocation, not manually duplicated lesson rows:

`department, program, semester, division, subject, activity_type,
hours_per_week, faculty_pool, required_room_type, duration_minutes`.

The expansion service creates atomic activities before solving:

- Lecture requirements become the requested number of valid single-period
  activities.
- Lab requirements become fixed-duration, contiguous activity blocks. A lab
  cannot cross a break, a department-calendar gap, or an unavailable resource
  window.
- Each activity has one division, one subject, a qualified faculty pool, and
  room/lab requirements.

## Hard Constraints

Every generated and manually changed timetable must satisfy all of these:

1. Monday-Friday only unless the department calendar explicitly adds days.
2. An activity lies wholly in one department's valid teaching periods.
3. Shared faculty, classroom, and laboratory time ranges do not overlap.
4. A division has at most one activity at any time.
5. Assigned faculty is qualified for the subject/activity type.
6. Faculty shift is enforced as an availability window: Shift 1 is
   08:00-15:00 and Shift 2 is 09:30-16:30 by default; institutions can replace
   these windows.
7. Room type and capacity meet the activity requirement.
8. A fixed-duration lab occupies consecutive compatible time without a break.
9. A division has no more than two lab activities per day.
10. Required weekly lecture/lab duration for every allocation is fully met.
11. Faculty daily and weekly workload limits are not exceeded.
12. Existing pinned activities remain at their specified real-time slot.

## Optimization Objectives

After hard feasibility, CP-SAT minimizes weighted penalties in this order:

1. Faculty idle gaps, excluding declared breaks.
2. More than three consecutive faculty teaching periods.
3. Four consecutive theory activities for a division.
4. More than one occurrence of the same subject in one division-day, unless
   it is explicitly configured as a double period.
5. Uneven weekly subject distribution; the model spreads occurrences across
   Monday-Friday.
6. Faculty preferred or avoided time windows.
7. Student idle gaps where the department policy requires a compact day.

The score report returns the weighted total, count, and concrete examples for
each objective. Hard violations are never converted into penalties.

## Preflight

Before queueing a solver job, the system validates master data and reports
actionable errors without creating a failed timetable:

- missing department calendar or invalid/non-monotonic periods;
- activity requirements with no qualified faculty or compatible room/lab;
- faculty shift or availability leaves no valid activity window;
- required duration cannot fit contiguously in the department calendar;
- weekly faculty demand exceeds a faculty pool's weekly capacity;
- laboratory demand exceeds available compatible lab time;
- a division's requested weekly duration exceeds its available teaching time;
- more than two required lab blocks force the same division-day under the
  available calendar.

Preflight returns a machine-readable issue code, affected entities, demand,
capacity, and a human explanation for the UI and AI agent.

## Solve Pipeline

1. Save master data and curriculum allocations.
2. Expand allocations into activities and validate the expansion.
3. Run preflight and stop with an actionable report if infeasible.
4. Build a global CP-SAT model over department-specific candidate time ranges.
5. Solve hard feasibility first, then optimize using the feasible schedule as
   a warm start.
6. Persist the solution only when every activity is assigned and final
   validation reports zero hard violations.
7. Return a quality report plus division, faculty, classroom, and laboratory
   views.

## AI Boundary

The AI may collect requirements in natural language, explain preflight
failures, and propose typed changes. It cannot invent activities, bypass
preflight, select a conflicting resource, or publish a timetable. All AI
proposals use the same expansion, validation, and solver interfaces.

## Data and Migration Direction

Add department, department calendar, calendar period, faculty shift, and
curriculum allocation models. Store real times as local `time` values plus a
department calendar timezone. Store activities with a duration and assigned
real-time range; retain legacy lesson rows only as migration/import input.

## Testing

Use a two-department fixture with overlapping local calendars, shared faculty,
shared rooms, different breaks, and fixed lab durations. Cover cross-department
overlap, shift boundaries, lab contiguity, max-two-labs-per-day, full weekly
requirement expansion, preflight failures, and final report correctness.
