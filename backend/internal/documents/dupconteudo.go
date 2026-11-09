package documents

import (
	"context"

	"github.com/jackc/pgx/v5"
)

// Duplicata de CONTEÚDO: o mesmo documento escaneado mais de uma vez, de formas diferentes (outra qualidade, inclinação,
// ruído), que o hash da imagem não reconhece. A decisão usa a similaridade do texto lido por OCR (ver similaridade.go) e
// só compara documentos que podem ser o mesmo: mesma pessoa/empresa, mesma competência, data e validade, e valores iguais.

// novoDoc: o documento que está sendo gravado.
type novoDoc struct {
	Tipo                 string
	Emp, Sup, CPFHash    *string
	Comp, Data, Validade string
	Texto                string
	Confianca            float64
}

// dupAchada: o documento já gravado que é o mesmo conteúdo.
type dupAchada struct {
	ID, Status, Batch string
	Confianca         float64
	Paginas           int
	SemFuncionario    bool
	Similaridade      float64
}

func igualOuVazio(a, b string) bool { return a == "" || b == "" || a == b }

func mesmoPonteiro(a, b *string) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

// podeSerOMesmo: as travas que não dependem do texto. Documentos de pessoas, empresas ou períodos diferentes nunca são duplicata,
// por mais parecido que seja o modelo.
func podeSerOMesmo(n novoDoc, emp, sup, cpf *string, comp, data, validade string) bool {
	if !mesmoPonteiro(n.Sup, sup) {
		return false
	}
	switch {
	case n.Emp != nil && emp != nil:
		if *n.Emp != *emp {
			return false
		}
	case n.Emp != nil || emp != nil: // um vinculado e o outro não: só se o CPF lido for o mesmo
		if n.CPFHash == nil || cpf == nil || *n.CPFHash != *cpf {
			return false
		}
	default:
		if n.CPFHash != nil && cpf != nil && *n.CPFHash != *cpf {
			return false
		}
	}
	return igualOuVazio(n.Comp, comp) && igualOuVazio(n.Data, data) && igualOuVazio(n.Validade, validade)
}

// acharDuplicataDeConteudo devolve o documento já gravado mais parecido (e acima do limite), ou nil.
func acharDuplicataDeConteudo(ctx context.Context, tx pgx.Tx, tenantID string, n novoDoc, limite float64) (*dupAchada, error) {
	if n.Texto == "" {
		return nil, nil
	}
	// O tipo NÃO entra na comparação: o mesmo documento escaneado pior pode ser lido como outro tipo (o OCR estraga o título). Texto
	// parecido + mesmos valores + mesma pessoa/empresa + mesma competência é o mesmo documento; fica a cópia de leitura mais confiável.
	rows, err := tx.Query(ctx, `SELECT id::text, status, confianca::float8, employee_id::text, supplier_id::text, cpf_extraido_hash, coalesce(competencia,''),
	    coalesce(data_documento::text,''), coalesce(validade_ate::text,''), batch_id::text, coalesce(array_length(paginas,1),0), texto_anonimizado
	  FROM documents WHERE tenant_id=$1 AND status IN ('AUTO_APROVADO','AGUARDANDO_REVISAO','REVISADO') AND texto_anonimizado <> ''
	    AND ($2::uuid IS NULL OR employee_id=$2::uuid OR employee_id IS NULL)
	  ORDER BY criado_em DESC LIMIT 300`, tenantID, n.Emp)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var melhor *dupAchada
	for rows.Next() {
		var d dupAchada
		var emp, sup, cpf *string
		var comp, data, validade, texto string
		var batch *string
		if err := rows.Scan(&d.ID, &d.Status, &d.Confianca, &emp, &sup, &cpf, &comp, &data, &validade, &batch, &d.Paginas, &texto); err != nil {
			return nil, err
		}
		if batch != nil {
			d.Batch = *batch
		}
		if !podeSerOMesmo(n, emp, sup, cpf, comp, data, validade) {
			continue
		}
		c := Comparar(n.Texto, texto)
		if !c.Duplicado(limite) {
			continue
		}
		if melhor == nil || c.Texto > melhor.Similaridade {
			d.Similaridade, d.SemFuncionario = c.Texto, emp == nil
			melhor = &d
		}
	}
	return melhor, rows.Err()
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
