import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ClipboardList, FileText, FolderOpen, Pencil, Plus, ShieldAlert, ShieldCheck, Truck, UserCheck, Users } from 'lucide-react'
import { SectionLayout, type SideGroup } from '@/components/shell/SectionLayout'
import { Avatar, Button, Card, ComplianceRing, DataTable, EmptyState, ErrorState, Field, Input, Modal, SectionHeading, Select, SkeletonRows, StatusPill, clsx } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { CATEGORIAS_RISCO, cnpjMask, cnpjValido, competenciaLabel, EXPOSICAO, fmtDate } from '@/lib/format'

export function ExposicaoBadge({ v }: { v?: string }) {
  const e = EXPOSICAO[v ?? 'BAIXA'] ?? EXPOSICAO.BAIXA
  return <span title={e.explica} className={clsx('inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', e.cls)}>{e.label}</span>
}

const TIPOS: Record<string, string> = { TERCEIRIZADA: 'Terceirizada', FORNECEDOR: 'Fornecedor' }
const nomeCurto = (e: any) => e.nome_fantasia || e.razao_social

/** Lista de fornecedores e terceirizadas, agrupados pelo CNPJ lido nos documentos, com a exposição da contratante a processo trabalhista. */
export function SuppliersPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { can } = useAuth()
  const [sp, setSp] = useSearchParams()
  const [f, setF] = useState({ q: '', tipo: '', status: '' })
  const [newOpen, setNewOpen] = useState(false)
  const r = useGet<any[]>('/suppliers', { ...f, pre: sp.get('pre') || '' }, { keep: true })
  const list = r.data ?? []
  const alta = list.filter((s) => s.exposicao === 'ALTA').length
  return (
    <div>
      <SectionHeading eyebrow="Terceirização" title="Fornecedores e terceirizadas" action={can('funcionarios:gerir') && <Button variant="primary" onClick={() => setNewOpen(true)}><Plus className="h-4 w-4" />Novo fornecedor</Button>}>
        O CNPJ lido nos documentos identifica a empresa e agrupa seus funcionários e documentos. A contratante responde subsidiariamente pelas obrigações trabalhistas que a terceirizada deixar de cumprir (TST Súmula 331, IV): os documentos exigidos servem para reduzir esse risco, e os indicadores mostram onde ele aparece.
      </SectionHeading>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Card><p className="text-xs text-muted-foreground">Fornecedores listados</p><p className="text-2xl font-bold text-brand-darker">{list.length}</p></Card>
        <Card><p className="text-xs text-muted-foreground">Com exposição alta a processo trabalhista</p><p className={clsx('text-2xl font-bold', alta ? 'text-danger' : 'text-success')}>{alta}</p></Card>
        <Card><p className="text-xs text-muted-foreground">Pré-cadastros a completar</p><p className="text-2xl font-bold text-warning">{list.filter((s) => s.pre_cadastro).length}</p></Card>
      </div>
      <div className="mb-4 flex flex-wrap gap-3">
        <Input aria-label="Buscar fornecedor" className="!w-64" placeholder="Nome ou CNPJ" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
        <Select aria-label="Origem do cadastro" className="!w-52" value={sp.get('pre') || ''} onChange={(e) => setSp(e.target.value ? { pre: e.target.value } : {})}><option value="">Todos os cadastros</option><option value="1">Pré-cadastrados pelo lote</option></Select>
        <Select aria-label="Tipo" className="!w-44" value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}><option value="">Todos os tipos</option><option value="TERCEIRIZADA">Terceirizada</option><option value="FORNECEDOR">Fornecedor</option></Select>
        <Select aria-label="Status" className="!w-40" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">Todos os status</option><option value="ATIVO">Ativo</option><option value="INATIVO">Inativo</option></Select>
      </div>
      {r.error ? <ErrorState error={r.error} retry={r.refetch} /> : (
        <DataTable rows={list} loading={r.isLoading} onRow={(s) => nav(`/app/fornecedores/${s.id}`)}
          empty={<EmptyState icon={<Truck className="h-5 w-5" />} title="Nenhum fornecedor" text="Envie um lote com documentos de uma terceirizada: o CNPJ lido cria o fornecedor e agrupa tudo dele. Também é possível cadastrar manualmente." />}
          cols={[
            { key: 'razao_social', header: 'Empresa', render: (s) => <span className="flex items-center gap-2"><Avatar nome={nomeCurto(s)} size="sm" /><span><b className="block text-brand-darker">{nomeCurto(s)}</b><span className="text-xs text-muted-foreground">{cnpjMask(s.cnpj)}</span></span>{s.pre_cadastro && <span className="rounded bg-warning-bg px-1.5 py-0.5 text-[10px] font-semibold text-warning">Pré-cadastro</span>}</span> },
            { key: 'tipo', header: 'Tipo', render: (s) => TIPOS[s.tipo] ?? s.tipo },
            { key: 'funcionarios', header: 'Funcionários' },
            { key: 'conf', header: 'Conformidade', render: (s) => <span className="flex items-center gap-2"><ComplianceRing pct={s.total ? (100 * s.ok) / s.total : 0} size={34} />{s.pendencias > 0 && <span className="text-xs text-muted-foreground">{s.pendencias} pend.</span>}</span> },
            { key: 'riscos', header: 'Riscos', render: (s) => s.riscos ? <span className={s.riscos_altos ? 'font-semibold text-danger' : 'text-warning'}>{s.riscos}{s.riscos_altos ? ` (${s.riscos_altos} alto)` : ''}</span> : <span className="text-muted-foreground">—</span> },
            { key: 'exposicao', header: 'Exposição', render: (s) => s.status === 'INATIVO' ? <StatusPill status="INATIVO" /> : <ExposicaoBadge v={s.exposicao} /> },
          ]} />
      )}
      <SupplierForm open={newOpen} onClose={() => setNewOpen(false)} onDone={(id) => { setNewOpen(false); qc.invalidateQueries({ queryKey: ['/suppliers'] }); nav(`/app/fornecedores/${id}`) }} />
    </div>
  )
}

