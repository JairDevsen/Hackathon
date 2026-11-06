import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Button, Field, Input, Modal, Select, Textarea } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { SchemaForm } from './Review'

// campos que têm entrada própria no formulário (não repetem no formulário do tipo)
const PROPRIOS = new Set(['data_documento', 'validade_ate', 'competencia', 'cpf'])

/** Lança um documento escrevendo as informações (formulário do tipo), sem imagem. Alimenta os indicadores; não comprova a exigência. */
export function ManualDocModal({ employeeId, open, onClose }: { employeeId: string; open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const { can } = useAuth()
  const types = useGet<any[]>(open ? '/document-types' : null)
  const [tipo, setTipo] = useState('')
  const [campos, setCampos] = useState<Record<string, any>>({})
  const [f, setF] = useState({ data_documento: '', competencia: '', validade_ate: '', observacao: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const schema = useGet<any>(open && tipo ? `/document-types/${tipo}/schema` : null)
  const opcoes = useMemo(() => (types.data ?? []).filter((t) => t.escopo === 'FUNCIONARIO' && (!t.sensivel_saude || can('saude:ler'))), [types.data, can])
  const formSchema = useMemo(() => {
    const props = Object.fromEntries(Object.entries<any>(schema.data?.properties ?? {}).filter(([k]) => !PROPRIOS.has(k)))
    return { ...(schema.data ?? {}), properties: props }
  }, [schema.data])
  useEffect(() => { setCampos({}) }, [tipo])
  const reset = () => { setTipo(''); setCampos({}); setF({ data_documento: '', competencia: '', validade_ate: '', observacao: '' }); setErr('') }
  const mensal = ['HOLERITE', 'CARTAO_PONTO', 'RECIBO_BENEFICIOS'].includes(tipo)
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      await api(`/employees/${employeeId}/documents/manual`, { method: 'POST', body: { tipo, campos, ...f } })
      for (const k of [`/employees/${employeeId}/documents`, `/employees/${employeeId}`, `/employees/${employeeId}/compliance`, '/risks', '/metrics/overview']) qc.invalidateQueries({ queryKey: [k] })
      reset(); onClose()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal wide open={open} onClose={() => { reset(); onClose() }} eyebrow="Dossiê" title="Lançar documento manualmente"
      footer={<><Button onClick={() => { reset(); onClose() }}>Cancelar</Button><Button variant="primary" loading={busy} disabled={!tipo} onClick={submit}>Lançar documento</Button></>}>
      <p className="mb-3 rounded-lg bg-warning-bg p-2 text-sm text-warning">Sem imagem anexada, o lançamento fica identificado como <b>manual</b>: ele alimenta os indicadores de risco (por exemplo, a data do TRCT), mas <b>não comprova</b> a exigência documental. Sempre que possível, envie também a cópia legível.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Tipo de documento *">{(id) => <Select id={id} value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="">Selecione…</option>{opcoes.map((t) => <option key={t.codigo} value={t.codigo}>{t.nome}</option>)}</Select>}</Field>
        <Field label="Data do documento">{(id) => <Input id={id} type="date" value={f.data_documento} onChange={(e) => setF({ ...f, data_documento: e.target.value })} />}</Field>
        {mensal && <Field label="Competência (mês)">{(id) => <Input id={id} type="month" value={f.competencia} onChange={(e) => setF({ ...f, competencia: e.target.value })} />}</Field>}
        <Field label="Validade até">{(id) => <Input id={id} type="date" value={f.validade_ate} onChange={(e) => setF({ ...f, validade_ate: e.target.value })} />}</Field>
      </div>
      {tipo && <div className="mt-4"><p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Informações do documento</p>
        {schema.isLoading ? <p className="text-sm text-muted-foreground">Carregando formulário…</p> : <SchemaForm schema={formSchema} value={campos} onChange={setCampos} />}</div>}
      <div className="mt-4"><Field label="Observação">{(id) => <Textarea id={id} value={f.observacao} onChange={(e) => setF({ ...f, observacao: e.target.value })} />}</Field></div>
      {err && <p role="alert" className="mt-3 rounded-lg bg-danger-bg p-2 text-sm text-danger">{err}</p>}
    </Modal>
  )
}
