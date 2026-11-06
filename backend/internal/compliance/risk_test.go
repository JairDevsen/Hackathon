package compliance

import (
	"testing"
	"time"
)

func TestRegrasDeRiscoCruzadas(t *testing.T) {
	now := time.Date(2026, 11, 5, 0, 0, 0, 0, time.Local)
	d := func(y int, m time.Month, dia int) *time.Time {
		x := time.Date(y, m, dia, 0, 0, 0, 0, time.Local)
		return &x
	}
	emps := []remp{
		{ID: "A", Adm: d(2024, 1, 10), Status: "ATIVO"},                        // férias vencidas + HE sem pagamento + sem registro
		{ID: "B", Adm: d(2026, 3, 1), Des: d(2026, 6, 1), Status: "DESLIGADO"}, // TRCT ausente + doc fora do vínculo
		{ID: "C", Adm: d(2026, 1, 1), Des: d(2026, 5, 20), Status: "DESLIGADO"},
	}
	docs := []rdoc{
		{ID: "p1", Emp: "A", Tipo: "CARTAO_PONTO", Comp: "2026-09", Campos: map[string]any{"horas_extras": "44:00"}},
		{ID: "h1", Emp: "A", Tipo: "HOLERITE", Comp: "2026-09", Campos: map[string]any{}},                            // sem pagamento de HE
		{ID: "p2", Emp: "A", Tipo: "CARTAO_PONTO", Comp: "2026-10", Campos: map[string]any{"horas_extras": "10:30"}}, // sem holerite
		{ID: "h2", Emp: "B", Tipo: "HOLERITE", Comp: "2026-09", Campos: map[string]any{}},                            // posterior ao desligamento
		{ID: "t1", Emp: "C", Tipo: "TRCT", Data: d(2026, 6, 15), Campos: map[string]any{}},                           // 26 dias depois
		{ID: "n1", Emp: "A", Tipo: "CARTAO_PONTO", Comp: "2026-08", NCs: []map[string]any{{"codigo": "JORNADA_ACIMA_10H", "descricao": "Jornada de 11:30"}}},
	}
	got := map[string]bool{}
	for _, r := range deriveRisks(emps, docs, map[string][][2]string{"A": {{"ASO", "PERIODICO"}}}, now) {
		got[r.Emp+":"+r.Codigo] = true
	}
	for _, want := range []string{"A:HE_SEM_PAGAMENTO", "A:HOLERITE_AUSENTE_COM_PONTO", "A:VINCULO_SEM_REGISTRO", "A:FERIAS_SEM_COMPROVANTE", "A:JORNADA_ACIMA_10H",
		"A:ASO_VENCIDO", "B:TRCT_AUSENTE", "B:DOCUMENTO_FORA_DO_VINCULO", "C:TRCT_FORA_DO_PRAZO"} {
		if !got[want] {
			t.Errorf("indicador esperado ausente: %s (veio %v)", want, got)
		}
	}
	// funcionário em dia não gera nada
	ok := []remp{{ID: "Z", Adm: d(2026, 8, 1), Status: "ATIVO"}}
	okDocs := []rdoc{{ID: "c", Emp: "Z", Tipo: "CONTRATO_TRABALHO"}, {ID: "h", Emp: "Z", Tipo: "HOLERITE", Comp: "2026-09", Campos: map[string]any{"pagamento_horas_extras": "100,00"}},
		{ID: "p", Emp: "Z", Tipo: "CARTAO_PONTO", Comp: "2026-09", Campos: map[string]any{"horas_extras": "02:00"}}}
	if r := deriveRisks(ok, okDocs, nil, now); len(r) != 0 {
		t.Fatalf("funcionário regular não deveria gerar indicadores: %+v", r)
	}
	if hhmm("44:00") != 44 || hhmm("1h30") != 1.5 || hhmm("") != 0 {
		t.Fatal("hhmm")
	}
}

func TestCatalogoDeRiscoTemBaseLegalEGravidade(t *testing.T) {
	for k, d := range riskCatalog {
		if d.Sev == "" || d.Cat == "" || d.Titulo == "" || d.Base == "" {
			t.Errorf("indicador %s incompleto: %+v", k, d)
		}
	}
}

