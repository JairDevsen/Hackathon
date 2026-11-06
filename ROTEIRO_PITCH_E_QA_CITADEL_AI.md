# 🎤 ROTEIRO OFICIAL DE PITCH (3 MIN) & GUIA DA BANCA (5 MIN) — PADRÃO OFICIAL SEBRAE / HACK GARANHUNS TECH
**Produto:** Citadel AI — Plataforma SaaS B2B de Inteligência e Conformidade Documental Trabalhista  
**Desafio:** Desafio 3 — Document AI Factory (Hack Garanhuns Tech 2026)  
**Formato Oficial do Demo Day (Slide 4 e 6 do Edital):**  
- **3 Minutos de Pitch** (com **1m15s = 40% do tempo de Demo ao Vivo Obrigatória** seguindo a régua `0:00 | 0:20 | 0:35 | 1:50 | 2:20 | 2:45`)  
- **5 Minutos de Perguntas da Banca** (avaliando os 6 critérios de 0 a 5 pontos)

---

## ⚠️ REGRAS DE OURO DA BANCA (EXTRAÍDAS DO PDF OFICIAL DOS ORGANIZADORES)

1. **Proibido uma pessoa só falar (Slide 17):** Dividam a fala entre **3 apresentadores** (Problema/Negócio + Demo + Arquitetura/Escala) + **1 operador no notebook**.
2. **Menos Slide, Mais Tela (Slide 7 e 9):** Dê **Zoom de 125%** no navegador para a banca enxergar de longe. Tenham um **Vídeo Curto Gravado (Plano B)** aberto no reprodutor caso a internet/servidor oscile na hora.
3. **Falar as Capacidades Mínimas em voz alta durante a Demo (Slide 9 e 14):** Ao clicar, diga claramente qual capacidade do desafio está sendo atendida.
4. **Honestidade Técnica gera nota máxima em Viabilidade e Escalabilidade (Slide 10, 11 e 15):** Diga claramente qual é o gargalo em 10x de escala, o que já é real de ponta a ponta e o que falta para ir para produção.
5. **Fechar com "O Pedido" nos últimos 15 segundos (Slide 6 e 12):** Pedir um piloto com empresa parceira (Bernhoeft) e a vaga no AgresTI / palco do FING.

---

## ⏱️ PARTE 1: ROTEIRO CRONOMETRADO DE 3 MINUTOS (RÉGUA OFICIAL DO SLIDE 6)

### 🔴 `0:00 - 0:20` (20s) — PROBLEMA: A Dor e Quanto Custa (Storytelling em 4 Tempos — Slides 8 e 16)
🎙️ **Apresentador 1 (Lucas — Produto & Negócios):**
> **"Às 8 horas da manhã, chega no RH um único PDF escaneado com 500 páginas misturadas de trabalhadores recém-contratados: tem exame ASO, ficha de EPI sem assinatura, atestado escrito à mão por médico e AR dos Correios. Às 17 horas, um analista ainda está cortando e renomeando arquivo por arquivo na mão — travando a entrada do trabalhador na obra por 3 dias e expondo a empresa a multas trabalhistas milionárias."**

---

### ⚡ `0:20 - 0:35` (15s) — SOLUÇÃO: O Que É e o Que a Diferencia (Critério 2: Inovação — Slide 6)
🎙️ **Apresentador 1 (Lucas):**
> **"Para resolver isso, criamos o Citadel AI: um SaaS B2B 100% Web que recebe lotes documentais brutos e, em segundos, fatia fisicamente os PDFs, organiza em pastas por Empresa e CPF, audita divergências trabalhistas e protege dados pela LGPD. Vamos ver funcionando ao vivo:"**

---

### 🖥️ `0:35 - 1:50` (1m15s = 75s) — DEMO AO VIVO (40% do Tempo — Critério 1: Pertinência e Capacidades Mínimas)
🎙️ **Apresentador 2 (Demo Técnica — ex: Jair/Davi falando + Operador clicando na tela):**

* **`[0:35 - 0:55 | Clique 1: "Carregar Exemplo" / Ingestão e Classificação]`**
  > **"Aqui atendemos as Capacidades de Ingestão e Classificação Multiclasse: o usuário sobe o PDF misturado direto no navegador. O sistema separa página a página, classifica ASO, Contrato, EPI, Manuscrito e AR Correios, e já cria a árvore de pastas por Empresa e CPF com download imediato do pacote ZIP com os PDFs recortados e renomeados por validade."**

* **`[0:55 - 1:15 | Clique 2: Abre Documento -> Mostra Extração JSON e Radar Trabalhista]`**
  > **"Ao abrir o documento, cumprimos a Capacidade de Extração Estruturada: extraímos nomes, CPFs, datas e assinaturas em JSON auditável. E nosso grande diferencial: o Radar Trabalhista cruza os dados, detecta que a ficha de EPI está sem assinatura, bloqueia a catraca preventivamente e calcula em Reais o passivo trabalhista evitado."**

