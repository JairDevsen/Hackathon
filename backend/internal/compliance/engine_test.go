package compliance

import (
	"testing"
	"time"
)

func TestEvaluate(t *testing.T) {
	now := time.Date(2026, 11, 5, 0, 0, 0, 0, time.Local)
	val := 365
	d := func(days int) *doc { x := now.AddDate(0, 0, days); return &doc{ID: "d", DataDoc: &x, Criado: x} }
	if s, _, _ := evaluate(nil, &val, 30, now); s != "PENDENTE" {
		t.Fatal("sem documento deve ser PENDENTE")
	}
	if s, _, _ := evaluate(d(-400), &val, 30, now); s != "VENCIDO" {
		t.Fatal("ASO de 400 dias deve estar VENCIDO")
	}
	if s, _, _ := evaluate(d(-345), &val, 30, now); s != "A_VENCER" {
		t.Fatal("vence em 20 dias deve ser A_VENCER")
	}
	if s, _, _ := evaluate(d(-10), &val, 30, now); s != "OK" {
		t.Fatal("recente deve estar OK")
	}
}

func TestBuildMensalAndPick(t *testing.T) {
	now := time.Date(2026, 11, 5, 0, 0, 0, 0, time.Local)
	adm := time.Date(2026, 8, 10, 0, 0, 0, 0, time.Local)
	pos := "p1"
	reqs := pick([]req{
		{ID: "r1", DocType: "HOLERITE", Momento: "MENSAL", Obrigatorio: true},
		{ID: "r2", DocType: "FICHA_EPI", Momento: "ADMISSAO", Obrigatorio: true},
		{ID: "r3", DocType: "FICHA_EPI", Momento: "ADMISSAO", Obrigatorio: false, PositionID: &pos}, // cargo dispensa EPI
	}, &pos, nil, nil)
	if len(reqs) != 1 || reqs[0].DocType != "HOLERITE" {
		t.Fatalf("a regra do cargo deve dispensar o EPI: %+v", reqs)
	}
	items := build(reqs, map[string][]*doc{"HOLERITE": {{ID: "h", Competencia: "2026-09", Criado: now}}}, &adm, nil, now)
	// ago, set, out (novembro ainda não encerrou)
	if len(items) != 3 {
		t.Fatalf("esperava 3 competências, veio %d", len(items))
	}
	got := map[string]string{}
	for _, it := range items {
		got[it.Ref] = it.Status
	}
	if got["2026-09"] != "OK" || got["2026-08"] != "PENDENTE" || got["2026-10"] != "PENDENTE" {
		t.Fatalf("status mensal incorreto: %v", got)
	}
}

func TestPrecedenciaFuncionarioCargoSetorTodos(t *testing.T) {
	s := func(x string) *string { return &x }
	cargo, setor, emp := s("c1"), s("s1"), s("e1")
	reqs := []req{
		{ID: "geral", DocType: "FICHA_EPI", Momento: "ADMISSAO", Obrigatorio: true},                      // todos
		{ID: "setor", DocType: "FICHA_EPI", Momento: "ADMISSAO", Obrigatorio: true, DepartmentID: setor}, // setor exige
		{ID: "cargo", DocType: "ASO", Momento: "PERIODICO", Obrigatorio: true, PositionID: cargo},
		{ID: "dispensa", DocType: "FICHA_EPI", Momento: "ADMISSAO", Obrigatorio: false, EmployeeID: emp}, // exceção do funcionário
		{ID: "outro", DocType: "ASO", Momento: "PERIODICO", Obrigatorio: false, EmployeeID: s("e2")},     // exceção de OUTRO funcionário
	}
	got := map[string]string{}
	for _, r := range pick(reqs, cargo, setor, emp) {
		got[r.DocType] = r.ID
	}
	if _, ok := got["FICHA_EPI"]; ok {
		t.Fatalf("a dispensa do funcionário deve vencer cargo/setor/geral: %v", got)
	}
	if got["ASO"] != "cargo" {
		t.Fatalf("a exceção de outro funcionário não pode afetar este: %v", got)
	}
	// outro funcionário do mesmo setor continua obrigado pelo setor
	other := s("e3")
	got2 := map[string]string{}
	for _, r := range pick(reqs, nil, setor, other) {
		got2[r.DocType] = r.ID
	}
	if got2["FICHA_EPI"] != "setor" {
		t.Fatalf("o setor deve prevalecer sobre o geral: %v", got2)
	}
	// sem setor/cargo, nada específico: só a regra geral
	got3 := pick(reqs, nil, nil, other)
	if len(got3) != 1 || got3[0].ID != "geral" {
		t.Fatalf("sem setor/cargo vale só a regra geral: %+v", got3)
	}
	// nenhum requisito => nada a cobrar (empresa que ainda não configurou não recebe acusações)
	if len(pick(nil, cargo, setor, emp)) != 0 {
		t.Fatal("sem regras configuradas não deve haver exigência")
	}
}

func TestSemAdmissaoNaoInventaMesesDePendencia(t *testing.T) {
	now := time.Date(2026, 11, 5, 0, 0, 0, 0, time.Local)
	reqs := []req{{ID: "h", DocType: "HOLERITE", Momento: "MENSAL", Obrigatorio: true}}
	// pré-cadastro sem admissão e sem nenhum documento: nada a cobrar
	if got := build(reqs, map[string][]*doc{}, nil, nil, now); len(got) != 0 {
		t.Fatalf("sem admissão e sem documentos não deve haver pendência mensal: %+v", got)
	}
	// com um holerite de 2026-08: cobra de ago a out (3 competências), não 35 meses
	got := build(reqs, map[string][]*doc{"HOLERITE": {{ID: "x", Competencia: "2026-08", Criado: now}}}, nil, nil, now)
	if len(got) != 3 {
		t.Fatalf("esperava 3 competências (ago–out), veio %d: %+v", len(got), got)
	}
}
