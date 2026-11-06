// Package problem implementa application/problem+json (RFC 7807).
package problem

import (
	"encoding/json"
	"net/http"

	"github.com/gin-gonic/gin"
)

type Problem struct {
	Type     string         `json:"type"`
	Title    string         `json:"title"`
	Status   int            `json:"status"`
	Detail   string         `json:"detail,omitempty"`
	Instance string         `json:"instance,omitempty"`
	Code     string         `json:"code,omitempty"`
	Errors   map[string]any `json:"errors,omitempty"`
}

func (p *Problem) Error() string { return p.Title + ": " + p.Detail }

func New(status int, code, detail string) *Problem {
	return &Problem{Type: "https://citadel.ia/problems/" + code, Title: http.StatusText(status), Status: status, Detail: detail, Code: code}
}

func BadRequest(detail string) *Problem   { return New(400, "requisicao-invalida", detail) }
func Unauthorized(detail string) *Problem { return New(401, "nao-autenticado", detail) }
func Forbidden(detail string) *Problem    { return New(403, "sem-permissao", detail) }
func NotFound(detail string) *Problem     { return New(404, "nao-encontrado", detail) }
func Conflict(detail string) *Problem     { return New(409, "conflito", detail) }
func TooMany(detail string) *Problem      { return New(429, "muitas-tentativas", detail) }
func Internal() *Problem {
	return New(500, "erro-interno", "erro interno; informe o request_id ao suporte")
}

// Write envia o problema no content-type correto e aborta a cadeia.
func Write(c *gin.Context, p *Problem) {
	p.Instance = c.Request.URL.Path
	body, _ := json.Marshal(p)
	c.Abort()
	c.Data(p.Status, "application/problem+json", body)
}

// From converte qualquer erro em Problem (erros desconhecidos viram 500 sem vazar detalhe).
func From(err error) *Problem {
	if p, ok := err.(*Problem); ok {
		return p
	}
	return Internal()
}
