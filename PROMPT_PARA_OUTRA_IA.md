# 🤖 PROMPT MESTRE PARA OUTRA IA (ATUALIZADO COM RADAR DE RISCO TRABALHISTA & DIVERGÊNCIAS)

Copie tudo que está dentro do bloco abaixo e cole na outra IA (Cursor, Copilot, Claude, ChatGPT ou Windsurf) que estiver com o repositório aberto:

---

```markdown
Você é um Engenheiro de Software Sênior Full-Stack (Python/FastAPI + JavaScript/Bootstrap 5) atuando no projeto "Citadel AI" — uma plataforma SaaS B2B 100% Web de Inteligência e Conformidade Documental Trabalhista (Desafio Document AI Factory / Bernhoeft).

O repositório já possui o backend funcional em `backend/` (`main.py`, `gemini_engine.py`, `ingestion.py`, `anonymizer.py`, `database.py`, `schemas.py`, `sample_generator.py`) e o frontend recém-redesenhado com a identidade visual "Citadel AI" em `frontend/index.html`, `frontend/app.js` e `frontend/styles.css`.

Sua missão é implementar as **10 entregas abaixo** (divididas entre **Parte A: Novo Motor de Indicadores e Alertas de Processo Trabalhista**, **Parte B: Sincronização do Frontend Citadel AI com as rotas do Backend** e **Parte C: Evoluções Dinâmicas do Backend**), mantendo o visual "Citadel AI" (`frontend/styles.css` e `frontend/index.html`) limpo, executivo e responsivo.

---

### PARTE A: NOVA FUNCIONALIDADE — MOTOR DE INDICADORES E ALERTAS DE RISCO TRABALHISTA & DIVERGÊNCIAS (`backend/` + `frontend/`)

Queremos que o SaaS detecte proativamente erros formais, falta de assinatura, vencimentos e **divergências cruzadas entre documentos** que possam gerar **Processos Trabalhistas (Súmula 331 TST), multas do eSocial ou autuações de NRs (Ministério do Trabalho)**, calculando inclusive o **Passivo Trabalhista Evitado (em R$)**.

1. **No Backend (`backend/schemas.py` e `backend/gemini_engine.py`):**
   - Crie em `backend/schemas.py` o modelo `LaborRiskAlert`:
     - `severidade`: `"CRITICO"` | `"ALTO"` | `"MEDIO"` | `"BAIXO"`
     - `tipo_divergencia`: string (ex: `"Ausência de Assinatura em EPI"`, `"Divergência Cruzada Cargo vs. NR"`, `"Exame Médico com Restrição / Baixa Legibilidade"`, `"Risco Contencioso em AR"`)
     - `descricao`: explicação clara do erro ou divergência encontrada.
     - `base_legal`: artigo da CLT / NR / Súmula TST (ex: `"Art. 166 CLT / NR-06 / Súmula 331 TST"`, `"NR-07 (PCMSO) / Art. 168 CLT"`, `"NR-35 / eSocial S-2220"`).
     - `passivo_estimado_brl`: `float` (valor estimado da multa ou condenação trabalhista evitada em Reais, ex: `25000.0`, `18500.0`).
     - `acao_recomendada`: instrução prática para o RH ou fornecedor corrigir na hora.
   - Adicione nos documentos gerados/analisados em `backend/gemini_engine.py` (função `_build_bernhoeft_compliance` ou nova função `_build_labor_risk_analysis(doc, all_docs_in_job)`):
     - `risco_trabalhista_score`: `"CRITICO"` | `"MODERADO"` | `"BAIXO"`
     - `passivo_evitado_brl`: soma em R$ dos riscos detectados naquele documento.
     - `alertas_trabalhistas`: lista de objetos `LaborRiskAlert`.
     - **Regras de Detecção Automática e Cruzada:**
       - **Ficha de EPI (`Ficha de EPI / Termo de Entrega`):** Se houver alerta de falta de assinatura ou item pendente, gerar alerta `CRITICO` (*"Falta de assinatura comprobatória na entrega de EPI. Em reclamatória trabalhista, invalida a prova de neutralização de insalubridade"*, Base Legal: `Art. 166 CLT / NR-06 / Súmula 289 TST`, Passivo: `R$ 28.000,00`).
       - **ASO (`ASO - Atestado de Saúde Ocupacional`):** Verificar assinatura/CRM do médico e realizar **cruzamento com a função do colaborador**: se a função envolver risco/eletricidade/altura ou se não houver certificado de NR anexado no lote para o mesmo CPF, gerar alerta de **Divergência Cruzada** (`MEDIO`/`ALTO`, Base Legal: `Art. 168 CLT / NR-07 / eSocial S-2220`, Passivo: `R$ 12.500,00`).
       - **Manuscrito Médico (`Prontuário / Manuscrito Médico`):** Se a confiança for `< 0.85` ou houver recomendação de afastamento/CID, gerar alerta `CRITICO` (*"Documento médico manuscrito com recomendação clínica de afastamento e baixa legibilidade caligráfica. Risco de doença ocupacional/acidente se mobilizado sem revisão do Médico do Trabalho"*, Base Legal: `Art. 169 CLT / NR-07 / Lei 8.213/91`, Passivo: `R$ 45.000,00`).
       - **AR Correios / Notificação (`AR Correios / Comprovante de Entrega` ou `Notificação Extrajudicial`):** Verificar recebedor e data para evitar revelia ou perda de prazo jurídico (Base Legal: `CPC Art. 248 / Súmula 331 TST`, Passivo: `R$ 15.000,00`).
       - **Para uploads reais (qualquer documento):** Analisar via Regex no `texto_ocr` se faltam palavras-chave de assinatura, se há datas vencidas ou divergência de CPF entre páginas do mesmo funcionário.
   - No retorno consolidado do Job (`backend/gemini_engine.py` / `backend/main.py`), adicione um objeto `resumo_risco_trabalhista`:
     - `passivo_total_evitado_brl`: soma total em R$ de todos os riscos detectados no lote (ex: `R$ 100.500,00`).
     - `total_divergencias_criticas`: contagem de alertas `CRITICO` e `ALTO`.
     - `funcionarios_bloqueados_catraca`: quantidade de colaboradores impedidos preventivamente de entrar na operação até regularização.

2. **No Frontend (`frontend/index.html` e `frontend/app.js`) — Painel de Indicadores Trabalhistas no Topo + Cards de Alerta por Documento:**
   - **No Topo da Workspace / Dashboard (`frontend/index.html`):** Adicione um banner executivo de destaque **"⚖️ Radar de Passivo Trabalhista & Conformidade CLT/NRs"** exibindo 3 indicadores claros:
     1. **🛡️ Passivo Trabalhista Evitado no Lote:** valor formatado em `R$ XX.XXX,00` (em destaque verde/esmeralda ou âmbar).
     2. **🚨 Divergências & Riscos de Processo:** quantidade de alertas trabalhistas detectados.
     3. **🚧 Bloqueios Preventivos de Catraca:** quantidade de documentos que travaram a mobilização antes de gerar multa.
   - **Dentro do Inspetor do Documento (`renderInspector` em `frontend/app.js`):**
     - Renderize a seção **"⚖️ Análise de Passivo Trabalhista & Divergências Cruzadas"** listando cada alerta de `doc.alertas_trabalhistas` com:
       - Badge de Severidade (`CRÍTICO` em vermelho, `ALTO`/`MÉDIO` em amarelo, `CONFORME` em verde);
       - Título da Divergência + Descrição do risco;
       - Badge da **Base Legal** (`CLT / NR / Súmula TST`);
       - Badge do **Passivo Evitado (`R$ XX.XXX,00`)**;
       - Box de **Ação Recomendada para o RH / Fornecedor**.

---

### PARTE B: SINCRONIZAÇÃO DO FRONTEND `CITADEL AI` COM AS ROTAS JÁ EXISTENTES NO BACKEND (`frontend/index.html` e `frontend/app.js`)

O redesign recente para o tema `Citadel AI` omitiu alguns botões e painéis que o `backend/main.py` já suporta nativamente. Conecte-os mantendo a estética `Citadel AI`:

3. **Botões de Corte Físico de PDF e Download `.ZIP` Hierárquico de RH:**
   - Na barra superior da lista de documentos (`frontend/index.html`), adicione o botão **"📦 Baixar Lote Separado (.ZIP RH)"** que faz download de `GET /api/jobs/{currentJobId}/export-zip?anonymized={anonymizeMode}`.
   - No cabeçalho do Inspetor do Documento (`#inspectorContent`), ao lado do botão de exportar JSON, adicione o botão **"📄 Baixar PDF Recortado"** apontando para `GET /api/documents/{doc.id}/pdf?anonymized={anonymizeMode}`.

