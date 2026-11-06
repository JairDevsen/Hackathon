import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Cpu, Download, EyeOff, FileJson, FolderTree, ShieldAlert, ShieldCheck, XCircle } from 'lucide-react'
import { DocumentViewer } from '@/components/DocumentViewer'
import { Button, Card, ConfidenceBar, ErrorState, SectionHeading, SkeletonRows, StatusPill } from '@/components/ui'
import { useGet } from '@/lib/query'
import { download } from '@/lib/api'
import { competenciaLabel, fmtDate } from '@/lib/format'
import { MotivoChips } from './Dossie'

function exportJson(d: any) {
  const limpo = { ...d }
  delete limpo.paginas_urls // URLs assinadas expiram: não entram no arquivo
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([JSON.stringify(limpo, null, 2)], { type: 'application/json' }))
  a.download = `${(d.nome_arquivo ?? d.id).replace(/\.pdf$/, '')}.json`
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 5000)
}

function Row({ k, v }: { k: string; v?: string | null }) {
  return <div><dt className="text-xs uppercase text-muted-foreground">{k}</dt><dd className="break-all text-sm font-medium">{v || '—'}</dd></div>
}

/** Indexação automática: empresa, funcionário e destino do arquivo na árvore de pastas do RH. */
function IndexacaoCard({ d }: { d: any }) {
  const cnpj = String(d.empresa_cnpj ?? '').replace(/\D/g, '')
  const cnpjFmt = cnpj.length === 14 ? cnpj.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5') : null
  return (
    <Card title="Indexação automática & destino RH" action={<FolderTree className="h-4 w-4 text-brand-default" aria-hidden />}>
      <dl className="grid gap-3 sm:grid-cols-2">
        <Row k="Empresa" v={d.empresa_nome} /><Row k="CNPJ" v={cnpjFmt} />
        <Row k="Funcionário" v={d.funcionario_nome ?? d.nome_extraido} /><Row k="CPF" v={d.funcionario_cpf} />
        <div className="sm:col-span-2"><Row k="Pasta de destino" v={d.pasta_destino && d.pasta_destino + '/'} /></div>
        <div className="sm:col-span-2"><Row k="Nome do arquivo" v={d.nome_arquivo} /></div>
      </dl>
    </Card>
  )
}

const CK: Record<string, { icon: any; cls: string; label: string }> = {
  OK: { icon: CheckCircle2, cls: 'text-success', label: 'OK' }, FALHA: { icon: XCircle, cls: 'text-danger', label: 'Falha' },
  ALERTA: { icon: AlertTriangle, cls: 'text-warning', label: 'Alerta' }, REVISAO_HUMANA: { icon: AlertTriangle, cls: 'text-warning', label: 'Revisão humana' },
}

/** Status de mobilização + checklist (validade, assinatura, NR-07/NR-06...). Verde = APTO, vermelho = BLOQUEADO, amarelo = demais. */
function MobilizacaoCard({ d }: { d: any }) {
  const st: string = d.status_mobilizacao ?? ''
  const tone = st.includes('APTO') ? 'bg-success-bg text-success' : st.includes('BLOQUEADO') ? 'bg-danger-bg text-danger' : 'bg-warning-bg text-warning'
  return (
    <Card title="Bernhoeft GRT — Status de Mobilização" action={<ShieldCheck className="h-4 w-4 text-brand-default" aria-hidden />}>
      <p className={`mb-3 inline-block rounded-full px-3 py-1 text-xs font-bold ${tone}`} role="status">{st || '—'}</p>
      {d.checklist?.length ? (
        <ul className="space-y-2">
          {d.checklist.map((c: any, i: number) => {
            const m = CK[c.status] ?? CK.ALERTA
            return <li key={i} className="flex gap-2 text-sm"><m.icon className={`mt-0.5 h-4 w-4 shrink-0 ${m.cls}`} aria-label={m.label} /><span><b className="text-brand-darker">{c.regra}</b><span className="block text-xs text-muted-foreground">{c.detalhe}</span></span></li>
          })}
        </ul>
      ) : <p className="text-sm text-muted-foreground">Sem itens de checklist para este tipo de documento.</p>}
    </Card>
  )
}

