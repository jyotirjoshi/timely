import { useState, type ReactNode } from 'react'
import { AppContext, type AppState } from '@/lib/store'
import type { AuthUser, Institution } from '@/types'

function safeParse<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw) as T
  } catch {
    localStorage.removeItem(key)
    return null
  }
}

function sanitizeInstitution(inst: Partial<Institution> | null): Institution | null {
  if (!inst || typeof inst !== 'object') return null
  return {
    id: inst.id ?? '',
    name: inst.name ?? '',
    type: inst.type ?? 'college',
    days_per_week: Number(inst.days_per_week) || 5,
    periods_per_day: Number(inst.periods_per_day) || 7,
    day_labels: Array.isArray(inst.day_labels) ? inst.day_labels : ['Mon','Tue','Wed','Thu','Fri'],
    period_labels: Array.isArray(inst.period_labels) ? inst.period_labels : [],
    term_name: inst.term_name ?? '',
    academic_year_start: (inst as any).academic_year_start ?? null,
    board: (inst as any).board ?? '',
    created_at: inst.created_at ?? '',
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('timely_token'))
  const [user, setUser] = useState<AuthUser | null>(() => safeParse<AuthUser>('timely_user'))
  const [institution, setInstitutionState] = useState<Institution | null>(
    () => sanitizeInstitution(safeParse<Partial<Institution>>('timely_institution'))
  )

  const setAuth = (t: string, u: AuthUser) => {
    localStorage.setItem('timely_token', t)
    localStorage.setItem('timely_user', JSON.stringify(u))
    setToken(t)
    setUser(u)
  }

  const setInstitution = (inst: Institution) => {
    const safe = sanitizeInstitution(inst)!
    localStorage.setItem('timely_institution', JSON.stringify(safe))
    setInstitutionState(safe)
  }

  const logout = () => {
    ['timely_token','timely_user','timely_institution'].forEach(k => localStorage.removeItem(k))
    setToken(null); setUser(null); setInstitutionState(null)
  }

  const value: AppState = { token, user, institution, setAuth, setInstitution, logout }
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
