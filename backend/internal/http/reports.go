package http

import (
	"bytes"
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"strings"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/xuri/excelize/v2"
)

// ---------- conformidade / pendências ----------

// GET /risks — sinais documentais para triagem, com fonte e referência legal.
func (s *Server) listRisks(c *gin.Context) {
	units, saude := s.userScope(c)
	status := c.DefaultQuery("status", "ABERTO")
	if status != "ABERTO" && status != "IGNORADO" {
		problem.Write(c, problem.BadRequest("status inválido"))
		return
	}
	s.queryJSON(c, `SELECT json_build_object(
	  'resumo', (SELECT json_build_object('alto',count(*) FILTER (WHERE r.severidade='ALTO'), 'medio',count(*) FILTER (WHERE r.severidade='MEDIO'), 'baixo',count(*) FILTER (WHERE r.severidade='BAIXO'))
	    FROM risk_indicators r LEFT JOIN employees e ON e.id=r.employee_id LEFT JOIN documents d ON d.id=r.document_id
	    WHERE r.status='ABERTO' AND ($1::uuid[]='{}' OR coalesce(e.unit_id,d.unit_id)=ANY($1)) AND ($4::text='' OR r.employee_id::text=$4)),
	  'items', (SELECT coalesce(json_agg(t ORDER BY t.prioridade,t.criado_em DESC),'[]') FROM (
	    SELECT r.id, r.codigo, r.severidade, r.categoria, r.titulo,
	      CASE WHEN d.sensivel_saude AND NOT $3 THEN 'Documento de saúde: acesso restrito' ELSE r.descricao END AS descricao,
	      r.base_legal, r.referencia, r.status, r.justificativa, r.criado_em,
	      r.employee_id, CASE WHEN d.sensivel_saude AND NOT $3 THEN NULL ELSE e.nome END AS funcionario,
	      r.document_id, d.document_type, d.batch_id,
	      CASE r.severidade WHEN 'ALTO' THEN 0 WHEN 'MEDIO' THEN 1 ELSE 2 END AS prioridade
	    FROM risk_indicators r LEFT JOIN employees e ON e.id=r.employee_id LEFT JOIN documents d ON d.id=r.document_id
	    WHERE r.status=$2 AND ($1::uuid[]='{}' OR coalesce(e.unit_id,d.unit_id)=ANY($1)) AND ($4::text='' OR r.employee_id::text=$4)
	    ORDER BY prioridade,r.criado_em DESC LIMIT 200) t))`, units, status, saude, c.Query("employee"))
}

func (s *Server) ignoreRisk(c *gin.Context) {
	var in struct {
		Justificativa string `json:"justificativa" binding:"required,min=5"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if len(strings.TrimSpace(in.Justificativa)) < 5 {
		problem.Write(c, problem.BadRequest("informe uma justificativa com pelo menos 5 caracteres"))
		return
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE risk_indicators SET status='IGNORADO', justificativa=$2, atualizado_em=now() WHERE id=$1`, c.Param("id"), strings.TrimSpace(in.Justificativa))
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("indicador não encontrado")
		}
		return s.audit(ctx, tx, c, "RISCO_IGNORADO", "risk_indicator", c.Param("id"), map[string]any{"justificativa": in.Justificativa})
	}) {
		c.Status(204)
	}
}

