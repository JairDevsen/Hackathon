package http

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"golang.org/x/text/cases"
	"golang.org/x/text/language"
	"net/http"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// ---------- unidades e cargos ----------

func (s *Server) listUnits(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(u ORDER BY u.nome),'[]') FROM (SELECT id, nome, cnpj, centro_custo, (SELECT count(*) FROM employees e WHERE e.unit_id=units.id) AS funcionarios FROM units) u`)
}

func (s *Server) saveUnit(c *gin.Context) {
	var in struct {
		Nome        string `json:"nome" binding:"required"`
		CNPJ        string `json:"cnpj"`
		CentroCusto string `json:"centro_custo"`
	}
	if !bindJSON(c, &in) {
		return
	}
	id := c.Param("id")
	var out string
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var err error
		if id == "" {
			err = tx.QueryRow(ctx, `INSERT INTO units (tenant_id,nome,cnpj,centro_custo) VALUES ($1,$2,nullif($3,''),nullif($4,'')) RETURNING id::text`, tid(c), in.Nome, in.CNPJ, in.CentroCusto).Scan(&out)
		} else {
			out = id
			_, err = tx.Exec(ctx, `UPDATE units SET nome=$2, cnpj=nullif($3,''), centro_custo=nullif($4,'') WHERE id=$1`, id, in.Nome, in.CNPJ, in.CentroCusto)
		}
		if err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "UNIDADE_SALVA", "unit", out, nil)
	}) {
		c.JSON(200, gin.H{"id": out})
	}
}

func (s *Server) listPositions(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(p ORDER BY p.nome),'[]') FROM (SELECT id, nome, cbo, descricao, segmento, ativo, (SELECT count(*) FROM employees e WHERE e.cargo_id=positions.id) AS funcionarios FROM positions) p`)
}

func (s *Server) savePosition(c *gin.Context) {
	var in struct {
		Nome      string `json:"nome" binding:"required"`
		CBO       string `json:"cbo"`
		Descricao string `json:"descricao"`
		Segmento  string `json:"segmento"`
		Ativo     *bool  `json:"ativo"`
	}
	if !bindJSON(c, &in) {
		return
	}
	id := c.Param("id")
	var out string
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var err error
		if id == "" {
			err = tx.QueryRow(ctx, `INSERT INTO positions (tenant_id,nome,cbo,descricao,segmento) VALUES ($1,$2,nullif($3,''),nullif($4,''),nullif($5,'')) RETURNING id::text`, tid(c), in.Nome, in.CBO, in.Descricao, in.Segmento).Scan(&out)
		} else {
			out = id
			_, err = tx.Exec(ctx, `UPDATE positions SET nome=$2, cbo=nullif($3,''), descricao=nullif($4,''), segmento=nullif($5,''), ativo=coalesce($6,ativo) WHERE id=$1`, id, in.Nome, in.CBO, in.Descricao, in.Segmento, in.Ativo)
		}
		if err != nil {
			if strings.Contains(err.Error(), "positions_tenant_id_nome_key") {
				return problem.Conflict("já existe um cargo com este nome")
			}
			return err
		}
		return s.audit(ctx, tx, c, "CARGO_SALVO", "position", out, nil)
	}) {
		c.JSON(200, gin.H{"id": out})
	}
}

func (s *Server) listDocTypes(c *gin.Context) {
	s.sysJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.categoria, t.nome),'[]') FROM (SELECT id, codigo, nome, categoria, sensivel_saude, escopo, validade_padrao_dias, retencao_padrao_dias FROM document_types) t`)
}

// ---------- matriz de obrigatoriedade ----------

func (s *Server) listRequirements(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.categoria, t.tipo_nome),'[]') FROM (
	  SELECT r.id, r.position_id, p.nome AS cargo, r.department_id, dp.nome AS setor, dt.id AS document_type_id, dt.codigo, dt.nome AS tipo_nome, dt.categoria, dt.escopo, r.momento, r.validade_dias, r.antecedencia_alerta_dias, r.obrigatorio, r.observacao
	  FROM requirements r JOIN document_types dt ON dt.id=r.document_type_id LEFT JOIN positions p ON p.id=r.position_id LEFT JOIN departments dp ON dp.id=r.department_id
	  WHERE r.employee_id IS NULL) t`)
}

