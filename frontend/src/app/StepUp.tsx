import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api, setStepUpHandler } from '@/lib/api'
import { Button, Field, Input, Modal } from '@/components/ui'

/** Reautenticação (step-up): ações sensíveis pedem um novo código por e-mail; o token vale 5 minutos. */
export function StepUpProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const ticket = useRef('')
  const pending = useRef<{ ok: (t: string) => void; fail: (e: Error) => void } | null>(null)

  useEffect(() => {
    setStepUpHandler(() => {
      const p = new Promise<string>((ok, fail) => { pending.current = { ok, fail } })
      setCode(''); setErr(''); setOpen(true)
      api<{ ticket: string }>('/auth/step-up', { method: 'POST' }).then((r) => { ticket.current = r.ticket }).catch((e) => setErr((e as Error).message))
      return p
    })
  }, [])

  const close = () => { setOpen(false); pending.current?.fail(new Error('Confirmação cancelada')); pending.current = null }
  const submit = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api<{ token: string }>('/auth/step-up', { method: 'POST', body: { ticket: ticket.current, code } })
      setOpen(false); pending.current?.ok(r.token); pending.current = null
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <>
      {children}
      <Modal open={open} onClose={close} eyebrow="Ação sensível" title="Confirme sua identidade"
        footer={<><Button onClick={close}>Cancelar</Button><Button variant="primary" loading={busy} disabled={code.length !== 6} onClick={submit}>Confirmar</Button></>}>
        <p className="text-sm text-muted-foreground">Enviamos um novo código de 6 dígitos para o seu e-mail corporativo.</p>
        <Field label="Código" error={err}>{(id, bad) => <Input id={id} aria-invalid={bad} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} onKeyDown={(e) => e.key === 'Enter' && code.length === 6 && submit()} autoFocus />}</Field>
      </Modal>
    </>
  )
}
