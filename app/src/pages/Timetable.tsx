import { useEffect, useState, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Loader2, Globe, GlobeLock, X, Send, Users, DoorOpen, GraduationCap, ArrowLeft, Sparkles, CheckCircle2, Printer, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api, agentApi } from '@/lib/api'
import type { Timetable, Assignment, Teacher, Room, Class, Subject } from '@/types'

type ViewMode = 'class'|'teacher'|'room'
interface AbsenceChange { type:'substitute'|'reschedule'; assignment_id:string; description:string; new_teacher_id?:string|null; new_teacher_name?:string|null; new_day?:number|null; new_period?:number|null; new_day_label?:string|null }
interface AbsencePlan { absent_teacher:string; day:string; affected_count:number; changes:AbsenceChange[] }
interface ChatMsg { role:'user'|'assistant'; content:string; plan?:AbsencePlan; planApplied?:boolean }

const COLORS = ['#6366f1','#8b5cf6','#ec4899','#f43f5e','#f97316','#eab308','#22c55e','#14b8a6','#06b6d4','#3b82f6']

export function TimetablePage() {
  const { id } = useParams<{ id:string }>()
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const navigate = useNavigate()
  const [timetable, setTimetable] = useState<Timetable|null>(null)
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [rooms, setRooms] = useState<Room[]>([])
  const [classes, setClasses] = useState<Class[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<ViewMode>('class')
  const [selectedEntity, setSelectedEntity] = useState<string>('')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState<ChatMsg[]>([{ role:'assistant', content:'Hi! Try:\n• "Prof. X is absent on Monday"\n• show conflicts\n• workload report\n• show [class/teacher] schedule' }])
  const [chatLoading, setChatLoading] = useState(false)
  const [applying, setApplying] = useState<string|null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<Assignment|null>(null)

  useEffect(() => {
    if (!id||!instId) return
    const load = async () => {
      try {
        const [tt,t,r,c,s]=await Promise.all([api.getTimetable(id),api.listTeachers(instId),api.listRooms(instId),api.listClasses(instId),api.listSubjects(instId)])
        setTimetable(tt as Timetable); setTeachers(t as Teacher[]); setRooms(r as Room[]); setClasses(c as Class[]); setSubjects(s as Subject[])
        if ((c as Class[]).length) setSelectedEntity((c as Class[])[0].id)
      } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
      finally { setLoading(false) }
    }
    load()
  }, [id,instId])

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior:'smooth' }) }, [chatHistory])
  useEffect(() => {
    if (viewMode==='class'&&classes.length) setSelectedEntity(classes[0].id)
    else if (viewMode==='teacher'&&teachers.length) setSelectedEntity(teachers[0].id)
    else if (viewMode==='room'&&rooms.length) setSelectedEntity(rooms[0].id)
  }, [viewMode])

  const handlePublish = async () => {
    if (!timetable) return
    try {
      const u=timetable.status==='published' ? await api.unpublishTimetable(timetable.id) : await api.publishTimetable(timetable.id)
      setTimetable(u as Timetable); toast.success(timetable.status==='published'?'Unpublished':'Published!')
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleDrop = useCallback(async (day: number, period: number) => {
    if (!timetable||!dragRef.current) return
    const a=dragRef.current; if (a.day===day&&a.period===period) return
    try {
      const updated=await api.updateAssignment(timetable.id,a.id,{day,period,room_id:a.room_id})
      setTimetable(tt => tt ? ({...tt,assignments:tt.assignments!.map(x=>x.id===a.id ? updated as Assignment : x)}) : tt)
      toast.success('Moved')
    } catch (e: unknown) {
      const msg=e instanceof Error ? e.message : 'Move failed'
      const parsed=(() => { try { return JSON.parse(msg) } catch { return null } })()
      toast.error(parsed?.conflicts ? parsed.conflicts.join(', ') : msg)
    }
  }, [timetable])

  const handleExportCSV = useCallback(() => {
    if (!timetable?.assignments) return
    const daysArr=institution?.day_labels||['Mon','Tue','Wed','Thu','Fri']
    const pLabels=institution?.period_labels?.length ? institution.period_labels : Array.from({length:institution?.periods_per_day||7},(_,i)=>`P${i+1}`)
    const rows=[['Day','Period','Class','Subject','Teacher','Room']]
    for (const a of timetable.assignments.sort((x,y)=>x.day-y.day||x.period-y.period)) {
      rows.push([daysArr[a.day]??`Day${a.day+1}`,pLabels[a.period]??`P${a.period+1}`,classes.find(c=>c.id===a.class_id)?.name??a.class_id,subjects.find(s=>s.id===a.subject_id)?.name??a.subject_id,teachers.find(t=>t.id===a.teacher_id)?.name??a.teacher_id,rooms.find(r=>r.id===a.room_id)?.name??a.room_id])
    }
    const csv=rows.map(r=>r.map(c=>`"${c}"`).join(',')).join('\n')
    const blob=new Blob([csv],{type:'text/csv'}); const url=URL.createObjectURL(blob)
    const a=document.createElement('a'); a.href=url; a.download=`${timetable.name.replace(/\s+/g,'_')}.csv`; a.click(); URL.revokeObjectURL(url)
    toast.success('CSV downloaded')
  }, [timetable,classes,subjects,teachers,rooms,institution])

  const sendChat = async () => {
    if (!chatInput.trim()||!timetable) return
    const msg=chatInput.trim(); setChatInput(''); setChatHistory(h=>[...h,{role:'user',content:msg}]); setChatLoading(true)
    try {
      const res=await api.chat({timetable_id:timetable.id,institution_id:instId,message:msg,history:chatHistory.slice(-10)}) as any
      const newMsg: ChatMsg={role:'assistant',content:res.reply}
      if (res.action==='absence_plan'&&res.data?.plan) { newMsg.plan=res.data.plan; newMsg.planApplied=false }
      setChatHistory(h=>[...h,newMsg])
    } catch (e: unknown) { setChatHistory(h=>[...h,{role:'assistant',content:'Error: '+(e instanceof Error?e.message:'Failed')}]) }
    finally { setChatLoading(false) }
  }

  const handleApplyPlan = async (msgIdx: number, plan: AbsencePlan) => {
    if (!timetable) return; setApplying(String(msgIdx))
    try {
      const res=await agentApi.applyPlan(timetable.id,plan.changes) as any
      setChatHistory(h=>h.map((m,i)=>i===msgIdx?{...m,planApplied:true}:m))
      const fresh=await api.getTimetable(timetable.id) as Timetable; setTimetable(fresh)
      toast.success(res.message)
      setChatHistory(h=>[...h,{role:'assistant',content:`✅ Applied ${res.applied?.length||0} change(s)${res.skipped?.length?` (${res.skipped.length} skipped)`:''}.`}])
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Apply failed') }
    finally { setApplying(null) }
  }

  const days=institution?.day_labels||['Mon','Tue','Wed','Thu','Fri']
  const periods=institution?.periods_per_day||7
  const periodLabels=institution?.period_labels?.length ? institution.period_labels : Array.from({length:periods},(_,i)=>`P${i+1}`)
  const subjectColorMap: Record<string,string>={}
  subjects.forEach((s,i)=>{ subjectColorMap[s.id]=s.color||COLORS[i%COLORS.length] })

  const getCell=(day:number,period:number): Assignment[] => {
    if (!timetable?.assignments) return []
    return timetable.assignments.filter(a => {
      if (a.day!==day||a.period!==period) return false
      if (viewMode==='class') return a.class_id===selectedEntity
      if (viewMode==='teacher') return a.teacher_id===selectedEntity
      if (viewMode==='room') return a.room_id===selectedEntity
      return true
    })
  }

  const entities=viewMode==='class' ? classes.map(c=>({id:c.id,label:c.name})) : viewMode==='teacher' ? teachers.map(t=>({id:t.id,label:t.name})) : rooms.map(r=>({id:r.id,label:r.name}))
  const statusColors: Record<string,string>={solved:'bg-green-100 text-green-700',published:'bg-blue-100 text-blue-700',failed:'bg-red-100 text-red-700',draft:'bg-gray-100 text-gray-600'}

  if (loading) return <Layout><div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div></Layout>
  if (!timetable) return <Layout><div className="p-8 text-center text-muted-foreground">Timetable not found</div></Layout>

  return (
    <Layout title={timetable.name} subtitle={`${timetable.assignments?.length||0} lectures · Score: ${timetable.soft_score}`}
      actions={
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={()=>navigate('/timetables')} className="gap-1.5"><ArrowLeft className="w-3.5 h-3.5" />Back</Button>
          <Badge className={statusColors[timetable.status]||''}>{timetable.status}</Badge>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={handlePublish}>{timetable.status==='published' ? <><GlobeLock className="w-3.5 h-3.5" />Unpublish</> : <><Globe className="w-3.5 h-3.5" />Publish</>}</Button>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={()=>window.print()}><Printer className="w-3.5 h-3.5" />Print</Button>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={handleExportCSV}><Download className="w-3.5 h-3.5" />CSV</Button>
          <Button size="sm" className="gap-1.5" onClick={()=>setChatOpen(o=>!o)}><Sparkles className="w-3.5 h-3.5" />AI Chat</Button>
        </div>
      }>
      <div className="flex h-full overflow-hidden">
        <div className="flex-1 overflow-auto p-6 min-w-0">
          <div className="flex items-center gap-4 mb-5 flex-wrap">
            <Tabs value={viewMode} onValueChange={v=>setViewMode(v as ViewMode)}>
              <TabsList>
                <TabsTrigger value="class" className="gap-1.5"><GraduationCap className="w-3.5 h-3.5" />By Class</TabsTrigger>
                <TabsTrigger value="teacher" className="gap-1.5"><Users className="w-3.5 h-3.5" />By Teacher</TabsTrigger>
                <TabsTrigger value="room" className="gap-1.5"><DoorOpen className="w-3.5 h-3.5" />By Room</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex gap-2 flex-wrap">
              {entities.map(e=><button key={e.id} onClick={()=>setSelectedEntity(e.id)} className={`px-3 py-1 rounded-full text-sm border transition-colors ${selectedEntity===e.id ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'}`}>{e.label}</button>)}
            </div>
          </div>

          {timetable.violations.length>0 && <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm"><span className="font-medium text-amber-800">Soft violations: </span><span className="text-amber-700">{timetable.violations.map(v=>`${v.type} (${v.count})`).join(' · ')}</span></div>}

          <div className="overflow-x-auto">
            <div className="inline-block min-w-full">
              <div className="grid border rounded-lg overflow-hidden bg-background shadow-sm" style={{gridTemplateColumns:`72px repeat(${days.length}, minmax(110px, 1fr))`}}>
                <div className="bg-muted/70 border-b border-r p-2 text-xs text-muted-foreground font-medium text-center">Period</div>
                {days.map((d,di)=><div key={di} className="bg-muted/70 border-b border-r last:border-r-0 p-2 text-center text-sm font-semibold">{d}</div>)}
                {periodLabels.map((pl,pi)=>(
                  <>
                    <div key={`l${pi}`} className="border-b border-r bg-muted/40 flex items-center justify-center p-2 text-xs font-medium text-muted-foreground">{pl}</div>
                    {days.map((_,di)=>{
                      const cells=getCell(di,pi)
                      return (
                        <div key={`c${di}${pi}`} className="border-b border-r last:border-r-0 min-h-[72px] p-1 relative"
                          onDragOver={e=>{e.preventDefault();e.currentTarget.classList.add('bg-primary/5')}}
                          onDragLeave={e=>e.currentTarget.classList.remove('bg-primary/5')}
                          onDrop={e=>{e.currentTarget.classList.remove('bg-primary/5');handleDrop(di,pi)}}>
                          {cells.map(cell=>{
                            const subj=subjects.find(s=>s.id===cell.subject_id)
                            const teacher=teachers.find(t=>t.id===cell.teacher_id)
                            const cls=classes.find(c=>c.id===cell.class_id)
                            const room=rooms.find(r=>r.id===cell.room_id)
                            const color=subjectColorMap[cell.subject_id]||'#6366f1'
                            return (
                              <div key={cell.id} draggable={timetable.status!=='published'} onDragStart={()=>{dragRef.current=cell}} onDragEnd={()=>{dragRef.current=null}}
                                className="rounded-md p-1.5 mb-1 text-white text-xs cursor-grab active:cursor-grabbing select-none shadow-sm hover:brightness-110 transition-all" style={{backgroundColor:color}}
                                title={`${subj?.name} · ${teacher?.name} · ${room?.name}`}>
                                <div className="font-semibold leading-tight truncate">{subj?.name||'?'}</div>
                                {viewMode!=='teacher'&&<div className="opacity-85 truncate">{teacher?.name}</div>}
                                {viewMode!=='class'&&<div className="opacity-85 truncate">{cls?.name}</div>}
                                {viewMode!=='room'&&room&&<div className="opacity-70 truncate text-[10px]">{room.name}</div>}
                              </div>
                            )
                          })}
                        </div>
                      )
                    })}
                  </>
                ))}
              </div>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-3">{timetable.status!=='published' ? 'Drag cells to move lectures. Use AI Chat for absences.' : 'Published — read only.'}</p>
        </div>

        {chatOpen && (
          <div className="w-96 flex-shrink-0 border-l flex flex-col bg-background">
            <div className="flex items-center justify-between p-4 border-b">
              <div className="flex items-center gap-2"><Sparkles className="w-4 h-4 text-primary" /><span className="font-semibold text-sm">AI Assistant</span></div>
              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={()=>setChatOpen(false)}><X className="w-3.5 h-3.5" /></Button>
            </div>
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-3">
                {chatHistory.map((msg,i)=>(
                  <div key={i} className={`flex flex-col ${msg.role==='user'?'items-end':'items-start'}`}>
                    <div className={`max-w-[95%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${msg.role==='user'?'bg-primary text-primary-foreground':'bg-muted text-foreground'}`}>{msg.content}</div>
                    {msg.plan&&!msg.planApplied&&(
                      <div className="mt-2 w-[95%] rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2">
                        <p className="text-xs font-semibold text-amber-800">📋 Plan — {msg.plan.changes.length} changes</p>
                        <div className="space-y-1">
                          {msg.plan.changes.map((ch,ci)=>(
                            <div key={ci} className={`text-xs flex items-start gap-1.5 ${ch.type==='substitute'?'text-blue-700':'text-purple-700'}`}>
                              <span className="flex-shrink-0">{ch.type==='substitute'?'👤':'📅'}</span>
                              <span>{ch.type==='substitute' ? (ch.new_teacher_name?`Cover P${(timetable.assignments?.find(a=>a.id===ch.assignment_id)?.period??0)+1} → ${ch.new_teacher_name}`:'⚠️ No substitute') : (ch.new_day!=null?`Reschedule → ${ch.new_day_label} P${(ch.new_period??0)+1}`:'⚠️ No slot')}</span>
                            </div>
                          ))}
                        </div>
                        <div className="flex gap-2 pt-1">
                          <Button size="sm" className="flex-1 gap-1.5 h-8 text-xs" disabled={applying===String(i)} onClick={()=>handleApplyPlan(i,msg.plan!)}>
                            {applying===String(i)?<Loader2 className="w-3.5 h-3.5 animate-spin" />:<CheckCircle2 className="w-3.5 h-3.5" />}
                            {applying===String(i)?'Applying…':'Confirm & Apply'}
                          </Button>
                          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={()=>setChatHistory(h=>h.map((m,idx)=>idx===i?{...m,planApplied:true}:m))}>Discard</Button>
                        </div>
                      </div>
                    )}
                    {msg.plan&&msg.planApplied&&<div className="mt-1 flex items-center gap-1.5 text-xs text-green-600"><CheckCircle2 className="w-3.5 h-3.5" />Applied</div>}
                  </div>
                ))}
                {chatLoading&&<div className="flex justify-start"><div className="bg-muted rounded-xl px-3 py-2"><Loader2 className="w-3.5 h-3.5 animate-spin" /></div></div>}
                <div ref={chatEndRef} />
              </div>
            </ScrollArea>
            <div className="p-3 border-t border-b">
              <div className="flex flex-wrap gap-1.5">
                {['Prof. X is absent on Monday','show conflicts','workload report','who teaches physics','show schedule','explain score'].map(q=><button key={q} className="text-xs px-2 py-1 rounded-full border hover:bg-muted transition-colors" onClick={()=>setChatInput(q)}>{q}</button>)}
              </div>
            </div>
            <div className="p-3 flex gap-2">
              <Textarea value={chatInput} onChange={e=>setChatInput(e.target.value)} placeholder='"Prof. Sharma is absent on Wednesday"' className="text-sm resize-none flex-1" rows={2} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat()}}} />
              <Button size="icon" onClick={sendChat} disabled={chatLoading||!chatInput.trim()}><Send className="w-3.5 h-3.5" /></Button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
