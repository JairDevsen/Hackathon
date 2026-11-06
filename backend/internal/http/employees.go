package http

import (
	"context"
	"encoding/base64"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/internal/documents"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cpf"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/xuri/excelize/v2"
)

const employeeSelect = `SELECT e.id, e.nome, e.cpf_mascarado, e.matricula, e.status, e.pre_cadastro, e.origem, e.admissao, e.desligamento, e.email, e.telefone,
  p.nome AS cargo, e.cargo_id, dp.nome AS setor, e.department_id, e.extra, u.nome AS unidade, e.unit_id, e.supplier_id, su.razao_social AS fornecedor, su.cnpj AS fornecedor_cnpj, CASE WHEN e.supplier_id IS NULL THEN 'PROPRIA' ELSE su.tipo END AS vinculo,
  coalesce(c.ok,0) AS ok, coalesce(c.total,0) AS total, coalesce(c.pend,0) AS pendencias, coalesce(rk.alto,0) AS riscos_altos, coalesce(rk.total,0) AS riscos, e.criado_em
  FROM employees e LEFT JOIN positions p ON p.id=e.cargo_id LEFT JOIN departments dp ON dp.id=e.department_id LEFT JOIN units u ON u.id=e.unit_id LEFT JOIN suppliers su ON su.id=e.supplier_id
  LEFT JOIN LATERAL (SELECT count(*) FILTER (WHERE status='OK') ok, count(*) FILTER (WHERE status<>'DISPENSADO') total,
     count(*) FILTER (WHERE status IN ('PENDENTE','VENCIDO')) pend FROM compliance_items WHERE employee_id=e.id) c ON true
  LEFT JOIN LATERAL (SELECT count(*) FILTER (WHERE severidade='ALTO') alto, count(*) total FROM risk_indicators WHERE employee_id=e.id AND status='ABERTO') rk ON true`

// pageOf corta limit+1 itens e monta o cursor (nome|id) para a próxima página.
func pageOf(raw []byte, limit int, cursorFields ...string) gin.H {
	var items []map[string]any
	json.Unmarshal(raw, &items)
	var next any
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		parts := make([]string, len(cursorFields))
		for i, f := range cursorFields {
			parts[i] = fmt.Sprint(last[f])
		}
		next = base64.RawURLEncoding.EncodeToString([]byte(strings.Join(parts, "|")))
	}
	if items == nil {
		items = []map[string]any{}
	}
	return gin.H{"items": items, "next_cursor": next}
}

func decodeCursor(c string) []string {
	if c == "" {
		return nil
	}
	b, err := base64.RawURLEncoding.DecodeString(c)
	if err != nil {
		return nil
	}
	return strings.SplitN(string(b), "|", 2)
}

func limitOf(c *gin.Context, def, max int) int {
	var n int
	fmt.Sscan(c.Query("limit"), &n)
	if n <= 0 {
		n = def
	}
	if n > max {
		n = max
	}
	return n
}

