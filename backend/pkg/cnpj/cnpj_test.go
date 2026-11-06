package cnpj

import "testing"

func TestValid(t *testing.T) {
	if !Valid("11.222.333/0001-81") || Valid("11.222.333/0001-82") || Valid("00000000000000") {
		t.Fatal("validação de CNPJ incorreta")
	}
}
