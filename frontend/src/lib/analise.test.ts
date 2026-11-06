import { nivelDoc, problemas, resumo } from './analise'

const base = { alertas: [], checklist: [], motivos_revisao: [], status: 'AUTO_APROVADO' }

describe('classificação da análise', () => {
  it('documento sem problemas é aprovado', () => { expect(nivelDoc(base)).toBe('aprovado') })
  it('alerta de erro (documento vencido) vira "com erro"', () => {
    const d = { ...base, alertas: [{ codigo: 'DOCUMENTO_VENCIDO', severidade: 'erro', mensagem: 'Documento vencido em 2004-11-07' }] }
    expect(nivelDoc(d)).toBe('erro'); expect(problemas(d)[0].titulo).toBe('Documento vencido')
  })
  it('imagem borrada e dados divergentes têm títulos próprios', () => {
    const d = { ...base, alertas: [{ codigo: 'IMAGEM_BORRADA', severidade: 'erro', mensagem: 'Envie uma imagem mais nítida.' }, { codigo: 'DADOS_DIVERGENTES', severidade: 'aviso', mensagem: 'nomes diferentes' }] }
    expect(problemas(d).map((p) => p.titulo).sort()).toEqual(['Dados divergentes', 'Imagem borrada'])
  })
  it('só aviso ou aguardando revisão = precisa de atenção; falha de checklist = erro', () => {
    expect(nivelDoc({ ...base, status: 'AGUARDANDO_REVISAO' })).toBe('atencao')
    expect(nivelDoc({ ...base, alertas: [{ codigo: 'CPF_INVALIDO', severidade: 'aviso', mensagem: 'x' }] })).toBe('atencao')
    expect(nivelDoc({ ...base, checklist: [{ regra: 'NR-07 · Periodicidade', status: 'FALHA', detalhe: 'vencido' }] })).toBe('erro')
  })
  it('o mesmo problema como aviso e erro prevalece como erro; resumo conta os três níveis', () => {
    const d = { ...base, alertas: [{ codigo: 'X', severidade: 'aviso', mensagem: 'a' }, { codigo: 'X', severidade: 'erro', mensagem: 'b' }] }
    expect(problemas(d)).toHaveLength(1); expect(nivelDoc(d)).toBe('erro')
    expect(resumo([base, d, { ...base, status: 'AGUARDANDO_REVISAO' }])).toEqual({ total: 3, aprovado: 1, atencao: 1, erro: 1 })
  })
  it('alerta informativo (pré-cadastro automático) não conta como problema', () => {
    const d = { ...base, alertas: [{ codigo: 'PRE_CADASTRO', severidade: 'info', mensagem: 'Funcionário pré-cadastrado a partir do documento' }] }
    expect(problemas(d)).toEqual([]); expect(nivelDoc(d)).toBe('aprovado')
  })
})
