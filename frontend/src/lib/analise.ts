/** Classificação do resultado da análise: cada documento vira aprovado, "precisa de atenção" ou "com erro". */
export type Nivel = 'aprovado' | 'atencao' | 'erro'
export interface Problema { codigo: string; titulo: string; texto: string; nivel: Exclude<Nivel, 'aprovado'> }

const TITULOS: Record<string, string> = {
  DOCUMENTO_VENCIDO: 'Documento vencido', CERTIDAO_VENCIDA: 'Certidão vencida', IMAGEM_BORRADA: 'Imagem borrada', DADOS_DIVERGENTES: 'Dados divergentes',
  CPF_INVALIDO: 'CPF inválido', CPF_DIVERGENTE: 'CPF divergente', POSSIVEL_DUPLICATA: 'Possível duplicata', DOCUMENTO_SEM_ASSINATURA: 'Documento sem assinatura', JORNADA_ACIMA_10H: 'Jornada acima de 10 horas',
  INTERVALO_INFERIOR_1H: 'Intervalo menor que 1 hora', FGTS_DIVERGENTE: 'FGTS divergente', PONTO_BRITANICO: 'Ponto britânico', RECUSA_SEM_TESTEMUNHAS: 'Recusa sem testemunhas',
}
const MOTIVOS: Record<string, [string, string, 'atencao' | 'erro']> = {
  SEM_VINCULO: ['Sem vínculo', 'Não foi possível ligar este documento a um funcionário cadastrado.', 'atencao'],
  BAIXA_CONFIANCA: ['Baixa confiança', 'A leitura automática ficou abaixo do limiar de confiança da empresa.', 'atencao'],
  PAGINA_ILEGIVEL: ['Página ilegível', 'Não foi possível ler o conteúdo desta página.', 'erro'],
  TIPO_OUTRO: ['Tipo não identificado', 'O documento não foi reconhecido em nenhum tipo do catálogo.', 'atencao'],
  MULTIPLOS_DOCUMENTOS: ['Mais de um documento na imagem', 'A imagem parece conter mais de um documento.', 'atencao'],
  VINCULO_POR_NOME: ['Vínculo só pelo nome', 'O funcionário foi encontrado apenas pelo nome: confirme.', 'atencao'],
  TRANSCRICAO_MANUAL: ['Transcrição manual', 'Os campos foram informados por uma pessoa; uma cópia legível ainda é necessária para comprovação.', 'atencao'],
  LIMITE_FUNCIONARIOS: ['Limite do plano', 'O limite de funcionários impediu o pré-cadastro; confira o plano da empresa.', 'atencao'],
}

export function problemas(d: any): Problema[] {
  const out = new Map<string, Problema>()
  const add = (p: Problema) => { const cur = out.get(p.codigo); if (!cur || (cur.nivel === 'atencao' && p.nivel === 'erro')) out.set(p.codigo, p) }
  for (const a of d.alertas ?? []) if (a.severidade !== 'info') add({ codigo: a.codigo, titulo: TITULOS[a.codigo] ?? a.codigo.replaceAll('_', ' ').toLowerCase().replace(/^./, (c: string) => c.toUpperCase()), texto: a.mensagem, nivel: a.severidade === 'erro' ? 'erro' : 'atencao' })
  for (const c of d.checklist ?? []) {
    if (c.status === 'FALHA') add({ codigo: 'CK:' + c.regra, titulo: c.regra, texto: c.detalhe, nivel: 'erro' })
    else if (c.status === 'ALERTA' || c.status === 'REVISAO_HUMANA') add({ codigo: 'CK:' + c.regra, titulo: c.regra, texto: c.detalhe, nivel: 'atencao' })
  }
  for (const m of d.motivos_revisao ?? []) {
    const x = MOTIVOS[m]
    if (x && !out.has(m)) add({ codigo: m, titulo: x[0], texto: x[1], nivel: x[2] })
  }
  return [...out.values()]
}

export function nivelDoc(d: any): Nivel {
  const ps = problemas(d)
  if (ps.some((p) => p.nivel === 'erro')) return 'erro'
  if (ps.length || d.status === 'AGUARDANDO_REVISAO') return 'atencao'
  return 'aprovado'
}

export function resumo(docs: any[]) {
  const r = { total: docs.length, aprovado: 0, atencao: 0, erro: 0 }
  for (const d of docs) r[nivelDoc(d)]++
  return r
}
