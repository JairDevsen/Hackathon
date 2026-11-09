import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis, Cell } from 'recharts'
import { Activity, Building2, Database, FileText, Plus, RefreshCw, TrendingUp, Users, AlertTriangle, HardDrive, Receipt, LifeBuoy, ScrollText, Bot, Trash2 } from 'lucide-react'
import { SectionLayout } from '@/components/shell/SectionLayout'
import { Button, Card, DataTable, EmptyState, ErrorState, Field, Input, KpiCard, Modal, SectionHeading, Select, SkeletonRows, StatusPill } from '@/components/ui'
import { C, ChartTip, SEQ, axis } from '@/components/charts'
import { useGet } from '@/lib/query'
import { api, setTenantOverride } from '@/lib/api'
import { fmtBytes, fmtDate, fmtDateTime, fmtMoney } from '@/lib/format'

export function MasterHome() {
  const r = useGet<any>('/admin/overview')
  if (r.error) return <ErrorState error={r.error} retry={r.refetch} />
  const o = r.data
  if (!o) return <SkeletonRows n={4} />
  return (
    <div>
      <SectionHeading eyebrow="Plataforma" title="Visão geral">Acompanhe clientes, processamento de documentos e indicadores da operação.</SectionHeading>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard label="Clientes ativos" icon={<Building2 className="h-4 w-4" />} value={o.clientes_ativos} hint={o.clientes_por_porte.map((p: any) => `${p.n} ${p.porte.toLowerCase()}`).join(' · ')} />
        <KpiCard label="Páginas no mês" icon={<FileText className="h-4 w-4" />} value={o.paginas_mes} />
        <KpiCard label="Armazenamento total" icon={<Database className="h-4 w-4" />} value={fmtBytes(o.armazenamento_total)} />
        <KpiCard label="Taxa de revisão humana (30d)" icon={<Users className="h-4 w-4" />} value={o.taxa_revisao_pct === null ? '—' : o.taxa_revisao_pct + '%'} />
        <KpiCard label="Lotes com falha/retentativa" icon={<AlertTriangle className="h-4 w-4" />} value={o.falhas_ia} tone={o.falhas_ia ? 'warning' : 'default'} />
        <KpiCard label="MRR" icon={<TrendingUp className="h-4 w-4" />} value={fmtMoney(o.mrr_centavos)} hint="preços por contrato (sob consulta)" />
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <Card title="Páginas por dia (30 dias)"><div className="h-56" role="img" aria-label="Páginas por dia"><ResponsiveContainer><BarChart data={o.paginas_por_dia}><CartesianGrid stroke={C.grid} vertical={false} /><XAxis dataKey="dia" {...axis} tickFormatter={(d) => d.slice(8)} /><YAxis {...axis} /><ChartTip /><Bar dataKey="paginas" name="Páginas" fill={C.brand} radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
        <Card title="Clientes perto da cota (≥ 80%)">{o.perto_da_cota.length ? <ul className="space-y-2 text-sm">{o.perto_da_cota.map((c: any) => <li key={c.id}><Link className="flex justify-between rounded-lg bg-warning-bg p-2 text-warning" to={`/app/clientes/${c.id}/armazenamento`}><span>{c.nome}</span><b>{c.pct}%</b></Link></li>)}</ul> : <p className="text-sm text-muted-foreground">Nenhum cliente perto da cota.</p>}</Card>
      </div>
    </div>
  )
}

