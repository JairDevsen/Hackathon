package documents

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/internal/ocrseal"
	"github.com/jackc/pgx/v5"
)

// BackfillOCR cifra o texto lido (OCR) que ainda está em claro no banco, de lotes processados antes da criptografia, e
// apaga as colunas em claro. É idempotente: sem nada a fazer, só confere e termina. Roda na subida da API.
func (i *Ingestor) BackfillOCR(ctx context.Context, db *database.DB) error {
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
	docs, pages := 0, 0
	for _, t := range tenants {
		d, p, err := i.backfillTenant(ctx, db, t)
		if err != nil {
			return fmt.Errorf("empresa %s: %w", t, err)
		}
		docs, pages = docs+d, pages+p
	}
	if docs+pages > 0 {
		slog.Info("texto lido (OCR) cifrado", "documentos", docs, "paginas", pages)
	}
	return nil
}

const lote = 200

func (i *Ingestor) backfillTenant(ctx context.Context, db *database.DB, tenantID string) (docs, pages int, err error) {
	for { // documentos
		var n int
		err = db.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
			sl, e := ocrseal.ForTx(ctx, tx, i.KR, tenantID)
			if e != nil {
				return e
			}
			rows, e := tx.Query(ctx, `SELECT id::text, texto_ocr FROM documents WHERE texto_ocr <> '' AND texto_ocr_cifrado IS NULL LIMIT $1`, lote)
			if e != nil {
				return e
			}
			type item struct{ id, texto string }
			var itens []item
			for rows.Next() {
				var it item
				if e := rows.Scan(&it.id, &it.texto); e != nil {
					rows.Close()
					return e
				}
				itens = append(itens, it)
			}
			rows.Close()
			for _, it := range itens {
				c, e := sl.Text(ocrseal.Texto, it.texto)
				if e != nil {
					return e
				}
				if _, e := tx.Exec(ctx, `UPDATE documents SET texto_ocr_cifrado=$2, texto_ocr='' WHERE id=$1`, it.id, c); e != nil {
					return e
				}
			}
			n = len(itens)
			return nil
		})
		if err != nil {
			return
		}
		docs += n
		if n < lote {
			break
		}
	}
	for { // páginas: texto embutido, palavras com posição e análise
		var n int
		err = db.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
			sl, e := ocrseal.ForTx(ctx, tx, i.KR, tenantID)
			if e != nil {
				return e
			}
			rows, e := tx.Query(ctx, `SELECT batch_id::text, numero, coalesce(texto_embutido,''), palavras::text, analise FROM pages
			  WHERE coalesce(texto_embutido,'') <> '' OR palavras <> '[]'::jsonb OR (analise IS NOT NULL AND NOT analise ? 'enc' AND (analise ? 'texto_ocr' OR analise ? 'campos'))
			  LIMIT $1`, lote)
			if e != nil {
				return e
			}
			type item struct {
				batch           string
				numero          int
				texto, palavras string
				analise         []byte
			}
			var itens []item
			for rows.Next() {
				var it item
				if e := rows.Scan(&it.batch, &it.numero, &it.texto, &it.palavras, &it.analise); e != nil {
					rows.Close()
					return e
				}
				itens = append(itens, it)
			}
			rows.Close()
			for _, it := range itens {
				tc, e := sl.Text(ocrseal.Nativo, it.texto)
				if e != nil {
					return e
				}
				var pc []byte
				if len(it.palavras) > 2 {
					if pc, e = sl.Text(ocrseal.Palavra, it.palavras); e != nil {
						return e
					}
				}
				an, e := sl.ProtectAnalise(it.analise)
				if e != nil {
					return e
				}
				if _, e := tx.Exec(ctx, `UPDATE pages SET texto_cifrado=coalesce($3, texto_cifrado), texto_len=greatest(texto_len, $4), palavras_cifradas=coalesce($5, palavras_cifradas),
				    texto_embutido=NULL, palavras='[]'::jsonb, analise=$6 WHERE batch_id=$1 AND numero=$2`, it.batch, it.numero, tc, len(it.texto), pc, an); e != nil {
					return e
				}
			}
			n = len(itens)
			return nil
		})
		if err != nil {
			return
		}
		pages += n
		if n < lote {
			break
		}
	}
	return
}
