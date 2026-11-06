package http

import (
	"context"
	"errors"
	"log/slog"
	"strings"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// DELETE /batches/:id  {"confirmar": true, "motivo": "..."} — apaga o lote enviado e tudo que veio dele.
//
// Remove: o lote, suas páginas, os documentos extraídos (com revisões, indicadores de risco e itens ligados a eles) e os
// arquivos (original, páginas, miniaturas e PDFs gerados). Devolve os bytes à cota e recalcula conformidade e riscos.
// Mantém: funcionários e fornecedores criados a partir do lote (podem ter outros documentos), o consumo de páginas já
// contabilizado no mês e a trilha de auditoria (que registra quem apagou, quando e por quê).
// Só vale para lote terminado (processado ou falho): lote em andamento é recusado.
func (s *Server) deleteBatch(c *gin.Context) {
	var in struct {
		Confirmar bool   `json:"confirmar"`
		Motivo    string `json:"motivo"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if !in.Confirmar {
		problem.Write(c, problem.BadRequest("confirme a exclusão: a ação é definitiva e não pode ser desfeita"))
		return
	}
	motivo := strings.TrimSpace(in.Motivo)
	if len([]rune(motivo)) < 5 {
		problem.Write(c, problem.BadRequest("informe o motivo da exclusão (mín. 5 caracteres): ele fica na auditoria"))
		return
	}
	id, tenant, user := c.Param("id"), tid(c), auth.ClaimsOf(c).Subject
	var docs, pages int
	var freed int64
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var status, arquivo, sha string
		err := tx.QueryRow(ctx, `SELECT status, arquivo_original, sha256 FROM batches WHERE id=$1 FOR UPDATE`, id).Scan(&status, &arquivo, &sha)
		if errors.Is(err, pgx.ErrNoRows) {
			return problem.NotFound("lote não encontrado")
		}
		if err != nil {
			return err
		}
		if status == "RECEBIDO" || status == "PROCESSANDO" {
			return problem.Conflict("o lote ainda está sendo processado: aguarde terminar (ou falhar) para apagar")
		}
		tx.QueryRow(ctx, `SELECT count(*) FROM documents WHERE batch_id=$1`, id).Scan(&docs)
		tx.QueryRow(ctx, `SELECT count(*) FROM pages WHERE batch_id=$1`, id).Scan(&pages)
		// documentos de outros lotes que este lote havia substituído voltam a valer
		if _, err := tx.Exec(ctx, `UPDATE documents SET status='REVISADO', atualizado_em=now()
		  WHERE status='SUBSTITUIDO' AND batch_id IS DISTINCT FROM $1 AND id IN (SELECT substitui_id FROM documents WHERE batch_id=$1 AND substitui_id IS NOT NULL)`, id); err != nil {
			return err
		}
		// referências de fora para documentos que vão sair (substituição e duplicidade)
		for _, col := range []string{"substitui_id", "duplicata_de"} {
			if _, err := tx.Exec(ctx, `UPDATE documents SET `+col+`=NULL WHERE batch_id IS DISTINCT FROM $1 AND `+col+` IN (SELECT id FROM documents WHERE batch_id=$1)`, id); err != nil {
				return err
			}
		}
		prefix := tenant + "/" + id + "/"
		if err := tx.QueryRow(ctx, `SELECT coalesce(sum(bytes),0) FROM storage_events WHERE tenant_id=$1 AND tipo IN ('UPLOAD','DERIVADO') AND (objeto LIKE $2 OR objeto=$3)`,
			tenant, prefix+"%", id).Scan(&freed); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `DELETE FROM documents WHERE batch_id=$1`, id); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx, `DELETE FROM batches WHERE id=$1`, id); err != nil { // páginas saem em cascata
			return err
		}
		if _, err := tx.Exec(ctx, `UPDATE tenants SET bytes_usados=greatest(bytes_usados-$2,0) WHERE id=$1`, tenant, freed); err != nil {
			return err
		}
		tx.Exec(ctx, `INSERT INTO storage_events (tenant_id, tipo, bytes, objeto, por) VALUES ($1,'EXCLUSAO',$2,$3,$4)`, tenant, freed, prefix, user)
		tx.Exec(ctx, `DELETE FROM notifications WHERE link=$1`, "/lotes/"+id)
		if err := compliance.Recompute(ctx, tx, tenant, ""); err != nil { // pendências e indicadores deixam de contar o que saiu
			return err
		}
		return s.audit(ctx, tx, c, "LOTE_EXCLUIDO", "batch", id, map[string]any{"arquivo": arquivo, "sha256": sha, "motivo": motivo, "documentos": docs, "paginas": pages, "bytes_liberados": freed})
	}) {
		return
	}
	// os arquivos saem depois do commit; se falhar, sobram objetos cifrados órfãos (sem referência no banco), só para limpar depois
	removidos, err := s.Vault.DeleteBatch(c.Request.Context(), tenant, id)
	if err != nil {
		slog.Error("lote apagado no banco, mas a remoção dos arquivos falhou", "batch", id, "tenant_id", tenant, "erro", err)
	}
	c.JSON(200, gin.H{"documentos": docs, "paginas": pages, "arquivos_removidos": removidos, "bytes_liberados": freed, "arquivos_com_falha": err != nil})
}
