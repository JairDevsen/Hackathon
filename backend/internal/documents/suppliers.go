package documents

import (
	"context"
	"strings"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/cnpj"
	"github.com/jackc/pgx/v5"
)

// Fornecedores e terceirizadas: o CNPJ da empresa lida no documento agrupa documentos, funcionários, conformidade e
// riscos da contratante. Documentos com o CNPJ da própria empresa (tenant) ficam sem fornecedor.

// supplierCNPJ devolve o CNPJ válido (14 dígitos) da empresa do documento, ou "" se não houver.
func supplierCNPJ(campos map[string]any) string {
	for _, k := range []string{"empresa_cnpj", "cnpj"} {
		if c := cnpj.Clean(str(campos, k)); len(c) == 14 && cnpj.Valid(c) {
			return c
		}
	}
	return ""
}

// ResolveSupplier acha o fornecedor pelo CNPJ do documento. Se não existe e `auto` está ligado, cria um pré-cadastro
// (origem informada) para o RH completar. Devolve nil quando o documento não traz CNPJ válido ou é da própria empresa.
func (i *Ingestor) ResolveSupplier(ctx context.Context, tx pgx.Tx, tenantID string, campos map[string]any, auto bool, origem string) (id *string, created bool, err error) {
	c := supplierCNPJ(campos)
	if c == "" {
		return nil, false, nil
	}
	var own bool
	if err := tx.QueryRow(ctx, `SELECT regexp_replace(cnpj,'[^0-9]','','g')=$2 FROM tenants WHERE id=$1`, tenantID, c).Scan(&own); err != nil {
		return nil, false, err
	}
	if own {
		return nil, false, nil
	}
	nome := strings.ToUpper(str(campos, "empresa_nome"))
	var sid, razao string
	var pre bool
	switch err := tx.QueryRow(ctx, `SELECT id::text, razao_social, pre_cadastro FROM suppliers WHERE tenant_id=$1 AND cnpj=$2`, tenantID, c).Scan(&sid, &razao, &pre); err {
	case nil:
		if pre && strings.HasPrefix(razao, "CNPJ ") && nome != "" { // o nome só apareceu num documento posterior
			if _, err := tx.Exec(ctx, `UPDATE suppliers SET razao_social=$2, atualizado_em=now() WHERE id=$1`, sid, nome); err != nil {
				return nil, false, err
			}
		}
		return &sid, false, nil
	case pgx.ErrNoRows:
	default:
		return nil, false, err
	}
	if !auto {
		return nil, false, nil
	}
	if nome == "" {
		nome = "CNPJ " + c
	}
	err = tx.QueryRow(ctx, `INSERT INTO suppliers (tenant_id, cnpj, razao_social, pre_cadastro, origem) VALUES ($1,$2,$3,true,$4)
	  ON CONFLICT (tenant_id, cnpj) DO NOTHING RETURNING id::text`, tenantID, c, nome, origem).Scan(&sid)
	if err == pgx.ErrNoRows { // outro processo criou no mesmo instante
		if err := tx.QueryRow(ctx, `SELECT id::text FROM suppliers WHERE tenant_id=$1 AND cnpj=$2`, tenantID, c).Scan(&sid); err != nil {
			return nil, false, err
		}
		return &sid, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	return &sid, true, nil
}

// reassignSupplier refaz a ligação do documento com o fornecedor depois que o revisor corrigiu o CNPJ nos campos.
func (i *Ingestor) reassignSupplier(ctx context.Context, tx pgx.Tx, tenantID, docID string, campos map[string]any) error {
	if supplierCNPJ(campos) == "" {
		return nil
	}
	var auto bool
	if err := tx.QueryRow(ctx, `SELECT pre_cadastro_automatico FROM tenants WHERE id=$1`, tenantID).Scan(&auto); err != nil {
		return err
	}
	sid, _, err := i.ResolveSupplier(ctx, tx, tenantID, campos, auto, "REVISAO")
	if err != nil {
		return err
	}
	_, err = tx.Exec(ctx, `UPDATE documents SET supplier_id=$2 WHERE id=$1`, docID, sid)
	return err
}

// documentSupplier devolve o fornecedor do documento (nulo se for da própria empresa).
func documentSupplier(ctx context.Context, tx pgx.Tx, docID string) *string {
	var s *string
	tx.QueryRow(ctx, `SELECT supplier_id::text FROM documents WHERE id=$1`, docID).Scan(&s)
	return s
}