export function TenantsPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const r = useGet<any[]>('/admin/tenants')
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ cnpj: '', razao_social: '', nome_fantasia: '', porte: 'MEDIA', admin_nome: '', admin_email: '', dominios: '' })
  const [err, setErr] = useState('')
  const create = async () => {
    setErr('')
    try { await api('/admin/tenants', { method: 'POST', body: { ...f, dominios_email: f.dominios ? f.dominios.split(',').map((x) => x.trim()) : undefined } }); setOpen(false); qc.invalidateQueries({ queryKey: ['/admin/tenants'] }) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div>
      <SectionHeading eyebrow="Clientes" title="Empresas clientes" action={<Button variant="primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Nova empresa</Button>}>Consulte o cadastro, o uso e a situação de cada empresa.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} onRow={(t) => nav(`/app/clientes/${t.id}`)} empty={<EmptyState title="Nenhuma empresa" />}
        cols={[{ key: 'razao_social', header: 'Empresa', render: (t) => <b className="text-brand-darker">{t.nome_fantasia ?? t.razao_social}</b> }, { key: 'cnpj', header: 'CNPJ' }, { key: 'porte', header: 'Porte' }, { key: 'status', header: 'Status', render: (t) => <StatusPill status={t.status} /> },
          { key: 'funcionarios', header: 'Funcionários' }, { key: 'uso', header: 'Armazenamento', render: (t) => `${fmtBytes(t.bytes_usados)} / ${fmtBytes(t.quota_bytes)}` }]} />
      <Modal wide open={open} onClose={() => setOpen(false)} eyebrow="Clientes" title="Nova empresa" footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button><Button variant="primary" onClick={create}>Cadastrar</Button></>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="CNPJ">{(id) => <Input id={id} value={f.cnpj} onChange={(e) => setF({ ...f, cnpj: e.target.value })} />}</Field>
          <Field label="Porte">{(id) => <Select id={id} value={f.porte} onChange={(e) => setF({ ...f, porte: e.target.value })}><option value="PEQUENA">Pequena</option><option value="MEDIA">Média</option><option value="GRANDE">Grande</option></Select>}</Field>
          <Field label="Razão social">{(id) => <Input id={id} value={f.razao_social} onChange={(e) => setF({ ...f, razao_social: e.target.value })} />}</Field>
          <Field label="Nome fantasia">{(id) => <Input id={id} value={f.nome_fantasia} onChange={(e) => setF({ ...f, nome_fantasia: e.target.value })} />}</Field>
          <Field label="Administrador (nome)">{(id) => <Input id={id} value={f.admin_nome} onChange={(e) => setF({ ...f, admin_nome: e.target.value })} />}</Field>
          <Field label="Administrador (e-mail)">{(id) => <Input id={id} type="email" value={f.admin_email} onChange={(e) => setF({ ...f, admin_email: e.target.value })} />}</Field>
          <Field label="Domínios permitidos" hint="Separados por vírgula. Padrão: domínio do administrador.">{(id) => <Input id={id} value={f.dominios} onChange={(e) => setF({ ...f, dominios: e.target.value })} />}</Field>
        </div>
        {err && <p role="alert" className="text-sm text-danger">{err}</p>}
      </Modal>
    </div>
  )
}

export function TenantLayout() {
  const { id } = useParams()
  const t = useGet<any>(`/admin/tenants/${id}`)
  const b = `/app/clientes/${id}`
  if (t.isLoading) return <SkeletonRows />
  if (!t.data) return <ErrorState error={t.error} />
  return (
    <SectionLayout back={{ to: '/app/clientes', label: 'Clientes' }}
      header={<div><p className="text-xs font-semibold uppercase tracking-[.14em] text-muted-foreground">Cliente</p><h1 className="font-display text-3xl font-bold text-brand-darker">{t.data.nome_fantasia ?? t.data.razao_social}</h1><p className="text-sm text-muted-foreground">{t.data.cnpj} · porte {t.data.porte} · <StatusPill status={t.data.status} /></p></div>}
      groups={[{ items: [{ to: b, label: 'Dados e porte', icon: Building2 }, { to: `${b}/plano`, label: 'Plano e limites', icon: Receipt }, { to: `${b}/armazenamento`, label: 'Armazenamento', icon: HardDrive }, { to: `${b}/usuarios`, label: 'Usuários', icon: Users },
        { to: `${b}/ia`, label: 'Uso da IA', icon: Bot }, { to: `${b}/faturamento`, label: 'Faturamento', icon: Receipt }, { to: `${b}/suporte`, label: 'Acessos de suporte', icon: LifeBuoy }, { to: `${b}/auditoria`, label: 'Auditoria', icon: ScrollText }] }]} />
  )
}

export function TenantDados() {
  const { id } = useParams()
  const qc = useQueryClient()
  const t = useGet<any>(`/admin/tenants/${id}`).data
  if (!t) return null
  const setStatus = async (status: string) => { await api(`/admin/tenants/${id}/status`, { method: 'POST', body: { status } }); qc.invalidateQueries() }
  return (
    <Card title="Dados e porte"><dl className="grid gap-3 text-sm sm:grid-cols-2">{[['Razão social', t.razao_social], ['CNPJ', t.cnpj], ['Porte', t.porte], ['Plano', t.plano], ['Domínios', t.dominios_email.join(', ')], ['Criada em', fmtDate(t.criado_em)]].map(([k, v]) => <div key={k}><dt className="text-xs uppercase text-muted-foreground">{k}</dt><dd>{v}</dd></div>)}</dl>
      <div className="mt-4 flex gap-2">{t.status !== 'ATIVO' && <Button onClick={() => setStatus('ATIVO')}>Ativar</Button>}{t.status === 'ATIVO' && <Button onClick={() => setStatus('SUSPENSO')}>Suspender</Button>}{t.status !== 'ENCERRADO' && <Button variant="danger" onClick={() => confirm('Encerrar a empresa derruba todas as sessões. Continuar?') && setStatus('ENCERRADO')}>Encerrar</Button>}</div></Card>
  )
}

export function TenantPlano() {
  const { id } = useParams()
  const qc = useQueryClient()
  const t = useGet<any>(`/admin/tenants/${id}`).data
  const plans = useGet<any[]>('/admin/plans').data
  const [f, setF] = useState<any>(null)
  if (!t) return null
  const v = f ?? { quota_bytes: t.quota_bytes / 2 ** 30, quota_paginas_mes: t.quota_paginas_mes, max_usuarios_rh: t.max_usuarios_rh ?? '', max_funcionarios: t.max_funcionarios ?? '', plano_id: t.plano_id }
  return (
    <Card title="Plano e limites"><div className="grid gap-3 sm:grid-cols-2">
      <Field label="Plano">{(i) => <Select id={i} value={v.plano_id} onChange={(e) => setF({ ...v, plano_id: e.target.value })}>{plans?.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}</Select>}</Field>
      <Field label="Cota de armazenamento (GB)">{(i) => <Input id={i} type="number" value={v.quota_bytes} onChange={(e) => setF({ ...v, quota_bytes: e.target.value })} />}</Field>
      <Field label="Páginas por mês">{(i) => <Input id={i} type="number" value={v.quota_paginas_mes} onChange={(e) => setF({ ...v, quota_paginas_mes: e.target.value })} />}</Field>
      <Field label="Usuários RH (vazio = ilimitado)">{(i) => <Input id={i} type="number" value={v.max_usuarios_rh} onChange={(e) => setF({ ...v, max_usuarios_rh: e.target.value })} />}</Field>
      <Field label="Funcionários ativos (vazio = ilimitado)">{(i) => <Input id={i} type="number" value={v.max_funcionarios} onChange={(e) => setF({ ...v, max_funcionarios: e.target.value })} />}</Field></div>
      <div className="mt-4"><Button variant="primary" disabled={!f} onClick={async () => { await api(`/admin/tenants/${id}`, { method: 'PATCH', body: { plano_id: v.plano_id, quota_bytes: Math.round(Number(v.quota_bytes) * 2 ** 30), quota_paginas_mes: Number(v.quota_paginas_mes), max_usuarios_rh: v.max_usuarios_rh === '' ? undefined : Number(v.max_usuarios_rh), max_funcionarios: v.max_funcionarios === '' ? undefined : Number(v.max_funcionarios) } }); setF(null); qc.invalidateQueries() }}>Salvar limites</Button></div></Card>
  )
}

export function TenantUso() {
  const { id, secao } = useParams()
  const u = useGet<any>(`/admin/tenants/${id}/usage`)
  if (!u.data) return <SkeletonRows />
  const d = u.data
  if (secao === 'armazenamento') return (<div className="space-y-4"><Card title="Eventos de armazenamento"><DataTable rows={d.eventos} cols={[{ key: 'tipo', header: 'Tipo' }, { key: 'bytes', header: 'Tamanho', render: (x) => fmtBytes(x.bytes) }, { key: 'criado_em', header: 'Quando', render: (x) => fmtDateTime(x.criado_em) }]} /></Card><Card title="Maiores lotes"><DataTable rows={d.maiores_lotes} cols={[{ key: 'arquivo_original', header: 'Arquivo' }, { key: 'bytes', header: 'Tamanho', render: (x) => fmtBytes(x.bytes) }, { key: 'total_paginas', header: 'Páginas' }]} /></Card></div>)
  if (secao === 'faturamento') return <Card title="Faturamento"><DataTable rows={d.faturas} empty={<EmptyState title="Nenhuma fatura" />} cols={[{ key: 'referencia', header: 'Referência' }, { key: 'valor_centavos', header: 'Valor', render: (x) => fmtMoney(x.valor_centavos) }, { key: 'status', header: 'Status' }, { key: 'vencimento', header: 'Vencimento', render: (x) => fmtDate(x.vencimento) }]} /></Card>
  return <Card title="Uso da IA por mês"><DataTable rows={d.mensal} cols={[{ key: 'mes', header: 'Mês' }, { key: 'paginas', header: 'Páginas' }, { key: 'docs', header: 'Documentos' }, { key: 'revisoes', header: 'Revisões' }, { key: 'tokens', header: 'Tokens' }, { key: 'custo_ia_centavos', header: 'Custo estimado', render: (x) => fmtMoney(x.custo_ia_centavos) }]} /></Card>
}

export function TenantUsuarios() {
  const { id } = useParams()
  const u = useGet<any[]>(`/admin/tenants/${id}/users`)
  const [sel, setSel] = useState<any>(null)
  const [j, setJ] = useState('')
  return (
    <Card title="Usuários (somente metadados)"><DataTable rows={u.data} loading={u.isLoading} cols={[{ key: 'nome', header: 'Nome' }, { key: 'email', header: 'E-mail' }, { key: 'role', header: 'Perfil' }, { key: 'status', header: 'Status', render: (x) => <StatusPill status={x.status} /> }, { key: 'ultimo_login', header: 'Último acesso', render: (x) => fmtDateTime(x.ultimo_login) },
      { key: 'a', header: '', align: 'right', render: (x) => x.role === 'ADMIN_EMPRESA' && <Button size="sm" onClick={() => setSel(x)}>Resetar 2FA</Button> }]} />
      <Modal open={!!sel} onClose={() => setSel(null)} eyebrow="Ação sensível" title="Resetar 2FA do administrador" footer={<><Button onClick={() => setSel(null)}>Cancelar</Button><Button variant="danger" disabled={j.length < 10} onClick={async () => { await api(`/admin/tenants/${id}/users/${sel.id}/reset-2fa`, { method: 'POST', body: { justificativa: j } }); setSel(null); setJ('') }}>Resetar</Button></>}>
        <p className="text-sm text-muted-foreground">Encerra todas as sessões de {sel?.nome} e exige novo convite. A justificativa fica na auditoria e a empresa a enxerga.</p>
        <Field label="Justificativa (mín. 10 caracteres)">{(i) => <Input id={i} value={j} onChange={(e) => setJ(e.target.value)} />}</Field></Modal></Card>
  )
}

export function TenantSuporte() {
  const { id } = useParams()
  const qc = useQueryClient()
  const r = useGet<any[]>(`/admin/tenants/${id}/support-access`)
  const [m, setM] = useState('')
  const nav = useNavigate()
  return (
    <Card title="Acessos de suporte"><p className="mb-3 text-sm text-muted-foreground">O acesso só vale depois que o administrador da empresa aprovar. Você enxerga apenas cópias anonimizadas.</p>
      <div className="mb-4 flex gap-2"><Input aria-label="Motivo" placeholder="Motivo do pedido (mín. 10 caracteres)" value={m} onChange={(e) => setM(e.target.value)} /><Button variant="primary" disabled={m.length < 10} onClick={async () => { await api(`/admin/support-access/${id}`, { method: 'POST', body: { motivo: m } }); setM(''); qc.invalidateQueries() }}>Solicitar acesso</Button></div>
      <DataTable rows={r.data} loading={r.isLoading} empty={<EmptyState title="Nenhum pedido" />} cols={[{ key: 'motivo', header: 'Motivo' }, { key: 'status', header: 'Status', render: (x) => <StatusPill status={x.status} /> }, { key: 'expira_em', header: 'Expira', render: (x) => fmtDateTime(x.expira_em) },
        { key: 'a', header: '', align: 'right', render: (x) => x.status === 'APROVADO' && new Date(x.expira_em) > new Date() && <Button size="sm" onClick={() => { setTenantOverride(id!); nav('/app/funcionarios') }}>Abrir como suporte</Button> }]} /></Card>
  )
}

export function AuditMaster() {
  const { id } = useParams()
  const [motivo, setMotivo] = useState('')
  const [go, setGo] = useState('')
  const r = useGet<{ items: any[] }>(go ? '/admin/audit' : null, { motivo: go, tenant: id, limit: 100 })
  const v = useGet<any>('/admin/audit/verify', { tenant: id })
  return (
    <div className="space-y-4">
      <SectionHeading eyebrow="Plataforma" title="Auditoria global">A consulta exige motivo e fica registrada na trilha da empresa.</SectionHeading>
      {v.data && <p className={`rounded-lg p-2 text-sm ${v.data.integra ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger'}`}>{v.data.integra ? `Cadeia de hash íntegra (${v.data.eventos} eventos)` : `CADEIA VIOLADA a partir do evento ${v.data.primeiro_elo_quebrado}`}</p>}
      <div className="flex gap-2"><Input aria-label="Motivo da consulta" placeholder="Motivo da consulta (mín. 10 caracteres)" value={motivo} onChange={(e) => setMotivo(e.target.value)} /><Button variant="primary" disabled={motivo.length < 10} onClick={() => setGo(motivo)}>Consultar</Button></div>
      {r.error && <ErrorState error={r.error} />}
      {go && <DataTable rows={r.data?.items} loading={r.isLoading} cols={[{ key: 'criado_em', header: 'Quando', render: (x) => fmtDateTime(x.criado_em) }, { key: 'acao', header: 'Ação' }, { key: 'ator_nome', header: 'Quem', render: (x) => x.ator_nome ?? x.ator_role }, { key: 'entidade', header: 'Entidade' }]} />}
    </div>
  )
}

export function PlansPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/admin/plans')
  return (
    <div><SectionHeading eyebrow="Planos" title="Planos e limites">Os limites por porte são padrões editáveis. Preço fica “sob consulta” até ser definido em contrato.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} cols={[{ key: 'nome', header: 'Plano' }, { key: 'clientes', header: 'Clientes' },
        { key: 'quota_bytes', header: 'Armazenamento (GB)', render: (p) => <Input className="!w-28" type="number" aria-label={`Armazenamento ${p.nome}`} defaultValue={Math.round(p.quota_bytes / 2 ** 30)} onBlur={async (e) => { await api(`/admin/plans/${p.id}`, { method: 'PATCH', body: { quota_bytes: Number(e.target.value) * 2 ** 30 } }); qc.invalidateQueries({ queryKey: ['/admin/plans'] }) }} /> },
        { key: 'quota_paginas_mes', header: 'Páginas/mês', render: (p) => <Input className="!w-28" type="number" aria-label={`Páginas ${p.nome}`} defaultValue={p.quota_paginas_mes} onBlur={async (e) => { await api(`/admin/plans/${p.id}`, { method: 'PATCH', body: { quota_paginas_mes: Number(e.target.value) } }); qc.invalidateQueries({ queryKey: ['/admin/plans'] }) }} /> },
        { key: 'max_usuarios_rh', header: 'Usuários RH', render: (p) => p.max_usuarios_rh ?? 'ilimitado' }, { key: 'max_funcionarios', header: 'Funcionários', render: (p) => p.max_funcionarios ?? 'ilimitado' }, { key: 'preco', header: 'Preço', render: (p) => fmtMoney(p.preco_mensal_centavos) }]} /></div>
  )
}

