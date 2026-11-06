import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ShieldAlert } from 'lucide-react'
import { Button, Card, EmptyState, ErrorState, Field, Modal, SectionHeading, Select, SkeletonRows, Textarea } from '@/components/ui'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { useGet } from '@/lib/query'
import { CATEGORIAS_RISCO } from '@/lib/format'

type Risco = { id: string; codigo: string; titulo: string; descricao: string; base_legal: string; severidade: 'ALTO' | 'MEDIO' | 'BAIXO'; categoria: string; funcionario?: string; employee_id?: string; document_id?: string; referencia?: string; justificativa?: string }

export function RiscosPage() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const [status, setStatus] = useState('ABERTO')
  const [selected, setSelected] = useState<Risco | null>(null)
  const [justificativa, setJustificativa] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const r = useGet<{ resumo: { alto: number; medio: number; baixo: number }; items: Risco[] }>('/risks', { status })
  const ignore = async () => {
    if (!selected) return
    setBusy(true); setErr('')
    try {
      await api(`/risks/${selected.id}/ignore`, { method: 'POST', body: { justificativa } })
      setSelected(null); setJustificativa('')
      qc.invalidateQueries({ queryKey: ['/risks'] })
      qc.invalidateQueries({ queryKey: ['/metrics/overview'] })
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return <div>
    <SectionHeading eyebrow="Análise documental" title="Indicadores de risco trabalhista">Sinais para conferência do RH e do jurídico. Cada indicador mostra o documento, a divergência e a referência aplicável; a leitura automática não conclui que houve infração.</SectionHeading>
    <div className="mb-4 grid gap-3 sm:grid-cols-3">
      {([['alto', 'Alto', 'text-danger'], ['medio', 'Médio', 'text-warning'], ['baixo', 'Baixo', 'text-brand']] as const).map(([key, label, tone]) =>
        <Card key={key}><p className="text-xs text-muted-foreground">{label}</p><p className={`text-2xl font-bold ${tone}`}>{r.data?.resumo?.[key] ?? 0}</p></Card>)}
    </div>
    <Select aria-label="Status dos indicadores" className="mb-4 !w-52" value={status} onChange={(e) => setStatus(e.target.value)}><option value="ABERTO">Em aberto</option><option value="IGNORADO">Ignorados</option></Select>
    {r.error ? <ErrorState error={r.error} retry={r.refetch} /> : r.isLoading ? <SkeletonRows /> : !r.data?.items?.length ? <EmptyState icon={<ShieldAlert className="h-5 w-5" />} title="Nenhum indicador nesta lista" /> :
      <ul className="space-y-3">{r.data.items.map((x) => <li key={x.id}>
        <Card><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex-1"><p className="flex items-center gap-2 font-semibold text-brand-darker"><AlertTriangle className={x.severidade === 'ALTO' ? 'h-4 w-4 text-danger' : 'h-4 w-4 text-warning'} />{x.titulo}<span className="rounded bg-muted px-2 py-0.5 text-xs">{x.severidade}</span></p>
          <p className="mt-1 text-sm">{x.descricao}</p><p className="mt-1 text-xs text-muted-foreground">{CATEGORIAS_RISCO[x.categoria] ?? x.categoria} · {x.base_legal}{x.referencia ? ` · ${x.referencia}` : ''}</p>
          <div className="mt-2 flex gap-3 text-sm">{x.employee_id && <Link to={`/app/funcionarios/${x.employee_id}`} className="font-medium text-brand underline">{x.funcionario ?? 'Funcionário'}</Link>}{x.document_id && <Link to={`/app/documentos/${x.document_id}`} className="font-medium text-brand underline">Ver documento</Link>}</div>
          {x.justificativa && <p className="mt-2 text-xs text-muted-foreground">Justificativa: {x.justificativa}</p>}</div>
          {status === 'ABERTO' && user?.role === 'ADMIN_EMPRESA' && <Button size="sm" onClick={() => { setSelected(x); setErr('') }}>Ignorar com justificativa</Button>}</div></Card>
      </li>)}</ul>}
    <Modal open={!!selected} onClose={() => setSelected(null)} eyebrow="Indicador" title="Ignorar sinal" footer={<><Button onClick={() => setSelected(null)}>Cancelar</Button><Button variant="primary" disabled={justificativa.trim().length < 5} loading={busy} onClick={ignore}>Registrar justificativa</Button></>}>
      <p className="mb-3 text-sm text-muted-foreground">O motivo fica registrado na auditoria e o indicador sai da lista de abertos.</p>
      <Field label="Justificativa" error={err}>{(id) => <Textarea id={id} value={justificativa} onChange={(e) => setJustificativa(e.target.value)} />}</Field>
    </Modal>
  </div>
}