// GET /employees?q=  — reconhece CPF (com/sem máscara), matrícula ou nome.
func (s *Server) listEmployees(c *gin.Context) {
	q := strings.TrimSpace(c.Query("q"))
	limit := limitOf(c, 30, 100)
	units, _ := s.userScope(c)
	where := []string{`($1::uuid[] = '{}' OR e.unit_id = ANY($1))`}
	args := []any{units}
	add := func(cond string, v any) {
		args = append(args, v)
		where = append(where, strings.ReplaceAll(cond, "?", fmt.Sprintf("$%d", len(args))))
	}
	kind := "lista"
	if q != "" {
		switch {
		case cpf.Looks(q):
			kind = "cpf"
			if !cpf.Valid(q) {
				c.JSON(200, gin.H{"items": []any{}, "tipo_busca": "cpf", "cpf_valido": false, "next_cursor": nil})
				return
			}
			add("e.cpf_hash = ?", s.KR.Blind(tid(c), cpf.Clean(q)))
		default:
			kind = "nome"
			args = append(args, q)
			i := len(args)
			where = append(where, fmt.Sprintf(`(e.matricula = $%d OR f_unaccent(lower(e.nome)) LIKE '%%'||f_unaccent(lower($%d))||'%%' OR similarity(f_unaccent(lower(e.nome)), f_unaccent(lower($%d))) > 0.35)`, i, i, i))
			if strings.Trim(q, "0123456789") == "" {
				kind = "matricula"
			}
		}
	}
	if v := c.Query("unit"); v != "" {
		add("e.unit_id = ?::uuid", v)
	}
	if v := c.Query("cargo"); v != "" {
		add("e.cargo_id = ?::uuid", v)
	}
	if c.Query("pre") == "1" {
		where = append(where, "e.pre_cadastro = true")
	}
	switch v := c.Query("vinculo"); v { // própria empresa × terceirizadas × fornecedores
	case "PROPRIA":
		where = append(where, "e.supplier_id IS NULL")
	case "TERCEIRIZADA", "FORNECEDOR":
		add("su.tipo = ?", v)
	}
	if v := c.Query("supplier"); v == "none" { // só funcionários da própria empresa
		where = append(where, "e.supplier_id IS NULL")
	} else if v != "" {
		add("e.supplier_id = ?::uuid", v)
	}
	if v := c.Query("setor"); v != "" {
		add("e.department_id = ?::uuid", v)
	}
	if v := c.Query("status"); v != "" {
		add("e.status = ?", v)
	}
	if c.Query("pre") == "1" {
		where = append(where, "e.pre_cadastro")
	}
	switch c.Query("conformidade") {
	case "pendente":
		where = append(where, "coalesce(c.pend,0) > 0")
	case "ok":
		where = append(where, "coalesce(c.pend,0) = 0")
	}
	if cur := decodeCursor(c.Query("cursor")); len(cur) == 2 {
		args = append(args, cur[0], cur[1])
		where = append(where, fmt.Sprintf("(e.nome, e.id::text) > ($%d, $%d)", len(args)-1, len(args)))
	}
	sql := fmt.Sprintf(`SELECT coalesce(json_agg(t),'[]') FROM (%s WHERE %s ORDER BY e.nome, e.id LIMIT %d) t`, employeeSelect, strings.Join(where, " AND "), limit+1)
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var e error
		raw, e = database.JSON(ctx, tx, sql, args...)
		return e
	}) {
		return
	}
	out := pageOf(raw, limit, "nome", "id")
	out["tipo_busca"] = kind
	c.JSON(200, out)
}

type empIn struct {
	Nome         string         `json:"nome" binding:"required,min=2"`
	CPF          string         `json:"cpf" binding:"required"`
	Matricula    string         `json:"matricula"`
	CargoID      *string        `json:"cargo_id"`
	DepartmentID *string        `json:"department_id"`
	UnitID       *string        `json:"unit_id"`
	Admissao     *string        `json:"admissao"`
	Email        string         `json:"email"`
	Telefone     string         `json:"telefone"`
	Extra        map[string]any `json:"extra"`
	SupplierID   *string        `json:"supplier_id"`
}

