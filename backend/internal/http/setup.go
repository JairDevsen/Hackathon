package http

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// ---------- setores ----------

func (s *Server) listDepartments(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(d ORDER BY d.nome),'[]') FROM (SELECT id, nome, descricao, ativo, (SELECT count(*) FROM employees e WHERE e.department_id=departments.id) AS funcionarios FROM departments) d`)
}

func (s *Server) saveDepartment(c *gin.Context) {
	var in struct {
		Nome      string `json:"nome" binding:"required"`
		Descricao string `json:"descricao"`
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
			err = tx.QueryRow(ctx, `INSERT INTO departments (tenant_id,nome,descricao) VALUES ($1,$2,nullif($3,'')) RETURNING id::text`, tid(c), strings.TrimSpace(in.Nome), in.Descricao).Scan(&out)
		} else {
			out = id
			_, err = tx.Exec(ctx, `UPDATE departments SET nome=$2, descricao=nullif($3,''), ativo=coalesce($4,ativo) WHERE id=$1`, id, strings.TrimSpace(in.Nome), in.Descricao, in.Ativo)
		}
		if err != nil {
			if strings.Contains(err.Error(), "departments_tenant_id_nome_key") {
				return problem.Conflict("já existe um setor com este nome")
			}
			return err
		}
		return s.audit(ctx, tx, c, "SETOR_SALVO", "department", out, nil)
	}) {
		c.JSON(200, gin.H{"id": out})
	}
}

func (s *Server) deleteDepartment(c *gin.Context) {
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `DELETE FROM departments WHERE id=$1`, c.Param("id")); err != nil { // funcionários ficam sem setor; regras do setor somem
			return err
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "SETOR_REMOVIDO", "department", c.Param("id"), nil)
	}) {
		c.Status(204)
	}
}

// ---------- "selecionar documentos": obrigatoriedade em lote por escopo ----------

type bulkItem struct {
	Codigo       string `json:"codigo" binding:"required"`
	Momento      string `json:"momento" binding:"required"`
	ValidadeDias *int   `json:"validade_dias"`
	Antecedencia *int   `json:"antecedencia_alerta_dias"`
	Obrigatorio  *bool  `json:"obrigatorio"` // false = dispensa explícita (ex.: cargo que não precisa de um documento exigido de "todos")
}

var errDryRun = errors.New("dry-run")

// PUT /requirements/bulk — define, de uma vez, os documentos exigidos de um escopo (todos | setor | cargo).
// Com dry_run=true aplica numa transação que é desfeita e devolve o impacto (pendências antes/depois).
func (s *Server) bulkRequirements(c *gin.Context) {
	var in struct {
		PositionID   *string    `json:"position_id"`
		DepartmentID *string    `json:"department_id"`
		Items        []bulkItem `json:"items"`
		DryRun       bool       `json:"dry_run"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if in.PositionID != nil && in.DepartmentID != nil {
		problem.Write(c, problem.BadRequest("escolha um escopo: cargo OU setor"))
		return
	}
	var res gin.H
	err := s.DB.Tenant(c.Request.Context(), tid(c), func(tx pgx.Tx) error {
		ctx := c.Request.Context()
		var antes, depois int
		tx.QueryRow(ctx, `SELECT count(*) FROM compliance_items WHERE status IN ('PENDENTE','VENCIDO')`).Scan(&antes)
		want := map[string]bool{}
		for _, it := range in.Items {
			want[it.Codigo+"|"+it.Momento] = true
		}
		rows, err := tx.Query(ctx, `SELECT r.id::text, dt.codigo, r.momento FROM requirements r JOIN document_types dt ON dt.id=r.document_type_id
		  WHERE r.employee_id IS NULL AND r.position_id IS NOT DISTINCT FROM $1::uuid AND r.department_id IS NOT DISTINCT FROM $2::uuid`, in.PositionID, in.DepartmentID)
		if err != nil {
			return err
		}
		var del []string
		have := map[string]bool{}
		for rows.Next() {
			var id, cod, mom string
			rows.Scan(&id, &cod, &mom)
			have[cod+"|"+mom] = true
			if !want[cod+"|"+mom] {
				del = append(del, id)
			}
		}
		rows.Close()
		if len(del) > 0 {
			if _, err := tx.Exec(ctx, `DELETE FROM requirements WHERE id = ANY($1::uuid[])`, del); err != nil {
				return err
			}
		}
		added := 0
		for _, it := range in.Items {
			if !have[it.Codigo+"|"+it.Momento] {
				added++
			}
			if err := upsertReq(ctx, tx, tid(c), reqIn{PositionID: in.PositionID, DepartmentID: in.DepartmentID, DocumentType: it.Codigo, Momento: it.Momento, ValidadeDias: it.ValidadeDias, Antecedencia: it.Antecedencia, Obrigatorio: it.Obrigatorio}); err != nil {
				return err
			}
		}
		if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil {
			return err
		}
		tx.QueryRow(ctx, `SELECT count(*) FROM compliance_items WHERE status IN ('PENDENTE','VENCIDO')`).Scan(&depois)
		res = gin.H{"adicionados": added, "removidos": len(del), "pendencias_antes": antes, "pendencias_depois": depois, "simulacao": in.DryRun}
		if in.DryRun {
			return errDryRun // desfaz tudo: era só para mostrar o impacto
		}
		return s.audit(ctx, tx, c, "OBRIGATORIEDADE_EM_LOTE", "requirement", "", map[string]any{"adicionados": added, "removidos": len(del), "setor": in.DepartmentID, "cargo": in.PositionID})
	})
	if err != nil && !errors.Is(err, errDryRun) {
		problem.Write(c, problem.From(err))
		return
	}
	c.JSON(200, res)
}

