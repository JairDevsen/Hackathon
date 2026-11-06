package database_test

import (
	"context"
	"crypto/rand"
	"fmt"
	"os"
	"testing"

	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
	"github.com/jackc/pgx/v5"
)

// Garante que nenhuma query vaza dados entre empresas (RLS) e que a auditoria é imutável.
// Requer DATABASE_URL (papel citadel_app) com o schema migrado; é pulado quando ausente.
func TestIsolamentoEntreEmpresas(t *testing.T) {
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		t.Skip("DATABASE_URL não definida")
	}
	ctx := context.Background()
	db, err := database.Connect(ctx, url)
	if err != nil {
		t.Skip("banco indisponível: ", err)
	}
	defer db.Pool.Close()
	mk := func(cnpj string) (id string) {
		err := db.System(ctx, func(tx pgx.Tx) error {
			return tx.QueryRow(ctx, `INSERT INTO tenants (cnpj,razao_social,porte,quota_bytes,quota_paginas_mes,dek_wrapped) VALUES ($1,'Teste','PEQUENA',1,1,'\x00') RETURNING id::text`, cnpj).Scan(&id)
		})
		if err != nil {
			t.Fatal(err)
		}
		return
	}
	rnd := make([]byte, 4)
	rand.Read(rnd)
	a, b := mk(fmt.Sprintf("T%x1", rnd)), mk(fmt.Sprintf("T%x2", rnd))
	defer db.System(ctx, func(tx pgx.Tx) error {
		_, e := tx.Exec(ctx, `DELETE FROM tenants WHERE id IN ($1,$2)`, a, b)
		return e
	})
	ins := func(tid, hash string) error {
		return db.Tenant(ctx, tid, func(tx pgx.Tx) error {
			_, e := tx.Exec(ctx, `INSERT INTO employees (tenant_id,cpf_cifrado,cpf_hash,cpf_mascarado,nome) VALUES ($1,'\x00',$2,'x','Fulano')`, tid, hash)
			return e
		})
	}
	if err := ins(a, "ha"); err != nil {
		t.Fatal(err)
	}
	if err := ins(b, "hb"); err != nil {
		t.Fatal(err)
	}
	count := func(tid string) (n int) {
		db.Tenant(ctx, tid, func(tx pgx.Tx) error { return tx.QueryRow(ctx, `SELECT count(*) FROM employees`).Scan(&n) })
		return
	}
	if count(a) != 1 || count(b) != 1 {
		t.Fatalf("cada empresa deve ver só os próprios funcionários: A=%d B=%d", count(a), count(b))
	}
	// A não consegue gravar linha de B nem ler/alterar pelo id
	if err := db.Tenant(ctx, a, func(tx pgx.Tx) error {
		_, e := tx.Exec(ctx, `INSERT INTO employees (tenant_id,cpf_cifrado,cpf_hash,cpf_mascarado,nome) VALUES ($1,'\x00','x','x','Invasor')`, b)
		return e
	}); err == nil {
		t.Fatal("a empresa A conseguiu gravar dados na empresa B")
	}
	var n int
	db.Tenant(ctx, a, func(tx pgx.Tx) error {
		tx.QueryRow(ctx, `SELECT count(*) FROM employees WHERE tenant_id=$1`, b).Scan(&n)
		ct, _ := tx.Exec(ctx, `UPDATE employees SET nome='hack' WHERE tenant_id=$1`, b)
		n += int(ct.RowsAffected())
		return nil
	})
	if n != 0 {
		t.Fatalf("vazamento entre empresas: %d linhas visíveis/alteráveis", n)
	}
	// sem contexto de empresa nada é visível
	var zero int
	db.Pool.QueryRow(ctx, `SELECT count(*) FROM employees`).Scan(&zero)
	if zero != 0 {
		t.Fatalf("sem app.tenant_id a conexão enxergou %d linhas", zero)
	}
}

func TestAuditoriaImutavelEEncadeada(t *testing.T) {
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		t.Skip("DATABASE_URL não definida")
	}
	ctx := context.Background()
	db, err := database.Connect(ctx, url)
	if err != nil {
		t.Skip("banco indisponível")
	}
	defer db.Pool.Close()
	var tid string
	db.System(ctx, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `INSERT INTO tenants (cnpj,razao_social,porte,quota_bytes,quota_paginas_mes,dek_wrapped) VALUES ($1,'Aud','PEQUENA',1,1,'\x00') RETURNING id::text`, fmt.Sprintf("A%d", os.Getpid())).Scan(&tid)
	})
	for i := 0; i < 5; i++ {
		if err := db.Tenant(ctx, tid, func(tx pgx.Tx) error {
			return audit.Log(ctx, tx, audit.Event{TenantID: tid, ActorRole: "TESTE", Acao: "EVENTO", Dados: map[string]any{"i": i, "z": "ç", "a": []int{1, 2}}})
		}); err != nil {
			t.Fatal(err)
		}
	}
	verify := func() (bool, int64) {
		var ok bool
		var broken int64
		db.Tenant(ctx, tid, func(tx pgx.Tx) error { ok, broken, _, _ = audit.Verify(ctx, tx, tid); return nil })
		return ok, broken
	}
	if ok, _ := verify(); !ok {
		t.Fatal("a cadeia recém-criada deveria estar íntegra")
	}
	for _, q := range []string{`UPDATE audit_log SET acao='x'`, `DELETE FROM audit_log`, `TRUNCATE audit_log`} {
		if err := db.Tenant(ctx, tid, func(tx pgx.Tx) error { _, e := tx.Exec(ctx, q); return e }); err == nil {
			t.Fatalf("o papel da aplicação conseguiu executar: %s", q)
		}
	}
}