func str0(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func (s *Server) createEmployee(c *gin.Context) {
	var in empIn
	if !bindJSON(c, &in) {
		return
	}
	if !cpf.Valid(in.CPF) {
		problem.Write(c, problem.BadRequest("CPF inválido (confira os dígitos)"))
		return
	}
	var id string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := s.checkEmployeeLimit(ctx, tx, tid(c)); err != nil {
			return err
		}
		// regras de cadastro da empresa (campos obrigatórios/personalizados)
		if err := s.validateCadastro(ctx, tx, tid(c), map[string]string{"matricula": in.Matricula, "admissao": str0(in.Admissao), "cargo_id": str0(in.CargoID),
			"department_id": str0(in.DepartmentID), "unit_id": str0(in.UnitID), "email": in.Email, "telefone": in.Telefone}, in.Extra); err != nil {
			return err
		}
		var e error
		id, e = s.Ingest.CreateEmployee(ctx, tx, tid(c), documents.NewEmployee{Nome: in.Nome, CPF: in.CPF, Matricula: in.Matricula, CargoID: in.CargoID, UnitID: in.UnitID, Admissao: in.Admissao, SupplierID: nilIfEmpty(in.SupplierID)})
		if e != nil {
			return e
		}
		tx.Exec(ctx, `UPDATE employees SET email=nullif($2,''), telefone=nullif($3,''), department_id=$4::uuid, extra=coalesce($5::jsonb,'{}') WHERE id=$1`, id, in.Email, in.Telefone, in.DepartmentID, mustJSONOrNil(in.Extra))
		if e = compliance.Recompute(ctx, tx, tid(c), id); e != nil {
			return e
		}
		return s.audit(ctx, tx, c, "FUNCIONARIO_CRIADO", "employee", id, map[string]any{"cpf": cpf.Mask(in.CPF)})
	}) {
		return
	}
	c.JSON(http.StatusCreated, gin.H{"id": id})
}

func (s *Server) checkEmployeeLimit(ctx context.Context, tx pgx.Tx, tenantID string) error {
	var max *int
	var n int
	tx.QueryRow(ctx, `SELECT max_funcionarios FROM tenants WHERE id=$1`, tenantID).Scan(&max)
	tx.QueryRow(ctx, `SELECT count(*) FROM employees WHERE tenant_id=$1 AND status<>'DESLIGADO'`, tenantID).Scan(&n)
	if max != nil && n >= *max {
		return problem.New(403, "limite-plano", fmt.Sprintf("o plano permite até %d funcionários ativos", *max))
	}
	return nil
}

func (s *Server) getEmployee(c *gin.Context) {
	units, _ := s.userScope(c)
	s.queryJSON(c, `SELECT coalesce((SELECT row_to_json(t) FROM (`+employeeSelect+` WHERE e.id=$1 AND ($2::uuid[]='{}' OR e.unit_id=ANY($2))) t), 'null'::json)`, c.Param("id"), units)
}

