import { Tooltip } from 'recharts'

/** Escala sequencial da marca (volume/intensidade); status usa só as cores semânticas; um destaque em `brand` por gráfico. */
export const SEQ = ['#d9c7f8', '#b794f6', '#9a63e6', '#7c3fd0', '#6020b8', '#4b1a96']
export const C = { brand: '#8a52d4', light: '#c8aef0', mid: '#a67be8', success: '#22c55e', warning: '#f59e0b', danger: '#ef4444', grid: 'var(--color-border)', text: 'var(--color-muted-foreground)' }
export const axis = { tick: { fill: C.text, fontSize: 12 }, axisLine: { stroke: C.grid }, tickLine: false as const }

function Tip({ active, payload, label, fmt }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-dropdown px-3 py-2 text-xs">
      <p className="mb-1 font-semibold text-brand-darker">{label}</p>
      {payload.map((p: any) => <p key={p.dataKey} style={{ color: p.color ?? p.fill }}>{p.name}: <b>{fmt ? fmt(p.value) : p.value}</b></p>)}
    </div>
  )
}
export const ChartTip = ({ fmt }: { fmt?: (v: number) => string }) => <Tooltip cursor={{ fill: 'rgba(138,82,212,.12)' }} content={<Tip fmt={fmt} />} />

import { Area, AreaChart, Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'

/** Minigráfico de tendência para os cartões (sem eixos). */
export function Spark({ data, color = '#9a63e6' }: { data: number[]; color?: string }) {
  if (data.length < 2) return null
  const rows = data.map((v, i) => ({ i, v }))
  const id = `sp${color.replace('#', '')}`
  return (
    <div className="h-10 w-24" aria-hidden><ResponsiveContainer><AreaChart data={rows} margin={{ top: 4, bottom: 0, left: 0, right: 0 }}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".5" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient></defs>
      <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#${id})`} isAnimationActive={false} />
    </AreaChart></ResponsiveContainer></div>
  )
}

/** Rosca com total no centro e legenda ao lado. */
export function Donut({ data, total, label }: { data: { nome: string; n: number }[]; total: number; label: string }) {
  const cores = [...SEQ].reverse()
  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="relative h-44 w-44 shrink-0" role="img" aria-label={`${label}: ${total}`}>
        <ResponsiveContainer><PieChart><Pie data={data} dataKey="n" nameKey="nome" innerRadius="66%" outerRadius="100%" paddingAngle={2} stroke="none" isAnimationActive={false}>
          {data.map((_, i) => <Cell key={i} fill={cores[i % cores.length]} />)}</Pie></PieChart></ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center"><div><p className="text-3xl font-bold text-brand-darker">{total.toLocaleString('pt-BR')}</p><p className="text-xs text-muted-foreground">{label}</p></div></div>
      </div>
      <ul className="min-w-44 flex-1 space-y-2 text-sm">
        {data.map((d, i) => (
          <li key={d.nome} className="flex items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: cores[i % cores.length] }} aria-hidden />
            <span className="min-w-0 flex-1 truncate text-foreground" title={d.nome}>{d.nome}</span><b className="text-brand-darker">{total ? Math.round((100 * d.n) / total) : 0}%</b></li>
        ))}
      </ul>
    </div>
  )
}

/** Rótulo de eixo que corta nomes longos (com tooltip nativo) em vez de sobrepor. */
export function YTick({ x, y, payload, max = 24 }: any) {
  const t: string = String(payload?.value ?? '')
  return (
    <g transform={`translate(${x},${y})`}><title>{t}</title>
      <text x={-6} y={0} dy={4} textAnchor="end" fill="var(--color-muted-foreground)" fontSize={12}>{t.length > max ? t.slice(0, max - 1) + '…' : t}</text></g>
  )
}
