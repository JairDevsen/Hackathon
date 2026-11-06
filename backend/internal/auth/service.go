// Package auth: login com senha + 2FA por e-mail, JWT EdDSA, refresh rotativo, step-up e sessões.
package auth

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/agreser-innovations/citadel-ia/backend/internal/notify"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/jwtx"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5"
	"github.com/redis/go-redis/v9"
)

const (
	AccessTTL      = 12 * time.Minute
	StepUpTTL      = 5 * time.Minute
	TicketTTL      = 5 * time.Minute
	CodeTTL        = 10 * time.Minute
	ResendInterval = 60 * time.Second
	MaxAttempts    = 5
	RefreshMaxAge  = 7 * 24 * time.Hour
	RefreshIdle    = 12 * time.Hour
	TrustDays      = 30
)

type Service struct {
	DB    *database.DB
	Redis *redis.Client
	Mail  notify.Mailer
	JWT   *jwtx.Signer
	Cfg   *config.Config
}

type User struct {
	ID, Email, Nome, Role, Status string
	TenantID                      string
	Perms                         []string
	SenhaHash                     string
}

func sha(s string) string { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }

func randToken(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

func otp() string {
	n, _ := rand.Int(rand.Reader, big.NewInt(1000000))
	return fmt.Sprintf("%06d", n.Int64())
}

// EffectivePerms deriva as permissões do papel (+ as concedidas ao usuário).
func EffectivePerms(role string, extra []string) []string {
	switch role {
	case "MASTER":
		return []string{"tenants:gerir", "catalogo:gerir", "planos:gerir", "auditoria:global", "ia:operar", "master:gerir"}
	case "ADMIN_EMPRESA":
		return []string{"saude:ler", "usuarios:gerir", "config:gerir", "lotes:enviar", "revisao:fazer", "funcionarios:gerir", "auditoria:ler", "plano:gerir", "relatorios:ler"}
	}
	return append([]string{"lotes:enviar", "revisao:fazer", "funcionarios:gerir", "relatorios:ler"}, extra...)
}

func (s *Service) loadUserByEmail(ctx context.Context, email string) (*User, error) {
	var u User
	var tid *string
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		var t *string
		e := tx.QueryRow(ctx, `SELECT u.id, u.email, u.nome, u.role, u.status, u.tenant_id::text, u.perms, coalesce(u.senha_hash,'')
		  FROM users u WHERE lower(u.email)=lower($1)`, email).Scan(&u.ID, &u.Email, &u.Nome, &u.Role, &u.Status, &t, &u.Perms, &u.SenhaHash)
		tid = t
		return e
	})
	if tid != nil {
		u.TenantID = *tid
	}
	return &u, err
}

func (s *Service) loadUserByID(ctx context.Context, id string) (*User, error) {
	var u User
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		var t *string
		e := tx.QueryRow(ctx, `SELECT id, email, nome, role, status, tenant_id::text, perms, coalesce(senha_hash,'') FROM users WHERE id=$1`, id).
			Scan(&u.ID, &u.Email, &u.Nome, &u.Role, &u.Status, &t, &u.Perms, &u.SenhaHash)
		if t != nil {
			u.TenantID = *t
		}
		return e
	})
	return &u, err
}

func (s *Service) tenantActive(ctx context.Context, tid string) bool {
	if tid == "" {
		return true
	}
	ok := false
	s.DB.System(ctx, func(tx pgx.Tx) error {
		var st string
		if tx.QueryRow(ctx, `SELECT status FROM tenants WHERE id=$1`, tid).Scan(&st) == nil {
			ok = st == "ATIVO"
		}
		return nil
	})
	return ok
}

func (s *Service) audit(ctx context.Context, tenant, actor, role, acao string, dados any, ip, ua string) {
	s.DB.System(ctx, func(tx pgx.Tx) error {
		return audit.Log(ctx, tx, audit.Event{TenantID: tenant, Actor: actor, ActorRole: role, Acao: acao, Entidade: "auth", EntidadeID: actor, Dados: dados, IP: ip, UA: ua})
	})
}

// ---------- rate limit com bloqueio progressivo ----------

// Allow conta uma tentativa na janela; devolve false quando excedeu.
func (s *Service) Allow(ctx context.Context, key string, max int, window time.Duration) (bool, time.Duration) {
	k := "rl:" + key
	n, err := s.Redis.Incr(ctx, k).Result()
	if err != nil {
		return true, 0 // falha aberta no Redis: o login continua protegido por Argon2 + OTP
	}
	if n == 1 {
		s.Redis.Expire(ctx, k, window)
	}
	if int(n) > max {
		ttl, _ := s.Redis.TTL(ctx, k).Result()
		return false, ttl
	}
	return true, 0
}

