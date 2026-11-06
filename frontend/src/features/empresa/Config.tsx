import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, UserPlus } from 'lucide-react'
import { Button, Card, DataTable, EmptyState, Field, Input, Modal, SectionHeading, Select, SkeletonRows, StatusPill, clsx, KpiCard } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api } from '@/lib/api'
import { fmtBytes, fmtDate, fmtDateTime, fmtMoney } from '@/lib/format'

export function CompanyPage() {
  const qc = useQueryClient()
  const t = useGet<any>('/tenant')
  const units = useGet<any[]>('/units')
  const [unit, setUnit] = useState({ nome: '', cnpj: '' })
  const [lim, setLim] = useState<number | null>(null)
  const [dom, setDom] = useState('')
  const [msg, setMsg] = useState('')
  if (!t.data) return <SkeletonRows />
  const c = t.data
  return (
    <div className="space-y-5">
      <SectionHeading eyebrow="Configurações" title="Empresa e unidades">Confira os dados da empresa e ajuste domínios de e-mail, unidades e o limiar de revisão.</SectionHeading>
      <Card title="Dados da empresa"><dl className="grid gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-xs uppercase text-muted-foreground">Razão social</dt><dd>{c.razao_social}</dd></div><div><dt className="text-xs uppercase text-muted-foreground">CNPJ</dt><dd>{c.cnpj}</dd></div><div><dt className="text-xs uppercase text-muted-foreground">Porte</dt><dd>{c.porte}</dd></div></dl></Card>
      <Card title="Domínios de e-mail permitidos" action={<span className="text-xs text-muted-foreground">alterar exige confirmação por código</span>}>
        <p className="mb-2 text-sm">{c.dominios_email.map((d: string) => <span key={d} className="mr-2 rounded-full bg-brand-lighter px-3 py-1 font-medium text-brand-darker">@{d}</span>)}</p>
        <div className="flex gap-2"><Input aria-label="Novos domínios separados por vírgula" placeholder="empresa.com.br, outra.com.br" value={dom} onChange={(e) => setDom(e.target.value)} /><Button disabled={!dom} onClick={async () => { await api('/tenant/domains', { method: 'PUT', body: { dominios_email: dom.split(',').map((x) => x.trim()) } }); setDom(''); qc.invalidateQueries({ queryKey: ['/tenant'] }); setMsg('Domínios atualizados.') }}>Salvar</Button></div>
      </Card>
      <Card title="Limiar de confiança para revisão humana">
        <p className="mb-2 text-sm text-muted-foreground">Documentos abaixo deste valor vão para a fila de revisão. Padrão: 75%.</p>
        <div className="flex items-center gap-3"><input type="range" min={30} max={99} aria-label="Limiar de confiança" value={lim ?? Math.round(c.limiar_confianca * 100)} onChange={(e) => setLim(Number(e.target.value))} /><b>{lim ?? Math.round(c.limiar_confianca * 100)}%</b>
          <Button disabled={lim === null} onClick={async () => { await api('/tenant', { method: 'PATCH', body: { limiar_confianca: lim! / 100 } }); setMsg('Limiar atualizado.'); qc.invalidateQueries({ queryKey: ['/tenant'] }) }}>Salvar</Button></div>
        {msg && <p role="status" className="mt-2 text-sm text-success">{msg}</p>}
      </Card>
      <Card title="Unidades">
        <DataTable rows={units.data} loading={units.isLoading} empty={<EmptyState title="Sem unidades" />} cols={[{ key: 'nome', header: 'Nome' }, { key: 'cnpj', header: 'CNPJ' }, { key: 'funcionarios', header: 'Funcionários' }]} />
        <div className="mt-3 flex flex-wrap gap-2"><Input className="!w-60" placeholder="Nome da unidade" aria-label="Nome da unidade" value={unit.nome} onChange={(e) => setUnit({ ...unit, nome: e.target.value })} /><Input className="!w-52" placeholder="CNPJ (opcional)" aria-label="CNPJ da unidade" value={unit.cnpj} onChange={(e) => setUnit({ ...unit, cnpj: e.target.value })} />
          <Button disabled={!unit.nome} onClick={async () => { await api('/units', { method: 'POST', body: unit }); setUnit({ nome: '', cnpj: '' }); qc.invalidateQueries({ queryKey: ['/units'] }) }}><Plus className="h-4 w-4" />Adicionar</Button></div>
      </Card>
    </div>
  )
}