func (s *Server) reopenRisk(c *gin.Context) {
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE risk_indicators SET status='ABERTO', atualizado_em=now() WHERE id=$1 AND status='IGNORADO'`, c.Param("id"))
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("indicador ignorado não encontrado")
		}
		return s.audit(ctx, tx, c, "RISCO_REABERTO", "risk_indicator", c.Param("id"), nil)
	}) {
		c.Status(204)
	}
}

const complianceSelect = `SELECT ci.id, ci.status, ci.referencia, ci.vence_em, ci.employee_id, e.nome AS funcionario, e.cpf_mascarado, p.nome AS cargo, u.nome AS unidade,
  dt.codigo AS tipo, dt.nome AS tipo_nome, dt.categoria, r.momento, ci.document_id, ci.justificativa_dispensa
  FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id
  LEFT JOIN employees e ON e.id=ci.employee_id LEFT JOIN positions p ON p.id=e.cargo_id LEFT JOIN units u ON u.id=e.unit_id`

func (s *Server) complianceWhere(c *gin.Context) (string, []any) {
	units, _ := s.userScope(c)
	args := []any{units}
	w := []string{`($1::uuid[]='{}' OR e.unit_id=ANY($1) OR ci.employee_id IS NULL)`}
	add := func(cond, v string) {
		if v != "" {
			args = append(args, v)
			w = append(w, strings.ReplaceAll(cond, "?", fmt.Sprintf("$%d", len(args))))
		}
	}
	if st := c.Query("status"); st != "" {
		args = append(args, strings.Split(st, ","))
		w = append(w, fmt.Sprintf("ci.status = ANY($%d::text[])", len(args)))
	} else {
		w = append(w, "ci.status IN ('PENDENTE','VENCIDO','A_VENCER')")
	}
	add("ci.employee_id = ?::uuid", c.Query("employee"))
	add("dt.codigo = ?", c.Query("type"))
	add("e.unit_id = ?::uuid", c.Query("unit"))
	add("e.cargo_id = ?::uuid", c.Query("cargo"))
	return strings.Join(w, " AND "), args
}

func (s *Server) listCompliance(c *gin.Context) {
	where, args := s.complianceWhere(c)
	limit := limitOf(c, 50, 500)
	if cur := decodeCursor(c.Query("cursor")); len(cur) == 2 {
		args = append(args, cur[0], cur[1])
		where += fmt.Sprintf(" AND (coalesce(e.nome,''), ci.id::text) > ($%d, $%d)", len(args)-1, len(args))
	}
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT coalesce(json_agg(t),'[]') FROM (`+complianceSelect+` WHERE `+where+
			fmt.Sprintf(` ORDER BY coalesce(e.nome,''), ci.id LIMIT %d) t`, limit+1), args...).Scan(&raw)
	}) {
		return
	}
	var items []map[string]any
	json.Unmarshal(raw, &items)
	out := gin.H{"items": items, "next_cursor": nil}
	if len(items) > limit {
		items = items[:limit]
		last := items[len(items)-1]
		nome := fmt.Sprint(last["funcionario"])
		if last["funcionario"] == nil {
			nome = ""
		}
		out["items"] = items
		out["next_cursor"] = encodeCursor(nome, fmt.Sprint(last["id"]))
	}
	var sum []byte
	s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		sw, sa := s.complianceWhere(c)
		_ = sw
		_ = sa
		sum, _ = database.JSON(ctx, tx, `SELECT json_build_object('ok', count(*) FILTER (WHERE status='OK'), 'pendente', count(*) FILTER (WHERE status='PENDENTE'),
		  'vencido', count(*) FILTER (WHERE status='VENCIDO'), 'a_vencer', count(*) FILTER (WHERE status='A_VENCER'), 'dispensado', count(*) FILTER (WHERE status='DISPENSADO')) FROM compliance_items`)
		return nil
	})
	var resumo any
	json.Unmarshal(sum, &resumo)
	out["resumo"] = resumo
	c.JSON(200, out)
}

func (s *Server) dispenseItem(c *gin.Context) {
	var in struct {
		Justificativa string `json:"justificativa" binding:"required,min=5"`
		Reativar      bool   `json:"reativar"`
	}
	if !bindJSON(c, &in) {
		return
	}
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		st, just := "DISPENSADO", in.Justificativa
		if in.Reativar {
			st = "PENDENTE"
		}
		ct, err := tx.Exec(ctx, `UPDATE compliance_items SET status=$2, justificativa_dispensa=$3, atualizado_em=now() WHERE id=$1`, c.Param("id"), st, just)
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return problem.NotFound("item não encontrado")
		}
		return s.audit(ctx, tx, c, "ITEM_"+st, "compliance_item", c.Param("id"), map[string]any{"justificativa": in.Justificativa})
	}) {
		c.Status(204)
	}
}

