package documents

import "testing"

func TestMesmaEmpresaComNomesDiferentes(t *testing.T) {
	cadastro := "Aparecida Limpeza Soluções Ltda"
	for _, v := range []string{"APARECIDA LIMPEZA DOMÉSTICA", "APARECIDA LIMPEZA SOLUCOES LTDA", "Aparecida Limpeza Soluções Ltda", "APARECIDA LIMPEZA SOLUÇÕES LTDA", "Aparecida Limpeza Soluções", "aparecida limpeza solucoes ltda."} {
		if !SameCompanyAs(v, cadastro) {
			t.Errorf("%q deveria ser a mesma empresa que %q", v, cadastro)
		}
	}
	for _, v := range []string{"BRILHO LIMPEZA LTDA", "SEGURA VIGILANCIA LTDA", "Limpeza Aparecida", "APARECIDA", ""} {
		if SameCompanyAs(v, cadastro) {
			t.Errorf("%q NÃO deveria ser a mesma empresa que %q", v, cadastro)
		}
	}
}

func TestChaveIgnoraAcentoCaixaPontuacaoETipoSocietario(t *testing.T) {
	a := CompanyKey("Aparecida Limpeza Soluções Ltda")
	for _, v := range []string{"APARECIDA LIMPEZA SOLUCOES LTDA", "APARECIDA LIMPEZA SOLUÇÕES LTDA.", "aparecida  limpeza soluções", "Aparecida Limpeza Soluções S/A"} {
		if CompanyKey(v) != a {
			t.Errorf("chave de %q = %q, esperado %q", v, CompanyKey(v), a)
		}
	}
	if CompanyKey("Aparecida Limpeza Doméstica") == a {
		t.Error("nomes diferentes não podem ter a mesma chave exata")
	}
}
