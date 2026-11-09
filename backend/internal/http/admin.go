package http

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cnpj"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// masterAudit registra a ação do Master na trilha global e, se houver empresa, na trilha da empresa (ela enxerga o acesso).
func (s *Server) masterAudit(ctx context.Context, tx pgx.Tx, c *gin.Context, tenantID, acao, entidade, id string, dados any) error {
	cl := auth.ClaimsOf(c)
	for _, t := range uniqueTenants(tenantID) {
		if err := audit.Log(ctx, tx, audit.Event{TenantID: t, Actor: cl.Subject, ActorRole: "MASTER", Acao: acao, Entidade: entidade, EntidadeID: id, Dados: dados, IP: c.ClientIP(), UA: c.Request.UserAgent()}); err != nil {
			return err
		}
	}
	return nil
}

func uniqueTenants(t string) []string {
	if t == "" {
		return []string{""}
	}
	return []string{"", t}
}

func (s *Server) adminRoutes(m *gin.RouterGroup, v1 *gin.RouterGroup) {
	m.GET("/overview", s.adminOverview)
	m.GET("/tenants", s.adminListTenants)
	m.POST("/tenants", s.adminCreateTenant)
	m.GET("/tenants/:id", s.adminGetTenant)
	m.PATCH("/tenants/:id", s.adminPatchTenant)
	m.POST("/tenants/:id/status", s.adminTenantStatus)
	m.GET("/tenants/:id/users", s.adminTenantUsers)
	m.POST("/tenants/:id/users/:uid/reset-2fa", s.adminReset2FA)
	m.GET("/tenants/:id/audit", s.adminTenantAudit)
	m.GET("/tenants/:id/usage", s.adminTenantUsage)
	m.GET("/tenants/:id/support-access", s.adminSupportList)
	m.GET("/plans", s.adminPlans)
	m.PATCH("/plans/:id", s.adminPatchPlan)
	m.GET("/storage", s.adminStorage)
	m.GET("/document-types", s.listDocTypes)
	m.PATCH("/document-types/:id", s.adminPatchDocType)
	m.GET("/ia/overview", s.adminIAOverview)
	m.GET("/ia/dead-letters", s.adminDeadLetters)
	m.POST("/ia/dead-letters/:id/retry", s.adminRetryDead)
	m.GET("/ia/quality", s.adminQuality)
	m.GET("/audit", s.adminAudit)
	m.GET("/audit/verify", s.adminAuditVerify)
	m.GET("/users", s.adminMasterUsers)
	m.POST("/users", s.adminInviteMaster)
	m.POST("/support-access/:tenantId", s.adminRequestSupport)
	m.POST("/reset", s.Auth.RequireStepUp(), s.adminReset) // apaga os dados das empresas: só Master, com código por e-mail e frase de confirmação
	m.GET("/leads", s.adminLeads)
}

func (s *Server) adminOverview(c *gin.Context) {
	s.sysJSON(c, `SELECT json_build_object(
	 'clientes_por_porte', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT porte, count(*) AS n FROM tenants WHERE status='ATIVO' GROUP BY 1 ORDER BY 1) x),
	 'clientes_ativos', (SELECT count(*) FROM tenants WHERE status='ATIVO'),
	 'paginas_mes', (SELECT coalesce(sum(paginas),0) FROM usage_monthly WHERE mes=to_char(now(),'YYYY-MM')),
	 'armazenamento_total', (SELECT coalesce(sum(bytes_usados),0) FROM tenants),
	 'taxa_revisao_pct', (SELECT round(100.0*count(*) FILTER (WHERE status IN ('REVISADO','AGUARDANDO_REVISAO'))/nullif(count(*),0),1) FROM documents WHERE criado_em > now()-interval '30 days'),
	 'falhas_ia', (SELECT count(*) FROM batches WHERE status='FALHOU' OR tentativas>0),
	 'mrr_centavos', (SELECT coalesce(sum(p.preco_mensal_centavos),0) FROM tenants t JOIN plans p ON p.id=t.plano_id WHERE t.status='ATIVO'),
	 'paginas_por_dia', (SELECT coalesce(json_agg(x ORDER BY x.dia),'[]') FROM (SELECT to_char(b.criado_em,'YYYY-MM-DD') AS dia, sum(b.total_paginas) AS paginas FROM batches b WHERE b.criado_em > now()-interval '30 days' GROUP BY 1) x),
	 'perto_da_cota', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT id, coalesce(nome_fantasia,razao_social) AS nome, bytes_usados, quota_bytes, round(100.0*bytes_usados/quota_bytes,1) AS pct FROM tenants WHERE bytes_usados >= quota_bytes*0.8 ORDER BY pct DESC) x))`)
}

