# 🎤 ROTEIRO OFICIAL DE PITCH (3 MIN) & GUIA DA BANCA (5 MIN) — LINGUAGEM CLARA PARA PÚBLICO GERAL
**Produto:** Citadel AI — Plataforma SaaS B2B de Inteligência e Conformidade Documental Trabalhista  
**Desafio:** Desafio 3 — Document AI Factory (Hack Garanhuns Tech 2026)  
**Formato Oficial do Demo Day (Slide 4 e 6 do Edital):**  
- **3 Minutos de Pitch** (com **1m15s = 40% do tempo de Demo ao Vivo Obrigatória** seguindo a régua `0:00 | 0:20 | 0:35 | 1:50 | 2:20 | 2:45`)  
- **5 Minutos de Perguntas da Banca** (avaliando os 6 critérios de 0 a 5 pontos)

---

## ⚠️ REGRAS DE OURO DA BANCA (EXTRAÍDAS DO PDF OFICIAL DOS ORGANIZADORES)

1. **Proibido uma pessoa só falar (Slide 17):** Dividam a fala entre **3 apresentadores** (Problema/Negócio + Demo + Arquitetura/Escala) + **1 operador no notebook**.
2. **Linguagem simples, sem sopa de letrinhas (Slide 7):** Fale de forma que empresários, mentores do SEBRAE e público geral entendam na hora (sem citar nomes de bibliotecas ou códigos como SHA-256 ou PyMuPDF durante o pitch).
3. **Menos Slide, Mais Tela (Slide 7 e 9):** Dê **Zoom de 125%** no navegador para a banca enxergar de longe. Tenham um **Vídeo Curto Gravado (Plano B)** aberto no reprodutor caso a internet/servidor oscile na hora.
4. **Honestidade gera nota máxima em Viabilidade e Escalabilidade (Slide 10, 11 e 15):** Diga claramente qual é o gargalo em 10x de escala, o que já funciona hoje e o que falta para ir para produção.
5. **Fechar com "O Pedido" nos últimos 15 segundos (Slide 6 e 12):** Pedir um piloto com empresa parceira (Bernhoeft) e a vaga no AgresTI / palco do FING.

---

## ⏱️ PARTE 1: ROTEIRO CRONOMETRADO DE 3 MINUTOS (ZERO JARGÃO TÉCNICO)

### 🔴 BLOCO 1: A Dor Real do Mercado (`0:00 até 0:35` — 35 segundos)
🎙️ **Apresentador 1 (Lucas — Postura firme, olhando para os jurados. Sem falar da Bernhoeft ainda — apresente como um produto SaaS de mercado real):**
> **"Boa noite! Todos os dias, milhares de construtoras, indústrias, hospitais e agroindústrias no Brasil precisam contratar e mobilizar trabalhadores rápido. Mas antes de qualquer funcionário entrar na operação, o RH precisa auditar dezenas de documentos obrigatórios.**
>
> **Qual é o problema real? Os documentos nunca chegam organizados. Eles chegam num único PDF 'Frankenstein' com 50 páginas misturadas no e-mail: tem exame ASO junto com ficha de EPI, contrato sem assinatura, atestado escrito à mão por médico de plantão e até comprovante AR dos Correios.**
>
> **O resultado disso? Equipes de RH perdendo 80% do dia recortando e renomeando PDF na mão, funcionários parados esperando dias pela liberação da catraca, e empresas levando multas milionárias por deixarem passar um documento vencido ou vazarem dados na LGPD."**

---

### ⚡ BLOCO 2: A Solução — Citadel AI (`0:35 até 0:50` — 15 segundos)
🎙️ **Apresentador 1 (Lucas):**
> **"Para acabar com esse gargalo, criamos o Citadel AI: uma plataforma SaaS online que recebe qualquer lote de documentos caóticos e, em segundos, devolve tudo separado em pastas por funcionário, auditado contra riscos trabalhistas e protegido pela LGPD. Vejam funcionando ao vivo:"**

---

### 🖥️ BLOCO 3: Apresentando o SaaS na Prática (`0:50 até 1:50` — 60 segundos de Demo Ao Vivo)
🎙️ **Apresentador 2 (Demo na Tela — ex: Jair/Davi falando + Operador clicando na tela):**

* **`[0:50 - 1:05 | Clique 1: "Carregar Exemplo" / Separação e Pastas]`**
  > **"Direto pelo navegador, sem instalar nada, o RH ou a terceirizada envia o PDF misturado. Em segundos, o sistema identifica onde começa e termina cada documento — ASO, Contrato, EPI, Manuscrito e AR dos Correios — e já cria as pastas por Empresa e Funcionário, prontas para baixar com cada PDF recortado e nomeado pela data de validade."**

