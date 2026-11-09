import { useEffect, useRef, useState } from 'react'
import { Link, NavLink as RLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Bell, ChevronDown, LogOut, Menu, Moon, Search, ShieldCheck, Sun, UserCircle, X } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Avatar, Logo, clsx } from '@/components/ui'
import { useAuth } from '@/lib/auth'
import { useGet } from '@/lib/query'
import { useTheme } from '@/lib/theme'
import { api } from '@/lib/api'
import { fmtDateTime } from '@/lib/format'
import type { NavEntry, NavLink } from './nav'
import { EntityFinder } from './EntityFinder'

function useOutside(ref: React.RefObject<HTMLElement | null>, onOut: () => void, active: boolean) {
  useEffect(() => {
    if (!active) return
    const click = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onOut() }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onOut() }
    document.addEventListener('mousedown', click); document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', click); document.removeEventListener('keydown', key) }
  }, [ref, onOut, active])
}

const Badge = ({ n }: { n?: number }) => (n ? <span className="badge-count ml-auto" aria-label={`${n} pendentes`}>{n > 999 ? '999+' : n}</span> : null)

function Item({ l, sub }: { l: NavLink; sub?: boolean }) {
  const { pathname } = useLocation()
  const novo = pathname === '/app/lotes/novo'
  return (
    <RLink to={l.to} end={l.to === '/app'} className={({ isActive }) => clsx('nav-item', sub && '!py-2 !pl-11 !text-[.86rem]', (l.to === '/app/lotes' ? isActive && !novo : isActive) && 'nav-item-active')}>
      {!sub && <l.icon className="h-[18px] w-[18px] shrink-0" aria-hidden />}<span className="truncate">{l.label}</span><Badge n={l.badge} />
    </RLink>
  )
}

function Sidebar({ nav, onNavigate }: { nav: NavEntry[]; onNavigate?: () => void }) {
  const loc = useLocation()
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  return (
    <div className="flex h-full flex-col" onClick={(e) => { if ((e.target as HTMLElement).closest('a')) onNavigate?.() }}>
      <Link to="/app" className="mb-6 flex items-center gap-2 px-2" aria-label="Citadel IA — início"><Logo /></Link>
      <nav aria-label="Principal" className="-mr-2 flex-1 space-y-1 overflow-y-auto pr-2">
        {nav.map((e) => {
          if (e.kind === 'link') return <Item key={e.to} l={e} />
          const active = e.children.some((c) => loc.pathname.startsWith(c.to))
          const open = openGroup === e.label || (openGroup === null && active)
          return (
            <div key={e.label}>
              <button className={clsx('nav-item', active && 'text-brand-darker')} aria-expanded={open} onClick={() => setOpenGroup(open ? '' : e.label)}>
                <e.icon className="h-[18px] w-[18px] shrink-0" aria-hidden /><span className="truncate">{e.label}</span>{!open && <Badge n={e.children.reduce((n, c) => n + (c.badge ?? 0), 0)} />}<ChevronDown className={clsx('ml-auto h-4 w-4 transition', open && 'rotate-180', !open && e.children.some((c) => c.badge) && '!ml-2')} aria-hidden />
              </button>
              {open && <div className="mt-1 space-y-0.5">{e.children.map((c) => <Item key={c.to} l={c} sub />)}</div>}
            </div>
          )
        })}
      </nav>
      <div className="mt-4 rounded-xl border border-border bg-brand-50 p-3 text-xs text-muted-foreground">
        <p className="mb-1 flex items-center gap-1.5 font-semibold text-brand-darker"><ShieldCheck className="h-4 w-4 text-brand-default" aria-hidden />Dados protegidos</p>
        Criptografia, isolamento por empresa e auditoria imutável.
      </div>
    </div>
  )
}

