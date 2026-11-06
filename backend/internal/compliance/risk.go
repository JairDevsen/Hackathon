package compliance

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// Indicadores de risco trabalhista: sinais, extraídos dos documentos, de situações que costumam gerar reclamações.
// São INDICADORES para triagem — não substituem a análise do jurídico.
type riskDef struct{ Sev, Cat, Titulo, Base string }

var riskCatalog = map[string]riskDef{
	"JORNADA_ACIMA_10H":          {"ALTO", "JORNADA", "Jornada acima de 10 horas", "CLT art. 59 (máximo de 2 horas extras por dia)"},
	"INTERVALO_INFERIOR_1H":      {"ALTO", "JORNADA", "Intervalo intrajornada insuficiente", "CLT art. 71"},
	"PONTO_BRITANICO":            {"ALTO", "JORNADA", "Cartão de ponto com marcações uniformes", "TST Súmula 338 (o ponto uniforme invalida o registro de horário)"},
	"HE_SEM_PAGAMENTO":           {"MEDIO", "REMUNERACAO", "Pagamento de horas extras não identificado no holerite", "CLT art. 59 §1º e CF art. 7º, XVI (adicional mínimo de 50%)"},
	"HOLERITE_AUSENTE_COM_PONTO": {"MEDIO", "REMUNERACAO", "Cartão de ponto com horas extras e sem holerite validado", "CLT art. 464 (prova do pagamento)"},
	"FGTS_DIVERGENTE":            {"ALTO", "REMUNERACAO", "Depósito de FGTS divergente do devido", "Lei 8.036/90 art. 15"},
	"FERIAS_SEM_COMPROVANTE":     {"MEDIO", "FERIAS", "Sem recibo de férias nos últimos 24 meses", "CLT art. 137 (pagamento em dobro quando concedidas fora do prazo)"},
	"TRCT_FORA_DO_PRAZO":         {"MEDIO", "RESCISAO", "TRCT datado depois de 10 dias do desligamento", "CLT art. 477 §6º e §8º (conferir data efetiva do pagamento)"},
	"TRCT_AUSENTE":               {"MEDIO", "RESCISAO", "Sem TRCT validado 10 dias após o desligamento", "CLT art. 477 §6º e §8º (conferir data efetiva do pagamento)"},
	"VINCULO_SEM_REGISTRO":       {"MEDIO", "REGISTRO", "Há holerite/ponto, mas nenhum registro validado no dossiê", "CLT art. 29 (registro do empregado)"},
	"DOCUMENTO_FORA_DO_VINCULO":  {"MEDIO", "REGISTRO", "Documento fora do período do vínculo", "Coerência entre admissão/desligamento e documentos"},
	"DOCUMENTO_SEM_ASSINATURA":   {"MEDIO", "PROVA", "Documento sem assinatura", "CLT art. 464 e art. 818 (ônus da prova)"},
	"RECUSA_SEM_TESTEMUNHAS":     {"MEDIO", "PROVA", "Recusa de ciência sem testemunhas", "CLT art. 818 (ônus da prova)"},
	"DADOS_DIVERGENTES":          {"MEDIO", "PROVA", "Dados divergentes entre documento e cadastro", "Fragiliza a prova documental"},
	"IMAGEM_BORRADA":             {"MEDIO", "PROVA", "Documento ilegível não serve como prova", "CLT art. 818 (ônus da prova)"},
	"PAGINA_ILEGIVEL":            {"MEDIO", "PROVA", "Página ilegível requer nova cópia", "CLT art. 818 (ônus da prova)"},
	"TIPO_OUTRO":                 {"BAIXO", "PROVA", "Tipo documental não identificado", "Classificação humana necessária para análise documental"},
	"CPF_INVALIDO":               {"MEDIO", "PROVA", "CPF lido com dígito verificador inválido", "Identificação do titular a confirmar"},
	"CPF_DIVERGENTE":             {"ALTO", "PROVA", "CPF da nova cópia diverge do funcionário indicado", "Identificação do titular a confirmar antes de vincular"},
	"TRANSCRICAO_MANUAL":         {"MEDIO", "PROVA", "Dados transcritos de original ilegível", "Conferir documento legível para comprovação"},
	"DOCUMENTO_VENCIDO":          {"MEDIO", "DOCUMENTAL", "Documento vencido", "Validade do documento"},
	"EMPREGADOR_DIVERGENTE":      {"MEDIO", "TERCEIRIZACAO", "Documento de empresa diferente do empregador cadastrado", "CLT arts. 2º e 3º (identificação do empregador); conferir se houve troca de empregador"},
	"FORN_CERTIDAO_AUSENTE":      {"MEDIO", "TERCEIRIZACAO", "Terceirizada sem certidão de regularidade no dossiê", "TST Súmula 331, IV (responsabilidade subsidiária do tomador); Lei 6.019/74 art. 5º-A §5º (fiscalização das obrigações)"},
	"FORN_CONTRATO_AUSENTE":      {"MEDIO", "TERCEIRIZACAO", "Fornecedor sem contrato de prestação de serviço no dossiê", "Lei 6.019/74 art. 5º-B (requisitos do contrato de prestação de serviços)"},
	"FORN_CONTRATO_VENCIDO":      {"MEDIO", "TERCEIRIZACAO", "Contrato vencido com funcionários ainda alocados", "Lei 6.019/74 art. 5º-A e 5º-B (a prestação exige contrato vigente)"},
	"FORN_GUIA_FGTS_AUSENTE":     {"MEDIO", "TERCEIRIZACAO", "Guia de FGTS da terceirizada ausente na competência", "Lei 8.036/90 art. 15; TST Súmula 331, IV (a contratante responde subsidiariamente pelas obrigações não pagas)"},
	"FORN_AUTUACAO":              {"ALTO", "TERCEIRIZACAO", "Autuação ou fiscalização envolvendo a terceirizada", "Lei 6.019/74 art. 5º-A §5º; TST Súmula 331, IV e VI"},
	"FORN_PROCESSO_JUDICIAL":     {"ALTO", "TERCEIRIZACAO", "Processo trabalhista envolvendo a terceirizada", "TST Súmula 331, IV e VI (a responsabilidade subsidiária abrange todas as verbas da condenação)"},
	"FORN_AUDITORIA_RISCO_ALTO":  {"ALTO", "TERCEIRIZACAO", "Auditoria aponta risco alto no fornecedor", "Lei 6.019/74 art. 5º-A §5º (dever de fiscalizar da contratante)"},
	"CERTIDAO_VENCIDA":           {"MEDIO", "TERCEIRIZACAO", "Certidão da empresa vencida", "TST Súmula 331 (responsabilidade subsidiária do tomador)"},
	"ASO_VENCIDO":                {"MEDIO", "SEGURANCA", "ASO vencido", "NR-7 (PCMSO)"},
	"NR_VENCIDO":                 {"MEDIO", "SEGURANCA", "Treinamento de NR vencido", "NR-1 e NRs específicas"},
}

