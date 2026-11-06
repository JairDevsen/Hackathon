import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, XAxis, YAxis, Area, AreaChart } from 'recharts'
import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardCheck, FileClock, FileText, FolderOpen, RefreshCw, Search, ShieldAlert, Truck, Upload, Users } from 'lucide-react'
import { Button, Card, ComplianceRing, ErrorState, Skeleton, StatusPill } from '@/components/ui'
import { C, ChartTip, Donut, YTick, axis } from '@/components/charts'
import { useGet } from '@/lib/query'
import { useAuth } from '@/lib/auth'
import { competenciaLabel, fmtBytes, fmtDateTime, fmtNum, fmtPct, MOTIVOS } from '@/lib/format'

type Counted = { n: number; tipo: string }
type Overview = {
  conformidade_pct: number | null; funcionarios_ativos: number; funcionarios_com_pendencia: number
  documentos_total: number; lotes_total: number; aguardando_revisao: number; documentos_ilegiveis: number
  por_vinculo?: { vinculo: string; funcionarios: number; empresas: number; ok: number; total: number }[]; fornecedores?: number; fornecedores_risco_alto?: number; fornecedores_pre_cadastro?: number
  pre_cadastros: number; riscos_abertos: number; vencidos: number; vencendo_30d: number; pendentes: number
  sem_vinculo: number; revisoes_mes: number; lotes_falhos: number
  armazenamento: { usado: number; cota: number }; paginas_mes: { usado: number; limite: number }
  documentos_por_tipo: { tipo: string; n: number }[]; a_vencer_por_tipo: Counted[]; vencido_por_tipo: Counted[]
}
type Batch = { id: string; arquivo_original: string; status: string; criado_em: string; total_paginas: number; paginas_ok: number; paginas_falhas: number; para_revisao: number; resumo?: { pre_cadastros?: number; classificacao_manual?: number } }
type Review = { id: string; tipo_nome: string; titulo?: string; funcionario_nome?: string; nome_extraido?: string; motivos_revisao: string[]; mascarado?: boolean }
type Risk = { id: string; titulo: string; severidade: 'ALTO' | 'MEDIO' | 'BAIXO'; funcionario?: string; employee_id?: string; document_id?: string }
type Compliance = { pendencias_por_tipo: { tipo: string; pendente: number; vencido: number; a_vencer: number }[]; por_unidade: { nome: string; pct: number | null }[] }
type Processing = { volume_mensal: { mes: string; paginas: number; docs: number }[]; tempo_medio_lote_seg: number | null }

function Metric({ label, value, detail, to, icon: Icon, tone = 'text-brand-darker' }: { label: string; value: number | string; detail: string; to: string; icon: typeof FileText; tone?: string }) {
  return <Link to={to} className="glass-panel group flex min-h-32 flex-col justify-between p-4 transition hover:-translate-y-0.5 hover:border-brand-light hover:shadow-lg">
    <div className="flex items-start justify-between gap-2"><span className="text-xs font-medium text-muted-foreground">{label}</span><Icon className={`h-4 w-4 shrink-0 ${tone}`} aria-hidden /></div>
    <div><p className={`text-3xl font-bold tracking-tight ${tone}`}>{value}</p><p className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>{detail}</span><ArrowRight className="h-3.5 w-3.5 shrink-0 transition group-hover:translate-x-1" aria-hidden /></p></div>
  </Link>
}

function SmallError({ retry }: { retry: () => void }) {
  return <div role="alert" className="rounded-xl border border-danger/30 bg-danger-bg p-4 text-sm text-danger">Não foi possível carregar estes dados. <button onClick={retry} className="font-semibold underline">Tentar novamente</button></div>
}

