"""
AI Agent router — LLM-powered timetabling assistant.

Supports:
  - Google Gemini (gemini-1.5-flash, free tier)
  - OpenAI (gpt-4o-mini)
  - Rule-based fallback (no API key needed)

Set in backend/.env:
  AI_PROVIDER=gemini
  GEMINI_API_KEY=your_key_here
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Assignment, Teacher, Class, Subject, Room, Timetable, Institution, User

# Load .env every time the module is imported (picks up keys added after first start)
load_dotenv(override=True)

router = APIRouter()


def _cfg():
    """Read config fresh on every request so a restart isn't needed after adding a key."""
    return {
        "provider": os.getenv("AI_PROVIDER", "gemini").lower(),
        "gemini_key": os.getenv("GEMINI_API_KEY", ""),
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    }


# ── schemas ───────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    timetable_id: str
    institution_id: str
    message: str
    history: list[dict] = []


class AbsencePlanChange(BaseModel):
    type: str
    assignment_id: str
    description: str
    new_teacher_id: Optional[str] = None
    new_teacher_name: Optional[str] = None
    new_day: Optional[int] = None
    new_period: Optional[int] = None
    new_day_label: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    action: Optional[str] = None
    data: Optional[dict] = None


class ApplyPlanRequest(BaseModel):
    timetable_id: str
    changes: list[AbsencePlanChange]


# ── DB helpers ────────────────────────────────────────────────────────────────
def _find_timetable(tid: str, db: Session) -> Timetable:
    t = db.query(Timetable).filter(Timetable.id == tid).first()
    if not t:
        raise HTTPException(404, "Timetable not found")
    return t


def _get_lookup(institution_id: str, db: Session):
    teachers    = {t.id: t for t in db.query(Teacher).filter(Teacher.institution_id == institution_id).all()}
    classes     = {c.id: c for c in db.query(Class).filter(Class.institution_id == institution_id).all()}
    subjects    = {s.id: s for s in db.query(Subject).filter(Subject.institution_id == institution_id).all()}
    rooms       = {r.id: r for r in db.query(Room).filter(Room.institution_id == institution_id).all()}
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    return teachers, classes, subjects, rooms, institution


# ── context builder (compact — stays within token limits) ────────────────────
def _build_context(timetable: Timetable, teachers: dict, classes: dict,
                   subjects: dict, rooms: dict, institution: Any) -> str:
    assignments = timetable.assignments or []
    days    = (institution.day_labels if institution else None) or ["Mon", "Tue", "Wed", "Thu", "Fri"]
    periods = (institution.periods_per_day if institution else 7)

    lines = [
        f"TIMETABLE: {timetable.name} | Status: {timetable.status} | {len(assignments)} lectures",
        f"Days: {', '.join(f'{i}={d}' for i,d in enumerate(days))} | Periods/day: {periods}",
        "",
        "TEACHERS:",
    ]
    for t in teachers.values():
        unavail = f" [blocked: {t.unavailable}]" if t.unavailable else ""
        lines.append(f"  {t.name} (id={t.id[:8]}){unavail}")

    lines += ["", "CLASSES:"]
    for c in classes.values():
        lines.append(f"  {c.name} (id={c.id[:8]}, size={c.size})")

    lines += ["", "SUBJECTS:"]
    for s in subjects.values():
        lines.append(f"  {s.name} (id={s.id[:8]}, type={s.room_type})")

    lines += ["", "ROOMS:"]
    for r in rooms.values():
        lines.append(f"  {r.name} (id={r.id[:8]}, type={r.type}, cap={r.capacity})")

    lines += ["", "SCHEDULE (day P=period):"]
    for a in sorted(assignments, key=lambda x: (x.day, x.period)):
        dl   = days[a.day] if a.day < len(days) else f"D{a.day}"
        sn   = subjects.get(a.subject_id, type('', (), {'name': '?'})()).name
        tn   = teachers.get(a.teacher_id, type('', (), {'name': '?'})()).name
        cn   = classes.get(a.class_id,   type('', (), {'name': '?'})()).name
        lines.append(f"  {dl} P{a.period+1}: {cn} | {sn} | {tn} (aid={a.id[:8]})")

    return "\n".join(lines)


