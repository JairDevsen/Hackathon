import { useState } from 'react'
import { Cpu, Coins, Database, Layers, ScanText, Sparkles } from 'lucide-react'
import { Card, DataTable, Field, Input, KpiCard, SectionHeading } from '@/components/ui'
import { useGet } from '@/lib/query'
import { PREMISSAS_PADRAO, VOLUME_PADRAO, simular, type Premissas } from '@/lib/finops'

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: n < 10 ? 2 : 0 })
const num = (n: number) => Math.round(n).toLocaleString('pt-BR')

/** Painel executivo: custo mensal do funil de 4 camadas vs. 100% visão, com slider de volume e premissas editáveis. */
export function FinopsPage() {
  const [volume, setVolume] = useState(VOLUME_PADRAO)
  const [p, setP] = useState<Premissas>(PREMISSAS_PADRAO)
  const r = simular(volume, p)
  const real = useGet<any[]>('/metrics/finops')
  const camadas = [
    { n: 0, icon: Database, titulo: 'Deduplicação SHA-256 + validade vigente', pct: 30, docs: r.docs.c0, custo: r.custo.c0, nota: 'Mesma página já processada: resultado reaproveitado, 0 tokens', cor: 'bg-success' },
    { n: 1, icon: ScanText, titulo: 'Texto nativo do PDF + regex local + poda de páginas inúteis', pct: 45, docs: r.docs.c1, custo: r.custo.c1, nota: 'Sem chamada de IA', cor: 'bg-success' },
    { n: 2, icon: Layers, titulo: 'Context caching + Gemini 2.5 Flash-Lite sobre o texto extraído', pct: 15, docs: r.docs.c2, custo: r.custo.c2, nota: '≈ US$ 0,01 por 1 mi de tokens (premissa do cenário)', cor: 'bg-brand-light' },
    { n: 3, icon: Cpu, titulo: 'Gemini 2.5 Flash Vision, imagem 1024 px em WebP, só manuscritos/AR/exames', pct: 10, docs: r.docs.c3, custo: r.custo.c3, nota: '258 tokens/página (premissa do cenário)', cor: 'bg-brand' },
  ]
  return (
    <div>
      <SectionHeading eyebrow="Escala 950k & FinOps" title="Quanto custa ler 950 mil vidas?">Simulação do custo mensal de IA para o volume de documentos de uma grande carteira de terceirizados: ler tudo como imagem versus o funil de 4 camadas, que só chama a visão quando o texto nativo não basta.</SectionHeading>

      <Card className="mb-5">
        <Field label={`Volume: ${num(volume)} documentos/mês`} hint="De 100 mil a 5 milhões. Padrão: 1,5 mi para 950 mil terceirizados.">
          {(id) => <input id={id} type="range" min={100_000} max={5_000_000} step={50_000} value={volume} onChange={(e) => setVolume(Number(e.target.value))} className="w-full accent-brand" aria-valuetext={`${num(volume)} documentos por mês`} />}
        </Field>
      </Card>

      <div className="mb-5 grid gap-4 md:grid-cols-3">
        <KpiCard label="Abordagem ingênua (100% visão)" value={usd(r.ingenuo)} hint="por mês" icon={<Coins className="h-4 w-4" />} tone="danger" />
        <KpiCard label="Funil de 4 camadas Citadel" value={usd(r.funil)} hint="por mês" icon={<Sparkles className="h-4 w-4" />} tone="success" />
        <KpiCard label="Economia" value={`${r.economiaPct.toFixed(1).replace('.', ',')}%`} hint={`${usd(r.ingenuo - r.funil)} a menos por mês`} />
      </div>

      <Card title="As 4 camadas" className="mb-5">
        <div className="mb-4 flex h-3 overflow-hidden rounded-full" role="img" aria-label="Distribuição dos documentos por camada: 30%, 45%, 15% e 10%">
          {camadas.map((c) => <span key={c.n} className={c.cor} style={{ width: c.pct + '%' }} title={`Camada ${c.n}: ${c.pct}%`} />)}
        </div>
        <ol className="space-y-3">
          {camadas.map((c) => (
            <li key={c.n} className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface/70 p-3">
              <span className="icon-circle"><c.icon className="h-4 w-4" /></span>
              <div className="min-w-0 flex-1"><p className="font-semibold text-brand-darker">Camada {c.n}: {c.titulo}</p><p className="text-xs text-muted-foreground">{c.nota}</p></div>
              <div className="text-right text-sm"><b className="text-brand-darker">{c.pct}% retido</b><br /><span className="text-muted-foreground">{num(c.docs)} docs · {c.custo === 0 ? '$0' : usd(c.custo)}</span></div>
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Premissas do cenário (editáveis)">
          <p className="mb-3 text-sm text-muted-foreground">Valores em US$ por documento. São premissas para a simulação, <b>não uma cotação</b>: confira na tabela de preços vigente do provedor antes de usar em proposta.</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {([['custoIngenuoPorDoc', '100% visão'], ['custoCamada2PorDoc', 'Camada 2'], ['custoCamada3PorDoc', 'Camada 3']] as const).map(([k, l]) => (
              <Field key={k} label={l}>{(id) => <Input id={id} type="number" step="0.000001" min={0} value={p[k]} onChange={(e) => setP({ ...p, [k]: Number(e.target.value) })} />}</Field>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">Nota: na documentação do Gemini que conheço, 258 tokens correspondem a imagens de até 384 px; imagens maiores são divididas em blocos de 768 px (≈ 258 tokens cada). Uma página reduzida a 1024 px pode, portanto, consumir mais de 258 tokens: use o consumo real medido (ao lado) para calibrar.</p>
        </Card>
        <Card title="Consumo real da sua empresa">
          <DataTable rows={real.data?.map((x) => ({ id: x.camada, ...x }))} loading={real.isLoading} empty={<p className="text-sm text-muted-foreground">Processe um lote para ver o consumo por camada.</p>}
            cols={[{ key: 'camada', header: 'Camada' }, { key: 'documentos', header: 'Docs' }, { key: 'tokens_consumidos', header: 'Tokens gastos', render: (x) => num(x.tokens_consumidos) }, { key: 'tokens_economizados', header: 'Economizados', render: (x) => num(x.tokens_economizados) }, { key: 'economia_media_pct', header: 'Economia', render: (x) => `${x.economia_media_pct}%` }]} />
        </Card>
      </div>
    </div>
  )
}