// ---------- exceções por funcionário ----------

var defaultMomento = map[string]string{"ADMISSAO": "ADMISSAO", "MENSAL": "MENSAL", "SAUDE_SEGURANCA": "PERIODICO", "DESLIGAMENTO": "DESLIGAMENTO", "DISCIPLINAR": "EVENTO", "OUTROS": "ADMISSAO", "EMPRESA": "PERIODICO"}

// GET /employees/:id/requirements — o que é exigido deste funcionário e de onde vem a regra.
func (s *Server) employeeRequirements(c *gin.Context) {
	var ef []compliance.Efetivo
	var types []gin.H
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var err error
		if ef, err = compliance.Effective(ctx, tx, tid(c), c.Param("id")); err != nil {
			if err == pgx.ErrNoRows {
				return problem.NotFound("funcionário não encontrado")
			}
			return err
		}
		rows, err := tx.Query(ctx, `SELECT codigo, nome, categoria, validade_padrao_dias FROM document_types WHERE escopo='FUNCIONARIO' AND codigo<>'OUTRO' ORDER BY categoria, nome`)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var cod, nome, cat string
			var val *int
			rows.Scan(&cod, &nome, &cat, &val)
			types = append(types, gin.H{"codigo": cod, "nome": nome, "categoria": cat, "validade_padrao_dias": val})
		}
		return nil
	}) {
		return
	}
	by := map[string][]compliance.Efetivo{}
	for _, e := range ef {
		by[e.Codigo] = append(by[e.Codigo], e)
	}
	out := []gin.H{}
	for _, t := range types {
		row := gin.H{"codigo": t["codigo"], "nome": t["nome"], "categoria": t["categoria"], "obrigatorio": false, "origem": nil, "momento": nil, "excecao": false, "validade_padrao_dias": t["validade_padrao_dias"]}
		for _, e := range by[t["codigo"].(string)] {
			row["origem"], row["momento"], row["excecao"] = e.Origem, e.Momento, e.Excecao
			if e.Obrigatorio {
				row["obrigatorio"] = true
			}
		}
		out = append(out, row)
	}
	c.JSON(200, out)
}

