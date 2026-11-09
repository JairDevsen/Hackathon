# Citadel IA

Plataforma multiempresa para **qualquer organização que precise controlar o risco documental e trabalhista de quem trabalha para ela**: empregados próprios, trabalhadores de empresas terceirizadas e fornecedores. Ela recebe lotes de documentos escaneados, separa as páginas, identifica o tipo, extrai os dados, reúne tudo por pessoa (CPF) e por empresa (CNPJ) e mostra o que está faltando, vencido ou inconsistente, antes que isso vire autuação, passivo ou processo.

Serve a empresas de qualquer porte e setor, de um escritório com poucos contratos a um grupo com muitos contratados, e também a escritórios jurídicos e consultorias que fazem essa gestão para seus clientes. Cada empresa define os próprios documentos obrigatórios, por cargo, setor ou funcionário. Escritórios como a Bernhoeft, que atuam nessa gestão, são um exemplo de uso, não o único: o sistema não carrega regras nem dados de nenhum cliente específico.

Em termos práticos, o RH e o jurídico:

- enviam documentos em lote, sem precisar separá-los antes;
- acompanham o processamento e revisam apenas o que a leitura automática deixou em dúvida;
- consultam o dossiê de cada pessoa e de cada empresa contratada;
- veem pendências, vencimentos e **indicadores de risco** para priorizar a conferência.

> É um protótipo. Os indicadores são sinais de triagem para o RH e o jurídico, não parecer jurídico, e a leitura por IA precisa ser validada com os documentos reais de cada operação.

**Fluxo principal:** `envio do lote → validação e armazenamento → análise por página → agrupamento em documentos → pré-cadastro/vínculo do funcionário → revisão humana quando necessária → dossiê, conformidade e alertas`.

Quando o documento permite identificar nome e CPF válido, o sistema pré-cadastra o funcionário por padrão. Documentos ilegíveis ou sem tipo identificado entram na fila para classificação, transcrição manual ou envio de uma cópia legível. A transcrição manual fica identificada como tal e não comprova sozinha uma exigência documental. Os indicadores de risco são sinais para conferência do RH e do jurídico, não conclusões jurídicas.

## Como funciona a aplicação

O trabalho do RH começa pelo envio de um lote. A aplicação processa o arquivo em segundo plano e organiza os resultados para conferência:

1. **Receber e proteger o arquivo.** A API verifica formato, tamanho, cota e duplicidade; executa antivírus quando configurado e guarda o original cifrado. O texto lido por OCR (texto completo, palavras com posição e análise de cada página) também é gravado **cifrado** no banco com a chave da empresa; a busca em texto usa só o texto anonimizado.
2. **Preparar as páginas.** O worker solicita ao IA Core a conversão em imagens e miniaturas. O texto vem da camada digital do PDF ou do OCR quando disponível.
3. **Reconhecer os documentos.** Cada página recebe tipo, campos, confiança e indicação de início ou continuação. O agrupador reúne as páginas de cada documento.
4. **Identificar pessoa e empresa.** O backend procura o funcionário por CPF, matrícula ou nome e identifica fornecedores pelo CNPJ. Quando os dados permitem, cria pré-cadastros para o RH completar.
5. **Conferir as exceções.** Leituras duvidosas entram na revisão humana. O usuário pode corrigir, vincular, dividir, juntar, rejeitar ou solicitar uma cópia melhor.
6. **Atualizar a gestão documental.** Os documentos aparecem nos dossiês. Regras de exigência e cruzamentos alimentam pendências, vencimentos, indicadores e relatórios.

**Exemplo:** um PDF com holerite, cartão de ponto de duas páginas e ASO pode gerar três documentos. O ponto é agrupado pelas marcas de continuação; o CPF ajuda a localizar o titular; e o CNPJ pode associar os registros a uma terceirizada. Se o ASO estiver ilegível, ele permanece disponível para tratamento. Quando exigido e sem outro comprovante elegível no dossiê, o ASO continua pendente até a regularização ou uma dispensa justificada.

