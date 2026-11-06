// Package storage: armazenamento de objetos (S3/MinIO ou disco), cofre cifrado por empresa
// (envelope AES-256-GCM) e URLs assinadas de curta duração.
package storage

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/crypto"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type Store interface {
	Put(ctx context.Context, key string, r io.Reader, size int64) error
	Get(ctx context.Context, key string) (io.ReadCloser, error)
	Delete(ctx context.Context, key string) error
	// DeletePrefix remove todos os objetos sob o prefixo (ex.: tudo de um lote) e devolve quantos removeu.
	DeletePrefix(ctx context.Context, prefix string) (int, error)
}

// ---------- disco ----------
type FS struct{ Root string }

func (f *FS) path(key string) (string, error) {
	p := filepath.Join(f.Root, filepath.FromSlash(key))
	if !strings.HasPrefix(p, filepath.Clean(f.Root)+string(os.PathSeparator)) {
		return "", errors.New("chave de objeto inválida")
	}
	return p, nil
}
func (f *FS) Put(ctx context.Context, key string, r io.Reader, _ int64) error {
	p, err := f.path(key)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o750); err != nil {
		return err
	}
	tmp := p + ".tmp"
	w, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if _, err := io.Copy(w, r); err != nil {
		w.Close()
		os.Remove(tmp)
		return err
	}
	if err := w.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, p)
}
func (f *FS) Get(ctx context.Context, key string) (io.ReadCloser, error) {
	p, err := f.path(key)
	if err != nil {
		return nil, err
	}
	return os.Open(p)
}
func (f *FS) Delete(ctx context.Context, key string) error {
	p, err := f.path(key)
	if err != nil {
		return err
	}
	return os.Remove(p)
}

// DeletePrefix apaga a pasta do prefixo (sem barra final). O prefixo vem de IDs do banco; o caminho continua preso ao Root.
func (f *FS) DeletePrefix(ctx context.Context, prefix string) (int, error) {
	p, err := f.path(strings.TrimSuffix(prefix, "/"))
	if err != nil {
		return 0, err
	}
	n := 0
	_ = filepath.WalkDir(p, func(_ string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() {
			n++
		}
		return nil
	})
	if err := os.RemoveAll(p); err != nil {
		return 0, err
	}
	return n, nil
}

// ---------- S3 / MinIO ----------
type S3 struct {
	c      *minio.Client
	bucket string
}

func NewS3(endpoint, access, secret, bucket string, ssl bool) (*S3, error) {
	c, err := minio.New(endpoint, &minio.Options{Creds: credentials.NewStaticV4(access, secret, ""), Secure: ssl})
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	ok, err := c.BucketExists(ctx, bucket)
	if err != nil {
		return nil, fmt.Errorf("s3 indisponível: %w", err)
	}
	if !ok {
		if err := c.MakeBucket(ctx, bucket, minio.MakeBucketOptions{}); err != nil {
			return nil, err
		}
	}
	return &S3{c: c, bucket: bucket}, nil
}
func (s *S3) Put(ctx context.Context, key string, r io.Reader, size int64) error {
	_, err := s.c.PutObject(ctx, s.bucket, key, r, size, minio.PutObjectOptions{PartSize: 16 << 20})
	return err
}
func (s *S3) Get(ctx context.Context, key string) (io.ReadCloser, error) {
	o, err := s.c.GetObject(ctx, s.bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return nil, err
	}
	if _, err := o.Stat(); err != nil {
		o.Close()
		return nil, err
	}
	return o, nil
}
func (s *S3) DeletePrefix(ctx context.Context, prefix string) (int, error) {
	n := 0
	for obj := range s.c.ListObjects(ctx, s.bucket, minio.ListObjectsOptions{Prefix: prefix, Recursive: true}) {
		if obj.Err != nil {
			return n, obj.Err
		}
		if err := s.c.RemoveObject(ctx, s.bucket, obj.Key, minio.RemoveObjectOptions{}); err != nil {
			return n, err
		}
		n++
	}
	return n, nil
}

func (s *S3) Delete(ctx context.Context, key string) error {
	return s.c.RemoveObject(ctx, s.bucket, key, minio.RemoveObjectOptions{})
}

// ---------- cofre cifrado por empresa ----------

// DEKFunc devolve a DEK (já aberta) da empresa; implementada sobre o Keyring + tabela tenants.
type DEKFunc func(ctx context.Context, tenantID string) ([]byte, error)

