package http

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/batches"
	"github.com/agreser-innovations/citadel-ia/backend/internal/storage"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

func (s *Server) uploadMeta(c *gin.Context) batches.UploadMeta {
	return batches.UploadMeta{Tenant: tid(c), User: auth.ClaimsOf(c).Subject, IP: c.ClientIP()}
}

// POST /batches/uploads — inicia o envio retomável em partes.
func (s *Server) startUpload(c *gin.Context) {
	var in struct {
		Filename             string `json:"filename" binding:"required"`
		Size                 int64  `json:"size" binding:"required"`
		UnitID               string `json:"unit_id"`
		TipoLote             string `json:"tipo_lote"`
		FailAt               int    `json:"simular_falha_na_pagina"`
		DicaFuncionarioID    string `json:"dica_funcionario_id"`
		DicaTipo             string `json:"dica_tipo"`
		SubstituiDocumentoID string `json:"substitui_documento_id"`
	}
	if !bindJSON(c, &in) {
		return
	}
	m := s.uploadMeta(c)
	m.Filename, m.Size, m.UnitID, m.TipoLote = in.Filename, in.Size, in.UnitID, in.TipoLote
	m.DicaFuncionarioID, m.DicaTipo, m.SubstituiDocumentoID = in.DicaFuncionarioID, in.DicaTipo, in.SubstituiDocumentoID
	if !s.Cfg.Prod() {
		m.FailAt = in.FailAt // simulação de queda só fora de produção
	}
	id, err := s.Batches.InitUpload(c.Request.Context(), m)
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	c.JSON(http.StatusCreated, gin.H{"upload_id": id, "chunk_size": batches.ChunkSize, "offset": 0})
}

func (s *Server) uploadStatus(c *gin.Context) {
	off, m, err := s.Batches.Offset(c.Request.Context(), tid(c), c.Param("id"))
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	c.Header("Upload-Offset", strconv.FormatInt(off, 10))
	c.JSON(200, gin.H{"offset": off, "size": m.Size, "filename": m.Filename})
}

func (s *Server) uploadChunk(c *gin.Context) {
	off, err := strconv.ParseInt(c.GetHeader("Upload-Offset"), 10, 64)
	if err != nil {
		problem.Write(c, problem.BadRequest("cabeçalho Upload-Offset obrigatório"))
		return
	}
	n, err := s.Batches.AppendChunk(c.Request.Context(), tid(c), c.Param("id"), off, c.Request.Body)
	if err != nil {
		c.Header("Upload-Offset", strconv.FormatInt(n, 10))
		problem.Write(c, problem.From(err))
		return
	}
	c.Header("Upload-Offset", strconv.FormatInt(n, 10))
	c.Status(http.StatusNoContent)
}

func (s *Server) uploadComplete(c *gin.Context) {
	r, err := s.Batches.Complete(c.Request.Context(), tid(c), auth.ClaimsOf(c).Subject, c.Param("id"))
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	c.JSON(http.StatusAccepted, r)
}

// POST /batches — envio simples (multipart) com Idempotency-Key.
func (s *Server) createBatch(c *gin.Context) {
	ctx := c.Request.Context()
	if k := c.GetHeader("Idempotency-Key"); k != "" {
		if id, err := s.Redis.Get(ctx, "idem:"+tid(c)+":"+k).Result(); err == nil {
			c.JSON(http.StatusOK, gin.H{"id": id, "status": "RECEBIDO", "repetido": true})
			return
		}
	}
	c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, s.Cfg.MaxUploadBytes+(1<<20))
	fh, err := c.FormFile("file")
	if err != nil {
		problem.Write(c, problem.BadRequest("envie o arquivo no campo 'file' (até "+strconv.FormatInt(s.Cfg.MaxUploadBytes>>20, 10)+" MB)"))
		return
	}
	src, _ := fh.Open()
	defer src.Close()
	tmp, _ := os.CreateTemp("", "upload-*")
	defer os.Remove(tmp.Name())
	io.Copy(tmp, src)
	tmp.Close()
	m := s.uploadMeta(c)
	m.Filename, m.UnitID, m.TipoLote = fh.Filename, c.PostForm("unit_id"), c.PostForm("tipo_lote")
	if !s.Cfg.Prod() {
		m.FailAt, _ = strconv.Atoi(c.PostForm("simular_falha_na_pagina"))
	}
	r, err := s.Batches.FinalizeFile(ctx, tid(c), m.User, m, tmp.Name())
	if err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	if k := c.GetHeader("Idempotency-Key"); k != "" {
		s.Redis.Set(ctx, "idem:"+tid(c)+":"+k, r.ID, 24*time.Hour)
	}
	c.JSON(http.StatusAccepted, r)
}

