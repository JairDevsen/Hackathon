package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/auth"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	"github.com/agreser-innovations/citadel-ia/backend/internal/documents"
	"github.com/jackc/pgx/v5"
)

// Seed: usuário Master (sempre) e, com SEED_DEMO=true, a empresa fictícia "Agrotech" com dados de demonstração.
func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	cfg, err := config.Load()
	if err != nil {
		slog.Error("configuração", "erro", err)
		os.Exit(1)
	}
	ctx := context.Background()
	a, err := app.New(ctx, cfg)
	if err != nil {
		slog.Error("inicialização", "erro", err)
		os.Exit(1)
	}
	defer a.Close()
	if cfg.MasterPassword == "" {
		slog.Error("defina MASTER_PASSWORD para criar o usuário Master")
		os.Exit(1)
	}
	if err := a.DB.System(ctx, func(tx pgx.Tx) error {
		_, err := tx.Exec(ctx, `INSERT INTO users (email,nome,role,status,senha_hash) VALUES (lower($1),'Operador Master','MASTER','ATIVO',$2) ON CONFLICT (lower(email)) DO NOTHING`,
			cfg.MasterEmail, auth.HashPassword(cfg.MasterPassword))
		return err
	}); err != nil {
		slog.Error("master", "erro", err)
		os.Exit(1)
	}
	slog.Info("usuário Master garantido", "email", cfg.MasterEmail)
	if cfg.SeedDemo {
		if cfg.Prod() { // as contas de demonstração têm senha pública (ACESSO.md): nunca em produção
			slog.Error("SEED_DEMO=true é proibido com APP_ENV=production: contas de demonstração não são criadas")
			os.Exit(1)
		}
		if err := demo(ctx, a); err != nil {
			slog.Error("demo", "erro", err)
			os.Exit(1)
		}
	}
}

