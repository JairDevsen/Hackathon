import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Check } from 'lucide-react'
import { Logo } from '@/components/ui'

const PONTOS = ['Separa e classifica cada documento do lote', 'Vincula ao CPF certo e mostra o que está faltando', 'Revisão humana só onde a IA tem dúvida', 'Criptografia, 2FA e auditoria imutável']

/** Tela dividida: painel escuro da marca à esquerda; formulário em fundo claro à direita. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <aside className="relative hidden overflow-hidden text-white lg:flex lg:flex-col lg:justify-between lg:p-12"
        style={{ background: 'radial-gradient(40rem 30rem at 90% 0%, rgba(138,82,212,.55), transparent 60%), radial-gradient(30rem 24rem at 0% 100%, rgba(96,32,184,.45), transparent 60%), #0b0716' }}>
        <img src="/brand/citadel-logo.png" alt="Citadel IA" className="-ml-6 -mt-4 h-24 w-auto self-start" />
        <div className="relative z-10 max-w-xl">
          <h2 className="font-display text-4xl font-bold leading-[1.1]">Documentos complexos.<br /><span className="text-[#c8aef0]">Gestão inteligente.</span></h2>
          <p className="mt-4 text-lg text-white/70">Transforme lotes digitalizados em dossiês organizados, classificados e pesquisáveis.</p>
          <ul className="mt-6 space-y-2.5 text-white/80">{PONTOS.map((p) => <li key={p} className="flex gap-3"><Check className="mt-0.5 h-5 w-5 shrink-0 text-[#c8aef0]" aria-hidden />{p}</li>)}</ul>
        </div>
        <figure className="pointer-events-none relative z-0 -mb-24 -mr-28 ml-28 mt-10 overflow-hidden rounded-t-2xl border border-white/10 shadow-[0_30px_80px_-20px_rgba(138,82,212,.6)]" aria-hidden>
          <img src="/landing/dashboard.webp" alt="" className="block w-full" />
        </figure>
      </aside>
      <main className="force-light flex flex-col justify-center bg-[#f7f5fb] px-6 py-10 sm:px-12" style={{ background: 'radial-gradient(40rem 26rem at 100% 0%, rgba(200,174,240,.45), transparent 60%), #f7f5fb' }}>
        <div className="mx-auto w-full max-w-md">
          <div className="mb-8 flex items-center justify-between"><Link to="/" className="lg:hidden" aria-label="Citadel IA"><Logo /></Link>
            <Link to="/" className="ml-auto inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-brand"><ArrowLeft className="h-4 w-4" aria-hidden />Voltar ao site</Link></div>
          {children}
          <p className="mt-10 text-center text-xs text-muted-foreground">Ao entrar você concorda com o tratamento de dados conforme a LGPD.</p>
        </div>
      </main>
    </div>
  )
}
