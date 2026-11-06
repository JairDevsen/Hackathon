package crypto

import (
	"bytes"
	"crypto/rand"
	"io"
	"strings"
	"testing"
)

func TestStreamRoundTrip(t *testing.T) {
	key := make([]byte, 32)
	rand.Read(key)
	for _, size := range []int{0, 10, segSize, segSize + 1, 3*segSize + 77} {
		plain := make([]byte, size)
		rand.Read(plain)
		var enc bytes.Buffer
		if _, err := Encrypt(&enc, bytes.NewReader(plain), key, []byte("t1")); err != nil {
			t.Fatal(err)
		}
		dr, err := Decrypt(bytes.NewReader(enc.Bytes()), key, []byte("t1"))
		if err != nil {
			t.Fatal(err)
		}
		got, err := io.ReadAll(dr)
		if err != nil || !bytes.Equal(got, plain) {
			t.Fatalf("size %d: round trip falhou: %v", size, err)
		}
		// aad errado (outro tenant) não decifra
		dr2, _ := Decrypt(bytes.NewReader(enc.Bytes()), key, []byte("t2"))
		if _, err := io.ReadAll(dr2); err == nil {
			t.Fatalf("size %d: decifrou com AAD de outra empresa", size)
		}
	}
}

func TestEnvelopeAndBlindIndex(t *testing.T) {
	kr, err := NewKeyring(strings.Repeat("ab", 32), strings.Repeat("cd", 32))
	if err != nil {
		t.Fatal(err)
	}
	dek, wrapped, _ := kr.NewDEK()
	got, err := kr.DEK("t1", wrapped)
	if err != nil || !bytes.Equal(got, dek) {
		t.Fatal("DEK não confere")
	}
	if kr.Blind("t1", "52998224725") == kr.Blind("t2", "52998224725") {
		t.Fatal("índice cego deve diferir entre empresas")
	}
}