// POST /compliance/cobrar — envia e-mail aos gestores com as pendências do funcionário/unidade.
func (s *Server) chargePending(c *gin.Context) {
	var in struct {
		EmployeeID string `json:"employee_id"`
		UnitID     string `json:"unit_id"`
	}
	if !bindJSON(c, &in) {
		return
	}
	var lines []string
	var emails []string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		rows, err := tx.Query(ctx, `SELECT coalesce(e.nome,'(empresa)'), dt.nome, ci.referencia, ci.status FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id
		  JOIN document_types dt ON dt.id=r.document_type_id LEFT JOIN employees e ON e.id=ci.employee_id
		  WHERE ci.status IN ('PENDENTE','VENCIDO') AND ($1='' OR ci.employee_id=$1::uuid) AND ($2='' OR e.unit_id=$2::uuid) ORDER BY 1 LIMIT 200`, in.EmployeeID, in.UnitID)
		if err != nil {
			return err
		}
		for rows.Next() {
			var a, b, d, st string
			rows.Scan(&a, &b, &d, &st)
			lines = append(lines, fmt.Sprintf("- %s · %s (%s) — %s", a, b, d, st))
		}
		rows.Close()
		er, _ := tx.Query(ctx, `SELECT email FROM users WHERE status='ATIVO' AND role IN ('ADMIN_EMPRESA','RH') AND ($1='' OR role='ADMIN_EMPRESA' OR cardinality(unit_scope)=0 OR $1::uuid=ANY(unit_scope))`, in.UnitID)
		for er.Next() {
			var e string
			er.Scan(&e)
			emails = append(emails, e)
		}
		er.Close()
		return s.audit(ctx, tx, c, "COBRANCA_ENVIADA", "compliance", in.EmployeeID, map[string]any{"itens": len(lines)})
	}) {
		return
	}
	if len(lines) == 0 {
		c.JSON(200, gin.H{"enviados": 0})
		return
	}
	for _, e := range emails {
		s.Mail.Send(e, "Citadel IA · pendências documentais", "Pendências documentais para regularização:\n\n"+strings.Join(lines, "\n")+"\n")
	}
	c.JSON(200, gin.H{"enviados": len(emails), "itens": len(lines)})
}

func (s *Server) calendar(c *gin.Context) {
	month := c.DefaultQuery("month", "")
	if month == "" {
		month = "now"
	}
	s.queryJSON(c, `SELECT coalesce(json_agg(t ORDER BY t.vence_em),'[]') FROM (
	  SELECT ci.id, ci.vence_em, ci.status, dt.nome AS tipo_nome, dt.codigo AS tipo, e.nome AS funcionario, e.id AS employee_id
	  FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id LEFT JOIN employees e ON e.id=ci.employee_id
	  WHERE ci.vence_em IS NOT NULL AND ci.status IN ('OK','A_VENCER','VENCIDO')
	    AND date_trunc('month', ci.vence_em) = date_trunc('month', CASE WHEN $1='now' THEN now() ELSE ($1||'-01')::date END)) t`, month)
}

// ---------- notificações ----------

func (s *Server) listNotifications(c *gin.Context) {
	cl := auth.ClaimsOf(c)
	s.queryJSON(c, `SELECT json_build_object('nao_lidas', (SELECT count(*) FROM notifications WHERE lida_em IS NULL AND (user_id IS NULL OR user_id=$1)),
	  'itens', (SELECT coalesce(json_agg(n),'[]') FROM (SELECT id, tipo, titulo, link, lida_em, criado_em FROM notifications WHERE user_id IS NULL OR user_id=$1 ORDER BY criado_em DESC LIMIT 30) n))`, cl.Subject)
}

func (s *Server) readNotification(c *gin.Context) {
	cl := auth.ClaimsOf(c)
	if s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		if c.Param("id") == "all" {
			_, err := tx.Exec(ctx, `UPDATE notifications SET lida_em=now() WHERE lida_em IS NULL AND (user_id IS NULL OR user_id=$1)`, cl.Subject)
			return err
		}
		_, err := tx.Exec(ctx, `UPDATE notifications SET lida_em=now() WHERE id=$1 AND (user_id IS NULL OR user_id=$2)`, c.Param("id"), cl.Subject)
		return err
	}) {
		c.Status(204)
	}
}

// ---------- métricas ----------

