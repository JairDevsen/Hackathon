// Cliente da API /api/v1. O access token vive SÓ em memória (nunca em localStorage); o refresh é cookie HttpOnly.
declare global { interface Window { __CONFIG__?: { API_URL?: string } } }

const BASE = (window.__CONFIG__?.API_URL ?? '') + '/api/v1'

export class ApiError extends Error {
  status: number
  code?: string
  errors?: Record<string, unknown>
  constructor(status: number, detail: string, code?: string, errors?: Record<string, unknown>) {
    super(detail)
    this.status = status
    this.code = code
    this.errors = errors
  }
}

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null
let onSessionLost: (() => void) | null = null
let stepUpHandler: (() => Promise<string>) | null = null
let tenantOverride: string | null = null

export const setSessionLostHandler = (fn: () => void) => { onSessionLost = fn }
export const setStepUpHandler = (fn: () => Promise<string>) => { stepUpHandler = fn }
export const setAccessToken = (t: string | null) => { accessToken = t }
export const setTenantOverride = (t: string | null) => { tenantOverride = t } // acesso de suporte (Master)

function cookie(name: string) {
  return document.cookie.split('; ').find((c) => c.startsWith(name + '='))?.split('=')[1] ?? ''
}

// Single-flight: várias requisições 401 simultâneas compartilham UM refresh (o refresh token é de uso único).
export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const r = await fetch(BASE + '/auth/refresh', { method: 'POST', credentials: 'include', headers: { 'X-CSRF-Token': cookie('citadel_csrf') } })
        if (!r.ok) return false
        accessToken = (await r.json()).access_token
        return true
      } catch { return false } finally { setTimeout(() => { refreshing = null }, 0) }
    })()
  }
  return refreshing
}

async function parseError(r: Response): Promise<ApiError> {
  let body: any = {}
  try { body = await r.json() } catch { /* corpo vazio */ }
  return new ApiError(r.status, body.detail ?? body.title ?? 'Erro inesperado', body.code, body.errors)
}

export interface Opts { method?: string; body?: unknown; query?: Record<string, string | number | undefined | null>; stepUp?: boolean; raw?: boolean; headers?: Record<string, string>; signal?: AbortSignal }

export async function api<T = any>(path: string, o: Opts = {}, retried = false, stepToken?: string): Promise<T> {
  const url = new URL(BASE + path, window.location.origin)
  Object.entries(o.query ?? {}).forEach(([k, v]) => v !== undefined && v !== null && v !== '' && url.searchParams.set(k, String(v)))
  const headers: Record<string, string> = { ...(o.headers ?? {}) }
  if (accessToken) headers.Authorization = 'Bearer ' + accessToken
  if (tenantOverride) headers['X-Tenant-ID'] = tenantOverride
  if (stepToken) headers['X-Step-Up-Token'] = stepToken
  let body: BodyInit | undefined
  if (o.body instanceof FormData || o.body instanceof Blob) body = o.body as BodyInit
  else if (o.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(o.body) }
  const r = await fetch(url, { method: o.method ?? 'GET', headers, body, credentials: 'include', signal: o.signal })
  if (r.status === 401) {
    if (r.headers.get('X-Step-Up-Required') === 'true' && stepUpHandler && !stepToken) {
      const t = await stepUpHandler() // pede o código por e-mail e repete a chamada
      return api<T>(path, o, retried, t)
    }
    if (!retried && accessToken !== null && (await refreshSession())) return api<T>(path, o, true, stepToken)
    if (!path.startsWith('/auth/')) onSessionLost?.()
  }
  if (!r.ok) throw await parseError(r)
  if (o.raw) return r as unknown as T
  if (r.status === 204) return undefined as T
  const ct = r.headers.get('content-type') ?? ''
  return (ct.includes('json') ? r.json() : r.text()) as Promise<T>
}

/** Baixa um arquivo autenticado (PDF, ZIP, CSV) e dispara o download no navegador. */
export async function download(path: string, query?: Opts['query'], method = 'GET') {
  const r = await api<Response>(path, { raw: true, query, method })
  const blob = await r.blob()
  const name = /filename="?([^";]+)"?/.exec(r.headers.get('Content-Disposition') ?? '')?.[1] ?? 'arquivo'
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = decodeURIComponent(name)
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 5000)
}

/** Upload retomável em partes: se a conexão cair, consulta o offset e continua de onde parou. */
export async function uploadBatch(file: File, meta: { unit_id?: string; tipo_lote?: string; simular_falha_na_pagina?: number; dica_funcionario_id?: string; dica_tipo?: string; substitui_documento_id?: string }, onProgress: (pct: number) => void) {
  const init = await api<{ upload_id: string; chunk_size: number }>('/batches/uploads', { method: 'POST', body: { filename: file.name, size: file.size, ...meta } })
  let offset = 0
  let falhas = 0
  while (offset < file.size) {
    const end = Math.min(offset + init.chunk_size, file.size)
    try {
      await api(`/batches/uploads/${init.upload_id}`, { method: 'PATCH', body: file.slice(offset, end), headers: { 'Upload-Offset': String(offset) } })
      offset = end
      falhas = 0
      onProgress(Math.round((offset / file.size) * 100))
    } catch (e) {
      if (++falhas > 5) throw e
      await new Promise((res) => setTimeout(res, 1000 * falhas))
      const st = await api<{ offset: number }>(`/batches/uploads/${init.upload_id}`) // retoma do offset do servidor
      offset = st.offset
    }
  }
  return api<{ id: string }>(`/batches/uploads/${init.upload_id}/complete`, { method: 'POST' })
}

/** SSE com cabeçalho Authorization (EventSource nativo não permite). */
export function streamEvents(path: string, onEvent: (e: any) => void, signal: AbortSignal) {
  ;(async () => {
    while (!signal.aborted) {
      try {
        const r = await fetch(BASE + path, { headers: { Authorization: 'Bearer ' + accessToken, Accept: 'text/event-stream' }, credentials: 'include', signal })
        if (r.status === 401 && (await refreshSession())) continue
        if (!r.ok || !r.body) throw new Error('sse')
        const reader = r.body.getReader()
        const dec = new TextDecoder()
        let buf = ''
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const parts = buf.split('\n\n')
          buf = parts.pop() ?? ''
          for (const p of parts) {
            const d = p.split('\n').find((l) => l.startsWith('data: '))
            if (d) try { onEvent(JSON.parse(d.slice(6))) } catch { /* ignora ping */ }
          }
        }
      } catch { /* reconecta */ }
      if (!signal.aborted) await new Promise((res) => setTimeout(res, 2000))
    }
  })()
}
