import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Loader2, Zap, BookMarked, CheckCircle2, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api, presetApi } from '@/lib/api'
import type { Teacher, Class, Subject, Lesson, CurriculumPresetSubject } from '@/types'

interface Cell { lectures_per_week: number; teacher_id: string }
type Matrix = Record<string, Record<string, Cell>>
const BOARDS = ['CBSE','ICSE','Maharashtra State Board']
const GRADE_GROUPS = ['1-5','6-8','9-10','11-12']

export function CurriculumPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const navigate = useNavigate()
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [classes, setClasses] = useState<Class[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [matrix, setMatrix] = useState<Matrix>({})
  const [presetOpen, setPresetOpen] = useState(false)
  const [selBoard, setSelBoard] = useState('CBSE')
  const [selGrade, setSelGrade] = useState('6-8')
  const [presetSubjs, setPresetSubjs] = useState<CurriculumPresetSubject[]>([])
  const [presetLoading, setPresetLoading] = useState(false)
  const [presetApplying, setPresetApplying] = useState(false)
  const [totalPW, setTotalPW] = useState(0)
  const [generating, setGenerating] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobProgress, setJobProgress] = useState(0)

  const load = useCallback(async () => {
    if (!instId) return
    try {
      const [t,c,s,l] = await Promise.all([api.listTeachers(instId),api.listClasses(instId),api.listSubjects(instId),api.listLessons(instId)])
      setTeachers(t as Teacher[]); setClasses(c as Class[]); setSubjects(s as Subject[])
      const m: Matrix = {}
      for (const subj of s as Subject[]) { m[subj.id]={};  for (const cls of c as Class[]) m[subj.id][cls.id]={lectures_per_week:0,teacher_id:''} }
      for (const lesson of l as Lesson[]) {
        if (!m[lesson.subject_id]?.[lesson.class_id]) continue
        m[lesson.subject_id][lesson.class_id].lectures_per_week += 1
        if (!m[lesson.subject_id][lesson.class_id].teacher_id) m[lesson.subject_id][lesson.class_id].teacher_id = lesson.teacher_id
      }
      setMatrix(m)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }, [instId])
  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!jobId) return
    const iv = setInterval(async () => {
      try {
        const job = await api.getJob(jobId) as any
        setJobProgress(job.progress)
        if (job.status==='done') { clearInterval(iv); setGenerating(false); setJobId(null); toast.success(`Generated! (${job.result_status})`); if (job.timetable_id) navigate(`/timetables/${job.timetable_id}`) }
        else if (job.status==='failed') { clearInterval(iv); setGenerating(false); setJobId(null); toast.error('Failed: '+job.error) }
      } catch {}
    }, 1500)
    return () => clearInterval(iv)
  }, [jobId, navigate])

  useEffect(() => {
    if (!presetOpen) return
    const f = async () => {
      setPresetLoading(true)
      try { const d = await presetApi.get(selBoard, selGrade) as any; setPresetSubjs(d.subjects); setTotalPW(d.total_lessons_per_week) }
      catch { setPresetSubjs([]) }
      finally { setPresetLoading(false) }
    }
    f()
  }, [selBoard, selGrade, presetOpen])

  const setCell = (sid: string, cid: string, field: keyof Cell, val: number|string) =>
    setMatrix(m => ({ ...m, [sid]: { ...m[sid], [cid]: { ...m[sid]?.[cid], [field]: val } } }))

  const eligibleTeachers = () => teachers  // show all — assignment done in matrix

  const saveMatrix = async (): Promise<boolean> => {
    const batch: Omit<Lesson,'id'|'institution_id'>[] = []
    for (const subj of subjects) {
      for (const cls of classes) {
        const cell = matrix[subj.id]?.[cls.id]
        if (!cell || cell.lectures_per_week===0) continue
        if (!cell.teacher_id) { toast.error(`Assign faculty for ${subj.name} → ${cls.name}`); return false }
        for (let k=0; k<cell.lectures_per_week; k++) batch.push({ class_id:cls.id, subject_id:subj.id, teacher_id:cell.teacher_id, pinned:null })
      }
    }
    if (!batch.length) { toast.error('No lectures configured'); return false }
    try { await api.deleteAllLessons(instId); await api.bulkCreateLessons(instId, batch); return true }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Save failed'); return false }
  }

  const handleGenerate = async () => {
    setGenerating(true); setJobProgress(0)
    const ok = await saveMatrix()
    if (!ok) { setGenerating(false); return }
    try {
      const job = await api.startSolve({ institution_id:instId, timetable_name:`Timetable ${new Date().toLocaleDateString('en-IN')}`, time_limit_s:90 }) as any
      setJobId(job.job_id); toast.success('Saved — generating…')
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed'); setGenerating(false) }
  }

  const handleApplyPreset = async () => {
    setPresetApplying(true)
    try {
      const existing = new Set(subjects.map(s=>s.name.toLowerCase()))
      const newSubjs: Subject[] = []
      for (const ps of presetSubjs.filter(p => !existing.has(p.name.toLowerCase()))) {
        const s = await api.createSubject(instId, { name:ps.name, room_type:ps.room_type as Subject['room_type'], color:ps.color, lessons_per_week:ps.lessons_per_week, allow_double:false }) as Subject
        newSubjs.push(s)
      }
      const allSubjs = [...subjects, ...newSubjs]
      const newMatrix: Matrix = { ...matrix }
      for (const subj of allSubjs) {
        const preset = presetSubjs.find(p => p.name.toLowerCase()===subj.name.toLowerCase())
        const lpw = preset ? preset.lessons_per_week : subj.lessons_per_week
        if (!newMatrix[subj.id]) newMatrix[subj.id]={}
        for (const cls of classes) newMatrix[subj.id][cls.id]={ lectures_per_week:lpw, teacher_id:newMatrix[subj.id]?.[cls.id]?.teacher_id||'' }
      }
      setSubjects(allSubjs); setMatrix(newMatrix); setPresetOpen(false)
      toast.success(`Applied ${selBoard} preset — assign faculty then generate`)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setPresetApplying(false) }
  }

  const issues: string[] = []; let totalLessons = 0
  for (const subj of subjects) for (const cls of classes) {
    const cell = matrix[subj.id]?.[cls.id]
    if (!cell || cell.lectures_per_week===0) continue
    totalLessons += cell.lectures_per_week
    if (!cell.teacher_id) issues.push(`${subj.name} → ${cls.name}`)
  }
  const perDay = institution && classes.length > 0 ? totalLessons / (institution.days_per_week * classes.length) : 0

  if (!loading && (classes.length===0 || subjects.length===0)) return (
    <Layout title="Curriculum Matrix">
      <div className="p-8 max-w-lg mx-auto text-center space-y-4 pt-20">
        <AlertTriangle className="w-10 h-10 mx-auto text-amber-500" />
        <h2 className="text-lg font-semibold">Setup incomplete</h2>
        <p className="text-muted-foreground text-sm">You need at least one batch and one subject.</p>
        <div className="flex gap-3 justify-center flex-wrap">
          {classes.length===0 && <Button variant="outline" onClick={() => navigate('/classes')}>Add batches</Button>}
          {subjects.length===0 && <Button variant="outline" onClick={() => navigate('/subjects')}>Add subjects</Button>}
          <Button variant="outline" onClick={() => setPresetOpen(true)} className="gap-2"><BookMarked className="w-4 h-4" />Load preset</Button>
        </div>
      </div>
    </Layout>
  )

  return (
    <Layout title="Curriculum Matrix" subtitle={`${totalLessons} lectures/week · ${subjects.length} subjects · ${classes.length} batches`}
      actions={
        <div className="flex gap-2 flex-wrap items-center">
          <Button variant="outline" className="gap-2" onClick={() => setPresetOpen(true)}><BookMarked className="w-4 h-4" />Load preset</Button>
          <Button variant="outline" onClick={async () => { const ok = await saveMatrix(); if (ok) { toast.success('Saved'); await load() } }}>Save only</Button>
          <Button className="gap-2" onClick={handleGenerate} disabled={generating || issues.length>0 || totalLessons===0}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" />{jobProgress}%…</> : <><Zap className="w-4 h-4" />Save & Generate</>}
          </Button>
        </div>
      }>
      <div className="p-6 space-y-4">
        {generating && <Card className="border-primary/30 bg-primary/5"><CardContent className="py-3"><div className="flex items-center gap-3 mb-2"><Loader2 className="w-4 h-4 animate-spin text-primary" /><span className="text-sm font-medium">Generating…</span><span className="ml-auto text-sm text-muted-foreground">{jobProgress}%</span></div><Progress value={jobProgress} className="h-2" /></CardContent></Card>}
        {issues.length>0 && <Card className="border-amber-200 bg-amber-50"><CardContent className="py-3"><div className="flex items-start gap-2"><AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5" /><div><p className="text-sm font-medium text-amber-800">{issues.length} cell{issues.length>1?'s':''} need faculty</p><p className="text-xs text-amber-700 mt-0.5">{issues.slice(0,4).join(' · ')}{issues.length>4?` · +${issues.length-4} more`:''}</p></div></div></CardContent></Card>}

        {!loading && (
          <>
            <div className="flex gap-3 flex-wrap text-sm">
              {[['Total lec/week',totalLessons],['Avg/class/day',perDay.toFixed(1)],['Subjects',subjects.length],['Batches',classes.length]].map(([l,v]) => (
                <div key={l as string} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted"><span className="text-muted-foreground">{l}:</span><strong>{v}</strong></div>
              ))}
              {issues.length===0 && totalLessons>0 && <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-green-50 border border-green-200"><CheckCircle2 className="w-3.5 h-3.5 text-green-600" /><span className="text-green-700">Ready to generate</span></div>}
            </div>

            <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 text-sm text-blue-800">
              <strong>How to use:</strong> Set lectures/week per cell. Select faculty. Set 0 = subject not taught to that batch. Click <strong>Save & Generate</strong>.
            </div>

            <div className="rounded-lg border shadow-sm" style={{overflowX:'auto'}}>
              <table className="border-collapse bg-background" style={{minWidth:'100%'}}>
                <thead>
                  <tr className="bg-muted/60 border-b">
                    <th className="text-left px-4 py-3 text-sm font-semibold border-r whitespace-nowrap" style={{minWidth:200,position:'sticky',left:0,background:'hsl(var(--muted)/0.6)',zIndex:2}}>Subject</th>
                    {classes.map(cls => <th key={cls.id} className="px-3 py-3 text-center text-sm font-semibold border-r last:border-r-0" style={{minWidth:180}}><div>{cls.name}</div><div className="text-xs font-normal text-muted-foreground">{cls.size} students</div></th>)}
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((subj,si) => {
                    const bgRow = si%2===0 ? 'hsl(var(--background))' : 'hsl(var(--muted)/0.2)'
                    return (
                      <tr key={subj.id} className="border-b last:border-b-0">
                        <td className="px-4 py-3 border-r font-medium text-sm" style={{background:bgRow,position:'sticky',left:0,zIndex:1}}>
                          <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full flex-shrink-0" style={{backgroundColor:subj.color}} /><div><div className="whitespace-nowrap">{subj.name}</div><Badge variant="outline" className="text-[10px] px-1 py-0 h-4 mt-0.5">{subj.room_type}</Badge></div></div>
                        </td>
                        {classes.map(cls => {
                          const cell = matrix[subj.id]?.[cls.id] || {lectures_per_week:0,teacher_id:''}
                          const hasIssue = cell.lectures_per_week>0 && !cell.teacher_id
                          return (
                            <td key={cls.id} className="px-3 py-2 border-r last:border-r-0 align-top" style={{background:bgRow}}>
                              <div className="space-y-2" style={{minWidth:160}}>
                                <div className="flex items-center gap-2">
                                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">Lec/wk</span>
                                  <input type="number" min={0} max={12} value={cell.lectures_per_week}
                                    onChange={e => setCell(subj.id,cls.id,'lectures_per_week',Math.max(0,+e.target.value))}
                                    className="w-16 h-7 text-center text-sm border rounded-md px-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
                                </div>
                                {cell.lectures_per_week>0 && (
                                  <div className="space-y-0.5">
                                    <span className="text-[10px] text-muted-foreground">Faculty</span>
                                    <select value={cell.teacher_id} onChange={e => setCell(subj.id,cls.id,'teacher_id',e.target.value)}
                                      className={`w-full h-8 text-xs border rounded-md px-2 bg-background focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer ${hasIssue?'border-amber-400 bg-amber-50':'border-input'}`}>
                                      <option value="">— assign faculty —</option>
                                      {eligibleTeachers().map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                                    </select>
                                    {hasIssue && <p className="text-[10px] text-amber-600">⚠ Assign faculty</p>}
                                  </div>
                                )}
                                {cell.lectures_per_week===0 && <p className="text-[10px] text-muted-foreground/40 text-center italic">not taught</p>}
                              </div>
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
                <tfoot>
                  <tr className="bg-muted/60 border-t-2">
                    <td className="px-4 py-2 text-xs font-semibold border-r" style={{position:'sticky',left:0,background:'hsl(var(--muted)/0.6)',zIndex:1}}>Total lec/week</td>
                    {classes.map(cls => {
                      const tot = subjects.reduce((s,subj) => s+(matrix[subj.id]?.[cls.id]?.lectures_per_week||0),0)
                      const pd = institution ? (tot/institution.days_per_week).toFixed(1) : '—'
                      return <td key={cls.id} className="px-3 py-2 text-center border-r last:border-r-0"><div className="font-semibold text-sm">{tot}</div><div className="text-[10px] text-muted-foreground">{pd}/day</div></td>
                    })}
                  </tr>
                </tfoot>
              </table>
            </div>
          </>
        )}

        {loading && <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>}
      </div>

      <Dialog open={presetOpen} onOpenChange={setPresetOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>Load Curriculum Preset</DialogTitle><DialogDescription>Pre-fills lectures/week. You still assign faculty.</DialogDescription></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5"><Label>Board</Label>
                <Select value={selBoard} onValueChange={setSelBoard}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{BOARDS.map(b => <SelectItem key={b} value={b}>{b}</SelectItem>)}</SelectContent></Select>
              </div>
              <div className="space-y-1.5"><Label>Grade group</Label>
                <Select value={selGrade} onValueChange={setSelGrade}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{GRADE_GROUPS.map(g => <SelectItem key={g} value={g}>Classes {g}</SelectItem>)}</SelectContent></Select>
              </div>
            </div>
            <div className="rounded-lg border max-h-64 overflow-y-auto">
              {presetLoading ? <div className="flex justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div> : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 sticky top-0"><tr><th className="text-left p-2 font-medium">Subject</th><th className="text-left p-2 font-medium">Room</th><th className="text-right p-2 font-medium">Lec/week</th></tr></thead>
                  <tbody>
                    {presetSubjs.map((s,i) => <tr key={i} className="border-t"><td className="p-2"><div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full" style={{backgroundColor:s.color}} />{s.name}</div></td><td className="p-2 text-muted-foreground">{s.room_type}</td><td className="p-2 text-right font-medium">{s.lessons_per_week}×</td></tr>)}
                    <tr className="border-t bg-muted/30 font-semibold"><td className="p-2" colSpan={2}>Total/class/week</td><td className="p-2 text-right">{totalPW}</td></tr>
                  </tbody>
                </table>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPresetOpen(false)}>Cancel</Button>
            <Button onClick={handleApplyPreset} disabled={presetApplying || !presetSubjs.length}>{presetApplying && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}Apply preset</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  )
}
