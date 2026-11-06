package http

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cnpj"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// Fornecedores e terceirizadas: agrupam funcionários, documentos, conformidade e riscos pelo CNPJ.

const supplierSelect = `SELECT s.id, s.cnpj, s.razao_social, s.nome_fantasia, s.tipo, s.status, s.pre_cadastro, s.origem, s.criticidade, s.objeto,
  s.contrato_inicio, s.contrato_fim, s.responsavel_nome, s.responsavel_email, s.criado_em,
  (SELECT count(*) FROM employees e WHERE e.supplier_id=s.id AND e.status<>'DESLIGADO') AS funcionarios,
  (SELECT count(*) FROM documents d WHERE d.supplier_id=s.id AND d.status NOT IN ('REJEITADO','SUBSTITUIDO')) AS documentos,
  coalesce(c.ok,0) AS ok, coalesce(c.total,0) AS total, coalesce(c.pend,0) AS pendencias,
  coalesce(rk.alto,0) AS riscos_altos, coalesce(rk.total,0) AS riscos, coalesce(c.venc,0) AS vencidos,
  -- exposição da CONTRATANTE a processo trabalhista por este fornecedor (responsabilidade subsidiária, TST Súmula 331):
  -- ALTA = indicador de risco alto ou documento exigido vencido; MEDIA = indicador ou exigência pendente; BAIXA = tudo em dia
  CASE WHEN coalesce(rk.alto,0)>0 OR coalesce(c.venc,0)>0 THEN 'ALTA' WHEN coalesce(rk.total,0)>0 OR coalesce(c.pend,0)>0 THEN 'MEDIA' ELSE 'BAIXA' END AS exposicao
  FROM suppliers s
  LEFT JOIN LATERAL (SELECT count(*) FILTER (WHERE ci.status='OK') ok, count(*) FILTER (WHERE ci.status<>'DISPENSADO') total,
      count(*) FILTER (WHERE ci.status IN ('PENDENTE','VENCIDO')) pend, count(*) FILTER (WHERE ci.status='VENCIDO') venc FROM compliance_items ci
      WHERE ci.supplier_id=s.id OR ci.employee_id IN (SELECT id FROM employees WHERE supplier_id=s.id)) c ON true
  LEFT JOIN LATERAL (SELECT count(*) FILTER (WHERE severidade='ALTO') alto, count(*) total FROM risk_indicators WHERE supplier_id=s.id AND status='ABERTO') rk ON true`

func (s *Server) listSuppliers(c *gin.Context) {
	args := []any{}
	where := []string{"true"}
	add := func(cond, v string) {
		if v != "" {
			args = append(args, v)
			where = append(where, strings.ReplaceAll(cond, "?", fmt.Sprintf("$%d", len(args))))
		}
	}
	add("s.tipo = ?", c.Query("tipo"))
	add("s.status = ?", c.Query("status"))
	if c.Query("pre") == "1" {
		where = append(where, "s.pre_cadastro = true")
	}
	if q := strings.TrimSpace(c.Query("q")); q != "" {
		if d := cnpj.Clean(q); len(d) >= 4 && len(d) == len(strings.Map(func(r rune) rune {
			if r >= '0' && r <= '9' || r == '.' || r == '/' || r == '-' || r == ' ' {
				return r
			}
			return -1
		}, q)) { // parece CNPJ (ou parte dele)
			args = append(args, d)
			where = append(where, fmt.Sprintf("s.cnpj LIKE '%%'||$%d||'%%'", len(args)))
		} else {
			args = append(args, q)
			where = append(where, fmt.Sprintf("(f_unaccent(lower(s.razao_social)) LIKE '%%'||f_unaccent(lower($%d))||'%%' OR f_unaccent(lower(coalesce(s.nome_fantasia,''))) LIKE '%%'||f_unaccent(lower($%d))||'%%')", len(args), len(args)))
		}
	}
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.razao_social),'[]') FROM (`+supplierSelect+` WHERE `+strings.Join(where, " AND ")+` LIMIT 500) t`, args...)
}

func (s *Server) getSupplier(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce((SELECT row_to_json(t) FROM (`+supplierSelect+` WHERE s.id=$1) t),'null'::json)`, c.Param("id"))
}

type supplierIn struct {
	CNPJ        string  `json:"cnpj"`
	Razao       *string `json:"razao_social"`
	Fantasia    *string `json:"nome_fantasia"`
	Tipo        *string `json:"tipo"`
	Status      *string `json:"status"`
	Criticidade *string `json:"criticidade"`
	Objeto      *string `json:"objeto"`
	Inicio      *string `json:"contrato_inicio"`
	Fim         *string `json:"contrato_fim"`
	RespNome    *string `json:"responsavel_nome"`
	RespEmail   *string `json:"responsavel_email"`
	PreCadastro *bool   `json:"pre_cadastro"`
}

