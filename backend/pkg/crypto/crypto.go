// Package crypto: criptografia por envelope (KEK → DEK por empresa) com AES-256-GCM,
// cifragem em streaming para arquivos grandes e HMAC para índices cegos (CPF).
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"sync"
)

type Keyring struct {
	kek     []byte // 32 bytes: protege as DEKs
	hmacKey []byte // 32 bytes: base dos HMACs
	mu      sync.RWMutex
	cache   map[string][]byte
}

// NewKeyring recebe chaves em hex (64 caracteres).
func NewKeyring(kekHex, hmacHex string) (*Keyring, error) {
	kek, err := hex.DecodeString(kekHex)
	if err != nil || len(kek) != 32 {
		return nil, errors.New("KEK_HEX deve ter 64 caracteres hexadecimais (32 bytes)")
	}
	h, err := hex.DecodeString(hmacHex)
	if err != nil || len(h) != 32 {
		return nil, errors.New("HMAC_KEY_HEX deve ter 64 caracteres hexadecimais (32 bytes)")
	}
	return &Keyring{kek: kek, hmacKey: h, cache: map[string][]byte{}}, nil
}

func newGCM(key []byte) (cipher.AEAD, error) {
	b, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(b)
}

// Seal cifra um valor pequeno: nonce || ciphertext.
func Seal(key, plain, aad []byte) ([]byte, error) {
	g, err := newGCM(key)
	if err != nil {
		return nil, err
	}
	n := make([]byte, g.NonceSize())
	if _, err := rand.Read(n); err != nil {
		return nil, err
	}
	return g.Seal(n, n, plain, aad), nil
}

func Open(key, sealed, aad []byte) ([]byte, error) {
	g, err := newGCM(key)
	if err != nil {
		return nil, err
	}
	if len(sealed) < g.NonceSize() {
		return nil, errors.New("dado cifrado inválido")
	}
	return g.Open(nil, sealed[:g.NonceSize()], sealed[g.NonceSize():], aad)
}

// NewDEK gera a chave de dados de uma empresa e devolve a versão protegida pela KEK.
func (k *Keyring) NewDEK() (dek, wrapped []byte, err error) {
	dek = make([]byte, 32)
	if _, err = rand.Read(dek); err != nil {
		return
	}
	wrapped, err = Seal(k.kek, dek, []byte("dek"))
	return
}

// DEK devolve (com cache) a chave de dados descriptografada.
func (k *Keyring) DEK(tenantID string, wrapped []byte) ([]byte, error) {
	k.mu.RLock()
	d, ok := k.cache[tenantID]
	k.mu.RUnlock()
	if ok {
		return d, nil
	}
	d, err := Open(k.kek, wrapped, []byte("dek"))
	if err != nil {
		return nil, fmt.Errorf("DEK inválida (KEK trocada?): %w", err)
	}
	k.mu.Lock()
	k.cache[tenantID] = d
	k.mu.Unlock()
	return d, nil
}

// Blind gera o índice cego (HMAC-SHA256) por empresa: igual para o mesmo CPF dentro da empresa,
// diferente entre empresas.
func (k *Keyring) Blind(tenantID, value string) string {
	m := hmac.New(sha256.New, k.hmacKey)
	m.Write([]byte("tenant:" + tenantID + "|"))
	m.Write([]byte(value))
	return hex.EncodeToString(m.Sum(nil))
}

// HMAC genérico (assinaturas de URL, callbacks).
func HMAC(key []byte, data ...[]byte) []byte {
	m := hmac.New(sha256.New, key)
	for _, d := range data {
		m.Write(d)
	}
	return m.Sum(nil)
}

func Equal(a, b []byte) bool { return hmac.Equal(a, b) }

// ---- Cifragem em streaming (segmentos de 1 MiB) ----
// formato: "CTL1" | prefixo de nonce (8 B) | { len(4 B, big-endian) | segmento cifrado }*
const segSize = 1 << 20