export function PositionsPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/positions')
  const deps = useGet<any[]>('/departments')
  const [nome, setNome] = useState('')
  const [seg, setSeg] = useState('')
  const [setor, setSetor] = useState('')
  const [err, setErr] = useState('')
  return (
    <div className="space-y-6">
      <SectionHeading eyebrow="Configurações" title="Setores e cargos">Cada empresa se organiza de um jeito. Crie os setores e cargos que existem na sua e, depois, escolha em “Documentos obrigatórios” o que cada um precisa entregar.</SectionHeading>
      <Card title="Setores">
        <div className="mb-3 flex flex-wrap gap-2"><Input className="!w-64" placeholder="Nome do setor (ex.: Manutenção)" aria-label="Nome do setor" value={setor} onChange={(e) => setSetor(e.target.value)} />
          <Button variant="primary" disabled={!setor} onClick={async () => { setErr(''); try { await api('/departments', { method: 'POST', body: { nome: setor } }); setSetor(''); qc.invalidateQueries({ queryKey: ['/departments'] }) } catch (e) { setErr((e as Error).message) } }}><Plus className="h-4 w-4" />Adicionar setor</Button></div>
        {err && <p role="alert" className="mb-2 text-sm text-danger">{err}</p>}
        <DataTable rows={deps.data} loading={deps.isLoading} empty={<EmptyState title="Nenhum setor" text="Opcional: use setores se a exigência de documentos muda de uma área para outra." />}
          cols={[{ key: 'nome', header: 'Setor' }, { key: 'funcionarios', header: 'Funcionários' },
            { key: 'a', header: '', align: 'right', render: (d) => <Button size="sm" variant="danger" onClick={async () => { if (confirm(`Remover o setor “${d.nome}”? Os funcionários ficam sem setor e as regras do setor deixam de valer.`)) { await api(`/departments/${d.id}`, { method: 'DELETE' }); qc.invalidateQueries({ queryKey: ['/departments'] }); qc.invalidateQueries({ queryKey: ['/requirements'] }) } }}><Trash2 className="h-3.5 w-3.5" />Remover</Button> }]} />
      </Card>
      <Card title="Cargos">
        <div className="mb-3 flex flex-wrap gap-2"><Input className="!w-64" placeholder="Nome do cargo" aria-label="Nome do cargo" value={nome} onChange={(e) => setNome(e.target.value)} />
          <Select aria-label="Segmento" className="!w-52" value={seg} onChange={(e) => setSeg(e.target.value)}><option value="">Segmento (opcional)</option>{['LIMPEZA', 'VIGILANCIA', 'MANUTENCAO', 'PORTARIA', 'ADMINISTRATIVO'].map((x) => <option key={x}>{x}</option>)}</Select>
          <Button variant="primary" disabled={!nome} onClick={async () => { await api('/positions', { method: 'POST', body: { nome, segmento: seg } }); setNome(''); qc.invalidateQueries({ queryKey: ['/positions'] }) }}><Plus className="h-4 w-4" />Adicionar cargo</Button></div>
        <DataTable rows={r.data} loading={r.isLoading} empty={<EmptyState title="Nenhum cargo" />} cols={[{ key: 'nome', header: 'Cargo' }, { key: 'segmento', header: 'Segmento' }, { key: 'funcionarios', header: 'Funcionários' }, { key: 'ativo', header: 'Status', render: (c) => <StatusPill status={c.ativo ? 'ATIVO' : 'INATIVO'} /> }]} />
      </Card>
    </div>
  )
}

const CAMPOS_PADRAO: [string, string][] = [['matricula', 'Matrícula'], ['admissao', 'Data de admissão'], ['cargo', 'Cargo'], ['setor', 'Setor'], ['unidade', 'Unidade'], ['email', 'E-mail'], ['telefone', 'Telefone']]
const slugChave = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').replace(/^(\d)/, 'c$1').slice(0, 30)

