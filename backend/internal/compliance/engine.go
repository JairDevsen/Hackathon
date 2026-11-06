// Package compliance: motor de conformidade documental. Gera os compliance_items esperados por
// funcionário (cargo × matriz de obrigatoriedade) e calcula OK / PENDENTE / VENCIDO / A_VENCER.
package compliance

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
)

type req struct {
	ID, DocType, Momento, Escopo string
	PositionID                   *string
	DepartmentID, EmployeeID     *string
	Validade                     *int
	Antecedencia                 int
	Obrigatorio                  bool
}

// Origem do requisito e precedência: funcionário (3) > cargo (2) > setor (1) > todos (0).
func (r req) rank() int {
	switch {
	case r.EmployeeID != nil:
		return 3
	case r.PositionID != nil:
		return 2
	case r.DepartmentID != nil:
		return 1
	}
	return 0
}

func (r req) Origin() string { return [...]string{"TODOS", "SETOR", "CARGO", "FUNCIONARIO"}[r.rank()] }

func (r req) general() bool { return r.rank() == 0 }

type doc struct {
	ID, Competencia string
	DataDoc         *time.Time
	ValidadeAte     *time.Time
	Criado          time.Time
}

type item struct {
	ReqID, Ref, Status string
	Vence              *time.Time
	DocID              *string
}

func today() time.Time {
	n := time.Now()
	return time.Date(n.Year(), n.Month(), n.Day(), 0, 0, 0, 0, time.Local)
}

func evaluate(d *doc, validade *int, antecedencia int, now time.Time) (string, *time.Time, *string) {
	if d == nil {
		return "PENDENTE", nil, nil
	}
	id := d.ID
	if validade == nil && d.ValidadeAte == nil {
		return "OK", nil, &id
	}
	var exp time.Time
	if d.ValidadeAte != nil {
		exp = *d.ValidadeAte
	} else {
		base := d.Criado
		if d.DataDoc != nil {
			base = *d.DataDoc
		}
		exp = base.AddDate(0, 0, *validade)
	}
	switch {
	case exp.Before(now):
		return "VENCIDO", &exp, &id
	case exp.Sub(now) <= time.Duration(antecedencia)*24*time.Hour:
		return "A_VENCER", &exp, &id
	}
	return "OK", &exp, &id
}

func monthsBetween(from, to time.Time) []string {
	var out []string
	cur := time.Date(from.Year(), from.Month(), 1, 0, 0, 0, 0, time.Local)
	end := time.Date(to.Year(), to.Month(), 1, 0, 0, 0, 0, time.Local)
	for !cur.After(end) {
		out = append(out, cur.Format("2006-01"))
		cur = cur.AddDate(0, 1, 0)
	}
	return out
}

func latest(ds []*doc) *doc {
	var best *doc
	for _, d := range ds {
		if best == nil || d.Criado.After(best.Criado) {
			best = d
		}
	}
	return best
}

// pick resolve, para cada (tipo, momento), a regra mais específica que vale para o funcionário.
// Uma regra com obrigatorio=false no nível mais específico dispensa o documento (não gera pendência).
func pick(reqs []req, positionID, departmentID, employeeID *string) []req {
	return pickAll(reqs, positionID, departmentID, employeeID, false)
}

func eq(a, b *string) bool { return a != nil && b != nil && *a == *b }

func pickAll(reqs []req, positionID, departmentID, employeeID *string, includeOff bool) []req {
	chosen := map[string]req{}
	for _, r := range reqs {
		switch {
		case r.EmployeeID != nil && !eq(r.EmployeeID, employeeID):
			continue
		case r.PositionID != nil && !eq(r.PositionID, positionID):
			continue
		case r.DepartmentID != nil && !eq(r.DepartmentID, departmentID):
			continue
		}
		k := r.DocType + "|" + r.Momento
		if cur, ok := chosen[k]; ok && cur.rank() >= r.rank() {
			continue // a regra mais específica prevalece
		}
		chosen[k] = r
	}
	var out []req
	for _, r := range chosen {
		if r.Obrigatorio || includeOff {
			out = append(out, r)
		}
	}
	return out
}

