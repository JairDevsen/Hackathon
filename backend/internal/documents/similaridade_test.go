package documents

import (
	"math/rand"
	"strings"
	"testing"
)

const holerite = `RECIBO DE PAGAMENTO DE SALARIO HOLERITE EMPRESA APARECIDA LIMPEZA SOLUCOES LTDA CNPJ 14.589.201/0001-80
COMPETENCIA 05/2026 MATRICULA 001245 FUNCAO SERVENTE ADMISSAO 15/03/2022 SALARIO BASE R$ 2.000,00 HORAS EXTRAS 50% R$ 150,00
ADICIONAL NOTURNO R$ 120,50 VALE TRANSPORTE DESCONTO R$ 120,00 INSS R$ 187,45 IRRF R$ 12,30 FGTS DEPOSITADO R$ 180,00
TOTAL DE VENCIMENTOS R$ 2.270,50 TOTAL DE DESCONTOS R$ 319,75 LIQUIDO A RECEBER R$ 1.950,75 ASSINATURA DO EMPREGADO RECEBI A QUANTIA ACIMA`

// ruido simula outro escaneamento: erra letras, perde palavras e inventa lixo. Nos números, como num OCR real, no máximo um
// dígito sai errado (nunca perde o número nem troca dígito por letra).
func ruido(texto string, taxa float64, seed int64) string {
	r := rand.New(rand.NewSource(seed))
	var out []string
	for _, p := range strings.Fields(texto) {
		x := r.Float64()
		if strings.ContainsAny(p, "0123456789") {
			if x < taxa/2 { // um dígito errado
				b := []byte(p)
				for k := 0; k < 8; k++ {
					if i := r.Intn(len(b)); b[i] >= '0' && b[i] <= '9' {
						b[i] = '0' + (b[i]-'0'+1)%10
						break
					}
				}
				p = string(b)
			}
		} else if x < taxa/3 { // palavra perdida
			continue
		} else if x < 2*taxa/3 && len(p) > 3 { // letra trocada
			b := []byte(p)
			b[r.Intn(len(b))] = 'x'
			p = string(b)
		}
		out = append(out, p)
		if r.Float64() < taxa/2 {
			out = append(out, "|", "e") // lixo
		}
	}
	return strings.Join(out, " ")
}

func TestMesmoDocumentoEscaneadoDeFormasDiferentesEDuplicado(t *testing.T) {
	for seed, taxa := range map[int64]float64{1: 0.05, 2: 0.10, 3: 0.15} {
		c := Comparar(holerite, ruido(holerite, taxa, seed))
		if !c.Duplicado(0.85) {
			t.Errorf("taxa de erro %.0f%%: deveria ser duplicado (texto %.2f, valores %.2f)", taxa*100, c.Texto, c.Valores)
		}
	}
}

func TestDocumentosDiferentesNaoSaoDuplicados(t *testing.T) {
	outro := `CERTIDAO NEGATIVA DE DEBITOS TRABALHISTAS CNDT JUSTICA DO TRABALHO EMPRESA APARECIDA LIMPEZA SOLUCOES LTDA CNPJ 14.589.201/0001-80
CERTIFICA QUE NAO CONSTA DEBITO INSCRITO NO BANCO NACIONAL DE DEVEDORES TRABALHISTAS EXPEDIDA EM 02/06/2026 VALIDA ATE 29/11/2026
ESTA CERTIDAO FOI EMITIDA GRATUITAMENTE E SUA AUTENTICIDADE PODE SER CONFIRMADA NO SITE DO TRIBUNAL SUPERIOR DO TRABALHO`
	if Comparar(holerite, outro).Duplicado(0.70) {
		t.Error("tipos de documento diferentes não podem ser duplicados nem no limite mínimo")
	}
}

func TestMesmoModeloComValoresDiferentesNaoEDuplicado(t *testing.T) {
	// o mesmo holerite, com a competência e os valores de outro mês: quase todas as palavras são iguais
	outro := strings.NewReplacer("05/2026", "06/2026", "2.000,00", "2.150,00", "150,00", "310,00", "120,50", "98,20", "187,45", "201,10", "2.270,50", "2.558,20", "319,75", "331,40", "1.950,75", "2.226,80", "180,00", "204,00").Replace(holerite)
	c := Comparar(holerite, outro)
	if c.Texto < 0.9 {
		t.Fatalf("premissa do teste: as palavras são quase as mesmas (texto %.2f)", c.Texto)
	}
	if c.Duplicado(0.85) {
		t.Errorf("valores diferentes (valores %.2f) não podem ser o mesmo documento", c.Valores)
	}
}

func TestLimiteDoClienteDecide(t *testing.T) {
	c := Comparar(holerite, ruido(holerite, 0.25, 7))
	if !(c.Texto > 0.6 && c.Texto < 0.95) {
		t.Skipf("ruído gerou similaridade fora da faixa de interesse: %.2f", c.Texto)
	}
	if c.Duplicado(0.99) {
		t.Error("com limite de 99% um escaneamento com muito erro não deve ser duplicado")
	}
	if !c.Duplicado(c.Texto-0.01) && c.Valores >= c.Texto-0.16 {
		t.Error("um limite logo abaixo da similaridade deve aceitar")
	}
}

func TestTextoCurtoNaoDecide(t *testing.T) {
	if Comparar("DOCUMENTO CURTO ASSINADO", "DOCUMENTO CURTO ASSINADO").Duplicado(0.85) {
		t.Error("texto com poucas palavras não prova que dois documentos são o mesmo")
	}
}

func TestVersaoRetificadaComPoucosValoresDiferentesNaoEDuplicado(t *testing.T) {
	// mesma competência, mesmo modelo, mas três valores diferentes: é outra via (retificada), não a mesma digitalizada de novo
	retificada := strings.NewReplacer("2.000,00", "2.150,00", "150,00", "310,00", "1.950,75", "2.226,80").Replace(holerite)
	c := Comparar(holerite, retificada)
	if c.Duplicado(0.85) {
		t.Errorf("versão retificada não pode ser descartada (texto %.2f, valores divergentes %.1f)", c.Texto, c.ValoresDivergentes)
	}
	if !Comparar(holerite, ruido(holerite, 0.10, 5)).Duplicado(0.85) {
		t.Error("o mesmo documento com erro de OCR continua sendo duplicado")
	}
}

func TestConfusaoDeDigitoPorLetraNoOCRNaoQuebraAPalavra(t *testing.T) {
	palavras, valores := tokensDoTexto("ASS1NATURA DO EMPREGADO L1QUIDO A RECEBER R$ 1.950,75 COMPETENCIA 05/2026 PROT A5A3956E36")
	for _, esperada := range []string{"ASSINATURA", "LIQUIDO", "EMPREGADO", "RECEBER"} {
		achou := false
		for _, p := range palavras {
			achou = achou || p == esperada
		}
		if !achou {
			t.Errorf("palavra %q não reconhecida em %v", esperada, palavras)
		}
	}
	if len(valores) != 3 || valores[0] != "195075" || valores[1] != "052026" {
		t.Errorf("valores = %v; esperado 195075, 052026 e o código", valores)
	}
}
