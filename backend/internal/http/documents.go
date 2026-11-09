package http

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/internal/documents"
	"github.com/agreser-innovations/citadel-ia/backend/internal/iacore"
	"github.com/agreser-innovations/citadel-ia/backend/internal/ocrseal"
	"github.com/agreser-innovations/citadel-ia/backend/internal/storage"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"golang.org/x/text/runes"
	"golang.org/x/text/transform"
	"golang.org/x/text/unicode/norm"
)

type docMeta struct {
	ID, Tipo, Titulo, Nome, Pasta, Batch, Status string
	Paginas                                      []int32
	Saude                                        bool
	Employee                                     *string
	Atualizado                                   time.Time
}

func (s *Server) loadDocMeta(ctx context.Context, tx pgx.Tx, id string) (*docMeta, error) {
	var d docMeta
	var batch, titulo, nome, pasta *string
	err := tx.QueryRow(ctx, `SELECT id::text, document_type, titulo, nome_arquivo, pasta_destino, batch_id::text, status, paginas, sensivel_saude, employee_id::text, atualizado_em FROM documents WHERE id=$1`, id).
		Scan(&d.ID, &d.Tipo, &titulo, &nome, &pasta, &batch, &d.Status, &d.Paginas, &d.Saude, &d.Employee, &d.Atualizado)
	if err == pgx.ErrNoRows {
		return nil, problem.NotFound("documento não encontrado")
	}
	d.Titulo, d.Nome, d.Pasta = deref(titulo), deref(nome), deref(pasta)
	d.Batch = deref(batch)
	return &d, err
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

// canSeeDoc: dados de saúde exigem saude:ler; no acesso de suporte só a cópia anonimizada.
func (s *Server) canSeeDoc(c *gin.Context, d *docMeta, anonymized bool) error {
	if support(c) && !anonymized {
		return problem.Forbidden("no acesso de suporte só é permitida a cópia anonimizada")
	}
	if d.Saude && !auth.HasPerm(auth.ClaimsOf(c), "saude:ler") {
		return problem.Forbidden("este documento contém dados de saúde: permissão saude:ler necessária")
	}
	return nil
}

func (s *Server) pageURLs(ctx context.Context, tx pgx.Tx, tenantID string, d *docMeta, ttl time.Duration) ([]gin.H, error) {
	if d.Batch == "" || len(d.Paginas) == 0 { // lançamento manual: não há imagem
		return []gin.H{}, nil
	}
	rows, err := tx.Query(ctx, `SELECT numero, storage_key, coalesce(thumb_key,''), rotacao, largura, altura FROM pages WHERE batch_id=$1 AND numero=ANY($2) ORDER BY numero`, d.Batch, d.Paginas)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []gin.H{}
	for rows.Next() {
		var n, rot int
		var k, tk string
		var w, h *int
		rows.Scan(&n, &k, &tk, &rot, &w, &h)
		item := gin.H{"numero": n, "rotacao": rot, "largura": w, "altura": h, "url": s.Signer.URL(storage.Grant{Tenant: tenantID, Key: k}, ttl)}
		if tk != "" {
			item["thumb_url"] = s.Signer.URL(storage.Grant{Tenant: tenantID, Key: tk}, ttl)
		}
		out = append(out, item)
	}
	return out, nil
}

// GET /documents/:id — detalhe com campos extraídos e páginas (URLs assinadas de 120 s).
func (s *Server) getDocument(c *gin.Context) {
	_, saude := s.userScope(c)
	var raw []byte
	var texto string
	var pages []gin.H
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		d, err := s.loadDocMeta(ctx, tx, c.Param("id"))
		if err != nil {
			return err
		}
		if err := s.canSeeDoc(c, d, support(c)); err != nil {
			return err
		}
		if !support(c) {
			if pages, err = s.pageURLs(ctx, tx, tid(c), d, 120*time.Second); err != nil {
				return err
			}
		}
		// o texto lido (OCR) está cifrado: é aberto aqui, só para quem pode ver o documento original. O acesso de suporte
		// recebe sempre o texto anonimizado.
		textCol := "''"
		if support(c) {
			textCol = "d.texto_anonimizado"
		}
		err = tx.QueryRow(ctx, `SELECT row_to_json(t) FROM (SELECT d.id, d.document_type, dt.nome AS tipo_nome, dt.categoria, d.titulo, d.competencia, d.data_documento, d.validade_ate,
		  d.status, d.origem, d.confianca, d.paginas, d.employee_id, d.batch_id, d.campos, d.alertas, d.motivos_revisao, d.nao_conformidades, d.dados_sensiveis, d.finops, `+textCol+` AS texto_ocr,
		  d.texto_anonimizado, d.nome_extraido, d.nome_arquivo, d.pasta_destino, d.checklist, d.origem, d.possui_manuscrito, d.sensivel_saude, d.versao, d.substitui_id, d.duplicata_de, d.criado_em,
		  e.nome AS funcionario_nome, e.cpf_mascarado AS funcionario_cpf, d.supplier_id,
		  (SELECT razao_social FROM suppliers WHERE id=d.supplier_id) AS fornecedor, (SELECT cnpj FROM suppliers WHERE id=d.supplier_id) AS fornecedor_cnpj
		  FROM documents d JOIN document_types dt ON dt.codigo=d.document_type LEFT JOIN employees e ON e.id=d.employee_id WHERE d.id=$1) t`, d.ID).Scan(&raw)
		if err != nil {
			return err
		}
		if !support(c) {
			sl, e := s.sealer(ctx, tx, tid(c))
			if e != nil {
				return e
			}
			var sealed []byte
			var legado string
			if e := tx.QueryRow(ctx, `SELECT texto_ocr_cifrado, texto_ocr FROM documents WHERE id=$1`, d.ID).Scan(&sealed, &legado); e != nil {
				return e
			}
			if texto, e = sl.PlainOrOpen(ocrseal.Texto, sealed, legado); e != nil {
				return e
			}
		}
		if d.Saude {
			return s.audit(ctx, tx, c, "VISUALIZACAO_DADO_SAUDE", "document", d.ID, nil)
		}
		_ = saude
		return nil
	}) {
		return
	}
	var out map[string]any
	json.Unmarshal(raw, &out)
	if !support(c) {
		out["texto_ocr"] = texto
	}
	var ck []map[string]any
	if b, e := json.Marshal(out["checklist"]); e == nil {
		json.Unmarshal(b, &ck)
	}
	out["status_mobilizacao"] = documents.MobilizationStatus(fmt.Sprint(out["status"]), ck)
	if m, ok := out["campos"].(map[string]any); ok {
		out["empresa_nome"], out["empresa_cnpj"] = m["empresa_nome"], m["empresa_cnpj"]
	}
	out["paginas_urls"] = pages
	c.JSON(200, out)
}