func (s *Server) adminListTenants(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.razao_social),'[]') FROM (SELECT t.id, t.cnpj, t.razao_social, t.nome_fantasia, t.porte, t.status, p.nome AS plano, t.bytes_usados, t.quota_bytes, t.criado_em,
	  (SELECT count(*) FROM employees e WHERE e.tenant_id=t.id) AS funcionarios, (SELECT count(*) FROM users u WHERE u.tenant_id=t.id) AS usuarios
	  FROM tenants t LEFT JOIN plans p ON p.id=t.plano_id) t`)
}

func (s *Server) adminGetTenant(c *gin.Context) {
	s.sysJSON(c, `SELECT row_to_json(t) FROM (SELECT t.id, t.cnpj, t.razao_social, t.nome_fantasia, t.endereco, t.porte, t.status, t.plano_id, p.nome AS plano, t.dominios_email, t.responsavel_financeiro,
	  t.quota_bytes, t.bytes_usados, t.quota_paginas_mes, t.max_usuarios_rh, t.max_funcionarios, t.criado_em FROM tenants t LEFT JOIN plans p ON p.id=t.plano_id WHERE t.id=$1) t`, c.Param("id"))
}

func (s *Server) adminCreateTenant(c *gin.Context) {
	var in struct {
		CNPJ        string         `json:"cnpj" binding:"required"`
		Razao       string         `json:"razao_social" binding:"required"`
		Fantasia    string         `json:"nome_fantasia"`
		Porte       string         `json:"porte" binding:"required,oneof=PEQUENA MEDIA GRANDE"`
		Dominios    []string       `json:"dominios_email"`
		Endereco    map[string]any `json:"endereco"`
		Responsavel map[string]any `json:"responsavel_financeiro"`
		AdminNome   string         `json:"admin_nome" binding:"required"`
		AdminEmail  string         `json:"admin_email" binding:"required,email"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if !cnpj.Valid(in.CNPJ) {
		problem.Write(c, problem.BadRequest("CNPJ inválido (confira os dígitos)"))
		return
	}
	if len(in.Dominios) == 0 {
		in.Dominios = []string{app.EmailDomain(in.AdminEmail)}
	}
	for i, d := range in.Dominios {
		in.Dominios[i] = strings.TrimPrefix(strings.ToLower(strings.TrimSpace(d)), "@")
	}
	wrapped, err := s.NewTenantKey()
	if err != nil {
		problem.Write(c, problem.Internal())
		return
	}
	token := randHex(32)
	var tenantID string
	if !s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		err := tx.QueryRow(ctx, `INSERT INTO tenants (cnpj, razao_social, nome_fantasia, porte, plano_id, dominios_email, endereco, responsavel_financeiro, quota_bytes, quota_paginas_mes, max_usuarios_rh, max_funcionarios, dek_wrapped)
		  SELECT $1,$2,nullif($3,''),$4,p.id,$5,$6,$7,p.quota_bytes,p.quota_paginas_mes,p.max_usuarios_rh,p.max_funcionarios,$8 FROM plans p WHERE p.codigo=$4 RETURNING id::text`,
			cnpj.Clean(in.CNPJ), in.Razao, in.Fantasia, in.Porte, in.Dominios, mustJSON(orEmpty(in.Endereco)), mustJSON(orEmpty(in.Responsavel)), wrapped).Scan(&tenantID)
		if err != nil {
			if strings.Contains(err.Error(), "tenants_cnpj_key") {
				return problem.Conflict("já existe uma empresa com este CNPJ")
			}
			return err
		}
		var uid string
		if err := tx.QueryRow(ctx, `INSERT INTO users (tenant_id,email,nome,role,status) VALUES ($1,lower($2),$3,'ADMIN_EMPRESA','CONVIDADO') RETURNING id::text`, tenantID, in.AdminEmail, in.AdminNome).Scan(&uid); err != nil {
			if strings.Contains(err.Error(), "users_email_uq") {
				return problem.Conflict("já existe um usuário com este e-mail")
			}
			return err
		}
		tx.Exec(ctx, `INSERT INTO user_invites (user_id, token_hash, expira_em) VALUES ($1,$2,$3)`, uid, sha256hex(token), time.Now().Add(72*time.Hour))
		tx.Exec(ctx, `INSERT INTO subscriptions (tenant_id, plano_id) SELECT $1, plano_id FROM tenants WHERE id=$1`, tenantID)
		return s.masterAudit(ctx, tx, c, tenantID, "EMPRESA_CRIADA", "tenant", tenantID, map[string]any{"porte": in.Porte})
	}) {
		return
	}
	s.Mail.Send(in.AdminEmail, "Citadel IA · acesso da sua empresa", fmt.Sprintf("Olá, %s.\n\nA empresa %s foi cadastrada na Citadel IA. Defina sua senha (mínimo de 12 caracteres) pelo link, válido por 72 horas:\n\n%s/convite?token=%s\n", in.AdminNome, in.Razao, s.Cfg.AppURL, token))
	c.JSON(http.StatusCreated, gin.H{"id": tenantID})
}