var magic = []byte("CTL1")

// Encrypt lê r até EOF e escreve o conteúdo cifrado em w. Devolve bytes de plaintext lidos.
func Encrypt(w io.Writer, r io.Reader, key, aad []byte) (int64, error) {
	g, err := newGCM(key)
	if err != nil {
		return 0, err
	}
	prefix := make([]byte, 8)
	if _, err := rand.Read(prefix); err != nil {
		return 0, err
	}
	if _, err := w.Write(append(append([]byte{}, magic...), prefix...)); err != nil {
		return 0, err
	}
	buf := make([]byte, segSize)
	var total int64
	for ctr := uint32(0); ; ctr++ {
		n, rerr := io.ReadFull(r, buf)
		if n > 0 {
			nonce := make([]byte, 12)
			copy(nonce, prefix)
			binary.BigEndian.PutUint32(nonce[8:], ctr)
			last := byte(0)
			if rerr == io.EOF || rerr == io.ErrUnexpectedEOF {
				last = 1
			}
			ct := g.Seal(nil, nonce, buf[:n], append(append([]byte{}, aad...), last))
			hdr := make([]byte, 5)
			binary.BigEndian.PutUint32(hdr, uint32(len(ct)))
			hdr[4] = last
			if _, err := w.Write(hdr); err != nil {
				return total, err
			}
			if _, err := w.Write(ct); err != nil {
				return total, err
			}
			total += int64(n)
		}
		if rerr == io.EOF || rerr == io.ErrUnexpectedEOF {
			if n == 0 { // arquivo vazio ou múltiplo exato: segmento final vazio marca o fim
				nonce := make([]byte, 12)
				copy(nonce, prefix)
				binary.BigEndian.PutUint32(nonce[8:], ctr)
				ct := g.Seal(nil, nonce, nil, append(append([]byte{}, aad...), 1))
				hdr := make([]byte, 5)
				binary.BigEndian.PutUint32(hdr, uint32(len(ct)))
				hdr[4] = 1
				w.Write(hdr)
				w.Write(ct)
			}
			return total, nil
		}
		if rerr != nil {
			return total, rerr
		}
	}
}

type decReader struct {
	r      io.Reader
	g      cipher.AEAD
	prefix []byte
	aad    []byte
	ctr    uint32
	buf    []byte
	done   bool
}

// Decrypt devolve um leitor que decifra e autentica segmento a segmento (detecta truncamento).
func Decrypt(r io.Reader, key, aad []byte) (io.Reader, error) {
	g, err := newGCM(key)
	if err != nil {
		return nil, err
	}
	head := make([]byte, 12)
	if _, err := io.ReadFull(r, head); err != nil || string(head[:4]) != string(magic) {
		return nil, errors.New("arquivo cifrado inválido")
	}
	return &decReader{r: r, g: g, prefix: head[4:], aad: aad}, nil
}

func (d *decReader) Read(p []byte) (int, error) {
	for len(d.buf) == 0 {
		if d.done {
			return 0, io.EOF
		}
		hdr := make([]byte, 5)
		if _, err := io.ReadFull(d.r, hdr); err != nil {
			return 0, errors.New("arquivo cifrado truncado")
		}
		ct := make([]byte, binary.BigEndian.Uint32(hdr))
		if _, err := io.ReadFull(d.r, ct); err != nil {
			return 0, errors.New("arquivo cifrado truncado")
		}
		nonce := make([]byte, 12)
		copy(nonce, d.prefix)
		binary.BigEndian.PutUint32(nonce[8:], d.ctr)
		pt, err := d.g.Open(nil, nonce, ct, append(append([]byte{}, d.aad...), hdr[4]))
		if err != nil {
			return 0, errors.New("falha de autenticação do arquivo cifrado")
		}
		d.ctr++
		d.buf = pt
		d.done = hdr[4] == 1
	}
	n := copy(p, d.buf)
	d.buf = d.buf[n:]
	return n, nil
}
