import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Loader2, BookOpen, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api } from '@/lib/api'
import type { Subject } from '@/types'

const COLORS = ['#3b82f6','#8b5cf6','#ec4899','#f97316','#22c55e','#06b6d4','#eab308','#f43f5e','#14b8a6','#a855f7']
const QUICK_SUBJECTS = [
  {name:'Mathematics',room_type:'classroom',lessons_per_week:4,color:'#3b82f6',has_lab:false},
  {name:'Physics',room_type:'classroom',lessons_per_week:3,color:'#6366f1',has_lab:true},
  {name:'Chemistry',room_type:'classroom',lessons_per_week:3,color:'#8b5cf6',has_lab:true},
  {name:'English',room_type:'classroom',lessons_per_week:3,color:'#f97316',has_lab:false},
  {name:'Data Structures',room_type:'classroom',lessons_per_week:4,color:'#22c55e',has_lab:true},
  {name:'Database Management',room_type:'classroom',lessons_per_week:3,color:'#14b8a6',has_lab:true},
  {name:'Operating Systems',room_type:'classroom',lessons_per_week:4,color:'#06b6d4',has_lab:true},
  {name:'Computer Networks',room_type:'classroom',lessons_per_week:4,color:'#ec4899',has_lab:true},
  {name:'Physical Education',room_type:'field',lessons_per_week:2,color:'#84cc16',has_lab:false},
]