type rdoc struct {
	ID, Emp, Tipo, Comp, Status, Origem string
	Data                                *time.Time
	NCs, Alertas                        []map[string]any
	Campos                              map[string]any
	Motivos                             []string
	Sup                                 string // fornecedor do documento (vazio = a própria empresa)
}
type remp struct {
	ID       string
	Adm, Des *time.Time
	Status   string
	Sup      string // empregador (fornecedor); vazio = a própria empresa
}

// rsup: fornecedor ou terceirizada da contratante.
type rsup struct {
	ID, Razao, Tipo, Status string
	Fim                     *time.Time
}
type riskRow struct{ Emp, Doc, Codigo, Ref, Desc, Sup string }

func hhmm(s string) float64 {
	var h, m int
	if _, err := fmt.Sscanf(strings.ReplaceAll(strings.ToLower(s), "h", ":"), "%d:%d", &h, &m); err != nil {
		return 0
	}
	return float64(h) + float64(m)/60
}

func str(m map[string]any, k string) string {
	if v, ok := m[k]; ok && v != nil {
		return strings.TrimSpace(fmt.Sprint(v))
	}
	return ""
}

// deriveRisks aplica as regras (puro: sem banco, testável).
func temTipo(ds []rdoc, tipo string) bool {
	for _, d := range ds {
		if d.Tipo == tipo {
			return true
		}
	}
	return false
}

