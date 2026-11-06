package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/agreser-innovations/citadel-ia/backend/internal/app"
	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/internal/batches"
	"github.com/agreser-innovations/citadel-ia/backend/internal/compliance"
	"github.com/agreser-innovations/citadel-ia/backend/internal/config"
	"github.com/hibiken/asynq"
	"github.com/jackc/pgx/v5"
)

const (
	taskWatchdog   = "batch:watchdog"
	taskCompliance = "compliance:daily"
	taskAudit      = "audit:verify"
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

	srv := asynq.NewServer(a.RedisOpt, asynq.Config{Concurrency: cfg.WorkerConcurrency, Queues: map[string]int{"default": 1},
		// se o worker cair no meio da tarefa, o lease expira e o job volta à fila (retomada)
		TaskCheckInterval: 2 * 1e9, ShutdownTimeout: 30 * 1e9,
		ErrorHandler: asynq.ErrorHandlerFunc(func(ctx context.Context, t *asynq.Task, err error) {
			slog.Error("tarefa falhou", "tipo", t.Type(), "erro", err)
		})})
	mux := asynq.NewServeMux()
	mux.HandleFunc(batches.TaskProcess, func(ctx context.Context, t *asynq.Task) error {
		var p batches.TaskPayload
		if err := json.Unmarshal(t.Payload(), &p); err != nil {
			return err
		}
		return a.Batches.Process(ctx, p)
	})
	mux.HandleFunc(taskWatchdog, func(ctx context.Context, t *asynq.Task) error { return a.Batches.Watchdog(ctx) })
	mux.HandleFunc(taskCompliance, func(ctx context.Context, t *asynq.Task) error { return dailyCompliance(ctx, a) })
	mux.HandleFunc(taskAudit, func(ctx context.Context, t *asynq.Task) error { return verifyAudit(ctx, a) })

	sched := asynq.NewScheduler(a.RedisOpt, nil)
	sched.Register("@every "+cfg.WatchdogInterval, asynq.NewTask(taskWatchdog, nil), asynq.Queue("default"), asynq.Unique(50*1e9))
	sched.Register("0 3 * * *", asynq.NewTask(taskCompliance, nil), asynq.Queue("default"))
	sched.Register("30 3 * * *", asynq.NewTask(taskAudit, nil), asynq.Queue("default"))
	if err := sched.Start(); err != nil {
		slog.Error("scheduler", "erro", err)
		os.Exit(1)
	}
	defer sched.Shutdown()
	go func() { <-ctx.Done(); srv.Shutdown() }()
	slog.Info("worker Citadel IA no ar", "concorrencia", cfg.WorkerConcurrency)
	if err := srv.Run(mux); err != nil {
		slog.Error("worker", "erro", err)
		os.Exit(1)
	}
}

func tenantIDs(ctx context.Context, a *app.App) []string {
	var ids []string
	a.DB.System(ctx, func(tx pgx.Tx) error {
		rows, _ := tx.Query(ctx, `SELECT id::text FROM tenants WHERE status='ATIVO'`)
		defer rows.Close()
		for rows.Next() {
			var id string
			rows.Scan(&id)
			ids = append(ids, id)
		}
		return nil
	})
	return ids
}

// dailyCompliance: recalcula a conformidade de cada empresa (vencimentos mudam com o tempo) e gera alertas.
func dailyCompliance(ctx context.Context, a *app.App) error {
	for _, id := range tenantIDs(ctx, a) {
		err := a.DB.Tenant(ctx, id, func(tx pgx.Tx) error {
			if err := compliance.Recompute(ctx, tx, id, ""); err != nil {
				return err
			}
			if err := compliance.DailyAlerts(ctx, tx, id); err != nil {
				return err
			}
			for _, lim := range []int{95, 80} { // alertas de cota (80% e 95%)
				tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link) SELECT $1,'COTA',$2,'/plano' FROM tenants WHERE id=$1 AND bytes_usados >= quota_bytes*$3/100.0
				  AND NOT EXISTS (SELECT 1 FROM notifications WHERE tenant_id=$1 AND tipo='COTA' AND titulo=$2 AND criado_em > now()-interval '7 days')`, id,
					"Armazenamento em "+itoa(lim)+"% da cota", lim)
			}
			return nil
		})
		if err != nil {
			slog.Error("conformidade diária", "tenant_id", id, "erro", err)
		}
	}
	return nil
}

func itoa(n int) string { b, _ := json.Marshal(n); return string(b) }

// verifyAudit confere a cadeia de hash de cada empresa e a global.
func verifyAudit(ctx context.Context, a *app.App) error {
	for _, id := range append([]string{""}, tenantIDs(ctx, a)...) {
		a.DB.System(ctx, func(tx pgx.Tx) error {
			ok, broken, n, err := audit.Verify(ctx, tx, id)
			switch {
			case err != nil:
				slog.Error("verificação de auditoria", "erro", err)
			case !ok:
				slog.Error("CADEIA DE AUDITORIA VIOLADA", "tenant_id", id, "primeiro_elo", broken)
			default:
				slog.Info("auditoria íntegra", "tenant_id", id, "eventos", n)
			}
			return nil
		})
	}
	return nil
}
