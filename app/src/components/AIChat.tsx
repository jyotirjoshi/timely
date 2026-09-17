import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router'
import { toast } from 'sonner'
import {
  Sparkles, X, Send, Loader2, CheckCircle2,
  ChevronDown, ChevronUp, BrainCircuit,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useApp } from '@/lib/store'
import { api, agentApi } from '@/lib/api'
import type { Timetable } from '@/types'

interface AbsenceChange {
  type: 'substitute' | 'reschedule'
  assignment_id: string
  description: string
  new_teacher_id?: string | null
  new_teacher_name?: string | null
  new_day?: number | null
  new_period?: number | null
  new_day_label?: string | null
}
interface AbsencePlan {
  absent_teacher: string
  day: string
  affected_count: number
  changes: AbsenceChange[]
}
interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  plan?: AbsencePlan
  planApplied?: boolean
}

// Pages where the AI button should NOT appear
const HIDE_ON = ['/', '/login', '/register']

const QUICK = [
  'Prof. X is absent on Monday',
  'show conflicts',
  'workload report',
  'who teaches physics',
  'show schedule',
  'summarize timetable',
]

export function AIChat() {
  const { institution, user, token } = useApp()
  const location = useLocation()
  const instId = institution?.id || user?.institution_id || ''

  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMsg[]>([{
    role: 'assistant',
    content:
      'Hi! I\'m your Timely AI 🎓\n\n' +
      'I can help with:\n' +
      '• **"Prof. Mehta is absent on Monday"** → find substitutes + reschedule automatically\n' +
      '• **show conflicts** → check for double-bookings\n' +
      '• **workload report** → see lecture counts per faculty\n' +
      '• **show [class/teacher] schedule** → full timetable\n' +
      '• **who teaches [subject]** → find the faculty\n\n' +
      'Just type naturally — I handle typos and Hindi too.',
  }])
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState<number | null>(null)
  const [timetable, setTimetable] = useState<Timetable | null>(null)
  const [loadingTT, setLoadingTT] = useState(false)
  const [minimized, setMinimized] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Don't render on public pages or when not logged in
  // NOTE: this check must come AFTER all hooks (React rules of hooks)
  const isPublicPage = HIDE_ON.includes(location.pathname)

  // Auto-load latest timetable when chat opens
  useEffect(() => {
    if (!open || !instId || timetable || isPublicPage || !token) return
    const load = async () => {
      setLoadingTT(true)
      try {
        const list = await api.listTimetables(instId) as Timetable[]
        const best = list.find(t => t.status === 'published') || list.find(t => t.status === 'solved')
        if (best) {
          const full = await api.getTimetable(best.id) as Timetable
          setTimetable(full)
          setMessages(m => [...m, {
            role: 'assistant',
            content: `✅ Loaded **${full.name}** (${full.assignments?.length || 0} lectures). Ready to help!`,
          }])
        } else {
          setMessages(m => [...m, {
            role: 'assistant',
            content: '📋 No timetable generated yet. Go to Dashboard → click **Generate Timetable** first.',
          }])
        }
      } catch {} finally { setLoadingTT(false) }
    }
    load()
  }, [open, instId])

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', content: msg }])
    setLoading(true)

    if (!timetable) {
      setMessages(m => [...m, {
        role: 'assistant',
        content: '⚠️ No timetable loaded yet. Go to Dashboard → **Generate Timetable** first, then I can help.',
      }])
      setLoading(false)
      return
    }

    try {
      const res = await api.chat({
        timetable_id: timetable.id,
        institution_id: instId,
        message: msg,
        history: messages.slice(-8),
      }) as any

      const newMsg: ChatMsg = { role: 'assistant', content: res.reply }
      if (res.action === 'absence_plan' && res.data?.plan) {
        newMsg.plan = res.data.plan
        newMsg.planApplied = false
      }
      setMessages(m => [...m, newMsg])
    } catch (e: unknown) {
      setMessages(m => [...m, {
        role: 'assistant',
        content: '❌ Error: ' + (e instanceof Error ? e.message : 'Request failed. Check your connection.'),
      }])
    } finally { setLoading(false) }
  }

  const applyPlan = async (idx: number, plan: AbsencePlan) => {
    if (!timetable) return
    setApplying(idx)
    try {
      const res = await agentApi.applyPlan(timetable.id, plan.changes) as any
      setMessages(m => m.map((msg, i) => i === idx ? { ...msg, planApplied: true } : msg))
      const fresh = await api.getTimetable(timetable.id) as Timetable
      setTimetable(fresh)
      toast.success(res.message)
      const skipped = res.skipped?.length ? ` (${res.skipped.length} skipped)` : ''
      setMessages(m => [...m, {
        role: 'assistant',
        content: `✅ Done! Applied ${res.applied?.length || 0} change(s)${skipped}.\n\nOpen the timetable view to see the updated schedule.`,
      }])
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Apply failed')
    } finally { setApplying(null) }
  }

  // Closed state — floating button (hide on public pages / not logged in)
  if (isPublicPage || !token) return null

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl hover:scale-105 transition-all flex items-center justify-center group"
        title="Open AI Assistant"
        aria-label="Open Timely AI"
      >
        <BrainCircuit className="w-6 h-6" />
        <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-background animate-pulse" />
      </button>
    )
  }

  // Open state — chat panel
  return (
    <div className={`fixed bottom-6 right-6 z-50 flex flex-col bg-background border rounded-2xl shadow-2xl transition-all duration-200 ${minimized ? 'h-14 w-80' : 'h-[600px] w-96'}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b rounded-t-2xl bg-gradient-to-r from-primary/10 to-primary/5 cursor-pointer select-none"
        onClick={() => setMinimized(m => !m)}
      >
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
            <BrainCircuit className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <span className="font-semibold text-sm">Timely AI</span>
            {timetable && (
              <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                {timetable.name.slice(0, 18)}{timetable.name.length > 18 ? '…' : ''}
              </Badge>
            )}
          </div>
          {loadingTT && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground ml-1" />}
        </div>
        <div className="flex items-center gap-1">
          {minimized
            ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
          <button
            onClick={e => { e.stopPropagation(); setOpen(false) }}
            className="ml-1 text-muted-foreground hover:text-foreground p-0.5 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!minimized && (
        <>
          {/* Messages */}
          <ScrollArea className="flex-1 p-4">
            <div className="space-y-3">
              {messages.map((msg, i) => (
                <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`max-w-[95%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground'
                  }`}>
                    {msg.content}
                  </div>

                  {/* Absence plan card */}
                  {msg.plan && !msg.planApplied && (
                    <div className="mt-2 w-[95%] rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2">
                      <p className="text-xs font-semibold text-amber-800">
                        📋 Plan for {msg.plan.absent_teacher} on {msg.plan.day}
                        <span className="ml-1 text-amber-600">({msg.plan.affected_count} lecture{msg.plan.affected_count !== 1 ? 's' : ''})</span>
                      </p>
                      <div className="space-y-1">
                        {msg.plan.changes.map((ch, ci) => (
                          <div key={ci} className={`text-xs flex items-start gap-1.5 ${
                            ch.type === 'substitute' ? 'text-blue-700' : 'text-purple-700'
                          }`}>
                            <span className="flex-shrink-0 mt-0.5">
                              {ch.type === 'substitute' ? '👤' : '📅'}
                            </span>
                            <span>
                              {ch.type === 'substitute'
                                ? ch.new_teacher_name
                                  ? `Cover → ${ch.new_teacher_name}`
                                  : '⚠️ No substitute available'
                                : ch.new_day != null
                                  ? `Reschedule → ${ch.new_day_label} P${(ch.new_period || 0) + 1}`
                                  : '⚠️ No free slot found'}
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className="flex gap-2 pt-1">
                        <Button
                          size="sm" className="flex-1 h-8 text-xs gap-1.5"
                          disabled={applying === i}
                          onClick={() => applyPlan(i, msg.plan!)}
                        >
                          {applying === i
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <CheckCircle2 className="w-3 h-3" />}
                          {applying === i ? 'Applying…' : 'Confirm & Apply'}
                        </Button>
                        <Button
                          size="sm" variant="outline" className="h-8 text-xs"
                          onClick={() => setMessages(m => m.map((m2, j) => j === i ? { ...m2, planApplied: true } : m2))}
                        >
                          Discard
                        </Button>
                      </div>
                    </div>
                  )}

                  {msg.plan && msg.planApplied && (
                    <div className="mt-1 flex items-center gap-1 text-xs text-green-600">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Applied to timetable</span>
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-xl px-4 py-2.5 flex items-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">Thinking…</span>
                  </div>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          </ScrollArea>

          {/* Quick prompts */}
          <div className="px-3 pt-2 pb-1 border-t">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">Quick prompts</p>
            <div className="flex gap-1.5 flex-wrap">
              {QUICK.map(q => (
                <button
                  key={q}
                  className="text-[10px] px-2 py-1 rounded-full border hover:bg-muted transition-colors text-left"
                  onClick={() => setInput(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {/* Input */}
          <div className="p-3 border-t flex gap-2">
            <Textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={timetable ? 'Ask anything about your timetable…' : 'Generate a timetable first…'}
              className="text-sm resize-none flex-1 min-h-[60px]"
              rows={2}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
            />
            <Button
              size="icon"
              onClick={send}
              disabled={loading || !input.trim()}
              className="self-end h-9 w-9"
            >
              <Send className="w-3.5 h-3.5" />
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
