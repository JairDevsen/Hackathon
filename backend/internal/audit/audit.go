// Package audit implementa a trilha de auditoria imutável encadeada por hash:
// hash = sha256(prev_hash || evento). O papel da aplicação só pode inserir (ver migração).
package audit

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"time"

	"github.com/jackc/pgx/v5"
)

type Event struct {
	TenantID   string // vazio = trilha global (Master)
	Actor      string
	ActorRole  string
	Acao       string
	Entidade   string
	EntidadeID string
	Dados      any
	IP, UA     string
}

const Genesis = "0000000000000000000000000000000000000000000000000000000000000000"

func normalize(v any) []byte {
	if v == nil {
		return []byte("{}")
	}
	raw, _ := json.Marshal(v)
	return canonical(raw)
}

// canonical reserializa com chaves ordenadas e números preservados (estável entre Go e jsonb).
func canonical(raw []byte) []byte {
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var x any
	if err := dec.Decode(&x); err != nil {
		return []byte("{}")
	}
	out, _ := json.Marshal(x)
	return out
}

func compute(prev string, tenant, actor, role, acao, ent, entID string, dados []byte, at time.Time) string {
	payload, _ := json.Marshal([]any{tenant, actor, role, acao, ent, entID, json.RawMessage(dados), at.UTC().Format("2006-01-02T15:04:05.000000Z")})
	h := sha256.Sum256(append([]byte(prev), payload...))
	return hex.EncodeToString(h[:])
}

// Log grava o evento dentro da transação do chamador (a auditoria faz parte do mesmo commit).
func Log(ctx context.Context, tx pgx.Tx, e Event) error {
	lockKey := "global"
	if e.TenantID != "" {
		lockKey = e.TenantID
	}
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtextextended($1,0))`, "audit:"+lockKey); err != nil {
		return err
	}
	prev := Genesis
	var tid any
	if e.TenantID != "" {
		tid = e.TenantID
	}
	err := tx.QueryRow(ctx, `SELECT hash FROM audit_log WHERE tenant_id IS NOT DISTINCT FROM $1::uuid ORDER BY id DESC LIMIT 1`, tid).Scan(&prev)
	if err != nil && err != pgx.ErrNoRows {
		return err
	}
	var actor any
	if e.Actor != "" {
		actor = e.Actor
	}
	dados := normalize(e.Dados)
	at := time.Now().UTC().Truncate(time.Microsecond)
	h := compute(prev, e.TenantID, e.Actor, e.ActorRole, e.Acao, e.Entidade, e.EntidadeID, dados, at)
	_, err = tx.Exec(ctx, `INSERT INTO audit_log (tenant_id, ator, ator_role, acao, entidade, entidade_id, dados, ip, ua, prev_hash, hash, criado_em)
	  VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`,
		tid, actor, e.ActorRole, e.Acao, e.Entidade, e.EntidadeID, dados, e.IP, e.UA, prev, h, at)
	return err
}

// Verify recalcula a cadeia de uma empresa ("" = global). Devolve (íntegra, id do primeiro elo quebrado, total).
func Verify(ctx context.Context, tx pgx.Tx, tenantID string) (bool, int64, int, error) {
	var tid any
	if tenantID != "" {
		tid = tenantID
	}
	rows, err := tx.Query(ctx, `SELECT id, coalesce(tenant_id::text,''), coalesce(ator::text,''), coalesce(ator_role,''), acao,
	  coalesce(entidade,''), coalesce(entidade_id,''), dados::text, prev_hash, hash, criado_em
	  FROM audit_log WHERE tenant_id IS NOT DISTINCT FROM $1::uuid ORDER BY id`, tid)
	if err != nil {
		return false, 0, 0, err
	}
	defer rows.Close()
	prev, n := Genesis, 0
	for rows.Next() {
		var id int64
		var t, a, r, ac, en, eid, dados, p, h string
		var at time.Time
		if err := rows.Scan(&id, &t, &a, &r, &ac, &en, &eid, &dados, &p, &h, &at); err != nil {
			return false, 0, n, err
		}
		n++
		if p != prev || compute(prev, t, a, r, ac, en, eid, canonical([]byte(dados)), at) != h {
			return false, id, n, nil
		}
		prev = h
	}
	return true, 0, n, rows.Err()
}
