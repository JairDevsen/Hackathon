# Especificação funcional — requisitos × implementação

Legenda: ✅ implementado **e verificado** (teste/E2E citado) · 🟡 implementado, **não verificado** ou parcial · ⛔ não implementado.

> O prompt de migração chegou **truncado** na seção 12 ("Segurança:…"): as seções 12 (resto), 14 (critérios de aceite) e 15 (deploy VPS) não foram vistas. O deploy foi inferido do que o texto referencia (Traefik/`agresernet`, GHCR, `.env.example`); os critérios de aceite foram tratados como os requisitos da tabela 1.1.

## Desafio 3 (seção 1.1)
| Requisito | Status | Onde / evidência |
|---|---|---|
| Arquivos grandes (500 MB, PDF/TIFF/JPG/PNG/HEIC) | 🟡 | upload retomável em partes ✅ (`e2e_smoke` interrompe e retoma); fatiamento em streaming via PyMuPDF/Pillow; HEIC exige `pillow-heif`; **500 MB não foi testado** (maior teste: 60 páginas) |
| Início/fim de cada documento + agrupamento | ✅/🟡 | `ia_core/agrupar.py` (marcador "Página 2/3", número do objeto do AR, páginas complementares como o termo de quitação do TRCT, tipo pela melhor leitura) + `orientacao.py` (página de cabeça para baixo); testes unitários e comparação com o gabarito do gerador (6 lotes de 143 documentos, motor local: documentos de várias páginas errados de 15/15 para 2/15; documentos 100% corretos de 96 para 115); frente/verso em folhas diferentes sem identificador legível ainda pode separar; "Dividir aqui" (usa a página do meio — falta seletor na UI) e "Juntar" na revisão |
| Classificação (58 tipos curados: 32 iniciais + 4 de risco da terceirizada + 8 que o gerador produz + 14 de admissão e documentação de terceirizadas) | ✅ | `ia_core/catalogo.py` ; acurácia medida **só no motor local, em lotes fictícios** |
| OCR pesquisável | 🟡 | PDF com camada de texto invisível posicionada (palavra a palavra quando há texto/OCR) ✅; busca em texto completo (`tsvector` pt, sem acento, sobre o texto anonimizado) e destaque na imagem ✅. **PDF/A-2b não** (PDF comum); OCR de **imagens escaneadas depende de Tesseract**, não instalado no ambiente de teste (não verificado) |
| Confiança e fila de revisão | ✅ | confiança por página/documento, motivos, fila priorizada, tela dividida, medição de duração |
| Cópia anonimizada: cobertura das tarjas | ✅/🟡 | Além das expressões (CPF, CNPJ, RG, CEP, telefone, e-mail, PIS, banco, nome/endereço após rótulo), há regras por **posição** (nome na linha do CPF, valor abaixo do rótulo, propagação por coluna de tabela, logradouro sem rótulo). Medido por OCR sobre a própria cópia em 4 lotes do gerador (com os dados reais como gabarito): ainda legíveis nomes 1/71, CPF 1/53, endereços 0/5, CEP 0/4, PIS 0/2 (antes: 33/71 nomes e 5/5 endereços). Limites: depende do OCR; data de nascimento não medida; tarja em excesso no endereço da empresa; manuscrito e campos que o OCR não lê não são tarjados |
| Duplicata de conteúdo (mesmo documento escaneado de formas diferentes) | ✅/🟡 | Similaridade por palavras do texto lido por OCR (`documents/similaridade.go`), tolerante a erro de leitura; compara só documentos da mesma pessoa/empresa, competência, data e validade (o tipo não é exigido); trava de valores (números/datas de 4+ dígitos) independente do limite; limite **configurável pelo cliente, padrão 85%, mínimo 70%** (`tenants.similaridade_duplicata`, `PATCH /tenant`, tela de Configurações); a cópia descartada vira `REJEITADO` + `DUPLICATA_CONTEUDO` + `duplicata_de`, com **Restaurar** no lote. Calibrado com OCR real: certidão 92–98%, holerite 63–91%, tabelas 45–87%, páginas diferentes 19–32%. E2E seção 18. Limites: escaneamentos muito degradados e tabelas/cartões de ponto não passam no limite padrão; até 2 valores diferentes podem ser tratados como a mesma via |
| **Tipos descobertos pela IA** (menos "OUTRO", menos custo) | ✅/🟡 | O modelo nomeia o tipo de um documento legível que o catálogo não cobre (`tipo_novo`: nome genérico, escopo, categoria, pistas). O IA Core reaproveita tipo equivalente, recusa nome vago ou instância (CPF, número, e-mail), confere as pistas no texto lido e registra o tipo; o backend o grava no catálogo global (`origem = IA`, teto de 150) e o documento sai classificado com alerta `TIPO_IA`. As pistas viram regra da Camada 1: o próximo documento do tipo é reconhecido **sem modelo** (inclusive após reiniciar o IA Core). O Master renomeia e confirma em *Plataforma → Catálogo*. **Testado só com modelo simulado** (E2E); a qualidade real das propostas com OpenAI/Gemini não foi medida. Catálogo global: o nome do tipo é visível a todas as empresas |
| **Roteador de camadas** (menos IA paga, mesma qualidade) | ✅/🟡 | `ia_core/roteador.py`: PDF escaneado também passa pelo OCR local antes de ir ao modelo. A página fecha na Camada 1 se o tipo é seguro (≥ 0,85) **e** os campos que o tipo exige (CPF válido; competência nos mensais) foram achados; texto legível com dúvida vai à Camada 2 (modelo de texto, **sem transcrever**); manuscrito, formulário, OCR ruim ou CPF não lido no OCR vão à Camada 3 (visão). Página em branco não chama modelo e é descartada (não vira documento "OUTRO"): a detecção ignora sombra de borda, furos, ruído, número de página e o aviso "intencionalmente em branco"; o lote mostra quantas folhas foram ignoradas. Medido com OCR real (403 págs, 20 lotes): 20–24% Camada 1, 11–16% Camada 2, 63–64% Camada 3 (antes: 100% Camada 3); tipo correto em 98–100% das páginas fechadas na Camada 1. Limites: o gasto real em reais não foi medido; a proporção depende do mix (o gerador tem muito aviso de recebimento/manuscrito) |
| Extração de CPF e competência sobre OCR | ✅ | Competência de 13% para 46% de acerto nas primeiras páginas ("Referente ao Mês", "Pagamento de salário", valor na linha seguinte, período de um mês); CPF tolera separadores perdidos e zero lido como O, sempre validado pelo dígito verificador. O classificador acha pistas coladas pelo OCR ("Recibode pagamento") |
| Chamadas de IA em paralelo | ✅ | Camadas 2 e 3 de um lote rodam em paralelo (limite global `IA_LLM_CONCURRENCY`, padrão 4); callbacks sempre em ordem de página, checkpoint contíguo e retry preservados. Teste com provedor simulado (ordem, falha no meio, queda simulada). Não medido com cobrança nem latência de provedor real |
| **Acesso por pessoa, setor, terceirizada e fornecedor** | ✅ | Menu "Quem trabalha" (Funcionários, Setores, Terceirizadas, Fornecedores); **localizador no topo (Ctrl/Cmd+K)** acha pessoa (nome, matrícula, CPF completo), setor e empresa (nome ou CNPJ); tela **Setores** com conformidade, pendências e riscos de quem trabalha no setor (inclui terceirizadas alocadas) e ficha do setor; terceirizadas e fornecedores com lista e filtro de exposição próprios; dossiê e listas ligam pessoa → setor → empresa. API: `GET /departments` (com indicadores), `/departments/{id}`, `/directory/search`, filtros `setor` e `supplier` em `/compliance`; respeita o escopo de unidades do RH. E2E seção 19 |
| **Redefinir dados (só Master)** | ✅ | `POST /admin/reset` + tela Plataforma › Redefinir dados: apaga, de todas as empresas ou de uma, funcionários, terceirizadas, fornecedores, lotes, documentos, revisões, riscos, pendências, notificações e **todos os arquivos**; zera o espaço usado. Exige perfil Master, **código por e-mail (step-up)**, frase `RESETAR TUDO` e motivo; recusa com lote em processamento. Mantém empresas, usuários (admins e RH), unidades, cargos, setores, obrigatórios, retenção, planos, faturas, consumo mensal e a **auditoria** (registra `DADOS_RESETADOS`). Depois do reset restam só as exigências da própria empresa (sem pessoa), como numa empresa nova. E2E seção 20. Não há desfazer: não há backup automático antes |
| Mesma empresa com grafias diferentes | ✅ | `documents/empresa.go`: chave do nome (sem acento, caixa, pontuação e Ltda/ME/S/A); sem CNPJ legível liga a fornecedor já cadastrado (chave exata) ou à própria empresa (mesma 1ª palavra e ≥ 2 palavras em comum com o nome cadastrado); grafia lida preservada em `empresa_nome_lida`; pasta de destino unificada; migração dos documentos antigos na subida da API; tela agrupa pela mesma chave. E2E seção 17. Limite: depende do nome cadastrado da própria empresa estar correto |
| Modelos multimodais (OpenAI) | 🟡 | `OpenAIProvider` (imagem em data URL + JSON com esquema no prompt, modelo reserva, tentativas automáticas) com testes usando cliente simulado. **Nunca executado com chave real**: os nomes padrão `gpt-5-mini`/`gpt-5`/`gpt-5-nano` não foram confirmados; `GET /diagnostico` mostra qual modelo responde. Tem prioridade sobre o Gemini quando as duas chaves existem |
| Modelos multimodais (Gemini) | ✅/🟡 | `GeminiProvider` (imagem + `response_schema`, tentativas automáticas em 429/5xx e modelo reserva) **validado com uma chave real em 6 páginas fictícias**: 6/6 tipos corretos, confiança 0,95–0,99, CPF e CNPJ lidos. Amostra pequena, só de documentos impressos (certidões, guias, ponto): **manuscritos e imagens ruins não foram testados**. Os modelos `2.5-*` foram **fechados para chaves novas** (404): os padrões passaram a `gemini-3.5-flash` (visão), `gemini-3.5-flash-lite` (texto) e `gemini-3.6-flash` (reserva); nenhum modelo Pro estava acessível nessa chave. Cada página levou 9 a 17 s e 3 a 4,4 mil tokens |
| Retomada após falha | ✅ | checkpoint por página, `/retry`, watchdog, backoff, fila de mensagens mortas; `chaos_test.py`: kill -9 do worker e IA Core com 15/60 páginas → termina com os 60 documentos do gabarito |
| Anonimização | ✅/🟡 | cópia com tarja **queimada**, sem camada de texto e sem metadados (teste automático) ✅; mascaramento por perfil ✅; **política por empresa existe como dado mas não é aplicada** campo a campo; recusa gerar cópia de página sem OCR; pseudonimização em exportações ⛔ |

