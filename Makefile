.PHONY: up down logs pull migrate seed backup restore keys check-secrets install-hooks test lint dev-deps dev web dev-down e2e

up:        ; docker compose up -d
down:      ; docker compose down
logs:      ; docker compose logs -f --tail=200 api worker ia-core
pull:      ; docker compose pull
migrate:   ; docker compose run --rm migrate
seed:      ; docker compose run --rm --entrypoint /seed api
backup:    ## dump do Postgres + cópia do bucket (ver OPERACAO.md)
	@mkdir -p backups && docker compose exec -T postgres pg_dump -U citadel -Fc citadel > backups/citadel-$$(date +%Y%m%d-%H%M).dump && ls -lh backups | tail -1
restore:   ## make restore FILE=backups/xxx.dump  (SEMPRE teste em ambiente separado antes)
	@test -n "$(FILE)" || (echo "use FILE=backups/arquivo.dump" && exit 1)
	docker compose exec -T postgres pg_restore -U citadel -d citadel --clean --if-exists < $(FILE)
keys:      ## gera a chave JWT; se .env existir, preenche segredos vazios sem exibir valores
	@python3 scripts/init-secrets.py
check-secrets: ## falha se um arquivo de credencial estiver preparado para commit
	@python3 scripts/check-secrets.py
install-hooks: ## ativa a checagem local antes de cada commit
	@git config core.hooksPath .githooks
test:
	cd backend && go test -race ./...
	cd ia-core && python -m pytest tests -q
	cd frontend && npm test
lint:
	cd backend && go vet ./... && (command -v golangci-lint >/dev/null && golangci-lint run || true)
	cd frontend && npm run lint && npx tsc --noEmit
dev-deps:  ; docker compose -f docker-compose.dev.yml up -d
dev-down:  ; docker compose -f docker-compose.dev.yml down
dev:       ## terminal 1: migra, popula e sobe API + worker + IA Core (Postgres e Redis já rodando)
	./scripts/dev.sh
web:       ## terminal 2: frontend em http://localhost:5173
	cd frontend && npm run dev
e2e:       ## smoke E2E: API=http://localhost:8080 MAIL_LOG=... (ver backend/scripts/)
	cd backend && python scripts/e2e_smoke.py