* **`[1:05 - 1:22 | Clique 2: Abre Documento -> Mostra Dados Extraídos e Radar Trabalhista]`**
  > **"Ao abrir o documento, o sistema já extrai todos os dados automaticamente: nomes, CPFs, datas e assinaturas. E aqui entra o nosso grande diferencial: o Radar Trabalhista cruza as informações, detecta que a ficha de EPI está sem assinatura, bloqueia a catraca preventivamente e já calcula em Reais a multa trabalhista que a empresa acabou de evitar."**

* **`[1:22 - 1:37 | Clique 3: Abre Manuscrito Médico + Fila de Revisão Humana]`**
  > **"Mesmo neste prontuário escrito à mão e no AR dos Correios, o sistema lê a caligrafia. Como a letra médica estava difícil e teve 74% de confiança — abaixo da nossa margem segura de 85% — o sistema não arrisca sozinho: ele separa o documento direto na Fila de Revisão Humana."**

* **`[1:37 - 1:50 | Clique 4: Ativa "Anonimizar (LGPD)" + Mostra Painel de Resultados]`**
  > **"E para garantir a privacidade na LGPD: com um clique aplicamos tarja preta automática sobre os dados pessoais no documento e geramos o painel completo com relatório de auditoria."**

---

### 🏗️ `1:50 - 2:20` (30s) — ARQUITETURA, ESCALA E LIMITES (Sem Jargão Técnico! — Slides 7, 10 e 11)
🎙️ **Apresentador 3 (Arquitetura & Escala — ex: Luis Miguel / Jamerson):**
*(Mostrando o Diagrama / Aba Escala & FinOps)*

> **"E como essa solução escala sem ficar cara? Pensem numa operação gigante como a da própria Bernhoeft, que audita 950 mil trabalhadores e 1 milhão e meio de páginas por mês. O grande gargalo seria o custo de acionar a Inteligência Artificial pesada em todas as páginas.**
>
> **Resolvemos isso com um Filtro Inteligente de 4 Etapas no nosso servidor: primeiro, o sistema barra na hora arquivos repetidos que já foram enviados antes e ainda estão na validade; segundo, documentos digitais gerados por computador são lidos direto pelo nosso sistema básico a custo zero — resolvendo 75% do volume sem gastar com Inteligência Artificial, que só é acionada nos manuscritos e documentos escaneados, cortando 94% do custo.**
>
> **Se a internet cair no meio de um lote grande, o sistema salva o progresso página por página e continua de onde parou. Hoje nosso protótipo processa um lote por vez; para ir para produção real, nosso próximo passo é ativar filas paralelas em nuvem para atender milhares de empresas ao mesmo tempo."**

---

### 💰 `2:20 - 2:45` (25s) — NEGÓCIO: Quem Paga, Pelo Quê e Por Que a Conta Fecha (Critério 3 — Slide 12)
🎙️ **Apresentador 1 (Lucas):**
> **"No modelo de negócio, construtoras, indústrias e consultorias de gestão de terceiros pagam uma assinatura de R$ 2,50 a R$ 5,00 por trabalhador monitorado ao mês — ou conectam nosso motor direto no sistema que já usam. A conta fecha com mais de 90% de margem porque 75% dos documentos rodam na nossa etapa de custo zero, reduzindo 3 dias de fila de catraca para 2 minutos."**

---

### 🤝 `2:45 - 3:00` (15s) — O PEDIDO FINAL (Critério 4: Viabilidade e Próximo Passo — Slide 12)
🎙️ **Apresentador 1 (Lucas):**
> **"Nosso pedido hoje é direto: queremos rodar um piloto de validação de 30 dias com lotes documentais reais junto à Bernhoeft, e conquistar a vaga na batalha de pitches do AgresTI para levar o Citadel AI ao palco do FING. Muito obrigado!"**

---
---

## 🧠 PARTE 2: AS 6 PERGUNTAS OFICIAIS DA BANCA (SLIDE 15) — RESPOSTAS CLARAS E DIRETAS

O Slide 15 do material oficial revelou **exatamente as 6 perguntas** que os jurados têm na prancheta para os **5 minutos de Roda de Conversa**:

---

### 1. "Quais capacidades mínimas funcionam de ponta a ponta?"
*(Dica da Banca no Slide 15: Liste com honestidade o que funciona e o que é simulado)*
> **Resposta:**
> *"Funcionam 100% de ponta a ponta hoje no sistema:*
> *1. Envio de PDF com várias páginas misturadas e separação visual de cada página;*
> *2. Classificação automática do tipo de documento e recorte físico dos PDFs gerando um pacote compactado organizado em pastas por Empresa e Funcionário;*
> *3. Extração automática dos dados do documento e alerta de riscos trabalhistas;*
> *4. Proteção de dados pessoais (CPF, RG, contatos e código de doença) com tarja preta na imagem e geração de planilha de auditoria;*
> *5. Salvamento automático página a página, permitindo retomar o lote se a conexão cair.*
> *Para garantir que a demonstração funcione mesmo se a internet do evento cair, deixamos um lote de teste pré-carregado, além da conexão direta com a Inteligência Artificial do Google Gemini."*

