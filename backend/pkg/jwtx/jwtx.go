// Package jwtx emite e valida JWT EdDSA (Ed25519) com kid e rotação por conjunto de chaves (JWKS).
package jwtx

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/pem"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	TenantID string   `json:"tid,omitempty"`
	Role     string   `json:"role"`
	Perms    []string `json:"perms,omitempty"`
	Session  string   `json:"sid"`
	AMR      []string `json:"amr"`
	Purpose  string   `json:"pur,omitempty"` // "access" | "stepup"
	jwt.RegisteredClaims
}

type Signer struct {
	kid    string
	priv   ed25519.PrivateKey
	pubs   map[string]ed25519.PublicKey
	issuer string
}

func kidOf(pub ed25519.PublicKey) string {
	h := sha256.Sum256(pub)
	return hex.EncodeToString(h[:6])
}

// Load lê a chave privada PEM (PKCS#8). Fora de produção, gera e grava se não existir.
// prevDir (opcional) contém chaves públicas PEM antigas que continuam válidas durante a rotação.
func Load(privFile, prevDir, issuer string, autoGen bool) (*Signer, error) {
	raw, err := os.ReadFile(privFile)
	if os.IsNotExist(err) && autoGen {
		_, priv, _ := ed25519.GenerateKey(rand.Reader)
		der, _ := x509.MarshalPKCS8PrivateKey(priv)
		raw = pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der})
		if err := os.MkdirAll(filepath.Dir(privFile), 0o700); err != nil {
			return nil, err
		}
		if err := os.WriteFile(privFile, raw, 0o600); err != nil {
			return nil, err
		}
	} else if err != nil {
		return nil, err
	}
	blk, _ := pem.Decode(raw)
	if blk == nil {
		return nil, errors.New("PEM inválido em " + privFile)
	}
	k, err := x509.ParsePKCS8PrivateKey(blk.Bytes)
	if err != nil {
		return nil, err
	}
	priv, ok := k.(ed25519.PrivateKey)
	if !ok {
		return nil, errors.New("a chave JWT deve ser Ed25519")
	}
	pub := priv.Public().(ed25519.PublicKey)
	s := &Signer{kid: kidOf(pub), priv: priv, pubs: map[string]ed25519.PublicKey{kidOf(pub): pub}, issuer: issuer}
	if prevDir != "" {
		files, _ := filepath.Glob(filepath.Join(prevDir, "*.pub.pem"))
		for _, f := range files {
			b, _ := os.ReadFile(f)
			if pb, _ := pem.Decode(b); pb != nil {
				if pk, err := x509.ParsePKIXPublicKey(pb.Bytes); err == nil {
					if ep, ok := pk.(ed25519.PublicKey); ok {
						s.pubs[kidOf(ep)] = ep
					}
				}
			}
		}
	}
	return s, nil
}

func (s *Signer) KID() string { return s.kid }

func (s *Signer) Sign(c Claims, ttl time.Duration) (string, error) {
	now := time.Now()
	c.IssuedAt = jwt.NewNumericDate(now)
	c.ExpiresAt = jwt.NewNumericDate(now.Add(ttl))
	c.Issuer = s.issuer
	t := jwt.NewWithClaims(jwt.SigningMethodEdDSA, c)
	t.Header["kid"] = s.kid
	return t.SignedString(s.priv)
}

func (s *Signer) Verify(tok string) (*Claims, error) {
	var c Claims
	_, err := jwt.ParseWithClaims(tok, &c, func(t *jwt.Token) (any, error) {
		kid, _ := t.Header["kid"].(string)
		if k, ok := s.pubs[kid]; ok {
			return k, nil
		}
		return nil, errors.New("kid desconhecido")
	}, jwt.WithValidMethods([]string{"EdDSA"}), jwt.WithIssuer(s.issuer), jwt.WithExpirationRequired())
	if err != nil {
		return nil, err
	}
	return &c, nil
}

// JWKS devolve o conjunto de chaves públicas no formato RFC 7517 (OKP/Ed25519).
func (s *Signer) JWKS() map[string]any {
	keys := []map[string]string{}
	for kid, p := range s.pubs {
		keys = append(keys, map[string]string{"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig", "kid": kid,
			"x": strings.TrimRight(base64.URLEncoding.EncodeToString(p), "=")})
	}
	return map[string]any{"keys": keys}
}