## Stack (seção 2)
| Item | Status |
|---|---|
| React 19 + TS + Vite + Tailwind v4 + Router + TanStack Query + RHF + zod + lucide + Recharts | ✅ |
| Go + Gin + pgx + `slog` + validator | ✅ |
| **sqlc** | ⛔ substituído por SQL escrito à mão com `json_agg` (decisão em `backend/docs/adr/0001`) |
| **OpenAPI gerado** | 🟡 `backend/api/openapi.yaml` escrito à mão (resumo dos endpoints) |
| golang-migrate (embed) | ✅ |
| Postgres 16 + RLS + `pg_trgm` | ✅ (teste de isolamento) |
| Redis (fila asynq, OTP, rate limit) | ✅ |
| S3/MinIO | 🟡 driver escrito, **não testado** (sem MinIO no ambiente; testado o driver `fs`) |
| ClamAV | 🟡 cliente INSTREAM escrito, **não testado** |
| Docker Compose dev/prod, Traefik, GHCR, Actions | 🟡 escritos, **nunca executados** (sem Docker no ambiente) |

## Perfis, segurança (3, 4)
| Item | Status | Evidência |
|---|---|---|
| JWT EdDSA com `kid`, JWKS, rotação | ✅ | `pkg/jwtx`; `/.well-known/jwks.json` |
| Argon2id (64 MB) ≥ 12 caracteres; checagem de vazamento (k-anonymity) | ✅ | só ativa em produção |
| Login + 2FA e-mail (ticket 5 min, código 10 min, 5 tentativas, reenvio 60 s) | ✅ | `auth_refresh_test.py` |
| Refresh opaco rotativo + detecção de reuso + CSRF | ✅ | idem |
| Dispositivo confiável 30 dias | 🟡 | implementado, sem teste |
| Step-up em ações sensíveis | ✅ | exportar dossiê, permissões, domínios, acesso de suporte, trocar senha |
| Rate limit/bloqueio progressivo + alerta ao dono | ✅/🟡 | alerta por e-mail sem teste |
| Isolamento por empresa (RLS) + teste automatizado | ✅ | `internal/database/isolation_test.go` |
| URLs assinadas 60–120 s + auditoria de download | ✅ | `e2e_smoke` |
| Criptografia por envelope AES-256-GCM (arquivos em streaming) | ✅ | `pkg/crypto` testado |
| CPF cifrado + `cpf_hash` HMAC; máscara | ✅ | |
| **Texto lido por OCR cifrado no banco** | ✅ | O texto completo do documento, o texto embutido do PDF, as palavras com posição e a análise de cada página (texto e campos) são gravados com **AES-256-GCM** e a DEK da empresa (`internal/ocrseal`, AAD = finalidade + empresa; teste: não abre com outra empresa, chave ou finalidade). Lotes antigos são migrados na subida da API (`BackfillOCR`, idempotente). Conferido varrendo todas as colunas do banco após um E2E: nenhum texto OCR em claro. Seguem em claro, por serem estruturados e mascarados: `campos` (CPF `***.456.789-**`), `texto_anonimizado` e `dados_sensiveis`. Nomes e valores em `campos` (ex.: salário) continuam em claro. A busca em texto passou a usar o **texto anonimizado** (rótulos como "Nome:" e endereços são mascarados; nome solto no corpo do texto não é), então não se encontra um documento pelo CPF digitado: use a busca de funcionário (hash cego). O texto lido continua visível, decifrado, na tela do documento para quem tem acesso; o acesso de suporte só recebe o anonimizado |
| Auditoria imutável encadeada + verificação diária | ✅ | teste de imutabilidade + `/admin/audit/verify` |
| Retenção configurável | 🟡 | política editável e salva; **job de exclusão/anonimização por prazo não existe** |
| Direitos do titular (relatório/exportação por CPF) | ⛔ | só o dossiê por funcionário |
| Acesso de suporte aprovado pelo admin (só anonimizado) | 🟡 | fluxo implementado; lista de páginas em modo suporte é bloqueada |

