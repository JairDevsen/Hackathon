import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { Archive, CheckCircle2, FileUp, RefreshCw, Trash2, UploadCloud } from 'lucide-react'
import { Button, Card, DataTable, EmptyState, ErrorState, Field, Select, SectionHeading, SkeletonRows, StatusPill, clsx } from '@/components/ui'
import { useGet } from '@/lib/query'
import { api, download, streamEvents, uploadBatch } from '@/lib/api'
import { fmtBytes, fmtDateTime, TIPOS_LOTE } from '@/lib/format'
import { useAuth } from '@/lib/auth'
import { ApagarLoteModal, type LoteParaApagar } from './ApagarLote'
import { ResultadoLote } from './ResultadoLote'

export function BatchList() {
  const nav = useNavigate()
  const { can } = useAuth()
  const [apagar, setApagar] = useState<LoteParaApagar | null>(null)
  const r = useGet<{ items: any[] }>('/batches', { limit: 50 }, { refetchInterval: 8000 })
  return (
    <div>
      <SectionHeading eyebrow="Lotes" title="Lotes enviados" action={<Button variant="primary" onClick={() => nav('/app/lotes/novo')}><UploadCloud className="h-4 w-4" />Enviar lote</Button>}>Acompanhe o processamento e abra um lote para conferir seus documentos.</SectionHeading>
      {r.error ? <ErrorState error={r.error} retry={r.refetch} /> : (
        <DataTable rows={r.data?.items} loading={r.isLoading} onRow={(b) => nav(`/app/lotes/${b.id}`)} empty={<EmptyState icon={<FileUp className="h-5 w-5" />} title="Nenhum lote ainda" text="Arraste um PDF, TIFF ou ZIP de imagens digitalizadas para começar." action={<Button variant="primary" onClick={() => nav('/app/lotes/novo')}>Enviar o primeiro lote</Button>} />}
          cols={[{ key: 'arquivo_original', header: 'Arquivo' }, { key: 'total_paginas', header: 'Páginas' }, { key: 'bytes', header: 'Tamanho', render: (b) => fmtBytes(b.bytes) },
            { key: 'status', header: 'Status', render: (b) => <StatusPill status={b.status} /> }, { key: 'para_revisao', header: 'Revisão', render: (b) => (b.para_revisao ? <span className="font-semibold text-warning">{b.para_revisao}</span> : '—') },
            { key: 'criado_em', header: 'Enviado em', render: (b) => fmtDateTime(b.criado_em) },
            ...(can('lotes:enviar') ? [{ key: 'acoes', header: '', render: (b: any) => <Button size="sm" variant="danger" aria-label={`Apagar o lote ${b.arquivo_original}`} onClick={(e) => { e.stopPropagation(); setApagar({ id: b.id, arquivo_original: b.arquivo_original, status: b.status, total_paginas: b.total_paginas, documentos: b.resumo?.documentos }) }}><Trash2 className="h-4 w-4" /></Button> }] : [])]} />
      )}
      {apagar && <ApagarLoteModal lote={apagar} open onClose={() => setApagar(null)} onDone={() => setApagar(null)} />}
    </div>
  )
}

