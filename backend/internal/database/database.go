// Package database: pool pgx, migrações embutidas e transações com contexto de empresa (RLS).
package database

import (
	"context"
	"embed"
	"errors"
	"fmt"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/pgx/v5"
	"github.com/golang-migrate/migrate/v4/source/iofs"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"strings"
)

//go:embed migrations/*.sql
var migrationsFS embed.FS

type DB struct{ Pool *pgxpool.Pool }

func Connect(ctx context.Context, url string) (*DB, error) {
	p, err := pgxpool.New(ctx, url)
	if err != nil {
		return nil, err
	}
	if err := p.Ping(ctx); err != nil {
		return nil, fmt.Errorf("postgres indisponível: %w", err)
	}
	return &DB{Pool: p}, nil
}

func (d *DB) run(ctx context.Context, tenantID string, bypass bool, fn func(pgx.Tx) error) error {
	tx, err := d.Pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	b := "off"
	if bypass {
		b = "on"
	}
	if _, err := tx.Exec(ctx, `SELECT set_config('app.tenant_id', $1, true), set_config('app.bypass', $2, true)`, tenantID, b); err != nil {
		return err
	}
	if err := fn(tx); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// Tenant executa fn numa transação com RLS ativa para a empresa (nada vaza entre empresas).
func (d *DB) Tenant(ctx context.Context, tenantID string, fn func(pgx.Tx) error) error {
	if tenantID == "" {
		return errors.New("tenant_id obrigatório")
	}
	return d.run(ctx, tenantID, false, fn)
}

// System ignora o isolamento por empresa. Use só em login, callbacks assinados, jobs e telas Master.
func (d *DB) System(ctx context.Context, fn func(pgx.Tx) error) error {
	return d.run(ctx, "", true, fn)
}

// JSON executa uma consulta que devolve uma linha/coluna JSON e a retorna crua.
func JSON(ctx context.Context, tx pgx.Tx, sql string, args ...any) ([]byte, error) {
	var raw []byte
	if err := tx.QueryRow(ctx, sql, args...).Scan(&raw); err != nil {
		return nil, err
	}
	return raw, nil
}

// EnsureAppRole cria o papel citadel_app (sem BYPASSRLS) usado pela API e pelo worker.
func EnsureAppRole(ctx context.Context, ownerURL, password string) error {
	conn, err := pgx.Connect(ctx, ownerURL)
	if err != nil {
		return err
	}
	defer conn.Close(ctx)
	var stmt string
	if err := conn.QueryRow(ctx, `SELECT format('CREATE ROLE citadel_app LOGIN PASSWORD %L NOBYPASSRLS NOSUPERUSER', $1::text)
	  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='citadel_app')`, password).Scan(&stmt); err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	if stmt != "" {
		_, err = conn.Exec(ctx, stmt)
	}
	return err
}

func Migrate(ownerURL string) error {
	src, err := iofs.New(migrationsFS, "migrations")
	if err != nil {
		return err
	}
	m, err := migrate.NewWithSourceInstance("iofs", src, strings.Replace(ownerURL, "postgres://", "pgx5://", 1))
	if err != nil {
		return err
	}
	defer m.Close()
	if err := m.Up(); err != nil && !errors.Is(err, migrate.ErrNoChange) {
		return err
	}
	return nil
}
