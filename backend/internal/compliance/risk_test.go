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
