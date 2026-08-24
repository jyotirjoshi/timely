import { useNavigate } from 'react-router'
import { Clock, Zap, BrainCircuit, Users, Shield, ArrowRight, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export function LandingPage() {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b sticky top-0 bg-background/95 backdrop-blur z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center"><Clock className="w-4 h-4 text-primary-foreground" /></div>
            <span className="font-bold text-xl">Timely</span>
          </div>
          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => navigate('/login')}>Sign in</Button>
            <Button onClick={() => navigate('/register')}>Get started</Button>
          </div>
        </div>
      </nav>
      <section className="max-w-6xl mx-auto px-6 py-24 text-center">
        <Badge variant="secondary" className="mb-6">AI-powered timetabling for colleges</Badge>
        <h1 className="text-5xl font-extrabold tracking-tight mb-6 leading-tight">Automated timetabling<br />for colleges & schools</h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
          Generate conflict-free timetables in minutes with OR-Tools CP-SAT. Manage teacher absences, substitutions, and schedule changes through AI chat.
        </p>
        <div className="flex gap-4 justify-center">
          <Button size="lg" onClick={() => navigate('/register')} className="gap-2">Start for free <ArrowRight className="w-4 h-4" /></Button>
          <Button size="lg" variant="outline" onClick={() => navigate('/login')}>Sign in</Button>
        </div>
      </section>
      <section className="bg-muted/50 py-20">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Everything you need</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Zap, title: 'Auto-generate', desc: 'OR-Tools CP-SAT solves hundreds of constraints instantly.' },
              { icon: BrainCircuit, title: 'AI assistant', desc: '"Prof. Sharma is absent Monday" — AI handles substitutes and reschedules automatically.' },
              { icon: Users, title: 'Multi-role', desc: 'Admins, faculty, students — separate views for everyone.' },
              { icon: Shield, title: 'Conflict-free', desc: 'No double-booked teachers, rooms, or classes — guaranteed.' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="bg-background rounded-xl p-6 border shadow-sm">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4"><Icon className="w-5 h-5 text-primary" /></div>
                <h3 className="font-semibold mb-2">{title}</h3>
                <p className="text-sm text-muted-foreground">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center mb-12">How it works</h2>
        <div className="max-w-lg mx-auto space-y-4">
          {['Add faculty, rooms, batches & subjects','Set lectures/week per subject per batch','Click Generate — conflict-free timetable in minutes','Use AI chat to handle absences, view schedules, resolve conflicts'].map((step, i) => (
            <div key={i} className="flex items-start gap-4">
              <div className="w-7 h-7 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold flex-shrink-0 mt-0.5">{i+1}</div>
              <div className="flex items-center gap-2 pt-1"><CheckCircle2 className="w-4 h-4 text-green-500 flex-shrink-0" /><p className="text-base">{step}</p></div>
            </div>
          ))}
        </div>
        <div className="text-center mt-12"><Button size="lg" onClick={() => navigate('/register')}>Create your institution →</Button></div>
      </section>
      <footer className="border-t py-8 text-center text-sm text-muted-foreground">© 2026 Timely. Built with OR-Tools CP-SAT + Supabase.</footer>
    </div>
  )
}
