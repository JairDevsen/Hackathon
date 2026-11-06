import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCheck, ClipboardCheck, Scale, Scissors, Send, ShieldAlert, Merge, Trash2 } from 'lucide-react'
import { CompareModal } from '@/components/CompareModal'
import { problemas } from '@/lib/analise'
import { DocumentViewer } from '@/components/DocumentViewer'
import { EmployeePicker } from '@/components/EmployeePicker'
import { Button, Card, ConfidenceBar, EmptyState, ErrorState, Field, Input, Modal, SectionHeading, Select, SkeletonRows, StatusPill, Textarea, clsx } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api } from '@/lib/api'
import { MOTIVOS, cpfMask } from '@/lib/format'

/** Formulário gerado a partir do JSON Schema do tipo (campos simples: string/boolean/number). */
export function SchemaForm({ schema, value, onChange }: { schema: any; value: Record<string, any>; onChange: (v: Record<string, any>) => void }) {
  const props = Object.entries<any>(schema?.properties ?? {})
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {props.map(([k, p]) => (
        <Field key={k} label={(p.title ?? k).replaceAll('_', ' ')} hint={p.description}>
          {(id) => p.type === 'boolean' || p.anyOf?.some((x: any) => x.type === 'boolean')
            ? <Select id={id} value={String(value[k] ?? '')} onChange={(e) => onChange({ ...value, [k]: e.target.value === '' ? null : e.target.value === 'true' })}><option value="">—</option><option value="true">Sim</option><option value="false">Não</option></Select>
            : <Input id={id} type={['data_documento', 'validade_ate', 'data_nascimento', 'data_admissao', 'data_desligamento', 'inicio_gozo'].includes(k) ? 'date' : 'text'} value={value[k] ?? ''} onChange={(e) => onChange({ ...value, [k]: k === 'cpf' ? cpfMask(e.target.value) : e.target.value })} />}
        </Field>
      ))}
    </div>
  )
}

