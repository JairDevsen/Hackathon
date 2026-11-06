import { useEffect, useMemo, useState } from 'react'
import { ArrowLeftRight } from 'lucide-react'
import { Modal, Select, clsx } from '@/components/ui'
import { useGet } from '@/lib/query'
import { competenciaLabel, fmtDate } from '@/lib/format'

const norm = (v: unknown) => String(v ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim()

function fields(d: any): [string, string][] {
  const base: [string, string][] = [
    ['Nome lido no documento', d.nome_extraido ?? ''], ['Nome no cadastro', d.funcionario_nome ?? ''], ['CPF', d.funcionario_cpf ?? ''], ['Empresa', d.empresa_nome ?? ''],
    ['Data do documento', d.data_documento ? fmtDate(d.data_documento) : ''], ['Validade', d.validade_ate ? fmtDate(d.validade_ate) : ''], ['Competência', d.competencia ? competenciaLabel(d.competencia) : ''],
  ]
  const extra = Object.entries(d.campos ?? {}).filter(([k, v]) => v && !['cpf', 'nome', 'empresa_nome', 'empresa_cnpj', 'data_documento', 'validade_ate', 'competencia'].includes(k)).map(([k, v]) => [k.replaceAll('_', ' '), String(v)] as [string, string])
  return [...base, ...extra]
}

/** Compara dois documentos do mesmo funcionário lado a lado e destaca o que diverge (nome, datas, números). */
export function CompareModal({ docId, open, onClose }: { docId: string | null; open: boolean; onClose: () => void }) {
  const a = useGet<any>(open && docId ? `/documents/${docId}` : null)
  const list = useGet<any[]>(open && a.data?.employee_id ? `/employees/${a.data.employee_id}/documents` : null)
  const [otherId, setOtherId] = useState('')
  const others = useMemo(() => (list.data ?? []).filter((x) => x.id !== docId && !x.mascarado), [list.data, docId])
  useEffect(() => { if (open && others.length && !others.some((o) => o.id === otherId)) setOtherId(others[0].id) }, [open, others, otherId])
  const b = useGet<any>(open && otherId ? `/documents/${otherId}` : null)
  const rowsA = a.data ? fields(a.data) : []
  const rowsB = b.data ? fields(b.data) : []
  const keys = [...new Set([...rowsA.map((r) => r[0]), ...rowsB.map((r) => r[0])])]
  const val = (rows: [string, string][], k: string) => rows.find((r) => r[0] === k)?.[1] ?? ''
  const thumb = (d: any) => d?.paginas_urls?.[0]?.thumb_url ?? d?.paginas_urls?.[0]?.url
  return (
    <Modal wide open={open} onClose={onClose} eyebrow="Revisão" title="Comparar documentos">
      {!a.data?.employee_id ? <p className="text-sm text-muted-foreground">Este documento não está vinculado a um funcionário: não há outro documento para comparar.</p> : !others.length && !list.isLoading ? <p className="text-sm text-muted-foreground">Este funcionário não tem outro documento para comparar.</p> : (
        <>
          <label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground" htmlFor="cmp">Comparar com</label>
          <Select id="cmp" value={otherId} onChange={(e) => setOtherId(e.target.value)}>{others.map((o) => <option key={o.id} value={o.id}>{o.tipo_nome}{o.competencia ? ` · ${competenciaLabel(o.competencia)}` : ''}</option>)}</Select>
          <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3">
            {[a.data, b.data].map((d, i) => (
              <div key={i} className={i === 1 ? 'col-start-3' : ''}>
                <p className="mb-1 text-sm font-semibold text-brand-darker">{d?.tipo_nome ?? '…'}</p>
                {thumb(d) ? <img src={thumb(d)} alt={`Primeira página: ${d?.tipo_nome}`} className="max-h-48 rounded-lg border border-border bg-surface object-contain" /> : <div className="h-24 rounded-lg bg-muted" />}
              </div>
            ))}
            <ArrowLeftRight className="col-start-2 row-start-1 mt-16 h-5 w-5 text-brand-default" aria-hidden />
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs uppercase text-muted-foreground"><th className="py-1">Campo</th><th>{a.data?.tipo_nome}</th><th>{b.data?.tipo_nome}</th></tr></thead>
            <tbody>{keys.map((k) => {
              const x = val(rowsA, k), y = val(rowsB, k)
              const diff = x && y && norm(x) !== norm(y)
              return <tr key={k} className={clsx('border-t border-border/60', diff && 'bg-warning-bg')}><th scope="row" className="py-1.5 pr-2 text-left font-medium capitalize text-brand-darker">{k}{diff && <span className="ml-2 rounded-full bg-warning px-1.5 text-[10px] font-bold text-white">diverge</span>}</th><td>{x || '—'}</td><td>{y || '—'}</td></tr>
            })}</tbody>
          </table>
        </>
      )}
    </Modal>
  )
}
