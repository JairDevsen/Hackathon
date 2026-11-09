package batches

import (
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

func TestPageHashImagemETextoEmbutido(t *testing.T) {
	img := sha256.Sum256([]byte("pixels da página"))
	puro := hex.EncodeToString(img[:])
	if PageHash(img[:], "") != puro {
		t.Fatal("sem texto embutido o hash é o SHA-256 puro da imagem")
	}
	a, b := PageHash(img[:], "VALOR 100,00"), PageHash(img[:], "VALOR 900,00")
	if a == b || a == puro || b == puro {
		t.Fatal("a mesma imagem com outro texto embutido precisa gerar outra chave de cache")
	}
	if a != PageHash(img[:], "VALOR 100,00") {
		t.Fatal("o hash precisa ser estável")
	}
	outra := sha256.Sum256([]byte("pixels da página."))
	if PageHash(outra[:], "VALOR 100,00") == a {
		t.Fatal("outra imagem precisa gerar outra chave")
	}
}