# ── tool: handle_absence ──────────────────────────────────────────────────────
def tool_handle_absence(
    teacher_query: str, day_query: str,
    assignments: list, teachers: dict, classes: dict,
    subjects: dict, rooms: dict, days: list, periods: int,
) -> dict:
    q = teacher_query.lower().strip()
    # Match by full name, first name, last name
    absent = None
    best = 0
    for t in teachers.values():
        for part in [t.name] + t.name.lower().replace('prof.','').replace('dr.','').split():
            part = part.strip('.')
            if len(part) > 2 and part in q or (len(part) > 2 and part in teacher_query.lower()):
                if len(part) > best:
                    absent = t
                    best = len(part)
    if not absent:
        # fallback: any substring match
        absent = next((t for t in teachers.values() if q in t.name.lower()), None)
    if not absent:
        return {"error": f"No teacher matching '{teacher_query}'. Available: {[t.name for t in list(teachers.values())[:5]]}"}

    day_idx = _resolve_day(day_query, days)
    if day_idx is None:
        return {"error": f"Could not identify day '{day_query}'."}

    day_label = days[day_idx] if day_idx < len(days) else f"Day{day_idx+1}"
    affected  = [a for a in assignments if a.teacher_id == absent.id and a.day == day_idx]

    if not affected:
        return {
            "error": None, "absent_teacher": absent.name, "day": day_label,
            "message": f"{absent.name} has no lectures on {day_label}.",
            "changes": [], "affected_count": 0,
        }

    teacher_busy: dict[str, set] = defaultdict(set)
    class_busy:   dict[str, set] = defaultdict(set)
    room_busy:    dict[str, set] = defaultdict(set)
    for a in assignments:
        teacher_busy[a.teacher_id].add((a.day, a.period))
        class_busy[a.class_id].add((a.day, a.period))
        room_busy[a.room_id].add((a.day, a.period))

    absent_busy   = teacher_busy[absent.id].copy()
    absent_unavail = set(map(tuple, absent.unavailable or []))
    changes = []

    for a in sorted(affected, key=lambda x: x.period):
        sname = subjects[a.subject_id].name if a.subject_id in subjects else a.subject_id
        cname = classes[a.class_id].name    if a.class_id  in classes  else a.class_id

        # Substitute
        sub_id, sub_name = None, None
        for tid, t in sorted(teachers.items(), key=lambda x: x[1].name):
            if tid == absent.id: continue
            if (a.day, a.period) in teacher_busy[tid]: continue
            if (a.day, a.period) in set(map(tuple, t.unavailable or [])): continue
            sub_id, sub_name = tid, t.name
            break

        changes.append({
            "type": "substitute", "assignment_id": a.id,
            "description": f"**Cover** {day_label} P{a.period+1} — {sname} ({cname})"
                           + (f" → **{sub_name}** covers" if sub_name else " → ⚠️ No free teacher"),
            "new_teacher_id": sub_id, "new_teacher_name": sub_name,
            "new_day": None, "new_period": None, "new_day_label": None,
        })

        # Reschedule
        stype  = subjects[a.subject_id].room_type if a.subject_id in subjects else "classroom"
        csz    = classes[a.class_id].size         if a.class_id  in classes  else 0
        compat = [r.id for r in rooms.values() if r.type == stype and r.capacity >= csz]
        same_subj_days = {a2.day for a2 in assignments
                          if a2.class_id == a.class_id and a2.subject_id == a.subject_id and a2.day != day_idx}

        rday = rperiod = rlabel = None
        for strict in (True, False):
            for d in range(len(days)):
                if d == day_idx: continue
                for p in range(periods):
                    s = (d, p)
                    if s in absent_busy or s in absent_unavail: continue
                    if s in class_busy[a.class_id]: continue
                    if not any(s not in room_busy[rid] for rid in compat): continue
                    if strict and d in same_subj_days: continue
                    rday, rperiod, rlabel = d, p, days[d] if d < len(days) else f"D{d}"
                    break
                if rday is not None: break
            if rday is not None: break

        changes.append({
            "type": "reschedule", "assignment_id": a.id,
            "description": f"**Reschedule** {sname} ({cname})"
                           + (f" → {rlabel} P{rperiod+1}" if rday is not None else " → ⚠️ No free slot"),
            "new_teacher_id": None, "new_teacher_name": None,
            "new_day": rday, "new_period": rperiod, "new_day_label": rlabel,
        })

        if sub_id:   teacher_busy[sub_id].add((a.day, a.period))
        if rday is not None:
            absent_busy.add((rday, rperiod))
            class_busy[a.class_id].add((rday, rperiod))

    return {
        "error": None, "absent_teacher": absent.name, "teacher_id": absent.id,
        "day": day_label, "day_idx": day_idx,
        "affected_count": len(affected), "changes": changes,
    }


