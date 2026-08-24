import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Loader2, DoorOpen, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Card, CardContent } from '@/components/ui/card'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { api } from '@/lib/api'
import type { Room } from '@/types'

const TEMPLATES = [
  { name:'Lecture Hall 101',type:'classroom',capacity:60,features:['projector','ac']},
  { name:'Lecture Hall 102',type:'classroom',capacity:60,features:['projector','ac']},
  { name:'Lecture Hall 103',type:'classroom',capacity:60,features:['projector','ac']},
  { name:'Computer Lab 1',type:'lab',capacity:30,features:['computers','ac']},
  { name:'Computer Lab 2',type:'lab',capacity:30,features:['computers','ac']},
  { name:'Physics Lab',type:'lab',capacity:30,features:['equipment']},
  { name:'Chemistry Lab',type:'lab',capacity:30,features:['equipment','ventilation']},
  { name:'Electronics Lab',type:'lab',capacity:30,features:['equipment','ac']},
  { name:'Seminar Hall',type:'hall',capacity:100,features:['projector','ac','mic']},
  { name:'Sports Ground',type:'field',capacity:200,features:[]},
]
const TYPE_COLORS: Record<string,string> = { classroom:'bg-blue-100 text-blue-700', lab:'bg-purple-100 text-purple-700', field:'bg-green-100 text-green-700', hall:'bg-orange-100 text-orange-700' }
const TYPE_ICONS: Record<string,string> = { classroom:'🏫', lab:'🔬', field:'⚽', hall:'🎭' }
const ROOM_TYPES = [
  {value:'classroom',label:'Classroom / Lecture Hall'},
  {value:'lab',label:'Laboratory'},
  {value:'field',label:'Sports Field / Ground'},
  {value:'hall',label:'Seminar Hall / Auditorium'},
]

export function RoomsPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const [rooms, setRooms] = useState<Room[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Room | null>(null)
  const [form, setForm] = useState({ name:'', type:'classroom', capacity:60, features:[] as string[] })
  const [featInput, setFeatInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [bulkLoading, setBulkLoading] = useState(false)

  const load = async () => {
    if (!instId) return
    try { setRooms(await api.listRooms(instId) as Room[]) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [instId])

  const openAdd = () => { setEditing(null); setForm({ name:'',type:'classroom',capacity:60,features:[] }); setFeatInput(''); setOpen(true) }
  const openEdit = (r: Room) => { setEditing(r); setForm({ name:r.name,type:r.type,capacity:r.capacity,features:r.features }); setFeatInput(r.features.join(', ')); setOpen(true) }

  const handleSave = async () => {
    setSaving(true)
    const payload = { ...form, features: featInput.split(',').map(f=>f.trim()).filter(Boolean) }
    try {
      if (editing) { const u = await api.updateRoom(editing.id, payload); setRooms(rs => rs.map(r => r.id===editing.id ? u as Room : r)); toast.success('Updated') }
      else { const c = await api.createRoom(instId, payload); setRooms(rs => [...rs, c as Room]); toast.success('Added') }
      setOpen(false)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false) }
  }

  const handleDelete = async (r: Room) => {
    if (!confirm(`Delete "${r.name}"?`)) return
    try { await api.deleteRoom(r.id); setRooms(rs => rs.filter(x => x.id!==r.id)); toast.success('Deleted') }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleAddAll = async () => {
    setBulkLoading(true)
    const existing = new Set(rooms.map(r => r.name.toLowerCase()))
    const toAdd = TEMPLATES.filter(t => !existing.has(t.name.toLowerCase()))
    if (!toAdd.length) { toast('All templates already added'); setBulkLoading(false); return }
    try {
      const added: Room[] = []
      for (const t of toAdd) { const c = await api.createRoom(instId, t) as Room; added.push(c) }
      setRooms(rs => [...rs, ...added]); toast.success(`Added ${added.length} rooms`)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setBulkLoading(false) }
  }

  const grouped = ROOM_TYPES.map(t => ({ ...t, rooms: rooms.filter(r => r.type===t.value) }))

  return (
    <Layout title="Rooms & Labs" subtitle={`${rooms.length} rooms — ${rooms.filter(r=>r.type==='lab').length} labs`}
      actions={<div className="flex gap-2">
        <Button variant="outline" onClick={handleAddAll} disabled={bulkLoading} className="gap-2">{bulkLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}Add college rooms</Button>
        <Button onClick={openAdd} className="gap-2"><Plus className="w-4 h-4" />Add room</Button>
      </div>}>
      <div className="p-8">
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
          : rooms.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <DoorOpen className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="mb-4">No rooms yet.</p>
              <Button onClick={handleAddAll} disabled={bulkLoading} className="gap-2">{bulkLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}Add all college rooms</Button>
            </div>
          ) : (
            <div className="space-y-6">
              {grouped.filter(g => g.rooms.length > 0).map(group => (
                <div key={group.value}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-lg">{TYPE_ICONS[group.value]}</span>
                    <h2 className="font-semibold">{group.label}</h2>
                    <Badge variant="secondary">{group.rooms.length}</Badge>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {group.rooms.map(r => (
                      <Card key={r.id} className="hover:shadow-sm transition-shadow">
                        <CardContent className="p-4 flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <p className="font-medium text-sm">{r.name}</p>
                              <Badge className={`${TYPE_COLORS[r.type]||''} text-[10px]`}>{r.type}</Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">Capacity: {r.capacity}</p>
                            {r.features.length > 0 && <div className="flex gap-1 flex-wrap mt-1">{r.features.map(f => <Badge key={f} variant="outline" className="text-[10px] px-1.5 py-0">{f}</Badge>)}</div>}
                          </div>
                          <div className="flex gap-1 ml-2">
                            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEdit(r)}><Pencil className="w-3 h-3" /></Button>
                            <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => handleDelete(r)}><Trash2 className="w-3 h-3" /></Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Edit room' : 'Add room'}</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5"><Label>Name *</Label><Input value={form.name} onChange={e => setForm(f=>({...f,name:e.target.value}))} placeholder="Computer Lab 1" /></div>
            <div className="space-y-1.5"><Label>Type</Label>
              <Select value={form.type} onValueChange={v => setForm(f=>({...f,type:v}))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{ROOM_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{TYPE_ICONS[t.value]} {t.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5"><Label>Capacity</Label><Input type="number" min={1} value={form.capacity} onChange={e => setForm(f=>({...f,capacity:+e.target.value}))} /></div>
            <div className="space-y-1.5"><Label>Features (comma-separated)</Label><Input value={featInput} onChange={e => setFeatInput(e.target.value)} placeholder="projector, ac, computers" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.name}>{saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}{editing ? 'Update' : 'Add'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  )
}
