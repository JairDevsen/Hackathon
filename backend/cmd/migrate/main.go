package main

import (
	"context"
	"log/slog"
	"os"

	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	"github.com/agreser-innovations/citadel-ia/backend/internal/database"
)

// Cria o papel citadel_app (sem BYPASSRLS) e aplica as migrações como dono do schema.
func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	cfg, err := config.Load()
	if err != nil {
		slog.Error("configuração", "erro", err)
		os.Exit(1)
	}
	if err := database.EnsureAppRole(context.Background(), cfg.DatabaseMigrate, cfg.AppDBPassword); err != nil {
		slog.Error("papel citadel_app", "erro", err)
		os.Exit(1)
	}
	if err := database.Migrate(cfg.DatabaseMigrate); err != nil {
		slog.Error("migrações", "erro", err)
		os.Exit(1)
	}
	slog.Info("migrações aplicadas")
}
