import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { AlertTriangle, Archive, Calendar, ClipboardList, FilePlus2, FileText, FolderOpen, History, IdCard, Pencil, ShieldAlert, ShieldCheck, Stethoscope, Upload, UserCheck, Gavel, DoorOpen, Layers } from 'lucide-react'
import { SectionLayout, type SideGroup } from '@/components/shell/SectionLayout'
import { Avatar, Button, Card, ComplianceRing, ConfidenceBar, DataTable, EmptyState, ErrorState, Field, Input, Modal, Select, SkeletonRows, StatusPill, Textarea } from '@/components/ui'
import { ManualDocModal } from './ManualDoc'
import { useGet } from '@/lib/query'
import { api, download } from '@/lib/api'
import { competenciaLabel, fmtDate, fmtDateTime, MOTIVOS } from '@/lib/format'
import { useAuth } from '@/lib/auth'

const CATS: Record<string, { label: string; cat: string; icon: any }> = {
  admissao: { label: 'Admissão', cat: 'ADMISSAO', icon: IdCard }, mensais: { label: 'Mensais', cat: 'MENSAL', icon: Calendar },
  saude: { label: 'Saúde e segurança', cat: 'SAUDE_SEGURANCA', icon: Stethoscope }, disciplinar: { label: 'Disciplinar', cat: 'DISCIPLINAR', icon: Gavel },
  desligamento: { label: 'Desligamento', cat: 'DESLIGAMENTO', icon: DoorOpen }, outros: { label: 'Outros', cat: 'OUTROS', icon: Layers },
}

export function DossieLayout() {
  const { id } = useParams()
  const emp = useGet<any>(`/employees/${id}`)
  const { can } = useAuth()
  const nav = useNavigate()
  const [manual, setManual] = useState(false)
  const e = emp.data
  if (emp.isLoading) return <SkeletonRows />
  if (emp.error || !e) return <ErrorState error={emp.error ?? new Error('Funcionário não encontrado')} />
  const pct = e.total ? (100 * e.ok) / e.total : 0
  const base = `/app/funcionarios/${id}`
  const groups: SideGroup[] = [
    { label: 'Cadastro', items: [{ to: base, label: 'Dados', icon: UserCheck }, { to: `${base}/documentos-exigidos`, label: 'Documentos exigidos', icon: ClipboardList }] },
    { label: 'Documentos', items: Object.entries(CATS).map(([k, v]) => ({ to: `${base}/documentos/${k}`, label: v.label, icon: v.icon })) },
    { label: 'Controle', items: [{ to: `${base}/pendencias`, label: 'Pendências', icon: ClipboardList, dot: e.pendencias > 0 }, { to: `${base}/riscos`, label: 'Riscos trabalhistas', icon: ShieldAlert, dot: e.riscos_altos > 0 }, { to: `${base}/linha-do-tempo`, label: 'Linha do tempo', icon: History }, { to: `${base}/revisoes`, label: 'Revisões', icon: ShieldCheck }] },
    { label: 'Exportar', items: [{ to: `${base}/exportar`, label: 'Dossiê completo', icon: Archive }] },
  ]
  return (
    <SectionLayout back={{ to: '/app/buscar', label: 'Voltar para a busca' }} groups={groups}
      action={<div className="space-y-2">
        {can('lotes:enviar') && <Button variant="primary" className="w-full" onClick={() => nav(`/app/lotes/novo?funcionario=${id}`)}><Upload className="h-4 w-4" />Enviar documento deste funcionário</Button>}
        {can('revisao:fazer') && <Button className="w-full" onClick={() => setManual(true)}><FilePlus2 className="h-4 w-4" />Lançar documento manualmente</Button>}
        <ManualDocModal employeeId={id!} open={manual} onClose={() => setManual(false)} />
      </div>}
      header={
        <div className="glass-panel flex flex-wrap items-center gap-4 p-4">
          <Avatar nome={e.nome} size="lg" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-display text-3xl font-bold text-brand-darker">{e.nome}</h1>
            <p className="text-sm text-muted-foreground">{e.cpf_mascarado} · {e.cargo ?? 'sem cargo'} · {e.unidade ?? 'sem unidade'} · matrícula {e.matricula ?? '—'}</p>
            <p className="text-sm text-muted-foreground">{e.supplier_id ? <>{e.vinculo === 'TERCEIRIZADA' ? 'Terceirizado de' : 'Trabalha para o fornecedor'} <Link to={`/app/fornecedores/${e.supplier_id}`} className="font-medium text-brand underline">{e.fornecedor}</Link></> : 'Funcionário da própria empresa'}</p>
          </div>
          <StatusPill status={e.status} />
          {e.pre_cadastro && <span className="rounded-full bg-warning-bg px-2 py-1 text-xs font-semibold text-warning">Pré-cadastrado pelo lote</span>}
          <div className="text-center"><ComplianceRing pct={pct} /><p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Conformidade</p></div>
        </div>
      } />
  )
}

