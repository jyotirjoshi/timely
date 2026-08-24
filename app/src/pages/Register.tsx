import { useState } from 'react'
import { useNavigate, Link } from 'react-router'
import { toast } from 'sonner'
import { Clock, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useApp } from '@/lib/store'
import { api } from '@/lib/api'

export function RegisterPage() {
  const [form, setForm] = useState({ email: '', password: '', full_name: '', institution_name: '' })
  const [loading, setLoading] = useState(false)
  const { setAuth } = useApp()
  const navigate = useNavigate()

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true)
    try {
      const data = await api.register(form)
      localStorage.setItem('timely_token', data.access_token)
      const me = await api.me()
      setAuth(data.access_token, me)
      toast.success('Account created! Welcome to Timely.')
      navigate('/dashboard')
    } catch (err: unknown) { toast.error(err instanceof Error ? err.message : 'Registration failed') }
    finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center"><Clock className="w-5 h-5 text-primary-foreground" /></div>
          <span className="text-2xl font-bold">Timely</span>
        </div>
        <Card>
          <CardHeader className="text-center"><CardTitle>Create account</CardTitle><CardDescription>Set up your institution and start scheduling</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5"><Label>Your name</Label><Input placeholder="Dr. Jane Smith" value={form.full_name} onChange={set('full_name')} required /></div>
              <div className="space-y-1.5"><Label>Email</Label><Input type="email" placeholder="jane@college.edu" value={form.email} onChange={set('email')} required /></div>
              <div className="space-y-1.5"><Label>Password</Label><Input type="password" placeholder="Min. 6 characters" value={form.password} onChange={set('password')} minLength={6} required /></div>
              <div className="space-y-1.5"><Label>Institution name</Label><Input placeholder="VJTI Mumbai / Springfield High" value={form.institution_name} onChange={set('institution_name')} required /></div>
              <Button type="submit" className="w-full" disabled={loading}>{loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}Create account</Button>
            </form>
            <p className="text-center text-sm text-muted-foreground mt-4">Already have an account? <Link to="/login" className="text-primary hover:underline font-medium">Sign in</Link></p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
