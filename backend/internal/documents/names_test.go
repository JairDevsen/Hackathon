package documents

import "testing"

func TestNameMismatch(t *testing.T) {
	cases := []struct {
		doc, cad string
		want     bool
	}{
		{"Carlos Eduardo Silva", "CARLOS EDUARDO SILVA", false},
		{"Carlos E. Silva", "Carlos Eduardo Silva", false},     // abreviação
		{"José da Silva", "Jose Silva", false},                 // acento + partícula
		{"João José de Santos", "José João de Santos", true},   // ordem trocada (exemplo da tela)
		{"Joana de Souza Silva", "Maria Fernanda Costa", true}, // pessoas diferentes
		{"Maria Costa", "Maria Fernanda Costa", false},         // sobrenome do meio omitido
		{"Maria", "Maria Fernanda Costa", false},               // pouco texto: não acusa
	}
	for _, c := range cases {
		if got, why := NameMismatch(c.doc, c.cad); got != c.want {
			t.Errorf("NameMismatch(%q,%q)=%v (%s), want %v", c.doc, c.cad, got, why, c.want)
		}
	}
}
