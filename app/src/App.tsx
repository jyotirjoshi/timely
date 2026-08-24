import { Component, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router'
import { AppProvider } from '@/providers/AppProvider'
import { Toaster } from '@/components/ui/sonner'
import { AIChat } from '@/components/AIChat'
import { LandingPage } from '@/pages/Landing'
import { LoginPage } from '@/pages/Login'
import { RegisterPage } from '@/pages/Register'
import { DashboardPage } from '@/pages/Dashboard'
import { TeachersPage } from '@/pages/Teachers'
import { RoomsPage } from '@/pages/Rooms'
import { ClassesPage } from '@/pages/Classes'
import { SubjectsPage } from '@/pages/Subjects'
import { CurriculumPage } from '@/pages/Curriculum'
import { TimetablePage } from '@/pages/Timetable'
import { TimetablesListPage } from '@/pages/TimetablesList'
import { HolidaysPage } from '@/pages/Holidays'
import { ProtectedRoute } from '@/components/ProtectedRoute'

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) return (
      <div className="min-h-screen flex items-center justify-center p-8 bg-background">
        <div className="max-w-lg w-full space-y-4">
          <h1 className="text-2xl font-bold text-destructive">Something went wrong</h1>
          <p className="text-muted-foreground text-sm">{this.state.error.message}</p>
          <div className="bg-muted rounded p-3 text-xs font-mono overflow-auto max-h-40">{this.state.error.stack}</div>
          <div className="flex gap-3">
            <button className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm"
              onClick={() => { localStorage.removeItem('timely_institution'); window.location.href = '/dashboard' }}>
              Clear cache &amp; reload
            </button>
            <button className="px-4 py-2 border rounded text-sm" onClick={() => this.setState({ error: null })}>Try again</button>
          </div>
        </div>
      </div>
    )
    return this.props.children
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/teachers" element={<TeachersPage />} />
            <Route path="/rooms" element={<RoomsPage />} />
            <Route path="/classes" element={<ClassesPage />} />
            <Route path="/subjects" element={<SubjectsPage />} />
            <Route path="/curriculum" element={<CurriculumPage />} />
            <Route path="/timetables" element={<TimetablesListPage />} />
            <Route path="/timetables/:id" element={<TimetablePage />} />
            <Route path="/holidays" element={<HolidaysPage />} />
            <Route path="/settings" element={<Navigate to="/dashboard" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster richColors position="top-right" />
        <AIChat />
      </AppProvider>
    </ErrorBoundary>
  )
}