func orEmpty(m map[string]any) map[string]any {
	if m == nil {
		return map[string]any{}
	}
	return m
}

func (s *Server) adminPatchTenant(c *gin.Context) {
	var in struct {
		Fantasia     *string  `json:"nome_fantasia"`
		Porte        *string  `json:"porte"`
		QuotaBytes   *int64   `json:"quota_bytes"`
		QuotaPaginas *int     `json:"quota_paginas_mes"`
		MaxUsuarios  *int     `json:"max_usuarios_rh"`
		MaxFunc      *int     `json:"max_funcionarios"`
		PlanoID      *string  `json:"plano_id"`
		Dominios     []string `json:"dominios_email"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `UPDATE tenants SET nome_fantasia=coalesce($2,nome_fantasia), porte=coalesce($3,porte), quota_bytes=coalesce($4,quota_bytes), quota_paginas_mes=coalesce($5,quota_paginas_mes),
		  max_usuarios_rh=coalesce($6,max_usuarios_rh), max_funcionarios=coalesce($7,max_funcionarios), plano_id=coalesce($8::uuid,plano_id), dominios_email=coalesce($9,dominios_email) WHERE id=$1`,
			c.Param("id"), in.Fantasia, in.Porte, in.QuotaBytes, in.QuotaPaginas, in.MaxUsuarios, in.MaxFunc, in.PlanoID, in.Dominios)
		if err != nil {
			return err
		}
		return s.masterAudit(ctx, tx, c, c.Param("id"), "EMPRESA_ALTERADA_MASTER", "tenant", c.Param("id"), map[string]any{"quota_bytes": in.QuotaBytes, "quota_paginas": in.QuotaPaginas, "plano": in.PlanoID})
	}) {
		c.Status(204)
	}
}

func (s *Server) adminTenantStatus(c *gin.Context) {
	var in struct {
		Status string `json:"status" binding:"required,oneof=ATIVO SUSPENSO ENCERRADO"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `UPDATE tenants SET status=$2 WHERE id=$1`, c.Param("id"), in.Status); err != nil {
			return err
		}
		if in.Status != "ATIVO" { // suspender/encerrar derruba as sessões
			rows, _ := tx.Query(ctx, `SELECT id::text FROM users WHERE tenant_id=$1`, c.Param("id"))
			var ids []string
			for rows.Next() {
				var id string
				rows.Scan(&id)
				ids = append(ids, id)
			}
			rows.Close()
			for _, id := range ids {
				s.Auth.RevokeAllForUser(ctx, tx, id)
			}
		}
		return s.masterAudit(ctx, tx, c, c.Param("id"), "EMPRESA_STATUS_"+in.Status, "tenant", c.Param("id"), nil)
	}) {
		c.Status(204)
	}
}

func (s *Server) adminTenantUsers(c *gin.Context) { // só metadados, nunca conteúdo
	s.sysJSON(c, `SELECT coalesce(json_agg(u ORDER BY u.nome),'[]') FROM (SELECT id, nome, email, role, status, ultimo_login FROM users WHERE tenant_id=$1) u`, c.Param("id"))
}