func TestTranscricaoManualERevisaoNaoViramProvaDePagamento(t *testing.T) {
	now := time.Date(2026, 11, 6, 0, 0, 0, 0, time.UTC)
	ems := []remp{{ID: "A", Status: "ATIVO"}}
	docs := []rdoc{
		{ID: "p", Emp: "A", Tipo: "CARTAO_PONTO", Comp: "2026-10", Status: "REVISADO", Campos: map[string]any{"horas_extras": "02:00"}},
		{ID: "h", Emp: "A", Tipo: "HOLERITE", Comp: "2026-10", Status: "REVISADO", Origem: "MANUAL", Motivos: []string{"PAGINA_ILEGIVEL", "TRANSCRICAO_MANUAL"}, Campos: map[string]any{"pagamento_horas_extras": "200,00"}},
	}
	got := map[string]bool{}
	for _, r := range deriveRisks(ems, docs, nil, now) {
		got[r.Codigo] = true
	}
	if !got["HOLERITE_AUSENTE_COM_PONTO"] || !got["TRANSCRICAO_MANUAL"] || !got["PAGINA_ILEGIVEL"] {
		t.Fatalf("transcrição deve manter a pendência e o risco de prova: %v", got)
	}
	if got["HE_SEM_PAGAMENTO"] {
		t.Fatalf("transcrição não deve ser tratada como holerite validado: %v", got)
	}
}

func TestDadoDigitadoAcrescentaMasNaoComprovaAusencia(t *testing.T) {
	des := time.Date(2026, 8, 1, 0, 0, 0, 0, time.UTC)
	adm := time.Date(2023, 1, 9, 0, 0, 0, 0, time.UTC)
	trct := time.Date(2026, 9, 20, 0, 0, 0, 0, time.UTC)
	rec := time.Date(2026, 10, 1, 0, 0, 0, 0, time.UTC)
	emps := []remp{{ID: "A", Adm: &adm, Des: &des, Status: "DESLIGADO"}, {ID: "B", Adm: &adm, Status: "ATIVO"}}
	docs := []rdoc{
		{ID: "t", Emp: "A", Tipo: "TRCT", Data: &trct, Status: "REVISADO", Origem: "MANUAL"},
		{ID: "f", Emp: "B", Tipo: "RECIBO_FERIAS", Data: &rec, Status: "REVISADO", Origem: "MANUAL"},
	}
	got := map[string]bool{}
	for _, r := range deriveRisks(emps, docs, nil, time.Date(2026, 11, 6, 0, 0, 0, 0, time.UTC)) {
		got[r.Emp+":"+r.Codigo] = true
	}
	if !got["A:TRCT_FORA_DO_PRAZO"] {
		t.Error("TRCT digitado e atrasado deve gerar indicador")
	}
	if !got["B:FERIAS_SEM_COMPROVANTE"] {
		t.Error("recibo de férias digitado não comprova: indicador deve permanecer")
	}
	docs[1].Origem = "IA"
	for _, r := range deriveRisks(emps, docs, nil, time.Date(2026, 11, 6, 0, 0, 0, 0, time.UTC)) {
		if r.Emp == "B" && r.Codigo == "FERIAS_SEM_COMPROVANTE" {
			t.Error("recibo com imagem (origem IA) deve apagar o indicador")
		}
	}
}

