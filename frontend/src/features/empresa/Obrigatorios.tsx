import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Building2, Briefcase, Layers, Sparkles, Info } from 'lucide-react'
import { Button, Card, Input, Modal, SectionHeading, Select, SkeletonRows, Field, clsx } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api } from '@/lib/api'

type Scope = { kind: 'todos' } | { kind: 'setor'; id: string; nome: string } | { kind: 'cargo'; id: string; nome: string }
interface Row { on: boolean; momento: string; validade: string; herdado: boolean; tocado: boolean; baseMomento: string }
const MOMENTOS: [string, string][] = [['ADMISSAO', 'Na admissão'], ['MENSAL', 'Todo mês'], ['ANUAL', 'Todo ano'], ['PERIODICO', 'Por validade'], ['DESLIGAMENTO', 'No desligamento']]
const CAT: Record<string, string> = { ADMISSAO: 'Admissão', MENSAL: 'Mensais', SAUDE_SEGURANCA: 'Saúde e segurança', DISCIPLINAR: 'Disciplinar', DESLIGAMENTO: 'Desligamento', OUTROS: 'Outros', EMPRESA: 'Documentos da empresa (certidões e guias)' }
const DEFAULT_MOMENTO: Record<string, string> = { ADMISSAO: 'ADMISSAO', MENSAL: 'MENSAL', SAUDE_SEGURANCA: 'PERIODICO', DESLIGAMENTO: 'DESLIGAMENTO', DISCIPLINAR: 'ADMISSAO', OUTROS: 'ADMISSAO', EMPRESA: 'PERIODICO' }

const sameScope = (r: any, s: Scope) => s.kind === 'todos' ? !r.position_id && !r.department_id : s.kind === 'setor' ? r.department_id === s.id : r.position_id === s.id

