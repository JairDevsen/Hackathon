// Package batches: recebimento de lotes (upload retomável), pipeline com checkpoint por página,
// callbacks do IA Core, retomada após falha, fila de mensagens mortas e eventos em tempo real (SSE).
package batches

import (
	"archive/zip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/internal/documents"
	"github.com/agreser-innovations/citadel-ia/backend/internal/iacore"
	"github.com/agreser-innovations/citadel-ia/backend/internal/storage"
	"github.com/hibiken/asynq"
	"github.com/jackc/pgx/v5"
	"github.com/redis/go-redis/v9"
)

const (
	TaskProcess  = "batch:process"
	MaxAttempts  = 3
	CamadaCache  = "Camada 0: Cache SHA-256 (0 Tokens - Instantâneo)"
	StallTimeout = 3 * time.Minute
)

type Service struct {
	Cfg    *config.Config
	DB     *database.DB
	Redis  *redis.Client
	Vault  *storage.Vault
	Signer *storage.Signer
	IA     *iacore.Client
	Ingest *documents.Ingestor
	Queue  *asynq.Client
	Stall  time.Duration
}

type TaskPayload struct {
	TenantID string `json:"tenant_id"`
	BatchID  string `json:"batch_id"`
	FailAt   int    `json:"fail_at,omitempty"` // simulação de queda (somente demonstração)
}

func (s *Service) stall() time.Duration {
	if s.Stall > 0 {
		return s.Stall
	}
	return StallTimeout
}

func (s *Service) Enqueue(p TaskPayload, delay time.Duration) error {
	b, _ := json.Marshal(p)
	opts := []asynq.Option{asynq.MaxRetry(0), asynq.Timeout(30 * time.Minute), asynq.Queue("default")}
	if delay > 0 {
		opts = append(opts, asynq.ProcessIn(delay))
	}
	_, err := s.Queue.Enqueue(asynq.NewTask(TaskProcess, b), opts...)
	return err
}

func timeline(ctx context.Context, tx pgx.Tx, batchID, tipo, msg string) {
	tx.Exec(ctx, `UPDATE batches SET linha_tempo = linha_tempo || jsonb_build_array(jsonb_build_object('quando', now(), 'tipo', $2::text, 'mensagem', $3::text)) WHERE id=$1`, batchID, tipo, msg)
}

// Snapshot: estado resumido do lote para a UI e para o SSE.
func Snapshot(ctx context.Context, tx pgx.Tx, batchID string) ([]byte, error) {
	return database.JSON(ctx, tx, `SELECT row_to_json(t) FROM (
	  SELECT b.id, b.status, b.total_paginas, b.tentativas, b.erro, b.versao, b.resumo,
	   (SELECT count(*) FROM pages p WHERE p.batch_id=b.id AND p.proc_status='OK') AS paginas_ok,
	   (SELECT count(*) FROM pages p WHERE p.batch_id=b.id AND p.proc_status='FALHOU') AS paginas_falhas,
	   (SELECT count(*) FROM documents d WHERE d.batch_id=b.id AND d.status<>'REJEITADO') AS documentos,
	   (SELECT count(*) FROM documents d WHERE d.batch_id=b.id AND d.status='AGUARDANDO_REVISAO') AS para_revisao
	  FROM batches b WHERE b.id=$1) t`, batchID)
}

func (s *Service) publish(ctx context.Context, tenantID, batchID, evento string) {
	s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		snap, err := Snapshot(ctx, tx, batchID)
		if err != nil {
			return nil
		}
		msg, _ := json.Marshal(map[string]any{"evento": evento, "lote": json.RawMessage(snap)})
		s.Redis.Publish(ctx, "batch:"+batchID, msg)
		return nil
	})
}

type batchRow struct {
	ID, TenantID, StorageKey, Filename, Status, TipoLote string
	UnitID                                               *string
	Versao, Tentativas, TotalPaginas                     int
}

func (s *Service) loadBatch(ctx context.Context, tx pgx.Tx, id string) (*batchRow, error) {
	var b batchRow
	err := tx.QueryRow(ctx, `SELECT id::text, tenant_id::text, storage_key, arquivo_original, status, tipo_lote, unit_id::text, versao, tentativas, total_paginas FROM batches WHERE id=$1`, id).
		Scan(&b.ID, &b.TenantID, &b.StorageKey, &b.Filename, &b.Status, &b.TipoLote, &b.UnitID, &b.Versao, &b.Tentativas, &b.TotalPaginas)
	return &b, err
}