func (s *Server) metricsOverview(c *gin.Context) {
	units, _ := s.userScope(c)
	s.queryJSON(c, `WITH scoped_employees AS (
	  SELECT e.* FROM employees e WHERE $2::uuid[]='{}' OR e.unit_id=ANY($2)
	), scoped_documents AS (
	  SELECT d.* FROM documents d LEFT JOIN employees e ON e.id=d.employee_id
	  WHERE $2::uuid[]='{}' OR d.unit_id=ANY($2) OR e.unit_id=ANY($2)
	), scoped_compliance AS (
	  SELECT ci.* FROM compliance_items ci LEFT JOIN employees e ON e.id=ci.employee_id
	  WHERE $2::uuid[]='{}' OR e.unit_id=ANY($2) OR ci.employee_id IS NULL
	), scoped_batches AS (
	  SELECT b.* FROM batches b WHERE $2::uuid[]='{}' OR b.unit_id=ANY($2)
	), scoped_risks AS (
	  SELECT r.* FROM risk_indicators r LEFT JOIN employees e ON e.id=r.employee_id LEFT JOIN documents d ON d.id=r.document_id
	  WHERE $2::uuid[]='{}' OR coalesce(e.unit_id,d.unit_id)=ANY($2)
	) SELECT json_build_object(
	 'conformidade_pct', (SELECT round(100.0*count(*) FILTER (WHERE status='OK')/nullif(count(*) FILTER (WHERE status<>'DISPENSADO'),0),1) FROM scoped_compliance),
	 'funcionarios_ativos', (SELECT count(*) FROM scoped_employees WHERE status='ATIVO'),
	 'funcionarios_com_pendencia', (SELECT count(DISTINCT employee_id) FROM scoped_compliance WHERE status IN ('PENDENTE','VENCIDO') AND employee_id IS NOT NULL),
	 'vencendo_30d', (SELECT count(*) FROM scoped_compliance WHERE status='A_VENCER' AND vence_em <= current_date+30),
	 'vencidos', (SELECT count(*) FROM scoped_compliance WHERE status='VENCIDO'),
	 'pendentes', (SELECT count(*) FROM scoped_compliance WHERE status='PENDENTE'),
	 'aguardando_revisao', (SELECT count(*) FROM scoped_documents WHERE status='AGUARDANDO_REVISAO'),
	 'riscos', (SELECT json_build_object('alto', count(*) FILTER (WHERE severidade='ALTO'), 'medio', count(*) FILTER (WHERE severidade='MEDIO'), 'baixo', count(*) FILTER (WHERE severidade='BAIXO'), 'funcionarios', count(DISTINCT employee_id)) FROM scoped_risks WHERE status='ABERTO'),
	 'riscos_por_codigo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT codigo, max(titulo) AS titulo, max(severidade) AS severidade, count(*) AS n FROM scoped_risks WHERE status='ABERTO' GROUP BY codigo ORDER BY (max(severidade)='ALTO') DESC, count(*) DESC LIMIT 5) x),
	 'documentos_total', (SELECT count(*) FROM scoped_documents WHERE status NOT IN ('REJEITADO','SUBSTITUIDO')),
	 'lotes_total', (SELECT count(*) FROM scoped_batches),
	 'documentos_por_tipo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT dt.nome AS tipo, count(*) AS n FROM scoped_documents d JOIN document_types dt ON dt.codigo=d.document_type WHERE d.status NOT IN ('REJEITADO','SUBSTITUIDO') GROUP BY 1 ORDER BY 2 DESC) x),
	 'sem_vinculo', (SELECT count(*) FROM scoped_documents WHERE status='AGUARDANDO_REVISAO' AND motivos_revisao ? 'SEM_VINCULO'),
	 'pre_cadastros', (SELECT count(*) FROM scoped_employees WHERE pre_cadastro),
	 'documentos_ilegiveis', (SELECT count(*) FROM scoped_documents WHERE status='AGUARDANDO_REVISAO' AND (motivos_revisao ? 'PAGINA_ILEGIVEL' OR motivos_revisao ? 'IMAGEM_BORRADA' OR motivos_revisao ? 'TIPO_OUTRO')),
	 'riscos_abertos', (SELECT count(*) FROM scoped_risks WHERE status='ABERTO'),
	 'revisoes_mes', (SELECT count(*) FROM reviews r JOIN scoped_documents d ON d.id=r.document_id WHERE r.criado_em >= date_trunc('month', now())),
	 'armazenamento', (SELECT json_build_object('usado', bytes_usados, 'cota', quota_bytes) FROM tenants WHERE id=$1),
	 'paginas_mes', (SELECT json_build_object('usado', coalesce((SELECT paginas FROM usage_monthly WHERE mes=to_char(now(),'YYYY-MM')),0), 'limite', quota_paginas_mes) FROM tenants WHERE id=$1),
	 'a_vencer_por_tipo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT dt.nome AS tipo, count(*) AS n FROM scoped_compliance ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id
	    WHERE ci.status='A_VENCER' GROUP BY 1 ORDER BY 2 DESC LIMIT 5) x),
	 'vencido_por_tipo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT dt.nome AS tipo, count(*) AS n FROM scoped_compliance ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id
	    WHERE ci.status='VENCIDO' GROUP BY 1 ORDER BY 2 DESC LIMIT 5) x),
	 'lotes_com_pendencias', (SELECT count(*) FROM scoped_batches WHERE status='PROCESSADO_COM_PENDENCIAS'),
	 'lotes_falhos', (SELECT count(*) FROM scoped_batches WHERE status='FALHOU'),
	 'nao_conformidades', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT nc->>'codigo' AS codigo, max(nc->>'descricao') AS descricao, count(*) AS n
	    FROM scoped_documents d, jsonb_array_elements(d.nao_conformidades) nc WHERE d.status NOT IN ('REJEITADO','SUBSTITUIDO') GROUP BY 1 ORDER BY 3 DESC LIMIT 10) x))`, tid(c), units)
}