export function BatchUpload() {
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const units = useGet<any[]>('/units')
  const [file, setFile] = useState<File | null>(null)
  const [unit, setUnit] = useState('')
  const [tipo, setTipo] = useState('MISTO')
  const [failAt, setFailAt] = useState(false)
  const [pct, setPct] = useState(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const send = async () => {
    if (!file) return
    setBusy(true); setErr('')
    try {
      const r = await uploadBatch(file, { unit_id: unit || undefined, tipo_lote: tipo, simular_falha_na_pagina: failAt ? 4 : undefined,
        dica_funcionario_id: sp.get('funcionario') || undefined, dica_tipo: sp.get('tipo') || undefined, substitui_documento_id: sp.get('substitui') || undefined }, setPct)
      nav(`/app/lotes/${r.id}`)
    } catch (e: any) {
      if (e.status === 409 && e.errors?.batch_id) { setErr('Este arquivo já foi enviado.'); setTimeout(() => nav(`/app/lotes/${e.errors.batch_id}`), 1200) } else setErr(e.message)
      setBusy(false)
    }
  }
  return (
    <div className="mx-auto max-w-3xl">
      <SectionHeading eyebrow="Enviar lote" title={sp.get('substitui') ? 'Enviar cópia legível' : 'Novo lote de documentos'}>Aceita PDF, TIFF multipágina, JPG, PNG, HEIC e ZIP de imagens, até 500 MB. O lote pré-cadastra funcionários identificados por CPF válido e nome. Se a conexão cair, o envio continua de onde parou.{sp.get('substitui') && ' A cópia anterior só será substituída após a nova ser aprovada.'}</SectionHeading>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files[0] ?? null) }}
        className={clsx('grid cursor-pointer place-items-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition', drag ? 'border-brand-default bg-brand-lighter' : 'border-border-strong bg-surface/60 hover:border-brand-light')}
        onClick={() => input.current?.click()} role="button" tabIndex={0} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()} aria-label="Selecionar arquivo do lote">
        <input ref={input} type="file" hidden accept=".pdf,.tif,.tiff,.jpg,.jpeg,.png,.heic,.zip" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <span className="icon-circle !h-14 !w-14"><UploadCloud className="h-6 w-6" /></span>
        {file ? <><b className="text-brand-darker">{file.name}</b><span className="text-sm text-muted-foreground">{fmtBytes(file.size)}</span></> : <><b className="text-brand-darker">Arraste o arquivo aqui</b><span className="text-sm text-muted-foreground">ou clique para escolher</span></>}
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Field label="Unidade">{(id) => <Select id={id} value={unit} onChange={(e) => setUnit(e.target.value)}><option value="">Todas / não informar</option>{units.data?.map((u) => <option key={u.id} value={u.id}>{u.nome}</option>)}</Select>}</Field>
        <Field label="Tipo de lote" hint="Só uma dica para a IA">{(id) => <Select id={id} value={tipo} onChange={(e) => setTipo(e.target.value)}>{TIPOS_LOTE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>}</Field>
      </div>
      {import.meta.env.DEV && <label className="mt-3 flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={failAt} onChange={(e) => setFailAt(e.target.checked)} />Simular queda na página 4 (demonstração de retomada — só em desenvolvimento)</label>}
      {busy && <div className="mt-4" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><div className="h-2 overflow-hidden rounded-full bg-brand-lighter"><div className="h-full bg-brand-default transition-all" style={{ width: pct + '%' }} /></div><p className="mt-1 text-xs text-muted-foreground">Enviando… {pct}%</p></div>}
      {err && <p role="alert" className="mt-3 text-sm text-danger">{err}</p>}
      <div className="mt-6 flex justify-end"><Button variant="primary" disabled={!file} loading={busy} onClick={send}>Enviar lote</Button></div>
    </div>
  )
}

const STEP_LABEL: Record<string, string> = { RECEBIDO: 'Recebido', FATIADO: 'Fatiado', ENVIADO_IA: 'Enviado à IA', FALHA: 'Falha', RETOMADO: 'Retomado', CONCLUIDO: 'Concluído', FALHOU: 'Falhou', RETOMADA_MANUAL: 'Retomada manual', CACHE_SHA256: 'Cache SHA-256' }