// Process é o handler do job: fatia (se preciso) e despacha ao IA Core só o que falta (retomada).
func (s *Service) Process(ctx context.Context, p TaskPayload) error {
	var b *batchRow
	err := s.DB.Tenant(ctx, p.TenantID, func(tx pgx.Tx) error {
		var e error
		if b, e = s.loadBatch(ctx, tx, p.BatchID); e != nil {
			return e
		}
		if b.Status == "PROCESSADO" || b.Status == "PROCESSADO_COM_PENDENCIAS" {
			b = nil
			return nil
		}
		_, e = tx.Exec(ctx, `UPDATE batches SET status='PROCESSANDO', iniciado_em=coalesce(iniciado_em, now()), heartbeat_em=now(), erro=NULL WHERE id=$1`, b.ID)
		return e
	})
	if err != nil || b == nil {
		return err
	}
	if err := s.slicePagesIfNeeded(ctx, b); err != nil {
		return s.retryOrFail(ctx, b.TenantID, b.ID, "fatiamento: "+err.Error())
	}
	if err := s.dispatch(ctx, b, p.FailAt); err != nil {
		return s.retryOrFail(ctx, b.TenantID, b.ID, "IA Core: "+err.Error())
	}
	s.publish(ctx, b.TenantID, b.ID, "processando")
	return nil
}

type manifest struct {
	Paginas []struct {
		Numero        int             `json:"numero"`
		TextoEmbutido string          `json:"texto_embutido"`
		Captura       string          `json:"captura"`
		Largura       int             `json:"largura"`
		Altura        int             `json:"altura"`
		Caixas        json.RawMessage `json:"caixas"`
		Palavras      json.RawMessage `json:"palavras"`
	} `json:"paginas"`
}

