package http

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cpf"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// POST /employees/:id/documents/manual — lança um documento escrevendo as informações (formulário por tipo), sem imagem.
func (s *Server) createManualDocument(c *gin.Context) {
	var in struct {
		Tipo          string         `json:"tipo" binding:"required"`
		Campos        map[string]any `json:"campos"`
		Competencia   string         `json:"competencia"`
		DataDocumento string         `json:"data_documento"`
		ValidadeAte   string         `json:"validade_ate"`
		Observacao    string         `json:"observacao"`
	}
	if !bindJSON(c, &in) {
		return
	}
	for _, d := range []string{in.DataDocumento, in.ValidadeAte} {
		if d != "" {
			if _, err := time.Parse("2006-01-02", d); err != nil {
				problem.Write(c, problem.BadRequest("data inválida (use AAAA-MM-DD)"))
				return
			}
		}
	}
	if in.Competencia != "" {
		if _, err := time.Parse("2006-01", in.Competencia); err != nil {
			problem.Write(c, problem.BadRequest("competência inválida (use AAAA-MM)"))
			return
		}
	}
	emp := c.Param("id")
	var id string
	if !s.tx(c, func(ctx context.Context, tx pgx.Tx) error {
		var nome, escopo string
		var saudeTipo bool
		if err := tx.QueryRow(ctx, `SELECT nome, escopo, sensivel_saude FROM document_types WHERE codigo=$1`, in.Tipo).Scan(&nome, &escopo, &saudeTipo); err != nil {
			return problem.BadRequest("tipo documental desconhecido")
		}
		if escopo != "FUNCIONARIO" {
			return problem.BadRequest("este tipo é documento da empresa, não de funcionário")
		}
		if saudeTipo && !auth.HasPerm(auth.ClaimsOf(c), "saude:ler") {
			return problem.Forbidden("documento de saúde: permissão saude:ler necessária")
		}
		var unit *string
		var empNome string
		if err := tx.QueryRow(ctx, `SELECT unit_id::text, nome FROM employees WHERE id=$1`, emp).Scan(&unit, &empNome); err != nil {
			return problem.NotFound("funcionário não encontrado")
		}
		campos := map[string]any{}
		var linhas []string
		for k, v := range in.Campos {
			sv := strings.TrimSpace(fmt.Sprint(v))
			if v == nil || sv == "" || sv == "<nil>" {
				continue
			}
			if k == "cpf" { // nunca guardamos CPF em claro nos campos
				if d := cpf.Clean(sv); len(d) == 11 {
					campos[k] = cpf.Mask(d)
				}
				continue
			}
			campos[k] = v
			linhas = append(linhas, strings.ReplaceAll(k, "_", " ")+": "+sv)
		}
		if in.Observacao != "" {
			linhas = append(linhas, "observação: "+in.Observacao)
		}
		alertas := []map[string]any{}
		if in.ValidadeAte != "" {
			if v, _ := time.Parse("2006-01-02", in.ValidadeAte); v.Before(time.Now()) {
				alertas = append(alertas, map[string]any{"severidade": "erro", "codigo": "DOCUMENTO_VENCIDO", "mensagem": "Documento vencido em " + v.Format("02/01/2006")})
			}
		}
		cj, _ := json.Marshal(campos)
		aj, _ := json.Marshal(alertas)
		if err := tx.QueryRow(ctx, `INSERT INTO documents (tenant_id, employee_id, unit_id, document_type, titulo, competencia, data_documento, validade_ate, paginas, confianca, status, campos, alertas,
		    texto_ocr, nome_extraido, sensivel_saude, origem)
		  VALUES ($1,$2,$3,$4,$5,nullif($6,''),nullif($7,'')::date,nullif($8,'')::date,'{}',1,'REVISADO',$9,$10,$11,$12,$13,'MANUAL') RETURNING id::text`,
			tid(c), emp, unit, in.Tipo, nome+" (lançamento manual)", in.Competencia, in.DataDocumento, in.ValidadeAte, cj, aj, strings.Join(linhas, "\n"), empNome, saudeTipo).Scan(&id); err != nil {
			return err
		}
		if err := compliance.Recompute(ctx, tx, tid(c), emp); err != nil {
			return err
		}
		return s.audit(ctx, tx, c, "DOCUMENTO_LANCADO_MANUALMENTE", "document", id, map[string]any{"tipo": in.Tipo, "funcionario": emp})
	}) {
		return
	}
	c.JSON(201, gin.H{"id": id})
}
