package documents

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/cpf"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/jackc/pgx/v5"
)

type NewEmployee struct {
	Nome, CPF, Matricula string
	CargoID, UnitID      *string
	Admissao             *string
	Origem               string // PRE_CADASTRO | REVISAO | MANUAL | IMPORTACAO (padrão MANUAL)
	Pre                  bool   // cadastro incompleto: o RH precisa completar
}

type ReviewInput struct {
	Acao          string         `json:"acao"` // CONFIRMAR CORRIGIR MUDAR_TIPO VINCULAR DIVIDIR JUNTAR REJEITAR SUBSTITUIR_ANTERIOR
	Tipo          string         `json:"tipo"`
	Campos        map[string]any `json:"campos"`
	EmployeeID    *string        `json:"employee_id"`
	Motivo        string         `json:"motivo"`
	PaginaDivisao int            `json:"pagina_divisao"`
	DuracaoMs     int            `json:"duracao_ms"`
	Forcado       bool           `json:"forcado"` // "aprovar mesmo assim": confirmou apesar de alertas de erro (fica na auditoria)
	Competencia   *string        `json:"competencia"`
	DataDocumento *string        `json:"data_documento"`
	ValidadeAte   *string        `json:"validade_ate"`
	NovoFunc      *struct {
		Nome      string  `json:"nome"`
		CPF       string  `json:"cpf"`
		Matricula string  `json:"matricula"`
		CargoID   *string `json:"cargo_id"`
		UnitID    *string `json:"unit_id"`
		Admissao  *string `json:"admissao"`
	} `json:"novo_funcionario"`
}

type snap struct {
	Tipo, Status, Competencia string
	EmployeeID                *string
	Paginas                   []int32
	Campos                    json.RawMessage
	Motivos                   []string
}

func (i *Ingestor) snapshot(ctx context.Context, tx pgx.Tx, id string) (*snap, string, error) {
	var s snap
	var mot json.RawMessage
	var batch *string
	var comp *string
	err := tx.QueryRow(ctx, `SELECT document_type, status, competencia, employee_id::text, paginas, campos, motivos_revisao, batch_id::text FROM documents WHERE id=$1`, id).
		Scan(&s.Tipo, &s.Status, &comp, &s.EmployeeID, &s.Paginas, &s.Campos, &mot, &batch)
	if err == pgx.ErrNoRows {
		return nil, "", problem.NotFound("documento não encontrado")
	}
	if comp != nil {
		s.Competencia = *comp
	}
	json.Unmarshal(mot, &s.Motivos)
	b := ""
	if batch != nil {
		b = *batch
	}
	return &s, b, err
}

func (i *Ingestor) rebuildText(ctx context.Context, tx pgx.Tx, batchID string, pages []int32) (string, error) {
	rows, err := tx.Query(ctx, `SELECT numero, coalesce(analise->>'texto_ocr','') FROM pages WHERE batch_id=$1 AND numero = ANY($2) ORDER BY numero`, batchID, pages)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	var parts []string
	for rows.Next() {
		var n int
		var t string
		rows.Scan(&n, &t)
		parts = append(parts, t)
	}
	return strings.Join(parts, "\n\n"), nil
}