4. **Card de Indexação Automática de RH e Visão em Árvore de Pastas (`Empresa ➔ Funcionário/CPF`):**
   - No Inspetor do Documento (`renderInspector`), exiba um card **"📁 Indexação Automática & Destino RH"** mostrando:
     - `doc.empresa_nome` e `doc.empresa_cnpj`
     - `doc.funcionario_nome` e `doc.funcionario_cpf`
     - `doc.pasta_destino_rh` (ex: `AGROTECH_GARANHUNS_LTDA_12345678000190/CARLOS_EDUARDO_SILVA_CPF_45892130487/`)
     - `doc.nome_arquivo_separado` (ex: `ASO_ADMISSIONAL_CARLOS_EDUARDO_SILVA_VALIDO_2027-03-14.pdf`)
   - Na sidebar esquerda (`#documentList`), adicione um alternador **"Por Página" | "📁 Pastas RH"**. Quando "Pastas RH" estiver selecionado, agrupe os documentos visualmente em árvore por `empresa_nome` ➔ `funcionario_nome (funcionario_cpf)` ➔ documentos daquele trabalhador.

5. **Painel de Status de Catraca / Mobilização e Checklist NR (`compliance_checklist`):**
   - No Inspetor do Documento, exiba o badge `doc.status_mobilizacao` (`APTO PARA MOBILIZAÇÃO (CATRACA LIBERADA)` em verde vs `BLOQUEADO - PENDÊNCIA DOCUMENTAL` em vermelho) e renderize os itens de `doc.compliance_checklist` (`regra`, `status`, `detalhe`).