def _resolve_day(dq: str, days: list) -> Optional[int]:
    dq = dq.lower().strip()
    for i, dl in enumerate(days):
        if dq in dl.lower() or dl.lower() in dq:
            return i
    day_words = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
        # typos
        "monady": 0, "mondey": 0, "tuseday": 1, "wendsday": 2,
        "wednessday": 2, "thirsday": 3, "fridy": 4,
        # Hindi
        "aaj": 0, "today": 0, "kal": 1, "tomorrow": 1,
    }
    if dq in day_words:
        idx = day_words[dq]
        return idx if idx < len(days) else len(days) - 1
    try:
        idx = int(dq) - 1
        return idx if 0 <= idx < len(days) else None
    except ValueError:
        return None


# ── other tools ───────────────────────────────────────────────────────────────
def tool_show_conflicts(assignments, teachers, classes, rooms):
    t_s = Counter((a.teacher_id, a.day, a.period) for a in assignments)
    c_s = Counter((a.class_id,   a.day, a.period) for a in assignments)
    r_s = Counter((a.room_id,    a.day, a.period) for a in assignments)
    lines = []
    for (tid, d, p), cnt in t_s.items():
        if cnt > 1: lines.append(f"Teacher **{teachers[tid].name if tid in teachers else tid}** double-booked: Day {d+1} P{p+1}")
    for (cid, d, p), cnt in c_s.items():
        if cnt > 1: lines.append(f"Class **{classes[cid].name if cid in classes else cid}** double-booked: Day {d+1} P{p+1}")
    for (rid, d, p), cnt in r_s.items():
        if cnt > 1: lines.append(f"Room **{rooms[rid].name if rid in rooms else rid}** double-booked: Day {d+1} P{p+1}")
    return "\n".join(lines) if lines else "✅ No conflicts — timetable is fully valid."


def tool_get_schedule(query, assignments, teachers, classes, subjects, days):
    q = query.lower()
    mt = next((t for t in teachers.values() if q in t.name.lower()), None)
    if mt:
        rows = sorted([a for a in assignments if a.teacher_id == mt.id], key=lambda a: (a.day, a.period))
        if not rows: return f"No lectures for {mt.name}."
        lines = [f"**{mt.name}** ({len(rows)} lectures):"]
        for a in rows:
            dl = days[a.day] if a.day < len(days) else f"D{a.day+1}"
            lines.append(f"  {dl} P{a.period+1}: {subjects.get(a.subject_id, type('',(),{'name':'?'})()).name} → {classes.get(a.class_id, type('',(),{'name':'?'})()).name}")
        return "\n".join(lines)
    mc = next((c for c in classes.values() if q in c.name.lower()), None)
    if mc:
        rows = sorted([a for a in assignments if a.class_id == mc.id], key=lambda a: (a.day, a.period))
        if not rows: return f"No lectures for {mc.name}."
        lines = [f"**{mc.name}** ({len(rows)} lectures):"]
        for a in rows:
            dl = days[a.day] if a.day < len(days) else f"D{a.day+1}"
            lines.append(f"  {dl} P{a.period+1}: {subjects.get(a.subject_id, type('',(),{'name':'?'})()).name} (by {teachers.get(a.teacher_id, type('',(),{'name':'?'})()).name})")
        return "\n".join(lines)
    return f"No teacher or class matching '{query}'."


