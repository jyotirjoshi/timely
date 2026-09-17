import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Users, DoorOpen, GraduationCap, BookOpen, CalendarDays, Plus, ArrowRight, Loader2, Zap, Save, Clock, FlaskConical, Coffee, Trash2, Settings2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api } from '@/lib/api'
import type { Teacher, Room, Class, Subject, Timetable, Institution, SolveJob } from '@/types'

function timeToMins(t: string) { if (!t||!t.includes(':')) return 0; const [h,m]=t.split(':').map(Number); return isNaN(h)||isNaN(m)?0:h*60+m }
function minsToTime(n: number) { const h=Math.floor(Math.max(0,n)/60)%24; const m=Math.max(0,n)%60; return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}` }
function fmt12(t: string) { const mins=timeToMins(t); const h24=Math.floor(mins/60); const m=mins%60; const ap=h24<12?'AM':'PM'; const h12=h24%12||12; return `${h12}:${String(m).padStart(2,'0')} ${ap}` }

interface BreakCfg { id: number; label: string; after_lecture: number; duration_mins: number }
interface PeriodSlot { label: string; period_num: number; is_break?: boolean; break_label?: string }

function buildSchedule(start: string, end: string, lec: number, breaks: BreakCfg[], n: number): PeriodSlot[] {
  const slots: PeriodSlot[] = []; let cur=timeToMins(start); const end_m=timeToMins(end); const dur=Math.max(15,lec||55)
  for (let p=1; p<=n; p++) {
    if (cur>=end_m) break
    const e=cur+dur; slots.push({ label:`${fmt12(minsToTime(cur))}–${fmt12(minsToTime(e))}`, period_num:p }); cur=e
    const brk=breaks.find(b=>b.after_lecture===p)
    if (brk&&brk.duration_mins>0) { const be=cur+brk.duration_mins; slots.push({ label:`${fmt12(minsToTime(cur))}–${fmt12(minsToTime(be))} (${brk.label})`, period_num:0, is_break:true, break_label:brk.label }); cur=be }
  }
  return slots
}

interface Stats { teachers:number; rooms:number; classes:number; subjects:number; lessons:number }

export function DashboardPage() {
  const { user, institution, setInstitution } = useApp()
  const navigate = useNavigate()
  const instId = institution?.id || user?.institution_id
  const [stats, setStats] = useState<Stats>({ teachers:0,rooms:0,classes:0,subjects:0,lessons:0 })
  const [timetables, setTimetables] = useState<Timetable[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [jobId, setJobId] = useState<string|null>(null)
  const [jobProgress, setJobProgress] = useState(0)
  const [savingInst, setSavingInst] = useState(false)
  const [form, setForm] = useState({ name:'',type:'college',days_per_week:5,periods_per_day:8,day_labels:'Mon,Tue,Wed,Thu,Fri',period_labels:'',term_name:'',academic_year_start:'',board:'' })
  const [timing, setTiming] = useState({ college_start:'09:00',college_end:'17:00',lecture_duration:55,lab_duration:110, breaks:[{id:1,label:'Short Break',after_lecture:2,duration_mins:10},{id:2,label:'Lunch Break',after_lecture:5,duration_mins:30}] as BreakCfg[] })
  const [nextBrkId, setNextBrkId] = useState(3)
  const [schedule, setSchedule] = useState<PeriodSlot[]>([])

  useEffect(() => {
    if (!institution) return
    setForm({ name:institution.name??'', type:institution.type??'college', days_per_week:institution.days_per_week??5, periods_per_day:institution.periods_per_day??8, day_labels:(institution.day_labels??[]).join(','), period_labels:(institution.period_labels??[]).join(','), term_name:institution.term_name??'', academic_year_start:(institution as any).academic_year_start??'', board:(institution as any).board??'' })
  }, [institution])

  useEffect(() => { try { setSchedule(buildSchedule(timing.college_start,timing.college_end,timing.lecture_duration,timing.breaks,form.periods_per_day)) } catch { setSchedule([]) } }, [timing,form.periods_per_day])

  useEffect(() => {
    if (!instId) { setLoading(false); return }
    const load = async () => {
      try {
        const [inst,t,r,c,s,l,tts]=await Promise.all([api.getInstitution(instId),api.listTeachers(instId),api.listRooms(instId),api.listClasses(instId),api.listSubjects(instId),api.listLessons(instId),api.listTimetables(instId)])
        setInstitution(inst as Institution)
        setStats({ teachers:(t as Teacher[]).length,rooms:(r as Room[]).length,classes:(c as Class[]).length,subjects:(s as Subject[]).length,lessons:(l as unknown[]).length })
        setTimetables(tts as Timetable[])
      } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
      finally { setLoading(false) }
    }
    load()
  }, [instId])

  useEffect(() => {
    if (!jobId) return
    const iv=setInterval(async () => {
      try {
        const job=await api.getJob(jobId) as SolveJob
        setJobProgress(job.progress)
        if (job.status==='done') { clearInterval(iv); setGenerating(false); setJobId(null); toast.success(`Generated! (${job.result_status})`); if (job.timetable_id) navigate(`/timetables/${job.timetable_id}`); else { const tts=await api.listTimetables(instId!); setTimetables(tts as Timetable[]) } }
        else if (job.status==='failed') { clearInterval(iv); setGenerating(false); setJobId(null); toast.error('Failed: '+job.error) }
      } catch {}
    }, 1500)
    return () => clearInterval(iv)
  }, [jobId])

  const handleGenerate = async () => {
    if (!instId) return; if (stats.lessons===0) { toast.error('Set up curriculum first.'); return }
    setGenerating(true); setJobProgress(0)
    try { const job=await api.startSolve({ institution_id:instId, timetable_name:`Timetable ${new Date().toLocaleDateString('en-IN')}`, time_limit_s:90 }) as any; setJobId(job.job_id) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed'); setGenerating(false) }
  }

  const handleSaveInst = async () => {
    if (!instId) return; setSavingInst(true)
    try {
      const updated=await api.updateInstitution(instId, { name:form.name, type:form.type as Institution['type'], days_per_week:form.days_per_week, periods_per_day:form.periods_per_day, day_labels:form.day_labels.split(',').map(s=>s.trim()).filter(Boolean), period_labels:form.period_labels.split(',').map(s=>s.trim()).filter(Boolean), term_name:form.term_name, academic_year_start:form.academic_year_start||null, board:form.board } as any)
      setInstitution(updated as Institution); toast.success('Saved')
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Save failed') }
    finally { setSavingInst(false) }
  }

  const applySchedule = () => { const lec=schedule.filter(s=>!s.is_break); setForm(f=>({ ...f, period_labels:lec.map(s=>s.label).join(','), periods_per_day:lec.length })); toast.success(`${lec.length} period times applied — click Save`) }
  const addBreak = () => { const id=nextBrkId; setNextBrkId(id+1); setTiming(t=>({ ...t, breaks:[...t.breaks,{id,label:'Break',after_lecture:Math.ceil(form.periods_per_day/2),duration_mins:15}] })) }
  const updateBreak = (id: number, field: keyof BreakCfg, val: string|number) => setTiming(t=>({ ...t, breaks:t.breaks.map(b=>b.id===id ? {...b,[field]:val} : b) }))
  const removeBreak = (id: number) => setTiming(t=>({ ...t, breaks:t.breaks.filter(b=>b.id!==id) }))

  const TEMPLATES = [
    { label:'Engg 8 lec Mon–Fri', days:5,periods:8,day_labels:'Mon,Tue,Wed,Thu,Fri', start:'09:00',end:'17:00',lec:55,lab:110, breaks:[{id:1,label:'Short Break',after_lecture:2,duration_mins:10},{id:2,label:'Lunch Break',after_lecture:5,duration_mins:30}] },
    { label:'Engg 6 lec Mon–Sat', days:6,periods:6,day_labels:'Mon,Tue,Wed,Thu,Fri,Sat', start:'09:00',end:'16:00',lec:55,lab:110, breaks:[{id:1,label:'Lunch Break',after_lecture:3,duration_mins:30}] },
    { label:'CBSE 8 periods', days:5,periods:8,day_labels:'Mon,Tue,Wed,Thu,Fri', start:'08:00',end:'14:00',lec:45,lab:90, breaks:[{id:1,label:'Short Break',after_lecture:2,duration_mins:10},{id:2,label:'Lunch',after_lecture:5,duration_mins:30}] },
    { label:'SSC 6 + Sat', days:6,periods:6,day_labels:'Mon,Tue,Wed,Thu,Fri,Sat', start:'07:30',end:'13:30',lec:45,lab:90, breaks:[{id:1,label:'Break',after_lecture:3,duration_mins:20}] },
  ] as const

  const scol=(s:string) => ({solved:'bg-green-100 text-green-700',published:'bg-blue-100 text-blue-700',failed:'bg-red-100 text-red-700',draft:'bg-gray-100 text-gray-600'}[s]||'bg-gray-100 text-gray-600')
  const STAT_CARDS = [{label:'Faculty',value:stats.teachers,icon:Users,href:'/teachers'},{label:'Rooms',value:stats.rooms,icon:DoorOpen,href:'/rooms'},{label:'Batches',value:stats.classes,icon:GraduationCap,href:'/classes'},{label:'Subjects',value:stats.subjects,icon:BookOpen,href:'/subjects'},{label:'Lectures',value:stats.lessons,icon:CalendarDays,href:'/curriculum'}]

  return (
    <Layout title={institution ? institution.name : `Welcome, ${user?.full_name||'Admin'}`} subtitle={institution ? `${(institution as any).board||institution.type} · ${institution.term_name||'No term set'}` : 'Complete setup below'}
      actions={<Button onClick={handleGenerate} disabled={generating} className="gap-2">{generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}{generating ? `Generating… ${jobProgress}%` : 'Generate Timetable'}</Button>}>
      <div className="p-6 space-y-6">
        {generating && <Card className="border-primary/30 bg-primary/5"><CardContent className="py-4"><div className="flex items-center gap-3 mb-2"><Loader2 className="w-4 h-4 animate-spin text-primary" /><span className="text-sm font-medium">Solving with OR-Tools CP-SAT…</span><span className="ml-auto text-sm text-muted-foreground">{jobProgress}%</span></div><Progress value={jobProgress} className="h-2" /></CardContent></Card>}
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div> : (
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="institution"><Settings2 className="w-3.5 h-3.5 mr-1.5" />Institution</TabsTrigger>
              <TabsTrigger value="timing"><Clock className="w-3.5 h-3.5 mr-1.5" />Timing</TabsTrigger>
            </TabsList>

            {/* Overview */}
            <TabsContent value="overview" className="space-y-5 pt-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {STAT_CARDS.map(({label,value,icon:Icon,href}) => (
                  <Card key={label} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate(href)}>
                    <CardContent className="p-5"><div className="flex items-center justify-between mb-3"><div className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center"><Icon className="w-4 h-4 text-muted-foreground" /></div><ArrowRight className="w-3.5 h-3.5 text-muted-foreground" /></div><div className="text-2xl font-bold">{value}</div><div className="text-sm text-muted-foreground">{label}</div></CardContent>
                  </Card>
                ))}
              </div>
              {stats.lessons===0 && (
                <Card className="border-amber-200 bg-amber-50">
                  <CardHeader><CardTitle className="text-base text-amber-900">Setup checklist</CardTitle><CardDescription className="text-amber-700">Complete these steps before generating</CardDescription></CardHeader>
                  <CardContent className="space-y-3">
                    {[{done:stats.teachers>0,label:'Add faculty',href:'/teachers'},{done:stats.rooms>0,label:'Add rooms & labs',href:'/rooms'},{done:stats.classes>0,label:'Add batches',href:'/classes'},{done:stats.subjects>0,label:'Add subjects',href:'/subjects'},{done:stats.lessons>0,label:'Map curriculum',href:'/curriculum'}].map(({done,label,href}) => (
                      <div key={label} className="flex items-center justify-between">
                        <div className="flex items-center gap-2"><div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${done?'bg-green-500 text-white':'bg-gray-200 text-gray-500'}`}>{done?'✓':'·'}</div><span className={`text-sm ${done?'line-through text-muted-foreground':''}`}>{label}</span></div>
                        {!done && <Button size="sm" variant="outline" className="h-7 text-xs gap-1" onClick={() => navigate(href)}><Plus className="w-3 h-3" />Go</Button>}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-3"><div><CardTitle>Timetables</CardTitle><CardDescription>Generated this term</CardDescription></div><Button variant="outline" size="sm" onClick={() => navigate('/timetables')}>View all</Button></CardHeader>
                <CardContent>
                  {timetables.length===0 ? <div className="text-center py-8 text-muted-foreground"><CalendarDays className="w-10 h-10 mx-auto mb-3 opacity-30" /><p className="text-sm">No timetables yet.</p></div>
                    : <div className="space-y-2">{timetables.slice(0,5).map(tt => (<div key={tt.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 cursor-pointer" onClick={() => navigate(`/timetables/${tt.id}`)}><div><p className="font-medium text-sm">{tt.name}</p><p className="text-xs text-muted-foreground">Score: {tt.soft_score} · {new Date(tt.created_at).toLocaleDateString('en-IN')}</p></div><Badge className={scol(tt.status)}>{tt.status}</Badge></div>))}</div>}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Institution Settings */}
            <TabsContent value="institution" className="pt-4">
              <Card>
                <CardHeader><CardTitle>Institution Details</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5"><Label>Name</Label><Input value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} placeholder="VJTI Mumbai" /></div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5"><Label>Type</Label>
                      <Select value={form.type} onValueChange={v=>setForm(f=>({...f,type:v}))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="college">College / University</SelectItem><SelectItem value="school">School</SelectItem><SelectItem value="office">Office</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5"><Label>Board / Affiliation</Label>
                      <Select value={form.board||'none'} onValueChange={v=>setForm(f=>({...f,board:v==='none'?'':v}))}>
                        <SelectTrigger><SelectValue placeholder="Select…" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Not specified</SelectItem>
                          <SelectItem value="Mumbai University">Mumbai University</SelectItem>
                          <SelectItem value="Pune University">SPPU Pune</SelectItem>
                          <SelectItem value="Nagpur University">RTM Nagpur</SelectItem>
                          <SelectItem value="GTU">Gujarat Technological University</SelectItem>
                          <SelectItem value="VTU">Visvesvaraya Tech University</SelectItem>
                          <SelectItem value="Anna University">Anna University</SelectItem>
                          <SelectItem value="CBSE">CBSE</SelectItem>
                          <SelectItem value="ICSE">ICSE / ISC</SelectItem>
                          <SelectItem value="Maharashtra State Board">Maharashtra SSC / HSC</SelectItem>
                          <SelectItem value="Other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5"><Label>Semester / Term</Label><Input value={form.term_name} onChange={e=>setForm(f=>({...f,term_name:e.target.value}))} placeholder="Sem III 2026" /></div>
                    <div className="space-y-1.5"><Label>Academic year start</Label><Input type="date" value={form.academic_year_start} onChange={e=>setForm(f=>({...f,academic_year_start:e.target.value}))} /></div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5"><Label>Working days / week</Label>
                      <Select value={String(form.days_per_week)} onValueChange={v=>setForm(f=>({...f,days_per_week:+v,day_labels:+v===6?'Mon,Tue,Wed,Thu,Fri,Sat':'Mon,Tue,Wed,Thu,Fri'}))}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="5">5 days (Mon–Fri)</SelectItem><SelectItem value="6">6 days (Mon–Sat)</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5"><Label>Lectures per day</Label><Input type="number" min={1} max={12} value={form.periods_per_day} onChange={e=>setForm(f=>({...f,periods_per_day:+e.target.value||8}))} /></div>
                  </div>
                  <div className="pt-2 flex justify-end"><Button onClick={handleSaveInst} disabled={savingInst} className="gap-2">{savingInst ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}Save</Button></div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Timing */}
            <TabsContent value="timing" className="pt-4 space-y-4">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Clock className="w-5 h-5 text-blue-600" />College Hours & Period Schedule</CardTitle><CardDescription>Set start/end, lecture duration, breaks. Click "Apply to timetable" then Save.</CardDescription></CardHeader>
                <CardContent className="space-y-5">
                  <div>
                    <Label className="text-xs uppercase tracking-wider text-muted-foreground mb-2 block">Quick templates</Label>
                    <div className="flex gap-2 flex-wrap">
                      {TEMPLATES.map(t => <Button key={t.label} variant="outline" size="sm" className="text-xs h-7" onClick={() => { setForm(f=>({...f,days_per_week:t.days,periods_per_day:t.periods,day_labels:t.day_labels})); setTiming({college_start:t.start,college_end:t.end,lecture_duration:t.lec,lab_duration:t.lab,breaks:t.breaks.map(b=>({...b}))}); setNextBrkId(10) }}>{t.label}</Button>)}
                    </div>
                  </div>
                  <Separator />
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5"><Label className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-green-600" />Start time</Label><Input type="time" value={timing.college_start} onChange={e=>setTiming(t=>({...t,college_start:e.target.value}))} /><p className="text-xs text-muted-foreground">First lecture starts here</p></div>
                    <div className="space-y-1.5"><Label className="flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-red-500" />End time</Label><Input type="time" value={timing.college_end} onChange={e=>setTiming(t=>({...t,college_end:e.target.value}))} /><p className="text-xs text-muted-foreground">No lectures after this</p></div>
                    <div className="space-y-1.5"><Label className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />Lecture duration (min)</Label><Input type="number" min={20} max={120} step={5} value={timing.lecture_duration} onChange={e=>setTiming(t=>({...t,lecture_duration:+e.target.value||55}))} /><p className="text-xs text-muted-foreground">Engineering: 55 · School: 45</p></div>
                    <div className="space-y-1.5"><Label className="flex items-center gap-1"><FlaskConical className="w-3.5 h-3.5 text-purple-600" />Lab duration (min)</Label><Input type="number" min={60} max={240} step={5} value={timing.lab_duration} onChange={e=>setTiming(t=>({...t,lab_duration:+e.target.value||110}))} /><p className="text-xs text-muted-foreground">Spans 2 periods · Typical: 110</p></div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between"><Label className="flex items-center gap-1.5 font-medium"><Coffee className="w-3.5 h-3.5 text-amber-600" />Breaks</Label><Button variant="outline" size="sm" className="h-7 gap-1 text-xs" onClick={addBreak}><Plus className="w-3 h-3" />Add break</Button></div>
                    {timing.breaks.sort((a,b)=>a.after_lecture-b.after_lecture).map(brk => (
                      <div key={brk.id} className="grid grid-cols-[1fr_90px_100px_32px] gap-2 items-end p-3 rounded-lg border bg-muted/20">
                        <div className="space-y-1"><Label className="text-xs">Name</Label><Input value={brk.label} onChange={e=>updateBreak(brk.id,'label',e.target.value)} placeholder="Lunch Break" className="h-8" /></div>
                        <div className="space-y-1"><Label className="text-xs">After lec #</Label><Input type="number" min={1} max={form.periods_per_day} value={brk.after_lecture} onChange={e=>updateBreak(brk.id,'after_lecture',+e.target.value||1)} className="h-8" /></div>
                        <div className="space-y-1"><Label className="text-xs">Duration (min)</Label><Input type="number" min={5} max={120} step={5} value={brk.duration_mins} onChange={e=>updateBreak(brk.id,'duration_mins',+e.target.value||10)} className="h-8" /></div>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive self-end" onClick={() => removeBreak(brk.id)}><Trash2 className="w-3.5 h-3.5" /></Button>
                      </div>
                    ))}
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs uppercase tracking-wider text-muted-foreground">Daily schedule preview ({schedule.filter(s=>!s.is_break).length} lectures)</Label>
                      <Button size="sm" variant="default" className="h-7 text-xs gap-1.5" onClick={applySchedule}><Save className="w-3 h-3" />Apply to timetable</Button>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                      {schedule.map((slot,i) => (
                        <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm border ${slot.is_break ? 'bg-amber-50 border-amber-200' : 'bg-background'}`}>
                          {slot.is_break ? <><Coffee className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" /><div><div className="text-xs font-medium text-amber-700">{slot.break_label}</div><div className="text-[10px] text-amber-600">{slot.label.split('(')[0].trim()}</div></div></>
                            : <><Badge variant="outline" className="text-xs w-7 h-7 flex items-center justify-center p-0 flex-shrink-0">{slot.period_num}</Badge><span className="text-xs text-muted-foreground">{slot.label}</span></>}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground bg-blue-50 border border-blue-200 rounded p-2">After clicking <strong>Apply to timetable</strong>, go to the <strong>Institution</strong> tab and click <strong>Save</strong>.</p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        )}
      </div>
    </Layout>
  )
}
