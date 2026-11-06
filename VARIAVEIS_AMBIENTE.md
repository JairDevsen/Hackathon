# Variáveis de ambiente

Para produção, copie `.env.example` para `.env` e execute `make keys`: ele preenche os segredos vazios ou com marcador sem sobrescrever valores reais, sem mostrar os valores no terminal. Em `APP_ENV=development` há padrões **públicos e inseguros** (chaves fixas) só para facilitar o desenvolvimento; em `production` as variáveis marcadas **obrigatória** não têm padrão e a aplicação não sobe sem elas. O comando `make dev` não lê o `.env` de produção.

| Variável | Para que serve | Padrão (dev) | Como gerar / observações |
|---|---|---|---|
| `APP_ENV` | `development` ou `production` (cookies Secure, HSTS, exige segredos) | `development` | |
| `DOMAIN` | domínio público (Traefik, links de e-mail) | – | compose |
| `ACME_EMAIL` | e-mail para emissão e renovação do HTTPS pelo Traefik | – | obrigatório no Compose de produção; DNS do `DOMAIN` deve apontar para a VPS |
| `APP_UID`, `APP_GID` | usuário/grupo não-root da VPS usados pela API e pelo worker | – | `make keys` preenche com o usuário que executa o comando; dá acesso à chave JWT e a `var/staging` |
| `HTTP_ADDR` | porta da API | `:8080` | |
| `DATABASE_URL` | conexão da API/worker (**papel `citadel_app`**, sujeito a RLS) | `postgres://citadel_app:…@localhost:5432/citadel` | nunca use superusuário |
| `DATABASE_MIGRATE_URL` | dono do schema, usado só por `/migrate` | `postgres://citadel:citadel@…` | precisa de `CREATEROLE` (no Docker o `POSTGRES_USER` já é superusuário) |
| `APP_DB_PASSWORD` | senha do papel `citadel_app` (criado pelo migrate) | `citadel_app` | **obrigatória** em produção |
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | senhas dos contêineres | – | `openssl rand -hex 24` |
| `REDIS_URL` | fila, OTP, rate limit, SSE | `redis://localhost:6379/0` | |
| `KEK_HEX` | chave mestra (32 B) que protege a chave de dados (DEK) de cada empresa | fixa de dev | **obrigatória**; `make keys`. Perder = perder acesso aos arquivos cifrados |
| `HMAC_KEY_HEX` | índice cego do CPF (`cpf_hash`) e URLs assinadas | fixa de dev | **obrigatória**; trocar invalida buscas por CPF e links |
| `JWT_PRIVATE_KEY_FILE` | chave Ed25519 (PEM PKCS#8) que assina os access tokens | `../secrets/jwt_ed25519.pem` (gerada em dev) | `make keys`. Rotação: ver OPERACAO.md |
| `JWT_PREVIOUS_KEYS_DIR` | pasta com `*.pub.pem` das chaves antigas (rotação sem derrubar sessões) | vazio | |
| `JWT_ISSUER` | `iss` dos tokens | `citadel-ia` | |
| `PUBLIC_BASE_URL` | URL pública da API (links assinados vistos pelo navegador) | `http://localhost:8080` | `https://$DOMAIN` |
| `INTERNAL_BASE_URL` | URL da API vista pelo IA Core (arquivos e callback) | `http://localhost:8080` | `http://api:8080` |
| `APP_URL` | URL do frontend (links de convite) | `http://localhost:5173` | |
| `STORAGE_DRIVER` | `fs` (disco) ou `s3` (MinIO/S3) | `fs` | produção: `s3` |
| `STORAGE_FS_DIR` | raiz do driver `fs` | `./var/storage` | |
| `S3_ENDPOINT/BUCKET/ACCESS_KEY/SECRET_KEY/USE_SSL` | objetos (`{tenant}/…`, cifrados) | `localhost:9000` / `citadel` | |
| `UPLOAD_STAGING_DIR` | área temporária dos uploads em partes | `./var/staging` | volume compartilhado entre réplicas da API, se houver |
| `MAX_UPLOAD_MB` | tamanho máximo por arquivo | `500` | |
| `CLAMAV_ADDR` | `host:3310` do clamd; vazio = antivírus desligado | vazio | **ligue em produção** |
| `IA_CORE_URL` | endereço do IA Core | `http://localhost:8001` | |
| `IA_CORE_API_KEY` | chave API → IA Core | `dev-ia-core-key` | **obrigatória** |
| `IA_CALLBACK_SECRET` | HMAC dos callbacks IA Core → API (janela de 10 min) | fixa de dev | **obrigatória**; mesmo valor nos dois |
| `IA_PROVIDER` | força o provedor: `openai`, `gemini` ou `local`. Vazio = escolha automática (OpenAI, depois Gemini, depois local) | vazio | provedor explícito sem a chave correspondente impede o IA Core de subir |
| `OPENAI_API_KEY` | liga o provedor OpenAI no IA Core; vazio = não usa | vazio | no `make dev`, coloque em `ia-core/.env.local` e reinicie; no Compose, configure no `.env`. Tem prioridade sobre a chave do Gemini |
| `OPENAI_MODEL`, `OPENAI_MODEL_FALLBACK` | modelo padrão (visão) e modelo maior para páginas difíceis | `gpt-5-mini` / `gpt-5` | nomes não validados com chave real: confira em `GET /diagnostico` |
| `OPENAI_MODEL_LITE` | modelo barato da Camada 2 (texto extraído, sem imagem) | `gpt-5-nano` | |
| `OPENAI_REASONING_EFFORT` | opcional: `minimal`, `low`, `medium` ou `high` (só para modelos que aceitam) | vazio | menos esforço = respostas mais rápidas e baratas |
| `OPENAI_BASE_URL` | opcional: endpoint compatível com a API da OpenAI (Azure, proxy interno) | vazio | |
| `GEMINI_API_KEY` | liga o provedor Gemini no IA Core; vazio = não usa | vazio | no `make dev`, coloque em `ia-core/.env.local` e reinicie; no Compose, configure no `.env` |
| `GEMINI_MODEL`, `GEMINI_MODEL_FALLBACK` | modelo padrão e modelo maior para páginas difíceis | `gemini-3.5-flash` / `gemini-3.6-flash` | |
| `GEMINI_MODEL_LITE` | modelo barato da Camada 2 (texto extraído, sem imagem) | `gemini-3.5-flash-lite` | |
| `IA_IMAGE_MAX_PX` (ou `GEMINI_IMAGE_MAX_PX`) | lado máximo da imagem enviada ao modelo de visão (redução proporcional, WebP q=80) | `1024` | só a cópia enviada à IA é reduzida; o original fica guardado. Menos pixels = menos tokens, mas pior para manuscrito |
| `IA_NITIDEZ_MIN` | limite de nitidez abaixo do qual uma imagem sem texto é tratada como **borrada** (variância do filtro de bordas) | `600` | heurística calibrada só com amostras sintéticas (texto nítido ≈ 2000, desfoque forte ≈ 400): **calibre com digitalizações reais** |
| `IA_WORKERS` | threads de análise no IA Core | `4` | |
| `IA_PAGE_DELAY_MS` | atraso por página (**só teste de caos**) | `0` | |
| `MAIL_DRIVER` | `log` (stdout) ou `smtp` | `log` | |
| `SMTP_HOST/PORT/USER/PASS`, `MAIL_FROM` | e-mails (2FA, convites, alertas) | Mailpit `localhost:1025` | |
| `COMMERCIAL_EMAIL` | quem recebe os leads da landing | `comercial@citadel.local` | |
| `MASTER_EMAIL`, `MASTER_PASSWORD` | usuário Master criado pelo `/seed` | `master@citadel.local` | senha **obrigatória** em produção |
| `SEED_DEMO` | cria a empresa fictícia de demonstração | `false` | nunca em produção |
| `WORKER_CONCURRENCY` | tarefas simultâneas | `4` | |
| `BATCH_STALL_SECONDS`, `WATCHDOG_INTERVAL` | quando um lote sem progresso é re-despachado, e a frequência da checagem | `180` / `1m` | |
| `CAPTCHA_SECRET` | Cloudflare Turnstile no formulário da landing; vazio = desligado | vazio | |
| `CORS_ORIGINS` | origens extras (dev sem proxy) | `http://localhost:5173` | em produção a SPA e a API usam o mesmo domínio |
| `PUBLIC_API_URL` (frontend) | base da API na SPA | vazio (mesma origem) | gerada em `/config.js` pelo `entrypoint.sh` |

**IA em produção:** o provedor Vertex AI ainda não está implementado. O motor local não envia páginas a serviços externos, mas tem limitações em manuscritos e digitalizações ruins. Se usar uma chave OpenAI ou Gemini, valide antes as condições de tratamento dos documentos reais; o fluxo pode enviar imagem ou texto de páginas difíceis ao serviço externo.
