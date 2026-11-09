package http

import (
	"context"
	"strings"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/cnpj"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cpf"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"

	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
)

// searchDirectory é o localizador único do topo da tela: uma busca devolve, ao mesmo tempo, funcionários (nome, matrícula ou
// CPF), setores e empresas (terceirizadas e fornecedores, por nome ou CNPJ). O escopo de unidades do usuário vale para as pessoas.
func (s *Server) searchDirectory(c *gin.Context) {
	q := strings.TrimSpace(c.Query("q"))
	if len([]rune(q)) < 2 {
		c.JSON(200, gin.H{"funcionarios": []any{}, "setores": []any{}, "empresas": []any{}})
		return
	}
	units, _ := s.userScope(c)

	// pessoas: CPF completo usa o índice cego; senão nome (sem acento) ou matrícula
	empWhere, empArgs := `($1::uuid[] = '{}' OR e.unit_id = ANY($1)) AND `, []any{units}
	if cpf.Looks(q) {
		if !cpf.Valid(q) {
			empWhere += `false`
		} else {
			empArgs = append(empArgs, s.KR.Blind(tid(c), cpf.Clean(q)))
			empWhere += `e.cpf_hash = $2`
		}
	} else {
		empArgs = append(empArgs, q)
		empWhere += `(e.matricula = $2 OR f_unaccent(lower(e.nome)) LIKE '%'||f_unaccent(lower($2))||'%' OR similarity(f_unaccent(lower(e.nome)), f_unaccent(lower($2))) > 0.35)`
	}
	// empresas: parte de um CNPJ (só dígitos e pontuação) ou nome
	ent := `f_unaccent(lower(s.razao_social)) LIKE '%'||f_unaccent(lower($1))||'%' OR f_unaccent(lower(coalesce(s.nome_fantasia,''))) LIKE '%'||f_unaccent(lower($1))||'%'`
	var entArg any = q
	if d := cnpj.Clean(q); len(d) >= 4 && strings.Trim(q, "0123456789./- ") == "" {
		ent, entArg = `s.cnpj LIKE '%'||$1||'%'`, d
	}
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var emp, dep, ents []byte
		var e error
		if emp, e = database.JSON(ctx, tx, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT e.id, e.nome, e.cpf_mascarado, e.status, dp.nome AS setor,
			CASE WHEN e.supplier_id IS NULL THEN 'PROPRIA' ELSE su.tipo END AS vinculo, coalesce(su.nome_fantasia, su.razao_social) AS empresa
			FROM employees e LEFT JOIN departments dp ON dp.id=e.department_id LEFT JOIN suppliers su ON su.id=e.supplier_id
			WHERE `+empWhere+` ORDER BY (e.status='DESLIGADO'), e.nome LIMIT 6) t`, empArgs...); e != nil {
			return e
		}
		if dep, e = database.JSON(ctx, tx, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT d.id, d.nome, (SELECT count(*) FROM employees x WHERE x.department_id=d.id AND x.status<>'DESLIGADO') AS funcionarios
			FROM departments d WHERE d.ativo AND f_unaccent(lower(d.nome)) LIKE '%'||f_unaccent(lower($1))||'%' ORDER BY d.nome LIMIT 5) t`, q); e != nil {
			return e
		}
		if ents, e = database.JSON(ctx, tx, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT s.id, s.cnpj, coalesce(s.nome_fantasia, s.razao_social) AS nome, s.tipo, s.status,
			(SELECT count(*) FROM employees x WHERE x.supplier_id=s.id AND x.status<>'DESLIGADO') AS funcionarios
			FROM suppliers s WHERE `+ent+` ORDER BY s.razao_social LIMIT 10) t`, entArg); e != nil {
			return e
		}
		raw = []byte(`{"funcionarios":` + string(emp) + `,"setores":` + string(dep) + `,"empresas":` + string(ents) + `}`)
		return nil
	}) {
		return
	}
	c.Data(200, "application/json", raw)
}