func build(reqs []req, byType map[string][]*doc, adm, desl *time.Time, now time.Time) []item {
	var items []item
	for _, r := range reqs {
		ds := byType[r.DocType]
		switch r.Momento {
		case "ADMISSAO", "EVENTO":
			if r.Momento == "EVENTO" {
				continue // gerado por gatilho de evento (checklist), não pelo ciclo diário
			}
			st, v, id := evaluate(latest(ds), r.Validade, r.Antecedencia, now)
			items = append(items, item{r.ID, "ADMISSAO", st, v, id})
		case "DESLIGAMENTO":
			if desl == nil {
				continue
			}
			st, v, id := evaluate(latest(ds), r.Validade, r.Antecedencia, now)
			items = append(items, item{r.ID, "DESLIGAMENTO", st, v, id})
		case "PERIODICO", "ANUAL":
			val := r.Validade
			if val == nil && r.Momento == "ANUAL" {
				d := 365
				val = &d
			}
			st, v, id := evaluate(latest(ds), val, r.Antecedencia, now)
			items = append(items, item{r.ID, r.Momento, st, v, id})
		case "MENSAL":
			from := now.AddDate(0, -35, 0)
			if adm != nil {
				if adm.After(from) {
					from = *adm
				}
			} else {
				// sem data de admissão (ex.: pré-cadastro): começa na 1ª competência que tem documento. Nunca inventar 35 meses de pendência.
				first := ""
				for _, d := range ds {
					if d.Competencia != "" && (first == "" || d.Competencia < first) {
						first = d.Competencia
					}
				}
				if first == "" {
					continue
				}
				t, err := time.ParseInLocation("2006-01", first, time.Local)
				if err != nil {
					continue
				}
				from = t
			}
			to := now.AddDate(0, -1, 0) // só competências já encerradas
			if desl != nil && desl.Before(to) {
				to = *desl
			}
			for _, comp := range monthsBetween(from, to) {
				var match []*doc
				for _, d := range ds {
					if d.Competencia == comp {
						match = append(match, d)
					}
				}
				st, v, id := evaluate(latest(match), r.Validade, r.Antecedencia, now)
				items = append(items, item{r.ID, comp, st, v, id})
			}
		}
	}
	return items
}