func (s *Server) metricsCompliance(c *gin.Context) {
	units, _ := s.userScope(c)
	s.queryJSON(c, `SELECT json_build_object(
	 'por_unidade', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT coalesce(u.nome,'Sem unidade') AS nome, round(100.0*count(*) FILTER (WHERE ci.status='OK')/nullif(count(*) FILTER (WHERE ci.status<>'DISPENSADO'),0),1) AS pct, count(*) AS itens
	    FROM compliance_items ci JOIN employees e ON e.id=ci.employee_id LEFT JOIN units u ON u.id=e.unit_id WHERE $1::uuid[]='{}' OR e.unit_id=ANY($1) GROUP BY 1 ORDER BY 1) x),
	 'por_cargo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT coalesce(p.nome,'Sem cargo') AS nome, round(100.0*count(*) FILTER (WHERE ci.status='OK')/nullif(count(*) FILTER (WHERE ci.status<>'DISPENSADO'),0),1) AS pct, count(*) AS itens
	    FROM compliance_items ci JOIN employees e ON e.id=ci.employee_id LEFT JOIN positions p ON p.id=e.cargo_id WHERE $1::uuid[]='{}' OR e.unit_id=ANY($1) GROUP BY 1 ORDER BY 1) x),
	 'pendencias_por_tipo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT dt.nome AS tipo, count(*) FILTER (WHERE ci.status='PENDENTE') AS pendente, count(*) FILTER (WHERE ci.status='VENCIDO') AS vencido, count(*) FILTER (WHERE ci.status='A_VENCER') AS a_vencer
	    FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id LEFT JOIN employees e ON e.id=ci.employee_id
	    WHERE ci.status IN ('PENDENTE','VENCIDO','A_VENCER') AND ($1::uuid[]='{}' OR e.unit_id=ANY($1) OR ci.employee_id IS NULL) GROUP BY 1 ORDER BY count(*) DESC LIMIT 12) x))`, units)
}

