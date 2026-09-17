import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Loader2, CalendarDays, Trash2, Eye, Globe, GlobeLock, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api } from '@/lib/api'
import type { Timetable, SolveJob } from '@/types'

export function TimetablesListPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const navigate = useNavigate()
  const [timetables, setTimetables] = useState<Timetable[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)

  const load = async () => {
    if (!instId) return
    try { setTimetables(await api.listTimetables(instId) as Timetable[]) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [instId])

  useEffect(() => {
    if (!jobId) return
    const iv = setInterval(async () => {
      try {
        const job = await api.getJob(jobId) as SolveJob
        setProgress(job.progress)
        if (job.status === 'done') { clearInterval(iv); setGenerating(false); setJobId(null); toast.success(`Generated! (${job.result_status})`); load() }
        else if (job.status === 'failed') { clearInterval(iv); setGenerating(false); setJobId(null); toast.error('Failed: ' + job.error) }
      } catch {}
    }, 1500)
    return () => clearInterval(iv)
  }, [jobId])

  const handleGenerate = async () => {
    if (!instId) return
    setGenerating(true); setProgress(0)
    try {
      const job = await api.startSolve({ institution_id: instId, time_limit_s: 90, timetable_name: `Timetable ${new Date().toLocaleDateString('en-IN')}` }) as any
      setJobId(job.job_id)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed'); setGenerating(false) }
  }

  const handlePublish = async (tt: Timetable) => {
    try {
      if (tt.status === 'published') { const u = await api.unpublishTimetable(tt.id); setTimetables(ts => ts.map(t => t.id===tt.id ? u as Timetable : t)); toast.success('Unpublished') }
      else { const u = await api.publishTimetable(tt.id); setTimetables(ts => ts.map(t => t.id===tt.id ? u as Timetable : t)); toast.success('Published') }
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleDelete = async (tt: Timetable) => {
    if (!confirm(`Delete "${tt.name}"?`)) return
    try { await api.deleteTimetable(tt.id); setTimetables(ts => ts.filter(t => t.id!==tt.id)); toast.success('Deleted') }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const statusColors: Record<string,string> = { solved:'bg-green-100 text-green-700', published:'bg-blue-100 text-blue-700', failed:'bg-red-100 text-red-700', draft:'bg-gray-100 text-gray-600' }

  return (
    <Layout title="Timetables" subtitle="All generated versions"
      actions={<Button onClick={handleGenerate} disabled={generating} className="gap-2">{generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}{generating ? `Generating ${progress}%` : 'Generate new'}</Button>}>
      <div className="p-8 space-y-4">
        {generating && <Card className="border-primary/30 bg-primary/5"><CardContent className="py-4"><div className="flex items-center gap-3 mb-2"><Loader2 className="w-4 h-4 animate-spin text-primary" /><span className="text-sm font-medium">Generating…</span><span className="ml-auto text-sm text-muted-foreground">{progress}%</span></div><Progress value={progress} className="h-2" /></CardContent></Card>}
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
          : timetables.length === 0 ? (
            <div className="text-center py-20 text-muted-foreground">
              <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No timetables yet.</p>
              <Button onClick={handleGenerate} className="mt-4" disabled={generating}>Generate first timetable</Button>
            </div>
          ) : timetables.map(tt => (
            <Card key={tt.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1"><h3 className="font-semibold truncate">{tt.name}</h3><Badge className={statusColors[tt.status]||''}>{tt.status}</Badge></div>
                    <p className="text-sm text-muted-foreground">Score: {tt.soft_score} · Solve: {tt.solve_time_s}s · {new Date(tt.created_at).toLocaleDateString('en-IN')}{tt.published_at && ` · Published ${new Date(tt.published_at).toLocaleDateString('en-IN')}`}</p>
                    {tt.violations.length > 0 && <p className="text-xs text-amber-600 mt-1">{tt.violations.length} soft violation type{tt.violations.length!==1?'s':''}</p>}
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button size="sm" variant="outline" className="gap-1.5" onClick={() => navigate(`/timetables/${tt.id}`)}><Eye className="w-3.5 h-3.5" />View</Button>
                    {tt.status !== 'failed' && <Button size="sm" variant="outline" className="gap-1.5" onClick={() => handlePublish(tt)}>{tt.status==='published' ? <><GlobeLock className="w-3.5 h-3.5" />Unpublish</> : <><Globe className="w-3.5 h-3.5" />Publish</>}</Button>}
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => handleDelete(tt)}><Trash2 className="w-3.5 h-3.5" /></Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
      </div>
    </Layout>
  )
}