type reqIn struct {
	PositionID   *string `json:"position_id"`
	DepartmentID *string `json:"department_id"`
	EmployeeID   *string `json:"employee_id"`
	DocumentType string  `json:"codigo" binding:"required"`
	Momento      string  `json:"momento" binding:"required"`
	ValidadeDias *int    `json:"validade_dias"`
	Antecedencia *int    `json:"antecedencia_alerta_dias"`
	Obrigatorio  *bool   `json:"obrigatorio"`
	Observacao   string  `json:"observacao"`
}

func upsertReq(ctx context.Context, tx pgx.Tx, tenantID string, in reqIn) error {
	ant, obr := 30, true
	if in.Antecedencia != nil {
		ant = *in.Antecedencia
	}
	if in.Obrigatorio != nil {
		obr = *in.Obrigatorio
	}
	ct, err := tx.Exec(ctx, `INSERT INTO requirements (tenant_id, position_id, department_id, employee_id, document_type_id, momento, validade_dias, antecedencia_alerta_dias, obrigatorio, observacao)
	  SELECT $1,$2::uuid,$9::uuid,$10::uuid,id,$4,$5,$6,$7,nullif($8,'') FROM document_types WHERE codigo=$3
	  ON CONFLICT (tenant_id, coalesce(position_id,'00000000-0000-0000-0000-000000000000'::uuid), coalesce(department_id,'00000000-0000-0000-0000-000000000000'::uuid),
	    coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid), document_type_id, momento)
	  DO UPDATE SET validade_dias=EXCLUDED.validade_dias, antecedencia_alerta_dias=EXCLUDED.antecedencia_alerta_dias, obrigatorio=EXCLUDED.obrigatorio, observacao=EXCLUDED.observacao`,
		tenantID, in.PositionID, in.DocumentType, in.Momento, in.ValidadeDias, ant, obr, in.Observacao, in.DepartmentID, in.EmployeeID)
	if err == nil && ct.RowsAffected() == 0 {
		return problem.BadRequest("tipo documental desconhecido: " + in.DocumentType)
	}
	return err
}

func (s *Server) putRequirement(c *gin.Context) {
	var in reqIn
	if !bindJSON(c, &in) {
		return
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := upsertReq(ctx, tx, tid(c), in); err != nil {
			return err
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "OBRIGATORIEDADE_ALTERADA", "requirement", in.DocumentType, map[string]any{"momento": in.Momento, "obrigatorio": in.Obrigatorio})
	}) {
		c.Status(204)
	}
}

func (s *Server) deleteRequirement(c *gin.Context) {
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `DELETE FROM requirements WHERE id=$1`, c.Param("id")); err != nil {
			return err
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "OBRIGATORIEDADE_REMOVIDA", "requirement", c.Param("id"), nil)
	}) {
		c.Status(204)
	}
}

type tpl struct {
	Codigo, Momento string
	Validade        int
}

var baseTpl = []tpl{{"CONTRATO_TRABALHO", "ADMISSAO", 0}, {"FICHA_REGISTRO", "ADMISSAO", 0}, {"CTPS", "ADMISSAO", 0}, {"RG", "ADMISSAO", 0},
	{"COMPROVANTE_RESIDENCIA", "ADMISSAO", 0}, {"DECLARACAO_VT", "ADMISSAO", 0}, {"ORDEM_SERVICO", "ADMISSAO", 0}, {"ASO", "PERIODICO", 365},
	{"HOLERITE", "MENSAL", 0}, {"CARTAO_PONTO", "MENSAL", 0}, {"TRCT", "DESLIGAMENTO", 0}}

