# Citadel IA

Plataforma multiempresa para receber lotes de documentos trabalhistas, separar páginas, identificar o tipo, extrair dados e montar o dossiê de cada funcionário. O RH acompanha o processamento, revisa leituras duvidosas e confere pendências e indicadores de risco documental.

**Fluxo principal:** `envio do lote → validação e armazenamento → análise por página → agrupamento em documentos → pré-cadastro/vínculo do funcionário → revisão humana quando necessária → dossiê, conformidade e alertas`.

Quando o documento permite identificar nome e CPF válido, o sistema pré-cadastra o funcionário por padrão. Documentos ilegíveis ou sem tipo identificado entram na fila para classificação, transcrição manual ou envio de uma cópia legível. A transcrição manual fica identificada como tal e não comprova sozinha uma exigência documental. Os indicadores de risco são sinais para conferência do RH e do jurídico, não conclusões jurídicas.

## Requisitos para rodar localmente

Instale estes itens antes de começar. As versões mínimas vêm do projeto (`backend/go.mod`, `ia-core/pyproject.toml`, `docker-compose.dev.yml`).

| Requisito | Versão | Para que serve | Conferir | Obrigatório |
|---|---|---|---|---|
| **Git** | qualquer recente | clonar o projeto | `git --version` | Sim |
| **Docker** com Compose v2 | Docker Desktop ou Engine | sobe o Postgres 16 e o Redis 7 (e, opcionalmente, MinIO, Mailpit e ClamAV) | `docker compose version` | Sim, salvo se instalar Postgres e Redis à mão |
| **Go** | 1.26+ | compila a API, o worker, a migração e o seed | `go version` | Sim |
| **Node.js** com npm | 22+ | roda o frontend (React + Vite) | `node --version` | Sim |
| **Python** com `venv` e `pip` | 3.11+ | roda o IA Core (FastAPI) | `python3 --version` (no Windows: `python --version`) | Sim |
| **make** | qualquer | atalhos `make dev` e `make web` | `make --version` | macOS e Linux. No Windows **não é necessário** ([como rodar sem ele](#windows--powershell-nativo-sem-wsl-e-sem-make)) |
| **OpenSSL** e **curl** | qualquer | `make keys` e as verificações do `scripts/dev.sh` | `openssl version` · `curl --version` | macOS e Linux. Não usados no caminho nativo do Windows |
| **Tesseract** com idioma `por` | qualquer com `por` | OCR de páginas escaneadas sem texto digital | `tesseract --list-langs` | Não. Sem ele, só páginas com texto digital são lidas e as demais vão para revisão |
| **Chave do Gemini** | `GEMINI_API_KEY` | camadas 2 e 3 do funil de IA | veja [Variáveis, chaves e Gemini](#variáveis-chaves-e-gemini) | Não. Sem a chave, funciona o motor local (heurístico) |
| **Navegador** moderno | testado no Chromium (Chrome/Edge) | usar a interface em `http://localhost:5173` | — | Sim |

**Sistemas:** macOS, Linux (Ubuntu 24.04/Debian) e Windows 10/11 (via WSL2 ou direto no PowerShell). Cada guia abaixo traz os comandos de instalação.

**Portas livres:** `5432` (Postgres), `6379` (Redis), `8080` (API), `8001` (IA Core) e `5173` (frontend). Se for usar MinIO, Mailpit e ClamAV, libere também `9000`, `9001`, `1025`, `8025` e `3310`.

**Internet:** necessária para instalar as dependências e baixar as imagens do Docker; o processamento local não chama serviços externos, a não ser que você configure o Gemini. Não medimos requisitos mínimos de CPU, memória e disco.

## Índice

- [Requisitos para rodar localmente](#requisitos-para-rodar-localmente)
- [Executar em desenvolvimento](#executar-em-desenvolvimento)
- [Windows sem WSL e sem make](#windows--powershell-nativo-sem-wsl-e-sem-make)
- [Executar com Docker Compose em produção](#executar-com-docker-compose-em-produção)
- [Módulos da aplicação](#módulos-da-aplicação)
- [Arquitetura e pastas](#arquitetura-e-pastas)
- [Como o sistema analisa, separa e mede os documentos](#como-o-sistema-analisa-separa-e-mede-os-documentos)
- [Variáveis, chaves e Gemini](#variáveis-chaves-e-gemini)
- [Testes e solução de problemas](#testes-e-solução-de-problemas)

## Executar em desenvolvimento

A API, o worker, o IA Core e o frontend rodam na máquina; Docker inicia apenas Postgres, Redis, MinIO e Mailpit. Os comandos `make dev` e `make web` ficam em **terminais separados**. No Windows, há dois caminhos: **dentro do Ubuntu no WSL2** (`scripts/dev.sh` usa Bash e `make keys` usa UID/GID do sistema Unix) ou **direto no PowerShell, sem `make` e sem WSL** ([seção abaixo](#windows--powershell-nativo-sem-wsl-e-sem-make)). [Instalação do WSL](https://learn.microsoft.com/en-us/windows/wsl/install) · [integração do Docker Desktop com WSL2](https://docs.docker.com/desktop/features/wsl/use-wsl/).

**Pré-requisitos:** veja [Requisitos para rodar localmente](#requisitos-para-rodar-localmente). Para o OCR de imagens escaneadas, o Tesseract com o idioma `por` precisa estar na mesma máquina em que roda o IA Core; confira com `tesseract --list-langs`. O contêiner de produção do IA Core já inclui Tesseract e português.

Nos exemplos abaixo, o clone fica em `~/Hackathon`. Se você já clonou o projeto, pule `git clone` e entre na pasta existente. Substitua `python3.12` ou `python3` pela versão 3.11+ instalada na sua máquina.

### macOS — Terminal

Inicie o Docker Desktop. Se faltar Go, Node ou Python 3.12 e você usa Homebrew, instale-os com `brew install go node python@3.12`. Para OCR local, use `brew install tesseract tesseract-lang`. O pacote `tesseract` sozinho inclui apenas inglês; `tesseract-lang` acrescenta português. [Fórmulas do Homebrew](https://formulae.brew.sh/formula/tesseract).

```bash
cd ~
git clone https://github.com/JairDevsen/Hackathon.git
cd Hackathon
docker compose version
go version && node --version && python3.12 --version
make dev-deps
make keys
python3.12 -m venv .venv
.venv/bin/python -m pip install -r ia-core/requirements.txt
cd frontend && npm ci && cd ..
make dev                              # terminal 1: API, worker e IA Core
```

Abra **outro Terminal**:

```bash
cd ~/Hackathon
make web                              # terminal 2: http://localhost:5173
```

### Linux — Ubuntu 24.04/Debian

Inicie o Docker Engine e tenha o plugin Compose disponível. Seu usuário precisa conseguir executar `docker compose` sem `sudo`, pois o Makefile chama `docker` diretamente. Instale as ferramentas de sistema e o módulo de ambientes virtuais do Python padrão da distribuição. Se for usar OCR local, instale também Tesseract e o idioma português:

```bash
sudo apt update
sudo apt install -y git make openssl curl python3-venv
sudo apt install -y tesseract-ocr tesseract-ocr-por
```

Prepare e inicie o projeto:

```bash
cd ~
git clone https://github.com/JairDevsen/Hackathon.git
cd Hackathon
docker compose version
go version && node --version && python3 --version  # confirme Python 3.11+
make dev-deps
make keys
python3 -m venv .venv
.venv/bin/python -m pip install -r ia-core/requirements.txt
cd frontend && npm ci && cd ..
make dev                              # terminal 1: API, worker e IA Core
```

Abra **outro terminal**:

```bash
cd ~/Hackathon
make web                              # terminal 2: http://localhost:5173
```

Em outras distribuições Linux, instale os pacotes equivalentes pelo gerenciador da distribuição. Se `python3 --version` mostrar uma versão anterior a 3.11, instale Python 3.11 ou 3.12 e o módulo `venv` **da mesma versão** (por exemplo, `python3.12-venv`); use esse comando de Python ao criar `.venv`. A versão de Go e Node deve atender aos pré-requisitos antes de executar `make dev` e `npm ci`.

### Windows — PowerShell + Ubuntu 24.04 no WSL2

No **PowerShell como administrador**, instale o WSL2 com Ubuntu uma vez:

```powershell
wsl --install -d Ubuntu-24.04
```

Reinicie o computador se solicitado. Depois, confira a distribuição em um novo PowerShell:

```powershell
wsl --list --verbose
wsl -d Ubuntu-24.04
```

Inicie o Docker Desktop e habilite **Settings → Resources → WSL Integration → Ubuntu-24.04**. Clone o projeto no sistema de arquivos do Ubuntu (`~/Hackathon`), seguindo a [recomendação do Docker para desenvolvimento com WSL2](https://docs.docker.com/desktop/features/wsl/use-wsl/). O [Ubuntu 24.04 usa Python 3.12](https://packages.ubuntu.com/noble/amd64/python3) como `python3`; instale Go 1.26+ e Node 22+ **dentro do Ubuntu**, além das ferramentas abaixo. Para OCR local, no terminal Ubuntu:

```bash
sudo apt update
sudo apt install -y git make openssl curl python3-venv
sudo apt install -y tesseract-ocr tesseract-ocr-por
```

Ainda **no terminal Ubuntu/WSL2**:

```bash
cd ~
git clone https://github.com/JairDevsen/Hackathon.git
cd Hackathon
docker compose version
go version && node --version && python3 --version  # confirme Python 3.11+
make dev-deps
make keys
python3 -m venv .venv
.venv/bin/python -m pip install -r ia-core/requirements.txt
cd frontend && npm ci && cd ..
make dev                              # terminal Ubuntu 1: API, worker e IA Core
```

Abra **um segundo terminal Ubuntu/WSL2**:

```bash
cd ~/Hackathon
make web                              # terminal Ubuntu 2: http://localhost:5173
```

Abra `http://localhost:5173` no navegador do Windows. Não execute `make dev` no PowerShell ou CMD: o script de desenvolvimento é Bash e os caminhos da `.venv` são Unix.

### Windows — PowerShell nativo (sem WSL e sem make)

Este caminho executa os mesmos programas do `make dev` e do `make web`, um por terminal, sem Bash e sem o terminal Ubuntu. Os comandos foram montados a partir dos scripts do projeto (`Makefile`, `scripts/dev.sh` e a configuração do backend) e **não foram executados em uma máquina Windows**. Se algo falhar, abra uma issue com a mensagem de erro.

**Instale uma vez** (por exemplo, com `winget`): [Git](https://git-scm.com/download/win), [Go 1.26+](https://go.dev/dl/), [Node.js 22+](https://nodejs.org/), [Python 3.11+](https://www.python.org/downloads/windows/) (marque "Add python.exe to PATH") e o [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/). O Docker é usado só para o Postgres e o Redis. O Docker Desktop costuma usar o WSL2 internamente; você não precisa abrir nem configurar o Ubuntu. Para OCR de imagens escaneadas, instale o [Tesseract para Windows](https://github.com/UB-Mannheim/tesseract/wiki) com o idioma **Portuguese** e deixe-o no `PATH`; sem ele, só páginas com texto digital são lidas. `make`, OpenSSL e `curl` **não** são necessários.

**Preparação** (PowerShell, uma vez):

```powershell
git clone https://github.com/JairDevsen/Hackathon.git
cd Hackathon

# 1. Postgres e Redis (Docker Desktop precisa estar aberto)
docker compose -f docker-compose.dev.yml up -d postgres redis

# 2. Ambiente Python do IA Core
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ia-core\requirements.txt

# 3. Frontend
cd frontend; npm ci; cd ..

# 4. Backend: compila, migra e cria a demonstração (gera backend\bin\*.exe)
cd backend
go build -o bin/ ./cmd/migrate ./cmd/seed ./cmd/api ./cmd/worker
$env:SEED_DEMO = "true"
.\bin\migrate.exe
.\bin\seed.exe
cd ..
```

Em desenvolvimento a API gera sozinha a chave JWT em `secrets\jwt_ed25519.pem` na primeira execução; por isso `make keys` não é necessário aqui.

**Execução: abra quatro terminais PowerShell na pasta do projeto.**

```powershell
# Terminal 1: API (http://localhost:8080)
cd backend; .\bin\api.exe

# Terminal 2: worker
cd backend; .\bin\worker.exe

# Terminal 3: IA Core (http://localhost:8001)
cd ia-core; ..\.venv\Scripts\python.exe -m uvicorn ia_core.main:app --port 8001
#   Opcional, para usar o Gemini: $env:GEMINI_API_KEY = "sua-chave"  (antes de iniciar o uvicorn)

# Terminal 4: frontend (http://localhost:5173)
cd frontend; npm run dev
```

Abra `http://localhost:5173`. No primeiro início, o Firewall do Windows pode pedir permissão para `api.exe`, `worker.exe`, `python.exe` e `node.exe`: permita em **redes privadas**. O código do 2FA aparece no **terminal 1** (log da API), numa linha com `é: ` seguida de seis dígitos; se o `é` aparecer estranho no console, procure só pelos seis dígitos. Para parar, use `Ctrl+C` em cada terminal e, para os contêineres, `docker compose -f docker-compose.dev.yml down`.

Se preferir o **Git Bash**, os comandos são os mesmos, com estas diferenças: use barras `/` (`./.venv/Scripts/python.exe`, `./bin/api.exe`) e `export SEED_DEMO=true` no lugar de `$env:SEED_DEMO`. Não use `scripts/dev.sh` no Git Bash: ele chama `.venv/bin/uvicorn`, que no Windows fica em `.venv/Scripts`.

**Equivalentes dos comandos do `make`:**

| `make` | Sem `make` (PowerShell, na raiz do projeto) |
|---|---|
| `make dev-deps` | `docker compose -f docker-compose.dev.yml up -d postgres redis` |
| `make dev-down` | `docker compose -f docker-compose.dev.yml down` |
| `make dev` | terminais 1 a 3 acima (mais `bin\migrate.exe` e `bin\seed.exe` antes da primeira vez e depois de atualizar o código) |
| `make web` | `cd frontend; npm run dev` |
| `make keys` | desnecessário em desenvolvimento. O `scripts/init-secrets.py` usa UID/GID e só funciona em Unix: para produção, use um servidor Linux |
| `make test` | `cd backend; go test ./...` · `cd ia-core; ..\.venv\Scripts\python.exe -m pytest tests -q` · `cd frontend; npm test` |
| `make lint` | `cd backend; go vet ./...` · `cd frontend; npm run lint; npx tsc --noEmit` |
| `make e2e` | `cd backend; python scripts\e2e_smoke.py` (defina `$env:API="http://localhost:8080"` e `$env:MAIL_LOG` apontando para o log da API; para isso, inicie a API com `.\bin\api.exe *> ..\api.log`) |

Sem Docker, é possível instalar o Postgres 16 (com os módulos contrib) e um servidor compatível com Redis no Windows, desde que existam o banco, o usuário e a senha `citadel` (com permissão de superusuário) e o Redis em `localhost:6379`. Esse arranjo não foi validado. A produção com Docker Compose deve rodar em um servidor Linux.

### Conferir, acessar e parar

O primeiro `make dev` compila o backend Go, aplica migrações e cria a demo. Aguarde a confirmação da API e do IA Core. O Vite encaminha `/api` para `http://localhost:8080`.

| Endereço | Uso |
|---|---|
| `http://localhost:5173` | interface web e landing page |
| `http://localhost:8080/healthz` | estado básico da API; `/readyz` verifica dependências |
| `http://localhost:8001/health` | estado do IA Core e provedor de análise ativo |
| `http://localhost:9001` | console local do MinIO |
| `http://localhost:8025` | interface local do Mailpit |

Entre com `admin@agrotech.demo` e a senha de demonstração em [ACESSO.md](ACESSO.md). No desenvolvimento, o 2FA usa `MAIL_DRIVER=log`: o código aparece no terminal de `make dev` e no log da API, **não** na caixa do Mailpit. A demo cria também usuários RH e Master descritos em [ACESSO.md](ACESSO.md).

Use `Ctrl+C` em ambos os terminais da aplicação. Para parar os contêineres de dependências, na pasta do projeto execute:

```bash
make dev-down
```

Os logs ficam em `${TMPDIR:-/tmp}/citadel-api.log`, `citadel-worker.log` e `citadel-ia.log`. Para os contêineres, use `docker compose -f docker-compose.dev.yml logs -f`. O ClamAV não é iniciado no fluxo local padrão; para testá-lo, execute `docker compose -f docker-compose.dev.yml --profile av up -d` e configure `CLAMAV_ADDR=localhost:3310` no ambiente do backend. O desenvolvimento usa armazenamento em disco (`STORAGE_DRIVER=fs`) por padrão; o MinIO está disponível para testar o driver S3.

Se `.venv` já existir com Python 3.9, recrie o ambiente virtual com Python 3.11 ou superior antes de instalar as dependências. `make dev` usa **a `.venv` da raiz** para iniciar o IA Core.

## Executar com Docker Compose em produção

O procedimento de produção abaixo é para uma **VPS Linux**. No macOS ou no Windows, conecte-se à VPS pelo Terminal ou PowerShell com `ssh usuario@IP_DA_VPS` e execute os comandos lá. O [docker-compose.yml](docker-compose.yml) inclui web, API, worker, IA Core, Postgres, Redis, MinIO, ClamAV e Traefik. Só Traefik publica as portas `80/443`. Antes de subir, aponte o DNS de `DOMAIN` para o servidor, libere essas portas e configure um servidor SMTP para os códigos de 2FA e convites.

Execute como o **mesmo usuário não-root** que fará o deploy; o Compose usa seu UID/GID para a API e o worker acessarem a chave JWT e a área de upload:

```bash
cp .env.example .env
# Edite .env: DOMAIN, ACME_EMAIL, MASTER_EMAIL, MAIL_FROM e SMTP_HOST/PORT/USER/PASS.
make keys                             # preenche segredos vazios e cria a chave JWT
docker compose config --quiet         # valida o YAML e as variáveis obrigatórias
docker compose up -d --build          # constrói imagens e inicia a pilha
docker compose ps
make seed                             # somente no primeiro deploy: cria o usuário Master
```

Abra `https://<DOMAIN>` e entre com `MASTER_EMAIL` e `MASTER_PASSWORD` do `.env`. O Compose executa a migração automaticamente **antes** da API. Para usar imagens publicadas em vez de construir localmente, ajuste `TAG` no `.env` e use `docker compose pull && docker compose up -d`; imagens privadas exigem login no GHCR. Consulte [OPERACAO.md](OPERACAO.md) para backup, atualização, rollback e procedimentos operacionais.

## Módulos da aplicação

A sidebar muda conforme o perfil do usuário. [ACESSO.md](ACESSO.md) explica Master, administrador da empresa e RH, além das permissões.

| Módulo na interface | O que faz |
|---|---|
| **Início** | Resumo de lotes, pendências, revisão, vencimentos e riscos que precisam de atenção. |
| **Buscar, Funcionários e Dossiê** | Busca por CPF, matrícula, nome ou texto dos documentos; pré-cadastros do lote; dados do funcionário, exigências, documentos, pendências, linha do tempo e exportação. |
| **Lotes e Enviar lote** | Upload retomável de PDF ou imagens, validação, acompanhamento do processamento, resultado por documento, reenvio de cópia legível e exportação do lote separado. |
| **Documentos** | Lista e filtra documentos; abre páginas, campos extraídos, alertas e versões; permite baixar o PDF original, pesquisável ou anonimizado conforme a permissão. |
| **Revisão** | Prioriza baixa confiança, ilegibilidade e ausência de vínculo; permite corrigir tipo e campos, vincular funcionário, dividir/juntar páginas, rejeitar ou solicitar novo envio. |
| **Pendências, Riscos trabalhistas e Calendário** | Aplica a matriz de documentos exigidos, acompanha faltas e vencimentos e mostra possíveis divergências de jornada, remuneração, rescisão e prova documental. |
| **Relatórios e Escala 950k & FinOps** | Exporta relatórios CSV/XLSX e mostra consumo de análise; a simulação de escala usa premissas, não preços oficiais de modelos. |
| **Configurações e Conta** | Administrador define unidades, setores, cargos, exigências, campos de cadastro, usuários, retenção e acesso de suporte; consulta plano, auditoria e logs. |
| **Plataforma Master** | Operador gerencia empresas, planos, catálogo, filas de processamento, benchmark da IA, usuários e auditoria global. |
| **Landing page** | Apresenta o produto, demonstra um lote fictício e recebe pedidos de contato. |

**Limites atuais:** políticas de retenção podem ser configuradas, mas a exclusão automática por prazo ainda não está implementada. Relatórios não têm agendamento mensal por e-mail. O motor local é heurístico; documentos manuscritos ou imagens ruins exigem mais revisão. Consulte o estado detalhado de cada requisito em [ESPECIFICACAO_FUNCIONAL.md](ESPECIFICACAO_FUNCIONAL.md).

## Arquitetura e pastas

| Caminho / serviço | Responsabilidade |
|---|---|
| [frontend/](frontend/) | React, TypeScript, Vite e Tailwind. `src/landing` contém a página pública; `src/features/rh`, `empresa` e `master` contêm as telas por perfil; `src/app` define rotas e navegação. |
| [backend/cmd/api/](backend/cmd/api/) | Servidor Go/Gin: autenticação e 2FA, API REST `/api/v1`, autorização, uploads, busca, revisão, relatórios e configurações. |
| [backend/cmd/worker/](backend/cmd/worker/) | Processa lotes em segundo plano com Redis/asynq, retoma falhas e executa verificações periódicas de conformidade e auditoria. |
| [backend/cmd/migrate/](backend/cmd/migrate/) e [backend/cmd/seed/](backend/cmd/seed/) | Atualizam o banco e criam usuários/dados iniciais. Migrações SQL estão em `backend/internal/database/migrations/`. |
| [ia-core/](ia-core/) | Serviço Python/FastAPI que fatia PDFs/imagens, classifica páginas, extrai campos, agrupa documentos, renderiza PDFs e envia checkpoints à API. |
| **Postgres 16** | Dados de empresas, funcionários, documentos e auditoria; isolamento por empresa com RLS. |
| **Redis** | Fila do worker, códigos de 2FA, limites de requisição e estado temporário. |
| **MinIO/S3** | Objetos dos documentos; em produção, arquivos são armazenados cifrados. |
| **ClamAV e SMTP** | Verificação antivírus dos uploads e envio de códigos, convites e avisos. |

A API pública está descrita em [backend/api/openapi.yaml](backend/api/openapi.yaml). Decisões técnicas do backend estão em [backend/docs/adr/](backend/docs/adr/).

### Como os serviços processam um lote

1. O frontend envia o arquivo em partes para a API. `backend/internal/batches/` controla tamanho, retomada, cota, hash e verificação antivírus quando o ClamAV está configurado.
2. A API guarda o arquivo e publica uma tarefa no Redis. `backend/cmd/worker/` consome a tarefa e solicita ao IA Core o fatiamento e a análise das páginas.
3. `ia-core/ia_core/fatiar.py` prepara páginas e miniaturas; `providers.py` escolhe o motor local ou Gemini; `catalogo.py` e `extracao.py` definem tipos e campos; `agrupar.py` reúne páginas em documentos.
4. O IA Core devolve resultados por callbacks assinados. `backend/internal/documents/` grava os documentos, cria ou associa pré-cadastros e encaminha casos duvidosos à revisão. `backend/internal/compliance/` recalcula exigências e indicadores.
5. A interface acompanha o progresso do lote e apresenta o resultado, os documentos e as ações pendentes. O worker também executa rotinas periódicas de vencimento e verificação da auditoria.

No backend, `internal/auth/` cuida de login, 2FA e permissões; `internal/database/` aplica as migrações e o isolamento por empresa; `internal/storage/` acessa os arquivos; `internal/audit/` registra ações; e `internal/notify/` envia e-mails. No IA Core, `render.py` gera versões pesquisáveis ou anonimizadas, e `qualidade_img.py` identifica imagens com baixa nitidez.

### Como o sistema analisa, separa e mede os documentos

Esta seção descreve o que acontece com um arquivo enviado, da página escaneada até os indicadores do painel. Os nomes entre parênteses são os arquivos onde cada etapa está implementada.

**1. Separação do lote em documentos** (`ia-core/ia_core/fatiar.py`, `agrupar.py`)

1. O PDF ou a imagem vira uma lista de páginas, renderizadas em 150 dpi, com miniatura e as palavras com suas coordenadas. Quando a página tem texto digital, ele é lido direto; quando é só imagem, usa-se OCR (Tesseract em português) se estiver instalado.
2. Antes de ler o conteúdo, o sistema confere a imagem: página sem conteúdo é marcada **em branco** (e descartada) e página com baixa nitidez é marcada **borrada** (`qualidade_img.py`, limite configurável em `IA_NITIDEZ_MIN`). Uma foto desfocada não é confundida com página em branco: ela vira um alerta de erro e pede uma imagem melhor. O limite foi calibrado com amostras sintéticas; ajuste-o com imagens reais.
3. Cada página recebe um **tipo** (um dos 32 do catálogo, ou `OUTRO`), uma confiança e a informação "inicia um documento novo?".
4. O agrupamento é determinístico: uma página que inicia documento abre um grupo; verso e continuações são anexados ao último documento **do mesmo tipo**, mesmo que haja páginas de outros tipos no meio (frente e verso digitalizados separados). Página em branco encerra o documento corrente. O resultado é a lista de documentos, cada um com as suas páginas.
5. O sistema tolera falha no meio do processamento: cada página é gravada ao ser analisada, e o worker retoma de onde parou.

**2. Classificação e extração** (`providers.py`, `catalogo.py`, `extracao.py`, `schemas.py`)

O processamento é um funil que só gasta IA quando o custo menor não resolve:

| Camada | O que faz | Custo |
|---|---|---|
| **0** | Se a mesma página (SHA-256) já foi analisada, reaproveita o resultado. | Zero |
| **1** | Texto nativo ou OCR + palavras-chave do catálogo + expressões regulares para CPF, datas, valores, horas etc. | Zero |
| **2** | Gemini Flash-Lite sobre o texto já extraído, quando a camada 1 não tem confiança. | Baixo |
| **3** | Gemini Flash Vision sobre a imagem reduzida (1024 px, WebP), com modelo Pro de reserva. | Maior |

Sem `GEMINI_API_KEY`, só as camadas 0 e 1 funcionam (motor local). A integração com o Gemini está implementada, mas não foi exercitada com uma chave real neste repositório. Cada tipo tem um schema com os campos esperados (por exemplo, horas e intervalo no cartão de ponto, bruto, FGTS e horas extras no holerite). Cada página registra a camada usada e os tokens consumidos, que alimentam a tela de FinOps.

**3. Validações e alertas** (`validacoes.py`, `checklist.py`, `backend/internal/documents/`)

Sobre os campos extraídos, regras objetivas geram **alertas** e **não conformidades**: jornada acima de 10 horas, intervalo menor que 1 hora, ponto britânico (marcações idênticas), FGTS depositado diferente do devido (valores lidos no holerite ou na guia), certidão ou documento vencido, ausência de assinatura, recusa sem testemunhas, CPF inválido e nome diferente do cadastro. Cada documento também recebe um **checklist** (por exemplo, NR-7 no ASO) e um status de mobilização (apto, em análise ou bloqueado).

**4. Vínculo com o funcionário e pré-cadastro** (`backend/internal/documents/ingest.go`)

1. A busca segue esta ordem: CPF (comparado por hash cego, sem guardar o CPF em claro) → matrícula → nome por similaridade (a partir de 0,85 e só se não houver empate). Vínculo apenas por nome sempre vai para revisão. Um CPF válido e desconhecido nunca é ligado a outra pessoa por nome.
2. Se não há cadastro, o CPF é válido, o nome foi lido e a página está legível, o sistema **cria um pré-cadastro** (nome, CPF e matrícula do documento). O RH não precisa cadastrar antes. A empresa pode desligar esse comportamento, e o limite de funcionários do plano é respeitado. O funcionário fica marcado como "pré-cadastrado" até o RH conferir e completar admissão, cargo e setor.
3. Um documento vai para a **fila de revisão humana** quando a confiança fica abaixo do limiar da empresa (padrão 0,75), a página é ilegível ou borrada, o tipo não foi identificado, há mais de um documento na imagem, falta vínculo, há possível duplicata ou existe alerta de erro. O lote informa quantos documentos exigem **classificação manual**.
4. Na revisão, a pessoa escolhe o tipo, preenche o formulário daquele tipo (transcrição manual), vincula ou cria o funcionário, divide ou junta páginas, rejeita, solicita novo envio ou envia uma cópia legível que substitui o documento ilegível. Também é possível **lançar um documento manualmente** pelo dossiê, sem imagem. A transcrição digitada é registrada como manual: ela alimenta os indicadores, mas **não comprova** uma exigência documental.
5. Cada documento recebe nome de arquivo e pasta padronizados (empresa/funcionário, com o CPF só parcial). O lote pode ser baixado como ZIP organizado, com cópias anonimizadas (LGPD) e um manifesto de auditoria.

**5. Conformidade: o que falta e o que vence** (`backend/internal/compliance/engine.go`)

A empresa define, por **setor, cargo ou funcionário**, quais documentos são exigidos e em qual momento (admissão, mensal, anual, periódico, desligamento). Quando regras se sobrepõem, vale a mais específica: funcionário, depois cargo, depois setor, depois todos. Assim, o sistema não cobra um documento de quem não precisa dele. Para cada funcionário e exigência, o motor calcula um status (`OK`, `PENDENTE`, `VENCIDO`, `A_VENCER` ou `DISPENSADO`, esta última com justificativa auditada). Sem data de admissão, ele não inventa meses de pendência. O cálculo roda ao concluir um lote, após cada revisão e em rotina diária do worker (03:00).

**6. Indicadores de risco trabalhista** (`backend/internal/compliance/risk.go`)

Um segundo cálculo cruza os documentos do mesmo funcionário e grava **indicadores** com severidade (alto, médio, baixo), categoria, texto explicativo, referência legal e o documento de origem. Exemplos:

| Indicador | Como é detectado | Base citada |
|---|---|---|
| Jornada acima de 10 h, intervalo menor que 1 h, ponto britânico | Validações do cartão de ponto | CLT art. 59 e 71; TST Súmula 338 |
| Horas extras sem pagamento | Ponto da competência com horas extras × holerite da mesma competência sem valor pago | CLT art. 59 §1º; CF art. 7º, XVI |
| FGTS divergente | Valor depositado × valor devido, lidos no holerite ou na guia | Lei 8.036/90 art. 15 |
| Férias sem comprovante | Vínculo com mais de 23 meses e nenhum recibo de férias nos últimos 24 | CLT art. 137 |
| TRCT fora do prazo ou ausente | Data do TRCT × 10 dias do desligamento | CLT art. 477 §6º e §8º |
| Vínculo sem registro, documento fora do vínculo | Holerite/ponto sem contrato, ficha ou CTPS; competência antes da admissão ou depois do desligamento | CLT art. 29 |
| ASO ou treinamento NR vencido, certidão vencida | Itens de conformidade vencidos | NR-7, NR-1 |
| Qualidade documental | Imagem borrada, página ilegível, dados divergentes, CPF inválido | CLT art. 818 (prova) |

Pontos importantes: os indicadores são **sinais de triagem**, não parecer jurídico nem prova de infração, e o texto do sistema diz isso. Documentos de saúde seguem a permissão `saude:ler`. Somente o administrador pode **ignorar** um indicador (com justificativa registrada na auditoria) ou reabri-lo, e o recálculo preserva essa decisão. Dados digitados manualmente podem **acrescentar** indicadores, mas nunca fazem um indicador de ausência desaparecer: isso exige um documento com imagem.

**7. Métricas e painéis** (`backend/internal/http/reports.go`)

Todos os números são calculados no banco, respeitando o isolamento por empresa e as unidades do usuário:

| Tela / endpoint | O que mostra |
|---|---|
| Início, `/metrics/overview` | Conformidade (% de itens `OK` entre os exigidos), funcionários ativos e com pendência, vencidos, a vencer em 30 dias, documentos aguardando revisão, ilegíveis, pré-cadastros, riscos em aberto por severidade e principais não conformidades. |
| `/metrics/compliance` | Pendências por tipo de documento e conformidade por unidade. |
| `/metrics/processing` | Volume mensal de páginas e documentos e tempo médio por lote. |
| Escala 950k & FinOps, `/metrics/finops` | Páginas e tokens por camada do funil, economia do cache e do funil local, e simulação de escala com premissas editáveis (não são preços oficiais de modelos). |
| Riscos trabalhistas, `/risks` | Lista filtrável por status e funcionário, com base legal e ação de ignorar para o administrador. |
| Relatórios, `/reports/:tipo` | Exportação CSV/XLSX de conformidade, pendências, não conformidades e armazenamento. |

Cada ação relevante (revisão, lançamento manual, dispensa, ignorar indicador, download) entra na **auditoria encadeada por hash**, que o worker verifica periodicamente.

## Variáveis, chaves e Gemini

| Ambiente | De onde vêm os valores |
|---|---|
| **Desenvolvimento (`make dev`)** | `backend/internal/config/config.go` fornece padrões locais. `scripts/dev.sh` define `SEED_DEMO=true`. A chave JWT é criada por `make keys`. Esse fluxo **não lê** o `.env` de produção. |
| **IA Core local com Gemini** | `scripts/dev.sh` lê somente `ia-core/.env.local` para `GEMINI_API_KEY` e opções `GEMINI_MODEL*`; esse arquivo é ignorado pelo Git. |
| **Produção (Compose)** | `.env` fornece credenciais e opções; `docker-compose.yml` monta a chave JWT e repassa as variáveis a cada serviço. `make keys` preenche os segredos em branco sem mostrá-los no terminal. |

Sem `GEMINI_API_KEY`, o IA Core usa **texto do PDF, OCR local com Tesseract e regras determinísticas**. Para usar Gemini no desenvolvimento:

```bash
cp ia-core/.env.local.example ia-core/.env.local
# Preencha GEMINI_API_KEY em ia-core/.env.local e reinicie make dev.
curl http://localhost:8001/health
```

O campo `provider` passa de `local-heuristico` para `gemini:<modelo>`. Isso mostra qual provedor foi selecionado, mas uma análise real é necessária para validar a chave. Algumas páginas com texto nativo suficiente continuam sendo resolvidas localmente. Em produção, configure `GEMINI_API_KEY` no `.env` se decidir usar esse provedor; páginas difíceis podem enviar imagem ou texto ao serviço externo. O provedor Vertex AI ainda não está implementado.

`.env`, `ia-core/.env.local`, chaves privadas e credenciais de provedores são ignorados pelo Git. Execute `make check-secrets` antes de preparar um commit; `make install-hooks` ativa essa checagem automaticamente. **Não use `git add -f` para incluí-los.** Se uma chave já foi publicada, revogue ou rotacione-a. Veja todas as opções em [VARIAVEIS_AMBIENTE.md](VARIAVEIS_AMBIENTE.md).

## Testes e solução de problemas

| Camada | Comando |
|---|---|
| Backend | `cd backend && go test -race ./...` |
| IA Core | `.venv/bin/python -m pip install pytest && cd ia-core && ../.venv/bin/python -m pytest tests -q` |
| Frontend | `cd frontend && npm test && npm run lint && npm run build` |
| Segredos preparados para commit | `make check-secrets` |

Os testes de isolamento RLS e auditoria que usam banco precisam de `DATABASE_URL`. Há scripts de ponta a ponta em `backend/scripts/`; use-os com a pilha local em execução e consulte os próprios arquivos para os parâmetros.

| Sintoma | Verificação rápida |
|---|---|
| `make dev` reclama da `.venv` | Confira `.venv/bin/python --version` (3.11+) e instale `ia-core/requirements.txt`. |
| A interface abre, mas não carrega dados | Confirme `http://localhost:8080/healthz` e veja `citadel-api.log`; o Vite precisa estar na porta `5173`. |
| IA Core retorna `local-heuristico` | É o comportamento esperado sem `GEMINI_API_KEY`; reinicie `make dev` depois de editar `ia-core/.env.local`. |
| Documento escaneado fica sem texto | Confira `tesseract --list-langs` e a presença do idioma `por`; veja `citadel-ia.log`. |
| Login pede código | No desenvolvimento, procure o código no terminal de `make dev`; em produção, confira SMTP e os logs da API. |
| Lote não avança | Veja os logs do worker e IA Core; em produção, `docker compose logs -f worker ia-core`. |

Material do protótipo original do hackathon: [docs/legacy/](docs/legacy/).
