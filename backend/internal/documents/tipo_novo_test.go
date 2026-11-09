package documents

import (
	"testing"

	"github.com/agreser-innovations/citadel-ia/backend/internal/iacore"
)

func TestValidarTipoNovo(t *testing.T) {
	ok := func(in iacore.TipoNovo) iacore.TipoNovo {
		t.Helper()
		out, valido := validarTipoNovo(&in)
		if !valido {
			t.Fatalf("esperava tipo válido: %+v", in)
		}
		return out
	}
	r := ok(iacore.TipoNovo{Codigo: "PROCURACAO", Nome: "  Procuração ", Escopo: "EMPRESA", Categoria: "MENSAL", Pistas: []string{"PROCURACAO PARTICULAR", "curta", "OUTORGANTE E OUTORGADO"}})
	if r.Nome != "Procuração" || r.Escopo != "EMPRESA" || r.Categoria != "EMPRESA" || len(r.Pistas) != 2 {
		t.Errorf("saneamento inesperado: %+v", r)
	}
	f := ok(iacore.TipoNovo{Codigo: "LAUDO_INSALUBRIDADE", Nome: "Laudo de insalubridade", Escopo: "?", Categoria: "INVENTADA"})
	if f.Escopo != "FUNCIONARIO" || f.Categoria != "OUTROS" || f.Pistas == nil {
		t.Errorf("valores desconhecidos devem cair no padrão: %+v", f)
	}
	for _, ruim := range []iacore.TipoNovo{
		{Codigo: "outro", Nome: "Outro tipo"},                              // código fora do padrão
		{Codigo: "OUTRO", Nome: "Outro"},                                   // OUTRO nunca é um tipo novo
		{Codigo: "AB", Nome: "Abc def"},                                    // código curto demais
		{Codigo: "CONTRATO_JOAO", Nome: "Contrato do João 123.456.789-00"}, // CPF no nome: é instância, não tipo
		{Codigo: "NF_12345678", Nome: "Nota 12345678"},                     // número longo
		{Codigo: "EMAIL", Nome: "Contato fulano@empresa.com"},              // e-mail
		{Codigo: "NOME_CURTO", Nome: "Abc"},                                // nome curto demais
	} {
		if _, valido := validarTipoNovo(&ruim); valido {
			t.Errorf("deveria recusar: %+v", ruim)
		}
	}
}