var segTpl = map[string][]tpl{
	"LIMPEZA":        {{"FICHA_EPI", "ADMISSAO", 0}, {"TREINAMENTO_NR", "PERIODICO", 730}},
	"VIGILANCIA":     {{"FICHA_EPI", "ADMISSAO", 0}, {"TREINAMENTO_NR", "PERIODICO", 730}, {"CNH", "PERIODICO", 1825}},
	"MANUTENCAO":     {{"FICHA_EPI", "ADMISSAO", 0}, {"TREINAMENTO_NR", "PERIODICO", 730}},
	"PORTARIA":       {{"RECIBO_BENEFICIOS", "MENSAL", 0}},
	"ADMINISTRATIVO": {},
}
var companyTpl = []tpl{{"CRF_FGTS", "PERIODICO", 30}, {"CNDT", "PERIODICO", 180}, {"CND_FEDERAL", "PERIODICO", 180}, {"GUIA_FGTS", "MENSAL", 0}, {"DARF", "MENSAL", 0}}

// POST /requirements/apply-template {segmento, position_id?, nome_cargo?, empresa?}
func (s *Server) applyTemplate(c *gin.Context) {
	var in struct {
		Segmento   string  `json:"segmento"`
		PositionID *string `json:"position_id"`
		NomeCargo  string  `json:"nome_cargo"`
		Empresa    bool    `json:"empresa"`
	}
	if !bindJSON(c, &in) {
		return
	}
	seg := strings.ToUpper(in.Segmento)
	extra, ok := segTpl[seg]
	if !ok && !in.Empresa {
		problem.Write(c, problem.BadRequest("segmento desconhecido (LIMPEZA, VIGILANCIA, MANUTENCAO, PORTARIA, ADMINISTRATIVO)"))
		return
	}
	created := 0
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		list := append(append([]tpl{}, baseTpl...), extra...)
		pos := in.PositionID
		if in.Empresa {
			list, pos = companyTpl, nil
		} else if pos == nil {
			nome := in.NomeCargo
			if nome == "" {
				nome = cases.Title(language.Portuguese).String(strings.ToLower(seg))
			}
			var id string
			if err := tx.QueryRow(ctx, `INSERT INTO positions (tenant_id,nome,segmento) VALUES ($1,$2,$3) ON CONFLICT (tenant_id,nome) DO UPDATE SET segmento=EXCLUDED.segmento RETURNING id::text`, tid(c), nome, seg).Scan(&id); err != nil {
				return err
			}
			pos = &id
		}
		for _, t := range list {
			var v *int
			if t.Validade > 0 {
				x := t.Validade
				v = &x
			}
			if err := upsertReq(ctx, tx, tid(c), reqIn{PositionID: pos, DocumentType: t.Codigo, Momento: t.Momento, ValidadeDias: v}); err != nil {
				return err
			}
			created++
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "MODELO_OBRIGATORIEDADE_APLICADO", "requirement", seg, map[string]any{"itens": created})
	}) {
		c.JSON(200, gin.H{"itens": created})
	}
}

