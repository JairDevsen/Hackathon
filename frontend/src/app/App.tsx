import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes, useParams } from 'react-router-dom'
import { Activity, BarChart3, Briefcase, Building2, CalendarDays, ClipboardCheck, Database, FileCog, FileText, FolderCog, Gauge, HardDrive, Home, LifeBuoy, ListChecks, Receipt, ScrollText, Search, Settings, ShieldCheck, Upload, UserCog, Users, Wallet, Bot, Layers, History, Coins, FolderOpen } from 'lucide-react'
import { AppShell } from '@/components/shell/AppShell'
import { filterNav, type NavEntry } from '@/components/shell/nav'
import { SkeletonRows } from '@/components/ui'
import { useAuth, type User } from '@/lib/auth'
import { useGet } from '@/lib/query'
const Landing = lazy(() => import('@/landing/Landing').then((m) => ({ default: m.Landing })))
import { Invite, Login } from '@/features/auth/Login'
import { SearchPage } from '@/features/rh/Search'
import { DossieDados, DossieDocs, DossieExigidos, DossieExport, DossieLayout, DossiePendencias, DossieRevisoes, DossieRiscos, DossieTimeline } from '@/features/rh/Dossie'
import { DocumentPage } from '@/features/rh/Document'
import { DocumentosPage } from '@/features/rh/Documentos'
import { BatchDetail, BatchList, BatchUpload } from '@/features/rh/Batches'
import { ReviewPage } from '@/features/rh/Review'
import { RiscosPage } from '@/features/rh/Riscos'
import { CalendarPage, EmployeesPage, PendenciasPage, ProfilePage, ReportsPage } from '@/features/rh/Lists'
const AdminDashboard = lazy(() => import('@/features/empresa/Dashboard').then((m) => ({ default: m.AdminDashboard })))
const FinopsPage = lazy(() => import('@/features/finops/Finops').then((m) => ({ default: m.FinopsPage })))
import { AuditPage, BillingPage, CadastroConfigPage, CompanyPage, LogsPage, PositionsPage, RetentionPage, SupportAccessPage, UsersPage } from '@/features/empresa/Config'
import { RequirementsPage } from '@/features/empresa/Obrigatorios'
const AuditMaster = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.AuditMaster })))
const CatalogPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.CatalogPage })))
const MasterAuditPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.MasterAuditPage })))
const MasterHome = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.MasterHome })))
const MasterUsersPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.MasterUsersPage })))
const PlansPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.PlansPage })))
const QualityPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.QualityPage })))
const QueuesPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.QueuesPage })))
const StoragePage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.StoragePage })))
const TenantDados = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantDados })))
const TenantLayout = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantLayout })))
const TenantPlano = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantPlano })))
const TenantSuporte = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantSuporte })))
const TenantUso = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantUso })))
const TenantUsuarios = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantUsuarios })))
const TenantsPage = lazy(() => import('@/features/master/Master').then((m) => ({ default: m.TenantsPage })))