func (s *Server) patchEmployee(c *gin.Context) {
	var in struct {
		Nome         *string        `json:"nome"`
		Matricula    *string        `json:"matricula"`
		CargoID      *string        `json:"cargo_id"`
		DepartmentID *string        `json:"department_id"`
		Extra        map[string]any `json:"extra"`
		UnitID       *string        `json:"unit_id"`
		Admissao     *string        `json:"admissao"`
		Desligamento *string        `json:"desligamento"`
		Status       *string        `json:"status"`
		Email        *string        `json:"email"`
		Telefone     *string        `json:"telefone"`
		PreCadastro  *bool          `json:"pre_cadastro"`
		SupplierID   *string        `json:"supplier_id"` // "" = volta a ser da própria empresa
	}
	if !bindJSON(c, &in) {
		return
	}
	id := c.Param("id")
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE employees SET nome=coalesce($2,nome), matricula=coalesce($3,matricula), cargo_id=coalesce($4::uuid,cargo_id), unit_id=coalesce($5::uuid,unit_id),
		  admissao=coalesce($6::date,admissao), desligamento=coalesce($7::date,desligamento), status=coalesce($8,status), email=coalesce($9,email), telefone=coalesce($10,telefone),
		  department_id=coalesce($11::uuid,department_id), extra=extra || coalesce($12::jsonb,'{}'), pre_cadastro=coalesce($13,pre_cadastro), supplier_id=CASE WHEN $14::text IS NULL THEN supplier_id ELSE nullif($14,'')::uuid END WHERE id=$1`,
			id, in.Nome, in.Matricula, in.CargoID, in.UnitID, in.Admissao, in.Desligamento, in.Status, in.Email, in.Telefone, in.DepartmentID, mustJSONOrNil(in.Extra), in.PreCadastro, in.SupplierID)
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("funcionário não encontrado")
		}
		if err := compliance.Recompute(ctx, tx, tid(c), id); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "FUNCIONARIO_ALTERADO", "employee", id, nil)
	}) {
		return
	}
	c.Status(204)
}

// documentRow: cartão do documento. Dados de saúde saem mascarados para quem não tem saude:ler.
func docRowSQL(saudeParam string) string {
	return `SELECT d.id, d.document_type, dt.nome AS tipo_nome, dt.categoria,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN 'Documento de saúde (acesso restrito)' ELSE d.titulo END AS titulo,
	  d.competencia, d.data_documento, d.validade_ate, d.status, d.confianca, d.paginas, d.employee_id, d.batch_id,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN '[]'::jsonb ELSE d.alertas END AS alertas,
	  d.motivos_revisao, d.nao_conformidades, d.sensivel_saude, (d.sensivel_saude AND NOT ` + saudeParam + `) AS mascarado, d.possui_manuscrito, d.versao, d.duplicata_de, d.criado_em, d.origem, d.supplier_id, sup.razao_social AS fornecedor, sup.cnpj AS fornecedor_cnpj, CASE WHEN d.supplier_id IS NULL THEN 'PROPRIA' ELSE sup.tipo END AS vinculo,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN NULL ELSE ef.nome END AS funcionario_nome,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN NULL ELSE ef.cpf_mascarado END AS funcionario_cpf,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN NULL ELSE d.campos->>'empresa_nome' END AS empresa_nome,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN NULL ELSE d.pasta_destino END AS pasta_destino,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN NULL ELSE d.nome_arquivo END AS nome_arquivo,
	  CASE WHEN d.sensivel_saude AND NOT ` + saudeParam + ` THEN '[]'::jsonb ELSE d.checklist END AS checklist
	  FROM documents d JOIN document_types dt ON dt.codigo=d.document_type LEFT JOIN employees ef ON ef.id=d.employee_id LEFT JOIN suppliers sup ON sup.id=d.supplier_id`
}

func (s *Server) employeeDocuments(c *gin.Context) {
	_, saude := s.userScope(c)
	args := []any{c.Param("id"), saude}
	where := "d.employee_id=$1 AND d.status NOT IN ('REJEITADO')"
	if v := c.Query("categoria"); v != "" {
		args = append(args, v)
		where += fmt.Sprintf(" AND dt.categoria=$%d", len(args))
	}
	if v := c.Query("competencia"); v != "" {
		args = append(args, v)
		where += fmt.Sprintf(" AND d.competencia=$%d", len(args))
	}
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.criado_em DESC),'[]') FROM (`+docRowSQL("$2")+` WHERE `+where+`) t`, args...)
}

func (s *Server) employeeCompliance(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.categoria, t.tipo_nome, t.referencia DESC),'[]') FROM (
	  SELECT ci.id, ci.referencia, ci.status, ci.vence_em, ci.document_id, ci.justificativa_dispensa, dt.codigo AS tipo, dt.nome AS tipo_nome, dt.categoria, r.momento
	  FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id WHERE ci.employee_id=$1) t`, c.Param("id"))
}

func (s *Server) employeeTimeline(c *gin.Context) {
	_, saude := s.userScope(c)
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.quando DESC),'[]') FROM (
	  SELECT d.criado_em AS quando, 'DOCUMENTO' AS tipo, (CASE WHEN d.sensivel_saude AND NOT $2 THEN 'Documento de saúde' ELSE dt.nome END) AS titulo, d.status AS detalhe, d.id::text AS ref
	    FROM documents d JOIN document_types dt ON dt.codigo=d.document_type WHERE d.employee_id=$1
	  UNION ALL
	  SELECT r.criado_em, 'REVISAO', r.acao, coalesce(u.nome,''), r.document_id::text FROM reviews r LEFT JOIN users u ON u.id=r.revisor_id
	    JOIN documents d ON d.id=r.document_id WHERE d.employee_id=$1) t`, c.Param("id"), saude)
}

