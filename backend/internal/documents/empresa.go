package documents

import (
	"context"
	"regexp"
	"strings"
	"unicode"

	"log/slog"

	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cnpj"
	"github.com/jackc/pgx/v5"
	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

// Identidade da empresa lida no documento.
//
// O mesmo empregador aparece escrito de jeitos diferentes: "Aparecida Limpeza Soluções Ltda", "APARECIDA LIMPEZA SOLUCOES
// LTDA", "APARECIDA LIMPEZA DOMÉSTICA" (nome de fantasia ou leitura diferente). Quando o CNPJ é lido, ele agrupa (fornecedor).
// Sem CNPJ, é preciso decidir pelo nome. Estas funções reduzem o nome a uma chave comparável e decidem quando dois nomes
// são a mesma empresa, para que os documentos fiquem na mesma pasta e no mesmo grupo.

var sufixosSocietarios = map[string]bool{"LTDA": true, "ME": true, "EPP": true, "EIRELI": true, "SA": true, "CIA": true, "MEI": true, "SS": true, "LIMITADA": true}
var sociedadeAnonima = regexp.MustCompile(`\bS\s*[/.]\s*A\b\.?`)
var semAcento = transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)

// CompanyTokens: palavras do nome em maiúsculas, sem acento nem pontuação e sem o tipo societário (LTDA, ME, S/A...).
func CompanyTokens(nome string) []string {
	s, _, _ := transform.String(semAcento, strings.ToUpper(nome))
	s = sociedadeAnonima.ReplaceAllString(s, "SA") // "S/A" e "S.A." viram uma palavra só
	campos := strings.FieldsFunc(s, func(r rune) bool { return !unicode.IsLetter(r) && !unicode.IsDigit(r) })
	out := make([]string, 0, len(campos))
	for _, t := range campos {
		if !sufixosSocietarios[t] {
			out = append(out, t)
		}
	}
	return out
}

// CompanyKey é a chave de igualdade EXATA: mesmo nome, ignorando acento, caixa, pontuação e tipo societário.
func CompanyKey(nome string) string { return strings.Join(CompanyTokens(nome), " ") }

// SameCompanyAs decide se `nome` é a empresa `referencia` (usada para a empresa PRÓPRIA, cujo nome conhecemos pelo cadastro).
// É a mesma empresa se as chaves são iguais, ou se começam pela mesma palavra e compartilham pelo menos duas palavras
// ("APARECIDA LIMPEZA DOMÉSTICA" × "Aparecida Limpeza Soluções Ltda"). A regra frouxa só vale contra a empresa do próprio
// cliente; entre empresas desconhecidas só a chave exata junta.
func SameCompanyAs(nome, referencia string) bool {
	a, b := CompanyTokens(nome), CompanyTokens(referencia)
	if len(a) == 0 || len(b) == 0 {
		return false
	}
	if strings.Join(a, " ") == strings.Join(b, " ") {
		return true
	}
	if a[0] != b[0] {
		return false
	}
	set := map[string]bool{}
	for _, t := range b {
		set[t] = true
	}
	comuns := 0
	for _, t := range a {
		if set[t] {
			comuns++
		}
	}
	return comuns >= 2
}

// ownCompanyName devolve o nome a gravar para um documento da PRÓPRIA empresa (sem fornecedor): o nome cadastrado, se o lido é
// a mesma empresa; senão, a grafia já usada em outro documento com a mesma chave; senão, o próprio nome lido.
func ownCompanyName(ctx context.Context, tx pgx.Tx, tenantID, lido string) (string, error) {
	if strings.TrimSpace(lido) == "" {
		return lido, nil
	}
	var razao string
	var fantasia *string
	if err := tx.QueryRow(ctx, `SELECT razao_social, nome_fantasia FROM tenants WHERE id=$1`, tenantID).Scan(&razao, &fantasia); err != nil {
		return lido, err
	}
	if SameCompanyAs(lido, razao) || (fantasia != nil && SameCompanyAs(lido, *fantasia)) {
		return razao, nil
	}
	rows, err := tx.Query(ctx, `SELECT DISTINCT campos->>'empresa_nome' FROM documents WHERE tenant_id=$1 AND supplier_id IS NULL AND coalesce(campos->>'empresa_nome','')<>'' ORDER BY 1 LIMIT 300`, tenantID)
	if err != nil {
		return lido, err
	}
	defer rows.Close()
	k := CompanyKey(lido)
	for rows.Next() {
		var outro string
		if err := rows.Scan(&outro); err != nil {
			return lido, err
		}
		if CompanyKey(outro) == k {
			return outro, nil
		}
	}
	return lido, rows.Err()
}

