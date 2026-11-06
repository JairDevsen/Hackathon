export const fmtDate = (s?: string | null) => (s ? new Date(s.length === 10 ? s + 'T00:00:00' : s).toLocaleDateString('pt-BR') : '—')
export const fmtDateTime = (s?: string | null) => (s ? new Date(s).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—')
export const fmtNum = (n?: number | null, max = 1) => (n === null || n === undefined ? '—' : Number(n).toLocaleString('pt-BR', { maximumFractionDigits: max }))
export const fmtPct = (n?: number | null, max = 0) => (n === null || n === undefined ? '—' : `${fmtNum(n, max)}%`)
export function fmtBytes(n?: number | null) {
  if (!n) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), u.length - 1)
  return `${fmtNum(n / 1024 ** i, i ? 1 : 0)} ${u[i]}`
}
export const initials = (nome?: string) => (nome ?? '?').split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase()
export const fmtMoney = (c?: number | null) => (c === null || c === undefined ? 'Sob consulta' : (c / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }))
export const competenciaLabel = (c?: string | null) => (c ? c.split('-').reverse().join('/') : '—')
export const cpfMask = (v: string) => {
  const d = v.replace(/\D/g, '').slice(0, 11)
  return d.replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d)/, '$1.$2').replace(/(\d{3})(\d{1,2})$/, '$1-$2')
}
export function cpfValido(s: string) {
  const d = s.replace(/\D/g, '')
  if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false
  for (const n of [9, 10]) {
    let sum = 0
    for (let i = 0; i < n; i++) sum += Number(d[i]) * (n + 1 - i)
    if (((sum * 10) % 11) % 10 !== Number(d[n])) return false
  }
  return true
}
export const emailDomain = (e: string) => e.split('@')[1]?.toLowerCase() ?? ''
export const FREE_DOMAINS = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'yahoo.com.br', 'uol.com.br', 'bol.com.br', 'icloud.com', 'live.com', 'terra.com.br', 'ig.com.br', 'msn.com', 'proton.me', 'protonmail.com']
export const TIPOS_LOTE = [['MISTO', 'Misto'], ['ADMISSAO', 'Admissão'], ['MENSAL', 'Mensal'], ['DESLIGAMENTO', 'Desligamento'], ['OCORRENCIAS', 'Ocorrências'], ['ARS', 'ARs']] as const
export const MOTIVOS: Record<string, string> = {
  BAIXA_CONFIANCA: 'Baixa confiança', PAGINA_ILEGIVEL: 'Página ilegível', MULTIPLOS_DOCUMENTOS: 'Mais de um documento', TIPO_OUTRO: 'Tipo não identificado',
  SEM_VINCULO: 'Sem vínculo', VINCULO_POR_NOME: 'Vínculo só por nome', ALERTA_ERRO: 'Alerta de erro', POSSIVEL_DUPLICATA: 'Possível duplicata', DIVISAO_MANUAL: 'Divisão manual',
  DADOS_DIVERGENTES: 'Dados divergentes', IMAGEM_BORRADA: 'Imagem borrada', REENVIO_SOLICITADO: 'Reenvio solicitado', EMPREGADOR_DIVERGENTE: 'Empregador divergente',
}

export const CATEGORIAS_RISCO: Record<string, string> = {
  JORNADA: 'Jornada', REMUNERACAO: 'Remuneração', FERIAS: 'Férias', RESCISAO: 'Rescisão', REGISTRO: 'Registro do vínculo', SEGURANCA: 'Saúde e segurança',
  DOCUMENTAL: 'Qualidade documental', PROVA: 'Prova documental', TERCEIRIZACAO: 'Terceirização',
}

/** CNPJ com máscara (00.000.000/0000-00); aceita só dígitos ou já formatado. */
export const cnpjMask = (v: string) => {
  const d = (v ?? '').replace(/\D/g, '').slice(0, 14)
  return d.replace(/^(\d{2})(\d)/, '$1.$2').replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3').replace(/\.(\d{3})(\d)/, '.$1/$2').replace(/(\d{4})(\d)/, '$1-$2')
}

/** Valida os dois dígitos verificadores do CNPJ. */
export function cnpjValido(s: string) {
  const d = (s ?? '').replace(/\D/g, '')
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false
  const dv = (n: number) => {
    const pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    const r = pesos.reduce((acc, p, i) => acc + p * Number(d[i]), 0) % 11
    return r < 2 ? 0 : 11 - r
  }
  return dv(12) === Number(d[12]) && dv(13) === Number(d[13])
}

/** Exposição da contratante a processo trabalhista causado pelo fornecedor (calculada no servidor). */
export const EXPOSICAO: Record<string, { label: string; cls: string; explica: string }> = {
  ALTA: { label: 'Exposição alta', cls: 'bg-danger-bg text-danger', explica: 'Há indicador de risco alto (autuação, processo, auditoria) ou documento exigido vencido.' },
  MEDIA: { label: 'Exposição média', cls: 'bg-warning-bg text-warning', explica: 'Há indicador de risco ou documento exigido pendente.' },
  BAIXA: { label: 'Exposição baixa', cls: 'bg-success-bg text-success', explica: 'Exigências em dia e nenhum indicador aberto.' },
}
