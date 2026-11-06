// Package cpf valida, normaliza e mascara CPFs.
package cpf

import "strings"

// Clean remove tudo que não é dígito.
func Clean(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func digit(d string, n int) int {
	sum := 0
	for i := 0; i < n; i++ {
		sum += int(d[i]-'0') * (n + 1 - i)
	}
	r := (sum * 10) % 11
	if r == 10 {
		r = 0
	}
	return r
}

// Valid confere tamanho, repetição e dígitos verificadores.
func Valid(s string) bool {
	d := Clean(s)
	if len(d) != 11 || d == strings.Repeat(string(d[0]), 11) {
		return false
	}
	return digit(d, 9) == int(d[9]-'0') && digit(d, 10) == int(d[10]-'0')
}

// Format devolve 000.000.000-00.
func Format(s string) string {
	d := Clean(s)
	if len(d) != 11 {
		return s
	}
	return d[:3] + "." + d[3:6] + "." + d[6:9] + "-" + d[9:]
}

// Mask devolve ***.456.789-** (exibição para quem não precisa ver o número inteiro).
func Mask(s string) string {
	d := Clean(s)
	if len(d) != 11 {
		return "***.***.***-**"
	}
	return "***." + d[3:6] + "." + d[6:9] + "-**"
}

// Looks reconhece se o texto digitado parece um CPF (11 dígitos, com ou sem máscara).
func Looks(s string) bool {
	d := Clean(s)
	if len(d) != 11 {
		return false
	}
	for _, r := range s {
		if (r < '0' || r > '9') && r != '.' && r != '-' && r != ' ' {
			return false
		}
	}
	return true
}
