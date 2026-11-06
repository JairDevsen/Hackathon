import type { ReactNode } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { ArrowLeft, type LucideIcon } from 'lucide-react'
import { clsx } from '@/components/ui'

export interface SideItem { to: string; label: string; icon?: LucideIcon; dot?: boolean; end?: boolean }
export interface SideGroup { label?: string; items: SideItem[] }

/** Submenu lateral (painel de vidro) para páginas com 4+ seções; abaixo de 900px vira faixa de chips. */
export function SectionLayout({ back, header, groups, action, children }: { back?: { to: string; label: string }; header: ReactNode; groups: SideGroup[]; action?: ReactNode; children?: ReactNode }) {
  return (
    <div>
      {back && <Link to={back.to} className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"><ArrowLeft className="h-4 w-4" />{back.label}</Link>}
      <div className="mb-5">{header}</div>
      <div className="grid gap-5 min-[900px]:grid-cols-[17rem_1fr]">
        <aside className="min-[900px]:sticky min-[900px]:top-0 min-[900px]:self-start">
          {action && <div className="mb-3">{action}</div>}
          <nav aria-label="Seções" className="glass-panel p-2 max-[899px]:flex max-[899px]:gap-1 max-[899px]:overflow-x-auto max-[899px]:rounded-full">
            {groups.map((g, i) => (
              <div key={i} className="max-[899px]:flex max-[899px]:gap-1 min-[900px]:mb-2 min-[900px]:last:mb-0">
                {g.label && <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[.14em] text-muted-foreground max-[899px]:hidden">{g.label}</p>}
                {g.items.map((it) => (
                  <NavLink key={it.to} to={it.to} end={it.end ?? true}
                    className={({ isActive }) => clsx('side-item max-[899px]:shrink-0 max-[899px]:rounded-full max-[899px]:py-2 max-[899px]:whitespace-nowrap', isActive && 'side-item-active')}>
                    {it.icon && <it.icon className="h-4 w-4" aria-hidden />}{it.label}
                    {it.dot && <span className="ml-auto h-2 w-2 rounded-full bg-danger" aria-label="com pendências" />}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
        </aside>
        <div className="min-w-0">{children ?? <Outlet />}</div>
      </div>
    </div>
  )
}
