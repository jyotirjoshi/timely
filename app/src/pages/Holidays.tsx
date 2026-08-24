import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Trash2, Loader2, CalendarDays, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Layout } from '@/components/Layout'
import { useApp } from '@/lib/store'
import { holidayApi } from '@/lib/api'
import type { Holiday } from '@/types'

const TYPE_COLORS: Record<string, string> = {
  national: 'bg-orange-100 text-orange-700', state: 'bg-blue-100 text-blue-700',
  school: 'bg-purple-100 text-purple-700', optional: 'bg-gray-100 text-gray-600',
}
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export function HolidaysPage() {
  const { institution, user } = useApp()
  const instId = institution?.id || user?.institution_id || ''
  const [holidays, setHolidays] = useState<Holiday[]>([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ date: '', name: '', type: 'school' })
  const [saving, setSaving] = useState(false)
  const [seeding, setSeeding] = useState(false)

  const load = async () => {
    if (!instId) return
    try { setHolidays(await holidayApi.list(instId) as Holiday[]) }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [instId])

  const handleAdd = async () => {
    if (!form.date || !form.name) { toast.error('Date and name required'); return }
    setSaving(true)
    try {
      const h = await holidayApi.create(instId, form) as Holiday
      setHolidays(hs => [...hs, h].sort((a, b) => a.date.localeCompare(b.date)))
      toast.success('Holiday added'); setOpen(false); setForm({ date: '', name: '', type: 'school' })
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    try { await holidayApi.delete(id); setHolidays(hs => hs.filter(h => h.id !== id)); toast.success('Deleted') }
    catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const handleSeedIndia = async () => {
    setSeeding(true)
    try {
      const res = await holidayApi.seedIndia(instId, new Date().getFullYear()) as any
      toast.success(res.message); await load()
    } catch (e: unknown) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setSeeding(false) }
  }

  const byMonth: Record<string, Holiday[]> = {}
  holidays.forEach(h => { const m = h.date.slice(0, 7); if (!byMonth[m]) byMonth[m] = []; byMonth[m].push(h) })

  return (
    <Layout title="Holidays & Calendar" subtitle={`${holidays.length} total`}
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleSeedIndia} disabled={seeding} className="gap-2">
            {seeding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}Load India Holidays
          </Button>
          <Button onClick={() => setOpen(true)} className="gap-2"><Plus className="w-4 h-4" />Add</Button>
        </div>
      }>
      <div className="p-8 space-y-6">
        <div className="flex gap-3 flex-wrap">{Object.entries(TYPE_COLORS).map(([type, cls]) => <Badge key={type} className={cls}>{type}</Badge>)}</div>
        {loading ? <div className="flex justify-center py-20"><Loader2 className="w-8 h-8 animate-spin text-muted-foreground" /></div>
          : holidays.length === 0 ? (
            <div className="text-center py-20 text-muted-foreground">
              <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm mb-4">No holidays yet.</p>
              <Button onClick={handleSeedIndia} disabled={seeding} variant="outline">Load Indian National Holidays</Button>
            </div>
          ) : Object.entries(byMonth).map(([month, mh]) => {
            const [y, m] = month.split('-')
            return (
              <Card key={month}>
                <CardHeader className="pb-2"><CardTitle className="text-base">{MONTHS[parseInt(m)-1]} {y}</CardTitle><CardDescription>{mh.length} holiday{mh.length !== 1 ? 's' : ''}</CardDescription></CardHeader>
                <CardContent className="pt-0">
                  {mh.map(h => (
                    <div key={h.id} className="flex items-center gap-3 py-1.5 border-b last:border-0">
                      <span className="text-sm font-mono text-muted-foreground w-8">{h.date.slice(8)}</span>
                      <span className="flex-1 text-sm font-medium">{h.name}</span>
                      <Badge className={TYPE_COLORS[h.type] || ''}>{h.type}</Badge>
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => handleDelete(h.id)}><Trash2 className="w-3 h-3" /></Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )
          })}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add holiday</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5"><Label>Date *</Label><Input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>Name *</Label><Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Diwali" /></div>
            <div className="space-y-1.5"><Label>Type</Label>
              <Select value={form.type} onValueChange={v => setForm(f => ({ ...f, type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="national">National</SelectItem>
                  <SelectItem value="state">State</SelectItem>
                  <SelectItem value="school">School / College</SelectItem>
                  <SelectItem value="optional">Optional</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={handleAdd} disabled={saving || !form.date || !form.name}>{saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}Add</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Layout>
  )
}