## Funcional (5–7, 11)
| Item | Status |
|---|---|
| Entidades, vínculo por CPF/matrícula/nome (`pg_trgm` ≥ 0,85), fila "Sem vínculo", criar funcionário | ✅ |
| Matriz por cargo, modelos por segmento, dispensa, motor diário + gatilhos | ✅ (testes unitários + E2E); **dispensa por funcionário só via API/sem tela** |
| Lotes: cota, SHA-256, SSE, linha do tempo, duplicata | ✅ |
| Revisão: confirmar, corrigir, mudar tipo, vincular, dividir, juntar, rejeitar, duplicata; atalhos | ✅ |
| Dados de saúde (`saude:ler`): mascarados em listas, 403 em detalhe, auditados | ✅ |
| Dashboards, métricas, não conformidades trabalhistas | ✅ (jornada > 10 h, intervalo < 1 h, FGTS divergente, certidão vencida, sem assinatura, recusa sem testemunhas, ponto britânico) |
| Relatórios CSV/XLSX | ✅; **agendamento mensal por e-mail** ⛔ |
| Calendário de vencimentos | ✅ (alertas por e-mail ⛔; notificação diária ✅) |
| Painel de produtividade da revisão | 🟡 endpoint `/metrics/processing`; sem tela dedicada |
| Portal de auditoria externa (11.2) | ⛔ (tabela `audit_shares` criada, sem endpoints) |
| Webhooks para GRANDE (11.7) | ⛔ |
| Versionamento de documentos | ✅ (substituir anterior) |
| Checklists de evento (admissão/desligamento) | 🟡 momentos ADMISSAO/DESLIGAMENTO geram itens; sem tela de checklist |
| Cota 80 % / 95 % + bloqueio de upload | ✅ |
| Qualidade da IA (Master) | ✅ benchmark com gabarito; **comparação entre provedores** ⛔ (um provedor por vez) |
| Master: empresas, planos, armazenamento, catálogo, filas/DLQ, auditoria com motivo, usuários | ✅ |

