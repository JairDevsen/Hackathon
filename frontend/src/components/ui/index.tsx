import { forwardRef, useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { createPortal } from 'react-dom'
import { Loader2, X } from 'lucide-react'
import { clsx } from 'clsx'

export { clsx }

/* ---------- Logo: símbolo da torre + "CITADEL" (brand-darker) + "IA" (brand) para o app claro ---------- */
export function LogoMark({ className = 'h-8 w-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="Citadel IA">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#8a52d4" /><stop offset=".55" stopColor="#6020b8" /><stop offset="1" stopColor="#2e1463" /></linearGradient></defs>
      <path d="M22 10h6v6h8v-6h6v6h2v8l-3 4 3 20h-8l-3-12-3 12h-8l3-20-3-4v-8h2z" fill="url(#lg)" />
      <path d="M6 50C22 44 44 34 58 22" stroke="url(#lg)" strokeWidth="4" strokeLinecap="round" fill="none" />
    </svg>
  )
}
export function Logo({ dark = false, compact = false }: { dark?: boolean; compact?: boolean }) {
  if (dark) return <img src="/brand/citadel-logo.png" alt="Citadel IA" className="h-12 w-auto object-contain" />
  return (
    <span className="inline-flex items-center gap-2">
      <LogoMark />
      {!compact && <span className="font-display text-lg font-bold tracking-[.18em] text-brand-darker">CITADEL <span className="text-brand">IA</span></span>}
    </span>
  )
}

/* ---------- Botões ---------- */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' | 'soft'; loading?: boolean; size?: 'sm' | 'md' }
export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button({ variant = 'ghost', loading, size = 'md', className, children, disabled, ...p }, ref) {
  const base = size === 'sm' ? 'text-xs px-3 py-1.5' : 'text-sm px-4 py-2'
  const v = {
    primary: 'btn-primary-gradient',
    soft: 'rounded-full bg-brand-lighter font-semibold text-brand-darker hover:bg-brand-light/60',
    ghost: 'rounded-full border border-border-strong bg-surface/80 font-medium text-foreground hover:border-brand-light hover:text-brand',
    danger: 'rounded-full bg-danger font-semibold text-white hover:opacity-90',
  }[variant]
  return (
    <button ref={ref} disabled={disabled || loading} className={clsx('inline-flex items-center justify-center gap-2 transition disabled:cursor-not-allowed disabled:opacity-60', variant !== 'primary' && base, variant === 'primary' && (size === 'sm' ? 'text-xs' : 'text-sm'), v, className)} {...p}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
})

/* ---------- Campos ---------- */
export function Field({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: (id: string, invalid: boolean) => ReactNode }) {
  const id = useId()
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</label>
      {children(id, !!error)}
      {error ? <p role="alert" className="text-xs text-danger">{error}</p> : hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} className={clsx('field-cristal', className)} {...p} />
})
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...p }, ref) {
  return <select ref={ref} className={clsx('field-cristal', className)} {...p} />
})
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} className={clsx('field-cristal min-h-24', className)} {...p} />
})

/* ---------- Modal (overlay com blur, cartão em degradê, eyebrow, título em Playfair, fechar circular) ---------- */
export function Modal({ open, onClose, eyebrow, title, children, footer, wide }: { open: boolean; onClose: () => void; eyebrow?: string; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => { document.removeEventListener('keydown', onKey); prev?.focus() }
  }, [open, onClose])
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center p-4 backdrop-blur-sm" style={{ background: 'rgba(20,11,40,.45)' }} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby="modal-title" tabIndex={-1}
        className={clsx('max-h-[90dvh] w-full overflow-auto rounded-xl border border-white/90 p-6 shadow-lg animate-pop', wide ? 'max-w-3xl' : 'max-w-lg')}
        style={{ background: 'var(--modal-bg)' }}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {eyebrow && <p className="text-xs font-semibold uppercase tracking-[.14em] text-muted-foreground">{eyebrow}</p>}
            <h2 id="modal-title" className="font-display text-2xl font-bold text-brand-darker">{title}</h2>
          </div>
          <button onClick={onClose} aria-label="Fechar" className="icon-circle shrink-0 hover:bg-brand-lighter"><X className="h-4 w-4" /></button>
        </div>
        <div className="space-y-4">{children}</div>
        {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>, document.body)
}

