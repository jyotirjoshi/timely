"""
Solver engine tests — run with:  python -m pytest backend/tests -q

These prove the engine's guarantees end-to-end on the sample dataset:
  1. it finds a feasible timetable,
  2. zero teacher clashes, zero class clashes, zero room clashes,
  3. teacher unavailability is respected,
  4. pinned lessons stay put,
  5. a deliberately impossible dataset reports INFEASIBLE.
"""

from collections import Counter

import pytest

from app.solver import solve_timetable
from app.solver.sample_data import build_sample_dataset


@pytest.fixture(scope="module")
def solved():
    """Solve the sample dataset once and share the result across tests."""
    ds = build_sample_dataset()
    return ds, solve_timetable(ds, time_limit_s=120)


def test_finds_feasible_solution(solved):
    ds, res = solved
    assert res.status in ("OPTIMAL", "FEASIBLE"), f"solver failed: {res.status}"
    assert len(res.assignments) == len(ds["lessons"])


def test_no_teacher_or_class_or_room_clashes(solved):
    ds, res = solved
    assert res.status in ("OPTIMAL", "FEASIBLE")
    teacher_slots = Counter((a["teacher_id"], a["day"], a["period"]) for a in res.assignments)
    class_slots = Counter((a["class_id"], a["day"], a["period"]) for a in res.assignments)
    room_slots = Counter((a["room_id"], a["day"], a["period"]) for a in res.assignments)
    assert all(v == 1 for v in teacher_slots.values()), "teacher double-booked"
    assert all(v == 1 for v in class_slots.values()), "class double-booked"
    assert all(v == 1 for v in room_slots.values()), "room double-booked"


def test_teacher_unavailability_respected(solved):
    ds, res = solved
    assert res.status in ("OPTIMAL", "FEASIBLE")
    unavail = {t["id"]: set(map(tuple, t.get("unavailable", []))) for t in ds["teachers"]}
    for a in res.assignments:
        assert (a["day"], a["period"]) not in unavail[a["teacher_id"]]


def test_pinned_lesson_stays_put():
    ds = build_sample_dataset()
    ds["lessons"][0]["pinned"] = {"day": 0, "period": 0, "room_id": None}
    res = solve_timetable(ds, time_limit_s=120)
    assert res.status in ("OPTIMAL", "FEASIBLE")
    pinned = next(a for a in res.assignments if a["lesson_id"] == ds["lessons"][0]["id"])
    assert (pinned["day"], pinned["period"]) == (0, 0)


def test_impossible_dataset_reports_infeasible():
    ds = build_sample_dataset()
    ds["lessons"][0]["pinned"] = {"day": 0, "period": 0, "room_id": None}
    ds["lessons"][1]["pinned"] = {"day": 0, "period": 0, "room_id": None}
    # both lessons belong to the same class -> same class, same slot => impossible
    ds["lessons"][1]["class_id"] = ds["lessons"][0]["class_id"]
    ds["lessons"][1]["teacher_id"] = ds["lessons"][0]["teacher_id"]
    res = solve_timetable(ds, time_limit_s=30)
    assert res.status == "INFEASIBLE"
