import { cpfMask, cpfValido, emailDomain, fmtBytes, FREE_DOMAINS } from './format'

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
})