def tool_find_free_slots(query, assignments, teachers, days, periods):
    q = query.lower()
    mt = next((t for t in teachers.values() if q in t.name.lower()), None)
    if not mt: return f"No teacher matching '{query}'."
    busy = {(a.day, a.period) for a in assignments if a.teacher_id == mt.id}
    unavail = set(map(tuple, mt.unavailable or []))
    free = [f"{days[d] if d<len(days) else f'D{d+1}'} P{p+1}"
            for d in range(len(days)) for p in range(periods)
            if (d,p) not in busy and (d,p) not in unavail]
    if not free: return f"{mt.name} has no free slots."
    return f"**{mt.name}** free at:\n" + "\n".join(f"  {s}" for s in free[:15]) + (f"\n  ...+{len(free)-15} more" if len(free)>15 else "")


def tool_who_teaches(subject_query, assignments, subjects, teachers):
    q = subject_query.lower()
    matching = [s for s in subjects.values() if q in s.name.lower()]
    if not matching: return f"No subject matching '{subject_query}'."
    return "\n".join(
        f"**{s.name}**: {', '.join(teachers[tid].name for tid in {a.teacher_id for a in assignments if a.subject_id==s.id} if tid in teachers) or 'none'}"
        for s in matching
    )


def tool_workload(assignments, teachers, days):
    counts: dict[str,dict] = {}
    for a in assignments:
        if a.teacher_id not in counts:
            counts[a.teacher_id] = {"total":0,"per_day":Counter()}
        counts[a.teacher_id]["total"] += 1
        counts[a.teacher_id]["per_day"][a.day] += 1
    lines = ["**Workload report:**"]
    for tid, st in sorted(counts.items(), key=lambda x:-x[1]["total"]):
        tn = teachers[tid].name if tid in teachers else tid
        pd = ", ".join(f"{days[d] if d<len(days) else f'D{d+1}'}:{n}" for d,n in sorted(st["per_day"].items()))
        lines.append(f"  {tn}: **{st['total']}** | {pd}")
    return "\n".join(lines)


