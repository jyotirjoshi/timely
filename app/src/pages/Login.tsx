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

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { setAuth } = useApp()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true)
    try {
      const data = await api.login(email, password)
      localStorage.setItem('timely_token', data.access_token)
      const me = await api.me()
      setAuth(data.access_token, me)
      toast.success('Welcome back!')
      navigate('/dashboard')
    } catch (err: unknown) { toast.error(err instanceof Error ? err.message : 'Login failed') }
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
          <CardHeader className="text-center"><CardTitle>Sign in</CardTitle><CardDescription>Enter your credentials to continue</CardDescription></CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5"><Label>Email</Label><Input type="email" placeholder="admin@college.edu" value={email} onChange={e => setEmail(e.target.value)} required /></div>
              <div className="space-y-1.5"><Label>Password</Label><Input type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required /></div>
              <Button type="submit" className="w-full" disabled={loading}>{loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}Sign in</Button>
            </form>
            <p className="text-center text-sm text-muted-foreground mt-4">No account? <Link to="/register" className="text-primary hover:underline font-medium">Create one</Link></p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
