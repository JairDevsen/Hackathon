// Package config carrega a configuração do ambiente (ver VARIAVEIS_AMBIENTE.md).
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	Env               string
	HTTPAddr          string
	DatabaseURL       string // papel citadel_app (sujeito a RLS)
	DatabaseMigrate   string // dono do schema
	AppDBPassword     string
	RedisURL          string
	KEKHex, HMACHex   string
	JWTPrivateFile    string
	JWTPrevDir        string
	JWTIssuer         string
	PublicBaseURL     string // URL pública da API (links no navegador)
	InternalBaseURL   string // URL da API vista pelo IA Core
	StorageDriver     string
	StorageFSDir      string
	S3Endpoint        string
	S3Bucket          string
	S3AccessKey       string
	S3SecretKey       string
	S3UseSSL          bool
	UploadStagingDir  string
	MaxUploadBytes    int64
	IACoreURL         string
	IACoreAPIKey      string
	IACallbackSecret  string
	MailDriver        string
	SMTPHost          string
	SMTPPort          string
	SMTPUser          string
	SMTPPass          string
	MailFrom          string
	CommercialEmail   string
	AppURL            string // URL do frontend (links em e-mails)
	ClamAVAddr        string
	MasterEmail       string
	MasterPassword    string
	CookieSecure      bool
	CORSOrigins       []string
	CaptchaSecret     string
	SeedDemo          bool
	WorkerConcurrency int
	BatchStallSeconds int
	WatchdogInterval  string
}

func get(k, def string) string {
	if v := strings.TrimSpace(os.Getenv(k)); v != "" {
		return v
	}
	return def
}

func Load() (*Config, error) {
	env := get("APP_ENV", "development")
	prod := env == "production"
	c := &Config{
		Env:              env,
		HTTPAddr:         get("HTTP_ADDR", ":8080"),
		DatabaseURL:      get("DATABASE_URL", "postgres://citadel_app:citadel_app@localhost:5432/citadel?sslmode=disable"),
		DatabaseMigrate:  get("DATABASE_MIGRATE_URL", "postgres://citadel:citadel@localhost:5432/citadel?sslmode=disable"),
		AppDBPassword:    get("APP_DB_PASSWORD", "citadel_app"),
		RedisURL:         get("REDIS_URL", "redis://localhost:6379/0"),
		KEKHex:           get("KEK_HEX", ""),
		HMACHex:          get("HMAC_KEY_HEX", ""),
		JWTPrivateFile:   get("JWT_PRIVATE_KEY_FILE", "../secrets/jwt_ed25519.pem"),
		JWTPrevDir:       get("JWT_PREVIOUS_KEYS_DIR", ""),
		JWTIssuer:        get("JWT_ISSUER", "citadel-ia"),
		PublicBaseURL:    strings.TrimRight(get("PUBLIC_BASE_URL", "http://localhost:8080"), "/"),
		InternalBaseURL:  strings.TrimRight(get("INTERNAL_BASE_URL", "http://localhost:8080"), "/"),
		StorageDriver:    get("STORAGE_DRIVER", "fs"),
		StorageFSDir:     get("STORAGE_FS_DIR", "./var/storage"),
		S3Endpoint:       get("S3_ENDPOINT", "localhost:9000"),
		S3Bucket:         get("S3_BUCKET", "citadel"),
		S3AccessKey:      get("S3_ACCESS_KEY", ""),
		S3SecretKey:      get("S3_SECRET_KEY", ""),
		S3UseSSL:         get("S3_USE_SSL", "false") == "true",
		UploadStagingDir: get("UPLOAD_STAGING_DIR", "./var/staging"),
		IACoreURL:        strings.TrimRight(get("IA_CORE_URL", "http://localhost:8001"), "/"),
		IACoreAPIKey:     get("IA_CORE_API_KEY", "dev-ia-core-key"),
		IACallbackSecret: get("IA_CALLBACK_SECRET", ""),
		MailDriver:       get("MAIL_DRIVER", "log"),
		SMTPHost:         get("SMTP_HOST", "localhost"),
		SMTPPort:         get("SMTP_PORT", "1025"),
		SMTPUser:         get("SMTP_USER", ""),
		SMTPPass:         get("SMTP_PASS", ""),
		MailFrom:         get("MAIL_FROM", "Citadel IA <nao-responda@citadel.local>"),
		CommercialEmail:  get("COMMERCIAL_EMAIL", "comercial@citadel.local"),
		AppURL:           strings.TrimRight(get("APP_URL", "http://localhost:5173"), "/"),
		ClamAVAddr:       get("CLAMAV_ADDR", ""),
		MasterEmail:      get("MASTER_EMAIL", "master@citadel.local"),
		MasterPassword:   get("MASTER_PASSWORD", ""),
		CookieSecure:     prod || get("COOKIE_SECURE", "false") == "true",
		CORSOrigins:      strings.Split(get("CORS_ORIGINS", "http://localhost:5173"), ","),
		CaptchaSecret:    get("CAPTCHA_SECRET", ""),
		SeedDemo:         get("SEED_DEMO", "false") == "true",
	}
	mb, _ := strconv.ParseInt(get("MAX_UPLOAD_MB", "500"), 10, 64)
	c.MaxUploadBytes = mb << 20
	c.WorkerConcurrency, _ = strconv.Atoi(get("WORKER_CONCURRENCY", "4"))
	c.BatchStallSeconds, _ = strconv.Atoi(get("BATCH_STALL_SECONDS", "180"))
	c.WatchdogInterval = get("WATCHDOG_INTERVAL", "1m")
	if !prod { // padrões de desenvolvimento: chaves fixas e públicas, NUNCA usar em produção
		if c.KEKHex == "" {
			c.KEKHex = strings.Repeat("11", 32)
		}
		if c.HMACHex == "" {
			c.HMACHex = strings.Repeat("22", 32)
		}
		if c.IACallbackSecret == "" {
			c.IACallbackSecret = "dev-callback-secret"
		}
		if c.MasterPassword == "" {
			c.MasterPassword = "Citadel!Master#2026"
		}
	}
	var miss []string
	for k, v := range map[string]string{"KEK_HEX": c.KEKHex, "HMAC_KEY_HEX": c.HMACHex, "IA_CALLBACK_SECRET": c.IACallbackSecret} {
		if v == "" {
			miss = append(miss, k)
		}
	}
	if prod && (c.MasterPassword == "" || c.IACoreAPIKey == "dev-ia-core-key") {
		miss = append(miss, "MASTER_PASSWORD/IA_CORE_API_KEY")
	}
	if len(miss) > 0 {
		return nil, fmt.Errorf("variáveis obrigatórias ausentes: %s", strings.Join(miss, ", "))
	}
	return c, nil
}

func (c *Config) Prod() bool { return c.Env == "production" }
