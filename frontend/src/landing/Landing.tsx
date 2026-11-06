import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AlertTriangle, ArrowRight, Boxes, Check, CheckCircle2, ChevronDown, ClipboardCheck, FolderTree, KeyRound, Layers, Lock, Menu, RefreshCcw, ScanText, ScrollText, Settings2, ShieldCheck, Sparkles, Timer, Upload, UserRoundCheck, X, Zap } from 'lucide-react'
import { clsx } from '@/components/ui'
import { api } from '@/lib/api'
import { useForceDark } from '@/lib/theme'
import { emailDomain, FREE_DOMAINS } from '@/lib/format'

const track = (name: string) => { if (localStorage.getItem('citadel_consent') === 'yes') (window as any).dataLayer?.push({ event: name }) } // sem dados pessoais

/* ---------- barra superior (versão sobre o escuro) ---------- */
function Bar() {
  const [open, setOpen] = useState(false)
  const links = [['como-funciona', 'Como funciona'], ['recursos', 'Recursos'], ['seguranca', 'Segurança'], ['planos', 'Planos'], ['faq', 'FAQ']]
  return (
    <header className="fixed inset-x-0 top-3 z-40 px-3">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 rounded-full border border-white/10 bg-night/60 px-4 py-2 backdrop-blur-lg">
        <a href="#topo" aria-label="Citadel IA"><img src="/brand/citadel-logo.png" alt="Citadel IA" className="-my-3 h-16 w-auto" /></a>
        <nav aria-label="Seções" className="hidden gap-1 md:flex">{links.map(([id, l]) => <a key={id} href={`#${id}`} className="rounded-full px-3 py-1.5 text-sm text-white/80 hover:bg-white/10 hover:text-white">{l}</a>)}</nav>
        <div className="flex items-center gap-2">
          <Link to="/entrar" className="hidden rounded-full px-3 py-1.5 text-sm text-white/80 hover:text-white sm:block">Entrar</Link>
          <a href="#contato" className="btn-primary-gradient !px-4 !py-2 text-sm" onClick={() => track('cta_demo')}><span className="sm:hidden">Demonstração</span><span className="hidden sm:inline">Agendar demonstração</span></a>
          <button className="icon-circle !bg-white/10 !text-white md:hidden" aria-label={open ? 'Fechar menu' : 'Abrir menu'} onClick={() => setOpen(!open)}>{open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}</button>
        </div>
      </div>
      {open && <div className="mx-auto mt-2 max-w-6xl rounded-2xl border border-white/10 bg-night/90 p-2 backdrop-blur-lg md:hidden">{links.map(([id, l]) => <a key={id} href={`#${id}`} onClick={() => setOpen(false)} className="block rounded-xl px-4 py-3 text-white/90 hover:bg-white/10">{l}</a>)}<Link to="/entrar" className="block px-4 py-3 text-white/90">Entrar</Link></div>}
    </header>
  )
}

/* ---------- hero ---------- */
function Frame({ src, alt, className }: { src: string; alt: string; className?: string }) {
  return (
    <figure className={clsx('overflow-hidden rounded-2xl border border-white/10 bg-[#120c2a] shadow-[0_30px_80px_-20px_rgba(138,82,212,.55)]', className)}>
      <div className="flex items-center gap-1.5 border-b border-white/10 bg-white/[.04] px-4 py-2.5" aria-hidden>{['#ff5f57', '#febc2e', '#28c840'].map((c) => <span key={c} className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />)}
        <span className="ml-3 rounded-md bg-white/[.06] px-3 py-0.5 text-[11px] text-white/50">app.citadel.ia</span></div>
      <img src={src} alt={alt} loading="lazy" className="block w-full" />
    </figure>
  )
}

function Float({ className, icon: I, tone, title, text }: { className: string; icon: any; tone: string; title: string; text: string }) {
  return (
    <div className={clsx('absolute hidden max-w-[15rem] items-start gap-3 rounded-xl border border-white/10 bg-[#1a1238]/95 p-3 shadow-xl backdrop-blur md:flex', className)}>
      <span className={clsx('grid h-8 w-8 shrink-0 place-items-center rounded-full', tone)}><I className="h-4 w-4" aria-hidden /></span>
      <span><b className="block text-sm text-white">{title}</b><span className="text-xs text-white/65">{text}</span></span>
    </div>
  )
}