export function StoragePage() {
  const nav = useNavigate()
  const r = useGet<any[]>('/admin/storage')
  return (
    <div><SectionHeading eyebrow="Armazenamento" title="Armazenamento por cliente">Alertas em 80% e 95%. Ao estourar a cota, novos uploads são bloqueados (a leitura continua liberada).</SectionHeading>
      <div className="mb-5 h-56" role="img" aria-label="Uso de cota por cliente"><ResponsiveContainer><BarChart data={r.data ?? []}><CartesianGrid stroke={C.grid} vertical={false} /><XAxis dataKey="nome" {...axis} /><YAxis domain={[0, 100]} {...axis} /><ChartTip fmt={(v) => v + '%'} /><Bar dataKey="pct" name="Uso da cota" radius={[8, 8, 0, 0]}>{(r.data ?? []).map((d, i) => <Cell key={i} fill={d.pct >= 95 ? C.danger : d.pct >= 80 ? C.warning : SEQ[3]} />)}</Bar></BarChart></ResponsiveContainer></div>
      <DataTable rows={r.data} loading={r.isLoading} onRow={(t) => nav(`/app/clientes/${t.id}/armazenamento`)} cols={[{ key: 'nome', header: 'Cliente' }, { key: 'porte', header: 'Porte' }, { key: 'uso', header: 'Uso', render: (t) => `${fmtBytes(t.bytes_usados)} / ${fmtBytes(t.quota_bytes)} (${t.pct}%)` }, { key: 'paginas_mes', header: 'Páginas no mês', render: (t) => `${t.paginas_mes} / ${t.quota_paginas_mes}` }, { key: 'crescimento_30d', header: 'Crescimento 30d', render: (t) => fmtBytes(t.crescimento_30d) }]} /></div>
  )
}

