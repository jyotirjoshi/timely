"""
Sample school dataset — used by seeds, tests, and the frontend demo.

Models a small but realistic school:
  * 5 days x 7 periods
  * 6 classes (Grade 6 A/B, Grade 7 A/B, Grade 8 A/B), ~30 students each
  * 12 teachers across subjects, some part-time (unavailability windows)
  * 8 rooms: 6 classrooms, 1 science lab, 1 sports field
"""

from __future__ import annotations

from typing import Any

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
PERIODS_PER_DAY = 7


def build_sample_dataset() -> dict[str, Any]:
    classes = [
        {"id": f"c{g}{s}", "name": f"Grade {g}-{s}", "size": 30}
        for g in (6, 7, 8) for s in ("A", "B")
    ]

    subjects = [
        {"id": "math",    "name": "Math",            "room_type": "classroom"},
        {"id": "eng",     "name": "English",         "room_type": "classroom"},
        {"id": "sci",     "name": "Science",         "room_type": "lab"},
        {"id": "hist",    "name": "History",         "room_type": "classroom"},
        {"id": "pe",      "name": "Physical Ed.",    "room_type": "field"},
        {"id": "art",     "name": "Art",             "room_type": "classroom"},
    ]

    teachers = [
        {"id": "t_math1", "name": "A. Sharma",  "subjects": ["math"], "max_per_day": 5,
         "unavailable": []},
        {"id": "t_math2", "name": "R. Verma",   "subjects": ["math"], "max_per_day": 5,
         "unavailable": [[0, 0], [0, 1]]},                       # not Mon periods 1-2
        {"id": "t_eng1",  "name": "S. Iyer",    "subjects": ["eng"], "max_per_day": 5,
         "unavailable": []},
        {"id": "t_eng2",  "name": "J. D'Souza", "subjects": ["eng"], "max_per_day": 4,
         "unavailable": [[4, p] for p in range(PERIODS_PER_DAY)]},  # off Fridays (part-time)
        {"id": "t_sci1",  "name": "K. Rao",     "subjects": ["sci"], "max_per_day": 5,
         "unavailable": []},
        {"id": "t_sci2",  "name": "M. Khan",    "subjects": ["sci"], "max_per_day": 5,
         "unavailable": []},
        {"id": "t_hist1", "name": "P. Nair",    "subjects": ["hist"], "max_per_day": 5,
         "unavailable": []},
        {"id": "t_hist2", "name": "L. Gupta",   "subjects": ["hist"], "max_per_day": 5,
         "unavailable": []},
        {"id": "t_pe1",   "name": "D. Singh",   "subjects": ["pe"], "max_per_day": 6,
         "unavailable": []},
        {"id": "t_art1",  "name": "N. Mehta",   "subjects": ["art"], "max_per_day": 5,
         "unavailable": [[2, p] for p in range(PERIODS_PER_DAY)]},  # off Wednesdays
    ]

    rooms = (
        [{"id": f"r_c{i}", "name": f"Room {100 + i}", "type": "classroom", "capacity": 35}
         for i in range(1, 7)]
        + [{"id": "r_lab1", "name": "Science Lab", "type": "lab", "capacity": 30},
           {"id": "r_field", "name": "Sports Field", "type": "field", "capacity": 100}]
    )

    # curriculum: subject -> lessons/week per class
    curriculum = {"math": 5, "eng": 5, "sci": 4, "hist": 3, "pe": 2, "art": 2}
    subject_teacher = {  # round-robin pools per subject
        "math": ["t_math1", "t_math2"], "eng": ["t_eng1", "t_eng2"],
        "sci": ["t_sci1", "t_sci2"], "hist": ["t_hist1", "t_hist2"],
        "pe": ["t_pe1"], "art": ["t_art1"],
    }

    lessons = []
    for ci, cls in enumerate(classes):
        for sid, count in curriculum.items():
            pool = subject_teacher[sid]
            tid = pool[ci % len(pool)]
            for k in range(count):
                lessons.append({
                    "id": f"l_{cls['id']}_{sid}_{k}",
                    "class_id": cls["id"],
                    "subject_id": sid,
                    "teacher_id": tid,
                    "pinned": None,
                })

    return {
        "days": DAYS,
        "periods_per_day": PERIODS_PER_DAY,
        "teachers": teachers,
        "rooms": rooms,
        "classes": classes,
        "subjects": subjects,
        "lessons": lessons,
        "soft_constraints": {
            "teacher_max_consecutive": {"weight": 5, "max": 3},
            "subject_spread": {"weight": 3},
            "subject_preferred_slots": {"weight": 2, "rules": [
                {"subject_id": "pe", "allowed_periods": [2, 3, 4, 5, 6]},  # not first two periods
                {"subject_id": "math", "allowed_periods": [0, 1, 2, 3, 4]},
            ]},
            "minimize_teacher_gaps": {"weight": 1},
        },
    }


if __name__ == "__main__":
    ds = build_sample_dataset()
    print(f"classes={len(ds['classes'])} teachers={len(ds['teachers'])} "
          f"rooms={len(ds['rooms'])} lessons={len(ds['lessons'])}")