func (s *Server) metricsProcessing(c *gin.Context) {
	s.queryJSON(c, `SELECT json_build_object(
	 'volume_mensal', (SELECT coalesce(json_agg(x ORDER BY x.mes),'[]') FROM (SELECT mes, paginas, docs, revisoes FROM usage_monthly ORDER BY mes DESC LIMIT 12) x),
	 'tempo_medio_lote_seg', (SELECT round(extract(epoch FROM avg(concluido_em-criado_em))::numeric,1) FROM batches WHERE concluido_em IS NOT NULL AND status LIKE 'PROCESSADO%' AND criado_em > now()-interval '90 days'),
	 'auto_vs_revisado', (SELECT coalesce(json_agg(x ORDER BY x.mes),'[]') FROM (SELECT to_char(criado_em,'YYYY-MM') AS mes, count(*) FILTER (WHERE status='AUTO_APROVADO') AS auto,
	    count(*) FILTER (WHERE status IN ('REVISADO','AGUARDANDO_REVISAO')) AS revisado FROM documents GROUP BY 1 ORDER BY 1 DESC LIMIT 12) x),
	 'produtividade_revisao', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT u.nome AS revisor, count(*) AS revisoes, round(avg(r.duracao_ms)/1000.0,1) AS tempo_medio_seg,
	    round(100.0*count(*) FILTER (WHERE r.acao IN ('CORRIGIR','MUDAR_TIPO'))/count(*),1) AS taxa_correcao
	    FROM reviews r LEFT JOIN users u ON u.id=r.revisor_id WHERE r.criado_em > now()-interval '90 days' GROUP BY 1 ORDER BY 2 DESC) x),
	 'acuracia_por_tipo', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT d.document_type AS tipo, count(*) AS revisoes, round(100.0*count(*) FILTER (WHERE r.acao='CONFIRMAR')/count(*),1) AS acertos_pct
	    FROM reviews r JOIN documents d ON d.id=r.document_id WHERE r.acao IN ('CONFIRMAR','CORRIGIR','MUDAR_TIPO') GROUP BY 1 ORDER BY 2 DESC) x))`)
}

func (s *Server) metricsStorage(c *gin.Context) {
	s.queryJSON(c, `SELECT json_build_object(
	 'resumo', (SELECT row_to_json(t) FROM (SELECT bytes_usados AS usado, quota_bytes AS cota FROM tenants WHERE id=$1) t),
	 'crescimento', (SELECT coalesce(json_agg(x ORDER BY x.mes),'[]') FROM (SELECT to_char(criado_em,'YYYY-MM') AS mes, sum(bytes) FILTER (WHERE tipo='UPLOAD') AS uploads, sum(bytes) FILTER (WHERE tipo='DERIVADO') AS derivados
	    FROM storage_events GROUP BY 1 ORDER BY 1 DESC LIMIT 12) x),
	 'maiores_lotes', (SELECT coalesce(json_agg(x),'[]') FROM (SELECT id, arquivo_original, bytes, criado_em FROM batches ORDER BY bytes DESC LIMIT 5) x))`, tid(c))
}

// metricsFinops: consumo real por camada do funil (Camada 0 cache SHA-256 … Camada 3 visão).
func (s *Server) metricsFinops(c *gin.Context) {
	s.queryJSON(c, `SELECT coalesce(json_agg(x ORDER BY x.camada),'[]') FROM (
	  SELECT left(finops->>'camada_roteamento', 8) AS camada, count(*) AS documentos,
	    coalesce(sum((finops->>'tokens_consumidos')::bigint),0) AS tokens_consumidos, coalesce(sum((finops->>'tokens_economizados')::bigint),0) AS tokens_economizados,
	    round(avg((finops->>'economia_estimada_pct')::numeric),1) AS economia_media_pct
	  FROM documents WHERE finops IS NOT NULL AND finops ? 'camada_roteamento' GROUP BY 1) x`)
}

// ---------- logs operacionais (admin) ----------