export function BatchDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const r = useGet<any>(`/batches/${id}`)
  const [live, setLive] = useState<any>(null)
  const [lgpd, setLgpd] = useState(false)
  const [zipBusy, setZipBusy] = useState(false)
  const [zipErr, setZipErr] = useState('')
  const [apagando, setApagando] = useState(false)
  const nav = useNavigate()
  const { can } = useAuth()
  useEffect(() => {
    const ac = new AbortController()
    streamEvents(`/batches/${id}/events`, (e) => { setLive(e.lote); if (['concluido', 'falhou', 'falha'].includes(e.evento)) qc.invalidateQueries({ queryKey: [`/batches/${id}`] }) }, ac.signal)
    return () => ac.abort()
  }, [id, qc])
  if (r.isLoading) return <SkeletonRows />
  if (r.error || !r.data) return <ErrorState error={r.error ?? new Error('Lote não encontrado')} />
  const b = r.data
  const total = live?.total_paginas ?? b.total_paginas
  const done = live?.paginas_ok ?? b.paginas.filter((p: any) => p.status === 'OK').length
  const status = live?.status ?? b.status
  const running = status === 'PROCESSANDO' || status === 'RECEBIDO'
  const sum = b.resumo ?? {}
  return (
    <div>
      <SectionHeading eyebrow="Lote" title={b.arquivo_original} showTitle action={status === 'FALHOU' ? <Button variant="primary" onClick={async () => { await api(`/batches/${id}/retry`, { method: 'POST' }); qc.invalidateQueries({ queryKey: [`/batches/${id}`] }) }}><RefreshCw className="h-4 w-4" />Retomar processamento</Button> : !!b.documentos?.length && (
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={lgpd} onChange={(e) => setLgpd(e.target.checked)} />Anonimizar (LGPD)</label>
          <Button variant="primary" loading={zipBusy} onClick={async () => { setZipBusy(true); setZipErr(''); try { await download(`/batches/${id}/export-zip`, { anonimizado: lgpd ? 'true' : 'false' }) } catch (e) { setZipErr((e as Error).message) } finally { setZipBusy(false) } }}><Archive className="h-4 w-4" />Baixar lote separado (.ZIP RH)</Button>
        </div>)}>
        {fmtBytes(b.bytes)} · enviado por {b.enviado_por ?? '—'} em {fmtDateTime(b.criado_em)} · SHA-256 {b.sha256?.slice(0, 12)}…</SectionHeading>
      {zipErr && <p role="alert" className="mb-3 rounded-lg bg-danger-bg p-2 text-sm text-danger">{zipErr}</p>}
      <Card className="mb-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><span className="flex items-center gap-3"><StatusPill status={status} />{can('lotes:enviar') && <Button size="sm" variant="danger" onClick={() => setApagando(true)}><Trash2 className="h-4 w-4" />Apagar lote</Button>}</span>
          <span className="text-sm text-muted-foreground" aria-live="polite">{total ? `${done} de ${total} páginas processadas` : 'Preparando páginas…'}{live?.paginas_falhas ? ` · ${live.paginas_falhas} com falha` : ''}</span></div>
        <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-brand-lighter" role="progressbar" aria-valuenow={done} aria-valuemax={total || 1}><div className={clsx('h-full transition-all', status === 'FALHOU' ? 'bg-danger' : 'bg-brand-default', running && 'animate-pulse')} style={{ width: `${total ? (100 * done) / total : 8}%` }} /></div>
        {b.erro && <p role="alert" className="mt-3 rounded-lg bg-danger-bg p-2 text-sm text-danger">{b.erro}</p>}
        {sum.documentos !== undefined && (
          <p className="mt-4 flex flex-wrap gap-3 text-sm"><span className="inline-flex items-center gap-1 font-semibold text-brand-darker"><CheckCircle2 className="h-4 w-4 text-success" />{sum.documentos} documentos</span>
            <span className="text-success">{sum.auto_aprovados} auto-aprovados</span><span className="text-brand">{sum.pre_cadastros ?? 0} funcionários pré-cadastrados</span><span className="text-warning">{sum.para_revisao} para revisão</span><span className="text-danger">{sum.classificacao_manual ?? 0} ilegíveis ou sem tipo</span><span className="text-muted-foreground">{sum.sem_vinculo} sem vínculo</span></p>
        )}
      </Card>
      {Number(sum.pre_cadastros) > 0 && <div role="status" className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-light bg-brand-lighter/50 p-3 text-sm"><span><b className="text-brand-darker">{sum.pre_cadastros} funcionário(s) pré-cadastrado(s) automaticamente</b> a partir dos documentos (nome e CPF lidos). Você não precisa cadastrar: só complete admissão, cargo e setor quando puder.</span><Link to="/app/funcionarios?pre=1" className="font-semibold text-brand underline">Ver pré-cadastros →</Link></div>}
      {Number(sum.fornecedores_pre_cadastrados) > 0 && <div role="status" className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-light bg-brand-lighter/50 p-3 text-sm"><span><b className="text-brand-darker">{sum.fornecedores_pre_cadastrados} fornecedor(es) ou terceirizada(s) identificado(s) pelo CNPJ</b> nos documentos. Os funcionários e os documentos de cada empresa ficam agrupados nela; informe o tipo e o contrato para o sistema cobrar os documentos certos.</span><Link to="/app/fornecedores?pre=1" className="font-semibold text-brand underline">Ver fornecedores →</Link></div>}
      {Number(sum.classificacao_manual) > 0 && <div role="status" className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-danger/50 bg-danger-bg/40 p-3 text-sm"><span><b className="text-danger">{sum.classificacao_manual} documento(s) ilegível(is) ou sem tipo identificado.</b> Classifique o tipo e preencha o formulário manualmente, ou envie uma cópia legível.</span><Link to="/app/revisao?motivo=PAGINA_ILEGIVEL" className="font-semibold text-brand underline">Classificar agora →</Link></div>}
      <div className="space-y-5">
        <div className="min-w-0"><ResultadoLote docs={b.documentos ?? []} running={running} onChanged={() => qc.invalidateQueries({ queryKey: [`/batches/${id}`] })} />
          {!!sum.para_revisao && <div className="mt-3 text-right"><Link to="/app/revisao" className="text-sm font-semibold text-brand underline">Ir para a fila de revisão →</Link></div>}</div>
        <Card title="Linha do tempo">
          <ol className="relative ml-3 space-y-3 border-l-2 border-brand-lighter pl-5">
            {b.linha_tempo.map((e: any, i: number) => (
              <li key={i}><span className={clsx('absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full', ['FALHA', 'FALHOU'].includes(e.tipo) ? 'bg-danger' : e.tipo === 'RETOMADO' || e.tipo === 'RETOMADA_MANUAL' ? 'bg-warning' : 'bg-brand-default')} aria-hidden />
                <p className="text-sm font-semibold text-brand-darker">{STEP_LABEL[e.tipo] ?? e.tipo}</p><p className="text-xs text-muted-foreground">{e.mensagem}</p><p className="text-[11px] text-muted-foreground">{fmtDateTime(e.quando)}</p></li>
            ))}
          </ol>
        </Card>
      </div>
      <ApagarLoteModal lote={{ id: b.id, arquivo_original: b.arquivo_original, status, total_paginas: total, documentos: b.documentos?.length, revisados: (b.documentos ?? []).filter((d: any) => d.status === 'REVISADO').length }} open={apagando} onClose={() => setApagando(false)} onDone={() => { setApagando(false); nav('/app/lotes') }} />
    </div>
  )
}
