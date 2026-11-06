package auth

import (
	"net/http"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/jwtx"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

const (
	cookieRT   = "citadel_rt"
	cookieCSRF = "citadel_csrf"
	cookieTD   = "citadel_td"
	ctxClaims  = "claims"
)

func ClaimsOf(c *gin.Context) *jwtx.Claims {
	v, _ := c.Get(ctxClaims)
	cl, _ := v.(*jwtx.Claims)
	return cl
}

func (s *Service) setAuthCookies(c *gin.Context, t *Tokens) {
	sec := s.Cfg.CookieSecure
	c.SetSameSite(http.SameSiteStrictMode)
	c.SetCookie(cookieRT, t.Refresh, int(RefreshMaxAge.Seconds()), "/api/v1/auth/refresh", "", sec, true)
	// CSRF double-submit: cookie legível pelo JS; o front reenvia no cabeçalho X-CSRF-Token.
	c.SetCookie(cookieCSRF, randToken(24), int(RefreshMaxAge.Seconds()), "/", "", sec, false)
}

func tokensBody(t *Tokens, u *User) gin.H {
	return gin.H{"access_token": t.Access, "token_type": "Bearer", "expires_in": t.ExpiresIn, "usuario": userBody(u)}
}

func userBody(u *User) gin.H {
	return gin.H{"id": u.ID, "nome": u.Nome, "email": u.Email, "role": u.Role, "tenant_id": u.TenantID, "perms": EffectivePerms(u.Role, u.Perms)}
}

// Register monta as rotas /auth. protected = middleware Authenticate.
func (s *Service) Register(g *gin.RouterGroup, protected gin.HandlerFunc) {
	g.POST("/login", s.login)
	g.POST("/mfa/verify", s.mfaVerify)
	g.POST("/mfa/resend", s.mfaResend)
	g.POST("/refresh", s.refresh)
	g.POST("/invite/accept", s.inviteAccept)
	p := g.Group("", protected)
	p.POST("/logout", s.logout)
	p.GET("/me", s.me)
	p.GET("/sessions", s.listSessions)
	p.DELETE("/sessions/:id", s.deleteSession)
	p.POST("/step-up", s.stepUp)
	p.POST("/password", s.RequireStepUp(), s.changePassword)
}

func (s *Service) login(c *gin.Context) {
	var in struct {
		Email string `json:"email" binding:"required,email"`
		Senha string `json:"senha" binding:"required"`
		Trust bool   `json:"confiar_dispositivo"`
	}
	if err := c.ShouldBindJSON(&in); err != nil {
		problem.Write(c, problem.BadRequest("e-mail e senha são obrigatórios"))
		return
	}
	ctx, ip, ua := c.Request.Context(), c.ClientIP(), c.Request.UserAgent()
	if ok, wait := s.Allow(ctx, "login:ip:"+ip, 30, 10*time.Minute); !ok {
		problem.Write(c, problem.TooMany("muitas tentativas deste IP; aguarde "+wait.Round(time.Second).String()))
		return
	}
	if wait := s.lockedFor(ctx, in.Email); wait > 0 {
		problem.Write(c, problem.TooMany("conta bloqueada temporariamente; aguarde "+wait.Round(time.Second).String()))
		return
	}
	u, err := s.loadUserByEmail(ctx, in.Email)
	hash := dummyHash
	if err == nil {
		hash = u.SenhaHash
	}
	passOK := VerifyPassword(in.Senha, hash) && err == nil
	if !passOK || u.Status != "ATIVO" || !s.tenantActive(ctx, u.TenantID) {
		var uu *User
		if err == nil {
			uu = u
			s.audit(ctx, u.TenantID, u.ID, u.Role, "LOGIN_FALHA", map[string]any{"motivo": "credenciais ou conta inativa"}, ip, ua)
		}
		s.registerFailure(ctx, uu, in.Email, ip, ua)
		problem.Write(c, problem.Unauthorized("e-mail ou senha inválidos"))
		return
	}
	s.Redis.Del(ctx, "fail:"+strings.ToLower(in.Email))
	// Dispositivo confiável: o 2FA é dispensado no login (continua obrigatório nas ações sensíveis).
	if v, e := c.Cookie(cookieTD); e == nil && s.trustValid(v, u.ID) {
		t, err := s.NewSession(ctx, u, ip, ua, []string{"pwd", "trusted_device"})
		if err != nil {
			problem.Write(c, problem.Internal())
			return
		}
		s.audit(ctx, u.TenantID, u.ID, u.Role, "LOGIN_OK", map[string]any{"dispositivo_confiavel": true}, ip, ua)
		s.setAuthCookies(c, t)
		c.JSON(http.StatusOK, tokensBody(t, u))
		return
	}
	tok, tk, err := s.StartTicket(ctx, u, "login", ip, ua, in.Trust)
	if err != nil {
		problem.Write(c, problem.New(502, "email-indisponivel", "não foi possível enviar o código por e-mail"))
		return
	}
	s.audit(ctx, u.TenantID, u.ID, u.Role, "LOGIN_SENHA_OK", map[string]any{"mfa": "enviado"}, ip, ua)
	c.JSON(http.StatusOK, gin.H{"mfa_ticket": tok, "mfa_required": true, "expira_em": time.Now().Add(TicketTTL), "reenvio_em": tk.ResendAt, "email_mascarado": maskEmail(u.Email)})
}

func maskEmail(e string) string {
	i := strings.Index(e, "@")
	if i < 2 {
		return e
	}
	return e[:1] + strings.Repeat("*", i-2) + e[i-1:]
}

func (s *Service) mfaVerify(c *gin.Context) {
	var in struct {
		Ticket string `json:"mfa_ticket" binding:"required"`
		Code   string `json:"code" binding:"required"`
		Trust  bool   `json:"confiar_dispositivo"`
	}
	if err := c.ShouldBindJSON(&in); err != nil {
		problem.Write(c, problem.BadRequest("informe o ticket e o código"))
		return
	}
	ctx, ip, ua := c.Request.Context(), c.ClientIP(), c.Request.UserAgent()
	if ok, _ := s.Allow(ctx, "mfa:ip:"+ip, 40, 10*time.Minute); !ok {
		problem.Write(c, problem.TooMany("muitas tentativas"))
		return
	}
	t, err := s.VerifyTicket(ctx, in.Ticket, in.Code, "login")
	if err != nil {
		if t != nil {
			if u, e := s.loadUserByID(ctx, t.UID); e == nil {
				s.audit(ctx, u.TenantID, u.ID, u.Role, "MFA_FALHA", map[string]any{"tentativa": t.Attempts}, ip, ua)
			}
		}
		problem.Write(c, problem.Unauthorized(ErrCode.Error()))
		return
	}
	u, err := s.loadUserByID(ctx, t.UID)
	if err != nil || u.Status != "ATIVO" {
		problem.Write(c, problem.Unauthorized("conta inativa"))
		return
	}
	tk, err := s.NewSession(ctx, u, ip, ua, []string{"pwd", "otp"})
	if err != nil {
		problem.Write(c, problem.Internal())
		return
	}
	s.audit(ctx, u.TenantID, u.ID, u.Role, "LOGIN_OK", map[string]any{"mfa": "ok"}, ip, ua)
	s.setAuthCookies(c, tk)
	if in.Trust || t.Trust {
		c.SetSameSite(http.SameSiteStrictMode)
		c.SetCookie(cookieTD, s.trustCookieValue(u.ID), TrustDays*86400, "/api/v1/auth/login", "", s.Cfg.CookieSecure, true)
	}
	c.JSON(http.StatusOK, tokensBody(tk, u))
}

func (s *Service) mfaResend(c *gin.Context) {
	var in struct {
		Ticket string `json:"mfa_ticket" binding:"required"`
	}
	if c.ShouldBindJSON(&in) != nil {
		problem.Write(c, problem.BadRequest("ticket obrigatório"))
		return
	}
	next, err := s.Resend(c.Request.Context(), in.Ticket)
	if err != nil {
		problem.Write(c, problem.TooMany(err.Error()))
		return
	}
	c.JSON(http.StatusOK, gin.H{"reenvio_em": next})
}

func (s *Service) refresh(c *gin.Context) {
	rt, err := c.Cookie(cookieRT)
	csrfC, _ := c.Cookie(cookieCSRF)
	if err != nil || csrfC == "" || c.GetHeader("X-CSRF-Token") != csrfC {
		problem.Write(c, problem.Unauthorized("sessão ausente"))
		return
	}
	tk, u, err := s.Rotate(c.Request.Context(), rt, c.ClientIP(), c.Request.UserAgent())
	if err != nil {
		c.SetSameSite(http.SameSiteStrictMode)
		c.SetCookie(cookieRT, "", -1, "/api/v1/auth/refresh", "", s.Cfg.CookieSecure, true)
		problem.Write(c, problem.Unauthorized(ErrRefresh.Error()))
		return
	}
	s.setAuthCookies(c, tk)
	c.JSON(http.StatusOK, tokensBody(tk, u))
}

func (s *Service) logout(c *gin.Context) {
	cl := ClaimsOf(c)
	s.runTx(c, cl, func(tx pgx.Tx) error { return s.RevokeSession(c.Request.Context(), tx, cl.Session) })
	s.audit(c.Request.Context(), cl.TenantID, cl.Subject, cl.Role, "LOGOUT", nil, c.ClientIP(), c.Request.UserAgent())
	c.SetCookie(cookieRT, "", -1, "/api/v1/auth/refresh", "", s.Cfg.CookieSecure, true)
	c.Status(http.StatusNoContent)
}

func (s *Service) runTx(c *gin.Context, cl *jwtx.Claims, fn func(pgx.Tx) error) error {
	return s.DB.System(c.Request.Context(), fn)
}

func (s *Service) me(c *gin.Context) {
	cl := ClaimsOf(c)
	u, err := s.loadUserByID(c.Request.Context(), cl.Subject)
	if err != nil {
		problem.Write(c, problem.Unauthorized("usuário não encontrado"))
		return
	}
	out := userBody(u)
	if u.TenantID != "" {
		s.DB.System(c.Request.Context(), func(tx pgx.Tx) error {
			var nome, porte string
			if tx.QueryRow(c.Request.Context(), `SELECT coalesce(nome_fantasia, razao_social), porte FROM tenants WHERE id=$1`, u.TenantID).Scan(&nome, &porte) == nil {
				out["empresa"] = gin.H{"nome": nome, "porte": porte}
			}
			return nil
		})
	}
	out["sessao_id"] = cl.Session
	c.JSON(http.StatusOK, out)
}

func (s *Service) listSessions(c *gin.Context) {
	cl := ClaimsOf(c)
	var out []gin.H
	s.DB.System(c.Request.Context(), func(tx pgx.Tx) error {
		rows, _ := tx.Query(c.Request.Context(), `SELECT id::text, coalesce(dispositivo,''), coalesce(ip,''), criado_em, ultimo_uso FROM sessions
		  WHERE user_id=$1 AND revogado_em IS NULL AND expira_em>now() ORDER BY ultimo_uso DESC`, cl.Subject)
		defer rows.Close()
		for rows.Next() {
			var id, d, ip string
			var cr, lu time.Time
			rows.Scan(&id, &d, &ip, &cr, &lu)
			out = append(out, gin.H{"id": id, "dispositivo": d, "ip": ip, "criado_em": cr, "ultimo_uso": lu, "atual": id == cl.Session})
		}
		return nil
	})
	if out == nil {
		out = []gin.H{}
	}
	c.JSON(http.StatusOK, out)
}

func (s *Service) deleteSession(c *gin.Context) {
	cl := ClaimsOf(c)
	id := c.Param("id")
	err := s.DB.System(c.Request.Context(), func(tx pgx.Tx) error {
		var owner string
		if e := tx.QueryRow(c.Request.Context(), `SELECT user_id::text FROM sessions WHERE id=$1`, id).Scan(&owner); e != nil {
			return problem.NotFound("sessão não encontrada")
		}
		if owner != cl.Subject {
			return problem.Forbidden("sessão de outro usuário")
		}
		return s.RevokeSession(c.Request.Context(), tx, id)
	})
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	c.Status(http.StatusNoContent)
}

// stepUp: sem "code" envia um novo código por e-mail; com "ticket"+"code" devolve o token de step-up (5 min).
func (s *Service) stepUp(c *gin.Context) {
	cl := ClaimsOf(c)
	var in struct {
		Ticket string `json:"ticket"`
		Code   string `json:"code"`
	}
	c.ShouldBindJSON(&in)
	ctx, ip, ua := c.Request.Context(), c.ClientIP(), c.Request.UserAgent()
	u, err := s.loadUserByID(ctx, cl.Subject)
	if err != nil {
		problem.Write(c, problem.Unauthorized("usuário não encontrado"))
		return
	}
	if in.Code == "" {
		if ok, _ := s.Allow(ctx, "stepup:"+u.ID, 5, 10*time.Minute); !ok {
			problem.Write(c, problem.TooMany("muitos pedidos de código"))
			return
		}
		tok, tk, err := s.StartTicket(ctx, u, "stepup", ip, ua, false)
		if err != nil {
			problem.Write(c, problem.New(502, "email-indisponivel", "não foi possível enviar o código"))
			return
		}
		c.JSON(http.StatusAccepted, gin.H{"ticket": tok, "reenvio_em": tk.ResendAt})
		return
	}
	t, err := s.VerifyTicket(ctx, in.Ticket, in.Code, "stepup")
	if err != nil || t.UID != u.ID {
		problem.Write(c, problem.Unauthorized(ErrCode.Error()))
		return
	}
	tok, err := s.JWT.Sign(jwtx.Claims{TenantID: u.TenantID, Role: u.Role, Session: cl.Session, AMR: []string{"pwd", "otp", "stepup"}, Purpose: "stepup",
		RegisteredClaims: jwtRegistered(u.ID)}, StepUpTTL)
	if err != nil {
		problem.Write(c, problem.Internal())
		return
	}
	s.audit(ctx, u.TenantID, u.ID, u.Role, "STEP_UP_OK", nil, ip, ua)
	c.JSON(http.StatusOK, gin.H{"token": tok, "expires_in": int(StepUpTTL.Seconds())})
}

func (s *Service) changePassword(c *gin.Context) {
	cl := ClaimsOf(c)
	var in struct {
		Atual string `json:"senha_atual" binding:"required"`
		Nova  string `json:"nova_senha" binding:"required"`
	}
	if c.ShouldBindJSON(&in) != nil {
		problem.Write(c, problem.BadRequest("informe a senha atual e a nova"))
		return
	}
	ctx := c.Request.Context()
	u, _ := s.loadUserByID(ctx, cl.Subject)
	if !VerifyPassword(in.Atual, u.SenhaHash) {
		problem.Write(c, problem.Forbidden("senha atual incorreta"))
		return
	}
	if err := CheckPolicy(in.Nova, s.Cfg.Prod()); err != nil {
		problem.Write(c, problem.BadRequest(err.Error()))
		return
	}
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		if _, e := tx.Exec(ctx, `UPDATE users SET senha_hash=$2 WHERE id=$1`, u.ID, HashPassword(in.Nova)); e != nil {
			return e
		}
		return s.RevokeAllForUser(ctx, tx, u.ID) // trocar a senha revoga tudo
	})
	if err != nil {
		problem.Write(c, problem.Internal())
		return
	}
	s.audit(ctx, u.TenantID, u.ID, u.Role, "SENHA_ALTERADA", nil, c.ClientIP(), c.Request.UserAgent())
	c.Status(http.StatusNoContent)
}