/** Cadastro de funcionários sob medida: o que aparece, o que é obrigatório e campos próprios da empresa. */
export function CadastroConfigPage() {
  const qc = useQueryClient()
  const r = useGet<any>('/tenant/cadastro-config')
  const [cfg, setCfg] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const cur = cfg ?? r.data
  if (!cur) return <SkeletonRows />
  const set = (c: any) => setCfg(c)
  const campo = (k: string) => cur.campos?.[k] ?? { ativo: true, obrigatorio: false }
  const addCustom = () => set({ ...cur, personalizados: [...(cur.personalizados ?? []), { chave: '', rotulo: '', tipo: 'texto', obrigatorio: false, opcoes: [] }] })
  const upd = (i: number, p: any) => set({ ...cur, personalizados: cur.personalizados.map((f: any, j: number) => (j === i ? { ...f, ...p } : f)) })
  const salvar = async () => {
    setErr(''); setMsg('')
    const usadas = new Set<string>()
    const personalizados = (cur.personalizados ?? []).map((f: any) => {
      let ch = f.chave || slugChave(f.rotulo)
      while (usadas.has(ch)) ch += '_2'
      usadas.add(ch)
      return { ...f, chave: ch }
    })
    try { await api('/tenant/cadastro-config', { method: 'PUT', body: { campos: cur.campos, personalizados } }); setMsg('Cadastro atualizado.'); setCfg(null); qc.invalidateQueries({ queryKey: ['/tenant/cadastro-config'] }) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div className="space-y-5">
      <SectionHeading eyebrow="Configurações" title="Cadastro de funcionários">Escolha quais campos aparecem nos cadastros criados a partir dos lotes. Nome e CPF são sempre obrigatórios.</SectionHeading>
      <Card title="Campos do cadastro">
        <table className="w-full text-sm"><thead><tr className="text-left text-xs uppercase text-muted-foreground"><th className="py-1">Campo</th><th>Mostrar</th><th>Obrigatório</th></tr></thead>
          <tbody>{CAMPOS_PADRAO.map(([k, l]) => { const c = campo(k); return (
            <tr key={k} className="border-t border-border/60"><th scope="row" className="py-2 text-left font-medium text-brand-darker">{l}</th>
              <td><input type="checkbox" aria-label={`Mostrar ${l}`} className="h-4 w-4 accent-brand" checked={c.ativo} onChange={(e) => set({ ...cur, campos: { ...cur.campos, [k]: { ativo: e.target.checked, obrigatorio: e.target.checked && c.obrigatorio } } })} /></td>
              <td><input type="checkbox" aria-label={`${l} obrigatório`} className="h-4 w-4 accent-brand" disabled={!c.ativo} checked={c.ativo && c.obrigatorio} onChange={(e) => set({ ...cur, campos: { ...cur.campos, [k]: { ativo: c.ativo, obrigatorio: e.target.checked } } })} /></td></tr>) })}</tbody></table>
      </Card>
      <Card title="Campos próprios da empresa" action={<Button size="sm" onClick={addCustom}><Plus className="h-3.5 w-3.5" />Adicionar campo</Button>}>
        {!(cur.personalizados ?? []).length ? <p className="text-sm text-muted-foreground">Ex.: “Número do crachá”, “Contrato / obra”, “Turno”. Eles aparecem no cadastro e ficam salvos no funcionário.</p> : (
          <ul className="space-y-3">{cur.personalizados.map((f: any, i: number) => (
            <li key={i} className="grid gap-2 rounded-xl border border-border bg-surface/70 p-3 sm:grid-cols-[1fr_9rem_8rem_auto]">
              <Input aria-label="Nome do campo" placeholder="Nome do campo" value={f.rotulo} onChange={(e) => upd(i, { rotulo: e.target.value })} />
              <Select aria-label="Tipo" value={f.tipo} onChange={(e) => upd(i, { tipo: e.target.value })}><option value="texto">Texto</option><option value="data">Data</option><option value="numero">Número</option><option value="lista">Lista</option></Select>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand" checked={f.obrigatorio} onChange={(e) => upd(i, { obrigatorio: e.target.checked })} />Obrigatório</label>
              <Button size="sm" variant="danger" aria-label={`Remover ${f.rotulo || 'campo'}`} onClick={() => set({ ...cur, personalizados: cur.personalizados.filter((_: any, j: number) => j !== i) })}><Trash2 className="h-3.5 w-3.5" /></Button>
              {f.tipo === 'lista' && <Input className="sm:col-span-4" aria-label="Opções separadas por vírgula" placeholder="Opções separadas por vírgula (ex.: Manhã, Tarde, Noite)" value={(f.opcoes ?? []).join(', ')} onChange={(e) => upd(i, { opcoes: e.target.value.split(',').map((x: string) => x.trim()).filter(Boolean) })} />}
            </li>))}</ul>)}
      </Card>
      {err && <p role="alert" className="text-sm text-danger">{err}</p>}{msg && <p role="status" className="text-sm text-success">{msg}</p>}
      <div className="flex justify-end"><Button variant="primary" disabled={!cfg} onClick={salvar}>Salvar cadastro</Button></div>
    </div>
  )
}

export function UsersPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/users')
  const units = useGet<any[]>('/units')
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ nome: '', email: '', saude: false, unit: '' })
  const [err, setErr] = useState('')
  const invite = async () => {
    setErr('')
    try { await api('/users', { method: 'POST', body: { nome: f.nome, email: f.email, role: 'RH', perms: f.saude ? ['saude:ler'] : [], unit_scope: f.unit ? [f.unit] : [] } }); setOpen(false); setF({ nome: '', email: '', saude: false, unit: '' }); qc.invalidateQueries({ queryKey: ['/users'] }) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <div>
      <SectionHeading eyebrow="Configurações" title="Usuários RH" action={<Button variant="primary" onClick={() => setOpen(true)}><UserPlus className="h-4 w-4" />Convidar</Button>}>O convite vai por e-mail e só aceita domínios corporativos permitidos pela empresa.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} empty={<EmptyState title="Nenhum usuário" />} cols={[{ key: 'nome', header: 'Nome' }, { key: 'email', header: 'E-mail' }, { key: 'role', header: 'Perfil' },
        { key: 'perms', header: 'Saúde', render: (u) => (u.role === 'ADMIN_EMPRESA' || u.perms.includes('saude:ler') ? 'Sim' : 'Não') }, { key: 'status', header: 'Status', render: (u) => <StatusPill status={u.status} /> }, { key: 'ultimo_login', header: 'Último acesso', render: (u) => fmtDateTime(u.ultimo_login) },
        { key: 'a', header: '', align: 'right', render: (u) => u.role === 'RH' && <span className="flex justify-end gap-1">
          <Button size="sm" onClick={async () => { await api(`/users/${u.id}`, { method: 'PATCH', body: { perms: u.perms.includes('saude:ler') ? [] : ['saude:ler'] } }); qc.invalidateQueries({ queryKey: ['/users'] }) }}>{u.perms.includes('saude:ler') ? 'Remover saúde' : 'Dar acesso a saúde'}</Button>
          <Button size="sm" onClick={async () => { await api(`/users/${u.id}/revoke-sessions`, { method: 'POST' }); }}>Encerrar sessões</Button>
          <Button size="sm" variant="danger" onClick={async () => { await api(`/users/${u.id}`, { method: 'PATCH', body: { status: 'INATIVO' } }); qc.invalidateQueries({ queryKey: ['/users'] }) }}>Desativar</Button></span> }]} />
      <Modal open={open} onClose={() => setOpen(false)} eyebrow="Usuários RH" title="Convidar usuário" footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button><Button variant="primary" disabled={!f.nome || !f.email} onClick={invite}>Enviar convite</Button></>}>
        <Field label="Nome">{(id) => <Input id={id} value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />}</Field>
        <Field label="E-mail corporativo" error={err}>{(id, bad) => <Input id={id} aria-invalid={bad} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}</Field>
        <Field label="Escopo de unidade">{(id) => <Select id={id} value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}><option value="">Todas as unidades</option>{units.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</Select>}</Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.saude} onChange={(e) => setF({ ...f, saude: e.target.checked })} />Pode ver dados de saúde (ASO, atestados, acidentes)</label>
      </Modal>
    </div>
  )
}