func deriveRisks(emps []remp, docs []rdoc, vencidos map[string][][2]string, now time.Time) []riskRow {
	var out []riskRow
	add := func(emp, doc, code, ref, desc string) {
		if _, ok := riskCatalog[code]; ok {
			out = append(out, riskRow{Emp: emp, Doc: doc, Codigo: code, Ref: ref, Desc: desc})
		}
	}
	byEmp := map[string][]rdoc{}
	for _, d := range docs {
		if d.Status != "AGUARDANDO_REVISAO" {
			byEmp[d.Emp] = append(byEmp[d.Emp], d)
		}
		for _, nc := range d.NCs {
			add(d.Emp, d.ID, str(nc, "codigo"), d.Comp, str(nc, "descricao"))
		}
		for _, a := range d.Alertas {
			switch c := str(a, "codigo"); c {
			case "DADOS_DIVERGENTES", "DOCUMENTO_VENCIDO", "IMAGEM_BORRADA", "CPF_INVALIDO", "CPF_DIVERGENTE", "EMPREGADOR_DIVERGENTE":
				add(d.Emp, d.ID, c, d.Comp, str(a, "mensagem"))
			}
		}
		for _, m := range d.Motivos {
			if m == "PAGINA_ILEGIVEL" || m == "TIPO_OUTRO" || m == "TRANSCRICAO_MANUAL" {
				add(d.Emp, d.ID, m, d.Comp, riskCatalog[m].Titulo)
			}
		}
	}
	for _, e := range emps {
		ds := byEmp[e.ID]
		// dados digitados (origem MANUAL) podem ACRESCENTAR indicadores, mas nunca comprovam presença: ausência exige documento com imagem
		var dp []rdoc
		for _, d := range ds {
			if d.Origem != "MANUAL" {
				dp = append(dp, d)
			}
		}
		hol := map[string]rdoc{}
		tipos := map[string]bool{}
		for _, d := range dp {
			tipos[d.Tipo] = true
			if d.Tipo == "HOLERITE" && d.Comp != "" {
				hol[d.Comp] = d
			}
		}
		for _, d := range ds {
			// horas extras no ponto × pagamento no holerite da mesma competência
			if d.Tipo == "CARTAO_PONTO" && d.Comp != "" && hhmm(str(d.Campos, "horas_extras")) > 0 {
				h, ok := hol[d.Comp]
				switch {
				case !ok:
					add(e.ID, d.ID, "HOLERITE_AUSENTE_COM_PONTO", d.Comp, fmt.Sprintf("Ponto de %s com %s de horas extras e nenhum holerite validado da competência", d.Comp, str(d.Campos, "horas_extras")))
				case str(h.Campos, "pagamento_horas_extras") == "":
					add(e.ID, d.ID, "HE_SEM_PAGAMENTO", d.Comp, fmt.Sprintf("Ponto de %s registra %s de horas extras; o pagamento não foi identificado no holerite extraído. Conferir o original.", d.Comp, str(d.Campos, "horas_extras")))
				}
			}
			// documento mensal fora do período do vínculo
			if d.Comp != "" && (d.Tipo == "HOLERITE" || d.Tipo == "CARTAO_PONTO" || d.Tipo == "RECIBO_BENEFICIOS") {
				if e.Adm != nil && d.Comp < e.Adm.Format("2006-01") {
					add(e.ID, d.ID, "DOCUMENTO_FORA_DO_VINCULO", d.Comp, fmt.Sprintf("Documento da competência %s é anterior à admissão (%s)", d.Comp, e.Adm.Format("02/01/2006")))
				}
				if e.Des != nil && d.Comp > e.Des.Format("2006-01") {
					add(e.ID, d.ID, "DOCUMENTO_FORA_DO_VINCULO", d.Comp, fmt.Sprintf("Documento da competência %s é posterior ao desligamento (%s)", d.Comp, e.Des.Format("02/01/2006")))
				}
			}
		}
		if (tipos["HOLERITE"] || tipos["CARTAO_PONTO"]) && !tipos["CONTRATO_TRABALHO"] && !tipos["FICHA_REGISTRO"] && !tipos["CTPS"] {
			add(e.ID, "", "VINCULO_SEM_REGISTRO", "", "Existem holerites/cartões de ponto no dossiê, mas nenhum contrato, ficha de registro ou CTPS validado")
		}
		// férias: vínculo com mais de 23 meses e nenhum recibo nos últimos 24
		if e.Status == "ATIVO" && e.Adm != nil && e.Adm.Before(now.AddDate(0, -23, 0)) {
			ok := false
			for _, d := range dp {
				if d.Tipo == "RECIBO_FERIAS" && (d.Data == nil || d.Data.After(now.AddDate(0, -24, 0))) {
					ok = true
				}
			}
			if !ok {
				add(e.ID, "", "FERIAS_SEM_COMPROVANTE", "", fmt.Sprintf("Admitido em %s e sem recibo de férias nos últimos 24 meses no dossiê", e.Adm.Format("02/01/2006")))
			}
		}
		// rescisão: TRCT em até 10 dias do desligamento
		if e.Des != nil {
			var trct *rdoc
			for i := range ds {
				if ds[i].Tipo == "TRCT" {
					trct = &ds[i]
				}
			}
			switch {
			case trct != nil && trct.Data != nil && trct.Data.Sub(*e.Des) > 10*24*time.Hour:
				add(e.ID, trct.ID, "TRCT_FORA_DO_PRAZO", "", fmt.Sprintf("TRCT datado em %s para desligamento em %s. Conferir a data do pagamento antes de concluir atraso.", trct.Data.Format("02/01/2006"), e.Des.Format("02/01/2006")))
			case !temTipo(dp, "TRCT") && now.Sub(*e.Des) > 10*24*time.Hour:
				add(e.ID, "", "TRCT_AUSENTE", "", fmt.Sprintf("Desligado em %s e sem TRCT validado no dossiê. Conferir o pagamento da rescisão.", e.Des.Format("02/01/2006")))
			}
		}
		for _, v := range vencidos[e.ID] {
			code := "ASO_VENCIDO"
			if v[0] == "TREINAMENTO_NR" {
				code = "NR_VENCIDO"
			}
			add(e.ID, "", code, v[1], "Item vencido: "+riskCatalog[code].Titulo)
		}
	}
	return out
}