/** Cadastro (novo) ou edição/complemento de um fornecedor. */
function SupplierForm({ open, onClose, onDone, edit }: { open: boolean; onClose: () => void; onDone: (id: string) => void; edit?: any }) {
  const ini = () => ({ cnpj: edit ? cnpjMask(edit.cnpj) : '', razao_social: edit?.razao_social ?? '', nome_fantasia: edit?.nome_fantasia ?? '', tipo: edit?.tipo ?? 'TERCEIRIZADA', criticidade: edit?.criticidade ?? 'MEDIA',
    objeto: edit?.objeto ?? '', contrato_inicio: edit?.contrato_inicio?.slice(0, 10) ?? '', contrato_fim: edit?.contrato_fim?.slice(0, 10) ?? '', responsavel_nome: edit?.responsavel_nome ?? '', responsavel_email: edit?.responsavel_email ?? '' })
  const [v, setV] = useState<Record<string, string>>(ini)
  const [conferido, setConferido] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const set = (k: string) => (e: { target: { value: string } }) => setV({ ...v, [k]: k === 'cnpj' ? cnpjMask(e.target.value) : e.target.value })
  const cnpjOk = edit ? true : cnpjValido(v.cnpj)
  const save = async () => {
    setBusy(true); setErr('')
    try {
      if (edit) {
        const body = Object.fromEntries(Object.entries(v).filter(([k]) => k !== 'cnpj')) // o CNPJ não muda: é a chave que liga os documentos
        await api(`/suppliers/${edit.id}`, { method: 'PATCH', body: { ...body, ...(edit.pre_cadastro && conferido ? { pre_cadastro: false } : {}) } })
        onDone(edit.id)
      } else {
        const r = await api<{ id: string }>('/suppliers', { method: 'POST', body: v })
        onDone(r.id)
      }
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal wide open={open} onClose={onClose} eyebrow="Terceirização" title={edit ? (edit.pre_cadastro ? 'Completar cadastro do fornecedor' : 'Editar fornecedor') : 'Novo fornecedor'}
      footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={!cnpjOk || v.razao_social.trim().length < 2} onClick={save}>Salvar</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="CNPJ *" error={v.cnpj && !cnpjOk ? 'CNPJ inválido: confira os dígitos' : undefined} hint={edit ? 'O CNPJ não muda: ele liga os documentos ao fornecedor.' : undefined}>{(id, bad) => <Input id={id} aria-invalid={bad} inputMode="numeric" value={v.cnpj} onChange={set('cnpj')} disabled={!!edit} />}</Field>
        <Field label="Razão social *">{(id) => <Input id={id} value={v.razao_social} onChange={set('razao_social')} />}</Field>
        <Field label="Nome fantasia">{(id) => <Input id={id} value={v.nome_fantasia} onChange={set('nome_fantasia')} />}</Field>
        <Field label="Tipo" hint="Terceirizada tem empregados alocados (cobra certidões e guias mensais). Fornecedor, não.">{(id) => <Select id={id} value={v.tipo} onChange={set('tipo')}><option value="TERCEIRIZADA">Terceirizada</option><option value="FORNECEDOR">Fornecedor</option></Select>}</Field>
        <Field label="Criticidade para a operação">{(id) => <Select id={id} value={v.criticidade} onChange={set('criticidade')}><option value="BAIXA">Baixa</option><option value="MEDIA">Média</option><option value="ALTA">Alta</option></Select>}</Field>
        <Field label="Objeto do contrato">{(id) => <Input id={id} value={v.objeto} onChange={set('objeto')} placeholder="Ex.: limpeza e conservação" />}</Field>
        <Field label="Início do contrato">{(id) => <Input id={id} type="date" value={v.contrato_inicio} onChange={set('contrato_inicio')} />}</Field>
        <Field label="Fim do contrato">{(id) => <Input id={id} type="date" value={v.contrato_fim} onChange={set('contrato_fim')} />}</Field>
        <Field label="Responsável na contratante">{(id) => <Input id={id} value={v.responsavel_nome} onChange={set('responsavel_nome')} />}</Field>
        <Field label="E-mail do responsável">{(id) => <Input id={id} type="email" value={v.responsavel_email} onChange={set('responsavel_email')} />}</Field>
      </div>
      {edit?.pre_cadastro && <label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={conferido} onChange={(e) => setConferido(e.target.checked)} />Cadastro conferido: remover a marca de pré-cadastro</label>}
      {err && <p role="alert" className="mt-3 rounded-lg bg-danger-bg p-2 text-sm text-danger">{err}</p>}
    </Modal>
  )
}

export function SupplierLayout() {
  const { id } = useParams()
  const sup = useGet<any>(`/suppliers/${id}`)
  const s = sup.data
  if (sup.isLoading) return <SkeletonRows />
  if (sup.error || !s) return <ErrorState error={sup.error ?? new Error('Fornecedor não encontrado')} />
  const base = `/app/fornecedores/${id}`
  const groups: SideGroup[] = [
    { label: 'Cadastro', items: [{ to: base, label: 'Dados e contrato', icon: UserCheck }] },
    { label: 'Documentos', items: [{ to: `${base}/documentos`, label: 'Documentos da empresa', icon: FolderOpen }, { to: `${base}/funcionarios`, label: 'Funcionários alocados', icon: Users }] },
    { label: 'Controle', items: [{ to: `${base}/pendencias`, label: 'Documentos exigidos', icon: ClipboardList, dot: s.pendencias > 0 }, { to: `${base}/riscos`, label: 'Riscos de processo trabalhista', icon: ShieldAlert, dot: s.riscos_altos > 0 }] },
  ]
  const pct = s.total ? (100 * s.ok) / s.total : 0
  return (
    <SectionLayout back={{ to: '/app/fornecedores', label: 'Voltar para fornecedores' }} groups={groups}
      header={
        <div className="glass-panel flex flex-wrap items-center gap-4 p-4">
          <Avatar nome={nomeCurto(s)} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-3xl font-bold text-brand-darker">{nomeCurto(s)}</h1>
            <p className="text-sm text-muted-foreground">CNPJ {cnpjMask(s.cnpj)} · {TIPOS[s.tipo]} · {s.funcionarios} funcionário(s) alocado(s)</p>
          </div>
          {s.status === 'INATIVO' ? <StatusPill status="INATIVO" /> : <ExposicaoBadge v={s.exposicao} />}
          {s.pre_cadastro && <span className="rounded-full bg-warning-bg px-2 py-1 text-xs font-semibold text-warning">Pré-cadastrado pelo lote</span>}
          <div className="text-center"><ComplianceRing pct={pct} /><p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Conformidade</p></div>
        </div>
      } />
  )
}

export function SupplierDados() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { can } = useAuth()
  const [edit, setEdit] = useState(false)
  const s = useGet<any>(`/suppliers/${id}`).data
  if (!s) return null
  const rows: [string, any][] = [['Razão social', s.razao_social], ['Nome fantasia', s.nome_fantasia], ['CNPJ', cnpjMask(s.cnpj)], ['Tipo', TIPOS[s.tipo]], ['Criticidade', ({ BAIXA: 'Baixa', MEDIA: 'Média', ALTA: 'Alta' } as Record<string, string>)[s.criticidade]],
    ['Objeto do contrato', s.objeto], ['Início do contrato', fmtDate(s.contrato_inicio)], ['Fim do contrato', fmtDate(s.contrato_fim)], ['Responsável', s.responsavel_nome], ['E-mail do responsável', s.responsavel_email]]
  return (
    <div className="space-y-4">
      {s.pre_cadastro && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/50 bg-warning-bg/50 p-3 text-sm"><span><b className="text-warning">Pré-cadastro gerado pelo CNPJ lido nos documentos.</b> Informe o tipo, a criticidade e as datas do contrato para o sistema cobrar os documentos certos e avisar quando o contrato vencer.</span>
        {can('funcionarios:gerir') && <Button variant="primary" onClick={() => setEdit(true)}><Pencil className="h-4 w-4" />Completar cadastro</Button>}</div>}
      <Card title="Dados e contrato" action={!s.pre_cadastro && can('funcionarios:gerir') ? <Button size="sm" onClick={() => setEdit(true)}><Pencil className="h-4 w-4" />Editar</Button> : undefined}>
        <dl className="grid gap-3 sm:grid-cols-2">{rows.map(([k, v]) => <div key={k}><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{k}</dt><dd className="text-sm">{v || '—'}</dd></div>)}</dl>
      </Card>
      <Card title="Por que a contratante exige estes documentos">
        <p className="text-sm text-muted-foreground">Se a terceirizada não pagar salários, FGTS ou verbas rescisórias, o trabalhador pode acionar também a contratante, que responde de forma subsidiária (TST Súmula 331, IV e VI; Lei 6.019/74, art. 5º-A, §5º). As certidões, as guias mensais e o contrato comprovam que a contratante fiscalizou. Os indicadores sinalizam onde a prova está faltando. São sinais de triagem, não parecer jurídico.</p>
      </Card>
      <SupplierForm key={String(edit)} open={edit} edit={s} onClose={() => setEdit(false)} onDone={() => { setEdit(false); for (const k of [`/suppliers/${id}`, '/suppliers', `/suppliers/${id}/compliance`, '/risks', '/metrics/overview']) qc.invalidateQueries({ queryKey: [k] }) }} />
    </div>
  )
}