func (in *supplierIn) validate() error {
	oneOf := func(v *string, ok ...string) bool {
		if v == nil {
			return true
		}
		for _, o := range ok {
			if *v == o {
				return true
			}
		}
		return false
	}
	switch {
	case !oneOf(in.Tipo, "TERCEIRIZADA", "FORNECEDOR"):
		return problem.BadRequest("tipo deve ser TERCEIRIZADA ou FORNECEDOR")
	case !oneOf(in.Status, "ATIVO", "INATIVO"):
		return problem.BadRequest("status deve ser ATIVO ou INATIVO")
	case !oneOf(in.Criticidade, "BAIXA", "MEDIA", "ALTA"):
		return problem.BadRequest("criticidade deve ser BAIXA, MEDIA ou ALTA")
	}
	for _, d := range []*string{in.Inicio, in.Fim} {
		if d != nil && *d != "" {
			if _, err := time.Parse("2006-01-02", *d); err != nil {
				return problem.BadRequest("datas do contrato devem estar em AAAA-MM-DD")
			}
		}
	}
	if in.Inicio != nil && in.Fim != nil && *in.Inicio != "" && *in.Fim != "" && *in.Fim < *in.Inicio {
		return problem.BadRequest("o fim do contrato não pode ser anterior ao início")
	}
	if in.Razao != nil && len(strings.TrimSpace(*in.Razao)) < 2 {
		return problem.BadRequest("informe a razão social")
	}
	return nil
}

func (s *Server) createSupplier(c *gin.Context) {
	var in supplierIn
	if !bindJSON(c, &in) {
		return
	}
	digits := cnpj.Clean(in.CNPJ)
	if !cnpj.Valid(digits) {
		problem.Write(c, problem.BadRequest("CNPJ inválido (confira os dígitos)"))
		return
	}
	if in.Razao == nil || strings.TrimSpace(*in.Razao) == "" {
		problem.Write(c, problem.BadRequest("informe a razão social"))
		return
	}
	if err := in.validate(); err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	var id string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var own bool
		if err := tx.QueryRow(ctx, `SELECT regexp_replace(cnpj,'[^0-9]','','g')=$2 FROM tenants WHERE id=$1`, tid(c), digits).Scan(&own); err != nil {
			return err
		}
		if own {
			return problem.BadRequest("este é o CNPJ da própria empresa, não de um fornecedor")
		}
		err := tx.QueryRow(ctx, `INSERT INTO suppliers (tenant_id, cnpj, razao_social, nome_fantasia, tipo, criticidade, objeto, contrato_inicio, contrato_fim, responsavel_nome, responsavel_email)
		  VALUES ($1,$2,$3,nullif($4,''),coalesce($5,'TERCEIRIZADA'),coalesce($6,'MEDIA'),nullif($7,''),nullif($8,'')::date,nullif($9,'')::date,nullif($10,''),nullif($11,'')) RETURNING id::text`,
			tid(c), digits, strings.ToUpper(strings.TrimSpace(*in.Razao)), deref(in.Fantasia), in.Tipo, in.Criticidade, deref(in.Objeto), deref(in.Inicio), deref(in.Fim), deref(in.RespNome), deref(in.RespEmail)).Scan(&id)
		if err != nil {
			if strings.Contains(err.Error(), "suppliers_tenant_id_cnpj_key") {
				return problem.Conflict("já existe um fornecedor com este CNPJ")
			}
			return err
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil { // as exigências da empresa passam a valer para ele
			return err
		}
		return s.audit(ctx, tx, c, "FORNECEDOR_CRIADO", "supplier", id, map[string]any{"cnpj": digits})
	}) {
		return
	}
	c.JSON(201, gin.H{"id": id})
}

func (s *Server) patchSupplier(c *gin.Context) {
	var in supplierIn
	if !bindJSON(c, &in) {
		return
	}
	if err := in.validate(); err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	id := c.Param("id")
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE suppliers SET
		    razao_social=coalesce(nullif(upper(trim($2)),''),razao_social), nome_fantasia=coalesce($3,nome_fantasia), tipo=coalesce($4,tipo),
		    status=coalesce($5,status), criticidade=coalesce($6,criticidade), objeto=coalesce($7,objeto),
		    contrato_inicio=CASE WHEN $8::text IS NULL THEN contrato_inicio ELSE nullif($8,'')::date END,
		    contrato_fim=CASE WHEN $9::text IS NULL THEN contrato_fim ELSE nullif($9,'')::date END,
		    responsavel_nome=coalesce($10,responsavel_nome), responsavel_email=coalesce($11,responsavel_email),
		    pre_cadastro=coalesce($12,pre_cadastro), atualizado_em=now() WHERE id=$1`,
			id, deref(in.Razao), in.Fantasia, in.Tipo, in.Status, in.Criticidade, in.Objeto, in.Inicio, in.Fim, in.RespNome, in.RespEmail, in.PreCadastro)
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("fornecedor não encontrado")
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil { // tipo, status e datas do contrato mudam o que é cobrado
			return err
		}
		return s.audit(ctx, tx, c, "FORNECEDOR_ALTERADO", "supplier", id, map[string]any{"status": in.Status, "tipo": in.Tipo})
	}) {
		c.Status(204)
	}
}

// documentos da EMPRESA do fornecedor (certidões, guias, contrato, apólice, autuações, processos, auditorias)
func (s *Server) supplierDocuments(c *gin.Context) {
	_, saude := s.userScope(c)
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.criado_em DESC),'[]') FROM (`+docRowSQL("$2")+`
	  WHERE d.supplier_id=$1 AND d.employee_id IS NULL AND d.status NOT IN ('REJEITADO')) t`, c.Param("id"), saude)
}

func (s *Server) supplierCompliance(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.categoria, t.tipo_nome, t.referencia DESC),'[]') FROM (
	  SELECT ci.id, ci.referencia, ci.status, ci.vence_em, ci.document_id, ci.justificativa_dispensa, dt.codigo AS tipo, dt.nome AS tipo_nome, dt.categoria, r.momento
	  FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id WHERE ci.supplier_id=$1) t`, c.Param("id"))
}