// inviteAccept: o convidado define a senha com o token recebido por e-mail.
func (s *Service) inviteAccept(c *gin.Context) {
	var in struct {
		Token string `json:"token" binding:"required"`
		Senha string `json:"senha" binding:"required"`
	}
	if c.ShouldBindJSON(&in) != nil {
		problem.Write(c, problem.BadRequest("token e senha são obrigatórios"))
		return
	}
	if err := CheckPolicy(in.Senha, s.Cfg.Prod()); err != nil {
		problem.Write(c, problem.BadRequest(err.Error()))
		return
	}
	ctx := c.Request.Context()
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		var uid, tid string
		var role string
		// só convite pendente de quem ainda está CONVIDADO: um usuário desativado depois do convite não se reativa pelo link
		if e := tx.QueryRow(ctx, `SELECT i.user_id::text, coalesce(u.tenant_id::text,''), u.role FROM user_invites i JOIN users u ON u.id=i.user_id
		  WHERE i.token_hash=$1 AND i.usado_em IS NULL AND i.expira_em>now() AND u.status='CONVIDADO'`, sha(in.Token)).Scan(&uid, &tid, &role); e != nil {
			return problem.BadRequest("convite inválido ou expirado")
		}
		tx.Exec(ctx, `UPDATE user_invites SET usado_em=now() WHERE token_hash=$1`, sha(in.Token))
		_, e := tx.Exec(ctx, `UPDATE users SET senha_hash=$2, status='ATIVO' WHERE id=$1 AND status='CONVIDADO'`, uid, HashPassword(in.Senha))
		return e
	})
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	c.Status(http.StatusNoContent)
}
