package documents

import (
	"strings"
	"unicode"

	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

var particles = map[string]bool{"de": true, "da": true, "do": true, "dos": true, "das": true, "e": true}

func nameTokens(s string) []string {
	t := transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)
	f, _, _ := transform.String(t, strings.ToLower(s))
	var out []string
	for _, w := range strings.FieldsFunc(f, func(r rune) bool { return !unicode.IsLetter(r) }) {
		if !particles[w] {
			out = append(out, w)
		}
	}
	return out
}

func tokenMatch(a, b string) bool {
	return a == b || (len(a) == 1 && strings.HasPrefix(b, a)) || (len(b) == 1 && strings.HasPrefix(a, b)) // inicial = nome abreviado
}

// NameMismatch compara o nome lido no documento com o do cadastro. Aceita abreviações ("Carlos E. Silva") e
// partículas; aponta nomes diferentes e também a MESMA composição em ordem trocada ("João José" × "José João").
func NameMismatch(doc, cadastro string) (bool, string) {
	a, b := nameTokens(doc), nameTokens(cadastro)
	if len(a) < 2 || len(b) < 2 {
		return false, "" // pouco texto para comparar com segurança
	}
	matched, lastIdx, inOrder := 0, -1, true
	for _, x := range a {
		for j, y := range b {
			if tokenMatch(x, y) {
				matched++
				if j < lastIdx {
					inOrder = false
				}
				lastIdx = j
				break
			}
		}
	}
	shorter := len(a)
	if len(b) < shorter {
		shorter = len(b)
	}
	score := float64(matched) / float64(shorter) // o nome mais curto deve estar contido no mais longo
	switch {
	case score < 0.8:
		return true, "nomes diferentes"
	case !inOrder:
		return true, "mesmos nomes em ordem diferente"
	}
	return false, ""
}