func (s *Server) documentPageURL(c *gin.Context) {
	var n int
	fmt.Sscan(c.Param("n"), &n)
	var url string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		d, err := s.loadDocMeta(ctx, tx, c.Param("id"))
		if err != nil {
			return err
		}
		if err := s.canSeeDoc(c, d, false); err != nil {
			return err
		}
		if d.Batch == "" {
			return problem.NotFound("documento lançado manualmente não tem imagem")
		}
		var key, tk string
		if err := tx.QueryRow(ctx, `SELECT storage_key, coalesce(thumb_key,'') FROM pages WHERE batch_id=$1 AND numero=$2 AND numero=ANY($3)`, d.Batch, n, d.Paginas).Scan(&key, &tk); err != nil {
			return problem.NotFound("página não encontrada neste documento")
		}
		if c.Query("thumb") == "1" && tk != "" {
			key = tk
		}
		url = s.Signer.URL(storage.Grant{Tenant: tid(c), Key: key}, 90*time.Second)
		return s.audit(ctx, tx, c, "VISUALIZACAO_PAGINA", "document", d.ID, map[string]any{"pagina": n})
	}) {
		return
	}
	c.JSON(200, gin.H{"url": url, "expira_em_segundos": 90})
}

func foldText(s string) string {
	t := transform.Chain(norm.NFD, runes.Remove(runes.In(unicode.Mn)), norm.NFC)
	out, _, _ := transform.String(t, strings.ToLower(s))
	return out
}