// POST /admin/tenants/:id/users/:uid/reset-2fa — encerra sessões e dispositivos confiáveis (justificativa obrigatória).
func (s *Server) adminReset2FA(c *gin.Context) {
	var in struct {
		Justificativa string `json:"justificativa" binding:"required,min=10"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := s.Auth.RevokeAllForUser(ctx, tx, c.Param("uid")); err != nil {
			return err
		}
		tx.Exec(ctx, `UPDATE users SET status='CONVIDADO' WHERE id=$1 AND role='ADMIN_EMPRESA'`, c.Param("uid"))
		return s.masterAudit(ctx, tx, c, c.Param("id"), "RESET_2FA_ADMIN", "user", c.Param("uid"), map[string]any{"justificativa": in.Justificativa})
	}) {
		c.Status(204)
	}
}

func (s *Server) adminTenantAudit(c *gin.Context) {
	s.adminAuditFor(c, c.Param("id"))
}

func (s *Server) adminAudit(c *gin.Context) { s.adminAuditFor(c, c.Query("tenant")) }

// Auditoria global do Master: exige motivo e o próprio acesso fica registrado (a empresa vê).
func (s *Server) adminAuditFor(c *gin.Context, tenantID string) {
	motivo := strings.TrimSpace(c.Query("motivo"))
	if len(motivo) < 10 {
		problem.Write(c, problem.BadRequest("informe o motivo da consulta (mín. 10 caracteres) no parâmetro 'motivo'"))
		return
	}
	limit := limitOf(c, 50, 200)
	args := []any{nullIfEmpty(tenantID), limit + 1}
	where := `($1::uuid IS NULL OR a.tenant_id=$1::uuid)`
	if cur := decodeCursor(c.Query("cursor")); len(cur) >= 1 {
		args = append(args, cur[0])
		where += fmt.Sprintf(" AND a.id < $%d::bigint", len(args))
	}
	var raw []byte
	if !s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := s.masterAudit(ctx, tx, c, tenantID, "AUDITORIA_CONSULTADA_MASTER", "audit", tenantID, map[string]any{"motivo": motivo}); err != nil {
			return err
		}
		return tx.QueryRow(ctx, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT a.id, a.tenant_id, a.acao, a.entidade, a.entidade_id, a.dados, a.ator_role, a.ip, a.criado_em, u.nome AS ator_nome
		  FROM audit_log a LEFT JOIN users u ON u.id=a.ator WHERE `+where+` ORDER BY a.id DESC LIMIT $2) t`, args...).Scan(&raw)
	}) {
		return
	}
	c.JSON(200, pageOf(raw, limit, "id"))
}

func (s *Server) adminAuditVerify(c *gin.Context) {
	tenant := c.Query("tenant")
	var ok bool
	var broken int64
	var n int
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		var e error
		ok, broken, n, e = audit.Verify(ctx, tx, tenant)
		return e
	}) {
		c.JSON(200, gin.H{"integra": ok, "primeiro_elo_quebrado": broken, "eventos": n})
	}
}

func (s *Server) adminTenantUsage(c *gin.Context) {
	s.sysJSON(c, `SELECT json_build_object(
	 'mensal', (SELECT coalesce(json_agg(u ORDER BY u.mes DESC),'[]') FROM (SELECT mes, paginas, docs, revisoes, bytes_total, tokens, custo_ia_centavos FROM usage_monthly WHERE tenant_id=$1 ORDER BY mes DESC LIMIT 12) u),
	 'eventos', (SELECT coalesce(json_agg(e),'[]') FROM (SELECT tipo, bytes, objeto, criado_em FROM storage_events WHERE tenant_id=$1 ORDER BY criado_em DESC LIMIT 50) e),
	 'maiores_lotes', (SELECT coalesce(json_agg(b),'[]') FROM (SELECT id, arquivo_original, bytes, total_paginas, criado_em FROM batches WHERE tenant_id=$1 ORDER BY bytes DESC LIMIT 5) b),
	 'faturas', (SELECT coalesce(json_agg(i),'[]') FROM (SELECT id, referencia, valor_centavos, status, vencimento FROM invoices WHERE tenant_id=$1 ORDER BY criado_em DESC LIMIT 12) i))`, c.Param("id"))
}

func (s *Server) adminSupportList(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.criado_em DESC),'[]') FROM (SELECT sa.id, sa.motivo, sa.status, sa.expira_em, sa.criado_em, u.nome AS solicitante FROM support_access sa JOIN users u ON u.id=sa.solicitado_por WHERE sa.tenant_id=$1) t`, c.Param("id"))
}

func (s *Server) adminRequestSupport(c *gin.Context) {
	var in struct {
		Motivo string `json:"motivo" binding:"required,min=10"`
	}
	if !bindJSON(c, &in) {
		return
	}
	var id string
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `INSERT INTO support_access (tenant_id, solicitado_por, motivo) VALUES ($1,$2,$3) RETURNING id::text`, c.Param("tenantId"), auth.ClaimsOf(c).Subject, in.Motivo).Scan(&id); err != nil {
			return err
		}
		tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'SUPORTE','Novo pedido de acesso de suporte aguardando sua aprovação','/configuracoes/suporte')`, c.Param("tenantId"))
		return s.masterAudit(ctx, tx, c, c.Param("tenantId"), "ACESSO_SUPORTE_SOLICITADO", "support_access", id, map[string]any{"motivo": in.Motivo})
	}) {
		c.JSON(http.StatusCreated, gin.H{"id": id, "status": "PENDENTE"})
	}
}