export function RetentionPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/retention')
  return (
    <div>
      <SectionHeading eyebrow="Configurações" title="Retenção">Prazos padrão são sugestões: valide com o jurídico da empresa. Terminado o prazo, o documento é excluído ou anonimizado, com registro. A execução automática do prazo ainda não está implementada: hoje a política é apenas registrada.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} cols={[{ key: 'nome', header: 'Tipo' }, { key: 'padrao_dias', header: 'Padrão (dias)' },
        { key: 'dias', header: 'Prazo da empresa (dias)', render: (x) => <Input aria-label={`Prazo de ${x.nome}`} className="!w-28" type="number" min={30} defaultValue={x.dias} onBlur={async (e) => { const v = Number(e.target.value); if (v >= 30 && v !== x.dias) { await api(`/retention/${x.document_type_id}`, { method: 'PUT', body: { dias: v, acao: x.acao } }); qc.invalidateQueries({ queryKey: ['/retention'] }) } }} /> },
        { key: 'acao', header: 'Ação', render: (x) => <Select aria-label={`Ação para ${x.nome}`} className="!w-36" defaultValue={x.acao} onChange={async (e) => { await api(`/retention/${x.document_type_id}`, { method: 'PUT', body: { dias: x.dias, acao: e.target.value } }); qc.invalidateQueries({ queryKey: ['/retention'] }) }}><option value="EXCLUIR">Excluir</option><option value="ANONIMIZAR">Anonimizar</option></Select> }]} />
    </div>
  )
}

