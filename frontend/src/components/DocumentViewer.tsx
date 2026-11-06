import { useState } from 'react'
import { ChevronLeft, ChevronRight, RotateCw, ZoomIn, ZoomOut } from 'lucide-react'
import { Button, clsx } from '@/components/ui'

export interface ViewPage { numero: number; url: string; thumb_url?: string; rotacao?: number }
export interface Highlight { numero: number; caixas: number[][] }

/** Visualizador: páginas com zoom, girar e navegar; destaca o termo buscado usando as caixas do OCR. */
export function DocumentViewer({ pages, highlights = [], rotateRef }: { pages: ViewPage[]; highlights?: Highlight[]; rotateRef?: (fn: () => void) => void }) {
  const [i, setI] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [rot, setRot] = useState<Record<number, number>>({})
  const p = pages[i]
  const rotate = () => setRot((r) => ({ ...r, [i]: ((r[i] ?? p?.rotacao ?? 0) + 90) % 360 }))
  rotateRef?.(rotate)
  if (!p) return <div className="grid h-64 place-items-center rounded-xl border border-dashed border-border-strong text-sm text-muted-foreground">Sem páginas para exibir</div>
  const boxes = highlights.find((h) => h.numero === p.numero)?.caixas ?? []
  const deg = rot[i] ?? p.rotacao ?? 0
  return (
    <div className="flex h-full min-h-[28rem] flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button size="sm" aria-label="Página anterior" disabled={i === 0} onClick={() => setI(i - 1)}><ChevronLeft className="h-4 w-4" /></Button>
          <span className="px-2 text-sm text-muted-foreground" aria-live="polite">Página {p.numero} <span className="opacity-60">({i + 1}/{pages.length})</span></span>
          <Button size="sm" aria-label="Próxima página" disabled={i === pages.length - 1} onClick={() => setI(i + 1)}><ChevronRight className="h-4 w-4" /></Button>
        </div>
        <div className="flex items-center gap-1">
          <Button size="sm" aria-label="Reduzir" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}><ZoomOut className="h-4 w-4" /></Button>
          <span className="w-12 text-center text-xs text-muted-foreground">{Math.round(zoom * 100)}%</span>
          <Button size="sm" aria-label="Ampliar" onClick={() => setZoom((z) => Math.min(3, z + 0.25))}><ZoomIn className="h-4 w-4" /></Button>
          <Button size="sm" aria-label="Girar (R)" onClick={rotate}><RotateCw className="h-4 w-4" /></Button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-border bg-brand-50/60 p-3">
        <div className="relative mx-auto origin-top-left" style={{ width: `${zoom * 100}%`, transform: deg ? `rotate(${deg}deg)` : undefined, transformOrigin: 'center' }}>
          <img src={p.url} alt={`Página ${p.numero} do documento`} className="block w-full rounded-md bg-surface shadow-md" draggable={false} />
          {boxes.map((b, k) => <span key={k} aria-hidden className="absolute rounded-sm bg-yellow-300/50 ring-1 ring-yellow-500" style={{ left: b[0] * 100 + '%', top: b[1] * 100 + '%', width: (b[2] - b[0]) * 100 + '%', height: (b[3] - b[1]) * 100 + '%' }} />)}
        </div>
      </div>
      {pages.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Páginas">
          {pages.map((q, k) => (
            <button key={q.numero} role="tab" aria-selected={k === i} onClick={() => setI(k)} className={clsx('h-16 w-12 shrink-0 overflow-hidden rounded-md border-2 bg-surface', k === i ? 'border-brand-default' : 'border-transparent opacity-70 hover:opacity-100')}>
              <img src={q.thumb_url ?? q.url} alt={`Miniatura da página ${q.numero}`} className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
