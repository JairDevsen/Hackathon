import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Trash2 } from 'lucide-react'
import { Button, Field, Modal, Textarea } from '@/components/ui'
import { api } from '@/lib/api'

export interface LoteParaApagar { id: string; arquivo_original: string; status: string; total_paginas?: number; documentos?: number; revisados?: number }

/** Confirmação para apagar um lote enviado: explica o que sai, o que fica e exige motivo e confirmação explícita. */
export function ApagarLoteModal({ lote, open, onClose, onDone }: { lote: LoteParaApagar; open: boolean; onClose: () => void; onDone: () => void }) {
  const qc = useQueryClient()
  const [motivo, setMotivo] = useState('')
  const [entendo, setEntendo] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const emAndamento = lote.status === 'RECEBIDO' || lote.status === 'PROCESSANDO'
  const fechar = () => { setMotivo(''); setEntendo(false); setErr(''); onClose() }
  const apagar = async () => {
    setBusy(true); setErr('')
    try {
      await api(`/batches/${lote.id}`, { method: 'DELETE', body: { confirmar: true, motivo } })
      for (const k of ['/batches', '/documents', '/employees', '/suppliers', '/risks', '/compliance', '/metrics/overview', '/review/queue']) qc.invalidateQueries({ queryKey: [k] })
      setMotivo(''); setEntendo(false); onDone()
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={fechar} eyebrow="Lote" title="Apagar este lote?"
      footer={<><Button onClick={fechar}>Cancelar</Button><Button variant="danger" loading={busy} disabled={emAndamento || !entendo || motivo.trim().length < 5} onClick={apagar}><Trash2 className="h-4 w-4" />Apagar lote definitivamente</Button></>}>
      <p className="rounded-lg bg-danger-bg p-3 text-sm text-danger"><AlertTriangle className="mr-1 inline h-4 w-4" aria-hidden /><b>{lote.arquivo_original}</b>: esta ação é definitiva e não pode ser desfeita.</p>
      {emAndamento
        ? <p role="status" className="text-sm text-warning">Este lote ainda está sendo processado. Aguarde terminar (ou falhar) para poder apagá-lo.</p>
        : <>
          <div className="text-sm">
            <p className="mb-1 font-semibold text-brand-darker">O que será apagado</p>
            <ul className="ml-5 list-disc space-y-1 text-muted-foreground">
              <li>O arquivo original e as imagens das páginas{lote.total_paginas ? ` (${lote.total_paginas} páginas)` : ''}.</li>
              <li>Todos os documentos extraídos dele{lote.documentos !== undefined ? ` (${lote.documentos})` : ''}{lote.revisados ? `, inclusive ${lote.revisados} já revisado(s) por uma pessoa` : ''}, com campos, alertas e histórico de revisão.</li>
              <li>Os indicadores de risco e os itens de conformidade ligados a esses documentos: pendências e riscos são recalculados.</li>
            </ul>
            <p className="mb-1 mt-3 font-semibold text-brand-darker">O que continua</p>
            <ul className="ml-5 list-disc space-y-1 text-muted-foreground">
              <li>Funcionários e fornecedores criados a partir do lote (podem ter outros documentos).</li>
              <li>O consumo de páginas do mês já contabilizado.</li>
              <li>O registro na auditoria: quem apagou, quando e o motivo.</li>
            </ul>
            <p className="mt-3 text-muted-foreground">O mesmo arquivo poderá ser enviado novamente depois. Documentos trabalhistas podem ter prazo legal de guarda: confirme com o jurídico antes de apagar.</p>
          </div>
          <Field label="Motivo da exclusão *" hint="Fica registrado na auditoria (mínimo de 5 caracteres).">{(id) => <Textarea id={id} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: arquivo enviado por engano" />}</Field>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={entendo} onChange={(e) => setEntendo(e.target.checked)} />Entendo que o lote e seus documentos serão apagados e que isso não pode ser desfeito.</label>
        </>}
      {err && <p role="alert" className="rounded-lg bg-danger-bg p-2 text-sm text-danger">{err}</p>}
    </Modal>
  )
}
