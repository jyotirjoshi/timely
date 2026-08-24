import { createContext, useContext } from 'react'
import type { AuthUser, Institution } from '@/types'

export interface AppState {
  token: string | null
  user: AuthUser | null
  institution: Institution | null
  setAuth: (token: string, user: AuthUser) => void
  setInstitution: (inst: Institution) => void
  logout: () => void
}

export const AppContext = createContext<AppState>({
  token: null,
  user: null,
  institution: null,
  setAuth: () => {},
  setInstitution: () => {},
  logout: () => {},
})

export const useApp = () => useContext(AppContext)