export function SupplierDocs() {
  const { id } = useParams()
  const docs = useGet<any[]>(`/suppliers/${id}/documents`)
  const nav = useNavigate()
  if (docs.isLoading) return <SkeletonRows />
  if (docs.error) return <ErrorState error={docs.error} retry={docs.refetch} />
  const list = docs.data ?? []
  if (!list.length) return <EmptyState icon={<FolderOpen className="h-5 w-5" />} title="Nenhum documento da empresa" text="Envie um lote com certidões (CRF, CNDT, CND), guias de FGTS, contrato, apólice de seguro, autuações, processos ou relatórios de auditoria. O CNPJ lido liga tudo a este fornecedor." />
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {list.map((d) => (
        <button key={d.id} onClick={() => nav(`/app/documentos/${d.id}`)} className="glass-panel p-4 text-left transition hover:shadow-lg">
          <div className="flex items-start justify-between gap-2"><span className="flex items-center gap-2 font-semibold text-brand-darker"><FileText className="h-4 w-4 text-brand-default" />{d.tipo_nome}</span><StatusPill status={d.status} /></div>
          <p className="mt-1 text-sm text-muted-foreground">{d.competencia ? `Competência ${competenciaLabel(d.competencia)}` : fmtDate(d.data_documento)}{d.paginas?.length ? ` · pág. ${d.paginas.join(', ')}` : ' · sem imagem'}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {d.origem === 'MANUAL' && <span className="rounded-full bg-brand-lighter px-2 py-0.5 text-xs font-semibold text-brand-darker">Lançado manualmente</span>}
            {d.nao_conformidades?.map((n: any) => <span key={n.codigo} className="rounded-full bg-warning-bg px-2 py-0.5 text-xs font-semibold text-warning">{n.codigo.replaceAll('_', ' ').toLowerCase()}</span>)}
            {d.alertas?.filter((a: any) => a.severidade === 'erro').map((a: any) => <span key={a.codigo} className="rounded-full bg-danger-bg px-2 py-0.5 text-xs font-semibold text-danger">{a.mensagem}</span>)}
          </div>
        </button>
      ))}
    </div>
  )
}

