import { useState, useRef, useEffect } from 'react'
import { toast } from 'sonner'
import { Sparkles, X, Send, Loader2, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useApp } from '@/lib/store'
import { api, agentApi } from '@/lib/api'
import type { Timetable } from '@/types'

interface AbsenceChange { type: 'substitute'|'reschedule'; assignment_id: string; description: string; new_teacher_id?: string|null; new_teacher_name?: string|null; new_day?: number|null; new_period?: number|null; new_day_label?: string|null }
interface AbsencePlan { absent_teacher: string; day: string; affected_count: number; changes: AbsenceChange[] }
interface ChatMsg { role: 'user'|'assistant'; content: string; plan?: AbsencePlan; planApplied?: boolean }

const QUICK = ['Prof. X is absent on Monday','show conflicts','workload report','who teaches physics','show schedule','summarize timetable']

export function AIChat() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMsg[]>([{ role:'assistant', content:'Hi! I\'m your timetabling AI 🎓\n\n• "Prof. Mehta is absent on Monday" → substitutes + reschedule\n• show conflicts\n• workload report\n• show [class/teacher] schedule' }])
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState<number|null>(null)
  const [timetable, setTimetable] = useState<Timetable|null>(null)
  const [loadingTT, setLoadingTT] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !instId || timetable) return
    const load = async () => {
      setLoadingTT(true)
      try {
        const list = await api.listTimetables(instId) as Timetable[]
        const best = list.find(t => t.status==='published') || list.find(t => t.status==='solved')
        if (best) { const full = await api.getTimetable(best.id) as Timetable; setTimetable(full); setMessages(m => [...m, { role:'assistant', content:`✅ Loaded: **${full.name}** (${full.assignments?.length||0} lectures). Ready!` }]) }
      } catch {} finally { setLoadingTT(false) }
    }
    load()
  }, [open, instId])

  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior:'smooth' }) }, [messages])

  const send = async () => {
    const msg = input.trim(); if (!msg || loading) return
    setInput(''); setMessages(m => [...m, { role:'user', content:msg }]); setLoading(true)
    if (!timetable) { setMessages(m => [...m, { role:'assistant', content:'⚠️ No timetable loaded. Generate one from Dashboard first.' }]); setLoading(false); return }
    try {
      const res = await api.chat({ timetable_id:timetable.id, institution_id:instId, message:msg, history:messages.slice(-8) }) as any
      const newMsg: ChatMsg = { role:'assistant', content:res.reply }
      if (res.action==='absence_plan' && res.data?.plan) { newMsg.plan=res.data.plan; newMsg.planApplied=false }
      setMessages(m => [...m, newMsg])
    } catch (e: unknown) { setMessages(m => [...m, { role:'assistant', content:'❌ Error: '+(e instanceof Error ? e.message : 'Failed') }]) }
    finally { setLoading(false) }
  }

  const applyPlan = async (idx: number, plan: AbsencePlan) => {
    if (!timetable) return; setApplying(idx)
    try {
      const res = await agentApi.applyPlan(timetable.id, plan.changes) as any
      setMessages(m => m.map((msg, i) => i===idx ? {...msg, planApplied:true} : msg))
      const fresh = await api.getTimetable(timetable.id) as Timetable; setTimetable(fresh)
      toast.success(res.message)
      setMessages(m => [...m, { role:'assistant', content:`✅ Applied ${res.applied?.length||0} change(s). Open the timetable to see the updated schedule.` }])
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Apply failed') }
    finally { setApplying(null) }
  }

  if (!open) return (
    <button onClick={() => setOpen(true)} className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl hover:scale-105 transition-all flex items-center justify-center" title="Open AI Assistant" aria-label="Open AI Chat">
      <Sparkles className="w-6 h-6" />
      <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-background" />
    </button>
  )

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex flex-col bg-background border rounded-2xl shadow-2xl transition-all duration-200 ${minimized ? 'h-14 w-80' : 'h-[600px] w-96'}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b rounded-t-2xl bg-primary/5 cursor-pointer" onClick={() => setMinimized(m => !m)}>
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm">Timely AI</span>
          {timetable && <Badge variant="secondary" className="text-[10px] px-1.5">{timetable.name.slice(0,20)}</Badge>}
          {loadingTT && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
        </div>
        <div className="flex items-center gap-1.5">
          {minimized ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
          <button onClick={e => { e.stopPropagation(); setOpen(false) }} className="text-muted-foreground hover:text-foreground p-0.5"><X className="w-4 h-4" /></button>
        </div>
      </div>

      {!minimized && (
        <>
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-3">
              {messages.map((msg, i) => (
                <div key={i} className={`flex flex-col ${msg.role==='user' ? 'items-end' : 'items-start'}`}>
                  <div className={`max-w-[95%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${msg.role==='user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'}`}>{msg.content}</div>
                  {msg.plan && !msg.planApplied && (
                    <div className="mt-2 w-[95%] rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2">
                      <p className="text-xs font-semibold text-amber-800">📋 Plan — {msg.plan.changes.length} changes</p>
                      <div className="space-y-1">
                        {msg.plan.changes.map((ch, ci) => (
                          <div key={ci} className={`text-xs flex items-start gap-1 ${ch.type==='substitute' ? 'text-blue-700' : 'text-purple-700'}`}>
                            <span className="flex-shrink-0">{ch.type==='substitute' ? '👤' : '📅'}</span>
                            <span>{ch.type==='substitute' ? (ch.new_teacher_name ? `Cover → ${ch.new_teacher_name}` : '⚠️ No substitute') : (ch.new_day!=null ? `Reschedule → ${ch.new_day_label} P${(ch.new_period||0)+1}` : '⚠️ No slot found')}</span>
                          </div>
                        ))}
                      </div>
                      <div className="flex gap-2 pt-1">
                        <Button size="sm" className="flex-1 h-8 text-xs gap-1" disabled={applying===i} onClick={() => applyPlan(i, msg.plan!)}>
                          {applying===i ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                          {applying===i ? 'Applying…' : 'Confirm & Apply'}
                        </Button>
                        <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setMessages(m => m.map((msg2,j) => j===i ? {...msg2,planApplied:true} : msg2))}>Discard</Button>
                      </div>
                    </div>
                  )}
                  {msg.plan && msg.planApplied && <div className="mt-1 flex items-center gap-1 text-xs text-green-600"><CheckCircle2 className="w-3 h-3" />Applied</div>}
                </div>
              ))}
              {loading && <div className="flex justify-start"><div className="bg-muted rounded-xl px-3 py-2"><Loader2 className="w-3.5 h-3.5 animate-spin" /></div></div>}
              <div ref={scrollRef} />
            </div>
          </ScrollArea>
          <div className="px-3 py-2 border-t">
            <div className="flex gap-1.5 flex-wrap">
              {QUICK.map(q => <button key={q} className="text-[10px] px-2 py-1 rounded-full border hover:bg-muted transition-colors" onClick={() => setInput(q)}>{q}</button>)}
            </div>
          </div>
          <div className="p-3 border-t flex gap-2">
            <Textarea ref={null} value={input} onChange={e => setInput(e.target.value)} placeholder={timetable ? 'Ask anything…' : 'Generate a timetable first…'} className="text-sm resize-none flex-1" rows={2} onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
            <Button size="icon" onClick={send} disabled={loading || !input.trim()}><Send className="w-3.5 h-3.5" /></Button>
          </div>
        </>
      )}
    </div>
  )
}
