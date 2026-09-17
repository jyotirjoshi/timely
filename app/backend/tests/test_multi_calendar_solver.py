from app.solver import solve_timetable


def candidate(day, start, end, teacher, room):
    return {
        "day": day, "start_minute": start, "end_minute": end,
        "teacher_id": teacher, "room_id": room, "preference_rank": 1,
    }


def activity(activity_id, division, subject, candidates, kind="theory", batch=None, parallel_group=None):
    return {
        "id": activity_id, "division_id": division, "batch_id": batch,
        "subject_id": subject, "kind": kind, "parallel_group": parallel_group,
        "duration_minutes": candidates[0]["end_minute"] - candidates[0]["start_minute"],
        "candidates": candidates,
    }


def test_shared_faculty_and_room_never_overlap_across_department_calendars():
    dataset = {"format": "multi_calendar", "activities": [
        activity("cse", "cse-a", "algo", [
            candidate(0, 540, 600, "shared", "r1"),
            candidate(0, 600, 660, "shared", "r1"),
        ]),
        activity("ece", "ece-a", "circuits", [
            candidate(0, 570, 630, "shared", "r1"),
            candidate(0, 660, 720, "shared", "r1"),
        ]),
    ]}

    result = solve_timetable(dataset, time_limit_s=5, seed=7)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    first, second = sorted(result.assignments, key=lambda item: item["start_minute"])
    assert first["end_minute"] <= second["start_minute"]


def test_fixed_lab_duration_complete_requirements_and_daily_lab_limit():
    activities = []
    for index in range(3):
        activities.append(activity(
            f"lab-{index}", "division", "programming", [
                candidate(0, 540 + index * 120, 660 + index * 120, f"t{index}", f"lab{index}"),
                candidate(1, 540 + index * 120, 660 + index * 120, f"t{index}", f"lab{index}"),
            ], kind="practical",
        ))

    result = solve_timetable({"format": "multi_calendar", "activities": activities}, time_limit_s=5)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert len(result.assignments) == 3
    assert all(item["end_minute"] - item["start_minute"] == 120 for item in result.assignments)
    per_day = {}
    for item in result.assignments:
        per_day[item["day"]] = per_day.get(item["day"], 0) + 1
    assert max(per_day.values()) <= 2


def test_parallel_batches_may_overlap_but_regular_division_classes_may_not():
    simultaneous = candidate(0, 540, 660, "teacher-a", "lab-a")
    dataset = {"format": "multi_calendar", "activities": [
        activity("batch-a", "division", "lab", [simultaneous], "practical", "a", "lab-pair"),
        activity("batch-b", "division", "lab", [candidate(0, 540, 660, "teacher-b", "lab-b")], "practical", "b", "lab-pair"),
    ]}
    result = solve_timetable(dataset, time_limit_s=5)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert {item["start_minute"] for item in result.assignments} == {540}

    dataset["activities"].append(activity(
        "whole-division", "division", "math", [candidate(0, 540, 600, "teacher-c", "r1")]
    ))
    assert solve_timetable(dataset, time_limit_s=5).status == "INFEASIBLE"


def test_same_subject_theory_is_not_scheduled_back_to_back():
    dataset = {"format": "multi_calendar", "activities": [
        activity("a1", "division", "math", [candidate(0, 540, 600, "t1", "r1")]),
        activity("a2", "division", "math", [
            candidate(0, 600, 660, "t2", "r2"),
            candidate(0, 660, 720, "t2", "r2"),
        ]),
    ]}
    result = solve_timetable(dataset, time_limit_s=5)
    second = next(item for item in result.assignments if item["activity_id"] == "a2")
    assert second["start_minute"] == 660


def test_seeded_multi_calendar_results_are_deterministic():
    dataset = {"format": "multi_calendar", "activities": [
        activity("a1", "d1", "s1", [
            candidate(0, 540, 600, "t1", "r1"), candidate(1, 540, 600, "t1", "r1")
        ]),
        activity("a2", "d2", "s2", [
            candidate(0, 540, 600, "t2", "r2"), candidate(1, 540, 600, "t2", "r2")
        ]),
    ]}
    first = solve_timetable(dataset, time_limit_s=5, seed=42, num_workers=1)
    second = solve_timetable(dataset, time_limit_s=5, seed=42, num_workers=1)
    assert first.assignments == second.assignments


def test_odd_and_even_week_activities_may_share_resources():
    odd = activity("odd", "division", "seminar", [candidate(0, 540, 600, "t1", "r1")])
    even = activity("even", "division", "seminar-2", [candidate(0, 540, 600, "t1", "r1")])
    odd["alternate_week_pattern"] = "odd"
    even["alternate_week_pattern"] = "even"
    result = solve_timetable({"format": "multi_calendar", "activities": [odd, even]}, time_limit_s=5)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert {item["start_minute"] for item in result.assignments} == {540}


def test_faculty_receive_a_break_after_three_consecutive_activities():
    activities = []
    for index in range(4):
        candidates = [candidate(0, 540 + index * 60, 600 + index * 60, "shared", f"r{index}")]
        if index == 3:
            candidates.append(candidate(0, 840, 900, "shared", f"r{index}"))
        activities.append(activity(f"a{index}", f"d{index}", f"s{index}", candidates))
    result = solve_timetable({
        "format": "multi_calendar",
        "activities": activities,
        "teacher_max_consecutive": 3,
    }, time_limit_s=5)
    fourth = next(item for item in result.assignments if item["activity_id"] == "a3")
    assert fourth["start_minute"] == 840