export function SupplierFuncionarios() {
  const { id } = useParams()
  const nav = useNavigate()
  const r = useGet<{ items: any[] }>('/employees', { supplier: id, limit: 100 })
  if (r.error) return <ErrorState error={r.error} retry={r.refetch} />
  return (
    <Card title="Funcionários alocados por este fornecedor">
      <DataTable rows={r.data?.items} loading={r.isLoading} onRow={(e) => nav(`/app/funcionarios/${e.id}`)}
        empty={<EmptyState icon={<Users className="h-5 w-5" />} title="Nenhum funcionário" text="Os funcionários aparecem aqui quando um documento deles traz o CNPJ deste fornecedor." />}
        cols={[{ key: 'nome', header: 'Nome', render: (e) => <span className="flex items-center gap-2"><Avatar nome={e.nome} size="sm" /><b className="text-brand-darker">{e.nome}</b>{e.pre_cadastro && <span className="rounded bg-warning-bg px-1.5 py-0.5 text-[10px] font-semibold text-warning">Pré-cadastro</span>}</span> },
          { key: 'cargo', header: 'Cargo', render: (e) => e.cargo ?? '—' }, { key: 'status', header: 'Status', render: (e) => <StatusPill status={e.status} /> },
          { key: 'riscos', header: 'Riscos', render: (e) => e.riscos ? <span className={e.riscos_altos ? 'font-semibold text-danger' : 'text-warning'}>{e.riscos}</span> : '—' }]} />
    </Card>
  )
}