// GET /requirements/impact?position_id=&momento= — estimativa de pendências criadas.
func (s *Server) requirementImpact(c *gin.Context) {
	s.queryJSON(c, `SELECT json_build_object('funcionarios_afetados', n, 'pendencias_estimadas', CASE WHEN $2='MENSAL' THEN n*12 WHEN $2='DESLIGAMENTO' THEN (SELECT count(*) FROM employees WHERE desligamento IS NOT NULL) ELSE n END)
	  FROM (SELECT count(*) AS n FROM employees WHERE status<>'DESLIGADO' AND ($1::uuid IS NULL OR cargo_id=$1::uuid)) x`, nullIfEmpty(c.Query("position_id")), c.DefaultQuery("momento", "ADMISSAO"))
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// ---------- usuários RH ----------

func (s *Server) listUsers(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(u ORDER BY u.nome),'[]') FROM (SELECT id, nome, email, role, perms, unit_scope, status, ultimo_login, criado_em FROM users WHERE role<>'MASTER') u`)
}

func randHex(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}
func sha256hex(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

// POST /users — convite por e-mail corporativo (domínio permitido pela empresa).
func (s *Server) inviteUser(c *gin.Context) {
	var in struct {
		Nome      string   `json:"nome" binding:"required"`
		Email     string   `json:"email" binding:"required,email"`
		Role      string   `json:"role"`
		Perms     []string `json:"perms"`
		UnitScope []string `json:"unit_scope"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if in.Role == "" {
		in.Role = "RH"
	}
	if in.Role != "RH" && in.Role != "ADMIN_EMPRESA" {
		problem.Write(c, problem.BadRequest("perfil inválido"))
		return
	}
	if in.UnitScope == nil {
		in.UnitScope = []string{}
	}
	if in.Perms == nil {
		in.Perms = []string{}
	}
	token := randHex(32)
	var tenantNome string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var domains []string
		var max *int
		var n int
		if err := tx.QueryRow(ctx, `SELECT dominios_email, max_usuarios_rh, coalesce(nome_fantasia,razao_social) FROM tenants WHERE id=$1`, tid(c)).Scan(&domains, &max, &tenantNome); err != nil {
			return err
		}
		ok := false
		d := app.EmailDomain(in.Email)
		for _, x := range domains {
			if strings.TrimPrefix(strings.ToLower(x), "@") == d {
				ok = true
			}
		}
		if !ok {
			return problem.BadRequest("o e-mail deve ser de um domínio corporativo permitido pela empresa: " + strings.Join(domains, ", "))
		}
		tx.QueryRow(ctx, `SELECT count(*) FROM users WHERE role='RH' AND status<>'INATIVO'`).Scan(&n)
		if in.Role == "RH" && max != nil && n >= *max {
			return problem.New(403, "limite-plano", fmt.Sprintf("o plano permite até %d usuários RH", *max))
		}
		var uid string
		err := tx.QueryRow(ctx, `INSERT INTO users (tenant_id, email, nome, role, perms, unit_scope, status) VALUES ($1,lower($2),$3,$4,$5,$6::uuid[],'CONVIDADO') RETURNING id::text`,
			tid(c), in.Email, in.Nome, in.Role, in.Perms, in.UnitScope).Scan(&uid)
		if err != nil {
			if strings.Contains(err.Error(), "users_email_uq") {
				return problem.Conflict("já existe um usuário com este e-mail")
			}
			return err
		}
		tx.Exec(ctx, `INSERT INTO user_invites (user_id, token_hash, expira_em) VALUES ($1,$2,$3)`, uid, sha256hex(token), time.Now().Add(72*time.Hour))
		return s.audit(ctx, tx, c, "USUARIO_CONVIDADO", "user", uid, map[string]any{"role": in.Role, "perms": in.Perms})
	}) {
		return
	}
	link := fmt.Sprintf("%s/convite?token=%s", s.Cfg.AppURL, token)
	s.Mail.Send(in.Email, "Citadel IA · convite de acesso", fmt.Sprintf("Olá, %s.\n\nVocê foi convidado para acessar a Citadel IA da empresa %s.\nDefina sua senha (mínimo de 12 caracteres) pelo link, válido por 72 horas:\n\n%s\n", in.Nome, tenantNome, link))
	c.Status(http.StatusCreated)
}

