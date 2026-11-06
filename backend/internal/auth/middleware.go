package auth

import (
	"strings"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/jwtx"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func jwtRegistered(sub string) jwt.RegisteredClaims {
	return jwt.RegisteredClaims{Subject: sub, ID: randToken(8)}
}

// Authenticate valida o access token (EdDSA), a sessão (não revogada) e injeta as claims.
func (s *Service) Authenticate() gin.HandlerFunc {
	return func(c *gin.Context) {
		h := c.GetHeader("Authorization")
		if !strings.HasPrefix(h, "Bearer ") {
			problem.Write(c, problem.Unauthorized("token ausente"))
			return
		}
		cl, err := s.JWT.Verify(strings.TrimPrefix(h, "Bearer "))
		if err != nil || cl.Purpose != "access" {
			problem.Write(c, problem.Unauthorized("token inválido ou expirado"))
			return
		}
		if s.IsRevoked(c.Request.Context(), cl.Session) {
			problem.Write(c, problem.Unauthorized("sessão encerrada"))
			return
		}
		c.Set(ctxClaims, cl)
		c.Next()
	}
}

func RequireRole(roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		cl := ClaimsOf(c)
		for _, r := range roles {
			if cl.Role == r {
				return
			}
		}
		problem.Write(c, problem.Forbidden("seu perfil não permite esta ação"))
	}
}

func HasPerm(cl *jwtx.Claims, p string) bool {
	for _, x := range cl.Perms {
		if x == p {
			return true
		}
	}
	return false
}

func RequirePerm(p string) gin.HandlerFunc {
	return func(c *gin.Context) {
		if !HasPerm(ClaimsOf(c), p) {
			problem.Write(c, problem.Forbidden("permissão necessária: "+p))
		}
	}
}

// RequireStepUp exige o cabeçalho X-Step-Up-Token (novo código por e-mail nos últimos 5 min).
func (s *Service) RequireStepUp() gin.HandlerFunc {
	return func(c *gin.Context) {
		cl := ClaimsOf(c)
		st, err := s.JWT.Verify(c.GetHeader("X-Step-Up-Token"))
		if err != nil || st.Purpose != "stepup" || st.Subject != cl.Subject || st.Session != cl.Session {
			c.Header("X-Step-Up-Required", "true")
			p := problem.New(401, "step-up-necessario", "confirme sua identidade com um novo código por e-mail")
			problem.Write(c, p)
		}
	}
}