export function ReviewPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const [filters, setFilters] = useState({ tipo: '', motivo: sp.get('motivo') ?? '' })
  const queue = useGet<any[]>('/review/queue', { tipo: filters.tipo, motivo: filters.motivo })
  const types = useGet<any[]>('/document-types')
  const [idx, setIdx] = useState(0)
  const wanted = sp.get('doc')
  const [cmp, setCmp] = useState(false)
  const [reenv, setReenv] = useState<string | null>(null)
  // abre direto no documento pedido (?doc=) quando vindo do resultado do lote
  useEffect(() => { if (wanted && queue.data) { const i = queue.data.findIndex((q) => q.id === wanted); if (i >= 0) setIdx(i) } }, [wanted, queue.data])
  const cur = queue.data?.[Math.min(idx, (queue.data?.length ?? 1) - 1)]
  const doc = useGet<any>(cur ? `/documents/${cur.id}` : null)
  const [tipo, setTipo] = useState('')
  const schema = useGet<any>(doc.data ? `/document-types/${tipo || doc.data.document_type}/schema` : null)
  const [campos, setCampos] = useState<Record<string, any>>({})
  const [emp, setEmp] = useState<any>(null)
  const [novo, setNovo] = useState(false)
  const [nf, setNf] = useState({ nome: '', cpf: '', matricula: '' })
  const [rej, setRej] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const t0 = useRef(Date.now())
  const rotate = useRef<() => void>(() => {})
  const d = doc.data
  const erros = d ? problemas(d).filter((p) => p.nivel === 'erro') : []
  const forcar = erros.length > 0 // "aprovar mesmo assim": confirma apesar de erro (fica na auditoria)
  const ilegivel = d?.motivos_revisao?.some((m: string) => ['PAGINA_ILEGIVEL', 'IMAGEM_BORRADA'].includes(m))

  useEffect(() => { if (d) { setTipo(d.document_type); setCampos(d.campos ?? {}); setEmp(null); setErr(''); t0.current = Date.now() } }, [d?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const act = useCallback(async (acao: string, extra: Record<string, any> = {}) => {
    if (!d) return
    setBusy(true); setErr('')
    try {
      await api(`/review/${d.id}`, { method: 'POST', body: { acao, tipo: tipo !== d.document_type ? tipo : undefined, campos: ['CORRIGIR', 'TRANSCRICAO_MANUAL'].includes(acao) ? campos : undefined, employee_id: emp?.id, duracao_ms: Date.now() - t0.current, forcado: forcar && ['CONFIRMAR', 'CORRIGIR'].includes(acao), ...extra } })
      await queue.refetch(); qc.invalidateQueries({ queryKey: ['/metrics/overview'] })
      if (['CONFIRMAR', 'CORRIGIR', 'TRANSCRICAO_MANUAL', 'REJEITAR', 'SUBSTITUIR_ANTERIOR', 'MANTER_AMBOS', 'SOLICITAR_REENVIO'].includes(acao)) setIdx((i) => Math.max(0, i))
      else await doc.refetch()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }, [d, tipo, campos, emp, queue, doc, qc, forcar])

  // atalhos: Enter confirma, J/K navegam, R gira a página
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = (e.target as HTMLElement).tagName
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(t) || rej !== null || novo) return
      if (e.key === 'Enter') { e.preventDefault(); act(Object.keys(campos).length && JSON.stringify(campos) !== JSON.stringify(d?.campos) ? 'CORRIGIR' : 'CONFIRMAR') }
      if (e.key.toLowerCase() === 'j') setIdx((i) => Math.min(i + 1, (queue.data?.length ?? 1) - 1))
      if (e.key.toLowerCase() === 'k') setIdx((i) => Math.max(0, i - 1))
      if (e.key.toLowerCase() === 'r') rotate.current()
    }
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k)
  }, [act, campos, d, queue.data, rej, novo])

  const pagesForSplit = useMemo(() => d?.paginas ?? [], [d])
  if (queue.isLoading) return <SkeletonRows />
  if (queue.error) return <ErrorState error={queue.error} retry={queue.refetch} />
  return (
    <div>
      <SectionHeading eyebrow="Revisão" title="Fila de revisão humana">Prioridade: erro → sem vínculo → baixa confiança. Atalhos: <kbd>Enter</kbd> confirma · <kbd>J</kbd>/<kbd>K</kbd> navega · <kbd>R</kbd> gira a página.</SectionHeading>
      <div className="mb-4 flex flex-wrap gap-3">
        <Select aria-label="Filtrar por tipo" className="!w-56" value={filters.tipo} onChange={(e) => setFilters({ ...filters, tipo: e.target.value })}><option value="">Todos os tipos</option>{types.data?.map((t) => <option key={t.codigo} value={t.codigo}>{t.nome}</option>)}</Select>
        <Select aria-label="Filtrar por motivo" className="!w-56" value={filters.motivo} onChange={(e) => setFilters({ ...filters, motivo: e.target.value })}><option value="">Todos os motivos</option>{Object.entries(MOTIVOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
        <span className="self-center text-sm text-muted-foreground">{queue.data?.length ?? 0} na fila</span>
      </div>
      {!queue.data?.length ? <EmptyState icon={<ClipboardCheck className="h-5 w-5" />} title="Fila zerada" text="Nenhum documento aguardando revisão. Bom trabalho!" /> : (
        <div className="grid gap-4 xl:grid-cols-[16rem_1.2fr_1fr]">
          <ul className="glass-panel max-h-[70dvh] space-y-1 overflow-auto p-2" aria-label="Fila">
            {queue.data.map((q, i) => (
              <li key={q.id}><button onClick={() => setIdx(i)} className={clsx('w-full rounded-lg p-2 text-left text-sm', i === idx ? 'bg-brand-lighter' : 'hover:bg-brand-50')}>
                <b className="block text-brand-darker">{q.tipo_nome}</b><span className="text-xs text-muted-foreground">{q.funcionario_nome ?? q.nome_extraido ?? 'sem vínculo'}</span>
                <span className="mt-1 flex flex-wrap items-center gap-1"><ConfidenceBar value={Number(q.confianca)} />{q.motivos_revisao.slice(0, 2).map((m: string) => <span key={m} className="rounded-full bg-warning-bg px-1.5 text-[10px] font-semibold text-warning">{MOTIVOS[m] ?? m}</span>)}</span></button></li>
            ))}
          </ul>
          <div className="min-w-0">{doc.isLoading || !d ? <SkeletonRows n={6} /> : <DocumentViewer key={d.id} pages={d.paginas_urls} rotateRef={(f) => { rotate.current = f }} />}</div>
          <div className="space-y-3">
            {d && (<>
              <Card>
                <div className="mb-3 flex flex-wrap items-center gap-2"><StatusPill status={d.status} /><ConfidenceBar value={Number(d.confianca)} />
                  {d.motivos_revisao.map((m: string) => <span key={m} className="rounded-full bg-warning-bg px-2 py-0.5 text-xs font-semibold text-warning">{MOTIVOS[m] ?? m}</span>)}</div>
                <Field label="Tipo sugerido">{(id) => <Select id={id} value={tipo} onChange={(e) => { setTipo(e.target.value); setCampos(e.target.value === d.document_type ? (d.campos ?? {}) : {}) }}>{types.data?.map((t) => <option key={t.codigo} value={t.codigo}>{t.nome}</option>)}</Select>}</Field>
                <div className="mt-3"><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Funcionário</p>
                  <p className="mb-2 text-sm">{emp ? <b className="text-brand-darker">{emp.nome}</b> : d.funcionario_nome ? <b className="text-brand-darker">{d.funcionario_nome} <span className="font-normal text-muted-foreground">({d.funcionario_cpf})</span></b> : <span className="text-danger">Sem vínculo — lido: {d.nome_extraido ?? '—'}</span>}</p>
                  <EmployeePicker onPick={setEmp} />
                  {!d.employee_id && !emp && <button className="mt-2 text-sm font-semibold text-brand underline" onClick={() => { setNf({ nome: d.nome_extraido ?? '', cpf: '', matricula: '' }); setNovo(true) }}>Criar funcionário com os dados extraídos</button>}</div>
              </Card>
              {problemas(d).length > 0 && <Card title="Problemas encontrados"><ul className="space-y-2 text-sm">{problemas(d).map((p) => <li key={p.codigo} className={`flex gap-2 rounded-lg p-2 ${p.nivel === 'erro' ? 'bg-danger-bg text-danger' : 'bg-warning-bg text-warning'}`}><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /><span><b>{p.titulo}</b><span className="block text-xs">{p.texto}</span></span></li>)}</ul></Card>}
              <Card title="Campos extraídos"><SchemaForm schema={schema.data} value={campos} onChange={setCampos} /></Card>
              {(ilegivel || d.document_type === 'OUTRO' || d.motivos_revisao?.includes('TIPO_OUTRO')) && <Card title="Tratamento manual"><p className="mb-3 text-sm text-muted-foreground">Escolha o tipo acima e preencha os campos do formulário. A transcrição fica identificada como manual e não comprova a regularidade documental; envie uma cópia legível para sanar a pendência.</p><div className="flex flex-wrap gap-2"><Button variant="primary" loading={busy} disabled={tipo === 'OUTRO'} onClick={() => act('TRANSCRICAO_MANUAL')}><ClipboardCheck className="h-4 w-4" />Salvar transcrição manual</Button><Button onClick={() => nav(`/app/lotes/novo?substitui=${d.id}${d.employee_id ? `&funcionario=${d.employee_id}` : ''}${tipo !== 'OUTRO' ? `&tipo=${tipo}` : ''}`)}><Send className="h-4 w-4" />Enviar cópia legível</Button></div></Card>}
              {err && <p role="alert" className="rounded-lg bg-danger-bg p-2 text-sm text-danger">{err}</p>}
              <div className="grid grid-cols-2 gap-2">
                <Button variant="primary" loading={busy} onClick={() => act('CONFIRMAR')} title={forcar ? 'Há erros neste documento: a aprovação fica registrada como forçada' : undefined}><CheckCheck className="h-4 w-4" />{forcar ? 'Aprovar mesmo assim' : 'Confirmar'}</Button>
                <Button onClick={() => { setReenv('Imagem ilegível ou documento com erro: envie novamente.') }}><Send className="h-4 w-4" />Solicitar novo envio</Button>
                {(d.employee_id || emp) && <Button onClick={() => setCmp(true)}><Scale className="h-4 w-4" />Comparar documentos</Button>}
                <Button loading={busy} onClick={() => act('CORRIGIR')}>Corrigir e confirmar</Button>
                <Button onClick={() => emp && act('VINCULAR')} disabled={!emp}>Vincular</Button>
                <Button onClick={() => act('MUDAR_TIPO')} disabled={tipo === d.document_type}>Mudar tipo</Button>
                {d.duplicata_de && <><Button onClick={() => act('SUBSTITUIR_ANTERIOR')}>Substituir anterior</Button><Button onClick={() => act('MANTER_AMBOS')}>Manter os dois</Button></>}
                {pagesForSplit.length > 1 && <Button onClick={() => act('DIVIDIR', { pagina_divisao: pagesForSplit[Math.floor(pagesForSplit.length / 2)] })}><Scissors className="h-4 w-4" />Dividir aqui</Button>}
                <Button onClick={() => act('JUNTAR')}><Merge className="h-4 w-4" />Juntar com o próximo</Button>
                <Button variant="danger" onClick={() => setRej('')}><Trash2 className="h-4 w-4" />Rejeitar</Button>
              </div>
            </>)}
          </div>
        </div>
      )}
      <Modal open={rej !== null} onClose={() => setRej(null)} eyebrow="Revisão" title="Rejeitar documento" footer={<><Button onClick={() => setRej(null)}>Cancelar</Button><Button variant="danger" disabled={!rej?.trim()} onClick={async () => { await act('REJEITAR', { motivo: rej }); setRej(null) }}>Rejeitar</Button></>}>
        <Field label="Motivo (obrigatório)">{(id) => <Textarea id={id} value={rej ?? ''} onChange={(e) => setRej(e.target.value)} />}</Field>
      </Modal>
      <CompareModal docId={d?.id ?? null} open={cmp} onClose={() => setCmp(false)} />
      <Modal open={reenv !== null} onClose={() => setReenv(null)} eyebrow="Revisão" title="Solicitar novo envio" footer={<><Button onClick={() => setReenv(null)}>Cancelar</Button><Button variant="primary" disabled={!reenv?.trim()} onClick={async () => { await act('SOLICITAR_REENVIO', { motivo: reenv }); setReenv(null) }}>Solicitar reenvio</Button></>}>
        <p className="text-sm text-muted-foreground">O documento sai da fila e quem enviou o lote recebe um e-mail pedindo o reenvio.</p>
        <Field label="Mensagem">{(id) => <Textarea id={id} value={reenv ?? ''} onChange={(e) => setReenv(e.target.value)} />}</Field>
      </Modal>
      <Modal open={novo} onClose={() => setNovo(false)} eyebrow="Vínculo" title="Novo funcionário" footer={<><Button onClick={() => setNovo(false)}>Cancelar</Button><Button variant="primary" disabled={!nf.nome || nf.cpf.replace(/\D/g, '').length !== 11} onClick={async () => { await act('VINCULAR', { novo_funcionario: nf }); setNovo(false) }}>Criar e vincular</Button></>}>
        <Field label="Nome">{(id) => <Input id={id} value={nf.nome} onChange={(e) => setNf({ ...nf, nome: e.target.value })} />}</Field>
        <Field label="CPF">{(id) => <Input id={id} value={nf.cpf} onChange={(e) => setNf({ ...nf, cpf: cpfMask(e.target.value) })} />}</Field>
        <Field label="Matrícula">{(id) => <Input id={id} value={nf.matricula} onChange={(e) => setNf({ ...nf, matricula: e.target.value })} />}</Field>
      </Modal>
    </div>
  )
}