/** Telemetria FinOps: camada que resolveu o documento, hash e economia de tokens. */
function FinopsBar({ f }: { f?: any }) {
  if (!f?.camada_roteamento) return null
  const eco = Number(f.economia_estimada_pct ?? 0)
  return (
    <div className="glass-panel flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-xs" aria-label="Telemetria FinOps">
      <span className="flex items-center gap-1.5 font-semibold text-brand-darker"><Cpu className="h-4 w-4 text-brand-default" aria-hidden />{f.camada_roteamento}</span>
      <span className="text-muted-foreground">SHA-256 <code className="rounded bg-muted px-1">{String(f.sha256_hash ?? '').slice(0, 12) || '—'}</code></span>
      <span className="text-muted-foreground">tokens: <b className="text-brand-darker">{f.tokens_consumidos ?? 0}</b> gastos · <b className="text-success">{f.tokens_economizados ?? 0}</b> economizados</span>
      <span className="ml-auto rounded-full bg-success-bg px-2 py-0.5 font-bold text-success">{eco.toFixed(1).replace('.', ',')}% de economia</span>
    </div>
  )
}

export function DocumentPage() {
  const { id } = useParams()
  const [sp] = useSearchParams()
  const q = sp.get('q') ?? ''
  const nav = useNavigate()
  const doc = useGet<any>(`/documents/${id}`)
  const hl = useGet<any[]>(q ? `/documents/${id}/highlights` : null, { q })
  if (doc.isLoading) return <SkeletonRows />
  if (doc.error) return <ErrorState error={doc.error} retry={doc.refetch} />
  const d = doc.data
  return (
    <div>
      <SectionHeading eyebrow={d.tipo_nome} title={d.titulo || d.tipo_nome} showTitle action={
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => download(`/documents/${id}/download`, { formato: 'original' })}><Download className="h-4 w-4" />Original</Button>
          <Button onClick={() => download(`/documents/${id}/download`, { formato: 'pesquisavel' })}><Download className="h-4 w-4" />PDF pesquisável</Button>
          <Button variant="soft" onClick={() => download(`/documents/${id}/download`, { formato: 'anonimizado' })}><EyeOff className="h-4 w-4" />Cópia anonimizada</Button>
          <Button onClick={() => exportJson(d)}><FileJson className="h-4 w-4" />Exportar JSON</Button>
        </div>} />
      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <DocumentViewer pages={d.paginas_urls} highlights={hl.data} />
        <div className="space-y-4">
          <IndexacaoCard d={d} />
          <MobilizacaoCard d={d} />
          <FinopsBar f={d.finops} />
          <Card title="Resumo">
            {d.origem === 'MANUAL' && <p className="mb-3 rounded-lg bg-warning-bg p-2 text-sm text-warning">Dados transcritos manualmente de um original ilegível. Uma cópia legível ainda é necessária para comprovação documental.</p>}
            <div className="flex flex-wrap items-center gap-2"><StatusPill status={d.status} /><ConfidenceBar value={Number(d.confianca)} /><MotivoChips motivos={d.motivos_revisao} /></div>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-xs uppercase text-muted-foreground">Funcionário</dt><dd>{d.funcionario_nome ? <button className="font-medium text-brand underline" onClick={() => nav(`/app/funcionarios/${d.employee_id}`)}>{d.funcionario_nome}</button> : 'Sem vínculo'}</dd></div>
              <div><dt className="text-xs uppercase text-muted-foreground">CPF</dt><dd>{d.funcionario_cpf ?? '—'}</dd></div>
              <div><dt className="text-xs uppercase text-muted-foreground">Competência</dt><dd>{competenciaLabel(d.competencia)}</dd></div>
              <div><dt className="text-xs uppercase text-muted-foreground">Data / validade</dt><dd>{fmtDate(d.data_documento)} / {fmtDate(d.validade_ate)}</dd></div>
            </dl>
          </Card>
          {(!!d.alertas?.length || !!d.nao_conformidades?.length) && (
            <Card title="Alertas e não conformidades"><ul className="space-y-2">
              {d.alertas.map((a: any, i: number) => <li key={i} className={`flex gap-2 rounded-lg p-2 text-sm ${a.severidade === 'erro' ? 'bg-danger-bg text-danger' : 'bg-warning-bg text-warning'}`}><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />{a.mensagem}</li>)}
            </ul></Card>
          )}
          <Card title="Campos extraídos"><dl className="space-y-2 text-sm">
            {Object.entries(d.campos ?? {}).filter(([, v]) => v).map(([k, v]) => <div key={k} className="flex justify-between gap-3 border-b border-border/60 pb-1"><dt className="text-muted-foreground">{k.replaceAll('_', ' ')}</dt><dd className="text-right font-medium">{String(v)}</dd></div>)}
          </dl></Card>
          <Card title="Texto lido (OCR)"><pre className="max-h-56 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">{d.texto_ocr}</pre></Card>
        </div>
      </div>
    </div>
  )
}