function Hero() {
  return (
    <section id="topo" className="relative overflow-hidden bg-night pb-24 pt-32 text-white" style={{ background: 'radial-gradient(46rem 30rem at 82% 8%, rgba(138,82,212,.5), transparent 60%), radial-gradient(34rem 24rem at 0% 95%, rgba(96,32,184,.4), transparent 60%), #0b0716' }}>
      <svg className="pointer-events-none absolute -right-48 -top-48 h-[44rem] w-[44rem] animate-orbit opacity-40" viewBox="0 0 400 400" fill="none" aria-hidden><ellipse cx="200" cy="200" rx="190" ry="70" transform="rotate(-24 200 200)" stroke="url(#o)" strokeWidth="3" /><defs><linearGradient id="o" x1="0" x2="1"><stop offset="0" stopColor="#8a52d4" stopOpacity="0" /><stop offset=".6" stopColor="#c8aef0" /><stop offset="1" stopColor="#8a52d4" stopOpacity="0" /></linearGradient></defs></svg>
      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-5 lg:grid-cols-[1fr_1.25fr]">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-[.18em] text-[#c8aef0]"><Sparkles className="h-3.5 w-3.5" aria-hidden />Document AI Factory</p>
          <h1 className="mt-5 font-display text-4xl font-bold leading-[1.1] sm:text-5xl">Do lote de papel ao <span className="text-[#c8aef0]">dossiê de cada funcionário</span>, em minutos.</h1>
          <p className="mt-6 max-w-xl text-lg text-white/75">Envie centenas de páginas escaneadas ou fotografadas. A Citadel IA separa cada documento, identifica o tipo, extrai os dados, vincula ao CPF certo e mostra o que está faltando.</p>
          <div className="mt-8 flex flex-wrap gap-3"><a href="#contato" className="btn-primary-gradient" onClick={() => track('cta_demo')}>Agendar demonstração</a><a href="#produto" className="inline-flex items-center gap-2 rounded-full border border-white/25 px-5 py-2.5 font-medium text-white hover:bg-white/10">Ver o produto <ArrowRight className="h-4 w-4" /></a></div>
          <ul className="mt-10 grid max-w-lg grid-cols-2 gap-x-6 gap-y-3 text-sm text-white/70">{['36 tipos de documentos trabalhistas e de terceirização', 'Arquivos de até 500 MB', 'Retoma de onde parou após falha', 'Anonimização com tarja irreversível'].map((t) => <li key={t} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-[#c8aef0]" aria-hidden />{t}</li>)}</ul>
        </div>
        <div className="relative">
          <Frame src="/landing/dashboard.webp" alt="Painel da Citadel IA com conformidade documental, documentos processados e gráficos (dados fictícios)" />
          <Float className="-left-10 -bottom-6" icon={CheckCircle2} tone="bg-success-bg text-success" title="Lote concluído" text="11 documentos separados e classificados" />
          <Float className="-right-4 -top-6" icon={AlertTriangle} tone="bg-warning-bg text-warning" title="Imagem borrada" text="Envie uma imagem mais nítida" />
        </div>
      </div>
    </section>
  )
}

const Section = ({ id, eyebrow, title, children, alt, lead }: { id?: string; eyebrow?: string; title: string; children: ReactNode; alt?: boolean; lead?: string }) => (
  <section id={id} className={clsx('px-5 py-24', alt && 'border-y border-white/[.06] bg-white/[.025]')}>
    <div className="mx-auto max-w-7xl">
      {eyebrow && <p className="text-xs font-semibold uppercase tracking-[.18em] text-brand">{eyebrow}</p>}
      <h2 className="mt-2 max-w-3xl font-display text-3xl font-bold text-brand-darker sm:text-4xl">{title}</h2>
      {lead && <p className="mt-3 max-w-2xl text-lg text-muted-foreground">{lead}</p>}
      <div className="mt-12">{children}</div>
    </div>
  </section>
)

/* ---------- dores ---------- */
const DORES: [string, string][] = [
  ['Recebemos um PDF de 300 páginas com tudo misturado e alguém passa o dia separando.', 'Separação automática com detecção de início e fim de cada documento, mesmo com páginas fora de ordem ou em branco.'],
  ['OCR comum não lê letra de mão, carimbo nem cartão de ponto.', 'Modelos multimodais que leem a imagem como uma pessoa: manuscrito, tabela, carimbo e assinatura.'],
  ['Só descobrimos que faltava o ASO ou a ficha de EPI quando chega a fiscalização.', 'Matriz de obrigatoriedade por cargo e alertas de pendente, vencido e a vencer.'],
  ['Terceirizada entrega documento incompleto e o risco trabalhista fica com a gente.', 'Conferência automática: jornada acima de 10h, FGTS divergente, certidão vencida, documento sem assinatura.'],
  ['Achar o documento de um funcionário é caça ao tesouro em pastas e e-mails.', 'Busca por CPF ou nome e busca em texto completo dentro dos documentos.'],
  ['Medo de vazar dado pessoal e de descumprir a LGPD.', 'Criptografia, isolamento por empresa, 2FA, auditoria imutável e anonimização com tarja irreversível.'],
]
const Dores = () => (
  <Section eyebrow="O problema" title="O que o RH e o DP enfrentam hoje">
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{DORES.map(([d, r], i) => (
      <article key={i} className="glass-panel flex flex-col gap-3 p-5"><p className="font-medium text-foreground">“{d}”</p><p className="mt-auto flex gap-2 border-t border-border pt-3 text-sm text-brand-dark"><Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-default" />{r}</p></article>))}</div>
  </Section>
)

/* ---------- como funciona ---------- */
const PASSOS = [[Upload, 'Recebe', 'Lotes grandes, com envio que continua de onde parou.'], [Layers, 'Separa', 'Início e fim de cada documento, mesmo fora de ordem.'], [Boxes, 'Classifica', '36 tipos de documentos trabalhistas e de terceirização.'], [ScanText, 'Lê e indexa', 'Campos extraídos e PDF pesquisável.'], [ClipboardCheck, 'Revisa e organiza', 'Fila humana só para o que tiver dúvida; vínculo ao CPF.']] as const
const Como = () => (
  <Section id="como-funciona" eyebrow="Como funciona" title="Cinco etapas, do arquivo ao dossiê" alt>
    <ol className="grid gap-6 md:grid-cols-5">{PASSOS.map(([Icon, t, d], i) => (
      <li key={t} className="relative md:text-center"><span className="icon-circle !h-12 !w-12 md:mx-auto" style={{ background: 'var(--gradient-brand)', color: '#fff' }}><Icon className="h-5 w-5" /></span>
        <p className="mt-3 text-xs font-semibold text-muted-foreground">Etapa {i + 1}</p><h3 className="font-display text-lg font-semibold text-brand-darker">{t}</h3><p className="text-sm text-muted-foreground">{d}</p>
        {i < 4 && <span aria-hidden className="absolute left-14 top-6 hidden h-px w-[calc(100%-3rem)] bg-brand-light/60 md:block" />}</li>))}</ol>
  </Section>
)

/* ---------- produto em ação (telas reais, dados fictícios) ---------- */
const ABAS = [
  { k: 'lote', label: 'Resultado do lote', img: 'lote_resultado', alt: 'Resultado do lote com um documento vencido e dados divergentes (dados fictícios)', t: 'Cada problema aparece com a explicação e a próxima ação', pts: ['Totais de aprovados, com atenção e com erro', 'Documento vencido, imagem borrada e dados divergentes entre documentos', 'Comparar documentos lado a lado, revisar ou solicitar novo envio'] },
  { k: 'revisao', label: 'Revisão humana', img: 'revisao', alt: 'Tela de revisão com a imagem do documento e os campos extraídos (dados fictícios)', t: 'A IA só pede ajuda no que tem dúvida', pts: ['Imagem ao lado dos campos extraídos', 'Fila priorizada: erro, sem vínculo, baixa confiança', 'Atalhos de teclado e aprovação forçada registrada na auditoria'] },
  { k: 'docs', label: 'Documentos', img: 'documentos', alt: 'Lista de todos os documentos com busca e filtros (dados fictícios)', t: 'Todos os documentos da empresa, em um só lugar', pts: ['Busca por funcionário, tipo ou arquivo', 'Filtros por situação, categoria e tipo', 'Documentos de saúde mascarados sem a permissão'] },
  { k: 'dossie', label: 'Dossiê do funcionário', img: 'dossie_exigidos', alt: 'Documentos exigidos de um funcionário e a origem de cada regra (dados fictícios)', t: 'O que falta, o que vence e o que não se aplica', pts: ['Anel de conformidade e pendências por documento', 'Cada regra mostra de onde vem: setor, cargo ou exceção', 'Exportação do dossiê completo em ZIP'] },
] as const

function Produto() {
  const [k, setK] = useState<(typeof ABAS)[number]['k']>('lote')
  const a = ABAS.find((x) => x.k === k)!
  return (
    <Section id="produto" eyebrow="Produto em ação" title="É assim que o seu RH vai trabalhar" lead="Telas reais da plataforma, com dados fictícios.">
      <div className="mb-8 flex flex-wrap gap-2" role="tablist" aria-label="Telas do produto">
        {ABAS.map((x) => <button key={x.k} role="tab" aria-selected={k === x.k} onClick={() => setK(x.k)} className={clsx('rounded-full border px-4 py-2 text-sm font-medium transition', k === x.k ? 'border-brand-default bg-brand-lighter text-brand-darker' : 'border-white/10 text-muted-foreground hover:border-white/25 hover:text-white')}>{x.label}</button>)}
      </div>
      <div className="grid items-center gap-10 lg:grid-cols-[1fr_1.7fr]">
        <div><h3 className="font-display text-2xl font-bold text-brand-darker">{a.t}</h3>
          <ul className="mt-5 space-y-3">{a.pts.map((p) => <li key={p} className="flex gap-3 text-muted-foreground"><CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />{p}</li>)}</ul></div>
        <Frame key={a.img} src={`/landing/${a.img}.webp`} alt={a.alt} />
      </div>
    </Section>
  )
}

/* ---------- configurável por empresa ---------- */
const CONF = [
  [Settings2, 'Setores e cargos do jeito da sua empresa', 'Crie os setores e cargos que existem na sua operação. Nada vem imposto.'],
  [ClipboardCheck, 'Você escolhe os documentos de cada grupo', 'Marque o que cada setor ou cargo precisa entregar. Só o que está marcado gera pendência.'],
  [Zap, 'Exceção por funcionário, com justificativa', 'Quem não precisa de um documento é dispensado só ele, e a razão fica na auditoria.'],
  [FolderTree, 'Cadastro sob medida', 'Mostre ou esconda campos, defina os obrigatórios e crie campos próprios, como turno ou número do crachá.'],
] as const

function Configuravel() {
  return (
    <Section id="configuracao" alt eyebrow="Configurável" title="Cada empresa é de um jeito. A cobrança também." lead="Para o sistema não acusar documento que aquele trabalhador nunca precisou ter.">
      <div className="grid items-center gap-10 lg:grid-cols-[1.6fr_1fr]">
        <Frame src="/landing/obrigatorios.webp" alt="Tela para selecionar os documentos obrigatórios de um setor (dados fictícios)" />
        <ul className="space-y-5">{CONF.map(([I, t, d]) => (
          <li key={t} className="flex gap-4"><span className="icon-circle !h-11 !w-11 shrink-0"><I className="h-5 w-5" aria-hidden /></span><span><b className="block text-brand-darker">{t}</b><span className="text-sm text-muted-foreground">{d}</span></span></li>))}</ul>
      </div>
    </Section>
  )
}

/* ---------- recursos ---------- */
function ResourceExample({ children }: { children: ReactNode }) {
  return <div className="mt-auto min-w-0 rounded-xl border border-border bg-surface/70 p-3 text-xs text-foreground">{children}</div>
}

const RECURSOS = [
  {
    icon: Layers,
    title: 'Separa e reúne as páginas',
    description: 'Encontra o começo e o fim de cada documento no lote e reúne as páginas que pertencem a ele.',
    example: <div className="flex flex-wrap items-center gap-1.5"><span className="rounded-md border border-border px-2 py-1">pág. 2</span><span className="rounded-md border border-border px-2 py-1">pág. 3</span><ArrowRight className="h-3.5 w-3.5 text-brand" aria-hidden /><strong className="rounded-md bg-brand-lighter px-2 py-1 text-brand-darker">1 documento</strong></div>,
  },
  {
    icon: Boxes,
    title: 'Reconhece o tipo',
    description: 'Classifica holerite, ASO, TRCT, cartão de ponto e outros tipos do catálogo trabalhista.',
    example: <div className="flex flex-wrap gap-1.5">{['Holerite', 'ASO', 'TRCT', 'Ponto'].map((type) => <span key={type} className="rounded-full border border-brand-light/40 bg-brand-lighter px-2 py-1 text-brand-darker">{type}</span>)}</div>,
  },
  {
    icon: ScanText,
    title: 'Extrai e permite buscar',
    description: 'Lê campos relevantes e gera uma camada de texto para localizar informações no PDF.',
    example: <p className="min-w-0 break-words font-mono">…jornada <mark className="rounded bg-warning-bg px-1 text-warning">diária</mark>: 11h30…</p>,
  },
  {
    icon: UserRoundCheck,
    title: 'Vincula ao funcionário',
    description: 'Usa nome e CPF válido para pré-cadastrar a pessoa e organizar seus documentos no dossiê.',
    example: <div className="flex flex-wrap items-center gap-2"><span className="font-medium">Maria F. Costa</span><span className="text-muted-foreground">CPF ···.···.881-··</span><span className="rounded-full bg-success-bg px-2 py-0.5 font-medium text-success">Vinculado</span></div>,
  },
  {
    icon: AlertTriangle,
    title: 'Sinaliza o que precisa de atenção',
    description: 'Mostra baixa confiança, documento ilegível ou divergência para conferência do RH.',
    example: <div className="flex items-center gap-2"><span className="h-2 w-20 overflow-hidden rounded-full bg-muted"><span className="block h-full w-[58%] rounded-full bg-warning" /></span><strong className="text-warning">58%</strong><span className="text-muted-foreground">· revisão necessária</span></div>,
  },
  {
    icon: ClipboardCheck,
    title: 'Dá controle à revisão humana',
    description: 'O RH pode corrigir o tipo, preencher os campos manualmente ou solicitar uma cópia legível.',
    example: <div className="flex flex-wrap gap-1.5">{['Classificar', 'Preencher', 'Pedir nova cópia'].map((action) => <span key={action} className="rounded-md border border-border px-2 py-1 text-muted-foreground">{action}</span>)}</div>,
  },
] as const

const Capacidades = () => (
  <Section id="recursos" eyebrow="Recursos" title="Do lote ao dossiê, com cada etapa à vista" lead="A automação organiza o volume. Quando há dúvida, o RH recebe o motivo e a próxima ação.">
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{RECURSOS.map(({ icon: Icon, title, description, example }) => (
      <article key={title} className="glass-panel flex min-w-0 flex-col gap-4 p-5 sm:p-6">
        <span className="grid h-11 w-11 place-items-center rounded-xl border border-brand-light/30 bg-brand-lighter text-brand" aria-hidden><Icon className="h-5 w-5" /></span>
        <div><h3 className="font-display text-xl font-semibold leading-tight text-brand-darker">{title}</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p></div>
        <ResourceExample>{example}</ResourceExample>
      </article>
    ))}</div>
  </Section>
)

/* ---------- diferenciais ---------- */
function Diferenciais() {
  const blocos: { eyebrow: string; title: string; text: string; visual: ReactNode }[] = [
    { eyebrow: 'Modelos multimodais', title: 'Não é só OCR: a IA enxerga o documento inteiro.', text: 'O modelo lê a imagem da página: layout, texto impresso, manuscrito, carimbos e assinaturas. A resposta vem em formato estruturado e validado; quando a página é difícil, um modelo maior confere.',
      visual: <div className="relative mx-auto w-64"><img src="/demo/p7.webp" alt="Holerite fictício com marca AMOSTRA" className="rounded-md shadow-lg" loading="lazy" /><span className="absolute left-[8%] top-[22%] h-[7%] w-[60%] rounded border-2 border-brand-default bg-brand-default/15" /><span className="absolute left-[8%] top-[48%] h-[6%] w-[50%] rounded border-2 border-success bg-success/15" /></div> },
    { eyebrow: 'Retomada após falha', title: 'Caiu a conexão ou o servidor? O lote continua de onde parou, sem duplicar nada.', text: 'Cada página tem checkpoint. Se algo cair no meio, só o que falta é reprocessado, e a linha do tempo do lote mostra o que foi retomado e quando.',
      visual: <ol className="glass-panel mx-auto w-full max-w-sm space-y-2 p-4 text-sm">{[['Recebido', 'bg-brand-default'], ['Fatiado · 60 páginas', 'bg-brand-default'], ['Enviado à IA', 'bg-brand-default'], ['Falha · sem progresso', 'bg-danger'], ['Retomado · 15 prontas, 45 pendentes', 'bg-warning'], ['Concluído · 60 documentos', 'bg-success']].map(([t, c]) => <li key={t} className="flex items-center gap-2"><span className={clsx('h-2.5 w-2.5 rounded-full', c)} />{t}</li>)}</ol> },
    { eyebrow: 'Anonimização', title: 'Compartilhe com auditoria externa sem expor CPF, endereço ou dado de saúde.', text: 'A cópia anonimizada tem tarja queimada na imagem, camada de texto refeita e metadados removidos. É irreversível: o dado não existe mais no arquivo.',
      visual: <div className="mx-auto grid max-w-md grid-cols-2 gap-3 text-xs">{['Antes', 'Depois'].map((l, k) => <figure key={l}><div className="rounded-md border border-border bg-white p-3 text-left font-mono leading-5"><p>COLABORADOR: {k ? <span className="bg-black text-black">MARIA FERNANDA</span> : 'MARIA FERNANDA'}</p><p>CPF: {k ? <span className="bg-black text-black">619.204.881-97</span> : '619.204.881-97'}</p><p>CID: {k ? <span className="bg-black text-black">M54.5</span> : 'M54.5'}</p></div><figcaption className="mt-1 text-center font-semibold text-muted-foreground">{l}</figcaption></figure>)}</div> },
  ]
  return (
    <Section eyebrow="Diferenciais" title="Três coisas que o OCR comum não faz" alt>
      <div className="space-y-16">{blocos.map((b, i) => (
        <div key={b.title} className={clsx('grid items-center gap-8 lg:grid-cols-2', i % 2 && 'lg:[&>*:first-child]:order-2')}>
          <div><p className="text-xs font-semibold uppercase tracking-[.18em] text-brand">{b.eyebrow}</p><h3 className="mt-2 font-display text-2xl font-bold text-brand-darker">{b.title}</h3><p className="mt-3 text-muted-foreground">{b.text}</p></div>{b.visual}</div>))}</div>
    </Section>
  )
}

/* ---------- painel ---------- */
const Painel = () => (
  <Section eyebrow="Painel e métricas" title="O que está em dia, o que falta e o que vence">
    <div className="grid items-center gap-10 lg:grid-cols-[1.6fr_1fr]">
      <Frame src="/landing/dashboard.webp" alt="Painel com conformidade, pendências, revisões e armazenamento (dados fictícios)" />
      <dl className="space-y-4 text-sm">{[['Conformidade', 'Percentual de itens exigidos que estão em dia.'], ['Com pendência', 'Funcionários com ao menos um documento faltando ou vencido.'], ['Vencem em 30 dias', 'ASOs, treinamentos e certidões perto do vencimento.'], ['Aguardando revisão', 'Documentos em que a IA teve dúvida.'], ['Armazenamento', 'Uso da cota do plano.']].map(([t, d]) => <div key={t}><dt className="font-semibold text-brand-darker">{t}</dt><dd className="text-muted-foreground">{d}</dd></div>)}
        <p className="rounded-lg border border-white/10 bg-white/[.04] p-3 text-brand-darker">Resultado do piloto: <b>[[métrica do piloto]]</b></p></dl>
    </div>
  </Section>
)

/* ---------- segurança ---------- */
const SEG = [[KeyRound, '2FA por e-mail corporativo'], [Layers, 'Isolamento por empresa no banco'], [Lock, 'Criptografia AES-256'], [ScrollText, 'Auditoria encadeada por hash'], [ShieldCheck, 'Dados de saúde por permissão'], [Timer, 'Retenção configurável']] as const
const Seguranca = () => (
  <Section id="seguranca" eyebrow="Segurança e LGPD" title="Dado de funcionário exige cuidado de verdade" alt>
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{SEG.map(([I, t]) => <li key={t} className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[.04] p-4 text-white"><I className="h-5 w-5 text-[#c8aef0]" aria-hidden /><span>{t}</span></li>)}</ul>
    <p className="mt-6 max-w-2xl text-sm text-muted-foreground">Não declaramos certificações que não temos. Cada item acima pode ser verificado na demonstração.</p>
  </Section>
)

/* ---------- para quem ---------- */
const PORTES = [['Pequena', 'até 50 funcionários', '3 usuários RH', '20 GB', '3.000 páginas/mês'], ['Média', 'até 500 funcionários', '15 usuários RH', '200 GB', '30.000 páginas/mês'], ['Grande', 'funcionários ilimitados', 'usuários ilimitados', 'armazenamento conforme contrato', 'páginas conforme contrato']]
const ParaQuem = () => (
  <Section id="planos" eyebrow="Para quem" title="Do RH pequeno à empresa que gerencia terceirizadas">
    <div className="grid gap-4 md:grid-cols-3">{PORTES.map(([n, ...l]) => (
      <article key={n} className={clsx('glass-panel p-6', n === 'Média' && 'ring-2 ring-brand-default')}><h3 className="font-display text-2xl font-bold text-brand-darker">{n}</h3><ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">{l.map((x) => <li key={x} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-brand-default" />{x}</li>)}</ul><p className="mt-4 font-semibold text-brand-darker">Preço sob consulta</p></article>))}</div>
    <p className="mt-6 rounded-xl bg-brand-lighter p-4 text-brand-darker"><b>Empresas que contratam terceirizadas:</b> receba o dossiê completo de cada prestador e confira o que está faltando antes da fiscalização.</p>
  </Section>
)

/* ---------- demonstração (somente leitura; nada é enviado pelo visitante) ---------- */
function Demo() {
  const [data, setData] = useState<any>(null)
  const [step, setStep] = useState<0 | 1 | 2 | 3>(0)
  const [sel, setSel] = useState<any>(null)
  const run = async () => { setData(await (await fetch('/demo/result.json')).json()); setStep(1); track('demo_iniciada'); setTimeout(() => setStep(2), 1400) }
  return (
    <Section eyebrow="Demonstração" title="Teste com um lote de exemplo" alt id="demo">
      <p className="mb-5 max-w-2xl text-muted-foreground">Processamos um lote fictício de 11 páginas com marca “AMOSTRA”. Você vê as páginas, os documentos encontrados e o dossiê, só para leitura. Nada do que você faz aqui é enviado.</p>
      {step === 0 && <button className="btn-primary-gradient" onClick={run}><Sparkles className="mr-2 inline h-4 w-4" />Processar lote de exemplo</button>}
      {step === 1 && <p role="status" className="flex items-center gap-2 text-brand-dark"><RefreshCcw className="h-4 w-4 animate-spin" />Separando e classificando as 11 páginas…</p>}
      {step >= 2 && data && (
        <div className="space-y-5">
          <ol className="flex flex-wrap gap-2 text-sm">{['Páginas', 'Documentos', 'Dossiê'].map((l, i) => <li key={l}><button onClick={() => setStep((i + 1) as any)} className={clsx('rounded-full px-4 py-1.5 font-medium', step === i + 1 || (step === 2 && i === 0) ? 'bg-brand-default text-white' : 'border border-white/10 text-muted-foreground hover:text-white')}>{i + 1}. {l}</button></li>)}</ol>
          {step === 2 && <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">{Array.from({ length: data.paginas }).map((_, i) => <img key={i} src={`/demo/p${i + 1}.webp`} alt={`Página ${i + 1} do lote de exemplo`} loading="lazy" className="rounded-md border border-border bg-white shadow-md" />)}</div>}
          {step === 3 && (<>
            <div className="grid gap-3 md:grid-cols-2">{data.documentos.map((d: any) => (
              <button key={d.id} onClick={() => setSel(d)} className="glass-panel p-4 text-left hover:shadow-lg"><div className="flex justify-between gap-2"><b className="text-brand-darker">{d.tipo}</b><span className={clsx('rounded-full px-2 py-0.5 text-xs font-semibold', d.status === 'Auto-aprovado' ? 'bg-success-bg text-success' : 'bg-warning-bg text-warning')}>{d.status}</span></div>
                <p className="text-sm text-muted-foreground">pág. {d.paginas.join(', ')} · {d.funcionario ?? 'Sem vínculo'} {d.cpf_mascarado ? `· ${d.cpf_mascarado}` : ''} · confiança {Math.round(d.confianca * 100)}%</p>
                {d.alertas.map((a: string) => <p key={a} className="mt-1 text-xs text-warning">⚠ {a}</p>)}</button>))}</div>
            {sel && <div className="glass-panel p-4"><h3 className="font-display text-lg font-semibold text-brand-darker">Dossiê · {sel.funcionario ?? 'Sem vínculo'}</h3><div className="mt-2 flex gap-3">{sel.paginas.map((p: number) => <img key={p} src={`/demo/p${p}.webp`} alt={`Página ${p}`} className="h-40 rounded border border-border" />)}</div><dl className="mt-3 grid grid-cols-2 gap-2 text-sm">{Object.entries(sel.campos).slice(0, 6).map(([k, v]) => <div key={k}><dt className="text-xs uppercase text-muted-foreground">{k.replaceAll('_', ' ')}</dt><dd>{String(v)}</dd></div>)}</dl></div>}
          </>)}
        </div>
      )}
    </Section>
  )
}

/* ---------- FAQ ---------- */
const FAQ: [string, string][] = [
  ['Que documentos a Citadel IA lê?', 'Os 36 tipos do catálogo: holerite, cartão de ponto, ASO, TRCT, AR dos Correios, atestado, CTPS, fichas de EPI, certificados NR, certidões (CRF, CNDT, CND), guias de FGTS e DARF, contrato, apólice de seguro, autuações e processos da terceirizada, entre outros.'],
  ['E letra de mão?', 'Sim. O modelo lê a imagem, inclusive manuscrito, carimbos e assinaturas. Quando a leitura é duvidosa, o documento vai para a fila de revisão humana.'],
  ['Quanto tempo leva?', 'Depende do tamanho do lote e do plano. Mostramos o tempo real no seu piloto: [[métrica do piloto]].'],
  ['O que acontece quando a IA tem dúvida?', 'O documento entra na fila de revisão com o motivo (baixa confiança, página ilegível, sem vínculo…). Você vê a imagem ao lado dos campos e confirma, corrige, divide ou junta páginas.'],
  ['Onde ficam os dados?', 'Em armazenamento com criptografia por empresa. A região e o contrato de tratamento de dados são definidos com você na contratação.'],
  ['E a LGPD?', 'Isolamento por empresa, 2FA, auditoria imutável, acesso a dados de saúde por permissão, retenção configurável e cópia anonimizada irreversível para auditorias externas.'],
  ['Integra com a folha de pagamento?', 'Hoje a importação de cadastro é por planilha CSV/XLSX. A integração com folha e eSocial é um ponto de extensão planejado.'],
  ['Quanto custa?', 'Preço sob consulta, por porte. Fale com a gente para um orçamento.'],
]
const Faq = () => (
  <Section id="faq" eyebrow="FAQ" title="Perguntas frequentes">
    <div className="max-w-3xl space-y-2">{FAQ.map(([q, a]) => <details key={q} className="glass-panel group p-4"><summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-semibold text-brand-darker">{q}<ChevronDown className="h-4 w-4 transition group-open:rotate-180" /></summary><p className="mt-2 text-sm text-muted-foreground">{a}</p></details>)}</div>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({ '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: FAQ.map(([q, a]) => ({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })) }) }} />
  </Section>
)

/* ---------- formulário ---------- */
const leadSchema = z.object({
  nome: z.string().min(2, 'Informe seu nome'),
  email: z.string().email('E-mail inválido').refine((e) => !FREE_DOMAINS.includes(emailDomain(e)), 'Use seu e-mail corporativo (domínios gratuitos não são aceitos)'),
  empresa: z.string().min(2, 'Informe a empresa'),
  porte: z.enum(['PEQUENA', 'MEDIA', 'GRANDE'], { message: 'Escolha o porte' }),
  funcionarios: z.coerce.number().int().min(1, 'Informe o número de funcionários'),
  consentimento: z.literal(true, { message: 'Precisamos do seu consentimento para entrar em contato' }),
  website: z.string().optional(),
})
function Contato() {
  const { register, handleSubmit, formState: { errors, isSubmitting }, setError } = useForm({ resolver: zodResolver(leadSchema) as any })
  const [ok, setOk] = useState(false)
  const submit = handleSubmit(async (v: any) => {
    try { await api('/public/leads', { method: 'POST', body: v }); setOk(true); track('lead_enviado') } catch (e) { setError('root', { message: (e as Error).message }) }
  })
  const fld = 'w-full rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-white placeholder:text-white/50 focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-default/50'
  const E = ({ k }: { k: string }) => (errors as any)[k] ? <p role="alert" className="mt-1 text-xs text-red-300">{(errors as any)[k].message}</p> : null
  return (
    <section id="contato" className="bg-night px-5 py-20 text-white" style={{ background: 'radial-gradient(36rem 20rem at 50% 0%, rgba(138,82,212,.35), transparent 60%), #140b28' }}>
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="font-display text-3xl font-bold sm:text-4xl">Transforme sua pilha de papel em informação confiável.</h2>
        <p className="mt-3 text-white/70">Conte um pouco sobre sua empresa e agendamos uma demonstração com um lote do seu dia a dia.</p>
        {ok ? <p role="status" className="mt-8 rounded-xl bg-success-bg p-5 font-medium text-success">Recebemos seu contato. Em breve falamos com você.</p> : (
          <form onSubmit={submit} noValidate className="mt-8 grid gap-3 text-left sm:grid-cols-2">
            <div><label className="mb-1 block text-xs text-white/70" htmlFor="l-nome">Nome</label><input id="l-nome" className={fld} {...register('nome')} /><E k="nome" /></div>
            <div><label className="mb-1 block text-xs text-white/70" htmlFor="l-email">E-mail corporativo</label><input id="l-email" type="email" className={fld} {...register('email')} /><E k="email" /></div>
            <div><label className="mb-1 block text-xs text-white/70" htmlFor="l-emp">Empresa</label><input id="l-emp" className={fld} {...register('empresa')} /><E k="empresa" /></div>
            <div><label className="mb-1 block text-xs text-white/70" htmlFor="l-porte">Porte</label><select id="l-porte" className={fld} defaultValue="" {...register('porte')}><option value="" disabled className="text-black">Selecione</option><option value="PEQUENA" className="text-black">Pequena (até 50)</option><option value="MEDIA" className="text-black">Média (até 500)</option><option value="GRANDE" className="text-black">Grande</option></select><E k="porte" /></div>
            <div className="sm:col-span-2"><label className="mb-1 block text-xs text-white/70" htmlFor="l-func">Número de funcionários</label><input id="l-func" type="number" min={1} className={fld} {...register('funcionarios')} /><E k="funcionarios" /></div>
            <input type="text" tabIndex={-1} autoComplete="off" aria-hidden className="absolute -left-[9999px]" {...register('website')} />
            <label className="flex items-start gap-2 text-sm text-white/80 sm:col-span-2"><input type="checkbox" className="mt-1" {...register('consentimento')} /><span>Concordo em ser contatado e com o tratamento dos meus dados conforme a <a href="/privacidade" className="underline">política de privacidade</a>.</span></label>
            <div className="sm:col-span-2"><E k="consentimento" /></div>
            {(errors as any).root && <p role="alert" className="text-sm text-red-300 sm:col-span-2">{(errors as any).root.message}</p>}
            <button type="submit" disabled={isSubmitting} className="btn-primary-gradient sm:col-span-2">{isSubmitting ? 'Enviando…' : 'Quero agendar uma demonstração'}</button>
          </form>)}
      </div>
    </section>
  )
}

const Footer = () => (
  <footer className="bg-night px-5 py-10 text-white/70"><div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4"><img src="/brand/citadel-logo.png" alt="Citadel IA" className="h-10" />
    <nav aria-label="Rodapé" className="flex gap-4 text-sm">{['Privacidade', 'Termos', 'Segurança', 'Contato'].map((l) => <a key={l} href={l === 'Contato' ? '#contato' : l === 'Segurança' ? '#seguranca' : `/${l.toLowerCase()}`} className="hover:text-white">{l}</a>)}</nav>
    <p className="text-xs">CNPJ 00.000.000/0000-00 (placeholder) · © {new Date().getFullYear()} Citadel IA</p></div></footer>
)

function ConsentBanner() {
  const [v, setV] = useState(() => localStorage.getItem('citadel_consent'))
  if (v) return null
  const set = (x: string) => { localStorage.setItem('citadel_consent', x); setV(x) }
  return (
    <div role="dialog" aria-label="Consentimento de analytics" className="fixed inset-x-3 bottom-3 z-50 mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-night/95 p-4 text-sm text-white shadow-lg backdrop-blur">
      <p className="max-w-xl text-white/80">Usamos medição anônima de uso (sem dados pessoais) para melhorar o site. Você aceita?</p>
      <div className="flex gap-2"><button className="rounded-full border border-white/25 px-4 py-1.5" onClick={() => set('no')}>Recusar</button><button className="btn-primary-gradient !px-4 !py-1.5" onClick={() => set('yes')}>Aceitar</button></div>
    </div>
  )
}

export function Landing() {
  useForceDark()
  useEffect(() => { document.title = 'Citadel IA · Document AI Factory — organização inteligente de documentos de funcionários' }, [])
  return (
    <div className="min-h-dvh scroll-smooth" style={{ scrollBehavior: 'smooth' }}>
      <Bar /><Hero /><Dores /><Como /><Produto /><Configuravel /><Capacidades /><Diferenciais /><Painel /><Seguranca /><ParaQuem /><Demo /><Faq /><Contato /><Footer /><ConsentBanner />
    </div>
  )
}