function BatchProgress({ batch }: { batch?: Batch }) {
  if (!batch) return <div className="space-y-3 py-3 text-sm text-muted-foreground"><p>Nenhum lote enviado ainda.</p><Link to="/app/lotes/novo" className="font-semibold text-brand underline">Enviar o primeiro lote</Link></div>
  const total = Number(batch.total_paginas) || 0
  const done = Number(batch.paginas_ok) || 0
  const completed = batch.status.startsWith('PROCESSADO')
  const pct = completed ? 100 : total ? Math.min(100, Math.round(100 * done / total)) : 0
  const active = batch.status === 'RECEBIDO' || batch.status === 'PROCESSANDO'
  return <div className="space-y-4">
    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><Link to={`/app/lotes/${batch.id}`} className="block truncate text-sm font-semibold text-brand-darker hover:underline">{batch.arquivo_original}</Link><p className="mt-1 text-xs text-muted-foreground">Enviado em {fmtDateTime(batch.criado_em)}</p></div><StatusPill status={batch.status} /></div>
    <div><div className="mb-1.5 flex justify-between gap-2 text-xs text-muted-foreground"><span>{total ? `${done} de ${total} páginas processadas` : 'Preparando páginas…'}</span><span>{total || completed ? `${pct}%` : '—'}</span></div>
      <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Progresso do lote" className="h-2.5 overflow-hidden rounded-full bg-brand-lighter"><div className={`h-full rounded-full transition-all ${batch.status === 'FALHOU' ? 'bg-danger' : completed ? 'bg-success' : 'bg-brand-default'}`} style={{ width: `${pct}%` }} /></div></div>
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {active && <span>Em processamento</span>}{batch.status === 'FALHOU' && <span className="font-medium text-danger">Falha no lote: retome o processamento</span>}
      {Number(batch.para_revisao) > 0 && <span className="text-warning">{batch.para_revisao} para revisão</span>}
      {Number(batch.resumo?.pre_cadastros) > 0 && <span>{batch.resumo?.pre_cadastros} pré-cadastrados</span>}
      {Number(batch.resumo?.classificacao_manual) > 0 && <span className="text-danger">{batch.resumo?.classificacao_manual} ilegíveis ou sem tipo</span>}
      {Number(batch.paginas_falhas) > 0 && <span className="text-danger">{batch.paginas_falhas} página(s) com falha</span>}
    </div>
    <Link to={`/app/lotes/${batch.id}`} className="inline-flex items-center gap-1 text-sm font-semibold text-brand hover:underline">Ver resultado do lote <ArrowRight className="h-4 w-4" /></Link>
  </div>
}

function Capacity({ used, limit, label }: { used: number; limit: number; label: string }) {
  const pct = limit > 0 ? Math.min(100, Math.round(100 * used / limit)) : 0
  return <div><div className="mb-1.5 flex justify-between gap-2 text-sm"><span className="text-muted-foreground">{label}</span><b className="text-brand-darker">{pct}%</b></div><div className="h-2 overflow-hidden rounded-full bg-brand-lighter"><div className={`h-full rounded-full ${pct >= 95 ? 'bg-danger' : pct >= 80 ? 'bg-warning' : 'bg-brand-default'}`} style={{ width: `${pct}%` }} /></div></div>
}

