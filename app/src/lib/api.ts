const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getToken(): string | null { return localStorage.getItem('timely_token') }

async function request<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE}${path}`)
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v))
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url.toString(), { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { const err = await res.json(); detail = err.detail || JSON.stringify(err); if (typeof detail === 'object') detail = JSON.stringify(detail) } catch {}
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  register: (body: { email: string; password: string; full_name: string; institution_name: string }) =>
    request<any>('POST', '/api/auth/register', body),
  login: (email: string, password: string) => {
    const form = new URLSearchParams(); form.set('username', email); form.set('password', password)
    return fetch(`${BASE}/api/auth/login`, { method: 'POST', body: form }).then(async r => {
      if (!r.ok) { const err = await r.json().catch(() => ({})); throw new Error(err.detail || 'Login failed') }
      return r.json()
    })
  },
  me: () => request<any>('GET', '/api/auth/me'),
  getInstitution: (id: string) => request<import('@/types').Institution>('GET', `/api/institutions/${id}`),
  updateInstitution: (id: string, body: any) => request<import('@/types').Institution>('PATCH', `/api/institutions/${id}`, body),
  listTeachers: (iid: string) => request<import('@/types').Teacher[]>('GET', '/api/teachers', undefined, { institution_id: iid }),
  createTeacher: (iid: string, body: any) => request<import('@/types').Teacher>('POST', '/api/teachers', body, { institution_id: iid }),
  updateTeacher: (id: string, body: any) => request<import('@/types').Teacher>('PATCH', `/api/teachers/${id}`, body),
  deleteTeacher: (id: string) => request<void>('DELETE', `/api/teachers/${id}`),
  listRooms: (iid: string) => request<import('@/types').Room[]>('GET', '/api/rooms', undefined, { institution_id: iid }),
  createRoom: (iid: string, body: any) => request<import('@/types').Room>('POST', '/api/rooms', body, { institution_id: iid }),
  updateRoom: (id: string, body: any) => request<import('@/types').Room>('PATCH', `/api/rooms/${id}`, body),
  deleteRoom: (id: string) => request<void>('DELETE', `/api/rooms/${id}`),
  listClasses: (iid: string) => request<import('@/types').Class[]>('GET', '/api/classes', undefined, { institution_id: iid }),
  createClass: (iid: string, body: any) => request<import('@/types').Class>('POST', '/api/classes', body, { institution_id: iid }),
  updateClass: (id: string, body: any) => request<import('@/types').Class>('PATCH', `/api/classes/${id}`, body),
  deleteClass: (id: string) => request<void>('DELETE', `/api/classes/${id}`),
  listSubjects: (iid: string) => request<import('@/types').Subject[]>('GET', '/api/subjects', undefined, { institution_id: iid }),
  createSubject: (iid: string, body: any) => request<import('@/types').Subject>('POST', '/api/subjects', body, { institution_id: iid }),
  updateSubject: (id: string, body: any) => request<import('@/types').Subject>('PATCH', `/api/subjects/${id}`, body),
  deleteSubject: (id: string) => request<void>('DELETE', `/api/subjects/${id}`),
  listLessons: (iid: string) => request<import('@/types').Lesson[]>('GET', '/api/lessons', undefined, { institution_id: iid }),
  createLesson: (iid: string, body: any) => request<import('@/types').Lesson>('POST', '/api/lessons', body, { institution_id: iid }),
  bulkCreateLessons: (iid: string, body: any[]) => request<import('@/types').Lesson[]>('POST', '/api/lessons/bulk', body, { institution_id: iid }),
  deleteLesson: (id: string) => request<void>('DELETE', `/api/lessons/${id}`),
  deleteAllLessons: (iid: string) => request<void>('DELETE', '/api/lessons', undefined, { institution_id: iid }),
  listTimetables: (iid: string) => request<import('@/types').Timetable[]>('GET', '/api/timetables', undefined, { institution_id: iid }),
  getTimetable: (id: string) => request<import('@/types').Timetable>('GET', `/api/timetables/${id}`),
  publishTimetable: (id: string) => request<import('@/types').Timetable>('PATCH', `/api/timetables/${id}/publish`),
  unpublishTimetable: (id: string) => request<import('@/types').Timetable>('PATCH', `/api/timetables/${id}/unpublish`),
  deleteTimetable: (id: string) => request<void>('DELETE', `/api/timetables/${id}`),
  updateAssignment: (tid: string, aid: string, body: any) => request<import('@/types').Assignment>('PATCH', `/api/timetables/${tid}/assignments/${aid}`, body),
  startSolve: (body: any) => request<any>('POST', '/api/solve', body),
  getJob: (jobId: string) => request<import('@/types').SolveJob>('GET', `/api/solve/${jobId}`),
  chat: (body: any) => request<any>('POST', '/api/agent/chat', body),
}

export const holidayApi = {
  list: (iid: string) => request<import('@/types').Holiday[]>('GET', '/api/holidays', undefined, { institution_id: iid }),
  create: (iid: string, body: any) => request<import('@/types').Holiday>('POST', '/api/holidays', body, { institution_id: iid }),
  delete: (id: string) => request<void>('DELETE', `/api/holidays/${id}`),
  seedIndia: (iid: string, year = 2026) => request<any>('POST', '/api/holidays/seed-india', undefined, { institution_id: iid, year: String(year) }),
  clear: (iid: string) => request<void>('DELETE', '/api/holidays', undefined, { institution_id: iid }),
}

export const presetApi = {
  list: () => request<any[]>('GET', '/api/presets'),
  get: (board: string, gradeGroup: string) => request<any>('GET', `/api/presets/${encodeURIComponent(board)}/${encodeURIComponent(gradeGroup)}`),
}

export const agentApi = {
  applyPlan: (timetableId: string, changes: any[]) =>
    request<any>('POST', '/api/agent/apply-plan', { timetable_id: timetableId, changes }),
}
