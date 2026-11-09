// Package app monta as dependências compartilhadas por API, worker e seed.
package app

import (
	"context"
	"encoding/hex"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/batches"
	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/internal/documents"
	"github.com/agreser-innovations/citadel-ia/backend/internal/iacore"
	"github.com/agreser-innovations/citadel-ia/backend/internal/notify"
	"github.com/agreser-innovations/citadel-ia/backend/internal/storage"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/crypto"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/jwtx"
	"github.com/hibiken/asynq"
	"github.com/jackc/pgx/v5"
	"github.com/redis/go-redis/v9"
)

type App struct {
	Cfg      *config.Config
	DB       *database.DB
	Redis    *redis.Client
	KR       *crypto.Keyring
	JWT      *jwtx.Signer
	Mail     notify.Mailer
	Vault    *storage.Vault
	Signer   *storage.Signer
	IA       *iacore.Client
	Ingest   *documents.Ingestor
	Auth     *auth.Service
	Batches  *batches.Service
	Queue    *asynq.Client
	RedisOpt asynq.RedisConnOpt
}

func New(ctx context.Context, cfg *config.Config) (*App, error) {
	a := &App{Cfg: cfg}
	var err error
	if a.DB, err = database.Connect(ctx, cfg.DatabaseURL); err != nil {
		return nil, err
	}
	ro, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		return nil, err
	}
	a.Redis = redis.NewClient(ro)
	if err := a.Redis.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis indisponível: %w", err)
	}
	if a.RedisOpt, err = asynq.ParseRedisURI(cfg.RedisURL); err != nil {
		return nil, err
	}
	a.Queue = asynq.NewClient(a.RedisOpt)
	if a.KR, err = crypto.NewKeyring(cfg.KEKHex, cfg.HMACHex); err != nil {
		return nil, err
	}
	if a.JWT, err = jwtx.Load(cfg.JWTPrivateFile, cfg.JWTPrevDir, cfg.JWTIssuer, !cfg.Prod()); err != nil {
		return nil, fmt.Errorf("chave JWT: %w", err)
	}
	a.Mail = notify.New(cfg.MailDriver, cfg.SMTPHost, cfg.SMTPPort, cfg.SMTPUser, cfg.SMTPPass, cfg.MailFrom)
	var store storage.Store
	if cfg.StorageDriver == "s3" {
		if store, err = storage.NewS3(cfg.S3Endpoint, cfg.S3AccessKey, cfg.S3SecretKey, cfg.S3Bucket, cfg.S3UseSSL); err != nil {
			return nil, err
		}
	} else {
		if err := os.MkdirAll(cfg.StorageFSDir, 0o750); err != nil {
			return nil, err
		}
		store = &storage.FS{Root: cfg.StorageFSDir}
	}
	a.Vault = &storage.Vault{Store: store, DEK: func(ctx context.Context, tid string) ([]byte, error) {
		var w []byte
		if err := a.DB.System(ctx, func(tx pgx.Tx) error {
			return tx.QueryRow(ctx, `SELECT dek_wrapped FROM tenants WHERE id=$1`, tid).Scan(&w)
		}); err != nil {
			return nil, err
		}
		return a.KR.DEK(tid, w)
	}}
	hk, _ := hex.DecodeString(cfg.HMACHex)
	a.Signer = &storage.Signer{Secret: crypto.HMAC(hk, []byte("signed-urls")), BaseURL: cfg.PublicBaseURL}
	a.IA = iacore.New(cfg.IACoreURL, cfg.IACoreAPIKey)
	a.Ingest = &documents.Ingestor{KR: a.KR, Anonimizar: a.IA.Anonymize}
	a.Auth = &auth.Service{DB: a.DB, Redis: a.Redis, Mail: a.Mail, JWT: a.JWT, Cfg: cfg}
	a.Batches = &batches.Service{Cfg: cfg, DB: a.DB, Redis: a.Redis, Vault: a.Vault, Signer: a.Signer, IA: a.IA, Ingest: a.Ingest, Queue: a.Queue, Stall: time.Duration(cfg.BatchStallSeconds) * time.Second}
	slog.Info("dependências prontas", "env", cfg.Env, "storage", cfg.StorageDriver, "mail", cfg.MailDriver)
	return a, nil
}

func (a *App) Close() {
	a.Queue.Close()
	a.Redis.Close()
	a.DB.Pool.Close()
}

// NewTenantKey gera a DEK da empresa protegida pela KEK.
func (a *App) NewTenantKey() ([]byte, error) {
	_, w, err := a.KR.NewDEK()
	return w, err
}

func EmailDomain(email string) string {
	i := strings.LastIndex(email, "@")
	if i < 0 {
		return ""
	}
	return strings.ToLower(email[i+1:])
}