export function SupportAccessPage() {
  const qc = useQueryClient()
  const r = useGet<any[]>('/support-access')
  const act = async (id: string, a: string) => { await api(`/support-access/${id}/${a}`, { method: 'POST', body: { horas: 8 } }); qc.invalidateQueries({ queryKey: ['/support-access'] }) }
  return (
    <div>
      <SectionHeading eyebrow="Configurações" title="Acesso de suporte">O Master não lê seus documentos. Quando precisa de ajuda técnica, pede um acesso temporário que só você pode aprovar, e a pessoa vê apenas cópias anonimizadas.</SectionHeading>
      <DataTable rows={r.data} loading={r.isLoading} empty={<EmptyState title="Nenhum pedido de acesso" />} cols={[{ key: 'solicitante', header: 'Solicitante' }, { key: 'motivo', header: 'Motivo' }, { key: 'status', header: 'Status', render: (x) => <StatusPill status={x.status} /> }, { key: 'expira_em', header: 'Expira', render: (x) => fmtDateTime(x.expira_em) },
        { key: 'a', header: '', align: 'right', render: (x) => <span className="flex justify-end gap-1">{x.status === 'PENDENTE' && <><Button size="sm" variant="primary" onClick={() => act(x.id, 'approve')}>Aprovar 8h</Button><Button size="sm" onClick={() => act(x.id, 'deny')}>Negar</Button></>}{x.status === 'APROVADO' && <Button size="sm" variant="danger" onClick={() => act(x.id, 'revoke')}>Revogar</Button>}</span> }]} />
    </div>
  )
}