* **`[1:15 - 1:32 | Clique 3: Abre Manuscrito Médico + Fila de Revisão Humana]`**
  > **"Neste prontuário escrito à mão e no AR dos Correios, o motor lê a caligrafia. Como a legibilidade médica teve 74% de confiança — abaixo do nosso corte de 85% — cumprimos o Tratamento de Incerteza: o sistema não aprova sozinho e isola o documento na Fila de Revisão Humana."**

* **`[1:32 - 1:50 | Clique 4: Ativa "Anonimizar (LGPD)" + Mostra Dashboard e CSV]`**
  > **"E atendendo à Segurança LGPD e Observabilidade: com um clique aplicamos tarja preta nas coordenadas do PDF, mascaramos CPFs, RGs e CIDs e geramos o Dashboard de Métricas com exportação da auditoria em CSV."**

---

### 🏗️ `1:50 - 2:20` (30s) — ARQUITETURA, ESCALA E LIMITES (Critério 6: Escalabilidade e Robustez — Slides 10 e 11)
🎙️ **Apresentador 3 (Arquitetura & IA — ex: Luis Miguel / Jamerson):**
*(Mostrando o Diagrama / Aba Escala & FinOps)*

> **"Na nossa arquitetura, qual seria o principal gargalo se multiplicássemos o volume por 10 — como na operação da Bernhoeft, que audita 950 mil terceirizados e 1,5 milhão de páginas por mês? O gargalo seria o custo e a latência de chamar a IA de Visão em todas as páginas.**
>
> **Resolvemos isso com um Funil de 4 Camadas no nosso servidor SaaS: documentos repetidos param no Cache SHA-256 na Camada 0, e PDFs digitais são lidos pelo PyMuPDF na Camada 1 a custo zero — resolvendo 75% do volume sem gastar tokens e acionando o Gemini 2.5 Flash só nos manuscritos e scans, cortando 94% do custo.**
>
> **Para falhas em lotes grandes, salvamos checkpoint por página com retomada via rota `/resume`. Hoje usamos SQLite síncrono no MVP; para produção real, evoluiremos para fila Redis/Celery e PostgreSQL."**

---

### 💰 `2:20 - 2:45` (25s) — NEGÓCIO: Quem Paga, Pelo Quê e Por Que a Conta Fecha (Critério 3 — Slide 12)
🎙️ **Apresentador 1 (Lucas):**
> **"No modelo de negócio, construtoras, indústrias e consultorias de gestão de terceiros pagam uma assinatura SaaS de R$ 2,50 a R$ 5,00 por colaborador monitorado ao mês — ou consomem via API. A conta fecha com mais de 90% de margem porque 75% dos documentos rodam na nossa camada de custo zero, reduzindo 3 dias de fila de catraca para 2 minutos."**

---

### 🤝 `2:45 - 3:00` (15s) — O PEDIDO FINAL (Critério 4: Viabilidade e Próximo Passo — Slide 12)
🎙️ **Apresentador 1 (Lucas):**
> **"Nosso pedido hoje é específico: queremos rodar um piloto de validação de 30 dias com lotes documentais reais junto à Bernhoeft, e conquistar a vaga na batalha de pitches do AgresTI para levar o Citadel AI ao palco do FING. Muito obrigado!"**

---
---

## 🧠 PARTE 2: AS 6 PERGUNTAS OFICIAIS DA BANCA (SLIDE 15 DO PDF) E RESPOSTAS NOTA 5/5

O Slide 15 do material oficial revelou **exatamente as 6 perguntas** que os jurados têm na prancheta para os **5 minutos de Roda de Conversa**:

---

### 1. "Quais capacidades mínimas funcionam de ponta a ponta?"
*(Dica da Banca no Slide 15: Liste com honestidade o que funciona e o que é simulado)*
> **Resposta (Squad Backend):**
> *"Funcionam 100% de ponta a ponta no nosso código atual:*
> *1. Upload de PDF multipágina e renderização real com PyMuPDF;*
> *2. Classificação multiclasse, separação semântica e corte físico dos PDFs gerando arquivo `.ZIP` organizado em pastas por Empresa e CPF;*
> *3. Extração estruturada de campos, entidades e alertas de risco trabalhista;*
> *4. Anonimização LGPD real por expressões regulares (CPF, RG, CNPJ, E-mail, Telefone, CID) com tarja preta renderizada no PDF e download de relatório CSV de auditoria;*
> *5. Persistência transacional em SQLite página a página com retomada real pela rota `/api/jobs/{id}/resume`.*
> *O que possui fallback determinístico pré-calibrado é o nosso lote sintético de demonstração para garantir velocidade e estabilidade caso a internet do evento oscile, mas a integração com a API do Gemini 2.5 Flash está implementada no motor."*

---

