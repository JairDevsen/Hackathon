package documents

import (
	"regexp"
	"strings"
	"unicode"

	"golang.org/x/text/transform"
)

// Similaridade de conteúdo entre dois documentos, a partir do texto lido por OCR.
//
// O mesmo documento escaneado duas vezes gera textos parecidos, mas não idênticos: o OCR erra letras, perde palavras e inventa
// ruído. Por isso a comparação é por PALAVRAS com tolerância a erro de leitura, e não por texto exato. Como modelos de
// documento parecem muito entre si (um holerite de março e o de abril têm quase as mesmas palavras), os VALORES (números e
// datas) são comparados à parte: duas versões com valores diferentes não são a mesma via.

const (
	minTokensComparacao = 15   // abaixo disso o texto é curto demais para dizer que dois documentos são o mesmo...
	minTokensIdentico   = 8    // ...salvo se o texto for IDÊNTICO: aí poucas palavras bastam
	minValoresParaTrava = 3    // com menos valores que isso a trava de valores não decide
	limiteTrechoFuzzy   = 500  // protege o custo da comparação aproximada
	razaoFuzzy          = 0.75 // semelhança mínima entre duas palavras para valerem como "a mesma lida com erro"
)

var apenasAlnum = regexp.MustCompile(`[^A-Z0-9]+`)

// confusões típicas de OCR entre dígito e letra, ao ler uma PALAVRA ("ASS1NATURA" é "ASSINATURA")
var digitoParaLetra = strings.NewReplacer("0", "O", "1", "I", "5", "S", "8", "B", "6", "G", "2", "Z")

// tokens do texto: maiúsculas, sem acento. Cada pedaço entre espaços é uma PALAVRA, um VALOR ou um código:
//   - só letras (ou letras com pontuação): palavra;
//   - só dígitos e separadores ("2.000,00", "05/2026", "14.589.201/0001-80"): valor, guardado só com os dígitos;
//   - letras e dígitos misturados: se as letras dominam, é palavra com dígito trocado por OCR; senão, é um código (valor).
//
// Descarta palavras de 1 caractere (ruído típico de OCR).
func tokensDoTexto(texto string) (palavras, valores []string) {
	s, _, _ := transform.String(semAcento, strings.ToUpper(texto))
	for _, bruto := range strings.Fields(s) {
		t := strings.TrimPrefix(strings.Trim(bruto, ".,;:()[]{}|\"'*-_/\\"), "R$")
		letras, digitos := 0, 0
		for _, r := range t {
			switch {
			case unicode.IsLetter(r):
				letras++
			case unicode.IsDigit(r):
				digitos++
			}
		}
		switch {
		case letras == 0 && digitos > 0:
			if v := soDigitos(t); len(v) >= 2 {
				valores = append(valores, v)
			}
		case digitos == 0 || float64(letras)/float64(letras+digitos) >= 0.6:
			if digitos > 0 {
				t = digitoParaLetra.Replace(t)
			}
			for _, p := range apenasAlnum.Split(t, -1) {
				if pareceUmaPalavra(p) {
					palavras = append(palavras, p)
				}
			}
		default:
			valores = append(valores, apenasAlnum.ReplaceAllString(t, ""))
		}
	}
	return palavras, valores
}

// pareceUmaPalavra descarta o lixo típico do OCR (rabiscos lidos como "TT", "DD", "jmmsm"): pedaços de 1 a 2 letras e pedaços sem
// nenhuma vogal. Esse lixo aparece só de um lado e derruba a similaridade sem dizer nada sobre o conteúdo do documento.
func pareceUmaPalavra(p string) bool {
	if len(p) < 3 {
		return false
	}
	return strings.ContainsAny(p, "AEIOU")
}

// valoresRelevantes: só os valores que distinguem uma via de outra (quantias, datas, documentos: 4 ou mais dígitos). Números
// pequenos ("12", "08", horas e quantidades em tabelas) são os que o OCR mais erra e quase nunca diferenciam duas vias.
func valoresRelevantes(v []string) []string {
	out := make([]string, 0, len(v))
	for _, x := range v {
		if len(x) >= 4 {
			out = append(out, x)
		}
	}
	return out
}

