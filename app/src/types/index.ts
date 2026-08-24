export interface Institution {
  id: string
  name: string
  type: 'school' | 'college' | 'office'
  days_per_week: number
  periods_per_day: number
  day_labels: string[]
  period_labels: string[]
  term_name: string
  academic_year_start?: string | null
  board?: string
  created_at: string
}

export interface Holiday {
  id: string
  institution_id: string
  date: string
  name: string
  type: 'national' | 'state' | 'school' | 'optional'
}

export interface TeacherAbsence {
  id: string
  teacher_id: string
  date: string
  reason: string
  institution_id: string
  created_at: string
}

export interface SubstituteSuggestion {
  assignment_id: string
  period: number
  subject_id: string
  class_id: string
  room_id: string
  candidates: { teacher_id: string; teacher_name: string; subjects: string[] }[]
}

export interface CurriculumPresetSubject {
  name: string
  room_type: string
  lessons_per_week: number
  color: string
}

export interface Teacher {
  id: string
  institution_id: string
  name: string
  email: string
  subjects: string[]
  max_per_day: number
  max_per_week: number
  unavailable: [number, number][]
  color: string
}

export interface Room {
  id: string
  institution_id: string
  name: string
  type: 'classroom' | 'lab' | 'field' | 'hall'
  capacity: number
  features: string[]
}

export interface Class {
  id: string
  institution_id: string
  name: string
  grade: string
  size: number
}

export interface Subject {
  id: string
  institution_id: string
  name: string
  room_type: 'classroom' | 'lab' | 'field' | 'hall'
  color: string
  lessons_per_week: number
  allow_double: boolean
}

export interface Lesson {
  id: string
  institution_id: string
  class_id: string
  subject_id: string
  teacher_id: string
  pinned: { day: number; period: number; room_id?: string } | null
}

export interface Assignment {
  id: string
  timetable_id: string
  lesson_id: string
  class_id: string
  subject_id: string
  teacher_id: string
  room_id: string
  day: number
  period: number
}

export interface Timetable {
  id: string
  institution_id: string
  name: string
  status: 'draft' | 'solving' | 'solved' | 'published' | 'failed'
  soft_score: number
  violations: Violation[]
  solve_time_s: number
  created_at: string
  published_at: string | null
  assignments?: Assignment[]
}

export interface Violation {
  type: string
  count: number
  weighted: number
  examples: Record<string, unknown>[]
}

export interface SolveJob {
  job_id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  progress: number
  result_status: string
  soft_score: number
  violations: Violation[]
  timetable_id: string | null
  error: string
  created_at: string
  finished_at: string | null
}

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: string
  institution_id: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: string
  role: string
  institution_id: string | null
}
