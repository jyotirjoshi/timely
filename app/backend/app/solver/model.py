"""
Timely Solver Engine — Google OR-Tools CP-SAT implementation.

This is the technical core of the product. It takes a problem dataset
(teachers, rooms, classes, subjects, lessons-to-schedule, constraints)
and produces a conflict-free timetable that optimizes soft constraints.

Design notes
------------
* The unit of work is a *lesson*: one occurrence of
  (class, subject, teacher, room-type) that must be placed into exactly
  one timeslot and one compatible room.
* Hard constraints must hold for the solution to be feasible.
* Soft constraints are linear penalty terms; the solver minimizes the
  weighted sum, and we return a human-readable score breakdown so the UI
  (and the AI agent) can explain *why* a timetable looks the way it does.
* Two-phase strategy for robustness on constrained hardware:
    Phase 1 — hard constraints only: fast, proves feasibility and gives
              us a guaranteed-valid fallback timetable.
    Phase 2 — full model with soft penalties, warm-started with the
              Phase 1 solution as a hint, time-boxed. If it finds
              nothing better we still return the Phase 1 timetable.
* `pinned` assignments enable incremental re-solve: after a manual edit,
  pin everything unchanged and re-solve only the affected lessons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model


# ---------------------------------------------------------------------------
# Result object
# ---------------------------------------------------------------------------

@dataclass
class SolveResult:
    status: str                       # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    assignments: list[dict[str, Any]] = field(default_factory=list)
    soft_score: int = 0
    violations: list[dict[str, Any]] = field(default_factory=list)
    solve_time_s: float = 0.0


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------

class _Model:
    """Builds the CP-SAT model; shared by the hard-only and full phases."""

    def __init__(self, dataset: dict[str, Any], include_soft: bool):
        self.ds = dataset
        self.n_days = len(dataset["days"])
        self.periods = dataset["periods_per_day"]
        self.slots = [(d, p) for d in range(self.n_days) for p in range(self.periods)]
        self.teachers = {t["id"]: t for t in dataset["teachers"]}
        self.classes = {c["id"]: c for c in dataset["classes"]}
        self.subjects = {s["id"]: s for s in dataset["subjects"]}
        self.lessons = dataset["lessons"]
        self.soft = dataset.get("soft_constraints", {}) if include_soft else {}

        self.model = cp_model.CpModel()
        self.x: dict[tuple[str, int, int], cp_model.IntVar] = {}
        self.room_var: dict[str, cp_model.IntVar] = {}
        self.has_room: dict[tuple[str, int], cp_model.IntVar] = {}
        self.penalties: list[tuple[cp_model.IntVar, int, str, dict]] = []
        self.compat = {l["id"]: self._compatible_rooms(l) for l in self.lessons}

    # -- rooms ----------------------------------------------------------
    def _compatible_rooms(self, lesson: dict) -> list[str]:
        need_type = self.subjects[lesson["subject_id"]].get("room_type", "classroom")
        class_size = self.classes[lesson["class_id"]].get("size", 0)
        return [
            r["id"] for r in self.ds["rooms"]
            if r.get("type", "classroom") == need_type and r.get("capacity", 0) >= class_size
        ]

    # -- build ----------------------------------------------------------
    def build(self) -> str | None:
        """Returns an infeasibility reason string, or None if built OK."""
        for lesson in self.lessons:
            if not self.compat[lesson["id"]]:
                return f"no_compatible_room:{lesson['id']}"

        m = self.model
        for l in self.lessons:
            lid = l["id"]
            for d, p in self.slots:
                self.x[(lid, d, p)] = m.new_bool_var(f"x_{lid}_{d}_{p}")
            self.room_var[lid] = m.new_int_var(0, len(self.compat[lid]) - 1, f"room_{lid}")
            for ridx in range(len(self.compat[lid])):
                b = m.new_bool_var(f"hr_{lid}_{ridx}")
                self.has_room[(lid, ridx)] = b
                m.add(self.room_var[lid] == ridx).only_enforce_if(b)
                m.add(self.room_var[lid] != ridx).only_enforce_if(b.negated())
            m.add_exactly_one(self.has_room[(lid, ridx)]
                              for ridx in range(len(self.compat[lid])))

        self._hard_constraints()
        self._soft_constraints()
        if self.penalties:
            m.minimize(sum(var * w for var, w, _, _ in self.penalties))
        return None

    # -- hard -----------------------------------------------------------
    def _hard_constraints(self):
        m = self.model
        for lesson in self.lessons:
            lid = lesson["id"]
            m.add_exactly_one(self.x[(lid, d, p)] for d, p in self.slots)
            pin = lesson.get("pinned")
            if pin:
                m.add(self.x[(lid, pin["day"], pin["period"])] == 1)
                if pin.get("room_id") in self.compat[lid]:
                    m.add(self.room_var[lid] == self.compat[lid].index(pin["room_id"]))
            for d, p in self.teachers[lesson["teacher_id"]].get("unavailable", []):
                m.add(self.x[(lid, d, p)] == 0)

        for d, p in self.slots:
            by_teacher: dict[str, list] = {}
            by_class: dict[str, list] = {}
            for lesson in self.lessons:
                lid = lesson["id"]
                by_teacher.setdefault(lesson["teacher_id"], []).append(self.x[(lid, d, p)])
                by_class.setdefault(lesson["class_id"], []).append(self.x[(lid, d, p)])
            for vars_ in by_teacher.values():
                m.add_at_most_one(vars_)
            for vars_ in by_class.values():
                m.add_at_most_one(vars_)

        # room uniqueness via z = placed-in-slot AND uses-this-room
        for room in self.ds["rooms"]:
            rid = room["id"]
            candidates = [l for l in self.lessons if rid in self.compat[l["id"]]]
            if not candidates:
                continue
            for d, p in self.slots:
                users = []
                for lesson in candidates:
                    lid = lesson["id"]
                    ridx = self.compat[lid].index(rid)
                    z = m.new_bool_var(f"z_{rid}_{lid}_{d}_{p}")
                    m.add_bool_and([self.x[(lid, d, p)],
                                    self.has_room[(lid, ridx)]]).only_enforce_if(z)
                    m.add_bool_or([self.x[(lid, d, p)].negated(),
                                   self.has_room[(lid, ridx)].negated()]
                                  ).only_enforce_if(z.negated())
                    users.append(z)
                m.add_at_most_one(users)

        for tid, teacher in self.teachers.items():
            if teacher.get("max_per_day"):
                t_lessons = [l for l in self.lessons if l["teacher_id"] == tid]
                for d in range(self.n_days):
                    m.add(sum(self.x[(l["id"], d, p)] for l in t_lessons
                              for p in range(self.periods)) <= teacher["max_per_day"])

    # -- soft -----------------------------------------------------------
    def _soft_constraints(self):
        m = self.model
        days, periods = self.n_days, self.periods

        cfg = self.soft.get("teacher_max_consecutive")
        if cfg and cfg.get("weight", 0) > 0:
            max_cons, w = cfg.get("max", 3), cfg["weight"]
            for tid in self.teachers:
                t_lessons = [l for l in self.lessons if l["teacher_id"] == tid]
                for d in range(days):
                    for p0 in range(periods - max_cons):
                        window = [self.x[(l["id"], d, p0 + k)]
                                  for l in t_lessons for k in range(max_cons + 1)]
                        over = m.new_int_var(0, len(window), f"cons_{tid}_{d}_{p0}")
                        m.add(over >= sum(window) - max_cons)
                        self.penalties.append((over, w, "teacher_max_consecutive",
                                               {"teacher_id": tid, "day": d}))

        cfg = self.soft.get("subject_spread")
        if cfg and cfg.get("weight", 0) > 0:
            w = cfg["weight"]
            for cls_id in self.classes:
                by_subject: dict[str, list] = {}
                for l in [l for l in self.lessons if l["class_id"] == cls_id]:
                    by_subject.setdefault(l["subject_id"], []).append(l)
                for sid, ls in by_subject.items():
                    if len(ls) < 2:
                        continue
                    for d in range(days):
                        same_day = sum(self.x[(l["id"], d, p)] for l in ls
                                       for p in range(periods))
                        over = m.new_int_var(0, len(ls), f"spread_{cls_id}_{sid}_{d}")
                        m.add(over >= same_day - 1)
                        self.penalties.append((over, w, "subject_spread",
                                               {"class_id": cls_id, "subject_id": sid, "day": d}))

        cfg = self.soft.get("subject_preferred_slots")
        if cfg and cfg.get("weight", 0) > 0:
            w = cfg["weight"]
            for rule in cfg.get("rules", []):
                allowed = set(rule.get("allowed_periods", range(periods)))
                for l in [l for l in self.lessons if l["subject_id"] == rule["subject_id"]]:
                    for d in range(days):
                        for p in range(periods):
                            if p not in allowed:
                                self.penalties.append((self.x[(l["id"], d, p)], w,
                                                       "subject_preferred_slots",
                                                       {"lesson_id": l["id"], "day": d, "period": p}))

        cfg = self.soft.get("minimize_teacher_gaps")
        if cfg and cfg.get("weight", 0) > 0:
            w = cfg["weight"]
            for tid in self.teachers:
                t_lessons = [l for l in self.lessons if l["teacher_id"] == tid]
                if not t_lessons:
                    continue
                for d in range(days):
                    busy = []
                    for p in range(periods):
                        b = m.new_bool_var(f"busy_{tid}_{d}_{p}")
                        m.add_max_equality(b, [self.x[(l["id"], d, p)] for l in t_lessons])
                        busy.append(b)
                    first = m.new_int_var(0, periods - 1, f"first_{tid}_{d}")
                    last = m.new_int_var(0, periods - 1, f"last_{tid}_{d}")
                    for p in range(periods):
                        m.add(first <= p + periods * (1 - busy[p]))
                        m.add(last >= p - periods * (1 - busy[p]))
                    taught = m.new_int_var(0, periods, f"taught_{tid}_{d}")
                    m.add(taught == sum(busy))
                    teaches_today = m.new_bool_var(f"tt_{tid}_{d}")
                    m.add(taught >= 1).only_enforce_if(teaches_today)
                    m.add(taught == 0).only_enforce_if(teaches_today.negated())
                    gap = m.new_int_var(0, periods, f"gap_{tid}_{d}")
                    m.add(gap >= last - first + 1 - taught)
                    gap_eff = m.new_int_var(0, periods, f"gape_{tid}_{d}")
                    m.add_multiplication_equality(gap_eff, [gap, teaches_today])
                    self.penalties.append((gap_eff, w, "minimize_teacher_gaps",
                                           {"teacher_id": tid, "day": d}))

    # -- hint ------------------------------------------------------------
    def add_hint(self, assignments: list[dict[str, Any]]):
        """Warm-start from a previous (hard-feasible) solution."""
        placed = {a["lesson_id"]: a for a in assignments}
        for l in self.lessons:
            lid = l["id"]
            a = placed.get(lid)
            for d, p in self.slots:
                self.model.add_hint(self.x[(lid, d, p)],
                                    1 if (a and a["day"] == d and a["period"] == p) else 0)
            if a and a["room_id"] in self.compat[lid]:
                ridx = self.compat[lid].index(a["room_id"])
                self.model.add_hint(self.room_var[lid], ridx)
                for i in range(len(self.compat[lid])):
                    self.model.add_hint(self.has_room[(lid, i)], 1 if i == ridx else 0)

    # -- extraction ------------------------------------------------------
    def extract(self, solver: cp_model.CpSolver, status: Any) -> SolveResult:
        # NOTE: ortools>=9.15 requires the status enum to be passed explicitly.
        name = solver.status_name(status)
        result = SolveResult(status=name, solve_time_s=round(solver.wall_time, 3))
        for lesson in self.lessons:
            lid = lesson["id"]
            for d, p in self.slots:
                if solver.value(self.x[(lid, d, p)]) == 1:
                    result.assignments.append({
                        "lesson_id": lid,
                        "class_id": lesson["class_id"],
                        "subject_id": lesson["subject_id"],
                        "teacher_id": lesson["teacher_id"],
                        "room_id": self.compat[lid][solver.value(self.room_var[lid])],
                        "day": d,
                        "period": p,
                    })
                    break
        agg: dict[str, dict] = {}
        for var, w, label, ctx in self.penalties:
            v = solver.value(var)
            if v > 0:
                bucket = agg.setdefault(label, {"count": 0, "weighted": 0, "examples": []})
                bucket["count"] += v
                bucket["weighted"] += v * w
                if len(bucket["examples"]) < 5:
                    bucket["examples"].append({**ctx, "amount": v})
                result.soft_score += v * w
        result.violations = [{"type": label, **data}
                             for label, data in sorted(agg.items(),
                                                       key=lambda kv: -kv[1]["weighted"])]
        return result


# ---------------------------------------------------------------------------
# Public entry point — two-phase solve
# ---------------------------------------------------------------------------

def _new_solver(time_limit_s: float, seed: int, num_workers: int = 8) -> cp_model.CpSolver:
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(time_limit_s)
    s.parameters.random_seed = seed
    s.parameters.num_workers = num_workers
    return s


def solve_timetable(dataset: dict[str, Any], time_limit_s: int = 300, seed: int = 42,
                    num_workers: int = 1) -> SolveResult:
    """
    Solve a timetabling problem. See module docstring for the dataset shape.

    Phase 1 proves feasibility fast; Phase 2 optimizes soft constraints
    warm-started from the Phase 1 solution. If Phase 2 finds nothing, the
    Phase 1 timetable is returned as a guaranteed-valid fallback.

    num_workers: CP-SAT parallel workers (default 1 for safety on all platforms;
                 set to 4-8 in production for faster results).
    """
    has_soft = any(c.get("weight", 0) > 0
                   for c in dataset.get("soft_constraints", {}).values())

    # ---------- Phase 1: hard constraints only ----------
    # Give Phase 1 at least 30s or half the budget, whichever is more generous
    hard_budget = min(max(30, time_limit_s // 2), time_limit_s) if has_soft else time_limit_s
    hard = _Model(dataset, include_soft=False)
    reason = hard.build()
    if reason:
        kind, lid = reason.split(":", 1)
        return SolveResult(status="INFEASIBLE", violations=[{
            "type": kind, "lesson_id": lid,
            "detail": "No room of the required type with enough capacity."}])
    s1 = _new_solver(hard_budget, seed, num_workers)
    st1 = s1.solve(hard.model)
    if st1 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(status=s1.status_name(st1), solve_time_s=round(s1.wall_time, 3))

    fallback = hard.extract(s1, st1)
    if not has_soft:
        return fallback

    # ---------- Phase 2: optimize soft constraints, warm-started ----------
    full = _Model(dataset, include_soft=True)
    full.build()
    full.add_hint(fallback.assignments)
    s2 = _new_solver(max(1, time_limit_s - hard_budget), seed, num_workers)
    s2.parameters.repair_hint = True
    st2 = s2.solve(full.model)
    if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result = full.extract(s2, st2)
        result.solve_time_s = round(s1.wall_time + s2.wall_time, 3)
        return result

    fallback.solve_time_s = round(s1.wall_time + s2.wall_time, 3)
    return fallback