/** "Selecionar documentos": marque o que cada setor/cargo precisa entregar. O que não está marcado NÃO gera pendência. */
export function RequirementsPage() {
  const qc = useQueryClient()
  const reqs = useGet<any[]>('/requirements')
  const types = useGet<any[]>('/document-types')
  const deps = useGet<any[]>('/departments')
  const cargos = useGet<any[]>('/positions')
  const [scope, setScope] = useState<Scope>({ kind: 'todos' })
  const [draft, setDraft] = useState<Record<string, Row>>({})
  const [preview, setPreview] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [tplOpen, setTplOpen] = useState(false)
  const [seg, setSeg] = useState('LIMPEZA')
  const [dirty, setDirty] = useState(false)

  const list = useMemo(() => (types.data ?? []).filter((t) => t.codigo !== 'OUTRO' && (scope.kind === 'todos' || t.escopo === 'FUNCIONARIO')), [types.data, scope.kind])
  const own = useMemo(() => (reqs.data ?? []).filter((r) => sameScope(r, scope)), [reqs.data, scope])
  const general = useMemo(() => (reqs.data ?? []).filter((r) => !r.position_id && !r.department_id), [reqs.data])

  // reconstrói o rascunho quando troca o escopo ou os dados chegam
  useEffect(() => {
    if (!reqs.data || !types.data) return
    const d: Record<string, Row> = {}
    for (const t of list) {
      const mine = own.find((r) => r.codigo === t.codigo)
      const inh = scope.kind !== 'todos' ? general.find((r) => r.codigo === t.codigo && r.obrigatorio) : undefined
      const base = DEFAULT_MOMENTO[t.categoria] ?? 'ADMISSAO'
      if (mine) d[t.codigo] = { on: mine.obrigatorio, momento: mine.momento, validade: mine.validade_dias ? String(mine.validade_dias) : '', herdado: false, tocado: false, baseMomento: mine.momento }
      else if (inh) d[t.codigo] = { on: true, momento: inh.momento, validade: inh.validade_dias ? String(inh.validade_dias) : '', herdado: true, tocado: false, baseMomento: inh.momento }
      else d[t.codigo] = { on: false, momento: base, validade: t.validade_padrao_dias && base === 'PERIODICO' ? String(t.validade_padrao_dias) : '', herdado: false, tocado: false, baseMomento: base }
    }
    setDraft(d); setDirty(false); setErr('')
  }, [reqs.data, types.data, list, own, general, scope])

  const set = (cod: string, patch: Partial<Row>) => { setDraft((d) => ({ ...d, [cod]: { ...d[cod], ...patch, tocado: true } })); setDirty(true) }
  const marcados = Object.values(draft).filter((r) => r.on).length

  const payload = () => {
    const items: any[] = []
    for (const t of list) {
      const r = draft[t.codigo]
      if (!r) continue
      const base = { codigo: t.codigo, momento: r.momento, validade_dias: r.validade ? Number(r.validade) : null }
      if (r.on && (!r.herdado || r.tocado)) items.push({ ...base, obrigatorio: true })
      else if (!r.on && r.herdado) items.push({ ...base, momento: r.baseMomento, obrigatorio: false }) // desmarcou o que vinha de "todos": dispensa neste escopo
    }
    // mantém linhas extras do escopo (mais de um momento para o mesmo documento) que a tela não edita
    for (const r of own) { if (!items.some((i) => i.codigo === r.codigo && i.momento === r.momento) && own.filter((o) => o.codigo === r.codigo).length > 1 && r.momento !== draft[r.codigo]?.baseMomento) items.push({ codigo: r.codigo, momento: r.momento, validade_dias: r.validade_dias, obrigatorio: r.obrigatorio }) }
    return { position_id: scope.kind === 'cargo' ? scope.id : null, department_id: scope.kind === 'setor' ? scope.id : null, items }
  }
  const simular = async () => {
    setBusy(true); setErr('')
    try { setPreview(await api('/requirements/bulk', { method: 'PUT', body: { ...payload(), dry_run: true } })) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const salvar = async () => {
    setBusy(true)
    try { await api('/requirements/bulk', { method: 'PUT', body: payload() }); setPreview(null); setDirty(false); qc.invalidateQueries({ queryKey: ['/requirements'] }); qc.invalidateQueries({ queryKey: ['/metrics/overview'] }) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  const cats = [...new Set(list.map((t) => t.categoria))]
  const count = (s: Scope) => (reqs.data ?? []).filter((r) => sameScope(r, s) && r.obrigatorio).length
  const Item = ({ s, label, icon: I }: { s: Scope; label: string; icon: any }) => {
    const active = scope.kind === s.kind && (s.kind === 'todos' || (scope as any).id === (s as any).id)
    return <button onClick={() => { if (!dirty || confirm('Há alterações não salvas. Descartar?')) setScope(s) }} className={clsx('side-item w-full text-left', active && 'side-item-active')}><I className="h-4 w-4" aria-hidden /><span className="min-w-0 flex-1 truncate">{label}</span><span className="rounded-full bg-muted px-2 text-xs text-muted-foreground">{count(s)}</span></button>
  }
  const titulo = scope.kind === 'todos' ? 'Todos os funcionários' : scope.nome

  return (
    <div>
      <SectionHeading eyebrow="Configurações" title="Documentos obrigatórios" action={<Button onClick={() => setTplOpen(true)}><Sparkles className="h-4 w-4" />Modelo por segmento</Button>}>
        Escolha quais documentos cada grupo precisa entregar. <b>Só o que estiver marcado gera pendência</b>: quem não precisa de um documento nunca é cobrado por ele. A regra mais específica vale: funcionário &gt; cargo &gt; setor &gt; todos.
      </SectionHeading>
      {reqs.isLoading || types.isLoading ? <SkeletonRows /> : (
        <div className="grid gap-5 lg:grid-cols-[17rem_1fr]">
          <nav aria-label="Escopos" className="glass-panel space-y-1 self-start p-2">
            <Item s={{ kind: 'todos' }} label="Todos os funcionários" icon={Building2} />
            <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground">Setores</p>
            {deps.data?.length ? deps.data.map((d) => <Item key={d.id} s={{ kind: 'setor', id: d.id, nome: d.nome }} label={d.nome} icon={Layers} />) : <p className="px-3 py-1 text-xs text-muted-foreground">Nenhum setor. Crie em “Setores e cargos”.</p>}
            <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground">Cargos</p>
            {cargos.data?.length ? cargos.data.map((c) => <Item key={c.id} s={{ kind: 'cargo', id: c.id, nome: c.nome }} label={c.nome} icon={Briefcase} />) : <p className="px-3 py-1 text-xs text-muted-foreground">Nenhum cargo cadastrado.</p>}
          </nav>
          <div>
            <Card title={titulo} action={<span className="text-sm text-muted-foreground">{marcados} documento(s) exigido(s)</span>}>
              {marcados === 0 && <p className="mb-3 flex gap-2 rounded-lg bg-muted p-3 text-sm text-muted-foreground"><Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />Nenhum documento marcado: {scope.kind === 'todos' ? 'a empresa ainda não cobra nada de ninguém.' : 'este grupo não gera nenhuma pendência além do que vier de “Todos os funcionários”.'}</p>}
              {scope.kind !== 'todos' && <p className="mb-3 text-xs text-muted-foreground">Documentos marcados como <span className="rounded bg-brand-lighter px-1.5 py-0.5 font-semibold text-brand-darker">herdado</span> vêm de “Todos os funcionários”. Desmarque para dispensar só neste grupo.</p>}
              <div className="space-y-5">
                {cats.map((cat) => (
                  <fieldset key={cat}><legend className="mb-1 text-xs font-semibold uppercase tracking-[.12em] text-muted-foreground">{CAT[cat] ?? cat}</legend>
                    <ul className="divide-y divide-border/60 rounded-xl border border-border bg-surface/70">
                      {list.filter((t) => t.categoria === cat).map((t) => {
                        const r = draft[t.codigo]
                        if (!r) return null
                        return (
                          <li key={t.codigo} className="flex flex-wrap items-center gap-3 px-3 py-2">
                            <label className="flex min-w-56 flex-1 cursor-pointer items-center gap-3"><input type="checkbox" className="h-4 w-4 accent-brand" checked={r.on} onChange={(e) => set(t.codigo, { on: e.target.checked })} />
                              <span className={clsx('text-sm', r.on ? 'font-medium text-brand-darker' : 'text-muted-foreground')}>{t.nome}{t.sensivel_saude && <span className="ml-2 rounded-full bg-muted px-1.5 text-[10px]">saúde</span>}{r.on && r.herdado && !r.tocado && <span className="ml-2 rounded bg-brand-lighter px-1.5 text-[10px] font-semibold text-brand-darker">herdado</span>}</span></label>
                            {r.on && (<>
                              <Select aria-label={`Quando exigir ${t.nome}`} className="!w-44 !py-1.5 !text-xs" value={r.momento} onChange={(e) => set(t.codigo, { momento: e.target.value })}>{MOMENTOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
                              {['PERIODICO', 'ANUAL'].includes(r.momento) && <Input aria-label={`Validade em dias de ${t.nome}`} className="!w-28 !py-1.5 !text-xs" type="number" min={1} placeholder="validade (dias)" value={r.validade} onChange={(e) => set(t.codigo, { validade: e.target.value })} />}
                            </>)}
                          </li>
                        )
                      })}
                    </ul></fieldset>
                ))}
              </div>
              {err && <p role="alert" className="mt-3 text-sm text-danger">{err}</p>}
              <div className="mt-4 flex justify-end gap-2"><Button disabled={!dirty} onClick={() => setScope({ ...scope })}>Descartar</Button><Button variant="primary" loading={busy} disabled={!dirty} onClick={simular}>Revisar e salvar</Button></div>
            </Card>
          </div>
        </div>
      )}
      <Modal open={!!preview} onClose={() => setPreview(null)} eyebrow={titulo} title="Confirmar alteração"
        footer={<><Button onClick={() => setPreview(null)}>Voltar</Button><Button variant="primary" loading={busy} onClick={salvar}>Aplicar</Button></>}>
        {preview && <>
          <p className="text-sm">Serão <b>adicionadas {preview.adicionados}</b> e <b>removidas {preview.removidos}</b> regra(s).</p>
          <p className={clsx('rounded-lg p-3 text-sm', preview.pendencias_depois > preview.pendencias_antes ? 'bg-warning-bg text-warning' : 'bg-success-bg text-success')}>
            Pendências abertas na empresa: <b>{preview.pendencias_antes}</b> → <b>{preview.pendencias_depois}</b> ({preview.pendencias_depois - preview.pendencias_antes >= 0 ? '+' : ''}{preview.pendencias_depois - preview.pendencias_antes}). Esta é uma simulação: nada foi salvo ainda.</p>
        </>}
      </Modal>
      <Modal open={tplOpen} onClose={() => setTplOpen(false)} eyebrow="Modelos prontos" title="Aplicar modelo por segmento" footer={<><Button onClick={() => setTplOpen(false)}>Cancelar</Button><Button onClick={async () => { await api('/requirements/apply-template', { method: 'POST', body: { empresa: true } }); setTplOpen(false); qc.invalidateQueries({ queryKey: ['/requirements'] }) }}>Aplicar certidões da empresa</Button>
        <Button variant="primary" onClick={async () => { await api('/requirements/apply-template', { method: 'POST', body: { segmento: seg } }); setTplOpen(false); qc.invalidateQueries({ queryKey: ['/requirements'] }); qc.invalidateQueries({ queryKey: ['/positions'] }) }}>Criar cargo e aplicar</Button></>}>
        <p className="text-sm text-muted-foreground">Ponto de partida: cria um cargo com o nome do segmento e a lista padrão. Depois ajuste marcando e desmarcando. Nada é aplicado a quem não for desse cargo.</p>
        <Field label="Segmento">{(id) => <Select id={id} value={seg} onChange={(e) => setSeg(e.target.value)}>{['LIMPEZA', 'VIGILANCIA', 'MANUTENCAO', 'PORTARIA', 'ADMINISTRATIVO'].map((x) => <option key={x}>{x}</option>)}</Select>}</Field>
      </Modal>
    </div>
  )
}