func demo(ctx context.Context, a *app.App) error {
	var exists bool
	a.DB.System(ctx, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM tenants WHERE cnpj='14589201000180')`).Scan(&exists)
	})
	if exists {
		slog.Info("empresa demo já existe")
		return nil
	}
	wrapped, err := a.NewTenantKey()
	if err != nil {
		return err
	}
	pw := auth.HashPassword("Demo!Citadel#2026")
	var tid string
	err = a.DB.System(ctx, func(tx pgx.Tx) error {
		if err := tx.QueryRow(ctx, `INSERT INTO tenants (cnpj, razao_social, nome_fantasia, porte, plano_id, dominios_email, quota_bytes, quota_paginas_mes, max_usuarios_rh, max_funcionarios, dek_wrapped)
		  SELECT '14589201000180','AGROTECH GARANHUNS LTDA','Agrotech Garanhuns','MEDIA',p.id,ARRAY['agrotech.demo'],p.quota_bytes,p.quota_paginas_mes,p.max_usuarios_rh,p.max_funcionarios,$1
		  FROM plans p WHERE p.codigo='MEDIA' RETURNING id::text`, wrapped).Scan(&tid); err != nil {
			return err
		}
		tx.Exec(ctx, `INSERT INTO users (tenant_id,email,nome,role,status,senha_hash) VALUES ($1,'admin@agrotech.demo','Ana Administradora','ADMIN_EMPRESA','ATIVO',$2)`, tid, pw)
		tx.Exec(ctx, `INSERT INTO users (tenant_id,email,nome,role,status,senha_hash,perms) VALUES ($1,'rh@agrotech.demo','Rafael do RH','RH','ATIVO',$2,ARRAY['saude:ler'])`, tid, pw)
		tx.Exec(ctx, `INSERT INTO users (tenant_id,email,nome,role,status,senha_hash) VALUES ($1,'rh2@agrotech.demo','Rita do RH (sem saúde)','RH','ATIVO',$2)`, tid, pw)
		tx.Exec(ctx, `INSERT INTO subscriptions (tenant_id, plano_id) SELECT id, plano_id FROM tenants WHERE id=$1`, tid)
		return nil
	})
	if err != nil {
		return err
	}
	type seedEmp struct{ Nome, CPF, Mat, Cargo, Unit, Adm string }
	emps := []seedEmp{
		{"CARLOS EDUARDO SILVA", "45871290388", "1001", "Operador de Empilhadeira", "Matriz Garanhuns", "2025-03-10"},
		{"MARIA FERNANDA COSTA", "61920488197", "1002", "Auxiliar de Limpeza", "Matriz Garanhuns", "2025-06-02"},
		{"ROBERTO ALMEIDA MENDES", "81234091178", "1003", "Supervisor de Portaria", "Filial Recife", "2024-11-18"},
		{"JOÃO PEDRO CAVALCANTI", "30944187242", "1004", "Gerente Administrativo", "Matriz Garanhuns", "2023-01-09"},
		{"JULIANA PEREIRA LIMA", "52998224725", "1005", "Auxiliar de Limpeza", "Filial Recife", time.Now().AddDate(0, -3, 0).Format("2006-01-02")},
	}
	return a.DB.Tenant(ctx, tid, func(tx pgx.Tx) error {
		units := map[string]string{}
		for _, n := range []string{"Matriz Garanhuns", "Filial Recife"} {
			var id string
			tx.QueryRow(ctx, `INSERT INTO units (tenant_id,nome) VALUES ($1,$2) RETURNING id::text`, tid, n).Scan(&id)
			units[n] = id
		}
		pos := map[string]string{}
		for _, p := range []struct{ Nome, Seg string }{{"Operador de Empilhadeira", "MANUTENCAO"}, {"Auxiliar de Limpeza", "LIMPEZA"}, {"Supervisor de Portaria", "PORTARIA"}, {"Gerente Administrativo", "ADMINISTRATIVO"}} {
			var id string
			tx.QueryRow(ctx, `INSERT INTO positions (tenant_id,nome,segmento) VALUES ($1,$2,$3) RETURNING id::text`, tid, p.Nome, p.Seg).Scan(&id)
			pos[p.Nome] = id
			if err := applyTpl(ctx, tx, tid, id, p.Seg); err != nil {
				return err
			}
		}
		if err := applyCompany(ctx, tx, tid); err != nil {
			return err
		}
		for _, e := range emps {
			cg, un, ad := pos[e.Cargo], units[e.Unit], e.Adm
			if _, err := a.Ingest.CreateEmployee(ctx, tx, tid, documents.NewEmployee{Nome: e.Nome, CPF: e.CPF, Matricula: e.Mat, CargoID: &cg, UnitID: &un, Admissao: &ad}); err != nil {
				return fmt.Errorf("funcionário %s: %w", e.Nome, err)
			}
		}
		return compliance.Recompute(ctx, tx, tid, "")
	})
}

func applyTpl(ctx context.Context, tx pgx.Tx, tid, pos, seg string) error {
	base := [][3]any{{"CONTRATO_TRABALHO", "ADMISSAO", 0}, {"FICHA_REGISTRO", "ADMISSAO", 0}, {"CTPS", "ADMISSAO", 0}, {"RG", "ADMISSAO", 0}, {"COMPROVANTE_RESIDENCIA", "ADMISSAO", 0},
		{"ASO", "PERIODICO", 365}, {"HOLERITE", "MENSAL", 0}, {"CARTAO_PONTO", "MENSAL", 0}, {"TRCT", "DESLIGAMENTO", 0}}
	if seg == "LIMPEZA" || seg == "MANUTENCAO" {
		base = append(base, [3]any{"FICHA_EPI", "ADMISSAO", 0}, [3]any{"TREINAMENTO_NR", "PERIODICO", 730})
	}
	if seg == "MANUTENCAO" {
		base = append(base, [3]any{"CNH", "PERIODICO", 1825})
	}
	for _, b := range base {
		var v any
		if b[2].(int) > 0 {
			v = b[2]
		}
		if _, err := tx.Exec(ctx, `INSERT INTO requirements (tenant_id, position_id, document_type_id, momento, validade_dias) SELECT $1,$2,id,$4,$5 FROM document_types WHERE codigo=$3`, tid, pos, b[0], b[1], v); err != nil {
			return err
		}
	}
	return nil
}

func applyCompany(ctx context.Context, tx pgx.Tx, tid string) error {
	for _, b := range [][3]any{{"CRF_FGTS", "PERIODICO", 30}, {"CNDT", "PERIODICO", 180}, {"CND_FEDERAL", "PERIODICO", 180}, {"GUIA_FGTS", "MENSAL", 0}} {
		var v any
		if b[2].(int) > 0 {
			v = b[2]
		}
		if _, err := tx.Exec(ctx, `INSERT INTO requirements (tenant_id, position_id, document_type_id, momento, validade_dias) SELECT $1,NULL,id,$3,$4 FROM document_types WHERE codigo=$2`, tid, b[0], b[1], v); err != nil {
			return err
		}
	}
	return nil
}