// supplierByName acha um fornecedor já cadastrado pelo NOME (chave exata), para documentos que não trazem CNPJ legível.
func supplierByName(ctx context.Context, tx pgx.Tx, tenantID, lido string) (*string, string, error) {
	k := CompanyKey(lido)
	if k == "" {
		return nil, "", nil
	}
	rows, err := tx.Query(ctx, `SELECT id::text, razao_social FROM suppliers WHERE tenant_id=$1`, tenantID)
	if err != nil {
		return nil, "", err
	}
	defer rows.Close()
	for rows.Next() {
		var id, razao string
		if err := rows.Scan(&id, &razao); err != nil {
			return nil, "", err
		}
		if CompanyKey(razao) == k {
			return &id, razao, nil
		}
	}
	return nil, "", rows.Err()
}

// NormalizeCompanyNames unifica, nos documentos já gravados, as grafias do nome da empresa própria (e da pasta de destino).
// Idempotente: documentos já normalizados (com `empresa_nome_lida`) ou sem diferença não são tocados. Roda na subida da API.
func (i *Ingestor) NormalizeCompanyNames(ctx context.Context, db *database.DB) error {
	var tenants []string
	if err := db.System(ctx, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT id::text FROM tenants`)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var id string
			if err := rows.Scan(&id); err != nil {
				return err
			}
			tenants = append(tenants, id)
		}
		return rows.Err()
	}); err != nil {
		return err
	}
	total := 0
	for _, t := range tenants {
		err := db.Tenant(ctx, t, func(tx pgx.Tx) error {
			type doc struct{ id, nome, cnpj string }
			rows, err := tx.Query(ctx, `SELECT id::text, campos->>'empresa_nome', coalesce(campos->>'empresa_cnpj','') FROM documents
			  WHERE tenant_id=$1 AND supplier_id IS NULL AND coalesce(campos->>'empresa_nome','')<>'' AND coalesce(campos->>'empresa_nome_lida','')='' ORDER BY criado_em`, t)
			if err != nil {
				return err
			}
			var docs []doc
			for rows.Next() {
				var d doc
				if err := rows.Scan(&d.id, &d.nome, &d.cnpj); err != nil {
					rows.Close()
					return err
				}
				docs = append(docs, d)
			}
			rows.Close()
			for _, d := range docs {
				novo, err := ownCompanyName(ctx, tx, t, d.nome)
				if err != nil {
					return err
				}
				if novo == d.nome {
					continue
				}
				pasta := slug(novo)
				if c := cnpj.Clean(d.cnpj); len(c) == 14 {
					pasta += "_" + c
				}
				if _, err := tx.Exec(ctx, `UPDATE documents SET campos = jsonb_set(jsonb_set(campos,'{empresa_nome_lida}', to_jsonb($2::text)),'{empresa_nome}', to_jsonb($3::text)),
				  pasta_destino = CASE WHEN position('/' in coalesce(pasta_destino,''))>0 THEN $4 || substr(pasta_destino, position('/' in pasta_destino)) ELSE pasta_destino END WHERE id=$1`,
					d.id, d.nome, novo, pasta); err != nil {
					return err
				}
				total++
			}
			return nil
		})
		if err != nil {
			return err
		}
	}
	if total > 0 {
		slog.Info("nomes da empresa unificados", "documentos", total)
	}
	return nil
}