export function SupplierPendencias() {
  const { id } = useParams()
  const r = useGet<any[]>(`/suppliers/${id}/compliance`)
  if (r.isLoading) return <SkeletonRows />
  if (r.error) return <ErrorState error={r.error} retry={r.refetch} />
  const items = r.data ?? []
  return (
    <Card title="Documentos exigidos da empresa">
      <p className="mb-3 text-sm text-muted-foreground">As exigências vêm de <Link to="/app/configuracoes/obrigatorios" className="font-medium text-brand underline">Documentos obrigatórios</Link> (escopo empresa). A terceirizada é cobrada por certidões, guias mensais e contrato; o fornecedor sem empregados alocados, só pelos documentos não mensais.</p>
      <DataTable rows={items} empty={<EmptyState icon={<ShieldCheck className="h-5 w-5" />} title="Nenhuma exigência para este fornecedor" text="Configure os documentos exigidos da empresa para que o sistema passe a cobrá-los." />}
        cols={[{ key: 'tipo_nome', header: 'Documento' }, { key: 'referencia', header: 'Referência', render: (x) => (/^\d{4}-\d{2}$/.test(x.referencia) ? competenciaLabel(x.referencia) : x.referencia.toLowerCase()) },
          { key: 'vence_em', header: 'Vence em', render: (x) => fmtDate(x.vence_em) }, { key: 'status', header: 'Status', render: (x) => <StatusPill status={x.status} /> }]} />
    </Card>
  )
}

