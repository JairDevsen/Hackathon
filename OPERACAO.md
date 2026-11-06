# Operação

## Deploy
```bash
cd /opt/citadel-ia
cp .env.example .env
# Edite DOMAIN, ACME_EMAIL, MASTER_EMAIL, MAIL_FROM e as opções SMTP no .env.
make keys                  # segredos, chave JWT e pasta de uploads com permissões restritas
docker compose config --quiet
docker compose up -d --build
make seed                  # apenas no primeiro deploy: cria o usuário Master
docker compose ps
```
O `docker-compose.yml` inclui o Traefik e emite certificado HTTPS pelo desafio HTTP-01. Configure o DNS de `DOMAIN` para a VPS e libere `80/443` antes de subir. Execute `make keys` como o **mesmo usuário não-root** que fará o deploy: o Compose usa seu UID/GID para que API e worker leiam `secrets/jwt_ed25519.pem` e gravem em `var/staging`. Só Traefik publica portas; Postgres, Redis, MinIO, ClamAV e IA Core ficam na rede Docker interna. A migração roda automaticamente antes da API. O primeiro `make seed` cria o Master; repeti-lo não altera a senha existente.

Para usar imagens já publicadas, substitua `docker compose up -d --build` por `docker compose pull && docker compose up -d` e ajuste `TAG` no `.env`. Imagens privadas no GHCR exigem login no registry na VPS. O `MASTER_PASSWORD` inicial fica somente no `.env` ou no cofre de segredos; altere a senha após o primeiro acesso. Mantenha `.env` e `secrets/` fora de backups públicos e de imagens Docker. O GitHub Actions (`.github/workflows/deploy.yml`) publica as imagens e faz `pull → up` por SSH em tags `v*`.

Deixe `OPENAI_API_KEY` e `GEMINI_API_KEY` vazios para o motor local; o endpoint interno `ia-core:8001/health` informa `local-heuristico`. Se informar uma chave, o IA Core seleciona o provedor (`openai:<modelo>` ou `gemini:<modelo>`; com as duas chaves, a OpenAI tem prioridade, ou force com `IA_PROVIDER`), e `GET ia-core:8001/diagnostico` (com `X-IACore-Key`) testa cada modelo configurado. Mesmo assim, páginas com texto nativo suficiente ainda são resolvidas localmente. O provedor Vertex AI ainda não está implementado; a chave pública de OpenAI ou Gemini requer uma decisão própria de tratamento de dados antes de enviar documentos reais.

## Rollback
`TAG=v1.2.2 docker compose up -d`. Migrações são **somente para frente** (`.down.sql` existe apenas para dev): faça backup antes de subir uma versão com migração nova e escreva migrações compatíveis com a versão anterior (expandir → migrar → contrair).

## Backup e **teste de restauração**
- **Postgres:** `make backup` (dump `-Fc`). Em produção habilite arquivamento de WAL para PITR (`archive_command` para o bucket de backup) — não vem configurado no compose.
- **Arquivos:** ative versionamento e replicação no bucket (MinIO: `mc version enable` + `mc replicate add`). Os objetos estão **cifrados**: o backup só é útil junto com `KEK_HEX` e com a tabela `tenants.dek_wrapped`.
- **Segredos:** guarde `KEK_HEX`, `HMAC_KEY_HEX` e `secrets/jwt_ed25519.pem` em cofre separado do backup de dados.
- **Teste de restauração (trimestral, e antes de cada mudança grande):** suba um ambiente vazio → `make restore FILE=…` → `make migrate` → entre como admin, abra um dossiê e baixe um PDF (prova que a chave e os objetos conferem) → rode `/admin/audit/verify` (cadeia íntegra).

## Rotação de chaves
- **JWT:** gere nova chave (`openssl genpkey -algorithm ed25519`), coloque a antiga como `*.pub.pem` em `JWT_PREVIOUS_KEYS_DIR`, troque `JWT_PRIVATE_KEY_FILE` e reinicie. Tokens antigos continuam válidos até expirar (≤ 15 min); depois remova a chave antiga. O JWKS está em `/.well-known/jwks.json` (rede interna).
- **KEK:** ainda **não** há comando de re-embrulho automático das DEKs. Procedimento manual: abrir cada `tenants.dek_wrapped` com a KEK antiga e regravar com a nova numa janela de manutenção. Não troque `KEK_HEX` sem isso.
- **HMAC_KEY:** trocar invalida `cpf_hash` (busca por CPF) e URLs assinadas; exige recalcular o hash de todos os CPFs (hoje só possível descriptografando `cpf_cifrado`).
- **Segredo do callback / chave do IA Core:** altere nos dois serviços e reinicie ambos.

## Troubleshooting
| Sintoma | Verificar |
|---|---|
| Lote parado em *Processando* | `docker compose logs worker ia-core`; o *watchdog* re-despacha após `BATCH_STALL_SECONDS` (3 tentativas, depois fila de mensagens mortas: Master → Plataforma → Filas, botão **Retomar**) |
| Login não envia e-mail | `MAIL_DRIVER=smtp` e credenciais; com `log` o código aparece no log da API |
| 403 ao baixar arquivo | link assinado expira em 60–120 s; gere de novo pela tela |
| "cota excedida" | Master → Clientes → Plano e limites; leitura segue liberada |
| `permission denied to create role` no migrate | o usuário de `DATABASE_MIGRATE_URL` precisa de `CREATEROLE` |
| Auditoria "cadeia violada" | alguém alterou a tabela fora da aplicação; preserve o banco e investigue (o papel da app não consegue UPDATE/DELETE em `audit_log`) |

## Checagens recorrentes
`/healthz`, `/readyz` (API); worker registra `auditoria íntegra` diariamente às 03:30 e recalcula a conformidade às 03:00.