export function SubjectsPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Subject | null>(null)
  const [form, setForm] = useState({ name:'', room_type:'classroom', color:'#8b5cf6', lessons_per_week:4, allow_double:false, has_lab:false })
  const [saving, setSaving] = useState(false)
  const [bulkLoading, setBulkLoading] = useState(false)

  const load = async () => {
    if (!instId) return
    try { setSubjects(await api.listSubjects(instId) as Subject[]) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [instId])

  const openAdd = () => { setEditing(null); setForm({ name:'', room_type:'classroom', color:COLORS[subjects.length % COLORS.length], lessons_per_week:4, allow_double:false, has_lab:false }); setOpen(true) }
  const openEdit = (s: Subject) => { setEditing(s); setForm({ name:s.name, room_type:s.room_type, color:s.color, lessons_per_week:s.lessons_per_week, allow_double:s.allow_double, has_lab:false }); setOpen(true) }

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Name required'); return }
    setSaving(true)
    const { has_lab, ...payload } = form
    try {
      if (editing) { const u = await api.updateSubject(editing.id, payload); setSubjects(ss => ss.map(s => s.id===editing.id ? u as Subject : s)); toast.success('Updated'); setOpen(false) }
      else {
        const s = await api.createSubject(instId, payload) as Subject
        const newSubjs = [s]
        if (has_lab && form.room_type !== 'lab') {
          const lab = await api.createSubject(instId, { name:`${form.name} Lab`, room_type:'lab', color:form.color, lessons_per_week:1, allow_double:true }) as Subject
          newSubjs.push(lab)
          toast.success(`Added "${s.name}" + "${lab.name}"`)
        } else { toast.success('Subject added') }
        setSubjects(ss => [...ss, ...newSubjs]); setOpen(false)
      }
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false) }
  }

  const handleDelete = async (s: Subject) => {
    if (!confirm(`Delete "${s.name}"?`)) return
    try { await api.deleteSubject(s.id); setSubjects(ss => ss.filter(x => x.id!==s.id)); toast.success('Deleted') }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleBulkAdd = async () => {
    setBulkLoading(true)
    const existing = new Set(subjects.map(s => s.name.toLowerCase()))
    const toAdd = QUICK_SUBJECTS.filter(qs => !existing.has(qs.name.toLowerCase()))
    if (!toAdd.length) { toast('All quick subjects already exist'); setBulkLoading(false); return }
    try {
      const created: Subject[] = []
      for (const qs of toAdd) {
        const s = await api.createSubject(instId, { name:qs.name, room_type:qs.room_type as Subject['room_type'], color:qs.color, lessons_per_week:qs.lessons_per_week, allow_double:false }) as Subject
        created.push(s)
        if (qs.has_lab) { const lab = await api.createSubject(instId, { name:`${qs.name} Lab`, room_type:'lab', color:qs.color, lessons_per_week:1, allow_double:true }) as Subject; created.push(lab) }
      }
      setSubjects(ss => [...ss, ...created]); toast.success(`Added ${created.length} subjects`)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setBulkLoading(false) }
  }

  const TYPE_BADGE: Record<string,string> = { classroom:'bg-blue-50 text-blue-700', lab:'bg-purple-50 text-purple-700', field:'bg-green-50 text-green-700', hall:'bg-orange-50 text-orange-700' }
  const theory = subjects.filter(s => s.room_type!=='lab')
  const labs = subjects.filter(s => s.room_type==='lab')

  return (
    <Layout title="Subjects" subtitle={`${subjects.length} — ${theory.length} theory, ${labs.length} lab`}
      actions={<div className="flex gap-2">
        <Button variant="outline" onClick={handleBulkAdd} disabled={bulkLoading} className="gap-2">{bulkLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}Add engineering subjects</Button>
        <Button onClick={openAdd} className="gap-2"><Plus className="w-4 h-4" />Add subject</Button>
      </div>}>
      <div className="p-8 space-y-6">
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
          : subjects.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground space-y-4">
              <BookOpen className="w-12 h-12 mx-auto opacity-30" />
              <p>No subjects yet.</p>
              <div className="flex gap-3 justify-center">
                <Button onClick={handleBulkAdd} disabled={bulkLoading} className="gap-2">{bulkLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}Add engineering subjects</Button>
                <Button variant="outline" onClick={openAdd}>Add manually</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {theory.length > 0 && (
                <div>
                  <h2 className="font-semibold mb-3 flex items-center gap-2">📚 Theory / Lecture <Badge variant="secondary">{theory.length}</Badge></h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {theory.map(s => (
                      <div key={s.id} className="flex items-start justify-between p-4 rounded-xl border bg-background hover:shadow-sm">
                        <div><div className="flex items-center gap-2 mb-1"><div className="w-3 h-3 rounded-full" style={{backgroundColor:s.color}} /><p className="font-medium text-sm">{s.name}</p></div>
                          <div className="flex items-center gap-1.5"><Badge className={`${TYPE_BADGE[s.room_type]||''} text-[10px]`}>{s.room_type}</Badge><span className="text-xs text-muted-foreground">{s.lessons_per_week}×/wk</span></div>
                        </div>
                        <div className="flex gap-1 ml-2"><Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEdit(s)}><Pencil className="w-3 h-3" /></Button><Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => handleDelete(s)}><Trash2 className="w-3 h-3" /></Button></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {labs.length > 0 && (
                <div>
                  <h2 className="font-semibold mb-3 flex items-center gap-2">🔬 Lab / Practical <Badge variant="secondary">{labs.length}</Badge></h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {labs.map(s => (
                      <div key={s.id} className="flex items-start justify-between p-4 rounded-xl border bg-background hover:shadow-sm">
                        <div><div className="flex items-center gap-2 mb-1"><div className="w-3 h-3 rounded-full" style={{backgroundColor:s.color}} /><p className="font-medium text-sm">{s.name}</p></div>
                          <div className="flex items-center gap-1.5"><Badge className="bg-purple-50 text-purple-700 text-[10px]">lab</Badge><span className="text-xs text-muted-foreground">{s.lessons_per_week}×/wk</span>{s.allow_double && <Badge variant="outline" className="text-[10px] px-1">2-period</Badge>}</div>
                        </div>
                        <div className="flex gap-1 ml-2"><Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEdit(s)}><Pencil className="w-3 h-3" /></Button><Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => handleDelete(s)}><Trash2 className="w-3 h-3" /></Button></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Edit subject' : 'Add subject'}</DialogTitle>{!editing && <DialogDescription>Enable "Has lab component" to auto-create a paired Lab subject.</DialogDescription>}</DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5"><Label>Subject name *</Label><Input value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} placeholder="Data Structures, Physics" /></div>
            <div className="space-y-1.5"><Label>Room type</Label>
              <Select value={form.room_type} onValueChange={v=>setForm(f=>({...f,room_type:v}))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="classroom">Classroom (lecture)</SelectItem>
                  <SelectItem value="lab">Laboratory (practical)</SelectItem>
                  <SelectItem value="field">Sports Field</SelectItem>
                  <SelectItem value="hall">Seminar Hall</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5"><Label>Lectures per week</Label><Input type="number" min={1} max={12} value={form.lessons_per_week} onChange={e=>setForm(f=>({...f,lessons_per_week:+e.target.value}))} /></div>
            {form.room_type==='classroom' && !editing && (
              <div className="flex items-start gap-3 p-3 rounded-lg border bg-purple-50/50">
                <Switch id="has-lab" checked={form.has_lab} onCheckedChange={v=>setForm(f=>({...f,has_lab:v}))} className="mt-0.5" />
                <div><Label htmlFor="has-lab" className="cursor-pointer font-medium">🔬 Has lab component</Label><p className="text-xs text-muted-foreground mt-0.5">Auto-creates "{form.name||'Subject'} Lab" (room: lab, 1×/wk, 2-period)</p></div>
              </div>
            )}
            <div className="flex items-center gap-3"><Switch checked={form.allow_double} onCheckedChange={v=>setForm(f=>({...f,allow_double:v}))} /><Label>Allow double periods</Label></div>
            <div className="space-y-1.5"><Label>Color</Label>
              <div className="flex items-center gap-3">
                <input type="color" value={form.color} onChange={e=>setForm(f=>({...f,color:e.target.value}))} className="w-10 h-10 rounded cursor-pointer border" />
                <div className="flex gap-1.5 flex-wrap">{COLORS.map(c => <button key={c} className={`w-6 h-6 rounded-full border-2 ${form.color===c?'border-primary scale-110':'border-transparent'}`} style={{backgroundColor:c}} onClick={()=>setForm(f=>({...f,color:c}))} />)}</div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={()=>setOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.name.trim()}>{saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}{editing ? 'Update' : form.has_lab ? 'Add + lab' : 'Add'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  )
}