export function CatalogPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/admin/document-types')
  return (
    <div><SectionHeading eyebrow="Plataforma" title="Catálogo global de tipos de documento">Os {r.data?.length ?? 0} tipos, com validade padrão e categoria. A alteração vale para todas as empresas. Tipos marcados "IA" foram reconhecidos pela IA durante a leitura de documentos que o catálogo curado não cobria: confira o nome (clique para renomear) e confirme.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} cols={[{ key: 'codigo', header: 'Código' }, { key: 'nome', header: 'Nome', render: (t) => t.origem === 'IA' ? <Input className="!w-64" aria-label={`Nome do tipo ${t.codigo}`} defaultValue={t.nome} onBlur={async (e) => { const v = e.target.value.trim(); if (v.length >= 4 && v !== t.nome) { await api(`/admin/document-types/${t.id}`, { method: 'PATCH', body: { nome: v } }); qc.invalidateQueries({ queryKey: ['/admin/document-types'] }) } }} /> : t.nome }, { key: 'categoria', header: 'Categoria' }, { key: 'escopo', header: 'Escopo' }, { key: 'sensivel_saude', header: 'Saúde', render: (t) => (t.sensivel_saude ? 'Sim' : '—') },
        { key: 'origem', header: 'Origem', render: (t) => (t.origem === 'IA' ? (t.revisado_em ? <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs font-semibold text-success">IA · confirmado</span> : <span className="inline-flex items-center gap-2"><span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning">IA · não revisado</span><Button variant="ghost" aria-label={`Confirmar o tipo ${t.nome}`} onClick={async () => { await api(`/admin/document-types/${t.id}`, { method: 'PATCH', body: { revisado: true } }); qc.invalidateQueries({ queryKey: ['/admin/document-types'] }) }}>Confirmar</Button></span>) : 'Curado') }, { key: 'documentos', header: 'Documentos' },
        { key: 'validade_padrao_dias', header: 'Validade padrão (dias)', render: (t) => <Input className="!w-24" type="number" aria-label={`Validade de ${t.nome}`} defaultValue={t.validade_padrao_dias ?? ''} onBlur={async (e) => { if (e.target.value) { await api(`/admin/document-types/${t.id}`, { method: 'PATCH', body: { validade_padrao_dias: Number(e.target.value) } }); qc.invalidateQueries({ queryKey: ['/admin/document-types'] }) } }} /> }]} /></div>
  )
}