// GET /documents/:id/highlights?q= — caixas das palavras encontradas (do OCR) para destacar no visualizador.
func (s *Server) documentHighlights(c *gin.Context) {
	terms := strings.Fields(foldText(c.Query("q")))
	res := []gin.H{}
	if len(terms) > 0 && s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		d, err := s.loadDocMeta(ctx, tx, c.Param("id"))
		if err != nil {
			return err
		}
		if err := s.canSeeDoc(c, d, false); err != nil {
			return err
		}
		if d.Batch == "" {
			return nil
		}
		sl, err := s.sealer(ctx, tx, tid(c))
		if err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT numero, palavras_cifradas, palavras FROM pages WHERE batch_id=$1 AND numero=ANY($2) ORDER BY numero`, d.Batch, d.Paginas)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var n int
			var sealed, legado []byte
			rows.Scan(&n, &sealed, &legado)
			raw := legado
			if len(sealed) > 0 {
				p, e := sl.OpenText(ocrseal.Palavra, sealed)
				if e != nil {
					return e
				}
				raw = []byte(p)
			}
			var words [][]any
			json.Unmarshal(raw, &words)
			boxes := [][]float64{}
			for _, w := range words {
				if len(w) < 5 {
					continue
				}
				txt := foldText(fmt.Sprint(w[4]))
				for _, t := range terms {
					if strings.Contains(txt, t) {
						b := make([]float64, 4)
						for i := 0; i < 4; i++ {
							b[i], _ = w[i].(float64)
						}
						boxes = append(boxes, b)
						break
					}
				}
			}
			if len(boxes) > 0 {
				res = append(res, gin.H{"numero": n, "caixas": boxes})
			}
		}
		return nil
	}) {
		c.JSON(200, res)
		return
	}
	if len(terms) == 0 {
		c.JSON(200, res)
	}
}

// renderDoc gera (ou reaproveita do cache cifrado) o PDF do documento: original | pesquisavel | anonimizado.
func (s *Server) renderDoc(ctx context.Context, tenantID, docID, modo string) ([]byte, *docMeta, error) {
	var meta *docMeta
	var pages []iacore.RenderPage
	termos := []string{}
	err := s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		d, err := s.loadDocMeta(ctx, tx, docID)
		if err != nil {
			return err
		}
		meta = d
		if d.Batch == "" {
			return problem.BadRequest("documento lançado manualmente não tem imagem para gerar PDF")
		}
		sl, err := s.sealer(ctx, tx, tenantID)
		if err != nil {
			return err
		}
		rows, err := tx.Query(ctx, `SELECT storage_key, analise, palavras_cifradas, palavras, caixas, texto_len + coalesce(length(texto_embutido),0) FROM pages WHERE batch_id=$1 AND numero=ANY($2) ORDER BY numero`, d.Batch, d.Paginas)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var k string
			var an, pwCifrado, pw, cx []byte
			var nativo int
			rows.Scan(&k, &an, &pwCifrado, &pw, &cx, &nativo)
			t, e := sl.AnaliseTexto(an)
			if e != nil {
				return e
			}
			if len(pwCifrado) > 0 {
				p, e := sl.OpenText(ocrseal.Palavra, pwCifrado)
				if e != nil {
					return e
				}
				pw = []byte(p)
			}
			rp := iacore.RenderPage{ImageURL: s.Signer.URLFor(s.Cfg.InternalBaseURL, storage.Grant{Tenant: tenantID, Key: k}, 10*time.Minute), Texto: t, TextoNativo: nativo >= 20}
			if modo != "original" {
				rp.Palavras = pw
			}
			if modo == "anonimizado" {
				rp.Caixas = cx
				rp.Texto = "" // a camada de texto é refeita sem os dados pessoais
			}
			pages = append(pages, rp)
		}
		rows.Close()
		if modo == "anonimizado" {
			// nomes já conhecidos do documento: a cópia tarja onde aparecerem, mesmo sem o rótulo "Nome:" ao lado
			var nomeDoc, nomeFunc *string
			tx.QueryRow(ctx, `SELECT d.nome_extraido, e.nome FROM documents d LEFT JOIN employees e ON e.id=d.employee_id WHERE d.id=$1`, docID).Scan(&nomeDoc, &nomeFunc)
			for _, n := range []*string{nomeDoc, nomeFunc} {
				if n != nil && strings.TrimSpace(*n) != "" {
					termos = append(termos, *n)
				}
			}
		}
		return nil
	})
	if err != nil {
		return nil, nil, err
	}
	cacheKey := fmt.Sprintf("%s/%s/derived/%s-%s-v2-%d.pdf", tenantID, meta.Batch, meta.ID, modo, meta.Atualizado.Unix())
	if b, err := s.Vault.ReadAll(ctx, tenantID, cacheKey); err == nil {
		return b, meta, nil
	}
	var buf bytes.Buffer
	if err := s.IA.Render(ctx, modo, meta.Titulo, pages, termos, &buf); err != nil {
		return nil, nil, err
	}
	if _, err := s.Vault.PutBytes(ctx, tenantID, cacheKey, buf.Bytes()); err == nil {
		s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
			tx.Exec(ctx, `INSERT INTO storage_events (tenant_id, tipo, bytes, objeto) VALUES ($1,'DERIVADO',$2,$3)`, tenantID, buf.Len(), cacheKey)
			_, e := tx.Exec(ctx, `UPDATE tenants SET bytes_usados=bytes_usados+$2 WHERE id=$1`, tenantID, buf.Len())
			return e
		})
	}
	return buf.Bytes(), meta, nil
}

// GET /documents/:id/download?formato=original|pesquisavel|anonimizado
func (s *Server) downloadDocument(c *gin.Context) {
	modo := c.DefaultQuery("formato", "original")
	if modo != "original" && modo != "pesquisavel" && modo != "anonimizado" {
		problem.Write(c, problem.BadRequest("formato inválido"))
		return
	}
	if support(c) {
		modo = "anonimizado"
	}
	ctx := c.Request.Context()
	var meta *docMeta
	var check error
	s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		meta, check = s.loadDocMeta(ctx, tx, c.Param("id"))
		return nil
	})
	if check != nil {
		problem.Write(c, problem.From(check))
		return
	}
	if err := s.canSeeDoc(c, meta, modo == "anonimizado"); err != nil {
		problem.Write(c, problem.From(err))
		return
	}
	if meta.Batch == "" {
		problem.Write(c, problem.BadRequest("documento lançado manualmente: não há imagem para gerar PDF"))
		return
	}
	pdf, meta, err := s.renderDoc(ctx, tid(c), meta.ID, modo)
	if err != nil {
		problem.Write(c, problem.New(502, "render-falhou", "não foi possível gerar o PDF: "+err.Error()))
		return
	}
	s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		return s.audit(ctx, tx, c, "DOWNLOAD_DOCUMENTO", "document", meta.ID, map[string]any{"formato": modo})
	})
	name := strings.TrimSuffix(meta.Nome, ".pdf")
	if name == "" {
		name = meta.ID
	}
	if modo == "anonimizado" {
		name = "LGPD_" + name
	}
	c.Header("Content-Disposition", fmt.Sprintf(`attachment; filename="%s.pdf"`, name))
	c.Data(200, "application/pdf", pdf)
}

// GET /documents/search?q= — busca em texto completo (tsvector em português, sem acentos), respeitando escopo e permissão.
func (s *Server) searchDocuments(c *gin.Context) {
	q := strings.TrimSpace(c.Query("q"))
	if len(q) < 2 {
		c.JSON(200, []any{})
		return
	}
	units, saude := s.userScope(c)
	s.queryJSON(c, `SELECT coalesce(json_agg(t),'[]') FROM (
	  SELECT d.id, d.document_type, dt.nome AS tipo_nome, d.competencia, d.paginas, d.status, d.employee_id, e.nome AS funcionario_nome, e.cpf_mascarado AS funcionario_cpf,
	    ts_rank(d.tsv, query) AS rank,
	    ts_headline('portuguese', f_unaccent(d.texto_anonimizado), query, 'MaxWords=24, MinWords=8, StartSel=<<, StopSel=>>, MaxFragments=1') AS trecho
	  FROM documents d JOIN document_types dt ON dt.codigo=d.document_type LEFT JOIN employees e ON e.id=d.employee_id, websearch_to_tsquery('portuguese', f_unaccent($1)) query
	  WHERE d.tsv @@ query AND d.status NOT IN ('REJEITADO','SUBSTITUIDO') AND (NOT d.sensivel_saude OR $3)
	    AND ($2::uuid[]='{}' OR d.unit_id=ANY($2) OR e.unit_id=ANY($2)) ORDER BY rank DESC LIMIT 30) t`, q, units, saude)
}

// GET /review/queue — fila priorizada: erro > sem vínculo > baixa confiança.
func (s *Server) reviewQueue(c *gin.Context) {
	units, saude := s.userScope(c)
	args := []any{saude, units}
	where := `d.status='AGUARDANDO_REVISAO' AND ($2::uuid[]='{}' OR d.unit_id=ANY($2) OR e.unit_id=ANY($2))`
	if v := c.Query("tipo"); v != "" {
		args = append(args, v)
		where += fmt.Sprintf(" AND d.document_type=$%d", len(args))
	}
	if v := c.Query("lote"); v != "" {
		args = append(args, v)
		where += fmt.Sprintf(" AND d.batch_id=$%d::uuid", len(args))
	}
	if v := c.Query("motivo"); v != "" {
		args = append(args, v)
		where += fmt.Sprintf(" AND d.motivos_revisao ? $%d", len(args))
	}
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.prioridade, t.confianca, t.criado_em),'[]') FROM (
	  SELECT d.id, d.document_type, dt.nome AS tipo_nome, CASE WHEN d.sensivel_saude AND NOT $1 THEN 'Documento de saúde (acesso restrito)' ELSE d.titulo END AS titulo,
	    d.confianca, d.paginas, d.batch_id, d.motivos_revisao, d.employee_id, d.nome_extraido, e.nome AS funcionario_nome, d.criado_em, (d.sensivel_saude AND NOT $1) AS mascarado,
	    CASE WHEN d.motivos_revisao ? 'ALERTA_ERRO' THEN 0 WHEN d.motivos_revisao ? 'SEM_VINCULO' THEN 1 ELSE 2 END AS prioridade
	  FROM documents d JOIN document_types dt ON dt.codigo=d.document_type LEFT JOIN employees e ON e.id=d.employee_id WHERE `+where+` LIMIT 200) t`, args...)
}