// PATCH /users/:id (step-up: mudar permissões é ação sensível)
func (s *Server) patchUser(c *gin.Context) {
	var in struct {
		Perms     *[]string `json:"perms"`
		UnitScope *[]string `json:"unit_scope"`
		Status    *string   `json:"status"`
		Nome      *string   `json:"nome"`
	}
	if !bindJSON(c, &in) {
		return
	}
	id := c.Param("id")
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE users SET perms=coalesce($2,perms), unit_scope=coalesce($3::uuid[],unit_scope), status=coalesce($4,status), nome=coalesce($5,nome) WHERE id=$1 AND role<>'MASTER'`,
			id, in.Perms, in.UnitScope, in.Status, in.Nome)
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("usuário não encontrado")
		}
		if in.Status != nil && *in.Status == "INATIVO" {
			if err := s.Auth.RevokeAllForUser(ctx, tx, id); err != nil { // desativar revoga tudo
				return err
			}
			tx.Exec(ctx, `UPDATE user_invites SET usado_em=now() WHERE user_id=$1 AND usado_em IS NULL`, id) // e invalida convites pendentes
		}
		return s.audit(ctx, tx, c, "USUARIO_ALTERADO", "user", id, map[string]any{"perms": in.Perms, "status": in.Status})
	}) {
		c.Status(204)
	}
}

func (s *Server) revokeUserSessions(c *gin.Context) {
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := s.Auth.RevokeAllForUser(ctx, tx, c.Param("id")); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "SESSOES_ENCERRADAS", "user", c.Param("id"), nil)
	}) {
		c.Status(204)
	}
}

// ---------- empresa, retenção, plano ----------

func (s *Server) getTenant(c *gin.Context) {
	s.queryJSON(c, `SELECT row_to_json(t) FROM (SELECT t.id, t.cnpj, t.razao_social, t.nome_fantasia, t.endereco, t.porte, t.status, t.dominios_email, t.responsavel_financeiro,
	  t.quota_bytes, t.bytes_usados, t.quota_paginas_mes, t.max_usuarios_rh, t.max_funcionarios, t.limiar_confianca, t.pre_cadastro_automatico, t.politica_anonimizacao, p.nome AS plano,
	  coalesce((SELECT paginas FROM usage_monthly WHERE tenant_id=t.id AND mes=to_char(now(),'YYYY-MM')),0) AS paginas_mes
	  FROM tenants t LEFT JOIN plans p ON p.id=t.plano_id WHERE t.id=$1) t`, tid(c))
}

func (s *Server) patchTenant(c *gin.Context) {
	var in struct {
		NomeFantasia *string        `json:"nome_fantasia"`
		Endereco     map[string]any `json:"endereco"`
		Limiar       *float64       `json:"limiar_confianca"`
		Politica     map[string]any `json:"politica_anonimizacao"`
		Responsavel  map[string]any `json:"responsavel_financeiro"`
		PreCadastro  *bool          `json:"pre_cadastro_automatico"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if in.Limiar != nil && (*in.Limiar < 0.3 || *in.Limiar > 0.99) {
		problem.Write(c, problem.BadRequest("limiar de confiança deve ficar entre 0,30 e 0,99"))
		return
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `UPDATE tenants SET nome_fantasia=coalesce($2,nome_fantasia), endereco=coalesce($3::jsonb,endereco), limiar_confianca=coalesce($4,limiar_confianca),
		  politica_anonimizacao=coalesce($5::jsonb,politica_anonimizacao), responsavel_financeiro=coalesce($6::jsonb,responsavel_financeiro), pre_cadastro_automatico=coalesce($7,pre_cadastro_automatico) WHERE id=$1`,
			tid(c), in.NomeFantasia, mustJSONOrNil(in.Endereco), in.Limiar, mustJSONOrNil(in.Politica), mustJSONOrNil(in.Responsavel), in.PreCadastro)
		if err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "EMPRESA_ALTERADA", "tenant", tid(c), nil)
	}) {
		c.Status(204)
	}
}

func mustJSONOrNil(m map[string]any) any {
	if m == nil {
		return nil
	}
	return mustJSON(m)
}

// PUT /tenant/domains (step-up)
func (s *Server) putDomains(c *gin.Context) {
	var in struct {
		Dominios []string `json:"dominios_email" binding:"required,min=1"`
	}
	if !bindJSON(c, &in) {
		return
	}
	for i, d := range in.Dominios {
		in.Dominios[i] = strings.TrimPrefix(strings.ToLower(strings.TrimSpace(d)), "@")
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `UPDATE tenants SET dominios_email=$2 WHERE id=$1`, tid(c), in.Dominios); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "DOMINIOS_ALTERADOS", "tenant", tid(c), map[string]any{"dominios": in.Dominios})
	}) {
		c.Status(204)
	}
}