### 2. "Por que essa arquitetura?"
*(Dica da Banca no Slide 15: Dê uma razão técnica e uma razão de negócio para cada escolha principal)*
> **Resposta (Squad Backend / Lucas):**
> *"Escolhemos a arquitetura em Funil (FastAPI + Hash SHA-256 + PyMuPDF na frente do Gemini 2.5 Flash) por duas razões:*
> *- **Razão Técnica:** PDFs nativos gerados por sistemas governamentais (FGTS, CND, contratos digitais) não precisam de OCR visual; o PyMuPDF extrai o texto em 2 milissegundos no próprio servidor do SaaS com latência quase zero.*
> *- **Razão de Negócio:** Chamar LLM multimodal em 1,5 milhão de páginas por mês custaria ~R$ 25 mil/mês. Barrando 75% do volume nas Camadas 0 e 1 a custo zero de tokens, derrubamos o custo em 94,6% e viabilizamos cobrar uma mensalidade acessível de R$ 2,50 a R$ 5,00 por funcionário."*

---

### 3. "Como tratam falhas e dados inconsistentes?"
*(Dica da Banca no Slide 15: Mostre o tratamento no código ou explique o plano)*
> **Resposta (Squad Backend):**
> *"Tratamos em duas frentes no código:*
> *- **Falhas de Rede ou Queda no meio do Lote:** Cada página do PDF é registrada na tabela `job_pages` com status individual (`PENDING`, `COMPLETED`, `FAILED`). Se um lote de 500 páginas cair na página 300, a rota `POST /api/jobs/{id}/resume` consulta o banco e processa apenas da página 301 em diante, sem perder trabalho nem cobrar tokens duplicados.*
> *- **Dados Inconsistentes, Rasurados ou Ilegíveis:** Aplicamos um limiar de confiança (`CONFIDENCE_THRESHOLD = 0.85`). Qualquer página com letra médica ilegível, rasura ou falta de assinatura cai automaticamente para a fila `REVISAO_HUMANA` e bloqueia a liberação automática da catraca."*

---

### 4. "Como garantem segurança e privacidade?"
*(Dica da Banca no Slide 15: Controle de acesso, dados de teste e credenciais fora do código)*
> **Resposta (Squad Segurança & LGPD — Thaynara):**
> *"Seguimos 3 práticas rigorosas de Privacy-by-Design:*
> *1. **Credenciais fora do código:** Nenhuma chave de API está hardcoded; usamos variáveis de ambiente (`.env`) ignoradas no Git.*
> *2. **Dados 100% Sintéticos:** Construímos um gerador próprio (`sample_generator.py`) para criar ASOs, RGs, prontuários e ARs de teste sem expor dados reais de nenhum cidadão.*
> *3. **Mascaramento Duplo (Texto e Imagem):** Nosso módulo `anonymizer.py` substitui CPFs, RGs, contatos e CIDs médicos por tokens mascarados no JSON, aplica tarja preta direta na imagem/PDF antes de exportações externas e gera um Log CSV auditável."*

---

### 5. "Quem pagaria por isso?"
*(Dica da Banca no Slide 15: O segmento validado e o modelo de receita)*
> **Resposta (Lucas — Negócios):**
> *"Temos dois segmentos pagantes claros:*
> *1. **Contratantes Diretos (Construtoras, Indústrias, Agroindústrias e Hospitais):** Pagam assinatura mensal SaaS de **R$ 2,50 a R$ 5,00 por colaborador ativo monitorado**, economizando até 85% do tempo da equipe de RH e evitando multas de NRs e processos trabalhistas (Súmula 331 TST).*
> *2. **Consultorias de Gestão de Terceiros e BPO de RH (como a Bernhoeft):** Contratam nosso motor via API White-Label por volume para automatizar a triagem de primeira camada dos analistas deles."*

---

### 6. "O que falta para ir para produção?"
*(Dica da Banca no Slide 15: Os próximos passos e o que precisam para executá-los)*
> **Resposta (Lucas / Squad Backend):**
> *"Mapeamos 3 passos realistas para sair do MVP para produção comercial em 30 dias:*
> *1. **Infraestrutura Assíncrona:** Substituir o SQLite local por PostgreSQL e adicionar uma fila de mensageria (Redis + Celery/RabbitMQ) com armazenamento em bucket S3/GCS para suportar milhares de uploads simultâneos.*
> *2. **Calibragem com Dados Reais:** Rodar um piloto com uma empresa parceira (como a Bernhoeft) usando um lote histórico anonimizado de 5.000 documentos reais para calibrar os pesos do nosso detector de divergências trabalhistas.*
> *3. **Controle de Acesso Multi-Tenant:** Implementar autenticação JWT/OAuth2 separando os ambientes do Fornecedor (quem envia) e do Auditor de RH (quem aprova)."*

---

## ✅ CHECKLIST FINAL DO DEMO DAY (SLIDE 18 DO PDF)
- [ ] **Até 12h00:** Repositório GitHub atualizado com `README.md` claro de como rodar, registro de premissas/limitações e code freeze feito.
- [ ] **Até 13h00:** Pitch ensaiado no cronômetro em **2m50s a 2m58s** (nunca passar de 3m00s!).
- [ ] **Zoom da Tela:** Navegador em `115%` ou `125%` para a banca ler os badges de longe.
- [ ] **Plano B Gravado:** Gravar um vídeo de 1 minuto da tela funcionando perfeitamente e deixar salvo na Área de Trabalho caso o Wi-Fi do evento caia.
