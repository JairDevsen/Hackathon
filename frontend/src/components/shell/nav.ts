import type { LucideIcon } from 'lucide-react'
import type { User } from '@/lib/auth'

export type NavLink = { kind: 'link'; to: string; label: string; icon: LucideIcon; badge?: number; dot?: boolean; roles?: User['role'][]; perm?: string }
export type NavGroup = { kind: 'group'; label: string; icon: LucideIcon; children: NavLink[] }
export type NavEntry = NavLink | NavGroup

const allowed = (l: NavLink, u: User) => (!l.roles || l.roles.includes(u.role)) && (!l.perm || u.perms.includes(l.perm))

/** Filtra por perfil e permissão ANTES de chegar ao AppShell. Grupo com 1 filho vira link; grupo vazio some. */
export function filterNav(entries: NavEntry[], user: User): NavEntry[] {
  const out: NavEntry[] = []
  for (const e of entries) {
    if (e.kind === 'link') { if (allowed(e, user)) out.push(e); continue }
    const kids = e.children.filter((c) => allowed(c, user))
    if (kids.length === 1) out.push({ ...kids[0], icon: kids[0].icon ?? e.icon })
    else if (kids.length > 1) out.push({ ...e, children: kids })
  }
  return out
}