// RecomputeRisks regenera os indicadores do funcionário (ou da empresa toda) preservando os que o admin marcou como ignorados.
func RecomputeRisks(ctx context.Context, tx pgx.Tx, tenantID, employeeID string) error {
	var emps []remp
	q := `SELECT id::text, admissao, desligamento, status, coalesce(supplier_id::text,'') FROM employees WHERE tenant_id=$1`
	args := []any{tenantID}
	if employeeID != "" {
		q += ` AND id=$2`
		args = append(args, employeeID)
	}
	rows, err := tx.Query(ctx, q, args...)
	if err != nil {
		return err
	}
	for rows.Next() {
		var e remp
		if err := rows.Scan(&e.ID, &e.Adm, &e.Des, &e.Status, &e.Sup); err != nil {
			rows.Close()
			return err
		}
		emps = append(emps, e)
	}
	rows.Close()
	dq := `SELECT id::text, coalesce(employee_id::text,''), document_type, coalesce(competencia,''), data_documento, status, origem, nao_conformidades, alertas, campos, motivos_revisao, coalesce(supplier_id::text,'')
	  FROM documents WHERE tenant_id=$1 AND status IN ('AUTO_APROVADO','REVISADO','AGUARDANDO_REVISAO')`
	dargs := []any{tenantID}
	if employeeID != "" {
		dq += ` AND employee_id=$2`
		dargs = append(dargs, employeeID)
	}
	drows, err := tx.Query(ctx, dq, dargs...)
	if err != nil {
		return err
	}
	var docs []rdoc
	for drows.Next() {
		var d rdoc
		var nc, al, cp, mot []byte
		if err := drows.Scan(&d.ID, &d.Emp, &d.Tipo, &d.Comp, &d.Data, &d.Status, &d.Origem, &nc, &al, &cp, &mot, &d.Sup); err != nil {
			drows.Close()
			return err
		}
		json.Unmarshal(nc, &d.NCs)
		json.Unmarshal(al, &d.Alertas)
		json.Unmarshal(cp, &d.Campos)
		json.Unmarshal(mot, &d.Motivos)
		docs = append(docs, d)
	}
	drows.Close()
	venc := map[string][][2]string{}
	vq := `SELECT ci.employee_id::text, dt.codigo, ci.referencia FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id
	  WHERE ci.tenant_id=$1 AND ci.status='VENCIDO' AND ci.employee_id IS NOT NULL AND dt.codigo IN ('ASO','TREINAMENTO_NR')`
	vargs := []any{tenantID}
	if employeeID != "" {
		vq += ` AND ci.employee_id=$2`
		vargs = append(vargs, employeeID)
	}
	vrows, err := tx.Query(ctx, vq, vargs...)
	if err != nil {
		return err
	}
	for vrows.Next() {
		var e, cod, ref string
		vrows.Scan(&e, &cod, &ref)
		venc[e] = append(venc[e], [2]string{cod, ref})
	}
	vrows.Close()

	now := time.Now()
	risks := deriveRisks(emps, docs, venc, now)
	// o fornecedor do risco: o do documento; sem documento, o empregador do funcionário
	docSup, empSup := map[string]string{}, map[string]string{}
	for _, d := range docs {
		docSup[d.ID] = d.Sup
	}
	for _, e := range emps {
		empSup[e.ID] = e.Sup
	}
	for k := range risks {
		if risks[k].Doc != "" {
			risks[k].Sup = docSup[risks[k].Doc]
		}
		if risks[k].Sup == "" && risks[k].Doc == "" && risks[k].Emp != "" {
			risks[k].Sup = empSup[risks[k].Emp]
		}
	}
	if employeeID == "" { // riscos do fornecedor precisam do quadro completo: só no recálculo da empresa toda
		srows, err := tx.Query(ctx, `SELECT id::text, razao_social, tipo, status, contrato_fim FROM suppliers WHERE tenant_id=$1`, tenantID)
		if err != nil {
			return err
		}
		var sups []rsup
		for srows.Next() {
			var x rsup
			if err := srows.Scan(&x.ID, &x.Razao, &x.Tipo, &x.Status, &x.Fim); err != nil {
				srows.Close()
				return err
			}
			sups = append(sups, x)
		}
		srows.Close()
		risks = append(risks, deriveSupplierRisks(sups, emps, docs, now)...)
	}
	var emp, sup, doc, cod, sev, cat, tit, desc, base, ref, keep []string
	seen := map[string]bool{}
	for _, r := range risks {
		def := riskCatalog[r.Codigo]
		k := r.Emp + "|" + r.Sup + "|" + r.Doc + "|" + r.Codigo + "|" + r.Ref
		if seen[k] {
			continue
		}
		seen[k] = true
		emp, sup, doc, cod, sev, cat, tit, desc, base, ref = append(emp, r.Emp), append(sup, r.Sup), append(doc, r.Doc), append(cod, r.Codigo), append(sev, def.Sev), append(cat, def.Cat), append(tit, def.Titulo), append(desc, r.Desc), append(base, def.Base), append(ref, r.Ref)
		keep = append(keep, k)
	}
	if len(cod) > 0 {
		if _, err := tx.Exec(ctx, `INSERT INTO risk_indicators (tenant_id, employee_id, supplier_id, document_id, codigo, severidade, categoria, titulo, descricao, base_legal, referencia)
		  SELECT $1, nullif(e,'')::uuid, nullif(sp,'')::uuid, nullif(d,'')::uuid, c, s, ca, t, de, b, r FROM unnest($2::text[],$3::text[],$4::text[],$5::text[],$6::text[],$7::text[],$8::text[],$9::text[],$10::text[],$11::text[]) AS x(e,sp,d,c,s,ca,t,de,b,r)
		  ON CONFLICT (tenant_id, coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid), coalesce(supplier_id,'00000000-0000-0000-0000-000000000000'::uuid), coalesce(document_id,'00000000-0000-0000-0000-000000000000'::uuid), codigo, referencia)
		  DO UPDATE SET descricao=EXCLUDED.descricao, severidade=EXCLUDED.severidade, titulo=EXCLUDED.titulo, base_legal=EXCLUDED.base_legal, atualizado_em=now()`,
			tenantID, emp, sup, doc, cod, sev, cat, tit, desc, base, ref); err != nil {
			return fmt.Errorf("upsert riscos: %w", err)
		}
	}
	// o que deixou de existir (documento corrigido/substituído) some; indicadores ignorados pelo admin são preservados
	sc := ``
	dargs2 := []any{tenantID, keep}
	if employeeID != "" {
		sc = ` AND employee_id=$3::uuid`
		dargs2 = append(dargs2, employeeID)
	}
	_, err = tx.Exec(ctx, `DELETE FROM risk_indicators WHERE tenant_id=$1 AND status='ABERTO'`+sc+`
	  AND (coalesce(employee_id::text,'')||'|'||coalesce(supplier_id::text,'')||'|'||coalesce(document_id::text,'')||'|'||codigo||'|'||referencia) <> ALL($2::text[])`, dargs2...)
	return err
}

