/** Simulador de custo do funil de 4 camadas. As premissas são do cenário (editáveis): NÃO são preços oficiais. */
export interface Premissas { custoIngenuoPorDoc: number; custoCamada2PorDoc: number; custoCamada3PorDoc: number }
export const FRACOES = { c0: 0.30, c1: 0.45, c2: 0.15, c3: 0.10 } as const
// calibradas para o cenário de referência: 1,5 mi docs/mês → ~US$ 4.725 (100% visão) vs ~US$ 255 (funil)
export const PREMISSAS_PADRAO: Premissas = { custoIngenuoPorDoc: 0.00315, custoCamada2PorDoc: 0.000015, custoCamada3PorDoc: 0.0016775 }
export const VOLUME_PADRAO = 1_500_000

export function simular(volume: number, p: Premissas = PREMISSAS_PADRAO) {
  const docs = { c0: volume * FRACOES.c0, c1: volume * FRACOES.c1, c2: volume * FRACOES.c2, c3: volume * FRACOES.c3 }
  const custo = { c0: 0, c1: 0, c2: docs.c2 * p.custoCamada2PorDoc, c3: docs.c3 * p.custoCamada3PorDoc }
  const funil = custo.c0 + custo.c1 + custo.c2 + custo.c3
  const ingenuo = volume * p.custoIngenuoPorDoc
  return { docs, custo, funil, ingenuo, economiaPct: ingenuo ? (100 * (ingenuo - funil)) / ingenuo : 0 }
}