/* ---------- Segmented ---------- */
export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label?: string }) {
  return (
    <div className="segmented" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)} className={clsx('segmented-tab', value === o.value && 'segmented-tab-active')}>{o.label}</button>
      ))}
    </div>
  )
}

/* ---------- Status ---------- */
const PILL: Record<string, [string, string]> = {
  OK: ['bg-success-bg text-success', 'OK'], AUTO_APROVADO: ['bg-success-bg text-success', 'Auto-aprovado'], REVISADO: ['bg-success-bg text-success', 'Revisado'], PROCESSADO: ['bg-success-bg text-success', 'Processado'], ATIVO: ['bg-success-bg text-success', 'Ativo'], APROVADO: ['bg-success-bg text-success', 'Aprovado'],
  A_VENCER: ['bg-warning-bg text-warning', 'A vencer'], AGUARDANDO_REVISAO: ['bg-warning-bg text-warning', 'Aguardando revisão'], PROCESSANDO: ['bg-warning-bg text-warning', 'Processando'], RECEBIDO: ['bg-warning-bg text-warning', 'Recebido'], PROCESSADO_COM_PENDENCIAS: ['bg-warning-bg text-warning', 'Com pendências'], PENDENTE: ['bg-danger-bg text-danger', 'Pendente'], CONVIDADO: ['bg-warning-bg text-warning', 'Convidado'], SUSPENSO: ['bg-warning-bg text-warning', 'Suspenso'],
  VENCIDO: ['bg-danger-bg text-danger', 'Vencido'], REJEITADO: ['bg-danger-bg text-danger', 'Rejeitado'], FALHOU: ['bg-danger-bg text-danger', 'Falhou'], NEGADO: ['bg-danger-bg text-danger', 'Negado'],
  DISPENSADO: ['bg-muted text-muted-foreground', 'Dispensado'], SEM_VINCULO: ['bg-muted text-muted-foreground', 'Sem vínculo'], SUBSTITUIDO: ['bg-muted text-muted-foreground', 'Substituído'], INATIVO: ['bg-muted text-muted-foreground', 'Inativo'], ENCERRADO: ['bg-muted text-muted-foreground', 'Encerrado'], DESLIGADO: ['bg-muted text-muted-foreground', 'Desligado'], AFASTADO: ['bg-warning-bg text-warning', 'Afastado'],
}
export function StatusPill({ status, label }: { status: string; label?: string }) {
  const [cls, txt] = PILL[status] ?? ['bg-muted text-muted-foreground', status]
  return <span className={clsx('inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', cls)}>{label ?? txt}</span>
}

export function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const tone = pct >= 85 ? 'bg-success' : pct >= 70 ? 'bg-warning' : 'bg-danger'
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted-foreground" title={`Confiança ${pct}%`}>
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-brand-lighter" aria-hidden><span className={clsx('block h-full', tone)} style={{ width: pct + '%' }} /></span>{pct}%
    </span>
  )
}

/* ---------- Cards e indicadores ---------- */
export function KpiCard({ label, value, hint, icon, tone = 'default', to }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode; tone?: 'default' | 'warning' | 'danger' | 'success'; to?: string }) {
  const toneCls = { default: 'text-brand-darker', warning: 'text-warning', danger: 'text-danger', success: 'text-success' }[tone]
  const inner = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        {icon && <span className="icon-circle !h-8 !w-8">{icon}</span>}
      </div>
      <p className={clsx('mt-2 text-3xl font-bold tracking-tight', toneCls)}>{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </>
  )
  const cls = 'glass-panel block p-4 transition hover:shadow-lg'
  return to ? <a href={to} className={cls}>{inner}</a> : <div className={cls}>{inner}</div>
}

export function ComplianceRing({ pct, size = 84, label = true }: { pct: number; size?: number; label?: boolean }) {
  const r = 36, c = 2 * Math.PI * r
  const p = Math.max(0, Math.min(100, pct || 0))
  const tone = p >= 90 ? '#16a34a' : p >= 70 ? '#8a52d4' : '#dc2626'
  return (
    <svg width={size} height={size} viewBox="0 0 88 88" role="img" aria-label={`Conformidade ${p.toFixed(0)}%`}>
      <circle cx="44" cy="44" r={r} fill="none" stroke="rgba(138,82,212,.16)" strokeWidth="9" />
      <circle cx="44" cy="44" r={r} fill="none" stroke={tone} strokeWidth="9" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - p / 100)} transform="rotate(-90 44 44)" />
      {label && <text x="44" y="50" textAnchor="middle" className="fill-brand-darker" style={{ font: '700 20px var(--font-sans)' }}>{p.toFixed(0)}%</text>}
    </svg>
  )
}