func (s *Service) slicePagesIfNeeded(ctx context.Context, b *batchRow) error {
	var n int
	s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT count(*) FROM pages WHERE batch_id=$1`, b.ID).Scan(&n)
	})
	if n > 0 && n == b.TotalPaginas {
		return nil
	}
	url := s.Signer.URLFor(s.Cfg.InternalBaseURL, storage.Grant{Tenant: b.TenantID, Key: b.StorageKey}, 45*time.Minute)
	tmp := filepath.Join(os.TempDir(), "slice-"+b.ID+".zip")
	defer os.Remove(tmp)
	if err := s.IA.Slice(ctx, url, b.Filename, tmp); err != nil {
		return err
	}
	zr, err := zip.OpenReader(tmp)
	if err != nil {
		return fmt.Errorf("resposta de fatiamento inválida: %w", err)
	}
	defer zr.Close()
	files := map[string]*zip.File{}
	for _, f := range zr.File {
		files[f.Name] = f
	}
	mf, ok := files["manifest.json"]
	if !ok {
		return fmt.Errorf("manifest.json ausente")
	}
	rc, _ := mf.Open()
	var m manifest
	json.NewDecoder(rc).Decode(&m)
	rc.Close()
	if len(m.Paginas) == 0 {
		return fmt.Errorf("nenhuma página encontrada no arquivo")
	}
	// cota mensal de páginas
	var quotaErr error
	s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		var used, quota int
		tx.QueryRow(ctx, `SELECT coalesce((SELECT paginas FROM usage_monthly WHERE tenant_id=$1 AND mes=to_char(now(),'YYYY-MM')),0), quota_paginas_mes FROM tenants WHERE id=$1`, b.TenantID).Scan(&used, &quota)
		if used+len(m.Paginas) > quota && n == 0 {
			quotaErr = fmt.Errorf("cota mensal de páginas excedida (%d + %d > %d)", used, len(m.Paginas), quota)
		}
		return nil
	})
	if quotaErr != nil {
		s.failPermanent(ctx, b.TenantID, b.ID, quotaErr.Error(), "COTA")
		return nil
	}
	var derived int64
	newPages := 0
	for _, pg := range m.Paginas {
		key := fmt.Sprintf("%s/%s/pages/%04d.png", b.TenantID, b.ID, pg.Numero)
		tkey := fmt.Sprintf("%s/%s/thumbs/%04d.webp", b.TenantID, b.ID, pg.Numero)
		hash := ""
		for name, k := range map[string]string{fmt.Sprintf("pages/%04d.png", pg.Numero): key, fmt.Sprintf("thumbs/%04d.webp", pg.Numero): tkey} {
			f, ok := files[name]
			if !ok {
				if strings.HasPrefix(name, "thumbs") {
					tkey = ""
					continue
				}
				return fmt.Errorf("página %d ausente no fatiamento", pg.Numero)
			}
			r, _ := f.Open()
			var src io.Reader = r
			h := sha256.New()
			if strings.HasPrefix(name, "pages/") {
				src = io.TeeReader(r, h) // hash SHA-256 da página (Camada 0: cache por conteúdo)
			}
			nb, err := s.Vault.Put(ctx, b.TenantID, k, src)
			r.Close()
			if err != nil {
				return err
			}
			if strings.HasPrefix(name, "pages/") {
				hash = hex.EncodeToString(h.Sum(nil))
			}
			derived += nb
		}
		err := s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
			ct, err := tx.Exec(ctx, `INSERT INTO pages (tenant_id, batch_id, numero, storage_key, thumb_key, texto_embutido, captura, largura, altura, caixas, palavras, hash_sha256)
			  VALUES ($1,$2,$3,$4,nullif($5,''),$6,nullif($7,''),$8,$9,coalesce($10::jsonb,'[]'),coalesce($11::jsonb,'[]'),$12) ON CONFLICT (batch_id, numero) DO NOTHING`,
				b.TenantID, b.ID, pg.Numero, key, tkey, pg.TextoEmbutido, pg.Captura, pg.Largura, pg.Altura, nilIfEmpty(pg.Caixas), nilIfEmpty(pg.Palavras), hash)
			newPages += int(ct.RowsAffected())
			return err
		})
		if err != nil {
			return err
		}
	}
	return s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		tx.Exec(ctx, `UPDATE batches SET total_paginas=$2, heartbeat_em=now() WHERE id=$1`, b.ID, len(m.Paginas))
		tx.Exec(ctx, `UPDATE tenants SET bytes_usados=bytes_usados+$2 WHERE id=$1`, b.TenantID, derived)
		tx.Exec(ctx, `INSERT INTO storage_events (tenant_id, tipo, bytes, objeto) VALUES ($1,'DERIVADO',$2,$3)`, b.TenantID, derived, b.ID)
		tx.Exec(ctx, `INSERT INTO usage_monthly (tenant_id, mes, paginas, bytes_total) VALUES ($1, to_char(now(),'YYYY-MM'), $2, $3)
		  ON CONFLICT (tenant_id, mes) DO UPDATE SET paginas=usage_monthly.paginas+$2, bytes_total=usage_monthly.bytes_total+$3`, b.TenantID, newPages, derived)
		timeline(ctx, tx, b.ID, "FATIADO", fmt.Sprintf("%d páginas extraídas e miniaturas geradas", len(m.Paginas)))
		return nil
	})
}

func (s *Service) dispatch(ctx context.Context, b *batchRow, failAt int) error {
	req := iacore.JobRequest{BatchID: b.ID, Versao: b.Versao, CallbackURL: s.Cfg.InternalBaseURL + "/internal/ia/callback", TipoLote: b.TipoLote,
		AnalisesPrevias: map[string]json.RawMessage{}, SimularFalhaNaPg: failAt, LimiarConfianca: 0.75}
	pending := 0
	// Camada 0: páginas idênticas (mesmo SHA-256) já processadas nesta empresa reaproveitam o resultado, sem chamar a IA
	s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		var n int
		err := tx.QueryRow(ctx, `WITH src AS (
		    SELECT DISTINCT ON (hash_sha256) hash_sha256, analise, batch_id FROM pages
		    WHERE proc_status='OK' AND analise IS NOT NULL AND hash_sha256 IS NOT NULL AND batch_id<>$1 ORDER BY hash_sha256, processado_em DESC),
		  upd AS (UPDATE pages p SET proc_status='OK', erro=NULL, processado_em=now(),
		    analise = jsonb_set(jsonb_set(jsonb_set(src.analise,'{camada}', to_jsonb($2::text)),'{tokens}','0'),'{reutilizada_de}', to_jsonb(src.batch_id::text))
		    FROM src WHERE p.batch_id=$1 AND p.proc_status<>'OK' AND p.hash_sha256=src.hash_sha256 RETURNING 1)
		  SELECT count(*) FROM upd`, b.ID, CamadaCache).Scan(&n)
		if err == nil && n > 0 {
			timeline(ctx, tx, b.ID, "CACHE_SHA256", fmt.Sprintf("%d página(s) reaproveitada(s) do cache SHA-256 (0 tokens)", n))
		}
		return nil
	})
	err := s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		tx.QueryRow(ctx, `SELECT limiar_confianca FROM tenants WHERE id=$1`, b.TenantID).Scan(&req.LimiarConfianca)
		rows, err := tx.Query(ctx, `SELECT numero, storage_key, proc_status, analise, coalesce(texto_embutido,'') FROM pages WHERE batch_id=$1 ORDER BY numero`, b.ID)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var n int
			var key, st, emb string
			var an []byte
			rows.Scan(&n, &key, &st, &an, &emb)
			if st == "OK" && an != nil {
				req.AnalisesPrevias[fmt.Sprint(n)] = an
				continue
			}
			pending++
			req.Paginas = append(req.Paginas, iacore.PageRef{Numero: n, TextoEmbutido: emb,
				ImageURL: s.Signer.URLFor(s.Cfg.InternalBaseURL, storage.Grant{Tenant: b.TenantID, Key: key}, 2*time.Hour)})
		}
		return nil
	})
	if err != nil {
		return err
	}
	if len(req.AnalisesPrevias) > 0 { // retomada: só o que falta é reprocessado
		_ = s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error { // a linha do tempo é informativa: falha aqui não impede a retomada
			timeline(ctx, tx, b.ID, "RETOMADO", fmt.Sprintf("retomado do checkpoint: %d páginas já concluídas, %d pendentes", len(req.AnalisesPrevias), pending))
			return nil
		})
	}
	// páginas pendentes passam a PROCESSANDO
	s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		_, e := tx.Exec(ctx, `UPDATE pages SET proc_status='PROCESSANDO', erro=NULL WHERE batch_id=$1 AND proc_status<>'OK'`, b.ID)
		return e
	})
	if err := s.IA.StartJob(ctx, req, b.Tentativas > 0 || len(req.AnalisesPrevias) > 0); err != nil {
		return err
	}
	return s.DB.Tenant(ctx, b.TenantID, func(tx pgx.Tx) error {
		timeline(ctx, tx, b.ID, "ENVIADO_IA", fmt.Sprintf("tentativa %d: %d páginas enviadas ao IA Core", b.Tentativas+1, pending))
		return nil
	})
}

// retryOrFail: backoff exponencial com até 3 tentativas; depois, fila de mensagens mortas.
func (s *Service) retryOrFail(ctx context.Context, tenantID, batchID, motivo string) error {
	attempts := 0
	var failAt int
	err := s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		if e := tx.QueryRow(ctx, `UPDATE batches SET tentativas=tentativas+1, versao=versao+1, heartbeat_em=now(), erro=$2 WHERE id=$1 RETURNING tentativas`, batchID, motivo).Scan(&attempts); e != nil {
			return e
		}
		if attempts >= MaxAttempts {
			return nil
		}
		timeline(ctx, tx, batchID, "FALHA", fmt.Sprintf("%s — nova tentativa %d/%d agendada", motivo, attempts+1, MaxAttempts))
		return nil
	})
	if err != nil {
		return err
	}
	if attempts >= MaxAttempts {
		s.failPermanent(ctx, tenantID, batchID, motivo, "IA")
		return nil
	}
	delay := time.Duration(5<<uint(attempts-1)) * time.Second
	slog.Warn("lote com falha; reagendando", "batch", batchID, "tentativa", attempts, "em", delay, "motivo", motivo)
	_ = failAt
	s.publish(ctx, tenantID, batchID, "falha")
	return s.Enqueue(TaskPayload{TenantID: tenantID, BatchID: batchID}, delay)
}

func (s *Service) failPermanent(ctx context.Context, tenantID, batchID, motivo, tipo string) {
	s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		tx.Exec(ctx, `UPDATE batches SET status='FALHOU', erro=$2, concluido_em=now() WHERE id=$1`, batchID, motivo)
		tx.Exec(ctx, `UPDATE pages SET proc_status='FALHOU' WHERE batch_id=$1 AND proc_status='PROCESSANDO'`, batchID)
		var tent int
		tx.QueryRow(ctx, `SELECT tentativas FROM batches WHERE id=$1`, batchID).Scan(&tent)
		tx.Exec(ctx, `INSERT INTO dead_letters (tenant_id, batch_id, tipo, erro, tentativas) VALUES ($1,$2,$3,$4,$5)`, tenantID, batchID, tipo, motivo, tent)
		tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'LOTE_FALHOU','Lote com falha — retome o processamento',$2)`, tenantID, "/lotes/"+batchID)
		timeline(ctx, tx, batchID, "FALHOU", "falha persistente: "+motivo+" (enviado à fila de mensagens mortas)")
		return audit.Log(ctx, tx, audit.Event{TenantID: tenantID, ActorRole: "SISTEMA", Acao: "LOTE_FALHOU", Entidade: "batch", EntidadeID: batchID, Dados: map[string]any{"erro": motivo}})
	})
	s.publish(ctx, tenantID, batchID, "falhou")
}