func loadReqs(ctx context.Context, tx pgx.Tx, tenantID string) ([]req, error) {
	rows, err := tx.Query(ctx, `SELECT r.id::text, t.codigo, r.momento, t.escopo, r.position_id::text, r.department_id::text, r.employee_id::text, coalesce(r.validade_dias, t.validade_padrao_dias),
	  r.antecedencia_alerta_dias, r.obrigatorio FROM requirements r JOIN document_types t ON t.id=r.document_type_id WHERE r.tenant_id=$1`, tenantID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []req
	for rows.Next() {
		var r req
		if err := rows.Scan(&r.ID, &r.DocType, &r.Momento, &r.Escopo, &r.PositionID, &r.DepartmentID, &r.EmployeeID, &r.Validade, &r.Antecedencia, &r.Obrigatorio); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func loadDocs(ctx context.Context, tx pgx.Tx, tenantID, employeeID string, company bool) (map[string]map[string][]*doc, error) {
	q := `SELECT coalesce(employee_id::text,''), document_type, id::text, coalesce(competencia,''), data_documento, validade_ate, criado_em
	  FROM documents WHERE tenant_id=$1 AND status IN ('AUTO_APROVADO','REVISADO') AND origem='IA'
	    AND NOT (motivos_revisao ?| array['PAGINA_ILEGIVEL','IMAGEM_BORRADA','TIPO_OUTRO'])`
	args := []any{tenantID}
	switch {
	case company:
		q += ` AND employee_id IS NULL`
	case employeeID != "":
		q += ` AND employee_id=$2`
		args = append(args, employeeID)
	default:
		q += ` AND employee_id IS NOT NULL`
	}
	rows, err := tx.Query(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]map[string][]*doc{}
	for rows.Next() {
		var emp, typ string
		d := &doc{}
		if err := rows.Scan(&emp, &typ, &d.ID, &d.Competencia, &d.DataDoc, &d.ValidadeAte, &d.Criado); err != nil {
			return nil, err
		}
		if out[emp] == nil {
			out[emp] = map[string][]*doc{}
		}
		out[emp][typ] = append(out[emp][typ], d)
	}
	return out, rows.Err()
}

func upsert(ctx context.Context, tx pgx.Tx, tenantID string, employeeID *string, items []item) error {
	var reqIDs, refs, sts []string
	var vences []*time.Time
	var docs []*string
	keep := []string{}
	for _, it := range items {
		reqIDs, refs, sts, vences, docs = append(reqIDs, it.ReqID), append(refs, it.Ref), append(sts, it.Status), append(vences, it.Vence), append(docs, it.DocID)
		keep = append(keep, it.ReqID+"|"+it.Ref)
	}
	if len(items) > 0 {
		_, err := tx.Exec(ctx, `INSERT INTO compliance_items (tenant_id, employee_id, requirement_id, referencia, status, vence_em, document_id)
		  SELECT $1, $2::uuid, r::uuid, f, s, v, d::uuid FROM unnest($3::text[], $4::text[], $5::text[], $6::date[], $7::text[]) AS x(r,f,s,v,d)
		  ON CONFLICT (tenant_id, coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid), requirement_id, referencia)
		  DO UPDATE SET status=EXCLUDED.status, vence_em=EXCLUDED.vence_em, document_id=EXCLUDED.document_id, atualizado_em=now()
		  WHERE compliance_items.status <> 'DISPENSADO'`, tenantID, employeeID, reqIDs, refs, sts, vences, docs)
		if err != nil {
			return fmt.Errorf("upsert compliance: %w", err)
		}
	}
	// remove itens que deixaram de ser esperados (cargo mudou, regra removida), preservando dispensas
	_, err := tx.Exec(ctx, `DELETE FROM compliance_items WHERE tenant_id=$1 AND employee_id IS NOT DISTINCT FROM $2::uuid
	  AND status <> 'DISPENSADO' AND (requirement_id::text || '|' || referencia) <> ALL($3::text[])`, tenantID, employeeID, keep)
	return err
}

// Recompute recalcula a conformidade de um funcionário (employeeID) ou de toda a empresa ("").
func Recompute(ctx context.Context, tx pgx.Tx, tenantID, employeeID string) error {
	reqs, err := loadReqs(ctx, tx, tenantID)
	if err != nil {
		return err
	}
	now := today()
	q := `SELECT id::text, cargo_id::text, department_id::text, admissao, desligamento FROM employees WHERE tenant_id=$1 AND status<>'DESLIGADO' OR (tenant_id=$1 AND desligamento IS NOT NULL AND desligamento > now() - interval '24 months')`
	args := []any{tenantID}
	if employeeID != "" {
		q = `SELECT id::text, cargo_id::text, department_id::text, admissao, desligamento FROM employees WHERE tenant_id=$1 AND id=$2`
		args = append(args, employeeID)
	}
	docs, err := loadDocs(ctx, tx, tenantID, employeeID, false)
	if err != nil {
		return err
	}
	type emp struct {
		ID      string
		Cargo   *string
		Dept    *string
		Adm, De *time.Time
	}
	rows, err := tx.Query(ctx, q, args...)
	if err != nil {
		return err
	}
	var emps []emp
	for rows.Next() {
		var e emp
		if err := rows.Scan(&e.ID, &e.Cargo, &e.Dept, &e.Adm, &e.De); err != nil {
			rows.Close()
			return err
		}
		emps = append(emps, e)
	}
	rows.Close()
	var employeeReqs []req
	var companyReqs []req
	for _, r := range reqs {
		if r.Escopo == "EMPRESA" {
			companyReqs = append(companyReqs, r)
		} else {
			employeeReqs = append(employeeReqs, r)
		}
	}
	for _, e := range emps {
		eid := e.ID
		items := build(pick(employeeReqs, e.Cargo, e.Dept, &eid), docs[eid], e.Adm, e.De, now)
		if err := upsert(ctx, tx, tenantID, &eid, items); err != nil {
			return err
		}
	}
	if employeeID == "" || len(companyReqs) > 0 && employeeID == "" {
		cdocs, err := loadDocs(ctx, tx, tenantID, "", true)
		if err != nil {
			return err
		}
		// empresa: mensal = últimos 6 meses encerrados; demais = item único
		var cr []req
		for _, r := range companyReqs {
			if r.general() && r.Obrigatorio {
				cr = append(cr, r)
			}
		}
		from := now.AddDate(0, -6, 0)
		items := build(cr, cdocs[""], &from, nil, now)
		if err := upsert(ctx, tx, tenantID, nil, items); err != nil {
			return err
		}
	}
	return RecomputeRisks(ctx, tx, tenantID, employeeID)
}

// DailyAlerts cria notificações de vencimento (uma por dia) para a empresa.
func DailyAlerts(ctx context.Context, tx pgx.Tx, tenantID string) error {
	var n int
	if err := tx.QueryRow(ctx, `SELECT count(*) FROM compliance_items WHERE tenant_id=$1 AND status='A_VENCER'`, tenantID).Scan(&n); err != nil {
		return err
	}
	if n == 0 {
		return nil
	}
	titulo := fmt.Sprintf("%d documento(s) a vencer — %s", n, time.Now().Format("02/01"))
	_, err := tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) SELECT $1,'A_VENCER',$2,'/pendencias?status=A_VENCER'
	  WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE tenant_id=$1 AND tipo='A_VENCER' AND titulo=$2)`, tenantID, titulo)
	return err
}

// Efetivo descreve, para um funcionário, se cada tipo documental é exigido e de onde vem a regra.
type Efetivo struct {
	Codigo      string `json:"codigo"`
	Obrigatorio bool   `json:"obrigatorio"`
	Origem      string `json:"origem"` // TODOS | SETOR | CARGO | FUNCIONARIO
	Momento     string `json:"momento"`
	ValidadeDia *int   `json:"validade_dias"`
	Excecao     bool   `json:"excecao"` // regra própria do funcionário (dispensa ou exigência)
}

// Effective calcula as regras vigentes do funcionário (inclui as dispensadas, com obrigatorio=false).
func Effective(ctx context.Context, tx pgx.Tx, tenantID, employeeID string) ([]Efetivo, error) {
	reqs, err := loadReqs(ctx, tx, tenantID)
	if err != nil {
		return nil, err
	}
	var cargo, dept *string
	if err := tx.QueryRow(ctx, `SELECT cargo_id::text, department_id::text FROM employees WHERE id=$1`, employeeID).Scan(&cargo, &dept); err != nil {
		return nil, err
	}
	var out []Efetivo
	for _, r := range pickAll(reqs, cargo, dept, &employeeID, true) {
		if r.Escopo != "FUNCIONARIO" {
			continue
		}
		out = append(out, Efetivo{r.DocType, r.Obrigatorio, r.Origin(), r.Momento, r.Validade, r.EmployeeID != nil})
	}
	return out, nil
}