### O papel da IA e das regras

O **IA Core** lê e classifica as páginas. Sem chave de IA, usa texto nativo, Tesseract e expressões regulares. Com uma chave da OpenAI ou do Gemini, pode encaminhar páginas ao modelo sobre texto ou imagem. Páginas idênticas já analisadas em outro lote da mesma empresa podem reutilizar a análise por SHA-256. O serviço ativo analisa uma página por vez; o extrator em janelas de oito páginas pertence ao material complementar em `ia-generator-documents/`.

O **backend Go** decide vínculos, revisão, exigências e indicadores. A empresa configura quais documentos cobrar de todos, de um setor, de um cargo ou de uma pessoa. A precedência é **funcionário → cargo → setor → todos**. As correções humanas ficam registradas, mas não retreinam automaticamente o modelo.

### Como interpretar os resultados

| Resultado | O que significa |
|---|---|
| **Status do documento** | Situação no fluxo: autoaprovado, aguardando revisão, revisado, rejeitado ou substituído. |
| **Conformidade** | Atendimento às exigências configuradas: OK, pendente, vencido, a vencer ou dispensado. |
| **Checklist e mobilização** | Conferências de um documento, como legibilidade e validade; o rótulo “apto” não representa liberação consolidada do funcionário. |
| **Indicador de risco** | Sinal para conferência, derivado do conteúdo ou de cruzamentos entre documentos. Não é probabilidade de processo nem conclusão jurídica. |

Um documento revisado pode continuar vencido ou com um indicador de risco. Um registro manual pode acrescentar informações, mas não comprova a exigência documental. A conformidade do painel é `100 × itens OK / itens não dispensados`; sem itens avaliáveis, a taxa pode ficar sem valor.

### Login e proteção dos dados

O acesso usa senha com hash Argon2id e código por e-mail. Há dispositivo confiável por até 30 dias, JWT de acesso de 12 minutos e refresh rotativo em cookie HttpOnly. Algumas ações, como exportar o dossiê e alterar permissões, exigem nova confirmação por código. Master administra a plataforma; admin configura a empresa; RH executa a operação, com restrição por unidade quando definida.

O banco aplica isolamento por empresa com RLS; arquivos e CPF do cadastro usam criptografia, e ações relevantes entram na auditoria encadeada por hash. OCR e checkpoints podem conter dados pessoais em claro no banco. Cópias com tarjas dependem da detecção e das coordenadas disponíveis, e precisam de conferência. Os controles e suas limitações estão detalhados no guia abaixo.

### Documentação completa e preparação para a banca