// PUT /employees/:id/requirements/:codigo — exige ou dispensa um documento SÓ para este funcionário (obrigatorio=null volta ao padrão).
func (s *Server) setEmployeeRequirement(c *gin.Context) {
	var in struct {
		Obrigatorio   *bool  `json:"obrigatorio"`
		Momento       string `json:"momento"`
		ValidadeDias  *int   `json:"validade_dias"`
		Justificativa string `json:"justificativa"`
	}
	if !bindJSON(c, &in) {
		return
	}
	emp, cod := c.Param("id"), c.Param("codigo")
	if in.Obrigatorio != nil && !*in.Obrigatorio && len(strings.TrimSpace(in.Justificativa)) < 5 {
		problem.Write(c, problem.BadRequest("informe a justificativa da dispensa (mín. 5 caracteres): ela fica na auditoria"))
		return
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `DELETE FROM requirements WHERE employee_id=$1 AND document_type_id=(SELECT id FROM document_types WHERE codigo=$2)`, emp, cod); err != nil {
			return err
		}
		if in.Obrigatorio != nil {
			ef, err := compliance.Effective(ctx, tx, tid(c), emp) // já sem a exceção apagada acima
			if err != nil {
				return err
			}
			var momentos []string
			var val = in.ValidadeDias
			for _, e := range ef {
				if e.Codigo == cod {
					momentos = append(momentos, e.Momento)
					if val == nil {
						val = e.ValidadeDia
					}
				}
			}
			if *in.Obrigatorio || len(momentos) > 0 {
				if *in.Obrigatorio && len(momentos) == 0 {
					m := in.Momento
					if m == "" {
						var cat string
						tx.QueryRow(ctx, `SELECT categoria FROM document_types WHERE codigo=$1`, cod).Scan(&cat)
						m = defaultMomento[cat]
					}
					momentos = []string{m}
				}
				if *in.Obrigatorio && in.Momento != "" {
					momentos = []string{in.Momento}
				}
				for _, m := range momentos {
					e := emp
					if err := upsertReq(ctx, tx, tid(c), reqIn{EmployeeID: &e, DocumentType: cod, Momento: m, ValidadeDias: val, Obrigatorio: in.Obrigatorio, Observacao: in.Justificativa}); err != nil {
						return err
					}
				}
			}
		}
		if err := compliance.Recompute(ctx, tx, tid(c), emp); err != nil {
			return err
		}
		acao := "EXCECAO_REMOVIDA"
		if in.Obrigatorio != nil {
			acao = map[bool]string{true: "DOCUMENTO_EXIGIDO_FUNCIONARIO", false: "DOCUMENTO_DISPENSADO_FUNCIONARIO"}[*in.Obrigatorio]
		}
		return s.audit(ctx, tx, c, acao, "employee", emp, map[string]any{"documento": cod, "justificativa": in.Justificativa})
	}) {
		c.Status(204)
	}
}

// ---------- cadastro de funcionário configurável ----------

var chaveRe = regexp.MustCompile(`^[a-z][a-z0-9_]{1,29}$`)

type customField struct {
	Chave       string   `json:"chave"`
	Rotulo      string   `json:"rotulo"`
	Tipo        string   `json:"tipo"` // texto | data | numero | lista
	Obrigatorio bool     `json:"obrigatorio"`
	Opcoes      []string `json:"opcoes"`
}
type cadastroCfg struct {
	Campos         map[string]struct{ Ativo, Obrigatorio bool } `json:"campos"`
	Personalizados []customField                                `json:"personalizados"`
}

var camposPadrao = []string{"matricula", "admissao", "cargo", "setor", "unidade", "email", "telefone"}

