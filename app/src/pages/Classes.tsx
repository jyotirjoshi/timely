import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, Loader2, GraduationCap, Zap } from 'lucide-react'
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
import type { Class } from '@/types'

type BatchType = 'Engineering' | 'Science' | 'Commerce' | 'Arts' | 'School'
const BATCH_TEMPLATES: Record<BatchType, { years: string[]; divisions: string[] }> = {
  Engineering: { years: ['FE','SE','TE','BE'], divisions: ['A','B','C','D'] },
  Science:     { years: ['FY','SY','TY'],      divisions: ['A','B','C'] },
  Commerce:    { years: ['FY','SY','TY'],      divisions: ['A','B'] },
  Arts:        { years: ['FY','SY','TY'],      divisions: ['A','B'] },
  School:      { years: ['Grade 6','Grade 7','Grade 8','Grade 9','Grade 10','Grade 11','Grade 12'], divisions: ['A','B','C'] },
}
const YEAR_BADGE: Record<string,string> = { FE:'bg-blue-100 text-blue-700',SE:'bg-green-100 text-green-700',TE:'bg-amber-100 text-amber-700',BE:'bg-purple-100 text-purple-700',FY:'bg-blue-100 text-blue-700',SY:'bg-green-100 text-green-700',TY:'bg-amber-100 text-amber-700' }