// deriveSupplierRisks: sinais, extraídos dos documentos do fornecedor, de risco para a CONTRATANTE (responsabilidade
// subsidiária pelas obrigações trabalhistas da terceirizada). Puro: sem banco. Dado digitado (origem MANUAL) acrescenta
// indicadores, mas não comprova presença de certidão, contrato ou guia.
func deriveSupplierRisks(sups []rsup, emps []remp, docs []rdoc, now time.Time) []riskRow {
	var out []riskRow
	atual := now.Format("2006-01")
	for _, s := range sups {
		if s.Status != "ATIVO" {
			continue
		}
		add := func(doc, code, ref, desc string) {
			if _, ok := riskCatalog[code]; ok {
				out = append(out, riskRow{Doc: doc, Codigo: code, Ref: ref, Desc: desc, Sup: s.ID})
			}
		}
		ativos := 0
		for _, e := range emps {
			if e.Sup == s.ID && e.Status == "ATIVO" {
				ativos++
			}
		}
		var proof []rdoc // documentos da empresa que comprovam (com imagem e já validados)
		comps, guias := map[string]bool{}, map[string]bool{}
		for _, d := range docs {
			if d.Sup != s.ID {
				continue
			}
			ok := d.Origem != "MANUAL" && d.Status != "AGUARDANDO_REVISAO"
			if d.Emp == "" {
				if ok {
					proof = append(proof, d)
				}
				if ok && d.Tipo == "GUIA_FGTS" && d.Comp != "" {
					guias[d.Comp] = true
				}
				switch d.Tipo {
				case "AUTO_INFRACAO":
					add(d.ID, "FORN_AUTUACAO", "", fmt.Sprintf("%s: documento de fiscalização/autuação registrado em nome do fornecedor. Avaliar impacto para a contratante.", s.Razao))
				case "PROCESSO_JUDICIAL":
					add(d.ID, "FORN_PROCESSO_JUDICIAL", "", fmt.Sprintf("%s: citação ou processo trabalhista registrado. Verificar se a contratante figura como responsável subsidiária.", s.Razao))
				case "RELATORIO_AUDITORIA":
					if strings.EqualFold(str(d.Campos, "nivel_risco"), "ALTO") {
						add(d.ID, "FORN_AUDITORIA_RISCO_ALTO", "", fmt.Sprintf("%s: relatório de auditoria classificou o risco como ALTO.", s.Razao))
					}
				}
			} else if ok && (d.Tipo == "HOLERITE" || d.Tipo == "CARTAO_PONTO") && d.Comp != "" && d.Comp < atual {
				comps[d.Comp] = true
			}
		}
		tem := func(tipo string) bool { return temTipo(proof, tipo) }
		if !tem("CONTRATO_PRESTACAO_SERVICO") {
			add("", "FORN_CONTRATO_AUSENTE", "", fmt.Sprintf("%s: nenhum contrato de prestação de serviço validado no dossiê.", s.Razao))
		} else if s.Fim != nil && s.Fim.Before(now) && ativos > 0 {
			add("", "FORN_CONTRATO_VENCIDO", s.Fim.Format("2006-01-02"), fmt.Sprintf("%s: contrato encerrado em %s e ainda há %d funcionário(s) ativo(s) alocado(s).", s.Razao, s.Fim.Format("02/01/2006"), ativos))
		}
		if s.Tipo != "TERCEIRIZADA" && ativos == 0 {
			continue // fornecedor sem trabalhadores alocados: sem certidões trabalhistas nem guias mensais
		}
		for _, t := range []string{"CRF_FGTS", "CNDT", "CND_FEDERAL"} {
			if !tem(t) {
				add("", "FORN_CERTIDAO_AUSENTE", t, fmt.Sprintf("%s: sem %s validado no dossiê.", s.Razao, strings.ReplaceAll(t, "_", " ")))
			}
		}
		for comp := range comps {
			if !guias[comp] {
				add("", "FORN_GUIA_FGTS_AUSENTE", comp, fmt.Sprintf("%s: há holerite ou cartão de ponto de %s, mas nenhuma guia de FGTS dessa competência.", s.Razao, comp))
			}
		}
	}
	return out
}