## Landing (10)
| Item | Status |
|---|---|
| 13 blocos de conteúdo, textos do prompt, sem números inventados, `[[métrica do piloto]]` | ✅ |
| Formulário: validação, bloqueio de e-mail gratuito, consentimento, honeypot, rate limit, grava em `leads`, avisa o comercial | ✅ (captcha só com `CAPTCHA_SECRET`) |
| Demonstração somente leitura com lote fictício | ✅ |
| Banner de consentimento de analytics | 🟡 (não há ferramenta de analytics integrada) |
| **Pré-renderização (SSG) para SEO** | ⛔ SPA com meta tags e JSON-LD estáticos no `index.html` |
| LCP < 2,5 s, AVIF/WebP `srcset`, **auditoria de acessibilidade** | ⛔ não medidos; imagens em WebP sem `srcset`. A landing foi **vista em navegador** (desktop e celular, Playwright), com telas reais do produto |

## Funil FinOps, indexação RH e mobilização (prompt complementar "Bernhoeft")
Esse prompt foi escrito para o protótipo antigo (`backend/main.py`, `app.js`/Bootstrap, SQLite, `test_pipeline.py`). Foi **adaptado à stack atual**; os nomes de rotas antigos (`/api/jobs/{id}/export-zip`, `/api/documents/{id}/pdf`, `/api/process-sample`, `/audit-csv`) não existem: os equivalentes estão abaixo.