func (s *Server) logs(c *gin.Context) {
	switch c.Param("tipo") {
	case "armazenamento":
		s.queryJSON(c, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT se.id, se.tipo, se.bytes, se.objeto, se.criado_em, u.nome AS por FROM storage_events se LEFT JOIN users u ON u.id=se.por ORDER BY se.criado_em DESC LIMIT 200) t`)
	case "processamento":
		s.queryJSON(c, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT b.id, b.arquivo_original, b.status, b.total_paginas, b.tentativas, b.erro, b.criado_em, b.concluido_em,
		  round(extract(epoch FROM (b.concluido_em-b.criado_em))::numeric,1) AS duracao_seg, (SELECT count(*) FROM documents d WHERE d.batch_id=b.id) AS documentos,
		  (SELECT count(*) FROM pages p WHERE p.batch_id=b.id AND p.proc_status='FALHOU') AS paginas_falhas FROM batches b ORDER BY b.criado_em DESC LIMIT 200) t`)
	case "organizacao":
		s.queryJSON(c, `SELECT json_build_object(
		  'vinculos', (SELECT json_build_object('automaticos', count(*) FILTER (WHERE NOT (motivos_revisao ? 'SEM_VINCULO') AND employee_id IS NOT NULL), 'sem_vinculo', count(*) FILTER (WHERE employee_id IS NULL AND motivos_revisao ? 'SEM_VINCULO')) FROM documents),
		  'manuais', (SELECT count(*) FROM reviews WHERE acao='VINCULAR'),
		  'divisoes', (SELECT count(*) FROM reviews WHERE acao='DIVIDIR'), 'juncoes', (SELECT count(*) FROM reviews WHERE acao='JUNTAR'),
		  'eventos', (SELECT coalesce(json_agg(t),'[]') FROM (SELECT r.id, r.acao, r.criado_em, u.nome AS por, r.document_id FROM reviews r LEFT JOIN users u ON u.id=r.revisor_id WHERE r.acao IN ('VINCULAR','DIVIDIR','JUNTAR','MUDAR_TIPO') ORDER BY r.criado_em DESC LIMIT 100) t))`)
	case "revisao":
		s.queryJSON(c, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT r.id, r.acao, r.criado_em, r.duracao_ms, u.nome AS por, d.document_type, r.document_id, r.antes, r.depois
		  FROM reviews r LEFT JOIN users u ON u.id=r.revisor_id JOIN documents d ON d.id=r.document_id ORDER BY r.criado_em DESC LIMIT 200) t`)
	default:
		problem.Write(c, problem.NotFound("log desconhecido"))
	}
}

// ---------- auditoria da empresa ----------

func (s *Server) listAudit(c *gin.Context) {
	cl := auth.ClaimsOf(c)
	limit := limitOf(c, 50, 200)
	args := []any{cl.Role == "RH", cl.Subject, limit + 1}
	where := `($1 = false OR a.ator = $2::uuid)`
	add := func(cond, v string) {
		if v != "" {
			args = append(args, v)
			where += " AND " + strings.ReplaceAll(cond, "?", fmt.Sprintf("$%d", len(args)))
		}
	}
	add("a.entidade = ?", c.Query("entity"))
	add("a.ator = ?::uuid", c.Query("actor"))
	add("a.criado_em >= ?::timestamptz", c.Query("from"))
	add("a.criado_em <= ?::timestamptz", c.Query("to"))
	add("a.acao ILIKE '%'||?||'%'", c.Query("acao"))
	if cur := decodeCursor(c.Query("cursor")); len(cur) >= 1 {
		add("a.id < ?::bigint", cur[0])
	}
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT coalesce(json_agg(t),'[]') FROM (SELECT a.id, a.acao, a.entidade, a.entidade_id, a.dados, a.ip, a.criado_em, a.ator_role, u.nome AS ator_nome
		  FROM audit_log a LEFT JOIN users u ON u.id=a.ator WHERE `+where+` ORDER BY a.id DESC LIMIT $3) t`, args...).Scan(&raw)
	}) {
		return
	}
	c.JSON(200, pageOf(raw, limit, "id"))
}

// ---------- relatórios CSV/XLSX ----------

