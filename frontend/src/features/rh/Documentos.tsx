import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import { FileText, Search } from 'lucide-react'
import { Button, ConfidenceBar, DataTable, EmptyState, ErrorState, Input, SectionHeading, Select, StatusPill, clsx } from '@/components/ui'
import { api } from '@/lib/api'
import { problemas } from '@/lib/analise'
import { useGet } from '@/lib/query'
import { competenciaLabel, fmtDate } from '@/lib/format'

const CATS: [string, string][] = [['', 'Todas as categorias'], ['ADMISSAO', 'Admissão'], ['MENSAL', 'Mensais'], ['SAUDE_SEGURANCA', 'Saúde e segurança'], ['DISCIPLINAR', 'Disciplinar'], ['DESLIGAMENTO', 'Desligamento'], ['EMPRESA', 'Empresa'], ['OUTROS', 'Outros']]
const ABAS: [string, string, string][] = [['', 'Todos', 'todos'], ['AUTO_APROVADO,REVISADO', 'Aprovados', 'aprovados'], ['AGUARDANDO_REVISAO', 'Em revisão', 'revisao'], ['REJEITADO', 'Rejeitados', 'rejeitados']]

/** Todos os documentos da empresa, com busca e filtros (a mesma visão para Admin e RH). */
export function DocumentosPage() {
  const nav = useNavigate()
  const types = useGet<any[]>('/document-types')
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  const [tipo, setTipo] = useState('')
  const [cat, setCat] = useState('')
  const [status, setStatus] = useState('')
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 300); return () => clearTimeout(t) }, [q])
  const r = useInfiniteQuery({
    queryKey: ['/documents', dq, tipo, cat, status],
    queryFn: ({ pageParam }) => api<any>('/documents', { query: { q: dq, tipo, categoria: cat, status, cursor: pageParam, limit: 30 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  })
  const rows = r.data?.pages.flatMap((p) => p.items) ?? []
  const resumo = r.data?.pages[0]?.resumo
  return (
    <div>
      <SectionHeading eyebrow="Documentos" title="Todos os documentos">Pesquise por funcionário, tipo ou nome do arquivo. Documentos de saúde aparecem mascarados para quem não tem a permissão.</SectionHeading>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-60 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden /><Input className="pl-9" placeholder="Buscar por funcionário, tipo ou arquivo…" aria-label="Buscar documentos" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Select aria-label="Tipo de documento" className="!w-56" value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="">Todos os tipos</option>{types.data?.filter((t) => t.codigo !== 'OUTRO').map((t) => <option key={t.codigo} value={t.codigo}>{t.nome}</option>)}</Select>
        <Select aria-label="Categoria" className="!w-52" value={cat} onChange={(e) => setCat(e.target.value)}>{CATS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
      </div>
      <div className="segmented mb-4 flex-wrap" role="tablist" aria-label="Situação">
        {ABAS.map(([v, l, k]) => <button key={l} role="tab" aria-selected={status === v} onClick={() => setStatus(v)} className={clsx('segmented-tab', status === v && 'segmented-tab-active')}>{l}{resumo ? ` (${resumo[k]})` : ''}</button>)}
      </div>
      {r.error ? <ErrorState error={r.error} retry={() => r.refetch()} /> : (
        <>
          <DataTable rows={rows} loading={r.isLoading} onRow={(d) => nav(`/app/documentos/${d.id}`)} empty={<EmptyState icon={<FileText className="h-5 w-5" />} title="Nenhum documento encontrado" text="Ajuste os filtros ou envie um lote para começar." />}
            cols={[
              { key: 'tipo_nome', header: 'Documento', render: (d) => <span><b className="text-brand-darker">{d.tipo_nome}</b>{d.nome_arquivo && <span className="block max-w-[26rem] truncate text-xs text-muted-foreground" title={d.nome_arquivo}>{d.nome_arquivo}</span>}</span> },
              { key: 'funcionario_nome', header: 'Funcionário', render: (d) => d.mascarado ? <span className="text-muted-foreground">restrito</span> : <span className="whitespace-nowrap">{d.funcionario_nome ?? <span className="text-muted-foreground">sem vínculo</span>}</span> },
              { key: 'competencia', header: 'Competência / data', render: (d) => (d.competencia ? competenciaLabel(d.competencia) : fmtDate(d.data_documento)) },
              { key: 'confianca', header: 'Confiança', render: (d) => <ConfidenceBar value={Number(d.confianca)} /> },
              { key: 'problemas', header: 'Problemas', render: (d) => { const ps = problemas(d); return ps.length ? <span className="flex flex-wrap gap-1">{ps.slice(0, 2).map((p) => <span key={p.codigo} className={clsx('rounded-full px-2 py-0.5 text-xs font-semibold', p.nivel === 'erro' ? 'bg-danger-bg text-danger' : 'bg-warning-bg text-warning')}>{p.titulo}</span>)}{ps.length > 2 && <span className="text-xs text-muted-foreground">+{ps.length - 2}</span>}</span> : <span className="text-muted-foreground">—</span> } },
              { key: 'status', header: 'Status', render: (d) => <StatusPill status={d.status} /> },
            ]} />
          {r.hasNextPage && <div className="mt-4 text-center"><Button loading={r.isFetchingNextPage} onClick={() => r.fetchNextPage()}>Carregar mais</Button></div>}
        </>
      )}
    </div>
  )
}