| Entrega | Status | Onde / evidência |
|---|---|---|
| 1. ZIP do lote por Empresa/Funcionário + PDF individual | ✅ | `GET /batches/{id}/export-zip?anonimizado=` (botão "Baixar lote separado (.ZIP RH)" + toggle LGPD) e `GET /documents/{id}/download` (3 formatos); E2E `8.`. Exportar JSON do documento na tela |
| 2. Card de indexação RH + modo "Pastas RH" | ✅ | detalhe do documento; toggle "Lista \| Pastas RH" no lote (empresa → funcionário (CPF mascarado) → documentos). **CPF parcial (6 dígitos) no nome de pasta/arquivo**, não o inteiro, para não expor PII em nomes de arquivo |
| 3. Status de mobilização + checklist (NR-07, NR-06, NR-35/NR, validade, assinatura) | ✅ | `ia_core/checklist.py`; status derivado em `documents.MobilizationStatus` (verde APTO / vermelho BLOQUEADO / amarelo demais). Regras são heurísticas de texto: não substituem análise de SST |
| 4. Telemetria FinOps por documento + aba "Escala 950k & FinOps" | ✅/🟡 | barra no documento (camada, SHA-256, tokens gastos × economizados, % economia); `/metrics/finops` (consumo real); simulador com slider 100 mil–5 mi. **Os valores em US$ são premissas calibradas para reproduzir o cenário pedido (≈ US$ 4.725 vs ≈ US$ 255, 94,6 %), não preços oficiais**; o consumo de tokens do Gemini Vision não foi medido (sem chave) |
| 5. Deduplicação SHA-256 (Camada 0) | ✅ | Chave = SHA-256 do PNG da página (já endireitada) **mais** o texto embutido, quando há. Só reaproveita análise da **mesma empresa**, feita pelo **mesmo motor** (impressão digital do provedor, modelos, prompt, catálogo e código: `ia_core/impressao.py`); trocar de modelo ou alterar as regras invalida o cache. Testado de ponta a ponta (`e2e_smoke` seção 16): um pixel diferente, outro texto embutido ou outro motor refazem a análise; página idêntica em outro arquivo é reaproveitada. Limites: nova digitalização da mesma folha não acerta o cache (sem comparação aproximada) e não há botão de "reanalisar sem cache". Escopo: entre lotes (dentro do mesmo lote o cache não atua) |
| 6. Extração dinâmica de empresa/CNPJ/funcionário | ✅ | `extracao.py` (regex; CNPJ validado por dígito) e campos `empresa_nome/empresa_cnpj` no schema do Gemini; sem nomes hardcoded; pasta usa a empresa lida (senão a do tenant) |
| 7. Tarja LGPD por coordenadas exatas | ✅ (já existia) | `fatiar._caixas_pii` (`page.search_for` do PyMuPDF) + `render._tarjar`. **Sem tarjas fixas de fallback**: em página sem texto/OCR a cópia anonimizada é recusada (um retângulo "chutado" daria falsa sensação de anonimização) |
| 8. Imagem 1024 px WebP antes do Gemini | 🟡 | `providers._reduzir` (`thumbnail` + WebP q=80; testado). A chamada real foi executada (6 páginas): o consumo medido foi de **3 a 4,4 mil tokens por página**, bem acima dos 258 do simulador (ver nota abaixo). Atenção: 258 tokens vale para imagens ≤ 384 px; a 1024 px o consumo tende a ser maior (blocos de 768 px) |
| Funil de 4 camadas nos provedores externos (OpenAI/Gemini) | 🟡 | Camada 1 (texto nativo + regex) e Camada 3 (visão, Pro como fallback) escritas; **Camada 2 (Flash-Lite sobre texto) escrita sem *context caching*** e nunca executada com chave real |

## Análise de erros e configuração por empresa (telas de referência: documento vencido, imagem borrada, dados divergentes)
| Item | Status | Onde / evidência |
|---|---|---|
| Resultado do lote: totais, **Aprovados / Com atenção / Com erro**, busca e cartões de problema com miniatura | ✅ | `features/rh/ResultadoLote.tsx`; classificação em `lib/analise.ts` (vitest) |
| **Documento vencido** | ✅ | alerta de erro + falha no checklist (E2E: CNH com validade 2004) |
| **Imagem borrada** | ✅/🟡 | `qualidade_img.py` separa **borrada × em branco × sem OCR**; antes, foto sem texto era descartada como "página em branco". Limite de nitidez é **heurística calibrada com amostras sintéticas** (`IA_NITIDEZ_MIN`); falsos positivos/negativos em scans reais não foram medidos |
| **Dados divergentes** (nome no documento × cadastro, inclusive ordem trocada) | ✅/🟡 | `documents/names.go` (testes); aceita abreviações e partículas. **Só compara nome**; outros campos (data de nascimento, filiação) não |
| Comparar documentos (lado a lado, destaque do que diverge) | ✅ | `CompareModal` (mesmo funcionário) |
| Solicitar novo envio | ✅/🟡 | tira o documento do lote, notifica e **envia e-mail a quem enviou o lote**; o funcionário não é avisado |
| Aprovar mesmo assim | ✅ | `forcado` registrado na auditoria (E2E) |
| **Setores** | ✅ | tabela `departments`; funcionários e regras por setor |
| **Selecionar documentos exigidos** por todos/setor/cargo, com simulação de impacto | ✅ | `PUT /requirements/bulk` (+`dry_run` em transação desfeita); `Obrigatorios.tsx`. **Só o que está marcado gera pendência**; empresa sem regras não cobra nada |
| Exceção **por funcionário** (dispensar/exigir, com justificativa auditada) | ✅ | aba "Documentos exigidos" do dossiê; precedência funcionário > cargo > setor > todos (teste unitário + E2E) |
| **Cadastro de funcionário configurável** (campos ativos/obrigatórios + campos próprios) | ✅ | `config_cadastro`, `/tenant/cadastro-config`; validação no servidor (E2E) |
| Visual **escuro** das telas de referência, menu lateral, home com banner, "Processamento em andamento" e rosca de tipos | ✅ | tema escuro padrão (+ claro opcional), `AppShell` com sidebar, `Dashboard.tsx`; verificado com capturas reais (Playwright) |
| **RH com a visão do admin** (painel, lotes, calendário, relatórios) + página **Documentos** | ✅ | mesma home para Admin e RH; `GET /documents` com filtros/cursor/totais; E2E seção 10 (configuração e conta continuam só admin → 403). **Os números do painel não são recortados por unidade** do RH |