func (s *Server) listRetention(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.nome),'[]') FROM (SELECT dt.id AS document_type_id, dt.codigo, dt.nome, dt.retencao_padrao_dias AS padrao_dias,
	  coalesce(rp.dias, dt.retencao_padrao_dias) AS dias, coalesce(rp.acao,'EXCLUIR') AS acao, rp.dias IS NOT NULL AS personalizado
	  FROM document_types dt LEFT JOIN retention_policies rp ON rp.document_type_id=dt.id) t`)
}

func (s *Server) putRetention(c *gin.Context) {
	var in struct {
		Dias int    `json:"dias" binding:"required,min=30"`
		Acao string `json:"acao"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if in.Acao == "" {
		in.Acao = "EXCLUIR"
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `INSERT INTO retention_policies (tenant_id, document_type_id, dias, acao) VALUES ($1,$2,$3,$4)
		  ON CONFLICT (tenant_id, document_type_id) DO UPDATE SET dias=EXCLUDED.dias, acao=EXCLUDED.acao`, tid(c), c.Param("typeId"), in.Dias, in.Acao); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "RETENCAO_ALTERADA", "document_type", c.Param("typeId"), map[string]any{"dias": in.Dias, "acao": in.Acao})
	}) {
		c.Status(204)
	}
}

func (s *Server) billing(c *gin.Context) {
	s.queryJSON(c, `SELECT json_build_object(
	  'plano', (SELECT row_to_json(p) FROM (SELECT p.nome, p.porte, p.preco_mensal_centavos FROM plans p JOIN tenants t ON t.plano_id=p.id WHERE t.id=$1) p),
	  'uso', (SELECT coalesce(json_agg(u ORDER BY u.mes DESC),'[]') FROM (SELECT mes, paginas, docs, revisoes, bytes_total FROM usage_monthly ORDER BY mes DESC LIMIT 12) u),
	  'faturas', (SELECT coalesce(json_agg(f ORDER BY f.criado_em DESC),'[]') FROM (SELECT id, referencia, valor_centavos, status, vencimento, criado_em FROM invoices) f),
	  'limites', (SELECT row_to_json(l) FROM (SELECT quota_bytes, bytes_usados, quota_paginas_mes, max_usuarios_rh, max_funcionarios FROM tenants WHERE id=$1) l))`, tid(c))
}

// ---------- acesso de suporte (aprovação pelo admin da empresa) ----------

func (s *Server) listSupportAccess(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.criado_em DESC),'[]') FROM (SELECT sa.id, sa.motivo, sa.status, sa.expira_em, sa.criado_em, u.nome AS solicitante, u.email FROM support_access sa JOIN users u ON u.id=sa.solicitado_por) t`)
}

func (s *Server) decideSupportAccess(c *gin.Context) {
	acao := c.Param("acao") // approve | deny | revoke
	status := map[string]string{"approve": "APROVADO", "deny": "NEGADO", "revoke": "REVOGADO"}[acao]
	if status == "" {
		problem.Write(c, problem.NotFound("ação desconhecida"))
		return
	}
	var in struct {
		Horas int `json:"horas"`
	}
	c.ShouldBindJSON(&in)
	if in.Horas <= 0 || in.Horas > 72 {
		in.Horas = 8
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var exp any
		if status == "APROVADO" {
			exp = time.Now().Add(time.Duration(in.Horas) * time.Hour)
		}
		ct, err := tx.Exec(ctx, `UPDATE support_access SET status=$2, aprovado_por=$3, expira_em=coalesce($4::timestamptz, expira_em) WHERE id=$1`, c.Param("id"), status, auth.ClaimsOf(c).Subject, exp)
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("solicitação não encontrada")
		}
		return s.audit(ctx, tx, c, "ACESSO_SUPORTE_"+status, "support_access", c.Param("id"), map[string]any{"horas": in.Horas})
	}) {
		c.Status(204)
	}
}