func (s *Service) lockedFor(ctx context.Context, email string) time.Duration {
	ttl, _ := s.Redis.TTL(ctx, "lock:"+strings.ToLower(email)).Result()
	if ttl > 0 {
		return ttl
	}
	return 0
}

func (s *Service) registerFailure(ctx context.Context, u *User, email, ip, ua string) {
	k := "fail:" + strings.ToLower(email)
	n, _ := s.Redis.Incr(ctx, k).Result()
	s.Redis.Expire(ctx, k, 30*time.Minute)
	if n >= 5 {
		mins := 1 << uint(min(int(n)-5, 6)) // 1,2,4,...,64 min
		s.Redis.Set(ctx, "lock:"+strings.ToLower(email), 1, time.Duration(mins)*time.Minute)
		if n == 5 && u != nil && u.ID != "" {
			s.Mail.Send(u.Email, "Citadel IA · tentativas de acesso bloqueadas",
				fmt.Sprintf("Olá, %s.\n\nHouve %d tentativas de login com senha incorreta na sua conta (IP %s). O acesso foi bloqueado temporariamente.\nSe não foi você, troque sua senha.\n", u.Nome, n, ip))
		}
	}
}

// ---------- 2FA ----------

type ticket struct {
	UID      string    `json:"uid"`
	CodeHash string    `json:"h"`
	Attempts int       `json:"a"`
	CodeExp  time.Time `json:"ce"`
	ResendAt time.Time `json:"ra"`
	IP       string    `json:"ip"`
	UA       string    `json:"ua"`
	Purpose  string    `json:"p"` // login | stepup
	Trust    bool      `json:"t"`
}

func (s *Service) putTicket(ctx context.Context, tok string, t *ticket) error {
	b, _ := json.Marshal(t)
	return s.Redis.Set(ctx, "mfa:"+sha(tok), b, TicketTTL).Err()
}

func (s *Service) getTicket(ctx context.Context, tok string) (*ticket, error) {
	b, err := s.Redis.Get(ctx, "mfa:"+sha(tok)).Bytes()
	if err != nil {
		return nil, errors.New("ticket expirado ou inválido")
	}
	var t ticket
	json.Unmarshal(b, &t)
	return &t, nil
}

func (s *Service) sendCode(u *User, code, ip, ua, motivo string) error {
	body := fmt.Sprintf(`Olá, %s.

Seu código de verificação Citadel IA (%s) é: %s

Ele vale por 10 minutos e pode ser usado uma única vez.
Origem aproximada: IP %s · %s · %s

Se não foi você, ignore este e-mail e troque sua senha.
`, u.Nome, motivo, code, ip, shortUA(ua), time.Now().Format("02/01/2006 15:04"))
	return s.Mail.Send(u.Email, "Citadel IA · seu código de verificação", body)
}

func shortUA(ua string) string {
	for _, b := range []string{"Edg", "Firefox", "Chrome", "Safari"} {
		if strings.Contains(ua, b) {
			return b
		}
	}
	if ua == "" {
		return "navegador desconhecido"
	}
	return ua[:min(len(ua), 40)]
}

// StartTicket gera o código e o ticket opaco.
func (s *Service) StartTicket(ctx context.Context, u *User, purpose, ip, ua string, trust bool) (string, *ticket, error) {
	code := otp()
	tok := randToken(32)
	t := &ticket{UID: u.ID, CodeHash: sha(tok + ":" + code), CodeExp: time.Now().Add(CodeTTL), ResendAt: time.Now().Add(ResendInterval), IP: ip, UA: ua, Purpose: purpose, Trust: trust}
	if err := s.putTicket(ctx, tok, t); err != nil {
		return "", nil, err
	}
	motivo := "login"
	if purpose == "stepup" {
		motivo = "confirmação de ação sensível"
	}
	return tok, t, s.sendCode(u, code, ip, ua, motivo)
}

var ErrCode = errors.New("código inválido ou expirado")

// VerifyTicket confere o código (máx. 5 tentativas, uso único). Devolve o usuário.
func (s *Service) VerifyTicket(ctx context.Context, tok, code, purpose string) (*ticket, error) {
	t, err := s.getTicket(ctx, tok)
	if err != nil || t.Purpose != purpose {
		return nil, ErrCode
	}
	if t.Attempts >= MaxAttempts || time.Now().After(t.CodeExp) {
		s.Redis.Del(ctx, "mfa:"+sha(tok))
		return nil, ErrCode
	}
	if sha(tok+":"+strings.TrimSpace(code)) != t.CodeHash {
		t.Attempts++
		if t.Attempts >= MaxAttempts {
			s.Redis.Del(ctx, "mfa:"+sha(tok))
		} else {
			b, _ := json.Marshal(t)
			s.Redis.SetArgs(ctx, "mfa:"+sha(tok), b, redis.SetArgs{KeepTTL: true})
		}
		return t, ErrCode
	}
	s.Redis.Del(ctx, "mfa:"+sha(tok))
	return t, nil
}

