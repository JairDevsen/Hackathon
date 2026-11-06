import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button, Field, Input } from '@/components/ui'
import { AuthLayout } from './AuthLayout'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'

const schema = z.object({ email: z.string().email('Informe um e-mail válido'), senha: z.string().min(1, 'Informe a senha') })

export function Login() {
  const { user, setSession } = useAuth()
  const nav = useNavigate()
  const [ticket, setTicket] = useState<{ t: string; email: string; resendAt: number } | null>(null)
  const [code, setCode] = useState('')
  const [trust, setTrust] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(Date.now())
  const { register, handleSubmit, formState: { errors } } = useForm({ resolver: zodResolver(schema) })

  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(i) }, [])
  if (user) return <Navigate to="/app" replace />

  const login = handleSubmit(async (v) => {
    setBusy(true); setErr('')
    try {
      const r = await api<any>('/auth/login', { method: 'POST', body: { ...v, confiar_dispositivo: trust } })
      if (r.mfa_required) setTicket({ t: r.mfa_ticket, email: r.email_mascarado, resendAt: new Date(r.reenvio_em).getTime() })
      else { await setSession(r.access_token); nav('/app') }
    } catch (e) { setErr((e as ApiError).message) } finally { setBusy(false) }
  })
  const verify = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api<any>('/auth/mfa/verify', { method: 'POST', body: { mfa_ticket: ticket!.t, code, confiar_dispositivo: trust } })
      await setSession(r.access_token); nav('/app')
    } catch (e) { setErr((e as ApiError).message) } finally { setBusy(false) }
  }
  const resend = async () => {
    try { const r = await api<any>('/auth/mfa/resend', { method: 'POST', body: { mfa_ticket: ticket!.t } }); setTicket({ ...ticket!, resendAt: new Date(r.reenvio_em).getTime() }); setErr('') } catch (e) { setErr((e as ApiError).message) }
  }
  const wait = ticket ? Math.max(0, Math.ceil((ticket.resendAt - now) / 1000)) : 0

  return (
    <AuthLayout>
      <h1 className="font-display text-3xl font-bold text-brand-darker">{ticket ? 'Verifique seu e-mail' : 'Entrar'}</h1>
      <p className="mb-6 mt-2 text-muted-foreground">{ticket ? `Enviamos um código de 6 dígitos para ${ticket.email}. Ele vale por 10 minutos.` : 'Acesse com seu e-mail corporativo.'}</p>
      {!ticket ? (
        <form onSubmit={login} className="space-y-4" noValidate>
          <Field label="E-mail" error={errors.email?.message as string}>{(id, bad) => <Input id={id} type="email" autoComplete="username" placeholder="voce@empresa.com.br" aria-invalid={bad} {...register('email')} />}</Field>
          <Field label="Senha" error={errors.senha?.message as string}>{(id, bad) => <Input id={id} type="password" autoComplete="current-password" aria-invalid={bad} {...register('senha')} />}</Field>
          <label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" className="accent-brand" checked={trust} onChange={(e) => setTrust(e.target.checked)} />Confiar neste dispositivo por 30 dias</label>
          {err && <p role="alert" className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">{err}</p>}
          <Button type="submit" variant="primary" loading={busy} className="w-full">Continuar</Button>
        </form>
      ) : (
        <div className="space-y-4">
          <Field label="Código de verificação" error={err}>{(id, bad) => <Input id={id} inputMode="numeric" autoComplete="one-time-code" maxLength={6} aria-invalid={bad} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} onKeyDown={(e) => e.key === 'Enter' && code.length === 6 && verify()} autoFocus className="text-center text-xl tracking-[.5em]" />}</Field>
          <Button variant="primary" className="w-full" loading={busy} disabled={code.length !== 6} onClick={verify}>Entrar</Button>
          <button onClick={resend} disabled={wait > 0} className="w-full text-sm font-medium text-brand underline disabled:no-underline disabled:opacity-60">{wait > 0 ? `Reenviar código em ${wait}s` : 'Reenviar código'}</button>
        </div>
      )}
    </AuthLayout>
  )
}

export function Invite() {
  const token = new URLSearchParams(location.search).get('token') ?? ''
  const nav = useNavigate()
  const [s1, setS1] = useState('')
  const [s2, setS2] = useState('')
  const [err, setErr] = useState('')
  const [ok, setOk] = useState(false)
  const submit = async () => {
    if (s1 !== s2) return setErr('As senhas não conferem')
    try { await api('/auth/invite/accept', { method: 'POST', body: { token, senha: s1 } }); setOk(true) } catch (e) { setErr((e as Error).message) }
  }
  return (
    <AuthLayout>
      <h1 className="font-display text-3xl font-bold text-brand-darker">{ok ? 'Senha definida' : 'Defina sua senha'}</h1>
      {ok ? <><p className="mb-6 mt-2 text-muted-foreground">Pronto. Agora é só entrar com seu e-mail corporativo.</p><Button variant="primary" className="w-full" onClick={() => nav('/entrar')}>Ir para o login</Button></> : (
        <div className="mt-2 space-y-4">
          <p className="text-muted-foreground">Use pelo menos 12 caracteres.</p>
          <Field label="Nova senha">{(id) => <Input id={id} type="password" autoComplete="new-password" value={s1} onChange={(e) => setS1(e.target.value)} />}</Field>
          <Field label="Repita a senha" error={err}>{(id, bad) => <Input id={id} type="password" aria-invalid={bad} autoComplete="new-password" value={s2} onChange={(e) => setS2(e.target.value)} />}</Field>
          <Button variant="primary" className="w-full" disabled={s1.length < 12} onClick={submit}>Salvar senha</Button>
        </div>
      )}
    </AuthLayout>
  )
}