export function DossieDados() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { can } = useAuth()
  const [edit, setEdit] = useState(false)
  const e = useGet<any>(`/employees/${id}`).data
  const cfg = useGet<any>('/tenant/cadastro-config').data
  if (!e) return null
  const extras: [string, any][] = (cfg?.personalizados ?? []).map((f: any) => [f.rotulo, e.extra?.[f.chave]])
  const rows: [string, any][] = [['Nome', e.nome], ['CPF', e.cpf_mascarado], ['Matrícula', e.matricula], ['Cargo', e.cargo], ['Setor', e.setor], ['Unidade', e.unidade], ['Admissão', fmtDate(e.admissao)], ['Desligamento', fmtDate(e.desligamento)], ['E-mail', e.email], ['Telefone', e.telefone], ...extras]
  return <div className="space-y-4">
    {e.pre_cadastro && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/50 bg-warning-bg/50 p-3 text-sm"><span><b className="text-warning">Pré-cadastro gerado a partir dos documentos.</b> Nome e CPF vieram da leitura automática ({e.origem === 'REVISAO' ? 'criado durante a revisão' : 'lote'}); complete admissão, cargo e setor para o sistema cobrar os documentos corretos.</span>
      {can('funcionarios:gerir') && <Button variant="primary" onClick={() => setEdit(true)}><Pencil className="h-4 w-4" />Completar cadastro</Button>}</div>}
    <Card title="Dados e cargo" action={!e.pre_cadastro && can('funcionarios:gerir') ? <Button size="sm" onClick={() => setEdit(true)}><Pencil className="h-4 w-4" />Editar</Button> : undefined}>
      <dl className="grid gap-3 sm:grid-cols-2">{rows.map(([k, v]) => <div key={k}><dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{k}</dt><dd className="text-sm">{v || '—'}</dd></div>)}</dl></Card>
    <EditEmployee open={edit} onClose={() => setEdit(false)} e={e} cfg={cfg} onDone={() => { setEdit(false); for (const k of [`/employees/${id}`, '/employees', `/employees/${id}/compliance`, '/metrics/overview', '/risks']) qc.invalidateQueries({ queryKey: [k] }) }} />
  </div>
}