func (s *Server) employeeReviews(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.criado_em DESC),'[]') FROM (
	  SELECT r.id, r.acao, r.criado_em, r.duracao_ms, u.nome AS revisor, d.document_type, r.document_id FROM reviews r
	  JOIN documents d ON d.id=r.document_id LEFT JOIN users u ON u.id=r.revisor_id WHERE d.employee_id=$1) t`, c.Param("id"))
}

// ---------- importação CSV/XLSX ----------

type importRow struct {
	Linha int    `json:"linha"`
	Erro  string `json:"erro,omitempty"`
}

func readSheet(c *gin.Context) ([][]string, error) {
	fh, err := c.FormFile("file")
	if err != nil {
		return nil, problem.BadRequest("envie a planilha no campo 'file'")
	}
	f, err := fh.Open()
	if err != nil {
		return nil, err
	}
	defer f.Close()
	if strings.HasSuffix(strings.ToLower(fh.Filename), ".xlsx") {
		x, err := excelize.OpenReader(f)
		if err != nil {
			return nil, problem.BadRequest("XLSX inválido")
		}
		return x.GetRows(x.GetSheetName(0))
	}
	r := csv.NewReader(f)
	r.FieldsPerRecord = -1
	r.LazyQuotes = true
	b, _ := io.ReadAll(f)
	_ = b
	f.Seek(0, 0)
	head := make([]byte, 4096)
	n, _ := f.Read(head)
	f.Seek(0, 0)
	if strings.Count(string(head[:n]), ";") > strings.Count(string(head[:n]), ",") {
		r.Comma = ';'
	}
	return r.ReadAll()
}

func (s *Server) importEmployees(c *gin.Context) {
	rows, err := readSheet(c)
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	if len(rows) < 2 {
		problem.Write(c, problem.BadRequest("a planilha precisa de cabeçalho e ao menos uma linha"))
		return
	}
	mapping := map[string]string{} // campo → nome da coluna na planilha
	if m := c.PostForm("mapping"); m != "" {
		json.Unmarshal([]byte(m), &mapping)
	}
	dry := c.PostForm("dry_run") == "true"
	norm := func(x string) string { return strings.ToLower(strings.TrimSpace(x)) }
	idx := map[string]int{}
	for i, h := range rows[0] {
		idx[norm(h)] = i
	}
	col := func(field string, aliases ...string) int {
		if n, ok := mapping[field]; ok {
			if i, ok := idx[norm(n)]; ok {
				return i
			}
		}
		for _, a := range append([]string{field}, aliases...) {
			if i, ok := idx[a]; ok {
				return i
			}
		}
		return -1
	}
	cSetor := col("setor", "departamento", "área")
	cCPF, cNome, cMat, cCargo, cUn, cAdm, cMail, cTel := col("cpf"), col("nome", "nome completo", "colaborador"), col("matricula", "matrícula"), col("cargo", "função"), col("unidade", "filial"), col("admissao", "admissão", "data de admissão"), col("email", "e-mail"), col("telefone", "celular")
	if cCPF < 0 || cNome < 0 {
		problem.Write(c, problem.BadRequest("colunas obrigatórias ausentes: cpf e nome (use o mapeamento de colunas)"))
		return
	}
	get := func(r []string, i int) string {
		if i < 0 || i >= len(r) {
			return ""
		}
		return strings.TrimSpace(r[i])
	}
	var errs []importRow
	created, valid := 0, 0
	err = s.DB.Tenant(c.Request.Context(), tid(c), func(tx pgx.Tx) error {
		ctx := c.Request.Context()
		for i, r := range rows[1:] {
			ln := i + 2
			nome, doc := get(r, cNome), get(r, cCPF)
			if nome == "" && doc == "" {
				continue
			}
			if !cpf.Valid(doc) {
				errs = append(errs, importRow{ln, "CPF inválido: " + doc})
				continue
			}
			if nome == "" {
				errs = append(errs, importRow{ln, "nome ausente"})
				continue
			}
			adm := get(r, cAdm)
			var admP *string
			if adm != "" {
				ok := false
				for _, l := range []string{"2006-01-02", "02/01/2006", "2/1/2006"} {
					if t, e := time.Parse(l, adm); e == nil {
						d := t.Format("2006-01-02")
						admP, ok = &d, true
						break
					}
				}
				if !ok {
					errs = append(errs, importRow{ln, "data de admissão inválida: " + adm})
					continue
				}
			}
			valid++
			if dry {
				continue
			}
			sp := fmt.Sprintf("sp%d", i)
			tx.Exec(ctx, "SAVEPOINT "+sp)
			var cargoID, unitID, deptID *string
			if st := get(r, cSetor); st != "" {
				var id string
				tx.QueryRow(ctx, `INSERT INTO departments (tenant_id, nome) VALUES ($1,$2) ON CONFLICT (tenant_id, nome) DO UPDATE SET nome=EXCLUDED.nome RETURNING id::text`, tid(c), st).Scan(&id)
				deptID = &id
			}
			if cg := get(r, cCargo); cg != "" {
				var id string
				tx.QueryRow(ctx, `INSERT INTO positions (tenant_id, nome) VALUES ($1,$2) ON CONFLICT (tenant_id, nome) DO UPDATE SET nome=EXCLUDED.nome RETURNING id::text`, tid(c), cg).Scan(&id)
				cargoID = &id
			}
			if un := get(r, cUn); un != "" {
				var id string
				if tx.QueryRow(ctx, `SELECT id::text FROM units WHERE lower(nome)=lower($1)`, un).Scan(&id) == pgx.ErrNoRows {
					tx.QueryRow(ctx, `INSERT INTO units (tenant_id, nome) VALUES ($1,$2) RETURNING id::text`, tid(c), un).Scan(&id)
				}
				unitID = &id
			}
			id, e := s.Ingest.CreateEmployee(ctx, tx, tid(c), documents.NewEmployee{Nome: nome, CPF: doc, Matricula: get(r, cMat), CargoID: cargoID, UnitID: unitID, Admissao: admP})
			if e != nil {
				tx.Exec(ctx, "ROLLBACK TO SAVEPOINT "+sp)
				errs = append(errs, importRow{ln, e.Error()})
				continue
			}
			tx.Exec(ctx, `UPDATE employees SET email=nullif($2,''), telefone=nullif($3,''), department_id=$4::uuid WHERE id=$1`, id, get(r, cMail), get(r, cTel), deptID)
			created++
		}
		if !dry && created > 0 {
			if e := compliance.Recompute(ctx, tx, tid(c), ""); e != nil {
				return e
			}
			return s.audit(ctx, tx, c, "FUNCIONARIOS_IMPORTADOS", "employee", "", map[string]any{"criados": created, "erros": len(errs)})
		}
		return nil
	})
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	if errs == nil {
		errs = []importRow{}
	}
	c.JSON(200, gin.H{"total": len(rows) - 1, "validos": valid, "criados": created, "erros": errs, "simulacao": dry})
}

type jsonRaw []byte

func (j jsonRaw) MarshalJSON() ([]byte, error) { return j, nil }

func base64RawURL(s string) string { return base64.RawURLEncoding.EncodeToString([]byte(s)) }

func unmarshal(b []byte, v any) { _ = json.Unmarshal(b, v) }

func nilIfEmpty(p *string) *string {
	if p == nil || strings.TrimSpace(*p) == "" {
		return nil
	}
	return p
}