// POST /review/:documentId
func (s *Server) applyReview(c *gin.Context) {
	var in documents.ReviewInput
	if !bindJSON(c, &in) {
		return
	}
	cl := auth.ClaimsOf(c)
	id := c.Param("documentId")
	var resend *struct{ Email, Nome, Tipo, Motivo string }
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		d, err := s.loadDocMeta(ctx, tx, id)
		if err != nil {
			return err
		}
		if err := s.canSeeDoc(c, d, false); err != nil {
			return err
		}
		affected, err := s.Ingest.Apply(ctx, tx, tid(c), cl.Subject, id, in)
		if err != nil {
			return err
		}
		for _, e := range affected {
			if err := compliance.Recompute(ctx, tx, tid(c), e); err != nil {
				return err
			}
		}
		if len(affected) == 0 {
			if err := compliance.Recompute(ctx, tx, tid(c), ""); err != nil {
				return err
			}
		}
		if in.Acao == "SOLICITAR_REENVIO" {
			var email, nome, tipo string
			if tx.QueryRow(ctx, `SELECT coalesce(u.email,''), coalesce(u.nome,''), dt.nome FROM documents d JOIN document_types dt ON dt.codigo=d.document_type
			  LEFT JOIN batches b ON b.id=d.batch_id LEFT JOIN users u ON u.id=b.enviado_por WHERE d.id=$1`, id).Scan(&email, &nome, &tipo) == nil {
				resend = &struct{ Email, Nome, Tipo, Motivo string }{email, nome, tipo, in.Motivo}
			}
			tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) VALUES ($1,'REENVIO',$2,'/lotes')`, tid(c), "Reenvio solicitado: "+tipo)
		}
		return s.audit(ctx, tx, c, "REVISAO_"+in.Acao, "document", id, map[string]any{"duracao_ms": in.DuracaoMs, "tipo": in.Tipo, "forcado": in.Forcado, "motivo": in.Motivo})
	}) {
		return
	}
	if resend != nil && resend.Email != "" {
		s.Mail.Send(resend.Email, "Citadel IA · reenvio de documento solicitado", fmt.Sprintf("Olá, %s.\n\nO documento \"%s\" não pôde ser lido ou validado e precisa ser enviado novamente (com imagem mais nítida, se for o caso).\n%s\nEnvie um novo lote com o documento corrigido.\n", resend.Nome, resend.Tipo, resend.Motivo))
	}
	c.Status(http.StatusNoContent)
}

func (s *Server) typeSchema(c *gin.Context) {
	raw, err := s.IA.Schema(c.Request.Context(), c.Param("codigo"))
	if err != nil {
		c.JSON(200, gin.H{"type": "object", "properties": gin.H{}})
		return
	}
	c.Data(200, "application/json", raw)
}

// POST /exports/dossie/:employeeId (step-up) — ZIP com os PDFs de cada documento + índice.
func (s *Server) exportDossie(c *gin.Context) {
	ctx := c.Request.Context()
	empID := c.Param("employeeId")
	_, saude := s.userScope(c)
	modo := "pesquisavel"
	if support(c) { // acesso de suporte: só cópia anonimizada, como no download e no ZIP do lote
		modo = "anonimizado"
	}
	type item struct{ ID, Pasta, Nome, Tipo, Comp, Status string }
	var items []item
	var empNome string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `SELECT nome FROM employees WHERE id=$1`, empID).Scan(&empNome); err != nil {
			return problem.NotFound("funcionário não encontrado")
		}
		rows, err := tx.Query(ctx, `SELECT id::text, coalesce(pasta_destino,''), coalesce(nome_arquivo, id::text||'.pdf'), document_type, coalesce(competencia,''), status FROM documents
		  WHERE employee_id=$1 AND status IN ('AUTO_APROVADO','REVISADO') AND (NOT sensivel_saude OR $2) ORDER BY document_type, competencia`, empID, saude)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var it item
			rows.Scan(&it.ID, &it.Pasta, &it.Nome, &it.Tipo, &it.Comp, &it.Status)
			items = append(items, it)
		}
		return s.audit(ctx, tx, c, "EXPORTACAO_DOSSIE", "employee", empID, map[string]any{"documentos": len(items)})
	}) {
		return
	}
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	index := []map[string]string{}
	for _, it := range items {
		pdf, _, err := s.renderDoc(ctx, tid(c), it.ID, modo)
		if err != nil {
			continue
		}
		path := strings.Trim(it.Pasta, "/") + "/" + it.Nome
		w, _ := zw.Create(path)
		w.Write(pdf)
		index = append(index, map[string]string{"arquivo": path, "tipo": it.Tipo, "competencia": it.Comp, "status": it.Status})
	}
	w, _ := zw.Create("00_INDICE.json")
	json.NewEncoder(w).Encode(map[string]any{"funcionario": empNome, "gerado_em": time.Now(), "documentos": index})
	zw.Close()
	c.Header("Content-Disposition", `attachment; filename="dossie.zip"`)
	c.Data(200, "application/zip", buf.Bytes())
}

// GET /batches/:id/export-zip?anonimizado=true — ZIP hierárquico por Empresa/Funcionário + manifesto de auditoria.
func (s *Server) exportBatchZip(c *gin.Context) {
	ctx := c.Request.Context()
	anon := c.Query("anonimizado") == "true" || support(c)
	modo := "pesquisavel"
	if anon {
		modo = "anonimizado"
	}
	_, saude := s.userScope(c)
	type item struct {
		ID, Pasta, Nome, Tipo, Status, Empresa, Func, Cpf string
		Ck                                                []map[string]any
		Finops                                            map[string]any
	}
	var items []item
	var arquivo string
	skippedHealth := 0
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `SELECT arquivo_original FROM batches WHERE id=$1`, c.Param("id")).Scan(&arquivo); err != nil {
			return problem.NotFound("lote não encontrado")
		}
		rows, err := tx.Query(ctx, `SELECT d.id::text, coalesce(d.pasta_destino,'DOSSIE_GERAL'), coalesce(d.nome_arquivo,d.id::text||'.pdf'), d.document_type, d.status,
		  coalesce(d.campos->>'empresa_nome',''), coalesce(e.nome,''), coalesce(e.cpf_mascarado,''), d.checklist, coalesce(d.finops,'{}'::jsonb), d.sensivel_saude
		  FROM documents d LEFT JOIN employees e ON e.id=d.employee_id WHERE d.batch_id=$1 AND d.status NOT IN ('REJEITADO','SUBSTITUIDO') ORDER BY d.paginas[1]`, c.Param("id"))
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var it item
			var ck, fo []byte
			var saudeDoc bool
			if err := rows.Scan(&it.ID, &it.Pasta, &it.Nome, &it.Tipo, &it.Status, &it.Empresa, &it.Func, &it.Cpf, &ck, &fo, &saudeDoc); err != nil {
				return err
			}
			if saudeDoc && !saude {
				skippedHealth++
				continue
			}
			json.Unmarshal(ck, &it.Ck)
			json.Unmarshal(fo, &it.Finops)
			items = append(items, it)
		}
		return s.audit(ctx, tx, c, "EXPORTACAO_LOTE", "batch", c.Param("id"), map[string]any{"documentos": len(items), "anonimizado": anon})
	}) {
		return
	}
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	manifest := []map[string]any{}
	for _, it := range items {
		entry := map[string]any{"id": it.ID, "tipo": it.Tipo, "status": it.Status, "empresa_nome": it.Empresa, "funcionario_nome": it.Func, "funcionario_cpf": it.Cpf,
			"status_mobilizacao": documents.MobilizationStatus(it.Status, it.Ck), "compliance_checklist": it.Ck, "finops_telemetria": it.Finops}
		if anon {
			entry["funcionario_nome"], entry["funcionario_cpf"] = nil, nil
		}
		pdf, _, err := s.renderDoc(ctx, tid(c), it.ID, modo)
		if err != nil {
			entry["erro"] = err.Error()
			manifest = append(manifest, entry)
			continue
		}
		name := it.Nome
		if anon {
			name = "LGPD_" + name
		}
		path := strings.Trim(it.Pasta, "/") + "/" + name
		w, _ := zw.Create(path)
		w.Write(pdf)
		entry["caminho_no_zip"] = path
		manifest = append(manifest, entry)
	}
	mw, _ := zw.Create("00_MANIFESTO_AUDITORIA.json")
	enc := json.NewEncoder(mw)
	enc.SetIndent("", "  ")
	enc.Encode(map[string]any{"lote": arquivo, "gerado_em": time.Now(), "modo_lgpd_anonimizado": anon, "documentos_exportados": len(items), "documentos_saude_omitidos_por_permissao": skippedHealth, "documentos": manifest})
	zw.Close()
	suffix := "Original"
	if anon {
		suffix = "LGPD"
	}
	c.Header("Content-Disposition", fmt.Sprintf(`attachment; filename="Lote_Separado_%s_%s.zip"`, strings.TrimSuffix(arquivo, ".pdf"), suffix))
	c.Data(200, "application/zip", buf.Bytes())
}

// GET /documents — visão geral dos documentos da empresa (filtros: q, tipo, categoria, status, employee, lote) com cursor e totais por status.
func (s *Server) listDocuments(c *gin.Context) {
	units, saude := s.userScope(c)
	limit := limitOf(c, 30, 100)
	scope := `($2::uuid[]='{}' OR d.unit_id=ANY($2) OR ef.unit_id=ANY($2))`
	args := []any{saude, units}
	where := []string{scope, "d.status <> 'SUBSTITUIDO'"}
	add := func(cond, v string) {
		if v != "" {
			args = append(args, v)
			where = append(where, strings.ReplaceAll(cond, "?", fmt.Sprintf("$%d", len(args))))
		}
	}
	add("d.document_type = ?", c.Query("tipo"))
	add("dt.categoria = ?", c.Query("categoria"))
	add("d.employee_id = ?::uuid", c.Query("employee"))
	add("d.supplier_id = ?::uuid", c.Query("supplier"))
	switch v := c.Query("vinculo"); v { // documentos da própria empresa × de terceirizadas × de fornecedores
	case "PROPRIA":
		where = append(where, "d.supplier_id IS NULL")
	case "TERCEIRIZADA", "FORNECEDOR":
		add("sup.tipo = ?", v)
	}
	add("d.batch_id = ?::uuid", c.Query("lote"))
	add("d.competencia = ?", c.Query("competencia"))
	if q := strings.TrimSpace(c.Query("q")); q != "" {
		args = append(args, q)
		n := len(args)
		where = append(where, fmt.Sprintf(`(f_unaccent(lower(coalesce(d.titulo,'')||' '||dt.nome||' '||coalesce(ef.nome,'')||' '||coalesce(d.nome_extraido,'')||' '||coalesce(d.nome_arquivo,''))) LIKE '%%'||f_unaccent(lower($%d))||'%%')`, n))
	}
	base := strings.Join(where, " AND ")
	listWhere := base
	if st := c.Query("status"); st != "" {
		args = append(args, strings.Split(st, ","))
		listWhere += fmt.Sprintf(" AND d.status = ANY($%d::text[])", len(args))
	}
	if cur := decodeCursor(c.Query("cursor")); len(cur) == 2 {
		args = append(args, cur[0], cur[1])
		listWhere += fmt.Sprintf(" AND (d.criado_em, d.id::text) < ($%d::timestamptz, $%d)", len(args)-1, len(args))
	}
	var raw, resumo []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `SELECT coalesce(json_agg(t),'[]') FROM (`+docRowSQL("$1")+` WHERE `+listWhere+fmt.Sprintf(` ORDER BY d.criado_em DESC, d.id DESC LIMIT %d) t`, limit+1), args...).Scan(&raw); err != nil {
			return err
		}
		// totais por status ignorando o filtro de status e o cursor (para as abas)
		cargs := args[:len(args)-(len(args)-countParams(base))]
		return tx.QueryRow(ctx, `SELECT json_build_object('todos', count(*), 'aprovados', count(*) FILTER (WHERE d.status IN ('AUTO_APROVADO','REVISADO')),
		  'revisao', count(*) FILTER (WHERE d.status='AGUARDANDO_REVISAO'), 'rejeitados', count(*) FILTER (WHERE d.status='REJEITADO'))
		  FROM documents d JOIN document_types dt ON dt.codigo=d.document_type LEFT JOIN employees ef ON ef.id=d.employee_id LEFT JOIN suppliers sup ON sup.id=d.supplier_id WHERE ($1::boolean IS NOT NULL) AND `+base, cargs...).Scan(&resumo)
	}) {
		return
	}
	out := pageOf(raw, limit, "criado_em", "id")
	out["resumo"] = jsonRaw(resumo)
	c.JSON(200, out)
}

// countParams devolve o maior $N usado na condição (para recortar os argumentos dos totais).
func countParams(cond string) int {
	max := 0
	for i := 1; i < 30; i++ {
		if strings.Contains(cond, fmt.Sprintf("$%d", i)) {
			max = i
		}
	}
	return max
}
