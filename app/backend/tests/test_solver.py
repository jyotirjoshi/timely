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


def _single_class_dataset(subject: dict | None = None) -> dict:
    subject = subject or {
        "id": "math",
        "name": "Mathematics",
        "room_type": "classroom",
        "allow_double": False,
    }
    return {
        "days": ["Mon"],
        "periods_per_day": 4,
        "teachers": [{"id": "t1", "name": "Teacher 1", "max_per_day": 4, "unavailable": []}],
        "rooms": [{"id": "r1", "name": "Room 1", "type": "classroom", "capacity": 30}],
        "classes": [{"id": "c1", "name": "Class 1", "size": 20}],
        "subjects": [subject],
        "lessons": [
            {
                "id": "l1",
                "class_id": "c1",
                "subject_id": subject["id"],
                "teacher_id": "t1",
                "pinned": None,
            },
            {
                "id": "l2",
                "class_id": "c1",
                "subject_id": subject["id"],
                "teacher_id": "t1",
                "pinned": None,
            },
        ],
        "soft_constraints": {},
    }


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


def test_non_double_subject_cannot_be_consecutive_for_same_class():
    # Catches removing the hard guard against same-subject back-to-back periods.
    ds = _single_class_dataset()
    ds["lessons"][0]["pinned"] = {"day": 0, "period": 1, "room_id": None}
    ds["lessons"][1]["pinned"] = {"day": 0, "period": 2, "room_id": None}

    res = solve_timetable(ds, time_limit_s=5)

    assert res.status == "INFEASIBLE"


def test_subjects_that_allow_double_can_be_consecutive_for_same_class():
    ds = _single_class_dataset({
        "id": "lab",
        "name": "Physics Lab",
        "room_type": "classroom",
        "allow_double": True,
    })
    ds["lessons"][0]["pinned"] = {"day": 0, "period": 1, "room_id": None}
    ds["lessons"][1]["pinned"] = {"day": 0, "period": 2, "room_id": None}

    res = solve_timetable(ds, time_limit_s=5)

    assert res.status in ("OPTIMAL", "FEASIBLE")


def test_library_period_cannot_be_scheduled_in_middle_of_day():
    # Catches removing the hard first-or-last-period rule for Library subjects.
    ds = _single_class_dataset({
        "id": "library",
        "name": "Library",
        "room_type": "classroom",
        "allow_double": False,
    })
    ds["lessons"] = ds["lessons"][:1]
    ds["lessons"][0]["pinned"] = {"day": 0, "period": 1, "room_id": None}

    res = solve_timetable(ds, time_limit_s=5)

    assert res.status == "INFEASIBLE"


def test_teacher_cannot_have_more_than_three_consecutive_periods():
    # Catches turning teacher breaks back into an optional soft preference.
    ds = {
        "days": ["Mon"],
        "periods_per_day": 5,
        "teachers": [{"id": "t1", "name": "Teacher 1", "max_per_day": 5, "unavailable": []}],
        "rooms": [
            {"id": f"r{i}", "name": f"Room {i}", "type": "classroom", "capacity": 30}
            for i in range(4)
        ],
        "classes": [
            {"id": f"c{i}", "name": f"Class {i}", "size": 20}
            for i in range(4)
        ],
        "subjects": [{
            "id": "math",
            "name": "Mathematics",
            "room_type": "classroom",
            "allow_double": False,
        }],
        "lessons": [
            {
                "id": f"l{i}",
                "class_id": f"c{i}",
                "subject_id": "math",
                "teacher_id": "t1",
                "pinned": {"day": 0, "period": i, "room_id": None},
            }
            for i in range(4)
        ],
        "soft_constraints": {"teacher_max_consecutive": {"weight": 5, "max": 3}},
    }

    res = solve_timetable(ds, time_limit_s=5)

    assert res.status == "INFEASIBLE"