export function ClassesPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const [classes, setClasses] = useState<Class[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Class | null>(null)
  const [form, setForm] = useState({ name:'', grade:'', size:60 })
  const [saving, setSaving] = useState(false)
  const [genOpen, setGenOpen] = useState(false)
  const [genType, setGenType] = useState<BatchType>('Engineering')
  const [genYears, setGenYears] = useState<string[]>(['FE','SE','TE','BE'])
  const [genDivs, setGenDivs] = useState<string[]>(['A','B'])
  const [genSize, setGenSize] = useState(60)
  const [genLoading, setGenLoading] = useState(false)

  const load = async () => {
    if (!instId) return
    try { setClasses(await api.listClasses(instId) as Class[]) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [instId])
  useEffect(() => { const t = BATCH_TEMPLATES[genType]; setGenYears(t.years.slice()); setGenDivs(t.divisions.slice(0,2)) }, [genType])

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Name required'); return }
    setSaving(true)
    try {
      if (editing) { const u = await api.updateClass(editing.id, form); setClasses(cs => cs.map(c => c.id===editing.id ? u as Class : c)); toast.success('Updated') }
      else { const c = await api.createClass(instId, form); setClasses(cs => [...cs, c as Class]); toast.success('Added') }
      setOpen(false)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false) }
  }

  const handleDelete = async (c: Class) => {
    if (!confirm(`Delete "${c.name}"?`)) return
    try { await api.deleteClass(c.id); setClasses(cs => cs.filter(x => x.id!==c.id)); toast.success('Deleted') }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleGenerate = async () => {
    if (!genYears.length || !genDivs.length) { toast.error('Select years and divisions'); return }
    setGenLoading(true)
    const existing = new Set(classes.map(c => c.name.toLowerCase()))
    const toCreate = genYears.flatMap(y => genDivs.map(d => ({ name:`${y}-${d}`, grade:y, size:genSize }))).filter(b => !existing.has(b.name.toLowerCase()))
    if (!toCreate.length) { toast('All selected batches already exist'); setGenLoading(false); return }
    try {
      const created: Class[] = []
      for (const b of toCreate) { const c = await api.createClass(instId, b) as Class; created.push(c) }
      setClasses(cs => [...cs, ...created]); toast.success(`Created ${created.length} batches`); setGenOpen(false)
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setGenLoading(false) }
  }

  const grouped: Record<string,Class[]> = {}
  classes.forEach(c => { const k = c.grade||'Other'; if (!grouped[k]) grouped[k]=[]; grouped[k].push(c) })

  return (
    <Layout title="Classes / Batches" subtitle={`${classes.length} batch${classes.length!==1?'es':''}`}
      actions={<div className="flex gap-2">
        <Button variant="outline" className="gap-2" onClick={() => setGenOpen(true)}><Zap className="w-4 h-4" />Generate batches</Button>
        <Button className="gap-2" onClick={() => { setEditing(null); setForm({name:'',grade:'',size:60}); setOpen(true) }}><Plus className="w-4 h-4" />Add batch</Button>
      </div>}>
      <div className="p-8">
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
          : classes.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">
              <GraduationCap className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="mb-4">No batches yet.</p>
              <Button onClick={() => setGenOpen(true)} className="gap-2"><Zap className="w-4 h-4" />Generate batches</Button>
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(grouped).map(([year, yClasses]) => (
                <div key={year}>
                  <div className="flex items-center gap-2 mb-3">
                    <Badge className={YEAR_BADGE[year]||'bg-gray-100 text-gray-700'}>{year}</Badge>
                    <span className="text-sm text-muted-foreground">{yClasses.length} batch{yClasses.length!==1?'es':''}</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                    {yClasses.map(c => (
                      <Card key={c.id} className="hover:shadow-sm">
                        <CardContent className="p-3">
                          <div className="flex items-start justify-between">
                            <div><p className="font-semibold text-sm">{c.name}</p><p className="text-xs text-muted-foreground">{c.size} students</p></div>
                            <div className="flex gap-0.5">
                              <button onClick={() => { setEditing(c); setForm({name:c.name,grade:c.grade,size:c.size}); setOpen(true) }} className="p-0.5 text-muted-foreground hover:text-foreground"><Pencil className="w-3 h-3" /></button>
                              <button onClick={() => handleDelete(c)} className="p-0.5 text-muted-foreground hover:text-destructive"><Trash2 className="w-3 h-3" /></button>
                            </div>
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

      {/* Add/Edit */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editing ? 'Edit batch' : 'Add batch'}</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5"><Label>Batch name *</Label><Input value={form.name} onChange={e=>setForm(f=>({...f,name:e.target.value}))} placeholder="SE-A, TE-B, Grade 10-A" /></div>
            <div className="space-y-1.5"><Label>Year / Grade</Label><Input value={form.grade} onChange={e=>setForm(f=>({...f,grade:e.target.value}))} placeholder="FE, SE, TE, BE, Grade 10" /></div>
            <div className="space-y-1.5"><Label>Size</Label><Input type="number" min={1} value={form.size} onChange={e=>setForm(f=>({...f,size:+e.target.value}))} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.name.trim()}>{saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}{editing ? 'Update' : 'Add'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate */}
      <Dialog open={genOpen} onOpenChange={setGenOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Generate batches</DialogTitle></DialogHeader>
          <div className="space-y-5 py-2">
            <div className="space-y-1.5"><Label>Programme type</Label>
              <Select value={genType} onValueChange={v => setGenType(v as BatchType)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Engineering">Engineering (FE/SE/TE/BE)</SelectItem>
                  <SelectItem value="Science">Science (FY/SY/TY)</SelectItem>
                  <SelectItem value="Commerce">Commerce (FY/SY/TY)</SelectItem>
                  <SelectItem value="Arts">Arts (FY/SY/TY)</SelectItem>
                  <SelectItem value="School">School (Grade 6–12)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2"><Label>Select years</Label>
              <div className="flex gap-2 flex-wrap">
                {BATCH_TEMPLATES[genType].years.map(y => (
                  <button key={y} onClick={() => setGenYears(ys => ys.includes(y) ? ys.filter(x=>x!==y) : [...ys,y])}
                    className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors ${genYears.includes(y) ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'}`}>{y}</button>
                ))}
              </div>
            </div>
            <div className="space-y-2"><Label>Select divisions</Label>
              <div className="flex gap-2 flex-wrap">
                {BATCH_TEMPLATES[genType].divisions.map(d => (
                  <button key={d} onClick={() => setGenDivs(ds => ds.includes(d) ? ds.filter(x=>x!==d) : [...ds,d])}
                    className={`w-10 h-10 rounded-lg border text-sm font-bold transition-colors ${genDivs.includes(d) ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'}`}>{d}</button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5"><Label>Batch size</Label><Input type="number" min={10} max={200} value={genSize} onChange={e=>setGenSize(+e.target.value)} /></div>
            {genYears.length > 0 && genDivs.length > 0 && (
              <div className="p-3 bg-muted/50 rounded-lg">
                <p className="text-xs font-medium mb-2 text-muted-foreground">Will create {genYears.length * genDivs.length} batches:</p>
                <div className="flex gap-1.5 flex-wrap">{genYears.flatMap(y => genDivs.map(d => <Badge key={`${y}-${d}`} variant="secondary" className="text-xs">{y}-{d}</Badge>))}</div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenOpen(false)}>Cancel</Button>
            <Button onClick={handleGenerate} disabled={genLoading || !genYears.length || !genDivs.length}>{genLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}Generate {genYears.length*genDivs.length} batches</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  )
}