func (s *Server) adminPlans(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(p ORDER BY p.quota_bytes),'[]') FROM (SELECT p.id, p.codigo, p.nome, p.porte, p.quota_bytes, p.quota_paginas_mes, p.max_usuarios_rh, p.max_funcionarios, p.preco_mensal_centavos,
	  (SELECT count(*) FROM tenants t WHERE t.plano_id=p.id) AS clientes FROM plans p) p`)
}

func (s *Server) adminPatchPlan(c *gin.Context) {
	var in struct {
		QuotaBytes   *int64 `json:"quota_bytes"`
		QuotaPaginas *int   `json:"quota_paginas_mes"`
		MaxUsuarios  *int   `json:"max_usuarios_rh"`
		MaxFunc      *int   `json:"max_funcionarios"`
		Preco        *int64 `json:"preco_mensal_centavos"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `UPDATE plans SET quota_bytes=coalesce($2,quota_bytes), quota_paginas_mes=coalesce($3,quota_paginas_mes), max_usuarios_rh=coalesce($4,max_usuarios_rh),
		  max_funcionarios=coalesce($5,max_funcionarios), preco_mensal_centavos=coalesce($6,preco_mensal_centavos) WHERE id=$1`, c.Param("id"), in.QuotaBytes, in.QuotaPaginas, in.MaxUsuarios, in.MaxFunc, in.Preco)
		if err != nil {
			return err
		}
		return s.masterAudit(ctx, tx, c, "", "PLANO_ALTERADO", "plan", c.Param("id"), in)
	}) {
		c.Status(204)
	}
}

func (s *Server) adminStorage(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.pct DESC),'[]') FROM (SELECT t.id, coalesce(t.nome_fantasia,t.razao_social) AS nome, t.porte, t.bytes_usados, t.quota_bytes,
	  round(100.0*t.bytes_usados/nullif(t.quota_bytes,0),1) AS pct, coalesce((SELECT paginas FROM usage_monthly u WHERE u.tenant_id=t.id AND u.mes=to_char(now(),'YYYY-MM')),0) AS paginas_mes, t.quota_paginas_mes,
	  (SELECT coalesce(sum(bytes),0) FROM storage_events s WHERE s.tenant_id=t.id AND s.criado_em > now()-interval '30 days') AS crescimento_30d FROM tenants t) t`)
}

func (s *Server) adminPatchDocType(c *gin.Context) {
	var in struct {
		Nome      *string `json:"nome"`
		Validade  *int    `json:"validade_padrao_dias"`
		Retencao  *int    `json:"retencao_padrao_dias"`
		Categoria *string `json:"categoria"`
		Revisado  *bool   `json:"revisado"` // true confirma um tipo que a IA descobriu (as pistas aprendidas continuam valendo)
	}
	if !bindJSON(c, &in) {
		return
	}
	if s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `UPDATE document_types SET nome=coalesce($2,nome), validade_padrao_dias=coalesce($3,validade_padrao_dias), retencao_padrao_dias=coalesce($4,retencao_padrao_dias), categoria=coalesce($5,categoria), revisado_em=CASE WHEN $6::boolean IS TRUE AND origem='IA' THEN coalesce(revisado_em, now()) ELSE revisado_em END WHERE id=$1`,
			c.Param("id"), in.Nome, in.Validade, in.Retencao, in.Categoria, in.Revisado)
		if err != nil {
			return err
		}
		return s.masterAudit(ctx, tx, c, "", "CATALOGO_ALTERADO", "document_type", c.Param("id"), in)
	}) {
		c.Status(204)
	}
}

func (s *Server) adminIAOverview(c *gin.Context) {
	s.sysJSON(c, `SELECT json_build_object(
	 'fila', (SELECT json_build_object('processando', count(*) FILTER (WHERE status='PROCESSANDO'), 'recebidos', count(*) FILTER (WHERE status='RECEBIDO'), 'falhos', count(*) FILTER (WHERE status='FALHOU')) FROM batches),
	 'tempo_medio_por_pagina_seg', (SELECT round((extract(epoch FROM sum(concluido_em-iniciado_em))/nullif(sum(total_paginas),0))::numeric,2) FROM batches WHERE concluido_em IS NOT NULL AND status LIKE 'PROCESSADO%'),
	 'reprocessamentos', (SELECT coalesce(sum(tentativas),0) FROM batches),
	 'dead_letters_abertas', (SELECT count(*) FROM dead_letters WHERE resolvido_em IS NULL),
	 'custo_por_empresa', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT coalesce(t.nome_fantasia,t.razao_social) AS empresa, sum(u.tokens) AS tokens, sum(u.custo_ia_centavos) AS custo_centavos
	    FROM usage_monthly u JOIN tenants t ON t.id=u.tenant_id WHERE u.mes=to_char(now(),'YYYY-MM') GROUP BY 1 ORDER BY 3 DESC) x))`)
}

func (s *Server) adminDeadLetters(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.criado_em DESC),'[]') FROM (SELECT d.id, d.batch_id, d.tipo, d.erro, d.tentativas, d.resolvido_em, d.criado_em, coalesce(te.nome_fantasia,te.razao_social) AS empresa, b.arquivo_original
	  FROM dead_letters d JOIN tenants te ON te.id=d.tenant_id LEFT JOIN batches b ON b.id=d.batch_id ORDER BY d.criado_em DESC LIMIT 200) t`)
}

