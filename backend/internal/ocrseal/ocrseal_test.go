package ocrseal

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func dek(b byte) []byte { return bytes.Repeat([]byte{b}, 32) }

func TestTextoNaoFicaEmClaroEAbreSoParaAEmpresaEAFinalidade(t *testing.T) {
	s := New(dek(1), "emp-a")
	sealed, err := s.Text(Texto, "CPF 458.712.903-88 MARIA")
	if err != nil || bytes.Contains(sealed, []byte("458.712")) || bytes.Contains(sealed, []byte("MARIA")) {
		t.Fatalf("texto em claro no cifrado: %v", err)
	}
	if got, err := s.OpenText(Texto, sealed); err != nil || got != "CPF 458.712.903-88 MARIA" {
		t.Fatalf("ida e volta: %q %v", got, err)
	}
	if _, err := New(dek(1), "emp-b").OpenText(Texto, sealed); err == nil {
		t.Fatal("outra empresa não pode abrir")
	}
	if _, err := New(dek(2), "emp-a").OpenText(Texto, sealed); err == nil {
		t.Fatal("outra chave não pode abrir")
	}
	if _, err := s.OpenText(Palavra, sealed); err == nil {
		t.Fatal("outra finalidade não pode abrir")
	}
	if v, err := s.PlainOrOpen(Texto, nil, "antigo"); err != nil || v != "antigo" {
		t.Fatal("linha antiga em claro deve continuar legível")
	}
	if b, _ := s.Text(Texto, ""); b != nil {
		t.Fatal("vazio não vira cifra")
	}
}

func TestAnaliseProtegeTextoECamposEMantemOResto(t *testing.T) {
	s := New(dek(3), "emp-a")
	entrada := `{"tipo":"TRCT","confianca":0.9,"camada":"Camada 1","tokens":0,"texto_ocr":"CPF 458.712.903-88","campos":{"cpf":"45871290388","nome":"MARIA"}}`
	prot, err := s.ProtectAnalise([]byte(entrada))
	if err != nil {
		t.Fatal(err)
	}
	for _, vaza := range []string{"458.712", "45871290388", "MARIA", "texto_ocr"} {
		if strings.Contains(string(prot), vaza) {
			t.Fatalf("%q ficou em claro: %s", vaza, prot)
		}
	}
	var m map[string]any
	json.Unmarshal(prot, &m)
	if m["tipo"] != "TRCT" || m["camada"] != "Camada 1" {
		t.Fatalf("o que não é sensível deve continuar legível: %s", prot)
	}
	if again, _ := s.ProtectAnalise(prot); string(again) != string(prot) {
		t.Fatal("proteger duas vezes não pode cifrar de novo")
	}
	rev, err := s.RevealAnalise(prot)
	if err != nil {
		t.Fatal(err)
	}
	var r struct {
		Texto  string            `json:"texto_ocr"`
		Campos map[string]string `json:"campos"`
		Tipo   string            `json:"tipo"`
	}
	json.Unmarshal(rev, &r)
	if r.Texto != "CPF 458.712.903-88" || r.Campos["cpf"] != "45871290388" || r.Tipo != "TRCT" {
		t.Fatalf("reconstrução: %s", rev)
	}
	if txt, _ := s.AnaliseTexto([]byte(entrada)); txt != "CPF 458.712.903-88" { // análise antiga em claro
		t.Fatal("análise antiga deve continuar legível")
	}
	if _, err := New(dek(3), "emp-b").RevealAnalise(prot); err == nil {
		t.Fatal("outra empresa não pode abrir")
	}
}