export function AppShell({ nav }: { nav: NavEntry[] }) {
  const { user, logout } = useAuth()
  const { theme, toggle } = useTheme()
  const loc = useLocation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [open, setOpen] = useState<string | null>(null)
  const [drawer, setDrawer] = useState(false)
  const [lastPath, setLastPath] = useState(loc.pathname)
  const topRef = useRef<HTMLDivElement>(null)
  if (lastPath !== loc.pathname) { setLastPath(loc.pathname); setOpen(null); setDrawer(false) } // fecha menus ao mudar de rota
  useOutside(topRef, () => setOpen(null), open !== null)

  const tenantUser = user?.role !== 'MASTER'
  const notifs = useGet<{ nao_lidas: number; itens: any[] }>(tenantUser ? '/notifications' : null, undefined, { refetchInterval: 30000 })
  const toggleMenu = (k: string) => setOpen((o) => (o === k ? null : k))
  const first = user?.nome.split(' ')[0]

  return (
    <div className="flex h-dvh overflow-hidden">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:rounded focus:bg-surface focus:p-2">Pular para o conteúdo</a>
      <aside className="sidebar hidden w-64 shrink-0 p-4 min-[900px]:block"><Sidebar nav={nav} /></aside>
      {drawer && (
        <div className="fixed inset-0 z-40 min-[900px]:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-black/50" onClick={() => setDrawer(false)} />
          <aside className="sidebar absolute inset-y-0 left-0 w-72 p-4 animate-pop"><Sidebar nav={nav} onNavigate={() => setDrawer(false)} /></aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header ref={topRef} className="relative z-30 flex items-center justify-end gap-3 px-4 py-3 sm:px-8">
          <button className="icon-circle mr-auto min-[900px]:hidden" aria-label="Abrir menu" onClick={() => setDrawer(true)}><Menu className="h-4 w-4" /></button>
          {tenantUser && <EntityFinder />}
          {tenantUser && <RLink to="/app/buscar" className="icon-circle min-[900px]:hidden" aria-label="Buscar"><Search className="h-4 w-4" /></RLink>}
          <div className="flex items-center gap-2">
            <button className="icon-circle hover:bg-brand-lighter" aria-label={theme === 'dark' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'} onClick={toggle}>{theme === 'dark' ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}</button>
            {tenantUser && (
              <div className="relative">
                <button className="icon-circle relative hover:bg-brand-lighter" aria-label="Notificações" aria-expanded={open === 'notif'} onClick={() => toggleMenu('notif')}>
                  <Bell className="h-[18px] w-[18px]" />
                  {!!notifs.data?.nao_lidas && <span className="absolute -right-1 -top-1 badge-count">{notifs.data.nao_lidas > 99 ? '99+' : notifs.data.nao_lidas}</span>}
                </button>
                {open === 'notif' && (
                  <div className="glass-dropdown absolute right-0 top-12 w-80 p-2">
                    <div className="flex items-center justify-between px-2 py-1"><b className="text-sm text-brand-darker">Notificações</b>
                      <button className="text-xs font-semibold text-brand" onClick={async () => { await api('/notifications/all/read', { method: 'POST' }); qc.invalidateQueries({ queryKey: ['/notifications'] }) }}>Marcar todas como lidas</button></div>
                    <ul className="max-h-80 overflow-auto">
                      {notifs.data?.itens.length ? notifs.data.itens.map((n) => (
                        <li key={n.id}><button onClick={() => { api(`/notifications/${n.id}/read`, { method: 'POST' }).then(() => qc.invalidateQueries({ queryKey: ['/notifications'] })); if (n.link) navigate('/app' + n.link) }}
                          className={clsx('block w-full rounded-md px-2 py-2 text-left text-sm hover:bg-brand-50', !n.lida_em && 'font-semibold')}>{n.titulo}<span className="block text-xs font-normal text-muted-foreground">{fmtDateTime(n.criado_em)}</span></button></li>
                      )) : <li className="px-2 py-6 text-center text-sm text-muted-foreground">Tudo em dia por aqui.</li>}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <div className="relative">
              <button className="flex items-center gap-2 rounded-full border border-border bg-surface/60 py-1 pl-1 pr-3 hover:border-brand-light" aria-label="Conta" aria-expanded={open === 'acc'} onClick={() => toggleMenu('acc')}>
                <Avatar nome={user?.nome} size="sm" /><span className="hidden text-sm font-medium text-brand-darker sm:block">{first}</span><ChevronDown className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              </button>
              {open === 'acc' && (
                <div role="menu" className="glass-dropdown absolute right-0 top-12 w-60 p-2">
                  <p className="px-2 py-1.5 text-xs text-muted-foreground">{user?.nome}<br />{user?.email}</p>
                  <RLink to="/app/perfil" role="menuitem" className="flex items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-brand-50"><UserCircle className="h-4 w-4" />Perfil e sessões</RLink>
                  <button role="menuitem" className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-brand-50" onClick={async () => { await logout(); navigate('/entrar') }}><LogOut className="h-4 w-4" />Sair</button>
                </div>
              )}
            </div>
          </div>
        </header>
        {/* só esta área rola; sem backdrop-filter/transform/filter aqui (quebraria modais fixed) */}
        <main id="conteudo" className="min-h-0 flex-1 overflow-y-auto px-4 pb-8 sm:px-8"><div className="mx-auto w-full max-w-[1400px]"><Outlet /></div></main>
      </div>
      {drawer && <button className="sr-only" onClick={() => setDrawer(false)}><X /></button>}
    </div>
  )
}
