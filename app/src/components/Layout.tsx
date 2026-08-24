import { NavLink, useNavigate } from 'react-router'
import { useApp } from '@/lib/store'
import { cn } from '@/lib/utils'
import { LayoutDashboard, Users, DoorOpen, BookOpen, GraduationCap, CalendarDays, List, LogOut, Clock, ChevronRight, Flag } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { ReactNode } from 'react'

const NAV = [
  { to: '/dashboard',  label: 'Dashboard',    icon: LayoutDashboard },
  { to: '/teachers',   label: 'Faculty',      icon: Users },
  { to: '/rooms',      label: 'Rooms & Labs', icon: DoorOpen },
  { to: '/classes',    label: 'Batches',      icon: GraduationCap },
  { to: '/subjects',   label: 'Subjects',     icon: BookOpen },
  { to: '/curriculum', label: 'Curriculum',   icon: CalendarDays },
  { to: '/timetables', label: 'Timetables',   icon: List },
  { to: '/holidays',   label: 'Holidays',     icon: Flag },
]

interface LayoutProps { children: ReactNode; title?: string; subtitle?: string; actions?: ReactNode }

export function Layout({ children, title, subtitle, actions }: LayoutProps) {
  const { user, institution, logout } = useApp()
  const navigate = useNavigate()

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <aside className="w-64 flex-shrink-0 border-r bg-sidebar flex flex-col">
        <div className="flex items-center gap-2 px-6 py-5 border-b border-sidebar-border">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Clock className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <span className="font-bold text-sidebar-foreground">Timely</span>
            <p className="text-[10px] text-muted-foreground leading-none mt-0.5">{institution?.term_name || 'Timetabling'}</p>
          </div>
        </div>
        {institution && (
          <div className="px-4 py-3 border-b border-sidebar-border">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1">Institution</p>
            <p className="text-sm font-medium text-sidebar-foreground truncate">{institution.name}</p>
            <Badge variant="secondary" className="mt-1 text-[10px]">{institution.type}</Badge>
          </div>
        )}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}>
              {({ isActive }) => (
                <span className={cn('flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer',
                  isActive ? 'bg-sidebar-primary text-sidebar-primary-foreground font-medium' : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground')}>
                  <Icon className="w-4 h-4 flex-shrink-0" />{label}
                  {isActive && <ChevronRight className="w-3 h-3 ml-auto" />}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-sidebar-border">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
              <span className="text-xs font-bold text-primary">{user?.full_name?.[0] || user?.email?.[0] || '?'}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-sidebar-foreground truncate">{user?.full_name || user?.email}</p>
              <p className="text-[11px] text-muted-foreground capitalize">{user?.role}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-muted-foreground" onClick={() => { logout(); navigate('/login') }}>
            <LogOut className="w-3.5 h-3.5" />Sign out
          </Button>
        </div>
      </aside>
      <div className="flex-1 flex flex-col overflow-hidden">
        {(title || actions) && (
          <header className="flex-shrink-0 border-b px-8 py-5 flex items-center justify-between bg-background">
            <div>{title && <h1 className="text-2xl font-bold">{title}</h1>}{subtitle && <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>}</div>
            {actions && <div className="flex items-center gap-3">{actions}</div>}
          </header>
        )}
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