func (s *Server) report(c *gin.Context) {
	var sql string
	args := []any{}
	switch c.Param("tipo") {
	case "conformidade":
		sql = `SELECT coalesce(u.nome,'Sem unidade') AS unidade, coalesce(p.nome,'Sem cargo') AS cargo, count(DISTINCT e.id) AS funcionarios,
		  count(*) FILTER (WHERE ci.status='OK') AS ok, count(*) FILTER (WHERE ci.status='PENDENTE') AS pendente, count(*) FILTER (WHERE ci.status='VENCIDO') AS vencido,
		  count(*) FILTER (WHERE ci.status='A_VENCER') AS a_vencer,
		  round(100.0*count(*) FILTER (WHERE ci.status='OK')/nullif(count(*) FILTER (WHERE ci.status<>'DISPENSADO'),0),1) AS conformidade_pct
		  FROM compliance_items ci JOIN employees e ON e.id=ci.employee_id LEFT JOIN units u ON u.id=e.unit_id LEFT JOIN positions p ON p.id=e.cargo_id GROUP BY 1,2 ORDER BY 1,2`
	case "pendencias":
		where, a := s.complianceWhere(c)
		sql, args = `SELECT e.nome AS funcionario, e.cpf_mascarado AS cpf, p.nome AS cargo, u.nome AS unidade, dt.nome AS documento, ci.referencia, ci.status, ci.vence_em
		  FROM compliance_items ci JOIN requirements r ON r.id=ci.requirement_id JOIN document_types dt ON dt.id=r.document_type_id
		  LEFT JOIN employees e ON e.id=ci.employee_id LEFT JOIN positions p ON p.id=e.cargo_id LEFT JOIN units u ON u.id=e.unit_id WHERE `+where+` ORDER BY e.nome, dt.nome`, a
	case "nao-conformidades":
		sql = `SELECT e.nome AS funcionario, dt.nome AS documento, d.competencia, nc->>'codigo' AS codigo, nc->>'descricao' AS descricao, d.criado_em
		  FROM documents d JOIN document_types dt ON dt.codigo=d.document_type LEFT JOIN employees e ON e.id=d.employee_id, jsonb_array_elements(d.nao_conformidades) nc
		  WHERE d.status NOT IN ('REJEITADO','SUBSTITUIDO') ORDER BY d.criado_em DESC`
	case "armazenamento":
		sql = `SELECT to_char(criado_em,'YYYY-MM') AS mes, tipo, count(*) AS eventos, sum(bytes) AS bytes FROM storage_events GROUP BY 1,2 ORDER BY 1 DESC,2`
	default:
		problem.Write(c, problem.NotFound("relatório desconhecido"))
		return
	}
	var raw []byte
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var e error
		raw, e = database.JSON(ctx, tx, `SELECT coalesce(json_agg(t),'[]') FROM (`+sql+`) t`, args...)
		return e
	}) {
		return
	}
	var rows []map[string]any
	json.Unmarshal(raw, &rows)
	writeTable(c, c.Param("tipo"), c.DefaultQuery("formato", "csv"), rows)
}

func writeTable(c *gin.Context, name, formato string, rows []map[string]any) {
	var cols []string
	if len(rows) > 0 {
		for k := range rows[0] {
			cols = append(cols, k)
		}
		sort.Strings(cols)
	}
	cell := func(v any) string {
		if v == nil {
			return ""
		}
		if f, ok := v.(float64); ok && f == float64(int64(f)) {
			return fmt.Sprint(int64(f))
		}
		return fmt.Sprint(v)
	}
	if formato == "xlsx" {
		x := excelize.NewFile()
		sh := x.GetSheetName(0)
		for i, col := range cols {
			n, _ := excelize.CoordinatesToCellName(i+1, 1)
			x.SetCellValue(sh, n, col)
		}
		for r, row := range rows {
			for i, col := range cols {
				n, _ := excelize.CoordinatesToCellName(i+1, r+2)
				x.SetCellValue(sh, n, cell(row[col]))
			}
		}
		var b bytes.Buffer
		x.Write(&b)
		c.Header("Content-Disposition", fmt.Sprintf(`attachment; filename="%s.xlsx"`, name))
		c.Data(http.StatusOK, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b.Bytes())
		return
	}
	var b bytes.Buffer
	b.WriteString("\ufeff")
	w := csv.NewWriter(&b)
	w.Comma = ';'
	w.Write(cols)
	for _, row := range rows {
		rec := make([]string, len(cols))
		for i, col := range cols {
			rec[i] = cell(row[col])
		}
		w.Write(rec)
	}
	w.Flush()
	c.Header("Content-Disposition", fmt.Sprintf(`attachment; filename="%s.csv"`, name))
	c.Data(http.StatusOK, "text/csv; charset=utf-8", b.Bytes())
}

func encodeCursor(parts ...string) string {
	return base64RawURL(strings.Join(parts, "|"))
}