// Retomar: botão "Retomar" (lote falho ou na fila de mensagens mortas). Reprocessa só o que falhou.
func (s *Service) Retomar(ctx context.Context, tenantID, batchID, userID string) error {
	err := s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE batches SET status='PROCESSANDO', tentativas=0, versao=versao+1, erro=NULL, heartbeat_em=now() WHERE id=$1 AND status IN ('FALHOU','PROCESSANDO')`, batchID)
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return fmt.Errorf("o lote não está em estado de falha")
		}
		tx.Exec(ctx, `UPDATE dead_letters SET resolvido_em=now() WHERE batch_id=$1 AND resolvido_em IS NULL`, batchID)
		timeline(ctx, tx, batchID, "RETOMADA_MANUAL", "retomada solicitada pelo usuário")
		return audit.Log(ctx, tx, audit.Event{TenantID: tenantID, Actor: userID, Acao: "LOTE_RETOMADO", Entidade: "batch", EntidadeID: batchID})
	})
	if err != nil {
		return err
	}
	return s.Enqueue(TaskPayload{TenantID: tenantID, BatchID: batchID}, 0)
}

// Watchdog: lotes PROCESSANDO sem sinal de vida (worker ou IA Core caiu) voltam à fila.
func (s *Service) Watchdog(ctx context.Context) error {
	type stuck struct{ T, B string }
	var list []stuck
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT tenant_id::text, id::text FROM batches WHERE status='PROCESSANDO' AND heartbeat_em < now() - make_interval(secs => $1)`, s.stall().Seconds())
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var x stuck
			rows.Scan(&x.T, &x.B)
			list = append(list, x)
		}
		return nil
	})
	if err != nil {
		return err
	}
	for _, x := range list {
		if err := s.retryOrFail(ctx, x.T, x.B, "sem progresso (worker ou IA Core indisponível)"); err != nil {
			slog.Error("watchdog", "erro", err)
		}
	}
	return nil
}

