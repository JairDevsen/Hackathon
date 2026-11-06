import { simular, FRACOES, VOLUME_PADRAO } from './finops'

describe('simulador FinOps', () => {
  it('as frações das camadas somam 100%', () => { expect(Object.values(FRACOES).reduce((a, b) => a + b, 0)).toBeCloseTo(1) })
  it('reproduz o cenário de referência (1,5 mi docs/mês)', () => {
    const r = simular(VOLUME_PADRAO)
    expect(Math.round(r.ingenuo)).toBe(4725)
    expect(Math.round(r.funil)).toBe(255)
    expect(r.economiaPct).toBeCloseTo(94.6, 1)
  })
  it('escala linearmente com o volume', () => {
    expect(simular(3_000_000).funil).toBeCloseTo(2 * simular(1_500_000).funil, 6)
  })
})
