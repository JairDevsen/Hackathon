import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search as SearchIcon, FileSearch } from 'lucide-react'
import { Avatar, ComplianceRing, EmptyState, Input, SectionHeading, SkeletonRows, StatusPill } from '@/components/ui'
import { useGet } from '@/lib/query'
import { cpfMask, cpfValido } from '@/lib/format'

/** Busca única: reconhece CPF (com/sem máscara, valida o dígito), matrícula ou nome. Atalho `/`. */
export function SearchPage() {
  const nav = useNavigate()
  const ref = useRef<HTMLInputElement>(null)
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  useEffect(() => { ref.current?.focus() }, [])
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') { e.preventDefault(); ref.current?.focus() } }
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k)
  }, [])
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 250); return () => clearTimeout(t) }, [q])
  const looksCpf = /^[\d.\-\s]+$/.test(dq) && dq.replace(/\D/g, '').length === 11
  const res = useGet<{ items: any[]; tipo_busca: string; cpf_valido?: boolean }>(dq.length >= 2 ? '/employees' : null, { q: dq, limit: 20 })
  const text = useGet<any[]>(dq.length >= 3 && !looksCpf ? '/documents/search' : null, { q: dq })
  // um resultado único abre o dossiê direto (só quando a busca é por CPF ou matrícula: nome pode ser ambíguo ao digitar)
  useEffect(() => {
    if (res.data?.items.length === 1 && ['cpf', 'matricula'].includes(res.data.tipo_busca)) nav(`/app/funcionarios/${res.data.items[0].id}`)
  }, [res.data, nav])

  return (
    <div className="mx-auto max-w-3xl">
      <SectionHeading eyebrow="Buscar" title="Buscar funcionários e documentos">Digite um CPF, uma matrícula ou um nome. Também é possível buscar um trecho dentro dos documentos, como “jornada diária”.</SectionHeading>
      <div className="relative">
        <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-brand-default" aria-hidden />
        <Input ref={ref} value={q} onChange={(e) => setQ(/^[\d.\-\s]+$/.test(e.target.value) && e.target.value.replace(/\D/g, '').length >= 9 ? cpfMask(e.target.value) : e.target.value)}
          placeholder="CPF, matrícula ou nome  (atalho: /)" aria-label="Buscar funcionário" className="!rounded-full !py-4 !pl-12 !text-lg shadow-md" />
      </div>
      {looksCpf && !cpfValido(dq) && <p role="alert" className="mt-2 text-sm text-danger">Esse CPF não é válido: confira os dígitos.</p>}
      <div className="mt-6 space-y-6">
        {res.isFetching && !res.data ? <SkeletonRows n={3} /> : res.data?.items.length ? (
          <ul className="space-y-2">
            {res.data.items.map((e) => {
              const pct = e.total ? (100 * e.ok) / e.total : 0
              return (
                <li key={e.id}><button onClick={() => nav(`/app/funcionarios/${e.id}`)} className="glass-panel flex w-full items-center gap-4 p-3 text-left transition hover:shadow-lg">
                  <Avatar nome={e.nome} size="lg" />
                  <span className="min-w-0 flex-1"><b className="block truncate text-brand-darker">{e.nome}</b><span className="text-sm text-muted-foreground">{e.cpf_mascarado} · {e.cargo ?? 'sem cargo'} · {e.unidade ?? 'sem unidade'}</span></span>
                  <StatusPill status={e.pendencias ? 'PENDENTE' : 'OK'} label={e.pendencias ? `${e.pendencias} pendência(s)` : 'Em dia'} />
                  <ComplianceRing pct={pct} size={52} label={false} />
                </button></li>
              )
            })}
          </ul>
        ) : dq.length >= 2 && !res.isFetching && !text.data?.length ? (
          <EmptyState icon={<SearchIcon className="h-5 w-5" />} title="Nenhum resultado" text="Confira o CPF/nome ou envie um lote para ver os documentos vinculados." />
        ) : null}
        {!!text.data?.length && (
          <section aria-label="Resultados dentro dos documentos">
            <h2 className="mb-2 flex items-center gap-2 font-display text-lg font-semibold text-brand-darker"><FileSearch className="h-5 w-5" />Dentro dos documentos</h2>
            <ul className="space-y-2">
              {text.data.map((d) => (
                <li key={d.id}><button onClick={() => nav(`/app/documentos/${d.id}?q=${encodeURIComponent(dq)}`)} className="glass-panel block w-full p-3 text-left hover:shadow-lg">
                  <span className="text-sm font-semibold text-brand-darker">{d.tipo_nome}</span><span className="text-sm text-muted-foreground"> · {d.funcionario_nome ?? 'sem funcionário'} · pág. {d.paginas.join(', ')}</span>
                  <span className="mt-1 block text-sm" dangerouslySetInnerHTML={{ __html: escapeHl(d.trecho) }} />
                </button></li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}

// o trecho vem com << >> como marcadores; escapa o HTML e só então aplica <mark>
function escapeHl(s: string) {
  const esc = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return esc.replace(/&lt;&lt;/g, '<mark class="rounded bg-yellow-200 px-0.5">').replace(/&gt;&gt;/g, '</mark>')
}