# ── LLM tool schema ───────────────────────────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "handle_absence",
        "description": (
            "CALL THIS when a teacher is absent, sick, on leave, not available, or cannot come "
            "on any specific day. Also call when someone says 'change the schedule because X is not available'. "
            "This finds all their lectures that day, assigns substitute teachers, and reschedules the lectures."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "teacher_name": {"type": "string", "description": "The name of the absent teacher (use the exact name from the timetable data)"},
                "day": {"type": "string", "description": "Day of absence e.g. 'Monday', 'Tuesday', 'Mon', 'today'"},
            },
            "required": ["teacher_name", "day"],
        },
    },
    {
        "name": "show_conflicts",
        "description": "Check for double-booked teachers, classes, or rooms.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_schedule",
        "description": "Get weekly schedule for a teacher or class/batch.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Teacher or class name"}},
            "required": ["name"],
        },
    },
    {
        "name": "find_free_slots",
        "description": "Find all free time slots for a teacher.",
        "parameters": {
            "type": "object",
            "properties": {"teacher_name": {"type": "string"}},
            "required": ["teacher_name"],
        },
    },
    {
        "name": "who_teaches",
        "description": "Find which teacher(s) teach a subject.",
        "parameters": {
            "type": "object",
            "properties": {"subject": {"type": "string"}},
            "required": ["subject"],
        },
    },
    {
        "name": "workload_report",
        "description": "Show total lecture count per teacher.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]


# ── tool dispatcher ────────────────────────────────────────────────────────────
def _dispatch(tool_name, args, timetable, teachers, classes, subjects, rooms, days, periods):
    asgn = timetable.assignments or []
    if tool_name == "handle_absence":
        plan = tool_handle_absence(args.get("teacher_name",""), args.get("day",""),
                                   asgn, teachers, classes, subjects, rooms, days, periods)
        if plan.get("error"):
            return plan["error"], None
        if plan["affected_count"] == 0:
            return plan.get("message", "No lectures affected."), None
        lines = [f"📋 **Absence plan — {plan['absent_teacher']} on {plan['day']}**",
                 f"{plan['affected_count']} lecture(s) affected:\n"]
        for ch in plan["changes"]:
            lines.append(f"• {ch['description']}")
        lines.append("\n*Click **Confirm & Apply** to apply these changes.*")
        return "\n".join(lines), {"action": "absence_plan", "plan": plan}
    elif tool_name == "show_conflicts":
        return tool_show_conflicts(asgn, teachers, classes, rooms), None
    elif tool_name == "get_schedule":
        return tool_get_schedule(args.get("name",""), asgn, teachers, classes, subjects, days), None
    elif tool_name == "find_free_slots":
        return tool_find_free_slots(args.get("teacher_name",""), asgn, teachers, days, periods), None
    elif tool_name == "who_teaches":
        return tool_who_teaches(args.get("subject",""), asgn, subjects, teachers), None
    elif tool_name == "workload_report":
        return tool_workload(asgn, teachers, days), None
    return f"Unknown tool: {tool_name}", None


# ── Gemini ────────────────────────────────────────────────────────────────────
def _gemini_call(system_prompt, messages, tools, gemini_key, gemini_model):
    """
    Call Gemini. Enforces strict alternating user/model turns as required by the API.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"

    # Enforce alternating user/model — merge consecutive same-role messages
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        text = msg.get("content") or ""
        if not text.strip():
            continue
        if contents and contents[-1]["role"] == role:
            # Append to last message of same role
            contents[-1]["parts"][0]["text"] += "\n" + text
        else:
            contents.append({"role": role, "parts": [{"text": text}]})

    # Must start with user
    if not contents or contents[0]["role"] != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "Begin."}]})

    # Must end with user (last message = the actual question)
    if contents[-1]["role"] != "user":
        contents.append({"role": "user", "parts": [{"text": "Please respond."}]})

    fn_decls = []
    for t in tools:
        params = t.get("parameters", {})
        if not params.get("properties"):
            params = {"type": "object", "properties": {}}
        fn_decls.append({"name": t["name"], "description": t["description"], "parameters": params})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "tools": [{"function_declarations": fn_decls}],
        "generation_config": {"temperature": 0.1, "max_output_tokens": 2048},
    }

    resp = httpx.post(url, params={"key": gemini_key}, json=payload, timeout=40)

    if not resp.is_success:
        raise httpx.HTTPStatusError(
            f"Gemini {resp.status_code}: {resp.text[:300]}",
            request=resp.request, response=resp
        )
    return resp.json()


def _gemini_extract(resp):
    parts = resp.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    texts, calls = [], []
    for p in parts:
        if "text" in p:
            texts.append(p["text"])
        elif "functionCall" in p:
            fc = p["functionCall"]
            calls.append({"name": fc["name"], "args": fc.get("args", {})})
    return ("\n".join(texts) if texts else None), calls


# ── OpenAI ────────────────────────────────────────────────────────────────────
def _openai_call(system_prompt, messages, tools, openai_key, openai_model):
    oa_tools = [{"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["parameters"]
    }} for t in tools]
    payload = {
        "model": openai_model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "tools": oa_tools, "tool_choice": "auto",
        "temperature": 0.1, "max_tokens": 2048,
    }
    resp = httpx.post("https://api.openai.com/v1/chat/completions",
                      headers={"Authorization": f"Bearer {openai_key}"},
                      json=payload, timeout=40)
    if not resp.is_success:
        raise httpx.HTTPStatusError(
            f"OpenAI {resp.status_code}: {resp.text[:300]}",
            request=resp.request, response=resp
        )
    return resp.json()


def _openai_extract(resp):
    msg = resp["choices"][0]["message"]
    calls = []
    for tc in msg.get("tool_calls") or []:
        calls.append({"name": tc["function"]["name"], "args": json.loads(tc["function"]["arguments"])})
    return msg.get("content"), calls


# ── agentic loop ──────────────────────────────────────────────────────────────
def _run_agent(system_prompt, messages, timetable, teachers, classes, subjects, rooms, days, periods, cfg):
    provider = cfg["provider"]

    def call_llm(msgs):
        if provider == "gemini":
            r = _gemini_call(system_prompt, msgs, TOOL_DEFINITIONS, cfg["gemini_key"], cfg["gemini_model"])
            return _gemini_extract(r)
        elif provider == "openai":
            r = _openai_call(system_prompt, msgs, TOOL_DEFINITIONS, cfg["openai_key"], cfg["openai_model"])
            return _openai_extract(r)
        raise ValueError(f"Unknown provider: {provider}")

    # First turn
    text, tool_calls = call_llm(messages)

    if not tool_calls:
        return (text or "I didn't understand. Try: 'Prof. X is absent on Monday', 'show conflicts', 'workload report'."), None

    # Execute tools
    tool_results, structured_data = [], None
    for tc in tool_calls:
        t_text, t_data = _dispatch(tc["name"], tc.get("args", {}),
                                   timetable, teachers, classes, subjects, rooms, days, periods)
        tool_results.append({"tool": tc["name"], "result": t_text})
        if t_data:
            structured_data = t_data

    # Absence plan → return immediately (already fully formatted)
    if structured_data and structured_data.get("action") == "absence_plan":
        return "\n\n".join(r["result"] for r in tool_results), structured_data

    # Other tools → second LLM turn for natural language answer
    tool_context = "\n\n".join(f"[{r['tool']}]\n{r['result']}" for r in tool_results)
    follow_up = messages + [
        {"role": "assistant", "content": f"Tool results:\n{tool_context}"},
        {"role": "user", "content": "Give me a clear, helpful answer based on those results."},
    ]
    final, _ = call_llm(follow_up)
    return final or tool_context, None


# ── rule-based fallback ───────────────────────────────────────────────────────
_ABSENCE_WORDS = [
    "absent", "sick", "leave", "not available", "not avail", "unavailable",
    "not coming", "won't come", "wont come", "cannot come", "can't come",
    "not present", "on leave", "holiday", "off today", "not in",
    "change", "replace", "substitute", "cover",
    # typos
    "avalible", "avaliable", "avialable", "availble", "avalable",
    # Hindi
    "nahi", "nhi", "chutti", "absen", "aayega", "aayegi", "nahi aaye", "band",
]

_DAY_MAP = {
    "monday":0, "tuesday":1, "wednesday":2, "thursday":3, "friday":4, "saturday":5,
    "mon":0, "tue":1, "wed":2, "thu":3, "fri":4, "sat":5,
    "monady":0, "mondey":0, "tuseday":1, "wendsday":2, "wednessday":2, "thirsday":3, "fridy":4,
    "today":0, "aaj":0, "tomorrow":1, "kal":1,
}


def _detect_absence(msg, teachers, days):
    m = msg.lower()
    if not any(kw in m for kw in _ABSENCE_WORDS):
        return None, None

    # Find teacher
    matched_teacher, best = None, 0
    for t in teachers.values():
        parts = [t.name] + [p.strip('.') for p in
                 t.name.lower().replace('prof.','').replace('dr.','').split() if len(p.strip('.')) > 2]
        for part in parts:
            if part.lower() in m and len(part) > best:
                matched_teacher, best = t.name, len(part)
    if not matched_teacher:
        return None, None

    # Find day
    found_day = days[0]
    for word in re.findall(r'\w+', m):
        if word in _DAY_MAP:
            idx = _DAY_MAP[word]
            found_day = days[idx] if idx < len(days) else days[-1]
            break
    for dl in days:
        if dl.lower() in m:
            found_day = dl
            break

    return matched_teacher, found_day


def _rule_based(msg, timetable, teachers, classes, subjects, rooms, days, periods):
    m = msg.lower().strip()
    asgn = timetable.assignments or []

    # Absence (typo-tolerant scan)
    tq, dq = _detect_absence(msg, teachers, days)
    if tq and dq:
        plan = tool_handle_absence(tq, dq, asgn, teachers, classes, subjects, rooms, days, periods)
        if plan.get("error"):
            return plan["error"], None
        if plan["affected_count"] == 0:
            return plan.get("message", "No lectures affected."), None
        lines = [f"📋 **Absence plan — {plan['absent_teacher']} on {plan['day']}**",
                 f"{plan['affected_count']} lecture(s) affected:\n"]
        for ch in plan["changes"]:
            lines.append(f"• {ch['description']}")
        lines.append("\n*Click **Confirm & Apply** to apply these changes.*")
        return "\n".join(lines), {"action": "absence_plan", "plan": plan}

    if any(w in m for w in ("conflict", "clash", "double")):
        return tool_show_conflicts(asgn, teachers, classes, rooms), None
    if "workload" in m:
        return tool_workload(asgn, teachers, days), None
    who = re.search(r"who\s+teaches\s+(.+)", m)
    if who:
        return tool_who_teaches(who.group(1).strip(), asgn, subjects, teachers), None
    sched = (re.search(r"(?:show|get|display)\s+(.+?)(?:'s)?\s+schedule", m) or
             re.search(r"schedule\s+(?:of|for)\s+(.+)", m))
    if sched:
        return tool_get_schedule(sched.group(1).strip(), asgn, teachers, classes, subjects, days), None
    if "schedule" in m:
        for t in teachers.values():
            if t.name.lower() in m or t.name.lower().split()[-1] in m:
                return tool_get_schedule(t.name, asgn, teachers, classes, subjects, days), None
        for c in classes.values():
            if c.name.lower() in m:
                return tool_get_schedule(c.name, asgn, teachers, classes, subjects, days), None
    free = re.search(r"free\s+slots?\s+(?:for|of)\s+(.+)", m)
    if free:
        return tool_find_free_slots(free.group(1).strip(), asgn, teachers, days, periods), None
    if "summar" in m or "overview" in m:
        nc = len({a.class_id for a in asgn}); nt = len({a.teacher_id for a in asgn})
        return (f"**{timetable.name}** — {timetable.status}\n"
                f"Lectures: {len(asgn)} | Classes: {nc} | Teachers: {nt} | Score: {timetable.soft_score}"), None

    # Last resort: teacher name in message
    for t in teachers.values():
        parts = [p.strip('.') for p in
                 t.name.lower().replace('prof.','').replace('dr.','').split() if len(p.strip('.')) > 3]
        if any(p in m for p in parts):
            if any(w in m for w in ("absent", "sick", "leave", "avail", "not", "change")):
                plan = tool_handle_absence(t.name, days[0], asgn, teachers, classes, subjects, rooms, days, periods)
                if not plan.get("error") and plan["affected_count"] > 0:
                    lines = [f"📋 **Absence plan — {plan['absent_teacher']} on {plan['day']}**",
                             f"(Assumed today = {plan['day']}. Say the day if different.)\n"]
                    for ch in plan["changes"]:
                        lines.append(f"• {ch['description']}")
                    lines.append("\n*Click **Confirm & Apply** to apply.*")
                    return "\n".join(lines), {"action": "absence_plan", "plan": plan}
            return tool_get_schedule(t.name, asgn, teachers, classes, subjects, days), None

    return (
        "I can help with:\n"
        "• **Prof. Sonu Surti is absent on Monday** — auto substitutes + reschedule\n"
        "• show conflicts\n"
        "• show [teacher/class] schedule\n"
        "• who teaches [subject]\n"
        "• find free slots for [teacher]\n"
        "• workload report\n"
        "• summarize timetable\n\n"
        "Type naturally — I handle typos and Hindi too."
    ), None


# ── system prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are Timely AI — a smart timetabling assistant for colleges and schools.

The timetable data is provided at the start of the conversation. Use it.

RULE 1 — ABSENCE: If the user's message mentions a teacher being absent, sick, unavailable,
on leave, not coming, or asks to "change" or "replace" a teacher's schedule for a day,
IMMEDIATELY call handle_absence with:
  - teacher_name: the exact teacher name from the timetable data
  - day: the day mentioned (Monday, Tuesday, etc.)

RULE 2 — OTHER QUERIES: Use the appropriate tool:
  - show_conflicts → double-bookings
  - get_schedule   → teacher or class weekly timetable
  - find_free_slots→ when is a teacher free
  - who_teaches    → which teacher covers a subject
  - workload_report→ lecture counts per teacher

RULE 3 — ALWAYS use the actual names from the timetable data, not placeholders.
RULE 4 — For handle_absence, DO NOT add commentary. The tool output is the full reply.
RULE 5 — Be concise. The user is a college admin, not a student.
"""


# ── main endpoint ──────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatMessage, db: Session = Depends(get_db),
         _: User = Depends(get_current_user)):
    cfg = _cfg()  # read .env fresh every request

    timetable = _find_timetable(body.timetable_id, db)
    teachers, classes, subjects, rooms, institution = _get_lookup(body.institution_id, db)
    days    = (institution.day_labels if institution else None) or ["Mon", "Tue", "Wed", "Thu", "Fri"]
    periods = (institution.periods_per_day if institution else 7)

    context = _build_context(timetable, teachers, classes, subjects, rooms, institution)

    # Build messages: context first, then history, then current question
    messages = [
        {"role": "user",      "content": f"Here is the current timetable:\n\n{context}"},
        {"role": "assistant", "content": "Understood. I have the timetable. Ask me anything."},
    ]
    for h in body.history[-6:]:   # keep last 6 turns to stay within token limits
        role    = h.get("role", "user")
        content = h.get("content", "")
        if content.strip():
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": body.message})

    # Decide: LLM or rule-based
    use_llm = (
        cfg["provider"] != "none"
        and not (cfg["provider"] == "gemini"  and not cfg["gemini_key"])
        and not (cfg["provider"] == "openai"  and not cfg["openai_key"])
    )

    reply, data = None, None
    try:
        if use_llm:
            reply, data = _run_agent(SYSTEM_PROMPT, messages,
                                     timetable, teachers, classes, subjects, rooms,
                                     days, periods, cfg)
        else:
            reply, data = _rule_based(body.message, timetable,
                                      teachers, classes, subjects, rooms, days, periods)
    except httpx.HTTPStatusError as e:
        err_body = e.response.text[:400] if e.response else str(e)
        fallback, data = _rule_based(body.message, timetable,
                                     teachers, classes, subjects, rooms, days, periods)
        reply = f"⚠️ LLM API error ({e.response.status_code if e.response else '?'}): {err_body}\n\n---\n{fallback}"
    except Exception as e:
        fallback, data = _rule_based(body.message, timetable,
                                     teachers, classes, subjects, rooms, days, periods)
        reply = f"⚠️ AI error: {str(e)[:200]}\n\n---\n{fallback}"

    return ChatResponse(
        reply=reply or "Something went wrong.",
        action=data.get("action") if data else None,
        data=data,
    )


