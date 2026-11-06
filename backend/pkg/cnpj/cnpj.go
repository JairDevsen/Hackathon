// Package cnpj valida e formata CNPJs.
package cnpj

import "strings"

func Clean(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= '0' && r <= '9' {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func dv(d string, n int) int {
	w := []int{6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2}
	w = w[len(w)-n:]
	sum := 0
	for i := 0; i < n; i++ {
		sum += int(d[i]-'0') * w[i]
	}
	r := sum % 11
	if r < 2 {
		return 0
	}
	return 11 - r
}

func Valid(s string) bool {
	d := Clean(s)
	if len(d) != 14 || d == strings.Repeat(string(d[0]), 14) {
		return false
	}
	return dv(d, 12) == int(d[12]-'0') && dv(d, 13) == int(d[13]-'0')
}

func Format(s string) string {
	d := Clean(s)
	if len(d) != 14 {
		return s
	}
	return d[:2] + "." + d[2:5] + "." + d[5:8] + "/" + d[8:12] + "-" + d[12:]
}