function useNav(): NavEntry[] {
  const { user } = useAuth()
  const isTenant = !!user && user.role !== 'MASTER'
  const ov = useGet<any>(isTenant ? '/metrics/overview' : null, undefined, { refetchInterval: 30000 })
  if (!user) return []
  const rev = ov.data?.aguardando_revisao || undefined
  const pend = ov.data ? ov.data.pendentes + ov.data.vencidos || undefined : undefined
  const T: User['role'][] = ['ADMIN_EMPRESA', 'RH']
  const all: NavEntry[] = [
    // Master
    { kind: 'link', to: '/app', label: 'Início', icon: Home, roles: ['MASTER'] },
    { kind: 'link', to: '/app/clientes', label: 'Clientes', icon: Building2, roles: ['MASTER'] },
    { kind: 'link', to: '/app/planos', label: 'Planos', icon: Wallet, roles: ['MASTER'] },
    { kind: 'link', to: '/app/armazenamento', label: 'Armazenamento', icon: HardDrive, roles: ['MASTER'] },
    { kind: 'group', label: 'Plataforma', icon: Layers, children: [
      { kind: 'link', to: '/app/plataforma/catalogo', label: 'Catálogo de documentos', icon: FolderCog, roles: ['MASTER'] },
      { kind: 'link', to: '/app/plataforma/qualidade', label: 'Qualidade da IA', icon: Bot, roles: ['MASTER'] },
      { kind: 'link', to: '/app/plataforma/filas', label: 'Filas e jobs', icon: Activity, roles: ['MASTER'] }] },
    { kind: 'link', to: '/app/auditoria-global', label: 'Auditoria', icon: ScrollText, roles: ['MASTER'] },
    { kind: 'link', to: '/app/usuarios-master', label: 'Usuários Master', icon: UserCog, roles: ['MASTER'] },
    // Administrador da empresa e RH: a mesma visão operacional (configuração e conta ficam só com o admin)
    { kind: 'link', to: '/app', label: 'Início', icon: Home, roles: T },
    { kind: 'link', to: '/app/buscar', label: 'Buscar', icon: Search, roles: T },
    { kind: 'link', to: '/app/funcionarios', label: 'Funcionários', icon: Users, roles: T },
    { kind: 'link', to: '/app/documentos', label: 'Documentos', icon: FolderOpen, roles: T },
    { kind: 'link', to: '/app/lotes', label: 'Lotes', icon: FileText, roles: T },
    { kind: 'link', to: '/app/lotes/novo', label: 'Enviar lote', icon: Upload, roles: T },
    { kind: 'link', to: '/app/revisao', label: 'Revisão', icon: ClipboardCheck, badge: rev, roles: T },
    { kind: 'link', to: '/app/pendencias', label: 'Pendências', icon: ListChecks, badge: pend, roles: T },
    { kind: 'link', to: '/app/riscos', label: 'Riscos trabalhistas', icon: ShieldCheck, badge: ov.data?.riscos_abertos || undefined, roles: T },
    { kind: 'link', to: '/app/calendario', label: 'Calendário', icon: CalendarDays, roles: T },
    { kind: 'link', to: '/app/relatorios', label: 'Relatórios', icon: BarChart3, roles: T },
    { kind: 'link', to: '/app/finops', label: 'Escala 950k & FinOps', icon: Coins, roles: ['ADMIN_EMPRESA', 'MASTER'] },
    { kind: 'group', label: 'Configurações', icon: Settings, children: [
      { kind: 'link', to: '/app/configuracoes/empresa', label: 'Empresa e unidades', icon: Building2, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/configuracoes/cargos', label: 'Setores e cargos', icon: Briefcase, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/configuracoes/cadastro', label: 'Cadastro de funcionários', icon: Users, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/configuracoes/obrigatorios', label: 'Documentos obrigatórios', icon: FileCog, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/configuracoes/usuarios', label: 'Usuários RH', icon: UserCog, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/configuracoes/retencao', label: 'Retenção', icon: History, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/configuracoes/suporte', label: 'Acesso de suporte', icon: LifeBuoy, roles: ['ADMIN_EMPRESA'] }] },
    { kind: 'group', label: 'Conta', icon: Wallet, children: [
      { kind: 'link', to: '/app/conta/plano', label: 'Plano e uso', icon: Receipt, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/conta/auditoria', label: 'Auditoria', icon: ShieldCheck, roles: ['ADMIN_EMPRESA'] },
      { kind: 'link', to: '/app/conta/logs', label: 'Logs', icon: Database, roles: ['ADMIN_EMPRESA'] }] },
  ]
  return filterNav(all, user)
}

function Protected() {
  const { user, loading } = useAuth()
  const nav = useNav()
  if (loading) return <div className="grid h-dvh place-items-center"><SkeletonRows n={3} /></div>
  if (!user) return <Navigate to="/entrar" replace />
  return <AppShell nav={nav} />
}

/** Bloqueia por perfil também na URL (o menu já esconde; a API é quem realmente barra). */
function OnlyRoles({ roles }: { roles: User['role'][] }) {
  const { user } = useAuth()
  return user && roles.includes(user.role) ? <Outlet /> : <Navigate to="/app" replace />
}

function Home_() {
  const { user } = useAuth()
  return user?.role === 'MASTER' ? <MasterHome /> : <AdminDashboard />  // Admin e RH compartilham o painel
}

export function App() {
  return (
    <Suspense fallback={<div className="grid h-dvh place-items-center"><SkeletonRows n={3} /></div>}>
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/entrar" element={<Login />} />
      <Route path="/convite" element={<Invite />} />
      <Route path="/app" element={<Protected />}>
        <Route index element={<Home_ />} />
        <Route path="perfil" element={<ProfilePage />} />
        <Route path="buscar" element={<SearchPage />} />
        <Route path="funcionarios" element={<EmployeesPage />} />
        <Route path="funcionarios/:id" element={<DossieLayout />}>
          <Route index element={<DossieDados />} />
          <Route path="documentos/:secao" element={<DossieDocs />} />
          <Route path="documentos-exigidos" element={<DossieExigidos />} />
          <Route path="pendencias" element={<DossiePendencias />} />
          <Route path="riscos" element={<DossieRiscos />} />
          <Route path="linha-do-tempo" element={<DossieTimeline />} />
          <Route path="revisoes" element={<DossieRevisoes />} />
          <Route path="exportar" element={<DossieExport />} />
        </Route>
        <Route path="documentos" element={<DocumentosPage />} />
        <Route path="documentos/:id" element={<DocumentPage />} />
        <Route path="lotes" element={<BatchList />} />
        <Route path="lotes/novo" element={<BatchUpload />} />
        <Route path="lotes/:id" element={<BatchDetail />} />
        <Route path="revisao" element={<ReviewPage />} />
        <Route path="pendencias" element={<PendenciasPage />} />
        <Route path="riscos" element={<RiscosPage />} />
        <Route path="calendario" element={<CalendarPage />} />
        <Route path="relatorios" element={<ReportsPage />} />
        <Route element={<OnlyRoles roles={['ADMIN_EMPRESA', 'MASTER']} />}><Route path="finops" element={<FinopsPage />} /></Route>
        <Route element={<OnlyRoles roles={['ADMIN_EMPRESA']} />}>
        <Route path="configuracoes/empresa" element={<CompanyPage />} />
        <Route path="configuracoes/cargos" element={<PositionsPage />} />
        <Route path="configuracoes/cadastro" element={<CadastroConfigPage />} />
        <Route path="configuracoes/obrigatorios" element={<RequirementsPage />} />
        <Route path="configuracoes/usuarios" element={<UsersPage />} />
        <Route path="configuracoes/retencao" element={<RetentionPage />} />
        <Route path="configuracoes/suporte" element={<SupportAccessPage />} />
        <Route path="conta/plano" element={<BillingPage />} />
        <Route path="conta/auditoria" element={<AuditPage />} />
        <Route path="conta/logs" element={<LogsPage />} />
        </Route>
        {/* Master */}
        <Route element={<OnlyRoles roles={['MASTER']} />}>
        <Route path="clientes" element={<TenantsPage />} />
        <Route path="clientes/:id" element={<TenantLayout />}>
          <Route index element={<TenantDados />} />
          <Route path="plano" element={<TenantPlano />} />
          <Route path=":secao" element={<TenantSecao />} />
        </Route>
        <Route path="planos" element={<PlansPage />} />
        <Route path="armazenamento" element={<StoragePage />} />
        <Route path="plataforma/catalogo" element={<CatalogPage />} />
        <Route path="plataforma/qualidade" element={<QualityPage />} />
        <Route path="plataforma/filas" element={<QueuesPage />} />
        <Route path="auditoria-global" element={<MasterAuditPage />} />
        <Route path="usuarios-master" element={<MasterUsersPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  )
}

function TenantSecao() {
  const { secao } = useParams()
  if (secao === 'usuarios') return <TenantUsuarios />
  if (secao === 'suporte') return <TenantSuporte />
  if (secao === 'auditoria') return <AuditMaster />
  return <TenantUso />
}
export const _icons = [Gauge]