type Risco = { id: string; codigo: string; titulo: string; descricao: string; base_legal: string; severidade: 'ALTO' | 'MEDIO' | 'BAIXO'; categoria: string; document_id?: string; employee_id?: string; funcionario?: string; referencia?: string }

export function SupplierRiscos() {
  const { id } = useParams()
  const sup = useGet<any>(`/suppliers/${id}`).data
  const r = useGet<{ resumo: { alto: number; medio: number; baixo: number }; items: Risco[] }>('/risks', { supplier: id })
  if (r.isLoading) return <SkeletonRows />
  if (r.error) return <ErrorState error={r.error} retry={r.refetch} />
  const items = r.data?.items ?? []
  return (
    <Card title="Indicadores de que este fornecedor pode gerar processo trabalhista para a contratante" action={sup && <ExposicaoBadge v={sup.exposicao} />}>
      <p className="mb-3 text-sm text-muted-foreground">Cada indicador mostra o que foi encontrado nos documentos, a base legal e o documento de origem. São sinais de triagem: não concluem que houve infração nem substituem a análise do jurídico.</p>
      {!items.length ? <EmptyState icon={<ShieldCheck className="h-5 w-5" />} title="Nenhum indicador em aberto" text="Os documentos deste fornecedor não apresentam sinais de risco até agora." /> :
        <ul className="space-y-3">{items.map((x) => (
          <li key={x.id} className={`rounded-xl border p-3 ${x.severidade === 'ALTO' ? 'border-danger/50 bg-danger-bg/30' : 'border-warning/50 bg-warning-bg/30'}`}>
            <p className="flex flex-wrap items-center gap-2 font-semibold text-brand-darker"><AlertTriangle className={x.severidade === 'ALTO' ? 'h-4 w-4 text-danger' : 'h-4 w-4 text-warning'} />{x.titulo}<span className="rounded bg-muted px-2 py-0.5 text-xs">{x.severidade}</span></p>
            <p className="mt-1 text-sm">{x.descricao}</p>
            <p className="mt-1 text-xs text-muted-foreground">{CATEGORIAS_RISCO[x.categoria] ?? x.categoria} · {x.base_legal}{x.referencia && !/^\d{4}-\d{2}-\d{2}$/.test(x.referencia) ? ` · ${x.referencia}` : ''}</p>
            <div className="mt-1 flex gap-3 text-sm">{x.employee_id && <Link to={`/app/funcionarios/${x.employee_id}`} className="font-medium text-brand underline">{x.funcionario ?? 'Funcionário'}</Link>}{x.document_id && <Link to={`/app/documentos/${x.document_id}`} className="font-medium text-brand underline">Ver documento</Link>}</div>
          </li>))}</ul>}
    </Card>
  )
}
