import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Loader2, UserCircle2, Grid3x3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api } from '@/lib/api'
import type { Teacher } from '@/types'

const COLORS = ['#6366f1','#8b5cf6','#ec4899','#f43f5e','#f97316','#eab308','#22c55e','#14b8a6','#06b6d4','#3b82f6']

function AvailabilityGrid({ days, periods, periodLabels, unavailable, onChange }: {
  days: string[]; periods: number; periodLabels: string[]
  unavailable: [number,number][]; onChange: (s: [number,number][]) => void
}) {
  const blocked = new Set(unavailable.map(([d,p]) => `${d}-${p}`))
  const toggle = (d: number, p: number) => {
    const key = `${d}-${p}`
    if (blocked.has(key)) onChange(unavailable.filter(([dd,pp]) => !(dd===d && pp===p)))
    else onChange([...unavailable, [d,p]])
  }
  const toggleDay = (d: number) => {
    const all = Array.from({length:periods},(_,p) => `${d}-${p}`).every(k => blocked.has(k))
    if (all) onChange(unavailable.filter(([dd]) => dd!==d))
    else { const n=[...unavailable]; for(let p=0;p<periods;p++) if(!blocked.has(`${d}-${p}`)) n.push([d,p]); onChange(n) }
  }
  const togglePeriod = (p: number) => {
    const all = days.every((_,d) => blocked.has(`${d}-${p}`))
    if (all) onChange(unavailable.filter(([,pp]) => pp!==p))
    else { const n=[...unavailable]; for(let d=0;d<days.length;d++) if(!blocked.has(`${d}-${p}`)) n.push([d,p]); onChange(n) }
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Click to mark unavailable (red). Click header to block whole day/period.</p>
        {unavailable.length > 0 && <button className="text-xs text-muted-foreground underline" onClick={() => onChange([])}>Clear all</button>}
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="border-collapse text-xs">
          <thead>
            <tr>
              <th className="p-2 bg-muted/50 border-b border-r min-w-[80px] text-muted-foreground font-medium">Period ↓ Day →</th>
              {days.map((d,di) => {
                const full = Array.from({length:periods},(_,p) => `${di}-${p}`).every(k => blocked.has(k))
                return <th key={di} className={`p-2 border-b border-r last:border-r-0 font-medium cursor-pointer select-none min-w-[52px] text-center transition-colors ${full ? 'bg-red-100 text-red-700' : 'bg-muted/50 hover:bg-muted text-muted-foreground'}`} onClick={() => toggleDay(di)}>{d}</th>
              })}
            </tr>
          </thead>
          <tbody>
            {periodLabels.map((pl,pi) => {
              const full = days.every((_,di) => blocked.has(`${di}-${pi}`))
              return (
                <tr key={pi}>
                  <td className={`p-2 border-b border-r font-medium cursor-pointer select-none text-center whitespace-nowrap transition-colors ${full ? 'bg-red-100 text-red-700' : 'bg-muted/30 hover:bg-muted text-muted-foreground'}`} onClick={() => togglePeriod(pi)}>{pl}</td>
                  {days.map((_,di) => {
                    const isBlocked = blocked.has(`${di}-${pi}`)
                    return <td key={di} onClick={() => toggle(di,pi)} className={`border-b border-r last:border-r-0 text-center cursor-pointer select-none transition-all ${isBlocked ? 'bg-red-100 hover:bg-red-200' : 'bg-green-50 hover:bg-green-100'}`} style={{width:52,height:36}}>
                      {isBlocked ? <span className="text-red-500 font-bold text-sm">✕</span> : <span className="text-green-500 text-sm">✓</span>}
                    </td>
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">🟥 Red = unavailable · 🟩 Green = available · {unavailable.length} slot{unavailable.length!==1?'s':''} blocked</p>
    </div>
  )
}

export function TeachersPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Teacher | null>(null)
  const [form, setForm] = useState({ name:'', email:'', subjects:[] as string[], max_per_day:6, max_per_week:30, unavailable:[] as [number,number][], color:'#6366f1' })
  const [subjectsInput, setSubjectsInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('details')

  const days = institution?.day_labels || ['Mon','Tue','Wed','Thu','Fri']
  const nPeriods = institution?.periods_per_day || 7
  const periodLabels = institution?.period_labels?.length ? institution.period_labels : Array.from({length:nPeriods},(_,i) => `P${i+1}`)

  const load = async () => {
    if (!instId) return
    try { setTeachers(await api.listTeachers(instId) as Teacher[]) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [instId])

  const openAdd = () => { setEditing(null); setForm({name:'',email:'',subjects:[],max_per_day:6,max_per_week:30,unavailable:[],color:COLORS[teachers.length%COLORS.length]}); setSubjectsInput(''); setActiveTab('details'); setOpen(true) }
  const openEdit = (t: Teacher) => { setEditing(t); setForm({name:t.name,email:t.email,subjects:t.subjects,max_per_day:t.max_per_day,max_per_week:t.max_per_week,unavailable:t.unavailable as [number,number][],color:t.color}); setSubjectsInput(t.subjects.join(', ')); setActiveTab('details'); setOpen(true) }

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Name required'); return }
    setSaving(true)
    const payload = { ...form, subjects: subjectsInput.split(',').map(s=>s.trim()).filter(Boolean) }
    try {
      if (editing) { const u = await api.updateTeacher(editing.id, payload); setTeachers(ts => ts.map(t => t.id===editing.id ? u as Teacher : t)); toast.success('Updated') }
      else { const c = await api.createTeacher(instId, payload); setTeachers(ts => [...ts, c as Teacher]); toast.success('Added') }
      setOpen(false)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false) }
  }

  const handleDelete = async (t: Teacher) => {
    if (!confirm(`Delete "${t.name}"?`)) return
    try { await api.deleteTeacher(t.id); setTeachers(ts => ts.filter(x => x.id!==t.id)); toast.success('Deleted') }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <Layout title="Faculty" subtitle={`${teachers.length} faculty member${teachers.length!==1?'s':''}`}
      actions={<Button onClick={openAdd} className="gap-2"><Plus className="w-4 h-4" />Add faculty</Button>}>
      <div className="p-8">
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
          : teachers.length === 0 ? (
            <div className="text-center py-20 text-muted-foreground">
              <UserCircle2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="mb-4">No faculty yet.</p>
              <Button onClick={openAdd} variant="outline" className="gap-2"><Plus className="w-4 h-4" />Add first faculty member</Button>
            </div>
          ) : (
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Subjects</TableHead>
                    <TableHead>Max/day</TableHead><TableHead>Max/week</TableHead><TableHead>Availability</TableHead><TableHead className="w-20"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {teachers.map(t => (
                    <TableRow key={t.id}>
                      <TableCell><div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{backgroundColor:t.color}} /><span className="font-medium">{t.name}</span></div></TableCell>
                      <TableCell className="text-muted-foreground text-sm">{t.email||'—'}</TableCell>
                      <TableCell><div className="flex gap-1 flex-wrap max-w-[180px]">{t.subjects.slice(0,3).map(s=><Badge key={s} variant="secondary" className="text-xs">{s}</Badge>)}{t.subjects.length>3&&<Badge variant="outline" className="text-xs">+{t.subjects.length-3}</Badge>}{t.subjects.length===0&&<span className="text-xs text-muted-foreground">All</span>}</div></TableCell>
                      <TableCell>{t.max_per_day}</TableCell><TableCell>{t.max_per_week}</TableCell>
                      <TableCell>{t.unavailable.length===0 ? <span className="text-xs text-green-600">Fully available</span> : <button className="text-xs text-amber-600 hover:underline flex items-center gap-1" onClick={() => openEdit(t)}><Grid3x3 className="w-3 h-3" />{t.unavailable.length} slots blocked</button>}</TableCell>
                      <TableCell><div className="flex gap-1.5"><Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(t)}><Pencil className="w-3.5 h-3.5" /></Button><Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => handleDelete(t)}><Trash2 className="w-3.5 h-3.5" /></Button></div></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? `Edit: ${editing.name}` : 'Add faculty member'}</DialogTitle>
            <DialogDescription>Details on first tab. Block unavailable slots on Availability tab.</DialogDescription>
          </DialogHeader>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full">
              <TabsTrigger value="details" className="flex-1">Details</TabsTrigger>
              <TabsTrigger value="availability" className="flex-1">Availability{form.unavailable.length > 0 && <Badge variant="destructive" className="ml-2 text-[10px] h-4 px-1">{form.unavailable.length}</Badge>}</TabsTrigger>
            </TabsList>
            <TabsContent value="details" className="space-y-4 pt-2">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5 col-span-2"><Label>Full name *</Label><Input value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} placeholder="Dr. Priya Sharma" /></div>
                <div className="space-y-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={e=>setForm(f=>({...f,email:e.target.value}))} placeholder="priya@college.edu" /></div>
                <div className="space-y-1.5"><Label>Color</Label>
                  <div className="flex items-center gap-2">
                    <input type="color" value={form.color} onChange={e=>setForm(f=>({...f,color:e.target.value}))} className="w-9 h-9 rounded cursor-pointer border" />
                    <div className="flex gap-1 flex-wrap">{COLORS.map(c => <button key={c} className={`w-5 h-5 rounded-full border-2 ${form.color===c?'border-primary scale-110':'border-transparent'}`} style={{backgroundColor:c}} onClick={()=>setForm(f=>({...f,color:c}))} />)}</div>
                  </div>
                </div>
              </div>
              <div className="space-y-1.5"><Label>Subject expertise (comma-separated)</Label><Input value={subjectsInput} onChange={e=>setSubjectsInput(e.target.value)} placeholder="Data Structures, Database Management" /><p className="text-xs text-muted-foreground">Leave blank = can teach any subject.</p></div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5"><Label>Max lectures/day</Label><Input type="number" min={1} max={12} value={form.max_per_day} onChange={e=>setForm(f=>({...f,max_per_day:+e.target.value}))} /><p className="text-xs text-muted-foreground">Typical: 4–6</p></div>
                <div className="space-y-1.5"><Label>Max lectures/week</Label><Input type="number" min={1} max={50} value={form.max_per_week} onChange={e=>setForm(f=>({...f,max_per_week:+e.target.value}))} /><p className="text-xs text-muted-foreground">Typical: 18–24</p></div>
              </div>
            </TabsContent>
            <TabsContent value="availability" className="pt-2">
              <div className="mb-3 p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800">Block unavailable slots — the solver will never schedule this faculty member during blocked slots.</div>
              <AvailabilityGrid days={days} periods={nPeriods} periodLabels={periodLabels} unavailable={form.unavailable} onChange={slots => setForm(f=>({...f,unavailable:slots}))} />
            </TabsContent>
          </Tabs>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.name.trim()}>{saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}{editing ? 'Save changes' : 'Add faculty'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  )
}