func (s *Server) adminRetryDead(c *gin.Context) {
	var tenantID, batchID string
	if !s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `SELECT tenant_id::text, batch_id::text FROM dead_letters WHERE id=$1`, c.Param("id")).Scan(&tenantID, &batchID); err != nil {
			return problem.NotFound("item não encontrado")
		}
		return s.masterAudit(ctx, tx, c, tenantID, "DLQ_RETOMADA", "batch", batchID, nil)
	}) {
		return
	}
	if err := s.Batches.Retomar(c.Request.Context(), tenantID, batchID, auth.ClaimsOf(c).Subject); err != nil {
		problem.Write(c, problem.Conflict(err.Error()))
		return
	}
	c.Status(http.StatusAccepted)
}

func (s *Server) adminQuality(c *gin.Context) {
	raw, err := s.IA.Quality(c.Request.Context())
	if err != nil {
		problem.Write(c, problem.New(502, "ia-indisponivel", err.Error()))
		return
	}
	c.Data(200, "application/json", raw)
}

func (s *Server) adminMasterUsers(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(u ORDER BY u.nome),'[]') FROM (SELECT id, nome, email, status, ultimo_login, criado_em FROM users WHERE role='MASTER') u`)
}

func (s *Server) adminInviteMaster(c *gin.Context) {
	var in struct {
		Nome  string `json:"nome" binding:"required"`
		Email string `json:"email" binding:"required,email"`
	}
	if !bindJSON(c, &in) {
		return
	}
	token := randHex(32)
	if !s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		var uid string
		if err := tx.QueryRow(ctx, `INSERT INTO users (email,nome,role,status) VALUES (lower($1),$2,'MASTER','CONVIDADO') RETURNING id::text`, in.Email, in.Nome).Scan(&uid); err != nil {
			if strings.Contains(err.Error(), "users_email_uq") {
				return problem.Conflict("já existe um usuário com este e-mail")
			}
			return err
		}
		tx.Exec(ctx, `INSERT INTO user_invites (user_id, token_hash, expira_em) VALUES ($1,$2,$3)`, uid, sha256hex(token), time.Now().Add(72*time.Hour))
		return s.masterAudit(ctx, tx, c, "", "MASTER_CONVIDADO", "user", uid, nil)
	}) {
		return
	}
	s.Mail.Send(in.Email, "Citadel IA · convite Master", fmt.Sprintf("Olá, %s.\n\nDefina sua senha: %s/convite?token=%s\n", in.Nome, s.Cfg.AppURL, token))
	c.Status(http.StatusCreated)
}

func (s *Server) adminLeads(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(l ORDER BY l.criado_em DESC),'[]') FROM (SELECT id, nome, email, empresa, porte, funcionarios, criado_em FROM leads ORDER BY criado_em DESC LIMIT 200) l`)
}

var _ = database.JSON
