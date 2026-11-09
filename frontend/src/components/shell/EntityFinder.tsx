import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building, Search, Truck, Users } from 'lucide-react'
import { Avatar, clsx } from '@/components/ui'
import { useDebounced, useGet } from '@/lib/query'
import { cnpjMask } from '@/lib/format'
import { empresaPath } from '@/features/rh/Fornecedores'

interface Hit { key: string; grupo: string; titulo: string; detalhe: string; to: string; icon: React.ReactNode }
interface Result { funcionarios: any[]; setores: any[]; empresas: any[] }

const VINCULO: Record<string, string> = { PROPRIA: 'Própria empresa', TERCEIRIZADA: 'Terceirizada', FORNECEDOR: 'Fornecedor' }

/** Localizador do topo (Ctrl/Cmd+K): uma busca acha pessoa, setor, terceirizada ou fornecedor e leva direto à ficha. */
export function EntityFinder() {
  const nav = useNavigate()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [sel, setSel] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const listId = useId()
  const dq = useDebounced(q.trim(), 220)
  const r = useGet<Result>(dq.length >= 2 ? '/directory/search' : null, { q: dq }, { keep: true })

  const hits = useMemo<Hit[]>(() => {
    const d = r.data
    if (!d || dq.length < 2) return []
    return [
      ...d.funcionarios.map((e): Hit => ({ key: 'f' + e.id, grupo: 'Funcionários', titulo: e.nome, to: `/app/funcionarios/${e.id}`, icon: <Avatar nome={e.nome} size="sm" />,
        detalhe: [e.cpf_mascarado, e.vinculo === 'PROPRIA' ? e.setor : `${VINCULO[e.vinculo]}${e.empresa ? ': ' + e.empresa : ''}`, e.status === 'DESLIGADO' ? 'desligado' : ''].filter(Boolean).join(' · ') })),
      ...d.setores.map((s): Hit => ({ key: 's' + s.id, grupo: 'Setores', titulo: s.nome, to: `/app/setores/${s.id}`, icon: <Building className="h-4 w-4 text-brand" aria-hidden />, detalhe: `${s.funcionarios} pessoa(s)` })),
      ...d.empresas.filter((e) => e.tipo === 'TERCEIRIZADA').map((e): Hit => ({ key: 't' + e.id, grupo: 'Terceirizadas', titulo: e.nome, to: empresaPath(e.tipo, e.id), icon: <Users className="h-4 w-4 text-brand" aria-hidden />, detalhe: `${cnpjMask(e.cnpj)} · ${e.funcionarios} alocado(s)${e.status === 'INATIVO' ? ' · inativa' : ''}` })),
      ...d.empresas.filter((e) => e.tipo !== 'TERCEIRIZADA').map((e): Hit => ({ key: 'p' + e.id, grupo: 'Fornecedores', titulo: e.nome, to: empresaPath(e.tipo, e.id), icon: <Truck className="h-4 w-4 text-brand" aria-hidden />, detalhe: `${cnpjMask(e.cnpj)}${e.status === 'INATIVO' ? ' · inativo' : ''}` })),
    ]
  }, [r.data, dq])

  useEffect(() => {
    const key = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); input.current?.focus(); setOpen(true) } }
    const click = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('keydown', key); document.addEventListener('mousedown', click)
    return () => { document.removeEventListener('keydown', key); document.removeEventListener('mousedown', click) }
  }, [])

  const go = (h: Hit) => { setOpen(false); setQ(''); input.current?.blur(); nav(h.to) }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setOpen(false); input.current?.blur() }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSel((i) => Math.min(i + 1, hits.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && hits[sel]) { e.preventDefault(); go(hits[sel]) }
  }
  const mostrar = open && dq.length >= 2
  const grupos = hits.reduce<Record<string, Hit[]>>((a, h) => { (a[h.grupo] ??= []).push(h); return a }, {})

  return (
    <div ref={box} className="relative mr-auto hidden w-full max-w-md min-[900px]:block">
      <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <input ref={input} role="combobox" aria-expanded={mostrar} aria-controls={listId} aria-autocomplete="list" aria-label="Buscar pessoa, setor, terceirizada ou fornecedor"
        className="w-full rounded-full border border-border bg-surface/60 py-2 pl-10 pr-16 text-sm outline-none transition focus:border-brand-light focus:ring-2 focus:ring-brand-light/30"
        placeholder="Buscar pessoa, setor ou empresa" value={q} onChange={(e) => { setQ(e.target.value); setSel(0); setOpen(true) }} onFocus={() => setOpen(true)} onKeyDown={onKey} />
      <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">Ctrl K</kbd>
      {mostrar && (
        <div id={listId} role="listbox" className="glass-dropdown absolute left-0 right-0 top-12 max-h-[26rem] overflow-auto p-2">
          {!hits.length ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">{r.isFetching ? 'Buscando…' : <>Nada encontrado para “{dq}”.<br /><span className="text-xs">Procure por nome, matrícula, CPF completo, setor, razão social ou CNPJ.</span></>}</p>
          ) : Object.entries(grupos).map(([g, list]) => (
            <div key={g} role="group" aria-label={g} className="mb-1 last:mb-0">
              <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground">{g}</p>
              {list.map((h) => {
                const i = hits.indexOf(h)
                return (
                  <button key={h.key} role="option" aria-selected={i === sel} onMouseEnter={() => setSel(i)} onClick={() => go(h)}
                    className={clsx('flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm', i === sel ? 'bg-brand-50' : 'hover:bg-brand-50')}>
                    <span className="grid h-7 w-7 shrink-0 place-items-center">{h.icon}</span>
                    <span className="min-w-0 flex-1"><b className="block truncate text-brand-darker">{h.titulo}</b><span className="block truncate text-xs text-muted-foreground">{h.detalhe}</span></span>
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
