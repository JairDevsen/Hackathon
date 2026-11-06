import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Download, FileSpreadsheet, LogOut, Mail, Plus, Users } from 'lucide-react'
import { Avatar, Button, Card, ComplianceRing, DataTable, EmptyState, ErrorState, Field, Input, Modal, SectionHeading, Segmented, Select, StatusPill } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api, download } from '@/lib/api'
import { competenciaLabel, cpfMask, cpfValido, fmtDate, fmtDateTime } from '@/lib/format'

/** Quem é o empregador: a própria empresa, uma terceirizada ou um fornecedor (com o nome da empresa). */
export function VinculoChip({ e }: { e: { vinculo?: string; fornecedor?: string } }) {
  if (!e.vinculo || e.vinculo === 'PROPRIA') return <span className="rounded bg-brand-lighter px-1.5 py-0.5 text-[11px] font-semibold text-brand-darker">Própria empresa</span>
  return <span className="inline-flex flex-col leading-tight"><span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{e.vinculo === 'TERCEIRIZADA' ? 'Terceirizada' : 'Fornecedor'}</span><span className="max-w-[12rem] truncate text-xs">{e.fornecedor}</span></span>
}

export function EmployeesPage() {
  const nav = useNavigate()
  const [sp, setSp] = useSearchParams()
  const qc = useQueryClient()
  const [f, setF] = useState({ unit: '', cargo: '', setor: '', status: '', conformidade: '', vinculo: sp.get('vinculo') ?? '', supplier: '' })
  const [newOpen, setNewOpen] = useState(false)
  const [impOpen, setImpOpen] = useState(false)
  const sups = useGet<any[]>('/suppliers'); const units = useGet<any[]>('/units'); const cargos = useGet<any[]>('/positions'); const deps = useGet<any[]>('/departments'); const cfg = useGet<any>('/tenant/cadastro-config')
  const r = useGet<{ items: any[] }>('/employees', { ...f, pre: sp.get('pre') || '', limit: 100 }, { keep: true })
  return (
    <div>
      <SectionHeading eyebrow="Funcionários" title="Funcionários" action={<div className="flex gap-2"><Button onClick={() => setImpOpen(true)}><FileSpreadsheet className="h-4 w-4" />Importar planilha</Button><Button variant="primary" onClick={() => setNewOpen(true)}><Plus className="h-4 w-4" />Novo funcionário</Button></div>}>Consulte os pré-cadastros gerados pelos lotes e confira os documentos de cada pessoa.</SectionHeading>
      <div className="mb-4 flex flex-wrap gap-3">
        <Select aria-label="Origem do cadastro" className="!w-48" value={sp.get('pre') || ''} onChange={(e) => setSp(e.target.value ? { pre: e.target.value } : {})}><option value="">Todos os cadastros</option><option value="1">Pré-cadastrados pelo lote</option></Select>
        <Select aria-label="Vínculo" className="!w-52" value={f.vinculo} onChange={(e) => setF({ ...f, vinculo: e.target.value, supplier: '' })}><option value="">Todos os vínculos</option><option value="PROPRIA">Própria empresa</option><option value="TERCEIRIZADA">Terceirizadas</option><option value="FORNECEDOR">Fornecedores</option></Select>
        {!!sups.data?.length && <Select aria-label="Empresa" className="!w-56" value={f.supplier} onChange={(e) => setF({ ...f, supplier: e.target.value, vinculo: '' })}><option value="">Todas as empresas</option>{sups.data.map((s) => <option key={s.id} value={s.id}>{s.nome_fantasia || s.razao_social}</option>)}</Select>}
        <Select aria-label="Unidade" className="!w-48" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}><option value="">Todas as unidades</option>{units.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</Select>
        <Select aria-label="Cargo" className="!w-52" value={f.cargo} onChange={(e) => setF({ ...f, cargo: e.target.value })}><option value="">Todos os cargos</option>{cargos.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</Select>
        {!!deps.data?.length && <Select aria-label="Setor" className="!w-44" value={f.setor} onChange={(e) => setF({ ...f, setor: e.target.value })}><option value="">Todos os setores</option>{deps.data.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</Select>}
        <Select aria-label="Status" className="!w-40" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">Todos os status</option><option value="ATIVO">Ativo</option><option value="AFASTADO">Afastado</option><option value="DESLIGADO">Desligado</option></Select>
        <Select aria-label="Conformidade" className="!w-44" value={f.conformidade} onChange={(e) => setF({ ...f, conformidade: e.target.value })}><option value="">Toda conformidade</option><option value="pendente">Com pendência</option><option value="ok">Em dia</option></Select>
      </div>
      {r.error ? <ErrorState error={r.error} retry={r.refetch} /> : <DataTable rows={r.data?.items} loading={r.isLoading} onRow={(e) => nav(`/app/funcionarios/${e.id}`)} empty={<EmptyState icon={<Users className="h-5 w-5" />} title="Nenhum funcionário" text="Envie um lote com documentos que tragam nome e CPF válido para gerar pré-cadastros." />}
        cols={[{ key: 'nome', header: 'Nome', render: (e) => <span className="flex items-center gap-2"><Avatar nome={e.nome} size="sm" /><b className="text-brand-darker">{e.nome}</b>{e.pre_cadastro && <span className="rounded bg-warning-bg px-1.5 py-0.5 text-[10px] font-semibold text-warning">Pré-cadastro</span>}</span> }, { key: 'cpf_mascarado', header: 'CPF' }, { key: 'vinculo', header: 'Vínculo', render: (e) => <VinculoChip e={e} /> }, { key: 'cargo', header: 'Cargo' }, { key: 'setor', header: 'Setor' }, { key: 'unidade', header: 'Unidade' },
          { key: 'status', header: 'Status', render: (e) => <StatusPill status={e.status} /> }, { key: 'conf', header: 'Conformidade', render: (e) => <span className="flex items-center gap-2"><ComplianceRing pct={e.total ? (100 * e.ok) / e.total : 0} size={34} label={false} />{e.pendencias ? `${e.pendencias} pend.` : 'Em dia'}</span> }]} />}
      <NewEmployee open={newOpen} onClose={() => setNewOpen(false)} cargos={cargos.data ?? []} units={units.data ?? []} deps={deps.data ?? []} cfg={cfg.data} onDone={() => { setNewOpen(false); qc.invalidateQueries({ queryKey: ['/employees'] }) }} />
      <ImportModal open={impOpen} onClose={() => setImpOpen(false)} onDone={() => qc.invalidateQueries({ queryKey: ['/employees'] })} />
    </div>
  )
}

const empSchema = z.object({ nome: z.string().min(3, 'Informe o nome'), cpf: z.string().refine(cpfValido, 'CPF inválido: confira os dígitos'), matricula: z.string().optional(), cargo_id: z.string().optional(), department_id: z.string().optional(), unit_id: z.string().optional(), admissao: z.string().optional(), email: z.string().email('E-mail inválido').optional().or(z.literal('')), telefone: z.string().optional() })

/** Cadastro de funcionário: mostra só os campos que a empresa ativou e exige os que ela marcou como obrigatórios. */
function NewEmployee({ open, onClose, cargos, units, deps, cfg, onDone }: any) {
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting }, setError, reset } = useForm({ resolver: zodResolver(empSchema) })
  const [extra, setExtra] = useState<Record<string, string>>({})
  const on = (k: string) => cfg?.campos?.[k]?.ativo !== false
  const req = (k: string) => on(k) && !!cfg?.campos?.[k]?.obrigatorio
  const lbl = (t: string, k: string) => t + (req(k) ? ' *' : '')
  const submit = handleSubmit(async (v) => {
    const faltam: string[] = []
    const vals: Record<string, any> = { matricula: v.matricula, admissao: v.admissao, cargo: v.cargo_id, setor: v.department_id, unidade: v.unit_id, email: v.email, telefone: v.telefone }
    const nomes: Record<string, string> = { matricula: 'Matrícula', admissao: 'Data de admissão', cargo: 'Cargo', setor: 'Setor', unidade: 'Unidade', email: 'E-mail', telefone: 'Telefone' }
    for (const k of Object.keys(nomes)) if (req(k) && !String(vals[k] ?? '').trim()) faltam.push(nomes[k])
    for (const f of cfg?.personalizados ?? []) if (f.obrigatorio && !String(extra[f.chave] ?? '').trim()) faltam.push(f.rotulo)
    if (faltam.length) return setError('root', { message: 'Preencha: ' + faltam.join(', ') })
    try {
      await api('/employees', { method: 'POST', body: { ...v, cargo_id: v.cargo_id || null, department_id: v.department_id || null, unit_id: v.unit_id || null, admissao: v.admissao || null, extra } })
      reset(); setExtra({}); onDone()
    } catch (e) { setError('root', { message: (e as Error).message }) }
  })
  return (
    <Modal wide open={open} onClose={onClose} eyebrow="Funcionários" title="Novo funcionário" footer={<><Button onClick={onClose}>Cancelar</Button><Button variant="primary" loading={isSubmitting} onClick={submit}>Cadastrar</Button></>}>
      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" noValidate>
        <Field label="Nome *" error={errors.nome?.message as string}>{(id, bad) => <Input id={id} aria-invalid={bad} {...register('nome')} />}</Field>
        <Field label="CPF *" error={errors.cpf?.message as string}>{(id, bad) => <Input id={id} aria-invalid={bad} inputMode="numeric" {...register('cpf', { onChange: (e) => setValue('cpf', cpfMask(e.target.value)) })} />}</Field>
        {on('matricula') && <Field label={lbl('Matrícula', 'matricula')}>{(id) => <Input id={id} {...register('matricula')} />}</Field>}
        {on('admissao') && <Field label={lbl('Admissão', 'admissao')}>{(id) => <Input id={id} type="date" {...register('admissao')} />}</Field>}
        {on('setor') && <Field label={lbl('Setor', 'setor')}>{(id) => <Select id={id} {...register('department_id')}><option value="">—</option>{deps.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Select>}</Field>}
        {on('cargo') && <Field label={lbl('Cargo', 'cargo')}>{(id) => <Select id={id} {...register('cargo_id')}><option value="">—</option>{cargos.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Select>}</Field>}
        {on('unidade') && <Field label={lbl('Unidade', 'unidade')}>{(id) => <Select id={id} {...register('unit_id')}><option value="">—</option>{units.map((c: any) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Select>}</Field>}
        {on('email') && <Field label={lbl('E-mail', 'email')} error={errors.email?.message as string}>{(id, bad) => <Input id={id} aria-invalid={bad} {...register('email')} />}</Field>}
        {on('telefone') && <Field label={lbl('Telefone', 'telefone')}>{(id) => <Input id={id} {...register('telefone')} />}</Field>}
        {(cfg?.personalizados ?? []).map((f: any) => (
          <Field key={f.chave} label={f.rotulo + (f.obrigatorio ? ' *' : '')}>{(id) => f.tipo === 'lista'
            ? <Select id={id} value={extra[f.chave] ?? ''} onChange={(e) => setExtra({ ...extra, [f.chave]: e.target.value })}><option value="">—</option>{f.opcoes.map((o: string) => <option key={o}>{o}</option>)}</Select>
            : <Input id={id} type={f.tipo === 'data' ? 'date' : f.tipo === 'numero' ? 'number' : 'text'} value={extra[f.chave] ?? ''} onChange={(e) => setExtra({ ...extra, [f.chave]: e.target.value })} />}</Field>
        ))}
        {errors.root && <p role="alert" className="col-span-full text-sm text-danger">{errors.root.message}</p>}
      </form>
    </Modal>
  )
}

function ImportModal({ open, onClose, onDone }: any) {
  const [file, setFile] = useState<File | null>(null)
  const [res, setRes] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const run = async (dry: boolean) => {
    if (!file) return
    setBusy(true); setErr('')
    const fd = new FormData(); fd.set('file', file); fd.set('dry_run', String(dry))
    try { const r = await api('/employees/import', { method: 'POST', body: fd }); setRes(r); if (!dry) onDone() } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal wide open={open} onClose={() => { setRes(null); setFile(null); onClose() }} eyebrow="Funcionários" title="Importar planilha" footer={<>
      <Button onClick={() => run(true)} disabled={!file} loading={busy}>Pré-validar</Button><Button variant="primary" disabled={!file || !res || res.simulacao === false} onClick={() => run(false)}>Importar {res?.validos ?? ''} válidos</Button></>}>
      <p className="text-sm text-muted-foreground">CSV (vírgula ou ponto e vírgula) ou XLSX com as colunas: <code>cpf</code>, <code>nome</code>, <code>matricula</code>, <code>cargo</code>, <code>unidade</code>, <code>admissao</code>, <code>email</code>. Os CPFs são validados antes de gravar.</p>
      <input type="file" accept=".csv,.xlsx" aria-label="Arquivo da planilha" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setRes(null) }} />
      {err && <p role="alert" className="text-sm text-danger">{err}</p>}
      {res && <div className="rounded-xl border border-border bg-surface/70 p-3 text-sm"><p><b>{res.total}</b> linhas · <b className="text-success">{res.validos}</b> válidas · <b className="text-danger">{res.erros.length}</b> com erro{res.simulacao === false && <> · <b className="text-success">{res.criados}</b> criados</>}</p>
        {!!res.erros.length && <ul className="mt-2 max-h-40 overflow-auto text-xs text-danger">{res.erros.map((e: any) => <li key={e.linha}>Linha {e.linha}: {e.erro}</li>)}</ul>}</div>}
    </Modal>
  )
}

export function PendenciasPage() {
  const nav = useNavigate()
  const [status, setStatus] = useState('PENDENTE,VENCIDO,A_VENCER')
  const [by, setBy] = useState<'funcionario' | 'tipo'>('funcionario')
  const [msg, setMsg] = useState('')
  const r = useGet<{ items: any[]; resumo: any }>('/compliance', { status, limit: 500 }, { keep: true })
  const items = r.data?.items ?? []
  const groups = Object.entries(items.reduce<Record<string, any[]>>((a, i) => { const k = by === 'tipo' ? i.tipo_nome : (i.funcionario ?? 'Documentos da empresa'); (a[k] ??= []).push(i); return a }, {}))
  return (
    <div>
      <SectionHeading eyebrow="Pendências" title="Pendências documentais" action={<Button onClick={() => download('/reports/pendencias', { formato: 'csv', status })}><Download className="h-4 w-4" />Exportar CSV</Button>}>Veja documentos faltantes ou vencidos, por funcionário ou por tipo.</SectionHeading>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented value={status} onChange={setStatus} label="Filtro de status" options={[{ value: 'PENDENTE,VENCIDO,A_VENCER', label: 'Todas' }, { value: 'VENCIDO', label: 'Vencidas' }, { value: 'PENDENTE', label: 'Pendentes' }, { value: 'A_VENCER', label: 'A vencer' }]} />
        <Segmented value={by} onChange={setBy} label="Agrupar por" options={[{ value: 'funcionario', label: 'Por funcionário' }, { value: 'tipo', label: 'Por tipo' }]} />
        {r.data?.resumo && <span className="text-sm text-muted-foreground">{r.data.resumo.vencido} vencidas · {r.data.resumo.pendente} pendentes · {r.data.resumo.a_vencer} a vencer</span>}
      </div>
      {msg && <p role="status" className="mb-3 rounded-lg bg-success-bg p-2 text-sm text-success">{msg}</p>}
      {r.error ? <ErrorState error={r.error} retry={r.refetch} /> : r.isLoading ? <DataTable loading rows={[]} cols={[]} /> : !groups.length ? <EmptyState title="Nenhuma pendência" text="Tudo em dia com os filtros atuais." /> : (
        <div className="space-y-3">{groups.map(([k, list]) => (
          <Card key={k} title={k} action={by === 'funcionario' && list[0].employee_id && <Button size="sm" onClick={async () => { const x = await api<any>('/compliance/cobrar', { method: 'POST', body: { employee_id: list[0].employee_id } }); setMsg(`Cobrança enviada a ${x.enviados} gestor(es).`) }}><Mail className="h-3.5 w-3.5" />Cobrar</Button>}>
            <ul className="divide-y divide-border/60">{list.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"><button className="text-left hover:underline" onClick={() => i.employee_id && nav(`/app/funcionarios/${i.employee_id}`)}>{by === 'tipo' ? i.funcionario ?? 'Empresa' : i.tipo_nome} <span className="text-muted-foreground">· {/^\d{4}-\d{2}$/.test(i.referencia) ? competenciaLabel(i.referencia) : i.referencia.toLowerCase()}{i.vence_em ? ` · vence ${fmtDate(i.vence_em)}` : ''}</span></button><StatusPill status={i.status} /></li>
            ))}</ul>
          </Card>
        ))}</div>
      )}
    </div>
  )
}

