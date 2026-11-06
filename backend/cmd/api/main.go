package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	apihttp "github.com/agreser-innovations/citadel-ia/backend/internal/http"
)

func main() {
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	cfg, err := config.Load()
	if err != nil {
		slog.Error("configuração", "erro", err)
		os.Exit(1)
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	a, err := app.New(ctx, cfg)
	if err != nil {
		slog.Error("inicialização", "erro", err)
		os.Exit(1)
	}
	defer a.Close()
	srv := &http.Server{Addr: cfg.HTTPAddr, Handler: (&apihttp.Server{App: a}).Router(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		slog.Info("API Citadel IA no ar", "addr", cfg.HTTPAddr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("servidor", "erro", err)
			stop()
		}
	}()
	<-ctx.Done()
	sh, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	srv.Shutdown(sh)
}
