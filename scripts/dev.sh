#!/usr/bin/env bash
# Terminal 1 do desenvolvimento local: migra, popula e sobe API + worker + IA Core.
# Pré-requisitos: Postgres e Redis rodando (README, passo 1). O frontend roda à parte: `make web`.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="${TMPDIR:-/tmp}"; LOGDIR="${LOGDIR%/}"
export SEED_DEMO="${SEED_DEMO:-true}"

[ -x "$ROOT/.venv/bin/uvicorn" ] || { echo "Falta o venv do IA Core: python3 -m venv .venv && .venv/bin/pip install -r ia-core/requirements.txt"; exit 1; }

# Só o IA Core lê estas opções. O parser aceita KEY=VALUE e comentários, sem executar código shell.
load_ia_env() {
  local file="$ROOT/ia-core/.env.local" line name value trimmed
  [ -f "$file" ] || return 0
  [ ! -L "$file" ] || { echo "IA Core: .env.local não pode ser link simbólico" >&2; return 1; }
  chmod 600 "$file"
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    trimmed="${line#"${line%%[![:space:]]*}"}"
    case "$trimmed" in ''|\#*) continue ;; esac
    case "$line" in *=*) ;; *) echo "IA Core: linha inválida em .env.local" >&2; return 1 ;; esac
    name="${line%%=*}"
    value="${line#*=}"
    case "$name" in
      IA_PROVIDER|IA_IMAGE_MAX_PX|OPENAI_API_KEY|OPENAI_MODEL|OPENAI_MODEL_FALLBACK|OPENAI_MODEL_LITE|OPENAI_REASONING_EFFORT|OPENAI_BASE_URL|GEMINI_API_KEY|GEMINI_MODEL|GEMINI_MODEL_FALLBACK|GEMINI_MODEL_LITE|GEMINI_IMAGE_MAX_PX) export "$name=$value" ;;
      *) echo "IA Core: variável não permitida em .env.local: $name" >&2; return 1 ;;
    esac
  done < "$file"
}

cd "$ROOT/backend"
echo "▸ compilando backend…"
mkdir -p bin && go build -o bin/ ./cmd/migrate ./cmd/seed ./cmd/api ./cmd/worker
echo "▸ migrando e populando o banco…"
./bin/migrate >/dev/null && ./bin/seed >/dev/null

pids=()
cleanup() { trap - EXIT INT TERM; echo; echo "▸ encerrando serviços…"; kill "${pids[@]}" 2>/dev/null || true; pkill -P $$ 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM

( cd "$ROOT/ia-core" && load_ia_env && exec "$ROOT/.venv/bin/uvicorn" ia_core.main:app --port 8001 ) >"$LOGDIR/citadel-ia.log" 2>&1 & pids+=($!)
./bin/api    >"$LOGDIR/citadel-api.log" 2>&1 & pids+=($!)
./bin/worker >"$LOGDIR/citadel-worker.log" 2>&1 & pids+=($!)

# o e-mail de 2FA vai para o log da API (MAIL_DRIVER=log): mostra só o código aqui
: >"$LOGDIR/citadel-api.log"
tail -F "$LOGDIR/citadel-api.log" 2>/dev/null | grep --line-buffered -o 'é: [0-9]\{6\}' | sed -u 's/^é: /  🔑 código 2FA: /' &
pids+=($!)

sleep 3
for p in 8080:API 8001:"IA Core"; do
  curl -fs "http://localhost:${p%%:*}/$([ "${p%%:*}" = 8080 ] && echo healthz || echo health)" >/dev/null && echo "✔ ${p#*:} no ar (:${p%%:*})" || echo "✘ ${p#*:} não respondeu — veja $LOGDIR/citadel-*.log"
done
echo "✔ worker iniciado"
echo
echo "Agora abra outro terminal:  make web      (http://localhost:5173)"
echo "Logs: $LOGDIR/citadel-{api,worker,ia}.log   ·   Ctrl+C aqui encerra tudo"
wait
