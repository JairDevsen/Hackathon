// Package http: roteador Gin, middlewares e handlers da API /api/v1.
package http

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/internal/ocrseal"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

type Server struct{ *app.App }

// sealer abre o cifrador do texto lido (OCR) da empresa, dentro de uma transação dela.
func (s *Server) sealer(ctx context.Context, tx pgx.Tx, tenantID string) (*ocrseal.Sealer, error) {
	return ocrseal.ForTx(ctx, tx, s.KR, tenantID)
}

const ctxTenant, ctxSupport = "tenant_id", "support_mode"

func (s *Server) Router() *gin.Engine {
	if s.Cfg.Prod() {
		gin.SetMode(gin.ReleaseMode)
	}
	r := gin.New()
	r.SetTrustedProxies([]string{"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.1"})
	r.Use(s.recovery(), s.requestLog(), s.securityHeaders(), s.cors())
	r.GET("/healthz", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })
	r.GET("/readyz", s.ready)
	r.GET("/.well-known/jwks.json", func(c *gin.Context) { c.JSON(200, s.JWT.JWKS()) })
	r.POST("/internal/ia/callback", s.iaCallback) // não exposto pelo Traefik público

	v1 := r.Group("/api/v1")
	v1.GET("/files/:token", s.serveFile)
	v1.POST("/public/leads", s.createLead)
	authn := s.Auth.Authenticate()
	s.Auth.Register(v1.Group("/auth"), authn)

	// ---------- Master ----------
	m := v1.Group("/admin", authn, auth.RequireRole("MASTER"))
	s.adminRoutes(m, v1)

	// ---------- Escopo da empresa (Admin, RH e Master com acesso de suporte aprovado) ----------
	t := v1.Group("", authn, s.tenantScope())
	s.tenantRoutes(t)
	return r
}

func (s *Server) recovery() gin.HandlerFunc {
	return gin.CustomRecovery(func(c *gin.Context, err any) {
		slog.Error("panic", "erro", err, "path", c.Request.URL.Path)
		problem.Write(c, problem.Internal())
	})
}

func (s *Server) requestLog() gin.HandlerFunc {
	return func(c *gin.Context) {
		rid := c.GetHeader("X-Request-ID")
		if rid == "" {
			rid = uuid.NewString()
		}
		c.Set("request_id", rid)
		c.Header("X-Request-ID", rid)
		t0 := time.Now()
		c.Next()
		attrs := []any{"request_id", rid, "metodo", c.Request.Method, "rota", c.FullPath(), "status", c.Writer.Status(), "ms", time.Since(t0).Milliseconds()}
		if cl := auth.ClaimsOf(c); cl != nil && cl.TenantID != "" {
			attrs = append(attrs, "tenant_id", cl.TenantID) // nunca logamos dado pessoal
		}
		slog.Info("http", attrs...)
	}
}

func (s *Server) securityHeaders() gin.HandlerFunc {
	return func(c *gin.Context) {
		h := c.Writer.Header()
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("X-Frame-Options", "DENY")
		h.Set("Referrer-Policy", "no-referrer")
		h.Set("Cache-Control", "no-store")
		if s.Cfg.Prod() {
			h.Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		}
		c.Next()
	}
}