function EditEmployee({ open, onClose, e, cfg, onDone }: { open: boolean; onClose: () => void; e: any; cfg: any; onDone: () => void }) {
  const cargos = useGet<any[]>(open ? '/positions' : null); const deps = useGet<any[]>(open ? '/departments' : null); const units = useGet<any[]>(open ? '/units' : null)
  const ini = () => ({ nome: e.nome ?? '', matricula: e.matricula ?? '', admissao: e.admissao?.slice(0, 10) ?? '', desligamento: e.desligamento?.slice(0, 10) ?? '', cargo_id: e.cargo_id ?? '', department_id: e.department_id ?? '', unit_id: e.unit_id ?? '', email: e.email ?? '', telefone: e.telefone ?? '' })
  const [v, setV] = useState<Record<string, string>>(ini)
  const [extra, setExtra] = useState<Record<string, string>>(e.extra ?? {})
  const [conferido, setConferido] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const set = (k: string) => (ev: { target: { value: string } }) => setV({ ...v, [k]: ev.target.value })
  const on = (k: string) => cfg?.campos?.[k]?.ativo !== false
  const save = async () => {
    setBusy(true); setErr('')
    const body: Record<string, unknown> = { nome: v.nome, matricula: v.matricula || undefined, cargo_id: v.cargo_id || undefined, department_id: v.department_id || undefined, unit_id: v.unit_id || undefined,
      admissao: v.admissao || undefined, desligamento: v.desligamento || undefined, email: v.email || undefined, telefone: v.telefone || undefined, extra }
    if (e.pre_cadastro && conferido) body.pre_cadastro = false
    if (v.desligamento && e.status !== 'DESLIGADO') body.status = 'DESLIGADO'
    try { await api(`/employees/${e.id}`, { method: 'PATCH', body }); onDone() } catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal wide open={open} onClose={onClose} eyebrow="Funcionário" title={e.pre_cadastro ? 'Completar cadastro' : 'Editar dados'} footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={busy} disabled={v.nome.trim().length < 3} onClick={save}>Salvar</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Nome *">{(id) => <Input id={id} value={v.nome} onChange={set('nome')} />}</Field>
        <Field label="CPF" hint="O CPF não é editável: ele liga os documentos ao funcionário.">{(id) => <Input id={id} value={e.cpf_mascarado} disabled />}</Field>
        {on('matricula') && <Field label="Matrícula">{(id) => <Input id={id} value={v.matricula} onChange={set('matricula')} />}</Field>}
        {on('admissao') && <Field label="Admissão">{(id) => <Input id={id} type="date" value={v.admissao} onChange={set('admissao')} />}</Field>}
        <Field label="Desligamento">{(id) => <Input id={id} type="date" value={v.desligamento} onChange={set('desligamento')} />}</Field>
        {on('setor') && <Field label="Setor">{(id) => <Select id={id} value={v.department_id} onChange={set('department_id')}><option value="">—</option>{deps.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Select>}</Field>}
        {on('cargo') && <Field label="Cargo">{(id) => <Select id={id} value={v.cargo_id} onChange={set('cargo_id')}><option value="">—</option>{cargos.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Select>}</Field>}
        {on('unidade') && <Field label="Unidade">{(id) => <Select id={id} value={v.unit_id} onChange={set('unit_id')}><option value="">—</option>{units.data?.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Select>}</Field>}
        {on('email') && <Field label="E-mail">{(id) => <Input id={id} value={v.email} onChange={set('email')} />}</Field>}
        {on('telefone') && <Field label="Telefone">{(id) => <Input id={id} value={v.telefone} onChange={set('telefone')} />}</Field>}
        {(cfg?.personalizados ?? []).map((f: any) => (
          <Field key={f.chave} label={f.rotulo + (f.obrigatorio ? ' *' : '')}>{(id) => f.tipo === 'lista'
            ? <Select id={id} value={extra[f.chave] ?? ''} onChange={(ev) => setExtra({ ...extra, [f.chave]: ev.target.value })}><option value="">—</option>{f.opcoes.map((o: string) => <option key={o}>{o}</option>)}</Select>
            : <Input id={id} type={f.tipo === 'data' ? 'date' : f.tipo === 'numero' ? 'number' : 'text'} value={extra[f.chave] ?? ''} onChange={(ev) => setExtra({ ...extra, [f.chave]: ev.target.value })} />}</Field>
        ))}
      </div>
      {e.pre_cadastro && <label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={conferido} onChange={(ev) => setConferido(ev.target.checked)} />Cadastro conferido: remover a marca de pré-cadastro</label>}
      {err && <p role="alert" className="mt-3 rounded-lg bg-danger-bg p-2 text-sm text-danger">{err}</p>}
    </Modal>
  )
}

type Risco = { id: string; codigo: string; titulo: string; descricao: string; base_legal: string; severidade: 'ALTO' | 'MEDIO' | 'BAIXO'; categoria: string; document_id?: string; referencia?: string }

export function DossieRiscos() {
  const { id } = useParams()
  const r = useGet<{ resumo: { alto: number; medio: number; baixo: number }; items: Risco[] }>('/risks', { employee: id })
  if (r.isLoading) return <SkeletonRows />
  if (r.error) return <ErrorState error={r.error} retry={r.refetch} />
  const items = r.data?.items ?? []
  return (
    <Card title="Indicadores de risco trabalhista deste funcionário">
      <p className="mb-3 text-sm text-muted-foreground">Sinais encontrados nos documentos, para conferência. Indicadores de triagem: não substituem a análise do jurídico.</p>
      {!items.length ? <EmptyState icon={<ShieldCheck className="h-5 w-5" />} title="Nenhum indicador em aberto" text="Os documentos deste funcionário não apresentam sinais de divergência até agora." /> :
        <ul className="space-y-3">{items.map((x) => (
          <li key={x.id} className={`rounded-xl border p-3 ${x.severidade === 'ALTO' ? 'border-danger/50 bg-danger-bg/30' : 'border-warning/50 bg-warning-bg/30'}`}>
            <p className="flex items-center gap-2 font-semibold text-brand-darker"><AlertTriangle className={x.severidade === 'ALTO' ? 'h-4 w-4 text-danger' : 'h-4 w-4 text-warning'} />{x.titulo}<span className="rounded bg-muted px-2 py-0.5 text-xs">{x.severidade}</span></p>
            <p className="mt-1 text-sm">{x.descricao}</p><p className="mt-1 text-xs text-muted-foreground">{x.base_legal}{x.referencia ? ` · ${x.referencia}` : ''}</p>
            {x.document_id && <Link to={`/app/documentos/${x.document_id}`} className="mt-1 inline-block text-sm font-medium text-brand underline">Ver documento</Link>}
          </li>))}</ul>}
    </Card>
  )
}

export function DossieDocs() {
  const { id, secao = 'admissao' } = useParams()
  const meta = CATS[secao] ?? CATS.admissao
  const docs = useGet<any[]>(`/employees/${id}/documents`, { categoria: meta.cat })
  const nav = useNavigate()
  const [comp, setComp] = useState<string | null>(null)
  if (docs.isLoading) return <SkeletonRows />
  if (docs.error) return <ErrorState error={docs.error} retry={docs.refetch} />
  const list = docs.data ?? []
  const comps = [...new Set(list.map((d) => d.competencia).filter(Boolean))].sort().reverse()
  const shown = secao === 'mensais' && comp ? list.filter((d) => d.competencia === comp) : list
  return (
    <div className="space-y-4">
      {secao === 'mensais' && !!comps.length && (
        <Card title="Competências" ><div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {comps.map((c) => <button key={c} onClick={() => setComp(comp === c ? null : c)} className={`rounded-lg border px-2 py-2 text-sm font-medium ${comp === c ? 'border-brand-default bg-brand-lighter text-brand-darker' : 'border-border bg-surface/70 text-muted-foreground hover:border-brand-light'}`}>{competenciaLabel(c as string)}</button>)}
        </div></Card>
      )}
      {!shown.length ? <EmptyState icon={<FolderOpen className="h-5 w-5" />} title={`Nenhum documento em “${meta.label}”`} text="Envie um lote com os documentos deste funcionário e eles aparecem aqui, já vinculados pelo CPF." /> : (
        <div className="grid gap-3 md:grid-cols-2">
          {shown.map((d) => (
            <button key={d.id} onClick={() => nav(`/app/documentos/${d.id}`)} className="glass-panel p-4 text-left transition hover:shadow-lg">
              <div className="flex items-start justify-between gap-2"><span className="flex items-center gap-2 font-semibold text-brand-darker"><FileText className="h-4 w-4 text-brand-default" />{d.tipo_nome}</span><StatusPill status={d.status} /></div>
              <p className="mt-1 text-sm text-muted-foreground">{d.competencia ? `Competência ${competenciaLabel(d.competencia)}` : fmtDate(d.data_documento)}{d.paginas?.length ? ` · pág. ${d.paginas.join(', ')}` : ' · sem imagem'}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2"><ConfidenceBar value={Number(d.confianca)} />
                {d.mascarado && <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">Dado de saúde restrito</span>}
                {d.origem === 'MANUAL' && <span className="rounded-full bg-brand-lighter px-2 py-0.5 text-xs font-semibold text-brand-darker">Lançado manualmente</span>}
                {d.nao_conformidades?.map((n: any) => <span key={n.codigo} className="rounded-full bg-warning-bg px-2 py-0.5 text-xs font-semibold text-warning">{n.codigo.replaceAll('_', ' ').toLowerCase()}</span>)}
                {d.alertas?.filter((a: any) => a.severidade === 'erro').map((a: any) => <span key={a.codigo} className="rounded-full bg-danger-bg px-2 py-0.5 text-xs font-semibold text-danger">{a.mensagem}</span>)}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function DossiePendencias() {
  const { id } = useParams()
  const r = useGet<any[]>(`/employees/${id}/compliance`)
  if (r.isLoading) return <SkeletonRows />
  const items = (r.data ?? []).filter((x) => x.status !== 'OK')
  return (
    <Card title="Pendências do funcionário">
      <DataTable rows={items} loading={r.isLoading} empty={<EmptyState title="Tudo em dia" text="Nenhum item pendente, vencido ou a vencer." />}
        cols={[{ key: 'tipo_nome', header: 'Documento' }, { key: 'referencia', header: 'Referência', render: (x) => (/^\d{4}-\d{2}$/.test(x.referencia) ? competenciaLabel(x.referencia) : x.referencia.toLowerCase()) },
          { key: 'vence_em', header: 'Vence em', render: (x) => fmtDate(x.vence_em) }, { key: 'status', header: 'Status', render: (x) => <StatusPill status={x.status} /> }]} />
    </Card>
  )
}

export function DossieTimeline() {
  const { id } = useParams()
  const r = useGet<any[]>(`/employees/${id}/timeline`)
  return (
    <Card title="Linha do tempo">
      {r.isLoading ? <SkeletonRows /> : !r.data?.length ? <EmptyState title="Sem eventos ainda" /> : (
        <ol className="relative ml-3 space-y-4 border-l-2 border-brand-lighter pl-5">
          {r.data.map((e, i) => (
            <li key={i}><span className="absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full bg-brand-default" aria-hidden />
              <p className="text-sm font-semibold text-brand-darker">{e.titulo} <span className="font-normal text-muted-foreground">· {e.detalhe}</span></p><p className="text-xs text-muted-foreground">{fmtDateTime(e.quando)}</p></li>
          ))}
        </ol>
      )}
    </Card>
  )
}

export function DossieRevisoes() {
  const { id } = useParams()
  const r = useGet<any[]>(`/employees/${id}/reviews`)
  return <Card title="Revisões"><DataTable rows={r.data} loading={r.isLoading} empty={<EmptyState title="Nenhuma revisão registrada" />}
    cols={[{ key: 'criado_em', header: 'Quando', render: (x) => fmtDateTime(x.criado_em) }, { key: 'acao', header: 'Ação' }, { key: 'document_type', header: 'Documento' }, { key: 'revisor', header: 'Revisor' }, { key: 'duracao_ms', header: 'Duração', render: (x) => (x.duracao_ms ? `${Math.round(x.duracao_ms / 1000)}s` : '—') }]} /></Card>
}

export function DossieExport() {
  const { id } = useParams()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  return (
    <Card title="Dossiê completo">
      <p className="mb-4 text-sm text-muted-foreground">Gera um ZIP com todos os documentos aprovados em PDF pesquisável e um índice. Por segurança, a exportação pede um novo código por e-mail e fica registrada na auditoria.</p>
      <Button variant="primary" loading={busy} onClick={async () => { setBusy(true); setErr(''); try { await download(`/exports/dossie/${id}`, undefined, 'POST') } catch (e) { setErr((e as Error).message) } finally { setBusy(false) } }}><Archive className="h-4 w-4" />Exportar dossiê (ZIP)</Button>
      {err && <p role="alert" className="mt-3 text-sm text-danger">{err}</p>}
    </Card>
  )
}

export function MotivoChips({ motivos }: { motivos: string[] }) {
  return <>{motivos?.map((m) => <span key={m} className="rounded-full bg-warning-bg px-2 py-0.5 text-xs font-semibold text-warning">{MOTIVOS[m] ?? m}</span>)}</>
}
export const _unused = Link

const ORIGEM: Record<string, string> = { TODOS: 'regra geral', SETOR: 'regra do setor', CARGO: 'regra do cargo', FUNCIONARIO: 'exceção deste funcionário' }

/** O que é exigido deste funcionário. Dispense ou exija um documento só para ele (fica na auditoria). */
export function DossieExigidos() {
  const { id } = useParams()
  const qc = useQueryClient()
  const { can } = useAuth()
  const r = useGet<any[]>(`/employees/${id}/requirements`)
  const [alvo, setAlvo] = useState<any>(null)
  const [just, setJust] = useState('')
  const [err, setErr] = useState('')
  const refresh = () => { qc.invalidateQueries({ queryKey: [`/employees/${id}/requirements`] }); qc.invalidateQueries({ queryKey: [`/employees/${id}/compliance`] }); qc.invalidateQueries({ queryKey: [`/employees/${id}`] }); qc.invalidateQueries({ queryKey: ['/metrics/overview'] }) }
  const put = async (cod: string, body: any) => { setErr(''); try { await api(`/employees/${id}/requirements/${cod}`, { method: 'PUT', body }); refresh(); setAlvo(null); setJust('') } catch (e) { setErr((e as Error).message) } }
  if (r.isLoading) return <SkeletonRows />
  const cats = [...new Set((r.data ?? []).map((x) => x.categoria))]
  const exigidos = (r.data ?? []).filter((x) => x.obrigatorio).length
  return (
    <div className="space-y-4">
      <Card title="Documentos exigidos"><p className="text-sm text-muted-foreground">{exigidos ? `${exigidos} documento(s) exigido(s) deste funcionário, conforme setor, cargo e regra geral.` : 'Nenhum documento é exigido deste funcionário: ele não gera pendências.'} Se algum não se aplica a ele, dispense aqui: o sistema para de cobrar só para esta pessoa.</p></Card>
      {cats.map((cat) => (
        <Card key={cat as string} title={CAT_LABEL[cat as string] ?? (cat as string)}>
          <ul className="divide-y divide-border/60">
            {(r.data ?? []).filter((x) => x.categoria === cat).map((x) => (
              <li key={x.codigo} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <span className="min-w-52 flex-1"><b className={x.obrigatorio ? 'text-brand-darker' : 'text-muted-foreground'}>{x.nome}</b>
                  <span className="ml-2 text-xs text-muted-foreground">{x.origem ? (x.obrigatorio ? `exigido · ${ORIGEM[x.origem]}` : `dispensado · ${ORIGEM[x.origem]}`) : 'não exigido'}</span></span>
                <StatusPill status={x.obrigatorio ? 'PENDENTE' : 'DISPENSADO'} label={x.obrigatorio ? 'Exigido' : 'Não exigido'} />
                {can('funcionarios:gerir') && (<span className="flex gap-1">
                  {x.obrigatorio ? <Button size="sm" onClick={() => { setAlvo(x); setJust(''); setErr('') }}>Dispensar deste funcionário</Button> : <Button size="sm" onClick={() => put(x.codigo, { obrigatorio: true })}>Exigir deste funcionário</Button>}
                  {x.excecao && <Button size="sm" onClick={() => put(x.codigo, { obrigatorio: null })}>Voltar ao padrão</Button>}
                </span>)}
              </li>
            ))}
          </ul>
        </Card>
      ))}
      <Modal open={!!alvo} onClose={() => setAlvo(null)} eyebrow="Exceção" title={alvo ? `Dispensar: ${alvo.nome}` : ''} footer={<><Button onClick={() => setAlvo(null)}>Cancelar</Button><Button variant="primary" disabled={just.trim().length < 5} onClick={() => put(alvo.codigo, { obrigatorio: false, justificativa: just })}>Dispensar</Button></>}>
        <p className="text-sm text-muted-foreground">O sistema deixa de cobrar este documento só deste funcionário. A justificativa fica registrada na auditoria.</p>
        <Field label="Justificativa (obrigatória)" error={err}>{(i) => <Textarea id={i} value={just} onChange={(e) => setJust(e.target.value)} placeholder="Ex.: atua só em atividade administrativa, não usa EPI" />}</Field>
      </Modal>
    </div>
  )
}
const CAT_LABEL: Record<string, string> = { ADMISSAO: 'Admissão', MENSAL: 'Mensais', SAUDE_SEGURANCA: 'Saúde e segurança', DISCIPLINAR: 'Disciplinar', DESLIGAMENTO: 'Desligamento', OUTROS: 'Outros' }
