# Timely — Automated & Agentic Timetabling Platform

> Generate conflict-free school timetables in minutes with OR-Tools CP-SAT, manage them with AI chat, handle teacher absences with auto-substitution, and work with the full Indian academic calendar.

---

## Quick Start

### Backend
```
Double-click: app\backend\start.bat
```
Or manually:
```bash
cd app/backend
C:\Users\spars\venv\Scripts\python.exe run.py
# API → http://localhost:8000
# Docs → http://localhost:8000/docs
```

### Frontend
```
Double-click: app\start-frontend.bat
```
Or manually:
```bash
cd app
npm run dev
# App → http://localhost:3000
```

---

## Features

### Timetable Generation (fully automatic)
- Enter classes, subjects, teachers, rooms
- Click **Generate Timetable** — OR-Tools CP-SAT solves everything automatically
- Hard constraints: no double-booking, room capacity, teacher unavailability
- Soft constraints: spread subjects across week, no 4 consecutive periods, minimize gaps
- Returns best feasible solution within the time limit

### Indian Curriculum Presets
Go to **Curriculum → Load preset (CBSE/ICSE)**:
- **CBSE** — Classes 1–5, 6–8, 9–10, 11–12 (Science)
- **ICSE / ISC** — Classes 1–5, 6–8, 9–10
- **Maharashtra State Board (SSC)** — Classes 1–5, 6–8, 9–10
- Automatically creates subjects with correct lessons/week (e.g. CBSE 6–8: Math 6×, Science 5×, Hindi 5×...)
- Generates the full curriculum in one click

### How lessons/week is decided
- Each subject has a `lessons_per_week` field (visible on the Subjects page)
- The preset sets it to board-recommended values automatically
- You can always adjust it manually on the Subjects page
- The Auto-generate function creates exactly that many lesson slots per class per subject

### Teacher Absences & Substitution
Go to **Absences**:
1. Click **Mark absent** → select teacher, date, reason
2. Click **Find substitutes** on any recorded absence
3. The system checks your active timetable and shows per-period candidates who are:
   - Free at that slot
   - Not marked absent on that date
   - Not blocked by their own unavailability
4. Select a substitute for each period and click **Apply substitutes**

### Indian Holidays Calendar
Go to **Holidays**:
- Click **Load India Holidays** to seed the full 2026 calendar including:
  - All Gazetted national holidays (Republic Day, Independence Day, Gandhi Jayanti, Eid, Diwali, Christmas, etc.)
  - State holidays
  - School-specific dates (Teacher's Day, Children's Day)
  - Summer vacation (May–mid June), Diwali break, Winter break
- Add custom holidays manually
- Types: national / state / school / optional

### AI Chat Assistant
Open any timetable → click **AI Chat**:
- Works without an API key (rule-based fallback)
- With Gemini API key: full natural language understanding
- Ask anything: conflicts, workloads, schedules, free slots, substitute suggestions

#### Enable Gemini AI (free, 2 min setup)
1. Get free key at https://aistudio.google.com/apikey
2. Create `app/backend/.env`:
   ```
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_key_here
   ```
3. Restart backend

---

## Settings → Indian School Templates
Quick-apply common structures:
- **CBSE 8 periods** — 5 days, 8:00–1:30
- **CBSE 7 periods** — 5 days, 8:00–1:30  
- **SSC 6 periods** — 6 days (including Saturday), 7:30–12:00

Set **Academic year start** (CBSE: 1 April, Maharashtra SSC: 15 June) and **Board affiliation**.

---

## Workflow for an Indian School

1. **Settings** → Set name, board (CBSE/ICSE/SSC), academic year start, apply period template
2. **Holidays** → Load India Holidays (seeds 70 dates for 2026 automatically)
3. **Teachers** → Add all teachers with their subject associations
4. **Rooms** → Add classrooms, labs (Science Lab), field (PT Ground)
5. **Classes** → Add all divisions (Grade 6-A, 6-B, 7-A, 7-B...)
6. **Curriculum** → Load preset → select board + grade group → Apply
7. **Dashboard** → Generate Timetable (takes ~30–90 seconds)
8. **Timetable** → View by class/teacher/room, drag to adjust, use AI chat
9. **Absences** → When a teacher calls in sick, mark absent and apply substitutes in 30 seconds

---

## DB Tables
```
users, institutions, teachers, rooms, classes, subjects,
lessons, timetables, assignments, solve_jobs,
holidays, teacher_absences, substitute_assignments
```
Default: SQLite (`timely.db` in backend folder). Set `DATABASE_URL` env var for PostgreSQL.

---

## Running Tests
```bash
cd app/backend
C:\Users\spars\venv\Scripts\python.exe -m pytest tests/ -v
# 5 tests: feasibility, zero-clashes, unavailability, pinned lessons, infeasibility
```
