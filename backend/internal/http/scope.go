package http

import (
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
)

// Escopo por unidade: um RH restrito a certas unidades só enxerga funcionários, documentos e lotes delas.
// As listagens já filtram; estes middlewares fecham o acesso direto por ID (detalhe, páginas, download, revisão,
// exportações), que antes ignorava a restrição e podia ser alcançado com IDs vistos em notificações.
// Sem restrição (Admin, RH sem unidades e Master em acesso de suporte aprovado) a checagem é imediata.

const (
	scopeEmployeeSQL = `SELECT EXISTS(SELECT 1 FROM employees e WHERE e.id=$1::uuid AND e.unit_id=ANY($2::uuid[]))`
	scopeDocumentSQL = `SELECT EXISTS(SELECT 1 FROM documents d LEFT JOIN employees e ON e.id=d.employee_id
	  WHERE d.id=$1::uuid AND (d.unit_id=ANY($2::uuid[]) OR e.unit_id=ANY($2::uuid[])))`
	scopeBatchSQL = `SELECT EXISTS(SELECT 1 FROM batches b WHERE b.id=$1::uuid AND b.unit_id=ANY($2::uuid[]))`
)

func (s *Server) scoped(param, query, notFound string) gin.HandlerFunc {
	return func(c *gin.Context) {
		units, _ := s.userScope(c)
		if len(units) == 0 {
			return
		}
		id := c.Param(param)
		allowed := false
		ctx := c.Request.Context()
		s.DB.Tenant(ctx, tid(c), func(tx pgx.Tx) error {
			var ok bool
			if err := tx.QueryRow(ctx, query, id, units).Scan(&ok); err == nil {
				allowed = ok
			}
			return nil
		})
		if !allowed {
			problem.Write(c, problem.NotFound(notFound)) // 404, não 403: não confirma que o recurso existe
		}
	}
}

func (s *Server) scopeEmployee(param string) gin.HandlerFunc {
	return s.scoped(param, scopeEmployeeSQL, "funcionário não encontrado")
}
func (s *Server) scopeDocument(param string) gin.HandlerFunc {
	return s.scoped(param, scopeDocumentSQL, "documento não encontrado")
}
func (s *Server) scopeBatch(param string) gin.HandlerFunc {
	return s.scoped(param, scopeBatchSQL, "lote não encontrado")
}