export function CalendarPage() {
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7))
  const r = useGet<any[]>('/calendar', { month })
  const days = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate()
  const first = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1, 1).getDay()
  const byDay = (r.data ?? []).reduce<Record<number, any[]>>((a, i) => { (a[Number(i.vence_em.slice(8, 10))] ??= []).push(i); return a }, {})
  const shift = (n: number) => { const d = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1 + n, 1); setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`) }
  return (
    <div>
      <SectionHeading eyebrow="Calendário" title="Vencimentos" action={<div className="flex items-center gap-2"><Button onClick={() => shift(-1)} aria-label="Mês anterior">‹</Button><b className="w-28 text-center text-brand-darker">{competenciaLabel(month)}</b><Button onClick={() => shift(1)} aria-label="Próximo mês">›</Button></div>}>ASOs, treinamentos NR, certidões e contratos que vencem no mês.</SectionHeading>
      <div className="grid grid-cols-7 gap-1.5 text-xs" role="grid">
        {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map((d) => <div key={d} className="px-1 text-center font-semibold uppercase text-muted-foreground">{d}</div>)}
        {Array.from({ length: first }).map((_, i) => <div key={'b' + i} />)}
        {Array.from({ length: days }).map((_, i) => (
          <div key={i} className="min-h-24 rounded-lg border border-border bg-surface/70 p-1.5"><span className="font-semibold text-muted-foreground">{i + 1}</span>
            {(byDay[i + 1] ?? []).slice(0, 3).map((e) => <p key={e.id} className={`mt-1 truncate rounded px-1 py-0.5 ${e.status === 'VENCIDO' ? 'bg-danger-bg text-danger' : e.status === 'A_VENCER' ? 'bg-warning-bg text-warning' : 'bg-success-bg text-success'}`} title={`${e.tipo_nome} · ${e.funcionario ?? 'empresa'}`}>{e.tipo_nome}</p>)}
            {(byDay[i + 1]?.length ?? 0) > 3 && <p className="mt-1 text-muted-foreground">+{byDay[i + 1].length - 3}</p>}</div>
        ))}
      </div>
    </div>
  )
}

export function ReportsPage() {
  const items = [['conformidade', 'Conformidade por unidade e cargo'], ['pendencias', 'Pendências documentais'], ['nao-conformidades', 'Não conformidades trabalhistas'], ['armazenamento', 'Uso de armazenamento']]
  return (
    <div>
      <SectionHeading eyebrow="Relatórios" title="Relatórios exportáveis">Exporte em CSV ou XLSX. O agendamento mensal por e-mail ainda não está disponível.</SectionHeading>
      <div className="grid gap-4 md:grid-cols-2">{items.map(([k, l]) => (
        <Card key={k} title={l}><div className="flex gap-2"><Button onClick={() => download(`/reports/${k}`, { formato: 'csv' })}><Download className="h-4 w-4" />CSV</Button><Button onClick={() => download(`/reports/${k}`, { formato: 'xlsx' })}><Download className="h-4 w-4" />XLSX</Button></div></Card>
      ))}</div>
    </div>
  )
}

export function ProfilePage() {
  const qc = useQueryClient()
  const s = useGet<any[]>('/auth/sessions')
  return (
    <div className="mx-auto max-w-3xl">
      <SectionHeading eyebrow="Perfil" title="Sessões e dispositivos" showTitle>Encerre sessões que você não reconhece. Trocar a senha encerra todas.</SectionHeading>
      <DataTable rows={s.data} loading={s.isLoading} cols={[{ key: 'dispositivo', header: 'Dispositivo', render: (x) => <>{x.dispositivo} {x.atual && <StatusPill status="OK" label="esta sessão" />}</> }, { key: 'ip', header: 'IP' }, { key: 'ultimo_uso', header: 'Último uso', render: (x) => fmtDateTime(x.ultimo_uso) },
        { key: 'a', header: '', align: 'right', render: (x) => !x.atual && <Button size="sm" onClick={async () => { await api(`/auth/sessions/${x.id}`, { method: 'DELETE' }); qc.invalidateQueries({ queryKey: ['/auth/sessions'] }) }}><LogOut className="h-3.5 w-3.5" />Encerrar</Button> }]} />
    </div>
  )
}
