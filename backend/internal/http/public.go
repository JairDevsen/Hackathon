package http

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"path/filepath"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/iacore"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// iaCallback recebe os eventos do IA Core (assinados com HMAC; rota interna, fora do Traefik público).
func (s *Server) iaCallback(c *gin.Context) {
	body, err := io.ReadAll(io.LimitReader(c.Request.Body, 32<<20))
	if err != nil || !iacore.VerifySignature(s.Cfg.IACallbackSecret, c.GetHeader("X-Timestamp"), c.GetHeader("X-Signature"), body) {
		problem.Write(c, problem.Unauthorized("assinatura do callback inválida"))
		return
	}
	var cb iacore.Callback
	if err := json.Unmarshal(body, &cb); err != nil {
		problem.Write(c, problem.BadRequest("callback malformado"))
		return
	}
	if err := s.Batches.HandleCallback(c.Request.Context(), c.GetHeader("Idempotency-Key"), cb); err != nil {
		slog.Error("callback do IA Core", "erro", err, "evento", cb.Evento, "batch", cb.BatchID)
		problem.Write(c, problem.New(500, "callback-falhou", "falha ao processar; reenvie"))
		return
	}
	c.Status(http.StatusOK)
}

var contentTypes = map[string]string{".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf", ".jpg": "image/jpeg", ".zip": "application/zip", ".tif": "image/tiff", ".tiff": "image/tiff"}

// serveFile entrega o objeto decifrado via URL assinada de curta duração (60–120 s) emitida após checagem de permissão.
func (s *Server) serveFile(c *gin.Context) {
	g, err := s.Signer.Verify(c.Param("token"))
	if err != nil {
		problem.Write(c, problem.Forbidden(err.Error()))
		return
	}
	r, err := s.Vault.Get(c.Request.Context(), g.Tenant, g.Key)
	if err != nil {
		problem.Write(c, problem.NotFound("arquivo não encontrado"))
		return
	}
	defer r.Close()
	ct := g.ContentType
	if ct == "" {
		ct = contentTypes[strings.ToLower(filepath.Ext(g.Key))]
	}
	if ct == "" {
		ct = "application/octet-stream"
	}
	if g.Download {
		c.Header("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, url.PathEscape(g.Filename)))
	}
	c.Header("Cache-Control", "private, max-age=60")
	c.DataFromReader(200, -1, ct, r, nil)
}

var freeDomains = map[string]bool{"gmail.com": true, "hotmail.com": true, "outlook.com": true, "yahoo.com": true, "yahoo.com.br": true, "uol.com.br": true,
	"bol.com.br": true, "icloud.com": true, "live.com": true, "terra.com.br": true, "ig.com.br": true, "msn.com": true, "proton.me": true, "protonmail.com": true, "aol.com": true, "gmx.com": true}

func (s *Server) createLead(c *gin.Context) {
	var in struct {
		Nome          string `json:"nome" binding:"required,min=2,max=120"`
		Email         string `json:"email" binding:"required,email"`
		Empresa       string `json:"empresa" binding:"required,min=2,max=160"`
		Porte         string `json:"porte"`
		Funcionarios  int    `json:"funcionarios"`
		Consentimento bool   `json:"consentimento"`
		Website       string `json:"website"` // honeypot: humanos não preenchem
		Captcha       string `json:"captcha_token"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if in.Website != "" { // bot: responde 202 sem gravar
		c.Status(http.StatusAccepted)
		return
	}
	ctx := c.Request.Context()
	if ok, _ := s.Auth.Allow(ctx, "lead:"+c.ClientIP(), 5, time.Hour); !ok {
		problem.Write(c, problem.TooMany("muitos envios; tente novamente mais tarde"))
		return
	}
	if !in.Consentimento {
		problem.Write(c, problem.BadRequest("é necessário o consentimento LGPD para o contato"))
		return
	}
	if freeDomains[app.EmailDomain(in.Email)] {
		problem.Write(c, problem.BadRequest("use seu e-mail corporativo (domínios gratuitos não são aceitos)"))
		return
	}
	if s.Cfg.CaptchaSecret != "" && !verifyCaptcha(ctx, s.Cfg.CaptchaSecret, in.Captcha, c.ClientIP()) {
		problem.Write(c, problem.BadRequest("falha na verificação anti-robô"))
		return
	}
	if !s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `INSERT INTO leads (nome,email,empresa,porte,funcionarios,consentimento,ip) VALUES ($1,$2,$3,nullif($4,''),$5,true,$6)`,
			in.Nome, in.Email, in.Empresa, in.Porte, in.Funcionarios, c.ClientIP())
		return err
	}) {
		return
	}
	go s.Mail.Send(s.Cfg.CommercialEmail, "Novo lead — Citadel IA", fmt.Sprintf("Nome: %s\nE-mail: %s\nEmpresa: %s\nPorte: %s\nFuncionários: %d\n", in.Nome, in.Email, in.Empresa, in.Porte, in.Funcionarios))
	c.JSON(http.StatusCreated, gin.H{"status": "recebido"})
}

func verifyCaptcha(ctx context.Context, secret, token, ip string) bool {
	if token == "" {
		return false
	}
	cli := http.Client{Timeout: 4 * time.Second}
	resp, err := cli.PostForm("https://challenges.cloudflare.com/turnstile/v0/siteverify", url.Values{"secret": {secret}, "response": {token}, "remoteip": {ip}})
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	var out struct{ Success bool }
	json.NewDecoder(resp.Body).Decode(&out)
	return out.Success
}