func soDigitos(s string) string {
	var b strings.Builder
	for _, r := range s {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// distancia de edição, com corte: devolve max+1 quando passa de max.
func distancia(a, b string, max int) int {
	if abs(len(a)-len(b)) > max {
		return max + 1
	}
	prev := make([]int, len(b)+1)
	cur := make([]int, len(b)+1)
	for j := range prev {
		prev[j] = j
	}
	for i := 1; i <= len(a); i++ {
		cur[0] = i
		menor := cur[0]
		for j := 1; j <= len(b); j++ {
			custo := 1
			if a[i-1] == b[j-1] {
				custo = 0
			}
			cur[j] = min3(prev[j]+1, cur[j-1]+1, prev[j-1]+custo)
			if cur[j] < menor {
				menor = cur[j]
			}
		}
		if menor > max {
			return max + 1
		}
		prev, cur = cur, prev
	}
	return prev[len(b)]
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

func min3(a, b, c int) int {
	m := a
	if b < m {
		m = b
	}
	if c < m {
		m = c
	}
	return m
}

// dice entre dois conjuntos de tokens (multiconjuntos): 2·casados/(|A|+|B|). Primeiro casa os iguais; o que sobra casa por
// semelhança, para absorver erros de OCR. `tolerancia` é o nº máximo de caracteres de diferença aceito numa palavra comparada
// aproximadamente (0 = só exata).
func dice(a, b []string, aproximado bool, maxErros int) (float64, float64) {
	if len(a) == 0 && len(b) == 0 {
		return 1, 0
	}
	if len(a) == 0 || len(b) == 0 {
		return 0, 0
	}
	contagem := map[string]int{}
	for _, t := range b {
		contagem[t]++
	}
	var sobraA []string
	casados := 0.0
	for _, t := range a {
		if contagem[t] > 0 {
			contagem[t]--
			casados++
		} else {
			sobraA = append(sobraA, t)
		}
	}
	if aproximado && len(sobraA) > 0 {
		var sobraB []string
		for t, n := range contagem {
			for ; n > 0; n-- {
				sobraB = append(sobraB, t)
			}
		}
		if len(sobraA) > limiteTrechoFuzzy {
			sobraA = sobraA[:limiteTrechoFuzzy]
		}
		if len(sobraB) > limiteTrechoFuzzy {
			sobraB = sobraB[:limiteTrechoFuzzy]
		}
		usado := make([]bool, len(sobraB))
		for _, x := range sobraA {
			melhor, melhorR := -1, 0.0
			for j, y := range sobraB {
				if usado[j] {
					continue
				}
				m := len(x)
				if len(y) > m {
					m = len(y)
				}
				erros := maxErros
				if maxErros < 0 { // proporcional ao tamanho da palavra
					erros = int(float64(m) * (1 - razaoFuzzy))
				}
				if m < 4 && maxErros < 0 {
					continue // palavra curta: ou é exata, ou é outra
				}
				if d := distancia(x, y, erros); d <= erros {
					if r := 1 - float64(d)/float64(m); r > melhorR {
						melhor, melhorR = j, r
					}
				}
			}
			if melhor >= 0 {
				usado[melhor] = true
				casados += melhorR
			}
		}
	}
	return 2 * casados / float64(len(a)+len(b)), casados
}

// Comparacao: resultado de comparar o texto de dois documentos.
type Comparacao struct {
	Texto   float64 // similaridade das palavras (0 a 1)
	Valores float64 // similaridade dos números e datas (0 a 1)
	// ValoresDivergentes: quantos números/datas de um documento não têm par no outro (já descontado o erro de um dígito)
	ValoresDivergentes float64
	NValores           int // quantos valores o MAIOR dos dois tem
	Tokens             int // quantas palavras o menor dos dois tem
}

// Comparar mede o quanto dois textos lidos por OCR são o mesmo conteúdo.
func Comparar(a, b string) Comparacao {
	pa, va := tokensDoTexto(a)
	pb, vb := tokensDoTexto(b)
	nv := len(va)
	if len(vb) > nv {
		nv = len(vb)
	}
	np := len(pa)
	if len(pb) < np {
		np = len(pb)
	}
	va, vb = valoresRelevantes(va), valoresRelevantes(vb)
	nv = len(va)
	if len(vb) > nv {
		nv = len(vb)
	}
	texto, _ := dice(pa, pb, true, -1)
	valores, casados := dice(va, vb, true, 1) // um dígito lido errado ainda vale; valores realmente diferentes (2.000,00 × 2.150,00) não
	return Comparacao{Texto: texto, Valores: valores, ValoresDivergentes: float64(nv) - casados, NValores: nv, Tokens: np}
}

// Duplicado diz se a comparação indica o MESMO documento, dado o limite do cliente (0,70 a 1,00). Exige texto suficiente para
// comparar e que os VALORES (números e datas) coincidam. Esta trava NÃO depende do limite do cliente: valores diferentes são
// outro documento (ex.: uma versão retificada), por mais que o modelo seja igual. Só se tolera a divergência que o erro de
// OCR explica: até 2 valores (ou 8% dos valores, o que for maior), já descontado o erro de um dígito.
func (c Comparacao) Duplicado(limite float64) bool {
	minimo := minTokensComparacao
	if c.Texto >= 0.999 {
		minimo = minTokensIdentico
	}
	if c.Tokens < minimo || c.Texto < limite {
		return false
	}
	if c.NValores < minValoresParaTrava {
		return true
	}
	tolerados := 0.08 * float64(c.NValores)
	if tolerados < 2 {
		tolerados = 2
	}
	return c.ValoresDivergentes <= tolerados+1e-9
}