## Pré-cadastro automático, ilegíveis, lançamento manual e indicadores de risco trabalhista
| Item | Status | Onde / evidência |
|---|---|---|
| **Pré-cadastro automático** a partir do lote (RH não cadastra antes) | ✅ | `documents/ingest.go`: só com CPF válido, nome lido, página legível e dentro do limite do plano; marca `pre_cadastro`/`origem`; chave por empresa `pre_cadastro_automatico`; E2E seção 4 |
| CPF inválido **não** vira pré-cadastro (vai para "Sem vínculo") | ✅ | E2E seção 4 |
| Pré-cadastro sem admissão **não gera meses de pendência** | ✅ | `compliance/engine.go` (teste unitário + E2E) |
| Lote informa **pré-cadastros** e **documentos ilegíveis para classificação manual**; notificações; avisos com links | ✅ | `resumo.pre_cadastros`/`classificacao_manual`; `Batches.tsx`; E2E |
| Lista de pré-cadastros, aviso no dossiê e **completar cadastro** (edição) | ✅ | `Lists.tsx`, `Dossie.tsx` (`PATCH /employees/:id`, filtro `?pre=1`); verificado com Playwright |
| **Classificação manual do tipo** + formulário do tipo (transcrição) para documento ilegível | ✅/🟡 | `Review.tsx` (schema do tipo escolhido). A transcrição é **marcada como manual e não comprova a exigência** |
| **Lançar novo documento legível** (cópia que substitui o ilegível; dicas de funcionário/tipo no upload) | ✅ | `substitui_documento_id`; o anterior vira `SUBSTITUIDO`, versão +1 |
| **Lançamento manual sem imagem** pelo dossiê (formulário por tipo) | ✅/🟡 | `POST /employees/:id/documents/manual` (`ManualDoc.tsx`); `origem=MANUAL`, auditado, exige `saude:ler` para tipos de saúde. **Acrescenta indicadores, mas nunca comprova ausência** (teste unitário + E2E) |
| **Indicadores de risco trabalhista** (jornada, intervalo, ponto britânico, horas extras sem pagamento, FGTS, férias, TRCT, vínculo, qualidade documental) com severidade e base legal | ✅/🟡 | `compliance/risk.go` (testes), `GET /risks`, página Riscos, aba no dossiê, cartões no Início. **São indicadores de triagem, não parecer jurídico**; as bases legais citadas devem ser **validadas pelo jurídico** antes de uso em produção |
| Ignorar (com justificativa) e reabrir indicador, só admin, auditado; recálculo preserva a decisão | ✅ | `POST /risks/:id/ignore` e `/reabrir`; E2E seção 11 |
| Cobertura das regras | 🟡 | A detecção depende dos campos extraídos: `horas_extras` e `pagamento_horas_extras` têm regex testada em amostras sintéticas; documentos reais podem usar outros rótulos |