func (s *Server) cors() gin.HandlerFunc {
	allowed := map[string]bool{}
	for _, o := range s.Cfg.CORSOrigins {
		allowed[strings.TrimSpace(o)] = true
	}
	return func(c *gin.Context) {
		o := c.GetHeader("Origin")
		if o != "" && allowed[o] {
			h := c.Writer.Header()
			h.Set("Access-Control-Allow-Origin", o)
			h.Set("Vary", "Origin")
			h.Set("Access-Control-Allow-Credentials", "true")
			h.Set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-CSRF-Token, X-Step-Up-Token, X-Tenant-ID, Idempotency-Key, Upload-Offset")
			h.Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS")
			h.Set("Access-Control-Expose-Headers", "Upload-Offset, X-Step-Up-Required, X-Request-ID")
		}
		if c.Request.Method == http.MethodOptions {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}

func (s *Server) ready(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 3*time.Second)
	defer cancel()
	if err := s.DB.Pool.Ping(ctx); err != nil {
		c.JSON(503, gin.H{"status": "db indisponível"})
		return
	}
	if err := s.Redis.Ping(ctx).Err(); err != nil {
		c.JSON(503, gin.H{"status": "redis indisponível"})
		return
	}
	c.JSON(200, gin.H{"status": "ready"})
}

// tenantScope resolve a empresa da requisição. O Master só entra com acesso de suporte aprovado (X-Tenant-ID).
func (s *Server) tenantScope() gin.HandlerFunc {
	return func(c *gin.Context) {
		cl := auth.ClaimsOf(c)
		if cl.Role != "MASTER" {
			c.Set(ctxTenant, cl.TenantID)
			return
		}
		tid := c.GetHeader("X-Tenant-ID")
		if tid == "" {
			problem.Write(c, problem.Forbidden("o perfil Master não acessa dados de empresas sem acesso de suporte"))
			return
		}
		ok := false
		s.DB.System(c.Request.Context(), func(tx pgx.Tx) error {
			var n int
			tx.QueryRow(c.Request.Context(), `SELECT count(*) FROM support_access WHERE tenant_id=$1 AND solicitado_por=$2 AND status='APROVADO' AND expira_em>now()`, tid, cl.Subject).Scan(&n)
			ok = n > 0
			return nil
		})
		if !ok {
			problem.Write(c, problem.Forbidden("não há acesso de suporte aprovado para esta empresa"))
			return
		}
		c.Set(ctxTenant, tid)
		c.Set(ctxSupport, true)
	}
}

func tid(c *gin.Context) string   { return c.GetString(ctxTenant) }
func support(c *gin.Context) bool { v, _ := c.Get(ctxSupport); b, _ := v.(bool); return b }

// tx abre uma transação com RLS da empresa e já devolve erros no padrão problem+json.
func (s *Server) tx(c *gin.Context, fn func(ctx context.Context, tx pgx.Tx) error) bool {
	ctx := c.Request.Context()
	if err := s.DB.Tenant(ctx, tid(c), func(tx pgx.Tx) error { return fn(ctx, tx) }); err != nil {
		if p, ok := err.(*problem.Problem); ok {
			problem.Write(c, p)
		} else {
			slog.Error("erro", "rota", c.FullPath(), "erro", err, "request_id", c.GetString("request_id"))
			problem.Write(c, problem.Internal())
		}
		return false
	}
	return true
}

func (s *Server) sys(c *gin.Context, fn func(ctx context.Context, tx pgx.Tx) error) bool {
	ctx := c.Request.Context()
	if err := s.DB.System(ctx, func(tx pgx.Tx) error { return fn(ctx, tx) }); err != nil {
		if p, ok := err.(*problem.Problem); ok {
			problem.Write(c, p)
		} else {
			slog.Error("erro", "rota", c.FullPath(), "erro", err, "request_id", c.GetString("request_id"))
			problem.Write(c, problem.Internal())
		}
		return false
	}
	return true
}

// queryJSON executa SELECT que devolve uma coluna json e a envia crua (sem structs intermediárias).
func (s *Server) queryJSON(c *gin.Context, sql string, args ...any) {
	var raw []byte
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var e error
		raw, e = database.JSON(ctx, tx, sql, args...)
		return e
	}) {
		c.Data(200, "application/json", raw)
	}
}

func (s *Server) sysJSON(c *gin.Context, sql string, args ...any) {
	var raw []byte
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		var e error
		raw, e = database.JSON(ctx, tx, sql, args...)
		return e
	}) {
		c.Data(200, "application/json", raw)
	}
}

// audit grava o evento na mesma transação.
func (s *Server) audit(ctx context.Context, tx pgx.Tx, c *gin.Context, acao, entidade, entidadeID string, dados any) error {
	cl := auth.ClaimsOf(c)
	t := tid(c)
	if cl.Role == "MASTER" && !support(c) {
		t = ""
	}
	if dados == nil {
		dados = map[string]any{}
	}
	if support(c) {
		if m, ok := dados.(map[string]any); ok {
			m["acesso_suporte"] = true
		}
	}
	return audit.Log(ctx, tx, audit.Event{TenantID: t, Actor: cl.Subject, ActorRole: cl.Role, Acao: acao, Entidade: entidade, EntidadeID: entidadeID, Dados: dados, IP: c.ClientIP(), UA: c.Request.UserAgent()})
}

// userScope devolve as unidades permitidas ao usuário (vazio = todas) e se ele pode ler dados de saúde.
func (s *Server) userScope(c *gin.Context) (units []string, saude bool) {
	cl := auth.ClaimsOf(c)
	saude = auth.HasPerm(cl, "saude:ler") && !support(c)
	if cl.Role == "RH" {
		s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
			var u []string
			tx.QueryRow(ctx, `SELECT unit_scope::text[] FROM users WHERE id=$1`, cl.Subject).Scan(&u)
			units = u
			return nil
		})
	}
	if units == nil {
		units = []string{}
	}
	return
}

func bindJSON(c *gin.Context, v any) bool {
	if err := c.ShouldBindJSON(v); err != nil {
		problem.Write(c, problem.BadRequest("dados inválidos: "+err.Error()))
		return false
	}
	return true
}

func mustJSON(v any) []byte { b, _ := json.Marshal(v); return b }