export function AdminDashboard() {
  const { user, can } = useAuth()
  const qc = useQueryClient()
  const ov = useGet<Overview>('/metrics/overview', undefined, { refetchInterval: 30000 })
  const comp = useGet<Compliance>('/metrics/compliance', undefined, { refetchInterval: 60000 })
  const proc = useGet<Processing>('/metrics/processing', undefined, { refetchInterval: 60000 })
  const batches = useGet<{ items: Batch[] }>('/batches', { limit: 5 }, { refetchInterval: 10000 })
  const review = useGet<Review[]>('/review/queue', undefined, { refetchInterval: 30000 })
  const risks = useGet<{ resumo: { alto: number; medio: number; baixo: number }; items: Risk[] }>('/risks', { status: 'ABERTO' }, { refetchInterval: 30000 })
  if (ov.error) return <ErrorState error={ov.error} retry={ov.refetch} />
  const o = ov.data
  const firstName = user?.nome.trim().split(' ')[0] || 'equipe'
  const dateLabel = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
  const batchList = batches.data?.items ?? []
  const currentBatch = batchList.find((b) => b.status === 'PROCESSANDO' || b.status === 'RECEBIDO' || b.status === 'FALHOU') ?? batchList[0]
  const priorities = [
    { n: o?.vencidos ?? 0, label: 'Documentos vencidos', help: 'Conferir validade e solicitar atualização', to: '/app/pendencias', tone: 'danger' },
    { n: o?.documentos_ilegiveis ?? 0, label: 'Ilegíveis ou sem tipo', help: 'Classificar, transcrever ou pedir cópia legível', to: '/app/revisao', tone: 'danger' },
    { n: o?.aguardando_revisao ?? 0, label: 'Na fila de revisão', help: 'Validar os documentos sinalizados pela análise', to: '/app/revisao', tone: 'warning' },
    { n: o?.sem_vinculo ?? 0, label: 'Documentos sem vínculo', help: 'Identificar o funcionário antes de arquivar', to: '/app/revisao', tone: 'warning' },
    { n: o?.riscos_abertos ?? 0, label: 'Indicadores trabalhistas', help: 'Verificar divergências e a prova documental', to: '/app/riscos', tone: 'warning' },
    { n: o?.pre_cadastros ?? 0, label: 'Pré-cadastros do lote', help: 'Conferir dados extraídos dos funcionários', to: '/app/funcionarios?pre=1', tone: 'brand' },
    { n: o?.lotes_falhos ?? 0, label: 'Lotes com falha', help: 'Retomar o processamento', to: '/app/lotes', tone: 'danger' },
  ].filter((x) => x.n > 0)
  const types = o?.documentos_por_tipo ?? []
  const topTypes = types.slice(0, 5)
  const otherTypes = types.slice(5).reduce((n, x) => n + Number(x.n), 0)
  const donut = otherTypes ? [...topTypes, { tipo: 'Outros', n: otherTypes }] : topTypes
  const pendingTypes = (comp.data?.pendencias_por_tipo ?? []).slice(0, 6)
  const volume = proc.data?.volume_mensal ?? []
  const months = [...volume].sort((a, b) => a.mes.localeCompare(b.mes)).slice(-6).map((x) => ({ ...x, label: competenciaLabel(x.mes) }))
  const refresh = () => { for (const path of ['/metrics/overview', '/metrics/compliance', '/metrics/processing', '/batches', '/review/queue', '/risks']) qc.invalidateQueries({ queryKey: [path] }) }

  return <div className="space-y-6">
    <section className="glass-panel relative overflow-hidden p-5 sm:p-7" style={{ background: 'linear-gradient(115deg, var(--glass-panel-bg), var(--color-brand-50))' }}>
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-6">
        <div className="max-w-2xl"><p className="text-xs font-semibold uppercase tracking-[.17em] text-brand">Visão da operação · {dateLabel}</p><h1 className="mt-2 font-display text-3xl font-bold text-brand-darker sm:text-4xl">Olá, {firstName}</h1><p className="mt-2 text-sm text-muted-foreground sm:text-base">Veja o que precisa de atenção, acompanhe os lotes e continue a análise documental.</p>
          <div className="mt-5 flex flex-wrap gap-2.5">
            {can('lotes:enviar') && <Link to="/app/lotes/novo"><Button variant="primary"><Upload className="h-4 w-4" />Enviar lote</Button></Link>}
            <Link to="/app/revisao"><Button><ClipboardCheck className="h-4 w-4" />Abrir revisão</Button></Link>
            <Link to="/app/buscar"><Button><Search className="h-4 w-4" />Buscar funcionário</Button></Link>
          </div>
        </div>
        <div className="flex min-w-52 items-center gap-4 rounded-xl border border-border bg-surface/60 p-4">{o?.conformidade_pct == null ? <div className="grid h-[78px] w-[78px] place-items-center rounded-full border-8 border-border text-lg font-semibold text-muted-foreground">—</div> : <ComplianceRing pct={Number(o.conformidade_pct)} size={78} />}<div><p className="text-xs text-muted-foreground">Conformidade documental</p><p className="text-xl font-bold text-brand-darker">{o?.conformidade_pct == null ? '—' : fmtPct(o.conformidade_pct, 1)}</p><p className="text-xs text-muted-foreground">{fmtNum(o?.funcionarios_ativos ?? 0, 0)} funcionários ativos</p><p className="text-xs text-muted-foreground">{fmtNum(o?.funcionarios_com_pendencia ?? 0, 0)} com pendências</p></div></div>
      </div>
    </section>

    <section aria-label="Indicadores principais"><div className="mb-3 flex items-center justify-between gap-3"><div><h2 className="font-display text-xl font-semibold text-brand-darker">O que importa agora</h2><p className="text-xs text-muted-foreground">Abra um indicador para tratar os itens relacionados.</p></div><Button size="sm" onClick={refresh}><RefreshCw className="h-3.5 w-3.5" />Atualizar</Button></div>
      {!o ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-32" />)}</div> : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Metric label="Aguardando revisão" value={fmtNum(o.aguardando_revisao, 0)} detail="documentos para conferir" to="/app/revisao" icon={ClipboardCheck} tone={o.aguardando_revisao ? 'text-warning' : 'text-success'} />
        <Metric label="Ilegíveis / sem tipo" value={fmtNum(o.documentos_ilegiveis, 0)} detail="exigem ação humana" to="/app/revisao" icon={AlertTriangle} tone={o.documentos_ilegiveis ? 'text-danger' : 'text-success'} />
        <Metric label="Vencidos" value={fmtNum(o.vencidos, 0)} detail="exigências a regularizar" to="/app/pendencias" icon={FileClock} tone={o.vencidos ? 'text-danger' : 'text-success'} />
        <Metric label="Vencem em 30 dias" value={fmtNum(o.vencendo_30d, 0)} detail="planeje as renovações" to="/app/calendario" icon={FileClock} tone={o.vencendo_30d ? 'text-warning' : 'text-success'} />
        <Metric label="Riscos em aberto" value={fmtNum(o.riscos_abertos, 0)} detail="sinais para conferência" to="/app/riscos" icon={ShieldAlert} tone={o.riscos_abertos ? 'text-danger' : 'text-success'} />
        <Metric label="Fornecedores em risco alto" value={fmtNum(o.fornecedores_risco_alto ?? 0, 0)} detail={`de ${fmtNum(o.fornecedores ?? 0, 0)} ativos`} to="/app/fornecedores" icon={Truck} tone={o.fornecedores_risco_alto ? 'text-danger' : 'text-success'} />
        <Metric label="Pré-cadastrados" value={fmtNum(o.pre_cadastros, 0)} detail="gerados pelos lotes" to="/app/funcionarios?pre=1" icon={Users} tone="text-brand" />
      </div>}
    </section>

    {!!o?.por_vinculo?.length && (
      <Card title="Quem trabalha para a empresa" action={<Link to="/app/fornecedores" className="text-sm font-semibold text-brand hover:underline">Ver fornecedores →</Link>}>
        <div className="grid gap-3 sm:grid-cols-3">
          {([['PROPRIA', 'Própria empresa', '/app/funcionarios?vinculo=PROPRIA'], ['TERCEIRIZADA', 'Terceirizadas', '/app/funcionarios?vinculo=TERCEIRIZADA'], ['FORNECEDOR', 'Fornecedores', '/app/funcionarios?vinculo=FORNECEDOR']] as const).map(([k, label, to]) => {
            const g = o.por_vinculo!.find((x) => x.vinculo === k)
            return <Link key={k} to={to} className="rounded-xl border border-border bg-surface/60 p-3 transition hover:border-brand-light">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
              <p className="text-2xl font-bold text-brand-darker">{g?.funcionarios ?? 0}<span className="ml-1 text-sm font-medium text-muted-foreground">trabalhadores{k !== 'PROPRIA' ? ` · ${g?.empresas ?? 0} empresa(s)` : ''}</span></p>
              <p className="text-xs text-muted-foreground">{g?.total ? `${fmtPct((100 * g.ok) / g.total)} dos documentos exigidos em dia` : 'sem exigências calculadas'}</p>
            </Link>
          })}
        </div>
      </Card>
    )}

    <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
      <Card title="Próximas ações" action={<Link to="/app/pendencias" className="text-sm font-semibold text-brand hover:underline">Ver pendências →</Link>}>
        {!o ? <Skeleton className="h-44" /> : priorities.length ? <ol className="divide-y divide-border/60">{priorities.map((x) => <li key={x.label}><Link to={x.to} className="group flex items-center gap-3 py-2.5 hover:text-brand"><span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg text-sm font-bold ${x.tone === 'danger' ? 'bg-danger-bg text-danger' : x.tone === 'warning' ? 'bg-warning-bg text-warning' : 'bg-brand-lighter text-brand'}`}>{x.n}</span><span className="min-w-0 flex-1"><b className="block text-sm text-brand-darker">{x.label}</b><span className="block text-xs text-muted-foreground">{x.help}</span></span><ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-1" /></Link></li>)}</ol> : <div className="flex items-center gap-3 py-8 text-sm text-success"><CheckCircle2 className="h-6 w-6" /><span>Nenhuma ação urgente identificada. Continue acompanhando os próximos lotes.</span></div>}
      </Card>
      <Card title="Acompanhamento do lote" action={<Link to="/app/lotes" className="text-sm font-semibold text-brand hover:underline">Todos os lotes →</Link>}>
        {batches.error ? <SmallError retry={batches.refetch} /> : batches.isLoading ? <Skeleton className="h-44" /> : <BatchProgress batch={currentBatch} />}
      </Card>
    </div>

    <div className="grid gap-4 xl:grid-cols-2">
      <Card title="Fila de revisão" action={<Link to="/app/revisao" className="text-sm font-semibold text-brand hover:underline">Abrir fila →</Link>}>
        {review.error ? <SmallError retry={review.refetch} /> : review.isLoading ? <Skeleton className="h-44" /> : review.data?.length ? <ul className="divide-y divide-border/60">{review.data.slice(0, 4).map((d) => <li key={d.id}><Link to={`/app/revisao?doc=${d.id}`} className="group flex items-center gap-3 py-2.5"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-warning-bg text-warning"><FileText className="h-4 w-4" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm text-brand-darker group-hover:text-brand">{d.tipo_nome}</b><span className="block truncate text-xs text-muted-foreground">{d.mascarado ? 'Dado de saúde restrito' : d.funcionario_nome ?? d.nome_extraido ?? 'Funcionário não identificado'} · {MOTIVOS[d.motivos_revisao?.[0]] ?? 'Conferência necessária'}</span></span><ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" /></Link></li>)}</ul> : <p className="flex items-center gap-2 py-8 text-sm text-success"><CheckCircle2 className="h-5 w-5" />Nenhum documento aguardando revisão.</p>}
      </Card>
      <Card title="Indicadores trabalhistas" action={<Link to="/app/riscos" className="text-sm font-semibold text-brand hover:underline">Ver indicadores →</Link>}>
        {risks.error ? <SmallError retry={risks.refetch} /> : risks.isLoading ? <Skeleton className="h-44" /> : risks.data?.items.length ? <div><p className="mb-2 text-xs text-muted-foreground">{risks.data.resumo.alto} alto · {risks.data.resumo.medio} médio · {risks.data.resumo.baixo} baixo. Sinais para conferência humana.</p><ul className="divide-y divide-border/60">{risks.data.items.slice(0, 3).map((r) => <li key={r.id}><Link to={r.document_id ? `/app/documentos/${r.document_id}` : '/app/riscos'} className="group flex items-center gap-3 py-2.5"><span className={`h-2.5 w-2.5 shrink-0 rounded-full ${r.severidade === 'ALTO' ? 'bg-danger' : r.severidade === 'MEDIO' ? 'bg-warning' : 'bg-brand-default'}`} /><span className="min-w-0 flex-1"><b className="block truncate text-sm text-brand-darker group-hover:text-brand">{r.titulo}</b><span className="block truncate text-xs text-muted-foreground">{r.funcionario ?? (r.employee_id ? 'Funcionário com acesso restrito' : 'Documento da empresa')} · {r.severidade.toLowerCase()}</span></span><ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" /></Link></li>)}</ul></div> : <p className="flex items-center gap-2 py-8 text-sm text-success"><CheckCircle2 className="h-5 w-5" />Nenhum indicador em aberto.</p>}
      </Card>
    </div>

    <section><div className="mb-3"><h2 className="font-display text-xl font-semibold text-brand-darker">Visão documental</h2><p className="text-xs text-muted-foreground">Distribuição dos documentos e exigências que precisam de regularização.</p></div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Documentos por tipo" action={<Link to="/app/documentos" className="text-sm font-semibold text-brand hover:underline">Ver documentos →</Link>}>
          {donut.length ? <Donut data={donut.map((x) => ({ nome: x.tipo, n: Number(x.n) }))} total={Number(o?.documentos_total ?? 0)} label="documentos" /> : <p className="py-8 text-sm text-muted-foreground">Os tipos aparecerão após o primeiro lote.</p>}
        </Card>
        <Card title="Pendências por tipo" action={<Link to="/app/pendencias" className="text-sm font-semibold text-brand hover:underline">Abrir pendências →</Link>}>
          {comp.error ? <SmallError retry={comp.refetch} /> : pendingTypes.length ? <div style={{ height: Math.max(210, pendingTypes.length * 38 + 35) }} role="img" aria-label="Pendências por tipo de documento"><ResponsiveContainer><BarChart data={pendingTypes} layout="vertical" margin={{ left: 8, right: 16 }}><CartesianGrid stroke={C.grid} horizontal={false} /><XAxis type="number" allowDecimals={false} {...axis} /><YAxis type="category" dataKey="tipo" width={150} tick={<YTick max={22} />} axisLine={false} tickLine={false} /><ChartTip /><Bar dataKey="vencido" name="Vencidos" stackId="a" fill={C.danger} /><Bar dataKey="pendente" name="Pendentes" stackId="a" fill={C.warning} /><Bar dataKey="a_vencer" name="A vencer" stackId="a" fill={C.light} radius={[0, 6, 6, 0]} /></BarChart></ResponsiveContainer></div> : <p className="py-8 text-sm text-muted-foreground">Nenhuma exigência pendente.</p>}
        </Card>
      </div>
    </section>

    <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
      <Card title="Lotes recentes" action={<Link to="/app/lotes" className="text-sm font-semibold text-brand hover:underline">Ver todos →</Link>}>
        {batches.error ? <SmallError retry={batches.refetch} /> : batchList.length ? <ul className="divide-y divide-border/60">{batchList.slice(0, 4).map((b) => <li key={b.id}><Link to={`/app/lotes/${b.id}`} className="flex flex-wrap items-center gap-2.5 py-2.5 text-sm hover:text-brand"><FolderOpen className="h-4 w-4 shrink-0 text-brand" /><span className="min-w-32 flex-1 truncate font-medium text-brand-darker">{b.arquivo_original}</span><span className="text-xs text-muted-foreground">{b.total_paginas} pág.</span><StatusPill status={b.status} /></Link></li>)}</ul> : <p className="py-7 text-sm text-muted-foreground">Nenhum lote enviado.</p>}
      </Card>
      <Card title="Capacidade da empresa"><div className="space-y-5">
        <Capacity label={`Armazenamento · ${fmtBytes(o?.armazenamento?.usado)} de ${fmtBytes(o?.armazenamento?.cota)}`} used={Number(o?.armazenamento?.usado ?? 0)} limit={Number(o?.armazenamento?.cota ?? 0)} />
        <Capacity label={`Páginas no mês · ${fmtNum(o?.paginas_mes?.usado ?? 0, 0)} de ${fmtNum(o?.paginas_mes?.limite ?? 0, 0)}`} used={Number(o?.paginas_mes?.usado ?? 0)} limit={Number(o?.paginas_mes?.limite ?? 0)} />
        <div className="grid grid-cols-3 gap-2 border-t border-border/60 pt-3 text-center"><div><p className="text-lg font-bold text-brand-darker">{fmtNum(o?.documentos_total ?? 0, 0)}</p><p className="text-[11px] text-muted-foreground">documentos</p></div><div><p className="text-lg font-bold text-brand-darker">{fmtNum(o?.lotes_total ?? 0, 0)}</p><p className="text-[11px] text-muted-foreground">lotes</p></div><div><p className="text-lg font-bold text-brand-darker">{fmtNum(o?.revisoes_mes ?? 0, 0)}</p><p className="text-[11px] text-muted-foreground">revisões no mês</p></div></div>
      </div></Card>
    </div>

    {(months.length > 0 || (comp.data?.por_unidade?.length ?? 0) > 0) && <section><div className="mb-3"><h2 className="font-display text-xl font-semibold text-brand-darker">Evolução da operação</h2><p className="text-xs text-muted-foreground">Acompanhe o volume da empresa e a conformidade das unidades permitidas.</p></div><div className="grid gap-4 xl:grid-cols-2">
      <Card title="Volume da empresa nos últimos meses">{months.length > 1 ? <div className="h-56" role="img" aria-label="Volume mensal de páginas e documentos da empresa"><ResponsiveContainer><AreaChart data={months}><CartesianGrid stroke={C.grid} vertical={false} /><XAxis dataKey="label" {...axis} /><YAxis {...axis} /><ChartTip /><Area dataKey="paginas" name="Páginas" stroke={C.brand} fill={C.brand} fillOpacity={0.18} strokeWidth={2} /><Area dataKey="docs" name="Documentos" stroke={C.light} fill={C.light} fillOpacity={0.12} strokeWidth={2} /></AreaChart></ResponsiveContainer></div> : <p className="py-8 text-sm text-muted-foreground">{months.length ? `${fmtNum(months[0].paginas, 0)} páginas e ${fmtNum(months[0].docs, 0)} documentos em ${months[0].label}.` : 'Sem volume registrado.'}</p>}</Card>
      <Card title="Conformidade por unidade">{comp.data?.por_unidade?.length ? <div style={{ height: Math.max(210, comp.data.por_unidade.length * 36 + 35) }} role="img" aria-label="Conformidade por unidade"><ResponsiveContainer><BarChart data={comp.data.por_unidade} layout="vertical" margin={{ left: 6, right: 25 }}><CartesianGrid stroke={C.grid} horizontal={false} /><XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} {...axis} /><YAxis type="category" dataKey="nome" width={145} tick={<YTick max={20} />} axisLine={false} tickLine={false} /><ChartTip fmt={(v) => fmtPct(v, 1)} /><Bar dataKey="pct" name="Conformidade" radius={[0, 5, 5, 0]}>{comp.data.por_unidade.map((x, i) => <Cell key={i} fill={(x.pct ?? 0) >= 90 ? C.success : (x.pct ?? 0) >= 60 ? C.mid : C.danger} />)}</Bar></BarChart></ResponsiveContainer></div> : <p className="py-8 text-sm text-muted-foreground">Sem unidades com exigências calculadas.</p>}</Card>
    </div></section>}
    {proc.data?.tempo_medio_lote_seg != null && <p className="text-right text-xs text-muted-foreground">Tempo médio de processamento dos lotes da empresa: {fmtNum(proc.data.tempo_medio_lote_seg, 1)} s</p>}
  </div>
}