export function Avatar({ nome, size = 'md' }: { nome?: string; size?: 'sm' | 'md' | 'lg' }) {
  const s = { sm: 'h-8 w-8 text-xs', md: 'h-10 w-10 text-sm', lg: 'h-14 w-14 text-lg' }[size]
  const ini = (nome ?? '?').split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase()
  return <span aria-hidden className={clsx('inline-grid shrink-0 place-items-center rounded-full font-bold text-white', s)} style={{ background: 'var(--gradient-brand)' }}>{ini}</span>
}

export function Skeleton({ className }: { className?: string }) { return <div className={clsx('skeleton h-4 w-full', className)} aria-hidden /> }
export function SkeletonRows({ n = 5 }: { n?: number }) {
  return <div role="status" aria-label="Carregando" className="space-y-3 p-2">{Array.from({ length: n }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
}

export function EmptyState({ icon, title, text, action }: { icon?: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="grid place-items-center gap-2 rounded-xl border border-dashed border-border-strong bg-surface/50 px-6 py-12 text-center">
      {icon && <span className="icon-circle !h-12 !w-12">{icon}</span>}
      <p className="font-display text-lg font-semibold text-brand-darker">{title}</p>
      {text && <p className="max-w-md text-sm text-muted-foreground">{text}</p>}
      {action}
    </div>
  )
}
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-danger/30 bg-danger-bg/60 p-4 text-sm text-danger">
      {(error as Error)?.message ?? 'Não foi possível carregar.'} {retry && <button className="ml-2 font-semibold underline" onClick={retry}>Tentar de novo</button>}
    </div>
  )
}

export function SectionHeading({ eyebrow, title, action, children, showTitle = false }: { eyebrow?: string; title: string; action?: ReactNode; children?: ReactNode; showTitle?: boolean }) {
  const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR')
  const showEyebrow = showTitle && eyebrow && !normalize(title).includes(normalize(eyebrow))
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {showEyebrow && <p className="text-xs font-semibold uppercase tracking-[.14em] text-muted-foreground">{eyebrow}</p>}
        <h1 className={showTitle ? 'font-display text-3xl font-bold text-brand-darker' : 'sr-only'}>{title}</h1>
        {children && <p className={clsx('max-w-2xl text-sm leading-relaxed text-muted-foreground', showTitle && 'mt-1')}>{children}</p>}
      </div>
      {action}
    </header>
  )
}
export const Card = ({ children, className, title, action }: { children: ReactNode; className?: string; title?: string; action?: ReactNode }) => (
  <section className={clsx('glass-panel p-5', className)}>
    {(title || action) && <div className="mb-3 flex items-center justify-between gap-2">{title && <h2 className="font-display text-lg font-semibold text-brand-darker">{title}</h2>}{action}</div>}
    {children}
  </section>
)

/* ---------- Tabela em vidro ---------- */
export interface Col<T> { key: string; header: string; render?: (row: T) => ReactNode; className?: string; align?: 'right' }
export function DataTable<T extends Record<string, any>>({ rows, cols, onRow, empty, loading, rowKey = 'id' }: { rows?: T[]; cols: Col<T>[]; onRow?: (r: T) => void; empty?: ReactNode; loading?: boolean; rowKey?: string }) {
  if (loading) return <SkeletonRows />
  if (!rows?.length) return <>{empty ?? <EmptyState title="Nada por aqui" />}</>
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface/70">
      <table className="w-full text-left text-sm">
        <thead><tr className="border-b border-border bg-brand-50/70">{cols.map((c) => <th key={c.key} scope="col" className={clsx('px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground', c.align === 'right' && 'text-right')}>{c.header}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r[rowKey] ?? i} onClick={() => onRow?.(r)} onKeyDown={(e) => e.key === 'Enter' && onRow?.(r)} tabIndex={onRow ? 0 : undefined}
              className={clsx('border-b border-border/60 last:border-0', onRow && 'cursor-pointer hover:bg-brand-50')}>
              {cols.map((c) => <td key={c.key} className={clsx('px-4 py-3', c.align === 'right' && 'text-right', c.className)}>{c.render ? c.render(r) : r[c.key] ?? '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