## Fornecedores e terceirizadas (risco de processo trabalhista para a contratante)
| Item | Status | Onde / evidência |
|---|---|---|
| **Fornecedor/terceirizada** como entidade, identificada pelo **CNPJ** lido no documento (único por empresa) | ✅ | migração `000006`; `documents/suppliers.go`; E2E seção 13 |
| Em contrato, vale o CNPJ da **contratada**, não o da contratante | ✅ | `ia_core/extracao.py` (`cnpj_da_empresa`, testado); depende de o texto trazer o rótulo "CONTRATADA/PRESTADORA" |
| **Pré-cadastro automático** do fornecedor; completar tipo, criticidade e contrato | ✅ | ingestão + `/suppliers` (POST/PATCH); tela Fornecedores |
| **Três grupos**: própria empresa × terceirizada × fornecedor, em funcionários, documentos, painel e árvore de pastas do lote | ✅ | campo `vinculo` e filtros `?vinculo=`; E2E |
| Funcionário herda o empregador; documento de **outra empresa** → `EMPREGADOR_DIVERGENTE` (revisão) | ✅ | `ingest.go`; E2E |
| Exigências da empresa avaliadas **por fornecedor** (certidões, guias mensais, contrato, apólice) | ✅ | `compliance/engine.go` (`recomputeSuppliers`), modelo de exigências da empresa ampliado |
| Fornecedor **sem trabalhadores** não é cobrado por certidões e guias mensais; **com** trabalhadores, sim | ✅ | `risk.go` + `engine.go` (testes unitários e E2E) |
| **Indicadores de risco** do fornecedor: certidão, contrato (ausente/vencido), guia de FGTS por competência, autuação, processo, auditoria, empregador divergente, com base legal | ✅/🟡 | `compliance/risk.go` (`deriveSupplierRisks`, testes). **Triagem, não parecer jurídico**; as bases legais precisam de validação do jurídico |
| **Nível de exposição** a processo trabalhista por fornecedor (alta/média/baixa) | ✅/🟡 | regra simples e explicada na tela (`supplierSelect`); não é um modelo estatístico |
| 4 tipos de documento novos: apólice de seguro, auto de infração, processo judicial, relatório de auditoria | ✅/🟡 | catálogo do IA Core, schemas e migração. O gerador de documentos fictícios **não** produz estes 4 tipos, então a acurácia de classificação deles não foi medida |
| Telas: lista, dossiê do fornecedor (dados, documentos, funcionários, exigidos, riscos), painel por vínculo | ✅ | `features/rh/Fornecedores.tsx`; verificado com capturas reais (Playwright) |
| Limites | 🟡 | Sem importação em planilha de fornecedores; sem exceção de exigência por fornecedor (a regra vale para todos); o motor local só reconhece o CNPJ quando o texto do documento tem camada de texto ou OCR |

## Apagar lote enviado (com confirmação)
| Item | Status | Onde / evidência |
|---|---|---|
| **Apagar um lote** enviado (botão na lista e no detalhe), com **modal de confirmação**: o que sai, o que fica, motivo obrigatório e caixa "entendo que é definitivo" | ✅ | `features/rh/ApagarLote.tsx`; `DELETE /batches/:id`; verificado com capturas reais e E2E seção 15 |
| A API também exige a confirmação (`confirmar:true`) e o motivo (mín. 5 caracteres) | ✅ | `http/batches_delete.go` (400 sem eles) |
| Só lote **terminado** (processado ou falho); em processamento → 409 | ✅ | E2E |
| Remove o lote, as páginas, os documentos (com revisões, indicadores e itens ligados) e os **arquivos** (original, páginas, miniaturas, PDFs gerados); devolve os bytes à cota; recalcula conformidade e riscos | ✅ | `Store.DeletePrefix` (disco e S3); E2E |
| Mantém funcionários/fornecedores criados a partir do lote, o consumo de páginas do mês e a **auditoria** (`LOTE_EXCLUIDO`, com motivo, arquivo e SHA-256) | ✅ | E2E |
| Escopo por unidade respeitado (RH restrito não apaga lote de outra unidade → 404); documentos de outros lotes que este havia substituído voltam a valer | ✅ | `scopeBatch`; E2E (a restauração de substituídos tem implementação, sem teste dedicado) |
| Limites | 🟡 | A exclusão é **definitiva**: não há lixeira nem restauração. A remoção dos arquivos ocorre depois do commit; se falhar, sobram objetos cifrados órfãos (registrado em log). Não verifica prazo legal de guarda dos documentos: o aviso na tela pede conferir com o jurídico |

## Revisão de segurança (código, funcionalidades, landing e perfis)
Escopo: backend Go, IA Core, frontend (landing e as telas dos perfis Master, Administrador, RH e RH restrito por unidade), infraestrutura (Docker/Traefik/nginx/CI) e dependências. Método: leitura do código com buscas dirigidas (SQL dinâmico, cobertura do filtro de dados de saúde, uso de escopo de unidade, sinks de XSS), `govulncheck`, `npm audit` e `pip-audit`.

