import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Copy, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui'
import { api } from '@/lib/api'
import { useGet } from '@/lib/query'

/** Documentos descartados por terem o mesmo conteúdo de outro (o mesmo documento escaneado de formas diferentes). Dá para restaurar. */
export function DuplicadosDescartados({ loteId, total }: { loteId: string; total: number }) {
  const qc = useQueryClient()
  const r = useGet<{ items: any[] }>(total > 0 ? '/documents' : null, { lote: loteId, status: 'REJEITADO', limit: 100 })
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState('')
  if (!total) return null
  const itens = (r.data?.items ?? []).filter((d) => (d.motivos_revisao ?? []).includes('DUPLICATA_CONTEUDO'))
  const restaurar = async (id: string) => {
    setBusy(id); setErr('')
    try {
      await api(`/review/${id}`, { method: 'POST', body: { acao: 'RESTAURAR_DUPLICATA' } })
      for (const k of [`/batches/${loteId}`, '/documents', '/review/queue', '/metrics/overview']) qc.invalidateQueries({ queryKey: [k] })
    } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }
  return (
    <details className="mb-3 rounded-xl border border-border bg-muted/40 p-3 text-sm">
      <summary className="flex cursor-pointer items-center gap-2 font-semibold text-brand-darker"><Copy className="h-4 w-4" aria-hidden />{total} documento(s) igual(is) a outro, escaneado(s) de forma diferente, descartado(s)</summary>
      <p className="mt-2 text-muted-foreground">O texto lido por OCR é praticamente o mesmo de um documento já guardado, então só uma cópia foi mantida. Se algum for na verdade um documento diferente, restaure-o: ele vai para a fila de revisão.</p>
      {r.isLoading ? <p className="mt-2 text-muted-foreground">Carregando…</p> : (
        <ul className="mt-2 space-y-1">
          {itens.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2 rounded-lg bg-white/70 px-2 py-1">
              <span><b className="text-brand-darker">{d.tipo_nome}</b> · pág. {(d.paginas ?? []).join(', ')}{d.funcionario_nome ? ` · ${d.funcionario_nome}` : ''}</span>
              <Button size="sm" loading={busy === d.id} onClick={() => restaurar(d.id)}><Undo2 className="h-4 w-4" />Restaurar</Button>
            </li>
          ))}
        </ul>
      )}
      {err && <p role="alert" className="mt-2 rounded-lg bg-danger-bg p-2 text-danger">{err}</p>}
    </details>
  )
}
