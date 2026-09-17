"""
Curriculum presets router — CBSE, ICSE, and State board subject/lesson mappings.
Returns preset subject lists with recommended lessons/week per grade.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.models import User

router = APIRouter()

# ── CBSE Curriculum (based on NCERT/CBSE guidelines) ─────────────────────────
CBSE = {
    "1-5": [  # Primary (Classes 1–5)
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "English",            "room_type": "classroom", "lessons_per_week": 6, "color": "#8b5cf6"},
        {"name": "Hindi",              "room_type": "classroom", "lessons_per_week": 5, "color": "#f97316"},
        {"name": "Environmental Studies","room_type": "classroom","lessons_per_week": 4, "color": "#22c55e"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
        {"name": "Art & Craft",        "room_type": "classroom", "lessons_per_week": 2, "color": "#f43f5e"},
        {"name": "Computer Science",   "room_type": "lab",       "lessons_per_week": 1, "color": "#06b6d4"},
    ],
    "6-8": [  # Middle School (Classes 6–8)
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "English",            "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "Hindi",              "room_type": "classroom", "lessons_per_week": 5, "color": "#f97316"},
        {"name": "Science",            "room_type": "lab",       "lessons_per_week": 5, "color": "#22c55e"},
        {"name": "Social Science",     "room_type": "classroom", "lessons_per_week": 4, "color": "#eab308"},
        {"name": "Sanskrit / 3rd Lang","room_type": "classroom", "lessons_per_week": 3, "color": "#a855f7"},
        {"name": "Computer Science",   "room_type": "lab",       "lessons_per_week": 2, "color": "#06b6d4"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
        {"name": "Art Education",      "room_type": "classroom", "lessons_per_week": 1, "color": "#f43f5e"},
        {"name": "Music / Dance",      "room_type": "classroom", "lessons_per_week": 1, "color": "#14b8a6"},
    ],
    "9-10": [  # Secondary (Classes 9–10)
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "English",            "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "Hindi",              "room_type": "classroom", "lessons_per_week": 5, "color": "#f97316"},
        {"name": "Science",            "room_type": "lab",       "lessons_per_week": 6, "color": "#22c55e"},
        {"name": "Social Science",     "room_type": "classroom", "lessons_per_week": 5, "color": "#eab308"},
        {"name": "Sanskrit / 3rd Lang","room_type": "classroom", "lessons_per_week": 4, "color": "#a855f7"},
        {"name": "Computer Science",   "room_type": "lab",       "lessons_per_week": 2, "color": "#06b6d4"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
    ],
    "11-12": [  # Senior Secondary (Classes 11–12) — Science stream
        {"name": "Physics",            "room_type": "lab",       "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "Chemistry",          "room_type": "lab",       "lessons_per_week": 6, "color": "#22c55e"},
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#8b5cf6"},
        {"name": "Biology / Computer Science", "room_type": "lab", "lessons_per_week": 6, "color": "#f97316"},
        {"name": "English",            "room_type": "classroom", "lessons_per_week": 5, "color": "#a855f7"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 1, "color": "#ec4899"},
    ],
}

# ── ICSE Curriculum ───────────────────────────────────────────────────────────
ICSE = {
    "1-5": [
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "English Language",   "room_type": "classroom", "lessons_per_week": 6, "color": "#8b5cf6"},
        {"name": "English Literature", "room_type": "classroom", "lessons_per_week": 3, "color": "#a855f7"},
        {"name": "Hindi",              "room_type": "classroom", "lessons_per_week": 4, "color": "#f97316"},
        {"name": "Environmental Science","room_type": "classroom","lessons_per_week": 3, "color": "#22c55e"},
        {"name": "Computer Studies",   "room_type": "lab",       "lessons_per_week": 2, "color": "#06b6d4"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
        {"name": "Art",                "room_type": "classroom", "lessons_per_week": 2, "color": "#f43f5e"},
    ],
    "6-8": [
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "English Language",   "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "English Literature", "room_type": "classroom", "lessons_per_week": 3, "color": "#a855f7"},
        {"name": "Hindi",              "room_type": "classroom", "lessons_per_week": 4, "color": "#f97316"},
        {"name": "History & Civics",   "room_type": "classroom", "lessons_per_week": 3, "color": "#eab308"},
        {"name": "Geography",          "room_type": "classroom", "lessons_per_week": 3, "color": "#14b8a6"},
        {"name": "Physics",            "room_type": "lab",       "lessons_per_week": 3, "color": "#22c55e"},
        {"name": "Chemistry",          "room_type": "lab",       "lessons_per_week": 3, "color": "#10b981"},
        {"name": "Biology",            "room_type": "lab",       "lessons_per_week": 2, "color": "#84cc16"},
        {"name": "Computer Applications", "room_type": "lab",   "lessons_per_week": 2, "color": "#06b6d4"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
    ],
    "9-10": [
        {"name": "Mathematics",        "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "English Language",   "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "English Literature", "room_type": "classroom", "lessons_per_week": 3, "color": "#a855f7"},
        {"name": "Hindi",              "room_type": "classroom", "lessons_per_week": 4, "color": "#f97316"},
        {"name": "History & Civics",   "room_type": "classroom", "lessons_per_week": 3, "color": "#eab308"},
        {"name": "Geography",          "room_type": "classroom", "lessons_per_week": 3, "color": "#14b8a6"},
        {"name": "Physics",            "room_type": "lab",       "lessons_per_week": 4, "color": "#22c55e"},
        {"name": "Chemistry",          "room_type": "lab",       "lessons_per_week": 4, "color": "#10b981"},
        {"name": "Biology",            "room_type": "lab",       "lessons_per_week": 3, "color": "#84cc16"},
        {"name": "Computer Applications", "room_type": "lab",   "lessons_per_week": 2, "color": "#06b6d4"},
        {"name": "Physical Education", "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
    ],
}

# ── Maharashtra State Board ───────────────────────────────────────────────────
MAHA_STATE = {
    "1-5": [
        {"name": "Ganit (Mathematics)", "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "Marathi",             "room_type": "classroom", "lessons_per_week": 6, "color": "#f97316"},
        {"name": "English",             "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "Hindi",               "room_type": "classroom", "lessons_per_week": 4, "color": "#eab308"},
        {"name": "Parisara Abhyas (EVS)","room_type": "classroom","lessons_per_week": 3, "color": "#22c55e"},
        {"name": "Physical Education",  "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
        {"name": "Art",                 "room_type": "classroom", "lessons_per_week": 2, "color": "#f43f5e"},
    ],
    "6-8": [
        {"name": "Ganit (Mathematics)", "room_type": "classroom", "lessons_per_week": 6, "color": "#3b82f6"},
        {"name": "Marathi",             "room_type": "classroom", "lessons_per_week": 5, "color": "#f97316"},
        {"name": "English",             "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "Hindi",               "room_type": "classroom", "lessons_per_week": 4, "color": "#eab308"},
        {"name": "Vigyan (Science)",    "room_type": "lab",       "lessons_per_week": 5, "color": "#22c55e"},
        {"name": "Itihas (History)",    "room_type": "classroom", "lessons_per_week": 3, "color": "#a855f7"},
        {"name": "Bhugol (Geography)",  "room_type": "classroom", "lessons_per_week": 3, "color": "#14b8a6"},
        {"name": "Nagrikshastra (Civics)","room_type": "classroom","lessons_per_week": 2,"color": "#06b6d4"},
        {"name": "Physical Education",  "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
    ],
    "9-10": [
        {"name": "Algebra",             "room_type": "classroom", "lessons_per_week": 4, "color": "#3b82f6"},
        {"name": "Geometry",            "room_type": "classroom", "lessons_per_week": 3, "color": "#2563eb"},
        {"name": "Marathi",             "room_type": "classroom", "lessons_per_week": 5, "color": "#f97316"},
        {"name": "English",             "room_type": "classroom", "lessons_per_week": 5, "color": "#8b5cf6"},
        {"name": "Hindi",               "room_type": "classroom", "lessons_per_week": 4, "color": "#eab308"},
        {"name": "Science Part 1 (Physics & Chem)", "room_type": "lab", "lessons_per_week": 5, "color": "#22c55e"},
        {"name": "Science Part 2 (Biology)", "room_type": "lab",  "lessons_per_week": 3, "color": "#10b981"},
        {"name": "History & Political Science", "room_type": "classroom", "lessons_per_week": 4, "color": "#a855f7"},
        {"name": "Geography",           "room_type": "classroom", "lessons_per_week": 3, "color": "#14b8a6"},
        {"name": "Physical Education",  "room_type": "field",     "lessons_per_week": 2, "color": "#ec4899"},
    ],
}

ALL_PRESETS = {
    "CBSE": CBSE,
    "ICSE": ICSE,
    "Maharashtra State Board": MAHA_STATE,
}

GRADE_GROUPS = ["1-5", "6-8", "9-10", "11-12"]


@router.get("")
def list_presets(_: User = Depends(get_current_user)):
    """List available curriculum presets and their grade groups."""
    return [
        {
            "board": board,
            "grade_groups": list(grades.keys()),
        }
        for board, grades in ALL_PRESETS.items()
    ]


@router.get("/{board}/{grade_group}")
def get_preset(board: str, grade_group: str, _: User = Depends(get_current_user)):
    """
    Get the subject list for a given board and grade group.
    board: CBSE | ICSE | Maharashtra State Board
    grade_group: 1-5 | 6-8 | 9-10 | 11-12
    """
    board_data = ALL_PRESETS.get(board)
    if not board_data:
        from fastapi import HTTPException
        raise HTTPException(404, f"Board '{board}' not found. Available: {list(ALL_PRESETS.keys())}")

    subjects = board_data.get(grade_group)
    if subjects is None:
        from fastapi import HTTPException
        raise HTTPException(404, f"Grade group '{grade_group}' not in {board}. Available: {list(board_data.keys())}")

    return {
        "board": board,
        "grade_group": grade_group,
        "subjects": subjects,
        "total_lessons_per_week": sum(s["lessons_per_week"] for s in subjects),
    }