---

### 2. "Por que essa arquitetura?"
*(Dica da Banca no Slide 15: Dê uma razão técnica e uma razão de negócio para cada escolha principal)*
> **Resposta:**
> *"Criamos a arquitetura em Funil de 4 Etapas por dois motivos simples:*
> *- **Motivo Técnico (Velocidade):** Documentos que já nascem digitais de sistemas do governo (como FGTS, certidões e contratos) não precisam de leitura por visão computacional; nosso servidor lê o texto instantaneamente em milésimos de segundo.*
> *- **Motivo de Negócio (Custo):** Usar Inteligência Artificial visual em 1,5 milhão de páginas custaria quase R$ 25 mil por mês. Como nosso filtro resolve 75% dos documentos sem gastar créditos de IA, reduzimos o custo em 94,6% e conseguimos cobrar apenas R$ 2,50 por funcionário mantendo alta lucratividade."*

---

### 3. "Como tratam falhas e dados inconsistentes?"
*(Dica da Banca no Slide 15: Mostre o tratamento no código ou explique o plano)*
> **Resposta:**
> *"Tratamos de duas formas:*
> *- **Queda de Internet ou Falha no Lote:** Cada página analisada é salva imediatamente no banco de dados. Se um arquivo de 500 páginas travar na página 300, nosso botão de retomada continua da página 301 sem perder o que já foi feito.*
> *- **Documentos Rasurados ou Letra Ilegível:** Definimos uma trava de segurança de 85% de certeza. Sempre que uma letra médica manuscrita ou documento batido fica abaixo de 85% de clareza, o sistema bloqueia a liberação automática da catraca e envia o documento para a Fila de Revisão Humana."*

---

### 4. "Como garantem segurança e privacidade?"
*(Dica da Banca no Slide 15: Controle de acesso, dados de teste e credenciais fora do código)*
> **Resposta:**
> *"Adotamos 3 medidas práticas:*
> *1. **Senhas e chaves protegidas:** Nenhuma senha ou chave de sistema fica exposta no código.*
> *2. **Dados de Teste Fictícios:** Todos os documentos da apresentação foram gerados artificialmente pelo nosso sistema para nunca expor dados médicos ou documentos reais de trabalhadores.*
> *3. **Tarja Preta e Ocultação de Dados:** Ao ativar o modo LGPD, o sistema oculta CPFs, RGs, contatos e diagnósticos médicos tanto no texto quanto aplicando uma tarja preta sobre o PDF antes de qualquer compartilhamento externo."*

---

### 5. "Quem pagaria por isso?"
*(Dica da Banca no Slide 15: O segmento validado e o modelo de receita)*
> **Resposta:**
> *"Temos dois perfis de clientes pagantes:*
> *1. **Empresas Contratantes (Construtoras, Indústrias, Agroindústrias e Hospitais):** Pagam assinatura mensal de **R$ 2,50 a R$ 5,00 por trabalhador ativo**, economizando 85% do tempo do RH e evitando processos trabalhistas por falhas em documentos.*
> *2. **Grandes Consultorias de Gestão de Terceiros (como a Bernhoeft):** Contratam nossa tecnologia integrada ao sistema deles para acelerar o trabalho de centenas de analistas."*

---

### 6. "O que falta para ir para produção?"
*(Dica da Banca no Slide 15: Os próximos passos e o que precisam para executá-los)*
> **Resposta:**
> *"Faltam 3 passos claros para colocarmos em operação comercial em 30 dias:*
> *1. **Processamento Paralelo em Nuvem:** Migrar nosso banco de testes local para um banco corporativo na nuvem com filas paralelas, permitindo que centenas de empresas enviem lotes ao mesmo tempo.*
> *2. **Piloto com Dados Reais:** Rodar um teste de 30 dias com uma empresa parceira como a Bernhoeft para calibrar ainda mais os alertas de risco trabalhista em casos reais.*
> *3. **Login Separado por Perfil:** Liberar o acesso com login próprio para o fornecedor enviar os documentos na ponta e o RH aprovar no painel central."*

---

## ✅ CHECKLIST FINAL DO DEMO DAY (SLIDE 18 DO PDF)
- [ ] **Até 12h00:** Repositório GitHub atualizado com `README.md` claro de como rodar, registro de premissas/limitações e code freeze feito.
- [ ] **Até 13h00:** Pitch ensaiado no cronômetro em **2m50s a 2m58s** (nunca passar de 3m00s!).
- [ ] **Zoom da Tela:** Navegador em `115%` ou `125%` para a banca ler os alertas de longe.
- [ ] **Plano B Gravado:** Gravar um vídeo de 1 minuto da tela funcionando perfeitamente e deixar salvo na Área de Trabalho caso o Wi-Fi do evento caia.