export function BillingPage() {
  const r = useGet<any>('/billing')
  const b = r.data
  if (!b) return <SkeletonRows />
  return (
    <div className="space-y-5">
      <SectionHeading eyebrow="Conta" title="Plano e uso">Acompanhe limites, armazenamento, consumo mensal e faturas da empresa.</SectionHeading>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Plano" value={b.plano?.nome} hint={fmtMoney(b.plano?.preco_mensal_centavos)} />
        <KpiCard label="Armazenamento" value={fmtBytes(b.limites.bytes_usados)} hint={`cota ${fmtBytes(b.limites.quota_bytes)}`} tone={b.limites.bytes_usados > b.limites.quota_bytes * 0.8 ? 'warning' : 'default'} />
        <KpiCard label="Páginas/mês (limite)" value={b.limites.quota_paginas_mes} />
        <KpiCard label="Usuários RH / funcionários" value={`${b.limites.max_usuarios_rh ?? '∞'} / ${b.limites.max_funcionarios ?? '∞'}`} />
      </div>
      <Card title="Uso mensal"><DataTable rows={b.uso} cols={[{ key: 'mes', header: 'Mês' }, { key: 'paginas', header: 'Páginas' }, { key: 'docs', header: 'Documentos' }, { key: 'revisoes', header: 'Revisões' }, { key: 'bytes_total', header: 'Armazenado', render: (x) => fmtBytes(x.bytes_total) }]} empty={<EmptyState title="Sem uso registrado" />} /></Card>
      <Card title="Faturas"><DataTable rows={b.faturas} cols={[{ key: 'referencia', header: 'Referência' }, { key: 'valor_centavos', header: 'Valor', render: (x) => fmtMoney(x.valor_centavos) }, { key: 'vencimento', header: 'Vencimento', render: (x) => fmtDate(x.vencimento) }, { key: 'status', header: 'Status' }]} empty={<EmptyState title="Nenhuma fatura" text="Preço sob consulta: o faturamento é combinado em contrato." />} /></Card>
    </div>
  )
}

export function AuditPage() {
  const [acao, setAcao] = useState('')
  const r = useGet<{ items: any[] }>('/audit', { acao, limit: 100 }, { keep: true })
  return (
    <div>
      <SectionHeading eyebrow="Conta" title="Auditoria">Trilha imutável encadeada por hash: ninguém, nem a plataforma, consegue alterar ou apagar um evento sem quebrar a cadeia.</SectionHeading>
      <div className="mb-3"><Input className="!w-72" placeholder="Filtrar por ação (ex.: DOWNLOAD)" aria-label="Filtrar por ação" value={acao} onChange={(e) => setAcao(e.target.value)} /></div>
      <DataTable rows={r.data?.items} loading={r.isLoading} cols={[{ key: 'criado_em', header: 'Quando', render: (x) => fmtDateTime(x.criado_em) }, { key: 'acao', header: 'Ação' }, { key: 'ator_nome', header: 'Quem', render: (x) => x.ator_nome ?? x.ator_role }, { key: 'entidade', header: 'Entidade' }, { key: 'ip', header: 'IP' }]} />
    </div>
  )
}

export function LogsPage() {
  const [tipo, setTipo] = useState('processamento')
  const r = useGet<any>(`/logs/${tipo}`)
  const rows = Array.isArray(r.data) ? r.data : r.data?.eventos
  return (
    <div>
      <SectionHeading eyebrow="Conta" title="Logs">Consulte eventos de armazenamento, processamento, organização e revisão.</SectionHeading>
      <div className="mb-4 segmented" role="tablist">{['armazenamento', 'processamento', 'organizacao', 'revisao'].map((t) => <button key={t} role="tab" aria-selected={tipo === t} onClick={() => setTipo(t)} className={clsx('segmented-tab', tipo === t && 'segmented-tab-active')}>{t === 'organizacao' ? 'Organização' : t === 'revisao' ? 'Revisão' : t[0].toUpperCase() + t.slice(1)}</button>)}</div>
      {tipo === 'organizacao' && r.data?.vinculos && <p className="mb-3 text-sm text-muted-foreground">Vínculos automáticos: <b>{r.data.vinculos.automaticos}</b> · sem vínculo: <b>{r.data.vinculos.sem_vinculo}</b> · manuais: <b>{r.data.manuais}</b> · divisões: <b>{r.data.divisoes}</b> · junções: <b>{r.data.juncoes}</b></p>}
      <DataTable rows={rows} loading={r.isLoading} cols={rows?.[0] ? Object.keys(rows[0]).filter((k) => !['antes', 'depois', 'id', 'document_id'].includes(k)).map((k) => ({ key: k, header: k.replaceAll('_', ' '), render: (x: any) => (/_em$|quando/.test(k) ? fmtDateTime(x[k]) : k === 'bytes' ? fmtBytes(x[k]) : String(x[k] ?? '—')) })) : []} />
    </div>
  )
}