# ── apply plan endpoint ────────────────────────────────────────────────────────
@router.post("/apply-plan")
def apply_plan(body: ApplyPlanRequest, db: Session = Depends(get_db),
               _: User = Depends(get_current_user)):
    timetable = db.query(Timetable).filter(Timetable.id == body.timetable_id).first()
    if not timetable:
        raise HTTPException(404, "Timetable not found")
    if timetable.status == "published":
        raise HTTPException(400, "Unpublish the timetable before editing.")

    applied, skipped = [], []

    for change in body.changes:
        a = db.query(Assignment).filter(
            Assignment.id == change.assignment_id,
            Assignment.timetable_id == body.timetable_id,
        ).first()
        if not a:
            skipped.append({"id": change.assignment_id, "reason": "not found"})
            continue

        if change.type == "substitute" and change.new_teacher_id:
            a.teacher_id = change.new_teacher_id
            applied.append({"type": "substitute", "id": a.id})

        elif change.type == "reschedule" and change.new_day is not None and change.new_period is not None:
            clash = db.query(Assignment).filter(
                Assignment.timetable_id == body.timetable_id,
                Assignment.day    == change.new_day,
                Assignment.period == change.new_period,
                Assignment.id     != change.assignment_id,
            ).filter(
                (Assignment.class_id   == a.class_id)   |
                (Assignment.teacher_id == a.teacher_id) |
                (Assignment.room_id    == a.room_id)
            ).first()
            if clash:
                skipped.append({"id": a.id, "reason": "conflict at target slot"})
                continue
            a.day    = change.new_day
            a.period = change.new_period
            applied.append({"type": "reschedule", "id": a.id,
                            "new_day": change.new_day, "new_period": change.new_period})

    db.commit()
    return {
        "message": f"✅ Applied {len(applied)} change(s)" +
                   (f", skipped {len(skipped)}" if skipped else "") + ".",
        "applied": applied,
        "skipped": skipped,
    }