type Vault struct {
	Store Store
	DEK   DEKFunc
}

func checkPrefix(tenantID, key string) error {
	if !strings.HasPrefix(key, tenantID+"/") {
		return errors.New("objeto não pertence à empresa")
	}
	return nil
}

// Put cifra em streaming e grava. Devolve bytes de plaintext.
func (v *Vault) Put(ctx context.Context, tenantID, key string, r io.Reader) (int64, error) {
	if err := checkPrefix(tenantID, key); err != nil {
		return 0, err
	}
	dek, err := v.DEK(ctx, tenantID)
	if err != nil {
		return 0, err
	}
	pr, pw := io.Pipe()
	var plain int64
	go func() {
		n, err := crypto.Encrypt(pw, r, dek, []byte(tenantID))
		plain = n
		pw.CloseWithError(err)
	}()
	if err := v.Store.Put(ctx, key, pr, -1); err != nil {
		pr.CloseWithError(err)
		return 0, err
	}
	return plain, nil
}

func (v *Vault) PutBytes(ctx context.Context, tenantID, key string, b []byte) (int64, error) {
	return v.Put(ctx, tenantID, key, strings.NewReader(string(b)))
}

type readCloser struct {
	io.Reader
	c io.Closer
}

func (r readCloser) Close() error { return r.c.Close() }

func (v *Vault) Get(ctx context.Context, tenantID, key string) (io.ReadCloser, error) {
	if err := checkPrefix(tenantID, key); err != nil {
		return nil, err
	}
	dek, err := v.DEK(ctx, tenantID)
	if err != nil {
		return nil, err
	}
	raw, err := v.Store.Get(ctx, key)
	if err != nil {
		return nil, err
	}
	dr, err := crypto.Decrypt(raw, dek, []byte(tenantID))
	if err != nil {
		raw.Close()
		return nil, err
	}
	return readCloser{dr, raw}, nil
}

// DeleteBatch remove todos os objetos de um lote (original, páginas, miniaturas e PDFs gerados).
func (v *Vault) DeleteBatch(ctx context.Context, tenantID, batchID string) (int, error) {
	prefix := tenantID + "/" + batchID + "/"
	if err := checkPrefix(tenantID, prefix); err != nil {
		return 0, err
	}
	return v.Store.DeletePrefix(ctx, prefix)
}

func (v *Vault) ReadAll(ctx context.Context, tenantID, key string) ([]byte, error) {
	r, err := v.Get(ctx, tenantID, key)
	if err != nil {
		return nil, err
	}
	defer r.Close()
	return io.ReadAll(r)
}

// ---------- URLs assinadas ("pré-assinadas" de 60–120 s) ----------

type Signer struct {
	Secret  []byte
	BaseURL string
}

type Grant struct {
	Tenant      string `json:"t"`
	Key         string `json:"k"`
	Exp         int64  `json:"e"`
	Filename    string `json:"f,omitempty"`
	ContentType string `json:"c,omitempty"`
	Download    bool   `json:"d,omitempty"`
}

func (s *Signer) URL(g Grant, ttl time.Duration) string { return s.URLFor(s.BaseURL, g, ttl) }

// URLFor assina para uma base específica (ex.: a URL interna vista pelo IA Core).
func (s *Signer) URLFor(base string, g Grant, ttl time.Duration) string {
	g.Exp = time.Now().Add(ttl).Unix()
	raw, _ := json.Marshal(g)
	p := base64.RawURLEncoding.EncodeToString(raw)
	sig := base64.RawURLEncoding.EncodeToString(crypto.HMAC(s.Secret, []byte("url|"+p)))
	return base + "/api/v1/files/" + p + "." + sig
}

func (s *Signer) Verify(token string) (*Grant, error) {
	parts := strings.SplitN(token, ".", 2)
	if len(parts) != 2 {
		return nil, errors.New("link inválido")
	}
	want := crypto.HMAC(s.Secret, []byte("url|"+parts[0]))
	got, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil || !crypto.Equal(want, got) {
		return nil, errors.New("assinatura inválida")
	}
	raw, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return nil, errors.New("link inválido")
	}
	var g Grant
	if err := json.Unmarshal(raw, &g); err != nil {
		return nil, err
	}
	if time.Now().Unix() > g.Exp {
		return nil, errors.New("link expirado")
	}
	return &g, nil
}

var _ = url.QueryEscape