func (s *Service) Resend(ctx context.Context, tok string) (time.Time, error) {
	t, err := s.getTicket(ctx, tok)
	if err != nil {
		return time.Time{}, err
	}
	if time.Now().Before(t.ResendAt) {
		return t.ResendAt, fmt.Errorf("aguarde %d s para reenviar", int(time.Until(t.ResendAt).Seconds())+1)
	}
	u, err := s.loadUserByID(ctx, t.UID)
	if err != nil {
		return time.Time{}, err
	}
	code := otp()
	t.CodeHash, t.CodeExp, t.ResendAt, t.Attempts = sha(tok+":"+code), time.Now().Add(CodeTTL), time.Now().Add(ResendInterval), 0
	if err := s.putTicket(ctx, tok, t); err != nil {
		return time.Time{}, err
	}
	return t.ResendAt, s.sendCode(u, code, t.IP, t.UA, "reenvio")
}

// ---------- sessões e tokens ----------

type Tokens struct {
	Access    string
	Refresh   string
	SessionID string
	ExpiresIn int
}

func (s *Service) accessFor(u *User, sid string, amr []string) (string, error) {
	return s.JWT.Sign(jwtx.Claims{
		TenantID: u.TenantID, Role: u.Role, Perms: EffectivePerms(u.Role, u.Perms), Session: sid, AMR: amr, Purpose: "access",
		RegisteredClaims: jwt.RegisteredClaims{Subject: u.ID, ID: randToken(8)},
	}, AccessTTL)
}

func (s *Service) NewSession(ctx context.Context, u *User, ip, ua string, amr []string) (*Tokens, error) {
	fam, rt := randToken(16), randToken(32)
	var sid string
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		var tid any
		if u.TenantID != "" {
			tid = u.TenantID
		}
		famID := ""
		if err := tx.QueryRow(ctx, `SELECT gen_random_uuid()::text`).Scan(&famID); err != nil {
			return err
		}
		if err := tx.QueryRow(ctx, `INSERT INTO sessions (user_id, tenant_id, familia, dispositivo, ip, expira_em)
		  VALUES ($1,$2,$3,$4,$5,$6) RETURNING id`, u.ID, tid, famID, shortUA(ua), ip, time.Now().Add(RefreshMaxAge)).Scan(&sid); err != nil {
			return err
		}
		_, err := tx.Exec(ctx, `INSERT INTO refresh_tokens (session_id, familia, hash, expira_em) VALUES ($1,$2,$3,$4)`, sid, famID, sha(rt), time.Now().Add(RefreshMaxAge))
		_, _ = tx.Exec(ctx, `UPDATE users SET ultimo_login=now() WHERE id=$1`, u.ID)
		_ = fam
		return err
	})
	if err != nil {
		return nil, err
	}
	at, err := s.accessFor(u, sid, amr)
	return &Tokens{Access: at, Refresh: rt, SessionID: sid, ExpiresIn: int(AccessTTL.Seconds())}, err
}

var ErrRefresh = errors.New("sessão expirada")