func (s *Server) listBatches(c *gin.Context) {
	units, _ := s.userScope(c)
	limit := limitOf(c, 30, 100)
	args := []any{units, limit + 1}
	where := `($1::uuid[]='{}' OR b.unit_id=ANY($1))`
	if cur := decodeCursor(c.Query("cursor")); len(cur) == 2 {
		args = append(args, cur[0], cur[1])
		where += ` AND (b.criado_em, b.id::text) < ($3::timestamptz, $4)`
	}
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT b.id, b.arquivo_original, b.bytes, b.tipo_lote, b.total_paginas, b.status, b.tentativas, b.erro, b.resumo,
		  b.criado_em, b.iniciado_em, b.concluido_em, u.nome AS enviado_por, un.nome AS unidade,
		  (SELECT count(*) FROM documents d WHERE d.batch_id=b.id AND d.status='AGUARDANDO_REVISAO') AS para_revisao,
		  (SELECT count(*) FROM pages p WHERE p.batch_id=b.id AND p.proc_status='OK') AS paginas_ok,
		  (SELECT count(*) FROM pages p WHERE p.batch_id=b.id AND p.proc_status='FALHOU') AS paginas_falhas
		  FROM batches b LEFT JOIN users u ON u.id=b.enviado_por LEFT JOIN units un ON un.id=b.unit_id WHERE `+where+` ORDER BY b.criado_em DESC, b.id DESC LIMIT $2) t`, args...).Scan(&raw)
	}) {
		return
	}
	out := pageOf(raw, limit, "criado_em", "id")
	c.JSON(200, out)
}

func (s *Server) getBatch(c *gin.Context) {
	_, saude := s.userScope(c)
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT coalesce((SELECT row_to_json(t) FROM (
	  SELECT b.id, b.arquivo_original, b.bytes, b.sha256, b.tipo_lote, b.total_paginas, b.status, b.tentativas, b.erro, b.versao, b.resumo, b.linha_tempo,
	    b.criado_em, b.iniciado_em, b.concluido_em, u.nome AS enviado_por, un.nome AS unidade,
	    (SELECT coalesce(json_agg(json_build_object('numero',p.numero,'status',p.proc_status,'erro',p.erro,'tentativas',p.tentativas) ORDER BY p.numero),'[]') FROM pages p WHERE p.batch_id=b.id) AS paginas,
	    (SELECT coalesce(json_agg(d ORDER BY (d.paginas)[1]),'[]') FROM (SELECT x.*, (SELECT pg.thumb_key FROM pages pg WHERE pg.batch_id=x.batch_id AND pg.numero=x.paginas[1]) AS thumb_key
	       FROM (`+docRowSQL("$2")+` WHERE d.batch_id=$1 AND d.status NOT IN ('REJEITADO','SUBSTITUIDO')) x) d) AS documentos
	  FROM batches b LEFT JOIN users u ON u.id=b.enviado_por LEFT JOIN units un ON un.id=b.unit_id WHERE b.id=$1) t),'null'::json)`, c.Param("id"), saude).Scan(&raw)
	}) {
		return
	}
	var out map[string]any
	if json.Unmarshal(raw, &out) != nil || out == nil {
		c.Data(200, "application/json", raw)
		return
	}
	// miniatura assinada (120 s) da 1ª página de cada documento; documentos de saúde mascarados não têm imagem
	if docs, ok := out["documentos"].([]any); ok {
		for _, d := range docs {
			m, _ := d.(map[string]any)
			if m == nil {
				continue
			}
			if k, _ := m["thumb_key"].(string); k != "" && m["mascarado"] != true && !support(c) {
				m["thumb_url"] = s.Signer.URL(storage.Grant{Tenant: tid(c), Key: k}, 120*time.Second)
			}
			delete(m, "thumb_key")
		}
	}
	c.JSON(200, out)
}

func (s *Server) retryBatch(c *gin.Context) {
	if err := s.Batches.Retomar(c.Request.Context(), tid(c), c.Param("id"), auth.ClaimsOf(c).Subject); err != nil {
		problem.Write(c, problem.Conflict(err.Error()))
		return
	}
	c.Status(http.StatusAccepted)
}

// batchEvents: SSE com o progresso do lote (assina o canal Redis antes de enviar o estado atual).
func (s *Server) batchEvents(c *gin.Context) {
	id := c.Param("id")
	var snap []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var e error
		snap, e = batches.Snapshot(ctx, tx, id)
		if e == pgx.ErrNoRows {
			return problem.NotFound("lote não encontrado")
		}
		return e
	}) {
		return
	}
	ctx := c.Request.Context()
	sub := s.Redis.Subscribe(ctx, "batch:"+id)
	defer sub.Close()
	h := c.Writer.Header()
	h.Set("Content-Type", "text/event-stream")
	h.Set("Cache-Control", "no-cache")
	h.Set("X-Accel-Buffering", "no")
	c.Status(200)
	send := func(ev string, data []byte) {
		c.Writer.WriteString("event: " + ev + "\ndata: " + string(data) + "\n\n")
		c.Writer.Flush()
	}
	send("snapshot", mustJSON(map[string]any{"evento": "snapshot", "lote": jsonRaw(snap)}))
	ping := time.NewTicker(15 * time.Second)
	defer ping.Stop()
	ch := sub.Channel()
	for {
		select {
		case m := <-ch:
			send("lote", []byte(m.Payload))
		case <-ping.C:
			c.Writer.WriteString(": ping\n\n")
			c.Writer.Flush()
		case <-ctx.Done():
			return
		}
	}
}