// Apply executa uma ação de revisão. Devolve os funcionários afetados (para recalcular conformidade).
func (i *Ingestor) Apply(ctx context.Context, tx pgx.Tx, tenantID, userID, docID string, in ReviewInput) ([]string, error) {
	before, batchID, err := i.snapshot(ctx, tx, docID)
	if err != nil {
		return nil, err
	}
	affected := map[string]bool{}
	if before.EmployeeID != nil {
		affected[*before.EmployeeID] = true
	}
	var types map[string]typeInfo
	types, err = loadTypes(ctx, tx)
	if err != nil {
		return nil, err
	}
	tipo := before.Tipo
	if in.Tipo != "" && in.Tipo != tipo {
		if _, ok := types[in.Tipo]; !ok {
			return nil, problem.BadRequest("tipo documental desconhecido")
		}
		tipo = in.Tipo
		if _, err := tx.Exec(ctx, `UPDATE documents SET document_type=$2, sensivel_saude=$3 WHERE id=$1`, docID, tipo, types[tipo].Saude); err != nil {
			return nil, err
		}
		if tipo != "OUTRO" {
			if _, err := tx.Exec(ctx, `UPDATE documents SET motivos_revisao=coalesce((SELECT jsonb_agg(x) FROM jsonb_array_elements_text(motivos_revisao) x WHERE x <> 'TIPO_OUTRO'),'[]'::jsonb) WHERE id=$1`, docID); err != nil {
				return nil, err
			}
		}
	}
	// aplica correções de campos / datas / vínculo
	if in.Campos != nil {
		var cur map[string]any
		json.Unmarshal(before.Campos, &cur)
		if cur == nil {
			cur = map[string]any{}
		}
		for k, v := range in.Campos {
			if k == "cpf" { // nunca persistimos CPF em claro nos campos
				if d := cpf.Clean(fmt.Sprint(v)); len(d) == 11 {
					cur[k] = cpf.Mask(d)
				}
				continue
			}
			cur[k] = v
		}
		b, _ := json.Marshal(cur)
		if _, err := tx.Exec(ctx, `UPDATE documents SET campos=$2 WHERE id=$1`, docID, b); err != nil {
			return nil, err
		}
		if comp := str(in.Campos, "competencia"); comp != "" {
			if parsed, err := time.Parse("2006-01", comp); err != nil || parsed.Format("2006-01") != comp {
				return nil, problem.BadRequest("competência deve estar em AAAA-MM")
			}
			if _, err := tx.Exec(ctx, `UPDATE documents SET competencia=$2 WHERE id=$1`, docID, comp); err != nil {
				return nil, err
			}
		}
		for field, column := range map[string]string{"data_documento": "data_documento", "validade_ate": "validade_ate"} {
			if value := str(in.Campos, field); value != "" {
				parsed := dateOrNil(value)
				if parsed == nil {
					return nil, problem.BadRequest(field + " deve ser uma data válida")
				}
				if _, err := tx.Exec(ctx, `UPDATE documents SET `+column+`=$2::date WHERE id=$1`, docID, *parsed); err != nil {
					return nil, err
				}
			}
		}
	}
	if in.Acao == "TRANSCRICAO_MANUAL" {
		eligible := false
		for _, reason := range before.Motivos {
			if reason == "PAGINA_ILEGIVEL" || reason == "IMAGEM_BORRADA" || reason == "TIPO_OUTRO" {
				eligible = true
			}
		}
		if !eligible {
			return nil, problem.BadRequest("transcrição manual disponível apenas para documento ilegível ou sem tipo identificado")
		}
		if tipo == "OUTRO" || str(in.Campos, "nome") == "" && types[tipo].Escopo == "FUNCIONARIO" {
			return nil, problem.BadRequest("classifique o tipo e informe o nome do titular no formulário")
		}
		filled := false
		for k := range in.Campos {
			if str(in.Campos, k) != "" {
				filled = true
				break
			}
		}
		if !filled {
			return nil, problem.BadRequest("preencha os campos do documento")
		}
	}
	if in.Competencia != nil {
		tx.Exec(ctx, `UPDATE documents SET competencia=nullif($2,'') WHERE id=$1`, docID, *in.Competencia)
	}
	if in.DataDocumento != nil {
		tx.Exec(ctx, `UPDATE documents SET data_documento=nullif($2,'')::date WHERE id=$1`, docID, *in.DataDocumento)
	}
	if in.ValidadeAte != nil {
		tx.Exec(ctx, `UPDATE documents SET validade_ate=nullif($2,'')::date WHERE id=$1`, docID, *in.ValidadeAte)
	}
	// o revisor preencheu CPF e nome no formulário manual: liga ao funcionário existente ou cria o pré-cadastro
	if in.EmployeeID == nil && in.NovoFunc == nil && before.EmployeeID == nil && in.Campos != nil && types[tipo].Escopo == "FUNCIONARIO" &&
		(in.Acao == "CONFIRMAR" || in.Acao == "CORRIGIR" || in.Acao == "VINCULAR" || in.Acao == "TRANSCRICAO_MANUAL") {
		raw := cpf.Clean(fmt.Sprint(in.Campos["cpf"]))
		if cpf.Valid(raw) {
			found, _, err := i.FindEmployee(ctx, tx, tenantID, raw, "", "")
			if err != nil {
				return nil, err
			}
			if found == nil {
				nome := strings.TrimSpace(fmt.Sprint(in.Campos["nome"]))
				var auto bool
				tx.QueryRow(ctx, `SELECT pre_cadastro_automatico FROM tenants WHERE id=$1`, tenantID).Scan(&auto)
				if nome != "" && nome != "<nil>" && auto {
					if blocked, _ := i.limitReached(ctx, tx, tenantID); !blocked {
						var unit *string
						tx.QueryRow(ctx, `SELECT unit_id::text FROM documents WHERE id=$1`, docID).Scan(&unit)
						newID, err := i.CreateEmployee(ctx, tx, tenantID, NewEmployee{Nome: nome, CPF: raw, UnitID: unit, Origem: "REVISAO", Pre: true})
						if err != nil {
							return nil, err
						}
						found = &newID
					}
				}
			}
			in.EmployeeID = found
		}
	}
	if in.NovoFunc != nil {
		d := cpf.Clean(in.NovoFunc.CPF)
		if !cpf.Valid(d) {
			return nil, problem.BadRequest("CPF do novo funcionário inválido")
		}
		id, err := i.CreateEmployee(ctx, tx, tenantID, NewEmployee{Nome: in.NovoFunc.Nome, CPF: d, Matricula: in.NovoFunc.Matricula, CargoID: in.NovoFunc.CargoID, UnitID: in.NovoFunc.UnitID, Admissao: in.NovoFunc.Admissao, Origem: "REVISAO", Pre: true})
		if err != nil {
			return nil, err
		}
		in.EmployeeID = &id
	}
	if in.EmployeeID != nil {
		var owns bool
		if err := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM employees WHERE tenant_id=$1 AND id=$2)`, tenantID, *in.EmployeeID).Scan(&owns); err != nil || !owns {
			return nil, problem.BadRequest("funcionário não pertence à empresa")
		}
		if raw := cpf.Clean(str(in.Campos, "cpf")); cpf.Valid(raw) {
			var stored string
			if err := tx.QueryRow(ctx, `SELECT cpf_hash FROM employees WHERE tenant_id=$1 AND id=$2`, tenantID, *in.EmployeeID).Scan(&stored); err != nil {
				return nil, err
			}
			if stored != i.KR.Blind(tenantID, raw) {
				return nil, problem.BadRequest("CPF informado diverge do funcionário selecionado")
			}
		}
		if _, err := tx.Exec(ctx, `UPDATE documents SET employee_id=$2 WHERE id=$1`, docID, *in.EmployeeID); err != nil {
			return nil, problem.BadRequest("funcionário inválido")
		}
		affected[*in.EmployeeID] = true
		tx.Exec(ctx, `UPDATE documents SET motivos_revisao = coalesce((SELECT jsonb_agg(x) FROM jsonb_array_elements_text(motivos_revisao) x WHERE x NOT IN ('SEM_VINCULO','VINCULO_POR_NOME')),'[]'::jsonb) WHERE id=$1`, docID)
	}
	if types[tipo].Escopo == "EMPRESA" && before.EmployeeID != nil {
		if _, err := tx.Exec(ctx, `UPDATE documents SET employee_id=NULL WHERE id=$1`, docID); err != nil {
			return nil, err
		}
	}
	if in.Campos != nil && (in.Acao == "CORRIGIR" || in.Acao == "TRANSCRICAO_MANUAL") {
		if err := i.reconcileReviewAlerts(ctx, tx, tenantID, docID, in.Campos); err != nil {
			return nil, err
		}
	}
	setStatus := func(st string) error {
		_, err := tx.Exec(ctx, `UPDATE documents SET status=$2, atualizado_em=now() WHERE id=$1`, docID, st)
		return err
	}
	needEmployee := func() error {
		var emp *string
		tx.QueryRow(ctx, `SELECT employee_id::text FROM documents WHERE id=$1`, docID).Scan(&emp)
		if emp == nil && types[tipo].Escopo == "FUNCIONARIO" {
			return problem.New(422, "vinculo-obrigatorio", "vincule o documento a um funcionário antes de confirmar")
		}
		return nil
	}
	switch in.Acao {
	case "CONFIRMAR", "CORRIGIR", "TRANSCRICAO_MANUAL":
		if err := needEmployee(); err != nil {
			return nil, err
		}
		if in.Acao == "TRANSCRICAO_MANUAL" {
			if _, err := tx.Exec(ctx, `UPDATE documents SET origem='MANUAL', motivos_revisao=coalesce(motivos_revisao,'[]'::jsonb) || '["TRANSCRICAO_MANUAL"]'::jsonb WHERE id=$1`, docID); err != nil {
				return nil, err
			}
		}
		if err := setStatus("REVISADO"); err != nil {
			return nil, err
		}
		if in.Acao != "TRANSCRICAO_MANUAL" {
			var old *string
			if err := tx.QueryRow(ctx, `SELECT substitui_id::text FROM documents WHERE id=$1`, docID).Scan(&old); err != nil {
				return nil, err
			}
			if old != nil {
				var illegible bool
				if err := tx.QueryRow(ctx, `SELECT motivos_revisao ?| array['PAGINA_ILEGIVEL','IMAGEM_BORRADA'] FROM documents WHERE id=$1`, docID).Scan(&illegible); err != nil {
					return nil, err
				}
				if illegible {
					return nil, problem.BadRequest("a nova cópia continua ilegível; envie outra imagem antes de substituir")
				}
				var same bool
				if err := tx.QueryRow(ctx, `SELECT o.employee_id IS NULL OR o.employee_id=n.employee_id FROM documents o, documents n WHERE o.id=$1 AND n.id=$2`, *old, docID).Scan(&same); err != nil {
					return nil, err
				}
				if !same {
					return nil, problem.BadRequest("a nova cópia pertence a outro funcionário; não é possível substituir a anterior")
				}
				if _, err := tx.Exec(ctx, `UPDATE documents SET status='SUBSTITUIDO', atualizado_em=now() WHERE id=$1 AND tenant_id=$2`, *old, tenantID); err != nil {
					return nil, err
				}
			}
		}
	case "MUDAR_TIPO", "VINCULAR":
		// continua na fila até ser confirmado
	case "SUBSTITUIR_ANTERIOR":
		if err := needEmployee(); err != nil {
			return nil, err
		}
		var dup *string
		tx.QueryRow(ctx, `SELECT duplicata_de::text FROM documents WHERE id=$1`, docID).Scan(&dup)
		if dup == nil {
			return nil, problem.BadRequest("este documento não tem duplicata registrada")
		}
		tx.Exec(ctx, `UPDATE documents SET status='SUBSTITUIDO', atualizado_em=now() WHERE id=$1`, *dup)
		tx.Exec(ctx, `UPDATE documents SET status='REVISADO', substitui_id=$2, versao=(SELECT versao+1 FROM documents WHERE id=$2), atualizado_em=now() WHERE id=$1`, docID, *dup)
	case "MANTER_AMBOS":
		if err := needEmployee(); err != nil {
			return nil, err
		}
		setStatus("REVISADO")
	case "SOLICITAR_REENVIO":
		tx.Exec(ctx, `UPDATE documents SET status='REJEITADO', motivos_revisao='["REENVIO_SOLICITADO"]', atualizado_em=now() WHERE id=$1`, docID)
	case "REJEITAR", "DESCARTAR":
		if strings.TrimSpace(in.Motivo) == "" {
			return nil, problem.BadRequest("informe o motivo da rejeição")
		}
		setStatus("REJEITADO")
	case "DIVIDIR":
		if batchID == "" {
			return nil, problem.BadRequest("documento sem lote de origem")
		}
		var keep, move []int32
		for _, p := range before.Paginas {
			if int(p) < in.PaginaDivisao {
				keep = append(keep, p)
			} else {
				move = append(move, p)
			}
		}
		if len(keep) == 0 || len(move) == 0 {
			return nil, problem.BadRequest("a página de divisão deve estar no meio do documento")
		}
		t1, _ := i.rebuildText(ctx, tx, batchID, keep)
		t2, _ := i.rebuildText(ctx, tx, batchID, move)
		tx.Exec(ctx, `UPDATE documents SET paginas=$2, texto_ocr=$3, status='AGUARDANDO_REVISAO', atualizado_em=now() WHERE id=$1`, docID, keep, t1)
		_, err := tx.Exec(ctx, `INSERT INTO documents (tenant_id,batch_id,employee_id,unit_id,document_type,titulo,paginas,confianca,status,campos,alertas,motivos_revisao,texto_ocr,sensivel_saude,nome_arquivo,pasta_destino)
		  SELECT tenant_id,batch_id,employee_id,unit_id,document_type,titulo,$2,confianca,'AGUARDANDO_REVISAO','{}','[]','["DIVISAO_MANUAL"]',$3,sensivel_saude,nome_arquivo,pasta_destino FROM documents WHERE id=$1`, docID, move, t2)
		if err != nil {
			return nil, err
		}
	case "JUNTAR":
		var nextID string
		var nextPages []int32
		err := tx.QueryRow(ctx, `SELECT id::text, paginas FROM documents WHERE batch_id=$1 AND id<>$2 AND status<>'REJEITADO' AND status<>'SUBSTITUIDO' AND paginas[1] > $3
		  ORDER BY paginas[1] LIMIT 1`, batchID, docID, before.Paginas[len(before.Paginas)-1]).Scan(&nextID, &nextPages)
		if err != nil {
			return nil, problem.BadRequest("não há documento seguinte para juntar")
		}
		all := append(append([]int32{}, before.Paginas...), nextPages...)
		txt, _ := i.rebuildText(ctx, tx, batchID, all)
		tx.Exec(ctx, `UPDATE documents SET paginas=$2, texto_ocr=$3, status='AGUARDANDO_REVISAO', atualizado_em=now() WHERE id=$1`, docID, all, txt)
		tx.Exec(ctx, `UPDATE documents SET status='REJEITADO', motivos_revisao='["JUNTADO"]', atualizado_em=now() WHERE id=$1`, nextID)
	default:
		return nil, problem.BadRequest("ação de revisão desconhecida")
	}
	after, _, _ := i.snapshot(ctx, tx, docID)
	bj, _ := json.Marshal(before)
	aj, _ := json.Marshal(after)
	if _, err := tx.Exec(ctx, `INSERT INTO reviews (tenant_id, document_id, revisor_id, acao, antes, depois, duracao_ms) VALUES ($1,$2,$3,$4,$5,$6,$7)`,
		tenantID, docID, userID, in.Acao, bj, aj, in.DuracaoMs); err != nil {
		return nil, err
	}
	mes := "to_char(now(),'YYYY-MM')"
	tx.Exec(ctx, `INSERT INTO usage_monthly (tenant_id, mes, revisoes) VALUES ($1, `+mes+`, 1) ON CONFLICT (tenant_id, mes) DO UPDATE SET revisoes=usage_monthly.revisoes+1`, tenantID)
	// fecha o lote quando não sobra nada na fila
	if batchID != "" {
		tx.Exec(ctx, `UPDATE batches SET status='PROCESSADO' WHERE id=$1 AND status='PROCESSADO_COM_PENDENCIAS'
		  AND NOT EXISTS (SELECT 1 FROM documents WHERE batch_id=$1 AND status='AGUARDANDO_REVISAO')`, batchID)
	}
	var out []string
	for k := range affected {
		out = append(out, k)
	}
	return out, nil
}

// Corrigir campos reavalia os alertas que dependem desses campos; sinais antigos não devem permanecer após a correção.
func (i *Ingestor) reconcileReviewAlerts(ctx context.Context, tx pgx.Tx, tenantID, docID string, submitted map[string]any) error {
	var fields, alertsRaw, ncsRaw, reasonsRaw []byte
	var employee *string
	var tipo string
	var expiry *time.Time
	if err := tx.QueryRow(ctx, `SELECT campos, alertas, nao_conformidades, motivos_revisao, employee_id::text, document_type, validade_ate FROM documents WHERE id=$1`, docID).
		Scan(&fields, &alertsRaw, &ncsRaw, &reasonsRaw, &employee, &tipo, &expiry); err != nil {
		return err
	}
	var campos map[string]any
	var alerts, ncs []map[string]any
	var reasons []string
	json.Unmarshal(fields, &campos)
	json.Unmarshal(alertsRaw, &alerts)
	json.Unmarshal(ncsRaw, &ncs)
	json.Unmarshal(reasonsRaw, &reasons)
	clean := map[string]bool{"DADOS_DIVERGENTES": true, "DOCUMENTO_VENCIDO": true, "CERTIDAO_VENCIDA": true}
	var cpfMismatch bool
	if raw := cpf.Clean(str(submitted, "cpf")); cpf.Valid(raw) {
		clean["CPF_INVALIDO"] = true
		clean["CPF_DIVERGENTE"] = true
		if employee != nil {
			var hash string
			if err := tx.QueryRow(ctx, `SELECT cpf_hash FROM employees WHERE tenant_id=$1 AND id=$2`, tenantID, *employee).Scan(&hash); err != nil {
				return err
			}
			if hash != i.KR.Blind(tenantID, raw) {
				cpfMismatch = true
			}
		}
	}
	filtered := make([]map[string]any, 0, len(alerts)+2)
	for _, a := range alerts {
		if !clean[str(a, "codigo")] {
			filtered = append(filtered, a)
		}
	}
	alerts = filtered
	if cpfMismatch {
		alerts = append(alerts, map[string]any{"severidade": "erro", "codigo": "CPF_DIVERGENTE", "mensagem": "CPF informado difere do funcionário vinculado"})
	}
	if employee != nil && str(campos, "nome") != "" {
		var cad string
		if err := tx.QueryRow(ctx, `SELECT nome FROM employees WHERE tenant_id=$1 AND id=$2`, tenantID, *employee).Scan(&cad); err != nil {
			return err
		}
		if bad, why := NameMismatch(str(campos, "nome"), cad); bad {
			alerts = append(alerts, map[string]any{"severidade": "aviso", "codigo": "DADOS_DIVERGENTES", "mensagem": fmt.Sprintf("Nome no documento (%q) difere do cadastro (%q): %s", str(campos, "nome"), cad, why)})
		}
	}
	expired := expiry != nil && expiry.Format("2006-01-02") < time.Now().Format("2006-01-02")
	cert := tipo == "CRF_FGTS" || tipo == "CNDT" || tipo == "CND_FEDERAL"
	if expired {
		code := "DOCUMENTO_VENCIDO"
		if cert {
			code = "CERTIDAO_VENCIDA"
		}
		alerts = append(alerts, map[string]any{"severidade": "erro", "codigo": code, "mensagem": "Documento vencido em " + expiry.Format("02/01/2006")})
	}
	cleanNC := make([]map[string]any, 0, len(ncs))
	for _, nc := range ncs {
		if str(nc, "codigo") != "CERTIDAO_VENCIDA" {
			cleanNC = append(cleanNC, nc)
		}
	}
	if expired && cert {
		cleanNC = append(cleanNC, map[string]any{"codigo": "CERTIDAO_VENCIDA", "descricao": "Certidão vencida em " + expiry.Format("02/01/2006")})
	}
	newReasons := make([]string, 0, len(reasons)+2)
	for _, r := range reasons {
		if r != "DADOS_DIVERGENTES" && r != "CPF_DIVERGENTE" && r != "ALERTA_ERRO" && !clean[r] {
			newReasons = append(newReasons, r)
		}
	}
	for _, a := range alerts {
		if code := str(a, "codigo"); code == "DADOS_DIVERGENTES" || code == "CPF_DIVERGENTE" {
			newReasons = append(newReasons, code)
		}
		if str(a, "severidade") == "erro" {
			newReasons = append(newReasons, "ALERTA_ERRO")
		}
	}
	aj, _ := json.Marshal(alerts)
	nj, _ := json.Marshal(cleanNC)
	mj, _ := json.Marshal(uniq(newReasons))
	_, err := tx.Exec(ctx, `UPDATE documents SET alertas=$2, nao_conformidades=$3, motivos_revisao=$4 WHERE id=$1`, docID, aj, nj, mj)
	return err
}

// CreateEmployee cadastra um funcionário (CPF cifrado com a DEK da empresa + hash cego para busca exata).
func (i *Ingestor) CreateEmployee(ctx context.Context, tx pgx.Tx, tenantID string, e NewEmployee) (string, error) {
	d := cpf.Clean(e.CPF)
	if !cpf.Valid(d) || len(strings.TrimSpace(e.Nome)) < 3 {
		return "", problem.BadRequest("nome e CPF válido são obrigatórios para o funcionário")
	}
	var wrapped []byte
	if err := tx.QueryRow(ctx, `SELECT dek_wrapped FROM tenants WHERE id=$1`, tenantID).Scan(&wrapped); err != nil {
		return "", err
	}
	dek, err := i.KR.DEK(tenantID, wrapped)
	if err != nil {
		return "", err
	}
	enc, err := sealCPF(dek, d, tenantID)
	if err != nil {
		return "", err
	}
	var id string
	origem := e.Origem
	if origem == "" {
		origem = "MANUAL"
	}
	query := `INSERT INTO employees (tenant_id, unit_id, cpf_cifrado, cpf_hash, cpf_mascarado, nome, matricula, cargo_id, admissao, pre_cadastro, origem)
	  VALUES ($1,$2,$3,$4,$5,$6,nullif($7,''),$8,$9::date,$10,$11)`
	if e.Pre {
		query += ` ON CONFLICT (tenant_id, cpf_hash) DO NOTHING`
	}
	err = tx.QueryRow(ctx, query+` RETURNING id::text`,
		tenantID, e.UnitID, enc, i.KR.Blind(tenantID, d), cpf.Mask(d), strings.TrimSpace(e.Nome), e.Matricula, e.CargoID, e.Admissao, e.Pre, origem).Scan(&id)
	if err == pgx.ErrNoRows && e.Pre {
		err = tx.QueryRow(ctx, `SELECT id::text FROM employees WHERE tenant_id=$1 AND cpf_hash=$2`, tenantID, i.KR.Blind(tenantID, d)).Scan(&id)
	}
	if err != nil && strings.Contains(err.Error(), "employees_tenant_id_cpf_hash_key") {
		return "", problem.Conflict("já existe funcionário com este CPF")
	}
	return id, err
}