Para entender em detalhe **como a IA lê, classifica, separa e avalia os documentos** (camadas, OCR, agrupamento, indicadores de risco, limites e medições), veja [COMO_A_IA_FUNCIONA.md](COMO_A_IA_FUNCIONA.md).
O [guia completo do sistema e da banca](DOCUMENTACAO_COMPLETA_SISTEMA_E_GUIA_BANCA.md) reúne arquitetura, funcionalidades, o catálogo de tipos de documentos, os indicadores de risco, regras de IA, segurança, APIs e **40 perguntas com respostas**. Use este README para entender o fluxo e executar a aplicação; consulte o guia para fórmulas, critérios exatos, evidências e limitações.

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
| **Chave de IA (OpenAI ou Gemini)** | `OPENAI_API_KEY` ou `GEMINI_API_KEY` | camadas 2 e 3 do funil de IA | veja [Variáveis, chaves e IA externa](#variáveis-chaves-e-ia-externa) | Não. Sem a chave, funciona o motor local (heurístico) |
| **Navegador** moderno | testado no Chromium (Chrome/Edge) | usar a interface em `http://localhost:5173` | — | Sim |

**Sistemas:** macOS, Linux (Ubuntu 24.04/Debian) e Windows 10/11 (via WSL2 ou direto no PowerShell). Cada guia abaixo traz os comandos de instalação.

**Portas livres:** `5432` (Postgres), `6379` (Redis), `8080` (API), `8001` (IA Core) e `5173` (frontend). Se for usar MinIO, Mailpit e ClamAV, libere também `9000`, `9001`, `1025`, `8025` e `3310`.

**Internet:** necessária para instalar as dependências e baixar as imagens do Docker. O processamento documental local não chama modelos externos; OpenAI/Gemini, SMTP externo, CAPTCHA e verificação de senha vazada podem depender de rede conforme a configuração. Não medimos requisitos mínimos de CPU, memória e disco.

## Índice

- [Como funciona a aplicação](#como-funciona-a-aplicação)
- [Documentação completa e preparação para a banca](#documentação-completa-e-preparação-para-a-banca)
- [Requisitos para rodar localmente](#requisitos-para-rodar-localmente)
- [Executar em desenvolvimento](#executar-em-desenvolvimento)
- [Windows sem WSL e sem make](#windows--powershell-nativo-sem-wsl-e-sem-make)
- [Executar com Docker Compose em produção](#executar-com-docker-compose-em-produção)
- [Módulos da aplicação](#módulos-da-aplicação)
- [Arquitetura e pastas](#arquitetura-e-pastas)
- [Como o sistema analisa, separa e mede os documentos](#como-o-sistema-analisa-separa-e-mede-os-documentos)
- [Variáveis, chaves e IA externa](#variáveis-chaves-e-ia-externa)
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
#   Opcional, para usar IA externa: $env:OPENAI_API_KEY = "<sua-chave>"  (ou GEMINI_API_KEY; antes de iniciar o uvicorn)

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
| **Lotes e Enviar lote** | Upload retomável de PDF ou imagens, validação, acompanhamento do processamento, resultado por documento, reenvio de cópia legível e exportação do lote separado e exclusão do lote enviado, com confirmação e motivo auditado. |
| **Documentos** | Lista e filtra documentos; abre páginas, campos extraídos, alertas e versões; permite baixar o PDF original, pesquisável ou anonimizado conforme a permissão. |
| **Revisão** | Prioriza baixa confiança, ilegibilidade e ausência de vínculo; permite corrigir tipo e campos, vincular funcionário, dividir/juntar páginas, rejeitar ou solicitar novo envio. |
| **Setores** | Conformidade, pendências e riscos de quem trabalha em cada setor (próprios e terceirizados), com a ficha do setor e as pessoas dele. |
| **Terceirizadas** e **Fornecedores** | Empresas agrupadas pelo CNPJ lido nos documentos, em listas separadas: dados e contrato, documentos da empresa, funcionários alocados, documentos exigidos e indicadores de risco de processo trabalhista para a contratante. |
| **Localizador** (Ctrl/Cmd+K) | Uma busca no topo acha pessoa (nome, matrícula, CPF), setor ou empresa (nome, CNPJ) e abre a ficha. |
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
3. `ia-core/ia_core/fatiar.py` prepara páginas e miniaturas; `providers.py` escolhe o motor local, a OpenAI ou o Gemini; `catalogo.py` e `extracao.py` definem tipos e campos; `agrupar.py` reúne páginas em documentos.
4. O IA Core devolve resultados por callbacks assinados. `backend/internal/documents/` grava os documentos, cria ou associa pré-cadastros e encaminha casos duvidosos à revisão. `backend/internal/compliance/` recalcula exigências e indicadores.
5. A interface acompanha o progresso do lote e apresenta o resultado, os documentos e as ações pendentes. O worker também executa rotinas periódicas de vencimento e verificação da auditoria.

No backend, `internal/auth/` cuida de login, 2FA e permissões; `internal/database/` aplica as migrações e o isolamento por empresa; `internal/storage/` acessa os arquivos; `internal/audit/` registra ações; e `internal/notify/` envia e-mails. No IA Core, `render.py` gera versões pesquisáveis ou anonimizadas, e `qualidade_img.py` identifica imagens com baixa nitidez.

### Como o sistema analisa, separa e mede os documentos

Esta seção descreve o que acontece com um arquivo enviado, da página escaneada até os indicadores do painel. Os nomes entre parênteses são os arquivos onde cada etapa está implementada.

**1. Separação do lote em documentos** (`ia-core/ia_core/fatiar.py`, `agrupar.py`)

1. O PDF vira páginas renderizadas em 150 dpi; entradas de imagem são convertidas em PNG. O sistema gera miniaturas e extrai texto e coordenadas quando disponíveis. Texto digital é lido direto; páginas sem texto podem usar OCR (Tesseract em português) quando instalado. O OCR feito depois do fatiamento nem sempre gera coordenadas para destaques e tarjas.
2. Quando não há texto embutido, o provedor verifica a nitidez da imagem (`qualidade_img.py`, limite configurável em `IA_NITIDEZ_MIN`). No modo local, também distingue página **em branco**, descartada do agrupamento, de conteúdo sem OCR suficiente, preservado para revisão. A heurística de borrão pode gerar falsos positivos e negativos; o limite foi calibrado com amostras sintéticas.
3. Cada página recebe um **tipo** (um dos 44 do catálogo, incluindo `OUTRO`), uma confiança e a informação "inicia um documento novo?".
4. O agrupamento (`agrupar.py`) é determinístico e vale para qualquer provedor. Para decidir se uma página continua o documento anterior, usa, nesta ordem:
   - **Marcador de paginação impresso** ("Página 2/3", "Folha 2/2", "fls. 3 de 5", inclusive quando o OCR perde a barra e lê "212"): a página entra no documento aberto se a contagem fecha, **mesmo que o tipo lido seja outro** (a página 1 pode ter vindo rotacionada ou ilegível). "Página 1/N" abre um documento novo.
   - **Número que identifica o documento** (ex.: número do objeto do AR, que se repete na frente e no verso): liga as páginas mesmo longe uma da outra. Se os dois lados têm número legível e ele difere, nunca são juntados.
   - **Páginas complementares conhecidas**: o *Termo de quitação* entra no TRCT e os *Dados do recebimento* entram no AR, antes ou depois da página principal, vinculados pelo CPF quando há outra página no meio.
   - A marca `inicia_documento=false` informada pelo provedor, anexando ao último documento do **mesmo tipo**.
   O tipo do documento é o da página lida com mais confiança: uma página ilegível não rebaixa o contrato a "Outro". Páginas em branco são omitidas, e folhas com vários documentos não são recortadas automaticamente. Páginas escaneadas ou fotografadas de cabeça para baixo (ou de lado) são **giradas de verdade no fatiamento** (`orientacao.py`): a orientação é detectada por OCR numa cópia reduzida e a imagem guardada já fica na posição certa, então a visualização, o download e a cópia anonimizada saem corretos. Em 3 lotes do gerador, 8 de 9 páginas rotacionadas foram endireitadas e nenhuma página normal foi girada; páginas quase vazias, só com marca d'água, não têm texto para decidir. Custa cerca de 1 s por página escaneada. Lotes já enviados não são corrigidos: reenvie o arquivo.
   **Medição** (motor local, 6 lotes fictícios do gerador, 143 documentos): documentos de várias páginas separados ou unidos errado caíram de **15 de 15 para 2 de 15**; nenhum documento de uma página só passou a ser juntado por engano, e os documentos com tipo e páginas exatamente iguais ao gabarito subiram de 96 para 115. Ainda erram cartões de ponto em que o OCR não lê nem o marcador "Folha 2/2". Os erros de **tipo** que restam (26 de 143) vêm de páginas ilegíveis, manuscritas ou muito degradadas, que o motor local não lê; com um provedor de IA externo a leitura tende a melhorar, mas isso não foi medido.
5. O sistema tolera falha no meio do processamento: cada página é gravada ao ser analisada, e o worker retoma de onde parou.

**2. Classificação e extração** (`providers.py`, `catalogo.py`, `extracao.py`, `schemas.py`)

O processamento é um funil que só gasta IA quando o custo menor não resolve:

| Camada | O que faz | Uso de modelo externo |
|---|---|---|
| **0** | Reaproveita análise de página idêntica já concluída em outro lote da mesma empresa. | Nenhuma nova chamada |
| **1** | Texto nativo ou OCR + palavras-chave do catálogo e expressões regulares. | Nenhuma chamada |
| **2** | Modelo leve (`OPENAI_MODEL_LITE` / `GEMINI_MODEL_LITE`) sobre texto elegível com pelo menos 120 caracteres, quando a confiança local fica abaixo de 0,85. | Chamada sobre texto |
| **3** | Modelo multimodal sobre imagem reduzida (lado máximo padrão de 1024 px, WebP), com modelo reserva maior para respostas difíceis. | Chamada sobre imagem |

Sem chave de IA, só as camadas 0 e 1 funcionam (motor local). Com a chave, tipos visuais, manuscritos e páginas sem texto suficiente podem ir diretamente à visão; o fluxo não passa obrigatoriamente por todas as camadas. O limiar de 0,85 é de roteamento local, enquanto o limiar da empresa, padrão 0,75, decide a revisão na ingestão.

Há schemas especializados para alguns tipos, como ponto, holerite e ASO; os demais usam campos base. Esses schemas também alimentam os formulários e não garantem que a regex local extraia todos os campos. Camada e tokens são registrados por página e agregados por documento no FinOps. Zero tokens externos não significa custo zero de infraestrutura. O [guia completo](DOCUMENTACAO_COMPLETA_SISTEMA_E_GUIA_BANCA.md#funil) descreve os critérios de fallback e o escopo das verificações realizadas.

**3. Validações e alertas** (`validacoes.py`, `checklist.py`, `backend/internal/documents/`)

Sobre o texto e os campos extraídos, regras geram **alertas** e **não conformidades**: jornada acima de 10 horas, intervalo menor que 1 hora, menção a ponto britânico/horários idênticos, FGTS depositado diferente do devido (valores lidos no holerite ou na guia), certidão ou documento vencido, ausência de sinal textual de assinatura, recusa sem testemunhas, CPF inválido e nome diferente do cadastro. Cada documento também recebe um **checklist** (por exemplo, NR-7 no ASO) e um status de mobilização (apto, em análise ou bloqueado). A análise não autentica assinaturas nem consulta depósitos oficiais.

**4. Vínculo com o funcionário e pré-cadastro** (`backend/internal/documents/ingest.go`)

1. A busca segue esta ordem: CPF por hash cego → matrícula → nome por similaridade (a partir de 0,85 e com margem mínima de 0,10 para o segundo candidato). O CPF do cadastro é cifrado e sua exibição é mascarada; o texto OCR e os checkpoints podem conter o número em claro. Vínculo apenas por nome sempre vai para revisão. Um CPF válido e desconhecido nunca é ligado a outra pessoa por nome.
2. Se não há cadastro, o CPF é válido, o nome foi lido e a página está legível, o sistema **cria um pré-cadastro** (nome, CPF e matrícula do documento). O RH não precisa cadastrar antes. A empresa pode desligar esse comportamento, e o limite de funcionários do plano é respeitado. O funcionário fica marcado como "pré-cadastrado" até o RH conferir e completar admissão, cargo e setor.
3. Um documento vai para a **fila de revisão humana** quando a confiança fica abaixo do limiar da empresa (padrão 0,75), a página é ilegível ou borrada, o tipo não foi identificado, há mais de um documento na imagem, falta vínculo, há possível duplicata ou existe alerta de erro. O lote informa quantos documentos exigem **classificação manual**.
4. **Documento repetido, escaneado de outra forma:** o texto lido por OCR é comparado com o dos documentos já guardados da mesma pessoa ou empresa. Se a similaridade passa do limite da empresa (**padrão 85%, ajustável em Configurações, mínimo 70%**) e os valores (números e datas) coincidem, só uma cópia, a de leitura mais confiável, fica; a outra é descartada e pode ser **restaurada** no lote. Detalhes, calibração e limites em [COMO_A_IA_FUNCIONA.md](COMO_A_IA_FUNCIONA.md).
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

**6b. Fornecedores e terceirizadas: três grupos de trabalhadores** (`backend/internal/documents/suppliers.go`, `compliance/risk.go`)

O módulo reúne documentos de prestadores para apoiar a conferência de obrigações e de sinais de risco para a contratante. As referências jurídicas exibidas são as cadastradas no código e precisam de validação no contexto de uso. O sistema separa os vínculos em **três grupos**: a **própria empresa**, as **terceirizadas** e os **fornecedores** (que também podem ter trabalhadores alocados). A separação aparece em funcionários, documentos e indicadores do painel.

1. **Identificação pelo CNPJ.** O IA Core lê o CNPJ da empresa do documento (`empresa_cnpj`). Em um contrato, que cita duas empresas, vale o da **contratada/prestadora**, não o da contratante (`ia_core/extracao.py`). Um CNPJ igual ao da própria empresa não cria fornecedor.
2. **Pré-cadastro do fornecedor.** CNPJ válido e desconhecido cria um fornecedor "pré-cadastrado" (a mesma chave `pre_cadastro_automatico` dos funcionários). O RH completa o tipo (terceirizada ou fornecedor), a criticidade e as datas do contrato. Um CNPJ válido nunca é fundido com outro: o CNPJ é único por empresa contratante.
3. **Agrupamento.** O funcionário pré-cadastrado a partir de um documento herda o empregador. Um documento de **outra** empresa para o mesmo funcionário vai para revisão com o motivo `EMPREGADOR_DIVERGENTE` (possível troca de empregador). Se o revisor corrigir o CNPJ, o documento muda de fornecedor.
4. **Documentos exigidos.** As exigências de escopo *empresa* (CRF do FGTS, CNDT, CND federal, guias de FGTS e DARF mensais, contrato, apólice de seguro) são avaliadas **por fornecedor**, com os documentos dele. A terceirizada, ou o fornecedor com trabalhadores alocados, é cobrada por certidões e guias mensais; o fornecedor sem trabalhadores, só pelos documentos não mensais. O ciclo mensal começa no início do contrato ou na primeira competência com documento: o sistema não inventa meses de pendência.
5. **Exposição a processo trabalhista.** Cada fornecedor recebe um nível calculado: **alta** (indicador de risco alto ou documento exigido vencido), **média** (indicador ou exigência pendente) ou **baixa** (tudo em dia). Os indicadores específicos são: certidão ausente, contrato ausente ou vencido com trabalhadores alocados, guia de FGTS ausente na competência com holerite ou ponto, autuação ou fiscalização, processo trabalhista, auditoria com risco alto e empregador divergente. Cada um traz a base legal e o documento de origem. Quatro tipos de documento foram acrescentados ao catálogo para isso: apólice de seguro, auto de infração, processo judicial e relatório de auditoria.

São indicadores de triagem, não parecer jurídico. Dado digitado manualmente pode acrescentar indicadores (por exemplo, registrar um processo), mas nunca faz desaparecer um indicador de ausência: isso exige documento com imagem.

**7. Métricas e painéis** (`backend/internal/http/reports.go`)

Os indicadores operacionais são calculados no banco, com isolamento por empresa. A visão geral e as métricas de conformidade aplicam filtros de unidade em diversas consultas; cotas e alguns agregados continuam sendo do tenant inteiro. Processamento, armazenamento e FinOps não possuem recorte completo por unidade:

| Tela / endpoint | O que mostra |
|---|---|
| Início, `/metrics/overview` | Conformidade (% de itens `OK` entre os não dispensados), funcionários ativos e com pendência, vencidos, a vencer em 30 dias, documentos aguardando revisão, ilegíveis, pré-cadastros, riscos em aberto por severidade e principais não conformidades. |
| `/metrics/compliance` | Pendências por tipo de documento e conformidade por unidade. |
| `/metrics/processing` | Volume mensal de páginas e documentos e tempo médio por lote. |
| Escala 950k & FinOps, `/metrics/finops` | Documentos e tokens registrados por camada, economia estimada em relação a um baseline e simulação de escala com premissas editáveis. A simulação não comprova preço oficial nem capacidade de processamento nessa escala. |
| Riscos trabalhistas, `/risks` | Lista filtrável por status e funcionário, com base legal e ação de ignorar para o administrador. |
| Relatórios, `/reports/:tipo` | Exportação CSV/XLSX de conformidade, pendências, não conformidades e armazenamento. |

Cada ação relevante (revisão, lançamento manual, dispensa, ignorar indicador, download) entra na **auditoria encadeada por hash**, que o worker verifica periodicamente.

## Variáveis, chaves e IA externa

| Ambiente | De onde vêm os valores |
|---|---|
| **Desenvolvimento (`make dev`)** | `backend/internal/config/config.go` fornece padrões locais. `scripts/dev.sh` define `SEED_DEMO=true`. A chave JWT é criada por `make keys`. Esse fluxo **não lê** o `.env` de produção. |
| **IA Core local com IA externa** | `scripts/dev.sh` lê somente `ia-core/.env.local` para `OPENAI_API_KEY`, `GEMINI_API_KEY`, `IA_PROVIDER` e as opções `OPENAI_MODEL*`/`GEMINI_MODEL*`; esse arquivo é ignorado pelo Git. |
| **Produção (Compose)** | `.env` fornece credenciais e opções; `docker-compose.yml` monta a chave JWT e repassa as variáveis a cada serviço. `make keys` preenche os segredos em branco sem mostrá-los no terminal. |

Sem nenhuma chave, o IA Core usa **texto do PDF, OCR local com Tesseract e regras determinísticas**. Para usar a OpenAI (ou o Gemini) no desenvolvimento:

```bash
cp ia-core/.env.local.example ia-core/.env.local
# Preencha OPENAI_API_KEY (ou GEMINI_API_KEY) em ia-core/.env.local e reinicie make dev.
curl http://localhost:8001/health
# testa cada modelo configurado e mostra o erro, se houver:
curl -H 'X-IACore-Key: dev-ia-core-key' http://localhost:8001/diagnostico
```

O campo `provider` passa de `local-heuristico` para `openai:<modelo>` ou `gemini:<modelo>`. Com as duas chaves, a OpenAI tem prioridade; `IA_PROVIDER=openai|gemini|local` força a escolha. Os modelos padrão da OpenAI (`gpt-5-mini`, `gpt-5`, `gpt-5-nano`) ainda não foram validados com chave real; se o `/diagnostico` mostrar erro de modelo, ajuste `OPENAI_MODEL*`. Isso mostra qual provedor foi selecionado, mas uma análise real é necessária para validar a chave. Algumas páginas com texto nativo suficiente continuam sendo resolvidas localmente. Em produção, configure a chave no `.env` se decidir usar esse provedor; páginas difíceis podem enviar imagem ou texto ao serviço externo. O provedor Vertex AI ainda não está implementado.

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
| IA Core retorna `local-heuristico` | É o comportamento esperado sem `OPENAI_API_KEY`/`GEMINI_API_KEY`; reinicie `make dev` depois de editar `ia-core/.env.local`. |
| Documento escaneado fica sem texto | Confira `tesseract --list-langs` e a presença do idioma `por`; veja `citadel-ia.log`. |
| Login pede código | No desenvolvimento, procure o código no terminal de `make dev`; em produção, confira SMTP e os logs da API. |
| Lote não avança | Veja os logs do worker e IA Core; em produção, `docker compose logs -f worker ia-core`. |

Material do protótipo original do hackathon: [docs/legacy/](docs/legacy/).
