import { Navigate, Outlet } from 'react-router'
import { useApp } from '@/lib/store'

export function ProtectedRoute() {
  const { token } = useApp()
  if (!token) return <Navigate to="/login" replace />
  return <Outlet />
}