| Achado | Gravidade | Estado | Correção / evidência |
|---|---|---|---|
| Contador de tentativas do código 2FA era lido e gravado sem trava: requisições paralelas contra o mesmo ticket avaliavam mais de 5 códigos | Média | ✅ corrigido | `auth/service.go`: `INCR` atômico no Redis e uso único por `DEL`; E2E seção 12 (12 tentativas simultâneas → no máximo 5 avaliadas) |
| `POST /exports/dossie` ignorava o modo suporte: o Master com acesso aprovado recebia PDFs **não anonimizados** | Média | ✅ corrigido | `http/documents.go`: no suporte força `anonimizado`, como o download e o ZIP do lote |
| RH restrito a unidades alcançava, **por ID**, funcionário, documento (páginas, download, revisão), lote e exportações de outra unidade; os IDs vazavam pelas notificações, que valem para a empresa toda | Média | ✅ corrigido | `http/scope.go` (middleware) aplicado em todas as rotas com ID; responde 404; E2E seção 12 |
| Relatórios CSV: nomes e textos vindos de documentos ou cadastro podiam virar fórmula no Excel (`=`, `+`, `-`, `@`) | Média | ✅ corrigido | `csvSafe` prefixa apóstrofo (o XLSX grava string e não fórmula); E2E seção 12 |
| Relatório de não conformidades ignorava escopo de unidade e a permissão de saúde; o de conformidade ignorava o escopo | Média | ✅ corrigido | `http/reports.go` |
| Convite pendente reativava um usuário que o admin desativou depois | Baixa | ✅ corrigido | `auth/handlers.go` (só `CONVIDADO`) e `patchUser` invalida convites; E2E seção 12 |
| Cookie de dispositivo confiável usava `sha256(segredo‖msg)` e comparação não constante; chave do IA Core comparada com `!=` | Baixa | ✅ endurecido | HMAC-SHA256 + `hmac.Equal`; `hmac.compare_digest` no IA Core (os cookies antigos deixam de valer: o 2FA é pedido de novo) |
| `SEED_DEMO=true` em produção criaria contas de demonstração com senha pública | Baixa | ✅ endurecido | `cmd/seed` recusa em `APP_ENV=production` |
| `quic-go` v0.59.0 (GO-2026-5676, alcançável pelo servidor HTTP) | Baixa (negação de serviço) | ✅ corrigido | atualizado para v0.59.1; `govulncheck`: 0 vulnerabilidades |
| Dependências Python do IA Core sem piso de versão (pip-audit apontou `python-multipart`, `starlette`, `urllib3`, `requests`, `pymupdf`, `pillow-heif`, `python-dotenv`) | Baixa a média | ✅ pisos adicionados | `ia-core/requirements.txt` |

**Verificado sem achado:** SQL parametrizado em todos os pontos (só fragmentos constantes são concatenados); JWT EdDSA com algoritmo fixado, `iss`/`exp` obrigatórios, refresh rotativo com detecção de reuso; CORS por lista; cookies `HttpOnly`/`SameSite=Strict` e CSRF no refresh; token de acesso só em memória no navegador; `dangerouslySetInnerHTML` único (busca) escapa antes de aplicar `<mark>`; cifra em segmentos com contador e marca de fim (sem truncamento); URLs assinadas curtas por HMAC com comparação em tempo constante; validação de nome, tamanho e assinatura do arquivo no upload; `callback` do IA Core com HMAC e janela de 10 min, fora do Traefik público; contêineres não-root, `read_only` e `cap_drop`; `npm audit`: 0.

**Riscos residuais (não corrigidos):**
- O IA Core baixa as URLs que recebe (`arquivo_url`, `image_url`, `callback_url`) e só a chave de API o protege; uma lista de hosts permitidos reduziria o impacto de vazamento da chave.
- A CSP do nginx mantém `script-src 'unsafe-inline'` por causa do script inline de tema no `index.html`; mover para arquivo externo permitiria removê-la.
- Com o Redis indisponível, a checagem de sessão revogada e os limites de tentativa falham abertos (o login ainda exige Argon2 e 2FA).
- A cobrança por e-mail (`POST /compliance/cobrar`) lista pendências de todas as unidades para todos os usuários, sem filtrar pelo escopo de cada destinatário.
- Um RH restrito pode vincular um documento (ação VINCULAR da revisão) a um funcionário de outra unidade.
- No acesso de suporte o Master ainda vê nome, e-mail e telefone de funcionários; só os documentos são anonimizados.
- Com `OPENAI_API_KEY` ou `GEMINI_API_KEY`, imagens e textos dos documentos saem para a API do provedor escolhido; valide o tratamento de dados reais antes de ativar.
- `ia-core/requirements.txt` não fixa versões exatas: a imagem Docker resolve as mais novas (por exemplo `fastapi` 0.162 e `starlette` 1.10), enquanto os testes locais rodaram em `fastapi` 0.128 e `starlette` 0.49 (Python 3.9). Fixe um lock e rode a suíte do IA Core em Python 3.12.
- Os testes de regressão da seção 12 foram executados só com o código corrigido; não foram rodados contra o código anterior para confirmar que falhavam.

## Qualidade (12)
Testes: `go test -race` (unit + RLS + auditoria), `pytest`, `vitest`, scripts E2E em Python. ⛔ Testcontainers, Playwright, `golangci-lint`, Prometheus, OpenTelemetry, PITR configurado, restauração testada.
