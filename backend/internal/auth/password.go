package auth

import (
	"crypto/rand"
	"crypto/sha1"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"golang.org/x/crypto/argon2"
)

// Parâmetros versionados: m=64 MiB (≥ 64 MB), t=3, p=2.
const (
	argonM uint32 = 64 * 1024
	argonT uint32 = 3
	argonP uint8  = 2
)

func HashPassword(pw string) string {
	salt := make([]byte, 16)
	rand.Read(salt)
	h := argon2.IDKey([]byte(pw), salt, argonT, argonM, argonP, 32)
	return fmt.Sprintf("$argon2id$v=19$m=%d,t=%d,p=%d$%s$%s", argonM, argonT, argonP,
		base64.RawStdEncoding.EncodeToString(salt), base64.RawStdEncoding.EncodeToString(h))
}

func VerifyPassword(pw, enc string) bool {
	p := strings.Split(enc, "$")
	if len(p) != 6 || p[1] != "argon2id" {
		return false
	}
	var m, t uint32
	var par uint8
	if _, err := fmt.Sscanf(p[3], "m=%d,t=%d,p=%d", &m, &t, &par); err != nil {
		return false
	}
	salt, err1 := base64.RawStdEncoding.DecodeString(p[4])
	want, err2 := base64.RawStdEncoding.DecodeString(p[5])
	if err1 != nil || err2 != nil {
		return false
	}
	got := argon2.IDKey([]byte(pw), salt, t, m, par, uint32(len(want)))
	return subtle.ConstantTimeCompare(got, want) == 1
}

// dummyHash equaliza o tempo de resposta quando o e-mail não existe.
var dummyHash = HashPassword("dummy-password-for-timing")

var common = map[string]bool{"123456789012": true, "password1234": true, "senha1234567": true, "qwertyuiop12": true, "administrador": true}

// CheckPolicy: mínimo de 12 caracteres, sem senhas óbvias e (opcional) checagem de vazamento por k-anonymity.
func CheckPolicy(pw string, checkLeak bool) error {
	if utf8.RuneCountInString(pw) < 12 {
		return fmt.Errorf("a senha deve ter pelo menos 12 caracteres")
	}
	if common[strings.ToLower(pw)] {
		return fmt.Errorf("senha muito comum")
	}
	if checkLeak && leaked(pw) {
		return fmt.Errorf("esta senha apareceu em vazamentos conhecidos; escolha outra")
	}
	return nil
}

func leaked(pw string) bool {
	sum := strings.ToUpper(hex.EncodeToString(func() []byte { h := sha1.Sum([]byte(pw)); return h[:] }()))
	cli := http.Client{Timeout: 2 * time.Second}
	resp, err := cli.Get("https://api.pwnedpasswords.com/range/" + sum[:5])
	if err != nil {
		return false // falha aberta: não bloqueia por indisponibilidade
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	for _, l := range strings.Split(string(b), "\n") {
		if strings.HasPrefix(strings.ToUpper(l), sum[5:]) {
			return true
		}
	}
	return false
}
