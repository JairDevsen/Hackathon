import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Eye, FileText, FolderTree, Info, List, Scale, Search, Send, CheckCheck, XCircle, CheckCircle2 } from 'lucide-react'
import { CompareModal } from '@/components/CompareModal'
import { Button, ConfidenceBar, DataTable, EmptyState, Field, Input, Modal, StatusPill, Textarea, clsx } from '@/components/ui'
import { api } from '@/lib/api'
import { nivelDoc, problemas, resumo, type Nivel } from '@/lib/analise'
import { useAuth } from '@/lib/auth'
import { chaveEmpresa, fmtDate } from '@/lib/format'
import { MotivoChips } from './Dossie'

const TONE: Record<Exclude<Nivel, 'aprovado'>, { box: string; icon: any; cls: string }> = {
  erro: { box: 'border-danger/60 bg-danger-bg/40', icon: XCircle, cls: 'text-danger' },
  atencao: { box: 'border-warning/60 bg-warning-bg/40', icon: AlertTriangle, cls: 'text-warning' },
}

function Kpi({ icon: I, label, n, pct, tone }: { icon: any; label: string; n: number; pct?: number; tone: string }) {
  return (
    <div className="glass-panel flex items-center gap-3 p-3">
      <I className={clsx('h-8 w-8 shrink-0', tone)} aria-hidden />
      <div><p className="text-xs text-muted-foreground">{label}</p><p className={clsx('text-2xl font-bold tracking-tight', tone)}>{n}{pct !== undefined && <span className="ml-1.5 text-sm font-semibold">({pct}%)</span>}</p></div>
    </div>
  )
}

function PastasRH({ docs, onOpen }: { docs: any[]; onOpen: (id: string) => void }) {
  const tree: Record<string, Record<string, any[]>> = {}
  const rotulo: Record<string, string> = {} // a mesma empresa escrita de jeitos diferentes fica numa pasta só, com a 1ª grafia vista
  for (const d of docs) {
    // separação: própria empresa × terceirizada × fornecedor, e dentro de cada um a empresa (pelo CNPJ) e o funcionário
    const grupo = d.vinculo === 'TERCEIRIZADA' ? '1|Terceirizada' : d.vinculo === 'FORNECEDOR' ? '2|Fornecedor' : '0|Própria empresa'
    const nomeEmp = d.fornecedor || d.empresa_nome || 'Empresa não identificada'
    const chave = `${grupo}|${chaveEmpresa(nomeEmp) || nomeEmp}`
    const emp = (rotulo[chave] ??= `${grupo}|${nomeEmp}`)
    const fn = d.funcionario_nome ? `${d.funcionario_nome} (${d.funcionario_cpf ?? 's/ CPF'})` : 'Documentos da empresa / sem vínculo'
    ;((tree[emp] ??= {})[fn] ??= []).push(d)
  }
  if (!docs.length) return <EmptyState title="Nenhum documento" />
  return (
    <ul className="space-y-3" aria-label="Árvore de pastas do RH">
      {Object.entries(tree).sort(([x], [y]) => x.localeCompare(y)).map(([emp, funcs]) => (
        <li key={emp}><p className="flex items-center gap-2 font-semibold text-brand-darker"><FolderTree className="h-4 w-4 text-brand-default" aria-hidden /><span className="rounded bg-brand-lighter px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide">{emp.split('|')[1]}</span>{emp.split('|').slice(2).join('|')}</p>
          <ul className="ml-3 mt-1 space-y-2 border-l-2 border-brand-lighter pl-4">
            {Object.entries(funcs).map(([fn, ds]) => (
              <li key={fn}><p className="text-sm font-medium text-foreground">{fn}</p>
                <ul className="mt-1 space-y-1">{ds.map((d) => <li key={d.id}><button onClick={() => onOpen(d.id)} className="w-full rounded-lg px-2 py-1 text-left text-sm hover:bg-brand-50"><span className="text-brand-darker">{d.tipo_nome}</span> <span className="text-xs text-muted-foreground">· pág. {d.paginas.join(', ')} · {d.nome_arquivo ?? ''}</span></button></li>)}</ul></li>
            ))}
          </ul></li>
      ))}
    </ul>
  )
}