func TestRiscosDeFornecedorParaAContratante(t *testing.T) {
	now := time.Date(2026, 11, 6, 0, 0, 0, 0, time.UTC)
	fim := time.Date(2026, 8, 1, 0, 0, 0, 0, time.UTC)
	sups := []rsup{
		{ID: "T", Razao: "BRILHO LIMPEZA", Tipo: "TERCEIRIZADA", Status: "ATIVO", Fim: &fim},
		{ID: "F", Razao: "PAPELARIA CENTRAL", Tipo: "FORNECEDOR", Status: "ATIVO"},
		{ID: "X", Razao: "ANTIGA LTDA", Tipo: "TERCEIRIZADA", Status: "INATIVO"},
	}
	emps := []remp{{ID: "e1", Status: "ATIVO", Sup: "T"}, {ID: "e2", Status: "DESLIGADO", Sup: "T"}}
	docs := []rdoc{
		{ID: "h", Emp: "e1", Sup: "T", Tipo: "HOLERITE", Comp: "2026-09", Status: "AUTO_APROVADO", Origem: "IA"},
		{ID: "ct", Sup: "T", Tipo: "CONTRATO_PRESTACAO_SERVICO", Status: "AUTO_APROVADO", Origem: "MANUAL"}, // digitado: não comprova
		{ID: "ai", Sup: "T", Tipo: "AUTO_INFRACAO", Status: "AGUARDANDO_REVISAO", Origem: "IA"},
		{ID: "pj", Sup: "T", Tipo: "PROCESSO_JUDICIAL", Status: "AUTO_APROVADO", Origem: "IA"},
		{ID: "ra", Sup: "T", Tipo: "RELATORIO_AUDITORIA", Status: "AUTO_APROVADO", Origem: "IA", Campos: map[string]any{"nivel_risco": "alto"}},
		{ID: "ra2", Sup: "F", Tipo: "RELATORIO_AUDITORIA", Status: "AUTO_APROVADO", Origem: "IA", Campos: map[string]any{"nivel_risco": "BAIXO"}},
	}
	got := map[string]int{}
	for _, r := range deriveSupplierRisks(sups, emps, docs, now) {
		got[r.Sup+":"+r.Codigo]++
	}
	for _, want := range []string{"T:FORN_CONTRATO_AUSENTE", "T:FORN_CERTIDAO_AUSENTE", "T:FORN_GUIA_FGTS_AUSENTE", "T:FORN_AUTUACAO", "T:FORN_PROCESSO_JUDICIAL", "T:FORN_AUDITORIA_RISCO_ALTO", "F:FORN_CONTRATO_AUSENTE"} {
		if got[want] == 0 {
			t.Errorf("faltou o indicador %s; obtidos: %v", want, got)
		}
	}
	if got["T:FORN_CERTIDAO_AUSENTE"] != 3 {
		t.Errorf("devia cobrar CRF, CNDT e CND (3), veio %d", got["T:FORN_CERTIDAO_AUSENTE"])
	}
	if got["F:FORN_CERTIDAO_AUSENTE"] != 0 || got["F:FORN_GUIA_FGTS_AUSENTE"] != 0 {
		t.Error("fornecedor sem empregados alocados não deve ser cobrado por certidões trabalhistas nem guias mensais")
	}
	if got["F:FORN_AUDITORIA_RISCO_ALTO"] != 0 {
		t.Error("auditoria de risco baixo não gera indicador")
	}
	for k := range got {
		if len(k) > 1 && k[:2] == "X:" {
			t.Errorf("fornecedor inativo não gera indicadores: %s", k)
		}
	}

	// com a documentação completa e com imagem, os indicadores de ausência somem; contrato vencido com ativos aparece
	docs = append(docs[:1:1],
		rdoc{ID: "ct2", Sup: "T", Tipo: "CONTRATO_PRESTACAO_SERVICO", Status: "AUTO_APROVADO", Origem: "IA"},
		rdoc{ID: "c1", Sup: "T", Tipo: "CRF_FGTS", Status: "AUTO_APROVADO", Origem: "IA"}, rdoc{ID: "c2", Sup: "T", Tipo: "CNDT", Status: "AUTO_APROVADO", Origem: "IA"},
		rdoc{ID: "c3", Sup: "T", Tipo: "CND_FEDERAL", Status: "AUTO_APROVADO", Origem: "IA"},
		rdoc{ID: "g", Sup: "T", Tipo: "GUIA_FGTS", Comp: "2026-09", Status: "AUTO_APROVADO", Origem: "IA"})
	got = map[string]int{}
	for _, r := range deriveSupplierRisks(sups[:1], emps, docs, now) {
		got[r.Codigo]++
	}
	if len(got) != 1 || got["FORN_CONTRATO_VENCIDO"] != 1 {
		t.Errorf("com tudo em dia só o contrato vencido deve aparecer: %v", got)
	}
}

func TestFornecedorComTrabalhadoresAlocadosEhCobradoComoTerceirizada(t *testing.T) {
	now := time.Date(2026, 11, 6, 0, 0, 0, 0, time.UTC)
	sups := []rsup{{ID: "F1", Razao: "SEM TRABALHADORES", Tipo: "FORNECEDOR", Status: "ATIVO"}, {ID: "F2", Razao: "COM TRABALHADORES", Tipo: "FORNECEDOR", Status: "ATIVO"}}
	emps := []remp{{ID: "e1", Status: "ATIVO", Sup: "F2"}}
	docs := []rdoc{{ID: "h", Emp: "e1", Sup: "F2", Tipo: "HOLERITE", Comp: "2026-09", Status: "AUTO_APROVADO", Origem: "IA"}}
	got := map[string]int{}
	for _, r := range deriveSupplierRisks(sups, emps, docs, now) {
		got[r.Sup+":"+r.Codigo]++
	}
	if got["F1:FORN_CERTIDAO_AUSENTE"] != 0 || got["F1:FORN_GUIA_FGTS_AUSENTE"] != 0 {
		t.Errorf("fornecedor sem trabalhadores não deve ser cobrado por certidões e guias: %v", got)
	}
	if got["F2:FORN_CERTIDAO_AUSENTE"] != 3 || got["F2:FORN_GUIA_FGTS_AUSENTE"] != 1 {
		t.Errorf("fornecedor com trabalhador alocado deve ser cobrado (3 certidões e a guia de 2026-09): %v", got)
	}
}