func (s *Server) getCadastroConfig(c *gin.Context) {
	s.queryJSON(c, `SELECT config_cadastro FROM tenants WHERE id=$1`, tid(c))
}

func (s *Server) putCadastroConfig(c *gin.Context) {
	var in cadastroCfg
	if !bindJSON(c, &in) {
		return
	}
	for k := range in.Campos {
		ok := false
		for _, p := range camposPadrao {
			ok = ok || p == k
		}
		if !ok {
			problem.Write(c, problem.BadRequest("campo padrão desconhecido: "+k))
			return
		}
	}
	seen := map[string]bool{}
	for i, f := range in.Personalizados {
		if !chaveRe.MatchString(f.Chave) || seen[f.Chave] || strings.TrimSpace(f.Rotulo) == "" {
			problem.Write(c, problem.BadRequest(fmt.Sprintf("campo personalizado #%d inválido (chave minúscula sem espaços, única, e rótulo)", i+1)))
			return
		}
		seen[f.Chave] = true
		if f.Tipo != "texto" && f.Tipo != "data" && f.Tipo != "numero" && f.Tipo != "lista" {
			problem.Write(c, problem.BadRequest("tipo inválido em "+f.Chave))
			return
		}
		if f.Tipo == "lista" && len(f.Opcoes) == 0 {
			problem.Write(c, problem.BadRequest("informe as opções de "+f.Chave))
			return
		}
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `UPDATE tenants SET config_cadastro=$2 WHERE id=$1`, tid(c), mustJSON(in)); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "CADASTRO_CONFIGURADO", "tenant", tid(c), map[string]any{"personalizados": len(in.Personalizados)})
	}) {
		c.Status(http.StatusNoContent)
	}
}

// validateCadastro aplica as regras da empresa (campos ativos/obrigatórios e personalizados). Nome e CPF são sempre obrigatórios.
func (s *Server) validateCadastro(ctx context.Context, tx pgx.Tx, tenantID string, vals map[string]string, extra map[string]any) error {
	var raw []byte
	if err := tx.QueryRow(ctx, `SELECT config_cadastro FROM tenants WHERE id=$1`, tenantID).Scan(&raw); err != nil {
		return err
	}
	var cfg cadastroCfg
	unmarshal(raw, &cfg)
	var miss []string
	rot := map[string]string{"matricula": "Matrícula", "admissao": "Data de admissão", "cargo_id": "Cargo", "department_id": "Setor", "unit_id": "Unidade", "email": "E-mail", "telefone": "Telefone"}
	key := map[string]string{"matricula": "matricula", "admissao": "admissao", "cargo_id": "cargo", "department_id": "setor", "unit_id": "unidade", "email": "email", "telefone": "telefone"}
	for field, label := range rot {
		if f, ok := cfg.Campos[key[field]]; ok && f.Ativo && f.Obrigatorio && strings.TrimSpace(vals[field]) == "" {
			miss = append(miss, label)
		}
	}
	for _, f := range cfg.Personalizados {
		v, has := extra[f.Chave]
		sv := strings.TrimSpace(fmt.Sprint(v))
		if !has || sv == "" || sv == "<nil>" {
			if f.Obrigatorio {
				miss = append(miss, f.Rotulo)
			}
			continue
		}
		switch f.Tipo {
		case "data":
			if _, err := time.Parse("2006-01-02", sv); err != nil {
				return problem.BadRequest(f.Rotulo + ": data inválida (use AAAA-MM-DD)")
			}
		case "lista":
			ok := false
			for _, o := range f.Opcoes {
				ok = ok || o == sv
			}
			if !ok {
				return problem.BadRequest(f.Rotulo + ": valor fora das opções")
			}
		}
	}
	if len(miss) > 0 {
		p := problem.New(422, "campos-obrigatorios", "preencha os campos exigidos pela empresa: "+strings.Join(miss, ", "))
		p.Errors = map[string]any{"campos": miss}
		return p
	}
	return nil
}