/** Resultado do lote: totais, abas Todos/Aprovados/Com atenção/Com erro, busca e cartões de problema com ações. */
export function ResultadoLote({ docs, running, onChanged }: { docs: any[]; running: boolean; onChanged: () => void }) {
  const nav = useNavigate()
  const { can } = useAuth()
  const [tab, setTab] = useState<'todos' | Nivel>('todos')
  const [view, setView] = useState<'lista' | 'pastas'>('lista')
  const [q, setQ] = useState('')
  const [cmp, setCmp] = useState<string | null>(null)
  const [reenvio, setReenvio] = useState<any>(null)
  const [motivo, setMotivo] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const r = resumo(docs)
  const pct = (n: number) => (r.total ? Math.round((100 * n) / r.total) : 0)
  const needle = q.trim().toLowerCase()
  const shown = docs.filter((d) => (tab === 'todos' || nivelDoc(d) === tab)
    && (!needle || [d.tipo_nome, d.funcionario_nome, d.titulo, d.nome_arquivo, d.empresa_nome].some((x) => String(x ?? '').toLowerCase().includes(needle))))
  const tabs: [typeof tab, string, number, string][] = [['todos', 'Todos', r.total, ''], ['aprovado', 'Aprovados', r.aprovado, ''], ['atencao', 'Com atenção', r.atencao, 'bg-warning'], ['erro', 'Com erro', r.erro, 'bg-danger']]

  const solicitar = async () => {
    setBusy(true); setErr('')
    try { await api(`/review/${reenvio.id}`, { method: 'POST', body: { acao: 'SOLICITAR_REENVIO', motivo } }); setReenvio(null); onChanged() } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi icon={FileText} label="Total de documentos" n={r.total} tone="text-brand" />
        <Kpi icon={CheckCircle2} label="Processados com sucesso" n={r.aprovado} pct={pct(r.aprovado)} tone="text-success" />
        <Kpi icon={AlertTriangle} label="Precisam de atenção" n={r.atencao} pct={pct(r.atencao)} tone="text-warning" />
        <Kpi icon={XCircle} label="Com erro" n={r.erro} pct={pct(r.erro)} tone="text-danger" />
      </div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="segmented flex-wrap" role="tablist" aria-label="Filtro do resultado">
          {tabs.map(([k, l, n, dot]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={clsx('segmented-tab', tab === k && 'segmented-tab-active')}>
              {dot && <span className={clsx('mr-1.5 inline-block h-2 w-2 rounded-full', dot)} aria-hidden />}{l} ({n})</button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden /><Input className="!w-72 pl-9" placeholder="Buscar por nome, documento…" aria-label="Buscar no lote" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          {(tab === 'todos' || tab === 'aprovado') && (
            <div className="segmented" role="tablist" aria-label="Modo de exibição">
              <button role="tab" aria-selected={view === 'lista'} onClick={() => setView('lista')} className={clsx('segmented-tab', view === 'lista' && 'segmented-tab-active')}><List className="mr-1 inline h-3.5 w-3.5" />Lista</button>
              <button role="tab" aria-selected={view === 'pastas'} onClick={() => setView('pastas')} className={clsx('segmented-tab', view === 'pastas' && 'segmented-tab-active')}><FolderTree className="mr-1 inline h-3.5 w-3.5" />Pastas RH</button>
            </div>
          )}
        </div>
      </div>

      {!shown.length ? <EmptyState title={running ? 'Processando…' : tab === 'todos' ? 'Nenhum documento' : 'Nada nesta categoria'} text={tab === 'erro' && !running ? 'Nenhum documento com erro neste lote.' : undefined} /> :
        tab === 'atencao' || tab === 'erro' ? (
          <ul className="space-y-3">
            {shown.map((d) => {
              const ps = problemas(d)
              const nivel = nivelDoc(d) as Exclude<Nivel, 'aprovado'>
              const t = TONE[nivel] ?? TONE.atencao
              const first = ps.find((p) => p.nivel === nivel) ?? ps[0]
              const diverge = ps.some((p) => p.codigo === 'DADOS_DIVERGENTES')
              const ilegivel = ps.some((p) => p.codigo === 'IMAGEM_BORRADA' || p.codigo === 'PAGINA_ILEGIVEL')
              const semTipo = d.document_type === 'OUTRO' || ps.some((p) => p.codigo === 'TIPO_OUTRO')
              return (
                <li key={d.id} className={clsx('grid gap-4 rounded-xl border-2 p-4 md:grid-cols-[1fr_16rem_auto] md:items-center', t.box)}>
                  <div>
                    <p className={clsx('flex items-center gap-2 font-display text-lg font-semibold', t.cls)}><t.icon className="h-5 w-5" aria-hidden />{first?.titulo ?? 'Revisão necessária'}</p>
                    <p className="mt-1 text-sm text-foreground">{first?.texto ?? 'O documento aguarda conferência humana.'}</p>
                    {ps.slice(1).map((p) => <p key={p.codigo} className="mt-1 flex gap-1.5 text-xs text-muted-foreground"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{p.titulo}: {p.texto}</p>)}
                    <p className="mt-2 text-xs text-muted-foreground">{d.tipo_nome} · {d.funcionario_nome ?? 'sem vínculo'} · pág. {d.paginas.join(', ')}{d.validade_ate ? ` · validade ${fmtDate(d.validade_ate)}` : ''}</p>
                  </div>
                  {d.thumb_url ? <img src={d.thumb_url} alt={`Primeira página de ${d.tipo_nome}`} loading="lazy" className={clsx('max-h-40 w-full rounded-lg border border-border bg-surface object-contain', ilegivel && 'blur-[1px]')} /> : <div className="grid h-24 place-items-center rounded-lg bg-muted text-xs text-muted-foreground">{d.mascarado ? 'Dado de saúde restrito' : 'Sem pré-visualização'}</div>}
                  <div className="flex flex-col gap-2">
                    {diverge && <Button variant="primary" onClick={() => setCmp(d.id)}><Scale className="h-4 w-4" />Comparar documentos</Button>}
                    {can('revisao:fazer') && <Button variant={diverge ? 'ghost' : 'primary'} onClick={() => nav(`/app/revisao?doc=${d.id}`)}><CheckCheck className="h-4 w-4" />Revisar documento</Button>}
                    {(ilegivel || semTipo) && can('revisao:fazer') && <Button onClick={() => nav(`/app/revisao?doc=${d.id}`)}><FileText className="h-4 w-4" />Classificar e preencher</Button>}
                    {ilegivel && can('lotes:enviar') && <Button onClick={() => nav(`/app/lotes/novo?substitui=${d.id}${d.employee_id ? `&funcionario=${d.employee_id}` : ''}${d.document_type !== 'OUTRO' ? `&tipo=${d.document_type}` : ''}`)}><Send className="h-4 w-4" />Enviar cópia legível</Button>}
                    {ilegivel && can('revisao:fazer') && <Button onClick={() => { setReenvio(d); setMotivo('Imagem ilegível: envie o documento novamente com uma imagem mais nítida.'); setErr('') }}><Send className="h-4 w-4" />Solicitar novo envio</Button>}
                    <Button onClick={() => nav(`/app/documentos/${d.id}`)}><Eye className="h-4 w-4" />Ver detalhes</Button>
                  </div>
                </li>
              )
            })}
          </ul>
        ) : view === 'pastas' ? <PastasRH docs={shown} onOpen={(i) => nav(`/app/documentos/${i}`)} /> : (
          <DataTable rows={shown} onRow={(d) => nav(`/app/documentos/${d.id}`)}
            cols={[{ key: 'tipo_nome', header: 'Tipo' }, { key: 'funcionario_nome', header: 'Funcionário', render: (d) => d.funcionario_nome ?? <span className="text-muted-foreground">sem vínculo</span> }, { key: 'paginas', header: 'Páginas', render: (d) => d.paginas.join(', ') },
              { key: 'confianca', header: 'Confiança', render: (d) => <ConfidenceBar value={Number(d.confianca)} /> },
              { key: 'status', header: 'Status', render: (d) => <div className="flex flex-wrap gap-1"><StatusPill status={d.status} /><MotivoChips motivos={d.motivos_revisao} /></div> }]} />
        )}

      <CompareModal docId={cmp} open={!!cmp} onClose={() => setCmp(null)} />
      <Modal open={!!reenvio} onClose={() => setReenvio(null)} eyebrow="Revisão" title="Solicitar novo envio"
        footer={<><Button onClick={() => setReenvio(null)}>Cancelar</Button><Button variant="primary" loading={busy} onClick={solicitar}>Solicitar reenvio</Button></>}>
        <p className="text-sm text-muted-foreground">O documento sai do lote e quem enviou recebe um e-mail pedindo o reenvio. A pendência continua aberta até chegar um documento válido.</p>
        <Field label="Mensagem" error={err}>{(id) => <Textarea id={id} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}</Field>
      </Modal>
    </div>
  )
}