6. **Telemetria FinOps por Documento + Aba 3 "Simulador de Escala & FinOps (Funil Custo Zero)":**
   - No Inspetor do Documento, mostre uma barra compacta com `doc.finops_telemetria` (`camada_roteamento`, `sha256_hash`, `tokens_consumidos`, `tokens_economizados`, `economia_estimada_pct`).
   - Adicione uma 3ª aba na navegação principal do topo: **"💰 Escala & FinOps"** (`#tabFinops`, `#viewFinops`) com um simulador interativo (slider de 100.000 a 5.000.000 páginas/mês, padrão 1.500.000 para o exemplo de 950.000 terceirizados da Bernhoeft), comparando:
     - **IA de Visão Comum (100% Vision = ~US$ 4.725/mês)** vs **Funil 4 Camadas Citadel AI (~US$ 255/mês — 94,6% de economia)**.
     - Explicando claramente que as **Camadas 0 e 1 rodam no motor nativo do servidor SaaS (SHA-256 + PyMuPDF) sem instalar nada no cliente e sem gastar 1 token de API externa (75% resolvido a Custo Zero)**.

---

### PARTE C: EVOLUÇÕES NO BACKEND PARA UPLOADS 100% DINÂMICOS (`backend/`)

7. **Deduplicação Real por Hash SHA-256 no SQLite (`backend/database.py` e `backend/gemini_engine.py`):**
   - Adicione a coluna `sha256_hash TEXT` em `job_pages` (`ALTER TABLE` seguro em `init_db`) e a função `find_cached_page_by_sha256(sha256_hash: str)`.
   - Antes de processar uma página em `gemini_engine.py`, consulte o hash SHA-256 no banco; se já existir, retorne o resultado em cache marcando `Camada 0: Cache SHA-256 (0 Tokens - Instantâneo)`.

8. **Extração Dinâmica de Empresa (CNPJ/Razão Social) e Funcionário (Nome/CPF) via Regex/LLM (`backend/gemini_engine.py`):**
   - Em `_infer_rh_hierarchy_and_filename(doc)`, extraia primeiro dinamicamente do `texto_ocr` e `campos_estruturados` qualquer CPF, CNPJ, Nome de Colaborador e Empresa via Regex, usando os nomes de demonstração apenas como fallback se o documento não contiver esses padrões.

9. **Tarja Preta LGPD Dinâmica nas Coordenadas Exatas do PDF (`backend/ingestion.py`):**
   - Em `render_pdf_page_to_png(..., redact_regions=True)`, use `page.search_for(termo_sensivel)` do PyMuPDF (`fitz`) buscando as strings de PII detectadas na página (CPFs, RGs, E-mails, Telefones, Nomes) para desenhar tarjas pretas exatamente sobre o texto sensível de qualquer PDF enviado, mantendo as tarjas percentuais como fallback para páginas puramente escaneadas.

10. **Compressão Real de Imagem (`1024x1024` WebP/JPEG) antes do Gemini Vision (`backend/gemini_engine.py`):**
    - Em `_analyze_page_with_gemini`, redimensione a imagem com `PIL.Image.thumbnail((1024, 1024))` e comprima em WebP/JPEG antes de converter para Base64, garantindo o teto de 258 tokens por imagem.

---

### TESTE E VALIDAÇÃO FINAL
Após implementar, execute `uv run python test_pipeline.py` (ou `.venv\Scripts\python.exe test_pipeline.py`) para garantir que o backend responde `200 OK` em todas as rotas e que o frontend carrega todos os indicadores trabalhistas, pastas de RH, exportação `.ZIP` e simulador FinOps sem erros no console.
```