// Rotate troca o refresh token. Reapresentar um token já usado revoga toda a família (roubo).
func (s *Service) Rotate(ctx context.Context, old, ip, ua string) (*Tokens, *User, error) {
	var sid, fam string
	var used *time.Time
	var revoked *time.Time
	var exp, lastUse, sessExp time.Time
	var sessRevoked *time.Time
	var uid string
	err := s.DB.System(ctx, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT r.session_id, r.familia::text, r.usado_em, r.revogado_em, r.expira_em, s.ultimo_uso, s.expira_em, s.revogado_em, s.user_id
		  FROM refresh_tokens r JOIN sessions s ON s.id=r.session_id WHERE r.hash=$1`, sha(old)).
			Scan(&sid, &fam, &used, &revoked, &exp, &lastUse, &sessExp, &sessRevoked, &uid)
	})
	if err != nil {
		return nil, nil, ErrRefresh
	}
	if used != nil {
		s.revokeFamily(ctx, fam)
		u, _ := s.loadUserByID(ctx, uid)
		s.audit(ctx, u.TenantID, uid, u.Role, "REFRESH_REUSO_DETECTADO", map[string]any{"sessao": sid}, ip, ua)
		return nil, nil, ErrRefresh
	}
	now := time.Now()
	if revoked != nil || sessRevoked != nil || now.After(exp) || now.After(sessExp) || now.Sub(lastUse) > RefreshIdle {
		return nil, nil, ErrRefresh
	}
	u, err := s.loadUserByID(ctx, uid)
	if err != nil || u.Status != "ATIVO" || !s.tenantActive(ctx, u.TenantID) {
		return nil, nil, ErrRefresh
	}
	nrt := randToken(32)
	err = s.DB.System(ctx, func(tx pgx.Tx) error {
		ct, err := tx.Exec(ctx, `UPDATE refresh_tokens SET usado_em=now() WHERE hash=$1 AND usado_em IS NULL`, sha(old))
		if err != nil {
			return err
		}
		if ct.RowsAffected() == 0 {
			return ErrRefresh // corrida: outro refresh já consumiu este token
		}
		if _, err := tx.Exec(ctx, `INSERT INTO refresh_tokens (session_id, familia, hash, expira_em) VALUES ($1,$2,$3,$4)`, sid, fam, sha(nrt), sessExp); err != nil {
			return err
		}
		_, err = tx.Exec(ctx, `UPDATE sessions SET ultimo_uso=now(), ip=$2 WHERE id=$1`, sid, ip)
		return err
	})
	if err != nil {
		return nil, nil, ErrRefresh
	}
	at, err := s.accessFor(u, sid, []string{"pwd", "otp"})
	return &Tokens{Access: at, Refresh: nrt, SessionID: sid, ExpiresIn: int(AccessTTL.Seconds())}, u, err
}

func (s *Service) revokeFamily(ctx context.Context, fam string) {
	s.DB.System(ctx, func(tx pgx.Tx) error {
		rows, _ := tx.Query(ctx, `UPDATE sessions SET revogado_em=now() WHERE familia=$1::uuid AND revogado_em IS NULL RETURNING id::text`, fam)
		var ids []string
		for rows.Next() {
			var id string
			rows.Scan(&id)
			ids = append(ids, id)
		}
		rows.Close()
		tx.Exec(ctx, `UPDATE refresh_tokens SET revogado_em=now() WHERE familia=$1::uuid AND revogado_em IS NULL`, fam)
		for _, id := range ids {
			s.Redis.Set(ctx, "revoked:"+id, 1, AccessTTL+time.Minute)
		}
		return nil
	})
}

// RevokeSession encerra uma sessão (o access token em circulação cai no próximo request).
func (s *Service) RevokeSession(ctx context.Context, tx pgx.Tx, sid string) error {
	if _, err := tx.Exec(ctx, `UPDATE sessions SET revogado_em=now() WHERE id=$1 AND revogado_em IS NULL`, sid); err != nil {
		return err
	}
	tx.Exec(ctx, `UPDATE refresh_tokens SET revogado_em=now() WHERE session_id=$1 AND revogado_em IS NULL`, sid)
	return s.Redis.Set(ctx, "revoked:"+sid, 1, AccessTTL+time.Minute).Err()
}

// RevokeAllForUser: troca de senha ou desativação.
func (s *Service) RevokeAllForUser(ctx context.Context, tx pgx.Tx, uid string) error {
	rows, err := tx.Query(ctx, `UPDATE sessions SET revogado_em=now() WHERE user_id=$1 AND revogado_em IS NULL RETURNING id::text`, uid)
	if err != nil {
		return err
	}
	var ids []string
	for rows.Next() {
		var id string
		rows.Scan(&id)
		ids = append(ids, id)
	}
	rows.Close()
	tx.Exec(ctx, `UPDATE refresh_tokens SET revogado_em=now() WHERE session_id IN (SELECT id FROM sessions WHERE user_id=$1) AND revogado_em IS NULL`, uid)
	for _, id := range ids {
		s.Redis.Set(ctx, "revoked:"+id, 1, AccessTTL+time.Minute)
	}
	return nil
}

func (s *Service) IsRevoked(ctx context.Context, sid string) bool {
	n, _ := s.Redis.Exists(ctx, "revoked:"+sid).Result()
	return n > 0
}

// ---------- dispositivo confiável (30 dias) ----------

func (s *Service) trustCookieValue(uid string) string {
	exp := time.Now().Add(TrustDays * 24 * time.Hour).Unix()
	p := fmt.Sprintf("%s|%d", uid, exp)
	m := sha(s.Cfg.HMACHex + "|trust|" + p)
	return base64.RawURLEncoding.EncodeToString([]byte(p + "|" + m))
}

func (s *Service) trustValid(val, uid string) bool {
	raw, err := base64.RawURLEncoding.DecodeString(val)
	if err != nil {
		return false
	}
	parts := strings.Split(string(raw), "|")
	if len(parts) != 3 || parts[0] != uid {
		return false
	}
	var exp int64
	fmt.Sscan(parts[1], &exp)
	return time.Now().Unix() < exp && sha(s.Cfg.HMACHex+"|trust|"+parts[0]+"|"+parts[1]) == parts[2]
}
