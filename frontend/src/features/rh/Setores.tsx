import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Building, ListChecks, Search, ShieldAlert, Users } from 'lucide-react'
import { Avatar, Card, ComplianceRing, DataTable, EmptyState, ErrorState, Input, KpiCard, SectionHeading, Segmented, SkeletonRows, StatusPill, clsx } from '@/components/ui'
import { useGet } from '@/lib/query'
import { useAuth } from '@/lib/auth'
import { competenciaLabel, fmtDate } from '@/lib/format'
import { VinculoChip } from './Lists'

const pct = (x: { ok: number; total: number }) => (x.total ? (100 * x.ok) / x.total : 0)

/** Setores com a conformidade de quem trabalha neles (pessoas da casa e de terceirizadas) e os riscos abertos. */
export function SectorsPage() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [soPend, setSoPend] = useState(false)
  const r = useGet<any[]>('/departments')
  const list = useMemo(() => (r.data ?? []).filter((d) => d.ativo && (!q || d.nome.toLowerCase().includes(q.toLowerCase())) && (!soPend || d.pendencias > 0 || d.riscos_altos > 0)), [r.data, q, soPend])
  const todos = (r.data ?? []).filter((d) => d.ativo)
  return (
    <div>
      <SectionHeading eyebrow="Quem trabalha" title="Setores" action={user?.role === 'ADMIN_EMPRESA' && <Link to="/app/configuracoes/cargos" className="text-sm font-semibold text-brand underline">Gerenciar setores e cargos</Link>}>
        Veja onde estão as pendências: cada setor reúne a conformidade das pessoas que trabalham nele, incluindo as de empresas terceirizadas alocadas ali.
      </SectionHeading>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <KpiCard label="Setores" value={todos.length} icon={<Building className="h-4 w-4" />} />
        <KpiCard label="Com pendências" value={todos.filter((d) => d.pendencias > 0).length} tone={todos.some((d) => d.pendencias > 0) ? 'warning' : 'success'} icon={<ListChecks className="h-4 w-4" />} />
        <KpiCard label="Com risco trabalhista alto" value={todos.filter((d) => d.riscos_altos > 0).length} tone={todos.some((d) => d.riscos_altos > 0) ? 'danger' : 'success'} icon={<ShieldAlert className="h-4 w-4" />} />
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden /><Input aria-label="Buscar setor" className="!w-64 !pl-9" placeholder="Buscar setor" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={soPend} onChange={(e) => setSoPend(e.target.checked)} />Só com pendência ou risco alto</label>
      </div>
      {r.error ? <ErrorState error={r.error} retry={r.refetch} /> : r.isLoading ? <SkeletonRows /> : !list.length ? (
        <EmptyState icon={<Building className="h-5 w-5" />} title={todos.length ? 'Nenhum setor com esses filtros' : 'Nenhum setor cadastrado'} text={todos.length ? undefined : 'Cadastre os setores em Configurações › Setores e cargos e vincule as pessoas a eles.'} />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((d) => (
            <li key={d.id}>
              <Link to={`/app/setores/${d.id}`} className="glass-panel flex h-full items-center gap-4 p-4 transition hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">
                <ComplianceRing pct={pct(d)} size={64} />
                <span className="min-w-0 flex-1">
                  <b className="block truncate text-brand-darker">{d.nome}</b>
                  <span className="block text-sm text-muted-foreground">{d.ativos} pessoa(s){d.terceirizados > 0 && <> · {d.terceirizados} terceirizada(s)</>}</span>
                  <span className="mt-1 flex flex-wrap gap-1.5 text-xs">
                    {d.vencidos > 0 && <span className="rounded bg-danger-bg px-1.5 py-0.5 font-semibold text-danger">{d.vencidos} vencido(s)</span>}
                    {d.pendencias - d.vencidos > 0 && <span className="rounded bg-warning-bg px-1.5 py-0.5 font-semibold text-warning">{d.pendencias - d.vencidos} pendente(s)</span>}
                    {d.riscos_altos > 0 && <span className="rounded bg-danger-bg px-1.5 py-0.5 font-semibold text-danger">{d.riscos_altos} risco(s) alto(s)</span>}
                    {!d.pendencias && !d.riscos && <span className={clsx('rounded px-1.5 py-0.5 font-semibold', d.total ? 'bg-success-bg text-success' : 'bg-brand-lighter text-muted-foreground')}>{d.total ? 'Em dia' : 'Sem exigências'}</span>}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Um setor: indicadores, as pessoas dele (com o vínculo: própria, terceirizada ou fornecedor) e o que está pendente. */
export function SectorDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [vinculo, setVinculo] = useState('')
  const d = useGet<any>(`/departments/${id}`)
  const emp = useGet<{ items: any[] }>('/employees', { setor: id, vinculo, limit: 100, status: 'ATIVO' }, { keep: true })
  const pend = useGet<{ items: any[] }>('/compliance', { setor: id, limit: 100 })
  if (d.isLoading) return <SkeletonRows />
  if (d.error || !d.data) return <ErrorState error={d.error ?? new Error('Setor não encontrado')} />
  const s = d.data
  const porTipo = Object.entries((pend.data?.items ?? []).reduce<Record<string, any[]>>((a, i) => { (a[i.tipo_nome] ??= []).push(i); return a }, {})).sort((a, b) => b[1].length - a[1].length)
  return (
    <div>
      <Link to="/app/setores" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"><ArrowLeft className="h-4 w-4" />Voltar para setores</Link>
      <div className="glass-panel mb-5 flex flex-wrap items-center gap-4 p-4">
        <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-lighter text-brand-darker"><Building className="h-6 w-6" aria-hidden /></span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-display text-3xl font-bold text-brand-darker">{s.nome}</h1>
          <p className="text-sm text-muted-foreground">{s.descricao || 'Setor'} · {s.ativos} pessoa(s) ativa(s){s.terceirizados > 0 && <> · {s.terceirizados} de empresas terceirizadas</>}</p>
        </div>
        <div className="flex gap-6 text-center">
          <div><p className={clsx('text-2xl font-bold', s.pendencias ? 'text-warning' : 'text-success')}>{s.pendencias}</p><p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Pendências</p></div>
          <div><p className={clsx('text-2xl font-bold', s.riscos_altos ? 'text-danger' : 'text-success')}>{s.riscos}</p><p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Riscos abertos</p></div>
          <div><ComplianceRing pct={pct(s)} /><p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Conformidade</p></div>
        </div>
      </div>
      <div className="grid gap-5 min-[1100px]:grid-cols-[1fr_22rem]">
        <section aria-label="Pessoas do setor">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-display text-lg font-bold text-brand-darker">Pessoas do setor</h2>
            <Segmented value={vinculo} onChange={setVinculo} label="Vínculo" options={[{ value: '', label: 'Todos' }, { value: 'PROPRIA', label: 'Própria empresa' }, { value: 'TERCEIRIZADA', label: 'Terceirizadas' }, { value: 'FORNECEDOR', label: 'Fornecedores' }]} />
          </div>
          {emp.error ? <ErrorState error={emp.error} retry={emp.refetch} /> : (
            <DataTable rows={emp.data?.items} loading={emp.isLoading} onRow={(e) => nav(`/app/funcionarios/${e.id}`)} empty={<EmptyState icon={<Users className="h-5 w-5" />} title="Ninguém neste filtro" text="Vincule pessoas ao setor no cadastro do funcionário." />}
              cols={[{ key: 'nome', header: 'Nome', render: (e) => <span className="flex items-center gap-2"><Avatar nome={e.nome} size="sm" /><b className="text-brand-darker">{e.nome}</b></span> }, { key: 'cargo', header: 'Cargo' }, { key: 'vinculo', header: 'Vínculo', render: (e) => <VinculoChip e={e} /> },
                { key: 'conf', header: 'Conformidade', render: (e) => <span className="flex items-center gap-2"><ComplianceRing pct={pct(e)} size={34} label={false} />{e.pendencias ? `${e.pendencias} pend.` : 'Em dia'}</span> }]} />
          )}
        </section>
        <aside aria-label="Pendências do setor">
          <Card title="O que falta no setor">
            {pend.isLoading ? <SkeletonRows n={3} /> : !porTipo.length ? <p className="text-sm text-muted-foreground">Nenhum documento pendente ou vencido.</p> : (
              <ul className="space-y-3">{porTipo.slice(0, 8).map(([tipo, itens]) => (
                <li key={tipo}>
                  <p className="flex items-center justify-between text-sm font-semibold text-brand-darker">{tipo}<span className="rounded-full bg-warning-bg px-2 text-xs text-warning">{itens.length}</span></p>
                  <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">{itens.slice(0, 3).map((i) => (
                    <li key={i.id} className="flex items-center justify-between gap-2"><Link to={`/app/funcionarios/${i.employee_id}`} className="truncate hover:underline">{i.funcionario}</Link><span className="flex shrink-0 items-center gap-1">{/^\d{4}-\d{2}$/.test(i.referencia) ? competenciaLabel(i.referencia) : i.vence_em ? fmtDate(i.vence_em) : ''}<StatusPill status={i.status} /></span></li>
                  ))}{itens.length > 3 && <li>+{itens.length - 3} pessoa(s)</li>}</ul>
                </li>))}
              </ul>
            )}
          </Card>
        </aside>
      </div>
    </div>
  )
}
