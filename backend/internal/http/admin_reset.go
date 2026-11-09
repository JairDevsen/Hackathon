package http

import (
	"context"
	"log/slog"
	"strings"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// FraseReset é o que o Master precisa digitar para confirmar o reset (evita clique acidental e chamada de API sem querer).
const FraseReset = "RESETAR TUDO"

// resetCounts: o que existia numa empresa antes do reset (vai para a resposta e para a auditoria).
type resetCounts struct {
	Empresa       string `json:"empresa"`
	Funcionarios  int    `json:"funcionarios"`
	Fornecedores  int    `json:"fornecedores"`
	Lotes         int    `json:"lotes"`
	Paginas       int    `json:"paginas"`
	Documentos    int    `json:"documentos"`
	Riscos        int    `json:"riscos"`
	Pendencias    int    `json:"pendencias"`
	BytesLiberado int64  `json:"bytes_liberados"`
}

// POST /admin/reset  {"confirmar":"RESETAR TUDO","motivo":"...","tenant_id":""}  — só MASTER, com código de verificação (step-up).
//
// Apaga os DADOS de todas as empresas (ou de uma só, com tenant_id): funcionários, terceirizadas e fornecedores, lotes, páginas,
// documentos (com revisões), indicadores de risco, pendências, notificações e TODOS os arquivos guardados. Zera o espaço usado.
// Mantém: as empresas e seus usuários (admins e RH), a configuração (unidades, cargos, setores, documentos obrigatórios,
// retenção, cadastro), planos, faturas, consumo mensal já contabilizado e a trilha de auditoria (que registra o reset).
// Recusa se houver lote em processamento: o reset no meio dele deixaria o worker gravando sobre dados apagados.
func (s *Server) adminReset(c *gin.Context) {
	var in struct {
		Confirmar string `json:"confirmar"`
		Motivo    string `json:"motivo"`
		TenantID  string `json:"tenant_id"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if strings.TrimSpace(in.Confirmar) != FraseReset {
		problem.Write(c, problem.BadRequest("confirmação inválida: digite exatamente "+FraseReset))
		return
	}
	motivo := strings.TrimSpace(in.Motivo)
	if len([]rune(motivo)) < 5 {
		problem.Write(c, problem.BadRequest("informe o motivo do reset (mín. 5 caracteres): ele fica na auditoria"))
		return
	}
	var tenants []resetCounts
	var ids []string
	if !s.sys(c, func(ctx context.Context, tx pgx.Tx) error {
		q := `SELECT id::text, coalesce(nome_fantasia, razao_social) FROM tenants`
		args := []any{}
		if in.TenantID != "" {
			q += ` WHERE id=$1::uuid`
			args = append(args, in.TenantID)
		}
		rows, err := tx.Query(ctx, q+` ORDER BY 2 FOR UPDATE`, args...)
		if err != nil {
			return err
		}
		for rows.Next() {
			var id, nome string
			if err := rows.Scan(&id, &nome); err != nil {
				rows.Close()
				return err
			}
			ids = append(ids, id)
			tenants = append(tenants, resetCounts{Empresa: nome})
		}
		rows.Close()
		if in.TenantID != "" && len(ids) == 0 {
			return problem.NotFound("empresa não encontrada")
		}
		var andamento int
		if err := tx.QueryRow(ctx, `SELECT count(*) FROM batches WHERE tenant_id = ANY($1::uuid[]) AND status IN ('RECEBIDO','PROCESSANDO')`, ids).Scan(&andamento); err != nil {
			return err
		}
		if andamento > 0 {
			return problem.Conflict("há lote em processamento: aguarde terminar (ou falhar) antes de resetar")
		}
		for i, id := range ids {
			t := &tenants[i]
			for _, x := range []struct {
				dst *int
				sql string
			}{
				{&t.Funcionarios, `SELECT count(*) FROM employees WHERE tenant_id=$1`}, {&t.Fornecedores, `SELECT count(*) FROM suppliers WHERE tenant_id=$1`},
				{&t.Lotes, `SELECT count(*) FROM batches WHERE tenant_id=$1`}, {&t.Paginas, `SELECT count(*) FROM pages WHERE tenant_id=$1`},
				{&t.Documentos, `SELECT count(*) FROM documents WHERE tenant_id=$1`}, {&t.Riscos, `SELECT count(*) FROM risk_indicators WHERE tenant_id=$1`},
				{&t.Pendencias, `SELECT count(*) FROM compliance_items WHERE tenant_id=$1 AND status IN ('PENDENTE','VENCIDO','A_VENCER')`},
			} {
				if err := tx.QueryRow(ctx, x.sql, id).Scan(x.dst); err != nil {
					return err
				}
			}
			if err := tx.QueryRow(ctx, `SELECT bytes_usados FROM tenants WHERE id=$1`, id).Scan(&t.BytesLiberado); err != nil {
				return err
			}
			// ordem: o que depende de documento/funcionário/fornecedor sai primeiro
			for _, sql := range []string{
				`DELETE FROM risk_indicators WHERE tenant_id=$1`,
				`DELETE FROM compliance_items WHERE tenant_id=$1`,
				`DELETE FROM reviews WHERE tenant_id=$1`,
				`DELETE FROM documents WHERE tenant_id=$1`, // as referências entre documentos (substituição, duplicata) saem na mesma instrução
				`DELETE FROM ia_callbacks WHERE batch_id IN (SELECT id FROM batches WHERE tenant_id=$1)`,
				`DELETE FROM batches WHERE tenant_id=$1`, // páginas e dead letters saem em cascata
				`DELETE FROM employees WHERE tenant_id=$1`,
				`DELETE FROM suppliers WHERE tenant_id=$1`,
				`DELETE FROM notifications WHERE tenant_id=$1`,
				`UPDATE tenants SET bytes_usados=0 WHERE id=$1`,
			} {
				if _, err := tx.Exec(ctx, sql, id); err != nil {
					return err
				}
			}
			tx.Exec(ctx, `INSERT INTO storage_events (tenant_id, tipo, bytes, objeto, por) VALUES ($1,'EXCLUSAO',$2,$3,$4)`, id, t.BytesLiberado, id+"/", auth.ClaimsOf(c).Subject)
			// pendências obrigatórias da própria empresa (sem funcionário nem fornecedor) voltam a ser calculadas como numa empresa nova
			if err := compliance.Recompute(ctx, tx, id, ""); err != nil {
				return err
			}
			if err := s.masterAudit(ctx, tx, c, id, "DADOS_RESETADOS", "tenant", id, map[string]any{"motivo": motivo, "apagado": *t}); err != nil {
				return err
			}
		}
		return nil
	}) {
		return
	}
	// os arquivos saem depois do commit; se falhar, sobram objetos cifrados sem referência no banco (nunca dado visível)
	removidos, falhas := 0, 0
	for _, id := range ids {
		n, err := s.Vault.DeleteTenantFiles(c.Request.Context(), id)
		removidos += n
		if err != nil {
			falhas++
			slog.Error("reset: dados apagados no banco, mas a remoção dos arquivos falhou", "tenant_id", id, "erro", err)
		}
	}
	tot := resetCounts{Empresa: "total"}
	for _, t := range tenants {
		tot.Funcionarios += t.Funcionarios
		tot.Fornecedores += t.Fornecedores
		tot.Lotes += t.Lotes
		tot.Paginas += t.Paginas
		tot.Documentos += t.Documentos
		tot.Riscos += t.Riscos
		tot.Pendencias += t.Pendencias
		tot.BytesLiberado += t.BytesLiberado
	}
	c.JSON(200, gin.H{"empresas": len(ids), "total": tot, "por_empresa": tenants, "arquivos_removidos": removidos, "empresas_com_falha_nos_arquivos": falhas})
}