export function QualityPage() {
  const [run, setRun] = useState(false)
  const r = useGet<any>(run ? '/admin/ia/quality' : null)
  return (
    <div><SectionHeading eyebrow="Plataforma" title="Qualidade da IA" action={<Button variant="primary" loading={r.isFetching} onClick={() => (run ? r.refetch() : setRun(true))}><Activity className="h-4 w-4" />Rodar benchmark</Button>}>Roda lotes fictícios com gabarito contra o IA Core e mede separação, classificação e extração. Útil para acompanhar a evolução dos prompts e comparar modelos.</SectionHeading>
      {r.error && <ErrorState error={r.error} />}
      {r.data && <><p className="mb-3 text-sm text-muted-foreground">Provedor: <b>{r.data.provider}</b></p>
        <div className="space-y-5">{r.data.resultados.map((x: any) => (
          <Card key={x.lote} title={`${x.lote} — ${x.segundos}s`}>
            <div className="mb-4 grid gap-3 sm:grid-cols-3"><KpiCard label="Separação" value={Math.round(x.acuracia_separacao * 100) + '%'} /><KpiCard label="Classificação" value={Math.round(x.acuracia_classificacao * 100) + '%'} /><KpiCard label="Extração do CPF" value={Math.round(x.acuracia_extracao_cpf * 100) + '%'} /></div>
            <DataTable rows={Object.entries<any>(x.por_tipo).map(([tipo, v]) => ({ id: tipo, tipo, ...v, pct: Math.round((100 * v.acertos) / v.total) }))} cols={[{ key: 'tipo', header: 'Tipo' }, { key: 'acertos', header: 'Acertos' }, { key: 'total', header: 'Total' }, { key: 'pct', header: '%' }]} />
            <h3 className="mb-1 mt-4 text-sm font-semibold text-brand-darker">Matriz de confusão (esperado → previsto)</h3>
            <pre className="overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(x.matriz_confusao, null, 1)}</pre></Card>))}</div></>}
      {!run && <EmptyState icon={<Activity className="h-5 w-5" />} title="Nenhuma execução ainda" text="Clique em “Rodar benchmark” para medir o desempenho atual." />}
    </div>
  )
}

export function QueuesPage() {
  const qc = useQueryClient()
  const o = useGet<any>('/admin/ia/overview', undefined, { refetchInterval: 10000 })
  const d = useGet<any[]>('/admin/ia/dead-letters')
  return (
    <div><SectionHeading eyebrow="Plataforma" title="Filas e jobs">Acompanhe o processamento e retome lotes com falhas persistentes.</SectionHeading>
      {o.data && <div className="mb-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><KpiCard label="Processando" value={o.data.fila.processando} /><KpiCard label="Falhos" value={o.data.fila.falhos} tone={o.data.fila.falhos ? 'danger' : 'default'} /><KpiCard label="Reprocessamentos" value={o.data.reprocessamentos} /><KpiCard label="Tempo médio por página" value={o.data.tempo_medio_por_pagina_seg ? o.data.tempo_medio_por_pagina_seg + 's' : '—'} /></div>}
      <Card title="Fila de mensagens mortas (falhas persistentes após 3 tentativas)">
        <DataTable rows={d.data} loading={d.isLoading} empty={<EmptyState title="Nenhuma falha persistente" />} cols={[{ key: 'empresa', header: 'Empresa' }, { key: 'arquivo_original', header: 'Lote' }, { key: 'erro', header: 'Erro' }, { key: 'tentativas', header: 'Tentativas' }, { key: 'criado_em', header: 'Quando', render: (x) => fmtDateTime(x.criado_em) },
          { key: 'a', header: '', align: 'right', render: (x) => (x.resolvido_em ? <StatusPill status="OK" label="Retomado" /> : <Button size="sm" onClick={async () => { await api(`/admin/ia/dead-letters/${x.id}/retry`, { method: 'POST' }); qc.invalidateQueries({ queryKey: ['/admin/ia/dead-letters'] }) }}><RefreshCw className="h-3.5 w-3.5" />Retomar</Button>) }]} /></Card>
      <Card className="mt-5" title="Custo estimado por empresa (mês)"><DataTable rows={o.data?.custo_por_empresa} cols={[{ key: 'empresa', header: 'Empresa' }, { key: 'tokens', header: 'Tokens' }, { key: 'custo_centavos', header: 'Custo', render: (x) => fmtMoney(x.custo_centavos) }]} empty={<EmptyState title="Sem consumo registrado neste mês" />} /></Card>
    </div>
  )
}

export function MasterAuditPage() {
  const [motivo, setMotivo] = useState('')
  const [go, setGo] = useState('')
  const r = useGet<{ items: any[] }>(go ? '/admin/audit' : null, { motivo: go, limit: 100 })
  const v = useGet<any>('/admin/audit/verify')
  return (
    <div className="space-y-4"><SectionHeading eyebrow="Auditoria" title="Auditoria global">Consulte a trilha de qualquer empresa. O motivo é obrigatório e a consulta fica visível para a empresa.</SectionHeading>
      {v.data && <p className={`rounded-lg p-2 text-sm ${v.data.integra ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger'}`}>Trilha global: {v.data.integra ? `íntegra (${v.data.eventos} eventos)` : 'CADEIA VIOLADA'}</p>}
      <div className="flex gap-2"><Input aria-label="Motivo da consulta" placeholder="Motivo da consulta (mín. 10 caracteres)" value={motivo} onChange={(e) => setMotivo(e.target.value)} /><Button variant="primary" disabled={motivo.length < 10} onClick={() => setGo(motivo)}>Consultar</Button></div>
      {go && <DataTable rows={r.data?.items} loading={r.isLoading} cols={[{ key: 'criado_em', header: 'Quando', render: (x) => fmtDateTime(x.criado_em) }, { key: 'acao', header: 'Ação' }, { key: 'ator_nome', header: 'Quem', render: (x) => x.ator_nome ?? x.ator_role }, { key: 'entidade', header: 'Entidade' }]} />}
    </div>
  )
}

export function MasterUsersPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/admin/users')
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ nome: '', email: '' })
  return (
    <div><SectionHeading eyebrow="Plataforma" title="Usuários Master" action={<Button variant="primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Convidar</Button>}>Gerencie o acesso da equipe responsável pela plataforma.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} cols={[{ key: 'nome', header: 'Nome' }, { key: 'email', header: 'E-mail' }, { key: 'status', header: 'Status', render: (x) => <StatusPill status={x.status} /> }, { key: 'ultimo_login', header: 'Último acesso', render: (x) => fmtDateTime(x.ultimo_login) }]} />
      <Modal open={open} onClose={() => setOpen(false)} eyebrow="Usuários Master" title="Convidar" footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button><Button variant="primary" onClick={async () => { await api('/admin/users', { method: 'POST', body: f }); setOpen(false); qc.invalidateQueries({ queryKey: ['/admin/users'] }) }}>Enviar convite</Button></>}>
        <Field label="Nome">{(i) => <Input id={i} value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />}</Field><Field label="E-mail">{(i) => <Input id={i} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}</Field></Modal></div>
  )
}

const FRASE_RESET = 'RESETAR TUDO'

/** Zona de perigo: apaga os dados (não a configuração) de todas as empresas ou de uma. Só o Master chega aqui; a API ainda pede o código por e-mail. */
export function ResetPage() {
  const tenants = useGet<any[]>('/admin/tenants')
  const [alvo, setAlvo] = useState('')
  const [motivo, setMotivo] = useState('')
  const [frase, setFrase] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [res, setRes] = useState<any>(null)
  const nome = alvo ? (tenants.data?.find((t) => t.id === alvo)?.nome_fantasia || tenants.data?.find((t) => t.id === alvo)?.razao_social) : 'TODAS as empresas'
  const pronto = frase === FRASE_RESET && motivo.trim().length >= 5
  const executar = async () => {
    setBusy(true); setErr(''); setRes(null)
    try { setRes(await api('/admin/reset', { method: 'POST', body: { confirmar: frase, motivo, tenant_id: alvo || undefined } })); setFrase(''); setMotivo('') } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <SectionHeading eyebrow="Plataforma" title="Redefinir dados" showTitle>Apaga os dados de teste ou de uma carga errada para recomeçar do zero. A ação é definitiva.</SectionHeading>
      <div role="alert" className="rounded-xl border border-danger/40 bg-danger-bg/40 p-4 text-sm">
        <p className="mb-2 flex items-center gap-2 font-semibold text-danger"><AlertTriangle className="h-4 w-4" aria-hidden />O que será apagado</p>
        <ul className="list-disc space-y-0.5 pl-5">
          <li>funcionários, terceirizadas e fornecedores;</li><li>lotes, páginas, documentos e revisões;</li><li>indicadores de risco e pendências;</li><li>notificações e <b>todos os arquivos guardados</b> (originais, páginas e PDFs gerados).</li>
        </ul>
        <p className="mb-1 mt-3 font-semibold">O que continua</p>
        <ul className="list-disc space-y-0.5 pl-5"><li>as empresas e seus usuários (administradores e RH);</li><li>unidades, cargos, setores, documentos obrigatórios, retenção e configurações;</li><li>planos, faturas, o consumo mensal já contabilizado e a trilha de auditoria (que registra este reset).</li></ul>
      </div>
      <Card title="Confirmar">
        <div className="space-y-3">
          <Field label="Empresa">{(id) => <Select id={id} value={alvo} onChange={(e) => setAlvo(e.target.value)}><option value="">Todas as empresas</option>{tenants.data?.map((t) => <option key={t.id} value={t.id}>{t.nome_fantasia || t.razao_social}</option>)}</Select>}</Field>
          <Field label="Motivo (fica na auditoria)">{(id) => <Input id={id} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: reiniciar a base de demonstração" />}</Field>
          <Field label={`Digite ${FRASE_RESET} para confirmar`}>{(id) => <Input id={id} value={frase} autoComplete="off" onChange={(e) => setFrase(e.target.value)} />}</Field>
          {err && <p role="alert" className="rounded-lg bg-danger-bg p-2 text-sm text-danger">{err}</p>}
          <Button variant="danger" loading={busy} disabled={!pronto} onClick={executar}><Trash2 className="h-4 w-4" />Apagar dados de {nome}</Button>
          <p className="text-xs text-muted-foreground">Será pedido um código enviado ao seu e-mail. Se houver lote em processamento, o reset é recusado.</p>
        </div>
      </Card>
      {res && (
        <div role="status" className="rounded-xl border border-success/40 bg-success-bg/40 p-4 text-sm">
          <p className="font-semibold text-success">Dados apagados em {res.empresas} empresa(s).</p>
          <p>{res.total.funcionarios} funcionário(s), {res.total.fornecedores} empresa(s) terceirizada(s)/fornecedora(s), {res.total.lotes} lote(s), {res.total.documentos} documento(s), {res.total.riscos} risco(s), {res.total.pendencias} pendência(s); {fmtBytes(res.total.bytes_liberados)} liberados, {res.arquivos_removidos} arquivo(s) removido(s).</p>
          {res.empresas_com_falha_nos_arquivos > 0 && <p className="mt-1 text-warning">A remoção de arquivos falhou em {res.empresas_com_falha_nos_arquivos} empresa(s): sobram objetos cifrados sem referência no banco (ver o log do servidor).</p>}
        </div>
      )}
    </div>
  )
}
