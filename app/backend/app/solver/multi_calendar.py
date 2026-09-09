"""CP-SAT solver for real-time, department-specific academic calendars."""
from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from app.solver.model import SolveResult


def _overlap(first: dict, second: dict) -> bool:
    return (
        first["day"] == second["day"]
        and first["start_minute"] < second["end_minute"]
        and second["start_minute"] < first["end_minute"]
    )


def _same_cohort_conflicts(first: dict, second: dict) -> bool:
    if first["division_id"] != second["division_id"]:
        return False
    first_batch = first.get("batch_id")
    second_batch = second.get("batch_id")
    same_parallel_group = (
        first_batch and second_batch and first_batch != second_batch
        and first.get("parallel_group")
        and first.get("parallel_group") == second.get("parallel_group")
    )
    return not same_parallel_group


def _weeks(activity: dict) -> tuple[int, ...]:
    pattern = activity.get("alternate_week_pattern", "every")
    if pattern == "odd":
        return (0,)
    if pattern == "even":
        return (1,)
    return (0, 1)


def solve_multi_calendar(
    dataset: dict,
    time_limit_s: int = 300,
    seed: int = 42,
    num_workers: int = 1,
) -> SolveResult:
    activities = sorted(dataset.get("activities", []), key=lambda value: value["id"])
    if any(not activity.get("candidates") for activity in activities):
        missing = [activity["id"] for activity in activities if not activity.get("candidates")]
        return SolveResult(
            status="INFEASIBLE",
            violations=[{"type": "no_candidate_window", "activity_ids": missing}],
        )

    model = cp_model.CpModel()
    choices: dict[tuple[int, int], cp_model.IntVar] = {}
    teacher_intervals: dict[tuple[str, int, int], list] = defaultdict(list)
    teacher_slot_choices: dict[tuple[str, int, int, int, int, int], list] = defaultdict(list)
    room_intervals: dict[tuple[str, int, int], list] = defaultdict(list)

    for activity_index, activity in enumerate(activities):
        activity_vars = []
        for candidate_index, candidate in enumerate(activity["candidates"]):
            choice = model.new_bool_var(f"a{activity_index}_c{candidate_index}")
            choices[(activity_index, candidate_index)] = choice
            activity_vars.append(choice)
            size = candidate["end_minute"] - candidate["start_minute"]
            for week in _weeks(activity):
                teacher_interval = model.new_optional_fixed_size_interval_var(
                    candidate["start_minute"], size, choice,
                    f"teacher_{activity_index}_{candidate_index}_w{week}",
                )
                room_interval = model.new_optional_fixed_size_interval_var(
                    candidate["start_minute"], size, choice,
                    f"room_{activity_index}_{candidate_index}_w{week}",
                )
                teacher_intervals[(candidate["teacher_id"], week, candidate["day"])].append(teacher_interval)
                teacher_slot_choices[(
                    candidate["teacher_id"],
                    week,
                    candidate["day"],
                    candidate["start_minute"],
                    candidate["end_minute"],
                    activity_index,
                )].append(choice)
                room_intervals[(candidate["room_id"], week, candidate["day"])].append(room_interval)
        model.add_exactly_one(activity_vars)

    for intervals in teacher_intervals.values():
        model.add_no_overlap(intervals)
    for intervals in room_intervals.values():
        model.add_no_overlap(intervals)

    teacher_occupancy: dict[tuple[str, int, int], list] = defaultdict(list)
    for slot, slot_choices in teacher_slot_choices.items():
        teacher_id, week, day, start_minute, end_minute, activity_index = slot
        occupied = model.new_bool_var(
            f"faculty_slot_{teacher_id}_{week}_{day}_{start_minute}_{activity_index}"
        )
        model.add(occupied == sum(slot_choices))
        teacher_occupancy[(teacher_id, week, day)].append(
            (start_minute, end_minute, activity_index, occupied)
        )

    max_consecutive = max(1, int(dataset.get("teacher_max_consecutive", 3)))
    for records in teacher_occupancy.values():
        by_start: dict[int, list] = defaultdict(list)
        for record in records:
            by_start[record[0]].append(record)

        prohibited_chains: set[tuple[str, ...]] = set()

        def add_chains(chain: list, used_activities: set[int]) -> None:
            if len(chain) == max_consecutive + 1:
                variables = tuple(record[3] for record in chain)
                signature = tuple(sorted(variable.name for variable in variables))
                if signature not in prohibited_chains:
                    prohibited_chains.add(signature)
                    model.add(sum(variables) <= max_consecutive)
                return
            for next_record in by_start.get(chain[-1][1], []):
                if next_record[2] not in used_activities:
                    add_chains(chain + [next_record], used_activities | {next_record[2]})

        for record in records:
            add_chains([record], {record[2]})

    for first_index, first in enumerate(activities):
        for second_index in range(first_index + 1, len(activities)):
            second = activities[second_index]
            weeks_intersect = bool(set(_weeks(first)) & set(_weeks(second)))
            cohort_conflict = weeks_intersect and _same_cohort_conflicts(first, second)
            consecutive_subject = (
                weeks_intersect
                and
                first["division_id"] == second["division_id"]
                and first.get("subject_id") == second.get("subject_id")
                and first.get("kind") != "practical"
                and second.get("kind") != "practical"
            )
            if not cohort_conflict and not consecutive_subject:
                continue
            for first_candidate_index, first_candidate in enumerate(first["candidates"]):
                for second_candidate_index, second_candidate in enumerate(second["candidates"]):
                    overlap = _overlap(first_candidate, second_candidate)
                    adjacent = (
                        first_candidate["day"] == second_candidate["day"]
                        and (
                            first_candidate["end_minute"] == second_candidate["start_minute"]
                            or second_candidate["end_minute"] == first_candidate["start_minute"]
                        )
                    )
                    if (cohort_conflict and overlap) or (consecutive_subject and adjacent):
                        model.add(
                            choices[(first_index, first_candidate_index)]
                            + choices[(second_index, second_candidate_index)] <= 1
                        )

    lab_by_division_day: dict[tuple[str, int, int], list] = defaultdict(list)
    for activity_index, activity in enumerate(activities):
        if activity.get("kind") != "practical" and activity.get("room_type") != "lab":
            continue
        for candidate_index, candidate in enumerate(activity["candidates"]):
            for week in _weeks(activity):
                lab_by_division_day[(activity["division_id"], week, candidate["day"])].append(
                    choices[(activity_index, candidate_index)]
                )
    for lab_choices in lab_by_division_day.values():
        model.add(sum(lab_choices) <= 2)

    teacher_limits = dataset.get("teacher_max_per_day", {})
    for (teacher_id, week, day), intervals in teacher_intervals.items():
        limit = teacher_limits.get(teacher_id)
        if limit:
            matching = [
                choices[(activity_index, candidate_index)]
                for activity_index, activity in enumerate(activities)
                for candidate_index, candidate in enumerate(activity["candidates"])
                if candidate["teacher_id"] == teacher_id and candidate["day"] == day
                and week in _weeks(activity)
            ]
            model.add(sum(matching) <= limit)

    preference_costs = []
    for activity_index, activity in enumerate(activities):
        for candidate_index, candidate in enumerate(activity["candidates"]):
            rank = max(1, int(candidate.get("preference_rank") or 100))
            preference_costs.append((rank - 1) * choices[(activity_index, candidate_index)])
    if preference_costs:
        model.minimize(sum(preference_costs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max(1, time_limit_s))
    solver.parameters.random_seed = seed
    solver.parameters.num_workers = num_workers
    status = solver.solve(model)
    name = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return SolveResult(status=name, solve_time_s=round(solver.wall_time, 3))

    assignments = []
    for activity_index, activity in enumerate(activities):
        for candidate_index, candidate in enumerate(activity["candidates"]):
            if solver.value(choices[(activity_index, candidate_index)]):
                assignments.append({
                    "activity_id": activity["id"],
                    "division_id": activity["division_id"],
                    "batch_id": activity.get("batch_id"),
                    "subject_id": activity.get("subject_id"),
                    "teacher_id": candidate["teacher_id"],
                    "room_id": candidate["room_id"],
                    "day": candidate["day"],
                    "start_minute": candidate["start_minute"],
                    "end_minute": candidate["end_minute"],
                })
                break
    assignments.sort(key=lambda value: value["activity_id"])
    return SolveResult(
        status=name,
        assignments=assignments,
        soft_score=int(round(solver.objective_value)),
        solve_time_s=round(solver.wall_time, 3),
    )
