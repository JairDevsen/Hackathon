import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, refreshSession, setAccessToken, setSessionLostHandler } from './api'

export interface User { id: string; nome: string; email: string; role: 'MASTER' | 'ADMIN_EMPRESA' | 'RH'; tenant_id: string; perms: string[]; empresa?: { nome: string; porte: string } }
interface Ctx {
  user: User | null
  loading: boolean
  setSession: (token: string, user?: User) => Promise<void>
  logout: () => Promise<void>
  can: (perm: string) => boolean
}
const AuthCtx = createContext<Ctx>(null!)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try { setUser(await api<User>('/auth/me')) } catch { setUser(null) }
  }, [])

  useEffect(() => {
    setSessionLostHandler(() => { setAccessToken(null); setUser(null) })
    ;(async () => {
      // restaura a sessão pelo cookie HttpOnly do refresh token
      if (await refreshSession()) await load()
      setLoading(false)
    })()
  }, [load])

  const value = useMemo<Ctx>(() => ({
    user, loading,
    setSession: async (token) => { setAccessToken(token); await load() },
    logout: async () => { try { await api('/auth/logout', { method: 'POST' }) } catch { /* sessão já encerrada */ } setAccessToken(null); setUser(null) },
    can: (p) => !!user?.perms.includes(p),
  }), [user, loading, load])
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>
}
