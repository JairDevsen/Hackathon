import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { useGet } from '@/lib/query'
import { Avatar, Input } from '@/components/ui'

export function EmployeePicker({ onPick, placeholder = 'Buscar por CPF, nome ou matrícula' }: { onPick: (e: any) => void; placeholder?: string }) {
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 250); return () => clearTimeout(t) }, [q])
  const res = useGet<{ items: any[] }>(dq.length >= 2 ? '/employees' : null, { q: dq, limit: 6 })
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <Input className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} aria-label="Buscar funcionário" />
      {!!res.data?.items.length && (
        <ul className="glass-dropdown absolute z-20 mt-1 max-h-64 w-full overflow-auto p-1">
          {res.data.items.map((e) => (
            <li key={e.id}><button type="button" className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm hover:bg-brand-50" onClick={() => { onPick(e); setQ(''); setDq('') }}>
              <Avatar nome={e.nome} size="sm" /><span><b className="block text-brand-darker">{e.nome}</b><span className="text-xs text-muted-foreground">{e.cpf_mascarado} · {e.cargo ?? 'sem cargo'}</span></span></button></li>
          ))}
        </ul>
      )}
    </div>
  )
}