// ---------- callbacks do IA Core ----------

func (s *Service) HandleCallback(ctx context.Context, idem string, cb iacore.Callback) error {
	var tenantID string
	var curVersao int
	var unitID *string
	if err := s.DB.System(ctx, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT tenant_id::text, versao, unit_id::text FROM batches WHERE id=$1`, cb.BatchID).Scan(&tenantID, &curVersao, &unitID)
	}); err != nil {
		return fmt.Errorf("lote desconhecido")
	}
	key := idem
	if key == "" {
		key = fmt.Sprintf("%s:%d:%s:%d", cb.BatchID, cb.Versao, cb.Evento, cb.Numero)
	}
	fresh := false
	s.DB.System(ctx, func(tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `INSERT INTO ia_callbacks (chave, batch_id) VALUES ($1,$2) ON CONFLICT DO NOTHING`, key, cb.BatchID)
		fresh = err == nil && ct.RowsAffected() == 1
		return err
	})
	if !fresh {
		return nil // idempotente: já processado
	}
	switch cb.Evento {
	case "pagina":
		err := s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
			if cb.Status == "OK" {
				_, e := tx.Exec(ctx, `UPDATE pages SET proc_status='OK', analise=$3, erro=NULL, processado_em=now() WHERE batch_id=$1 AND numero=$2`, cb.BatchID, cb.Numero, []byte(cb.Analise))
				tx.Exec(ctx, `UPDATE batches SET heartbeat_em=now() WHERE id=$1`, cb.BatchID)
				return e
			}
			_, e := tx.Exec(ctx, `UPDATE pages SET proc_status='FALHOU', erro=$3, tentativas=tentativas+1 WHERE batch_id=$1 AND numero=$2`, cb.BatchID, cb.Numero, cb.Erro)
			return e
		})
		s.publish(ctx, tenantID, cb.BatchID, "pagina")
		return err
	case "falhou":
		if cb.Versao != curVersao {
			return nil
		}
		return s.retryOrFail(ctx, tenantID, cb.BatchID, "IA Core: "+cb.Erro)
	case "concluido":
		if cb.Versao != curVersao {
			slog.Info("callback concluído de versão antiga ignorado", "batch", cb.BatchID, "versao", cb.Versao, "atual", curVersao)
			return nil
		}
		return s.complete(ctx, tenantID, unitID, cb)
	}
	return fmt.Errorf("evento desconhecido: %s", cb.Evento)
}

func (s *Service) complete(ctx context.Context, tenantID string, unitID *string, cb iacore.Callback) error {
	err := s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		var status string
		var limiar float64
		if err := tx.QueryRow(ctx, `SELECT b.status, t.limiar_confianca FROM batches b JOIN tenants t ON t.id=b.tenant_id WHERE b.id=$1`, cb.BatchID).Scan(&status, &limiar); err != nil {
			return err
		}
		if status == "PROCESSADO" || status == "PROCESSADO_COM_PENDENCIAS" {
			return nil
		}
		var h documents.Hints
		tx.QueryRow(ctx, `SELECT dica_funcionario_id::text, dica_tipo, substitui_documento_id::text FROM batches WHERE id=$1`, cb.BatchID).Scan(&h.EmployeeID, &h.Tipo, &h.Substitui)
		sum, _, err := s.Ingest.Ingest(ctx, tx, tenantID, cb.BatchID, unitID, limiar, cb.Documentos, h)
		if err != nil {
			return err
		}
		st := "PROCESSADO"
		if sum.Revisao > 0 {
			st = "PROCESSADO_COM_PENDENCIAS"
		}
		rj, _ := json.Marshal(sum)
		tx.Exec(ctx, `UPDATE batches SET status=$2, resumo=$3, concluido_em=now(), heartbeat_em=now(), erro=NULL WHERE id=$1`, cb.BatchID, st, rj)
		timeline(ctx, tx, cb.BatchID, "CONCLUIDO", fmt.Sprintf("%d documentos: %d auto-aprovados, %d para revisão, %d sem vínculo", sum.Documentos, sum.AutoAprovado, sum.Revisao, sum.SemVinculo))
		tx.Exec(ctx, `INSERT INTO usage_monthly (tenant_id, mes, docs, tokens, custo_ia_centavos) VALUES ($1,to_char(now(),'YYYY-MM'),$2,$3,$4)
		  ON CONFLICT (tenant_id, mes) DO UPDATE SET docs=usage_monthly.docs+$2, tokens=usage_monthly.tokens+$3, custo_ia_centavos=usage_monthly.custo_ia_centavos+$4`, tenantID, sum.Documentos, sum.Tokens, sum.CustoCent)
		if err := compliance.Recompute(ctx, tx, tenantID, ""); err != nil {
			return err
		}
		tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'LOTE_CONCLUIDO',$2,$3)`, tenantID,
			fmt.Sprintf("Lote concluído: %d documentos (%d para revisão)", sum.Documentos, sum.Revisao), "/lotes/"+cb.BatchID)
		if sum.PreCadastros > 0 {
			tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'PRE_CADASTRO',$2,'/funcionarios?pre=1')`, tenantID, fmt.Sprintf("%d funcionário(s) pré-cadastrado(s) a partir do lote: complete o cadastro", sum.PreCadastros))
		}
		if sum.Ilegiveis > 0 {
			tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'ILEGIVEL',$2,'/revisao')`, tenantID, fmt.Sprintf("%d documento(s) ilegível(is) precisam de classificação manual", sum.Ilegiveis))
		}
		if sum.Revisao > 0 {
			tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'REVISAO',$2,'/revisao')`, tenantID, fmt.Sprintf("%d documento(s) aguardando revisão humana", sum.Revisao))
		}
		return audit.Log(ctx, tx, audit.Event{TenantID: tenantID, ActorRole: "SISTEMA", Acao: "LOTE_PROCESSADO", Entidade: "batch", EntidadeID: cb.BatchID, Dados: sum})
	})
	if err != nil {
		// libera a chave idempotente para o IA Core poder reenviar o callback
		s.DB.System(ctx, func(tx pgx.Tx) error {
			_, e := tx.Exec(ctx, `DELETE FROM ia_callbacks WHERE batch_id=$1 AND chave LIKE '%concluido%'`, cb.BatchID)
			return e
		})
		return err
	}
	s.publish(ctx, tenantID, cb.BatchID, "concluido")
	return nil
}

var _ = io.EOF

func nilIfEmpty(b json.RawMessage) any {
	if len(b) == 0 || string(b) == "null" {
		return nil
	}
	return []byte(b)
}
