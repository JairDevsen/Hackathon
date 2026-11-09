import { chaveEmpresa, cnpjMask, cnpjValido, cpfMask, cpfValido, emailDomain, fmtBytes, FREE_DOMAINS } from './format'

describe('format', () => {
  it('valida CPF pelos dígitos verificadores', () => {
    expect(cpfValido('529.982.247-25')).toBe(true)
    expect(cpfValido('52998224725')).toBe(true)
    expect(cpfValido('111.111.111-11')).toBe(false)
    expect(cpfValido('529.982.247-24')).toBe(false)
  })
  it('aplica máscara de CPF enquanto digita', () => { expect(cpfMask('52998224725')).toBe('529.982.247-25'); expect(cpfMask('5299')).toBe('529.9') })
  it('formata bytes', () => { expect(fmtBytes(0)).toBe('0 B'); expect(fmtBytes(1536)).toBe('1,5 KB') })
  it('bloqueia domínios gratuitos', () => { expect(FREE_DOMAINS).toContain(emailDomain('x@Gmail.com')) })
  it('valida e mascara CNPJ', () => {
    expect(cnpjValido('11.222.333/0001-81')).toBe(true)
    expect(cnpjValido('11222333000181')).toBe(true)
    expect(cnpjValido('14.589.201/0001-80')).toBe(true)
    expect(cnpjValido('11.222.333/0001-80')).toBe(false)
    expect(cnpjValido('00000000000000')).toBe(false)
    expect(cnpjValido('1122233300018')).toBe(false)
    expect(cnpjMask('11222333000181')).toBe('11.222.333/0001-81')
    expect(cnpjMask('112223')).toBe('11.222.3')
    expect(cnpjMask('')).toBe('')
  })
})

describe('chaveEmpresa', () => {
  it('junta a mesma empresa escrita de jeitos diferentes', () => {
    const a = chaveEmpresa('Aparecida Limpeza Soluções Ltda')
    for (const v of ['APARECIDA LIMPEZA SOLUCOES LTDA', 'APARECIDA LIMPEZA SOLUÇÕES LTDA', 'aparecida limpeza soluções', 'Aparecida Limpeza Soluções S/A']) expect(chaveEmpresa(v)).toBe(a)
    expect(chaveEmpresa('APARECIDA LIMPEZA DOMÉSTICA')).not.toBe(a)
    expect(chaveEmpresa(undefined)).toBe('')
  })
})
