# 🏆 Briefing Geral da Equipe — Document AI Factory (Bernhoeft Edition)
**Hack Garanhuns Tech 2026 | Desafio 3 | Repositório Oficial:** https://github.com/JairDevsen/Hackathon

---

## 🎯 1. O Que Estamos Construindo e Por Quê (Foco Bernhoeft)
A **Bernhoeft** é líder nacional em **Gestão de Riscos com Terceiros (GRT)**, **BPO Trabalhista/Fiscal** e **Cálculos Judiciais**, gerenciando a conformidade documental de cerca de **950 mil funcionários terceirizados** no Brasil.

* **A Dor Real:** O RH das empresas terceirizadas escaneia dezenas de documentos de vários funcionários de uma vez só num único arquivo PDF pesado e caótico (`SCAN_001.pdf`), misturando CNH frente/verso, ASO médico, Contratos, **AR dos Correios preenchido à mão** e **Fichas de EPI manuscritas**. Hoje, cortar, descobrir de quem é cada página, renomear e auditar tudo leva horas de trabalho manual.
* **Nossa Solução (Document AI Factory • Bernhoeft Edition):** Uma esteira inteligente que recebe o lote bruto, detecta início e fim de cada documento, agrupa páginas do mesmo documento, lê texto impresso e **caligrafia escrita à mão (AR e EPI)**, recorta fisicamente cada documento em um **PDF individual**, organiza em **pastas automáticas por Empresa (CNPJ) e Funcionário (CPF)**, aplica **tarjas de anonimização LGPD** e emite o **Parecer de Liberação de Catraca GRT**.

---

## ✅ 2. Todos os Requisitos e Diferenciais Já Entregues no Código

### Capacidades Mínimas (100% Concluídas):
1. **Detecção de início e fim de cada documento:** Identifica automaticamente onde começa e termina cada documento no lote.
2. **Agrupamento de páginas + Recorte Físico em PDF:** Junta páginas do mesmo documento (ex: Frente e Verso da CNH nas págs 1–2; Contrato nas págs 5–6) e gera os arquivos PDF recortados prontos para download individual ou `.ZIP`.
3. **Classificação por tipo documental (Taxonomia Bernhoeft):**
   * `AVISO_RECEBIMENTO_CORREIOS` (AR Postal com rastreio e assinatura à caneta)
   * `DOCUMENTO_MANUSCRITO` / `FICHA_EPI_MANUSCRITA` (NR-06 e apontamentos escritos à mão)
   * `ASO_SAUDE_OCUPACIONAL` (Saúde Ocupacional NR-07)
   * `CNH`, `RG`, `CONTRATO`, `CARTAO_PONTO_TRABALHISTA`, `CERTIDAO_NEGATIVA_CND`, `HOLERITE`, `NOTA_FISCAL`.
4. **OCR Pesquisável (Impresso + Manuscrito):** Transcrição completa com barra de busca em tempo real e grifo amarelo (*highlight*).
5. **Score de Confiança e Fila de Revisão Humana (HITL):** Documentos com rasura manual ou confiança `< 78%` geram **Bloqueio Preventivo de Catraca** e vão para a aba **Fila do Analista GRT**, onde são validados e liberados em 1 clique.

### Diferenciais Que Surpreendem + Extras Campeões:
1. **Motor Multimodal (`gemini-3.8-flash`):** Extrai simultaneamente layout, código de rastreio de AR e caligrafia cursiva em JSON estruturado (Pydantic).
2. **Retomada após Falha (Resiliência com SQLite):** Salva checkpoint página a página (`COMPLETED`, `FAILED`, `PENDING`). Se o lote cair na página 4 de 6, o botão **Retomar Processamento** continua exatamente da página 4 sem perder nem pagar de novo pelas páginas 1 a 3.
3. **Anonimização de Dados Sensíveis (LGPD):** Mascara CPF, RG, CNPJ, telefones e nomes no OCR **e aplica tarjas pretas diretamente na imagem e nos PDFs recortados** (`LGPD_01_CNH_...pdf`).
4. **Indexação Automática para o RH (Árvore de Pastas):** Gera o `.ZIP` já organizado em `EMPRESA_CNPJ / COLABORADOR_NOME_CPF / TIPO_DOC_NOME_CPF_VALIDADE.pdf`.
5. **Funil de Custo Zero para 950 Mil Funcionários (Aba FinOps):**
   * **Camada 0 (35%):** Deduplicação via Hash SHA-256 (barra CNH, ASO e CNDs repetidos ainda vigentes = **0 Tokens**).
   * **Camada 1 (40%):** Extração nativa de PDFs digitais via `PyMuPDF` + Regex (**0 Tokens**).
   * **Camada 2 (15%):** OCR Local em container para impressos limpos (**0 Tokens**).
   * **Camada 3 (Apenas 10%):** Só manuscritos, ARs dos Correios e documentos rasurados sobem para o Gemini Multimodal (258 tokens/pág + Flex Tier), gerando **99,7% de economia** (de R$ 410 mil/mês para ~R$ 1.290/mês).

---

## 👥 3. Divisão Oficial da Equipe e Onde Está Cada Módulo

| Integrante | Papel no Time | Arquivos de Responsabilidade |
| :--- | :--- | :--- |
| **Lucas** | **Líder, Estratégia Bernhoeft & Pitch** | Coordenação geral, narrativa FinOps 950k, slides e demo ao vivo |
| **Jair (Dev 1)** | **Squad 1: Frontend (Ingestão & Visor)** | `frontend/index.html` (Uploader Drag & Drop, Visor Lado a Lado, Busca OCR e Download PDF/ZIP) |
| **Davi (Dev 2)** | **Squad 1: Frontend (HITL, LGPD & FinOps)** | `frontend/index.html` (Aba Fila do Analista GRT, Toggle LGPD e Aba Simulador 950k) |
| **Luis Miguel (Dev 3)** | **Squad 2: Backend (API & Fatiador PDF)** | `backend/main.py` & `backend/ingestion.py` (Rotas FastAPI, corte de páginas e exportação ZIP) |
| **Jamerson (Dev 4)** | **Squad 2: Backend (Motor IA & Funil)** | `backend/gemini_engine.py` & `backend/schemas.py` (Gemini Multimodal, AR/Manuscritos, Hash SHA-256 e Compliance GRT) |
| **Lennarth (Dev 5)** | **Squad 2: Backend (Resiliência SQLite)** | `backend/database.py` (Checkpoints transacionais página a página e rota `/resume`) |
| **Thaynara (Dev 6)** | **Squad 3: Segurança LGPD, Dados & QA** | `backend/anonymizer.py`, `backend/sample_generator.py` & `test_pipeline.py` (Tarjas LGPD, Dossiês de Teste e Testes E2E) |

---

## ⚡ 4. Como Rodar o Projeto na Máquina de Qualquer Dev (1 Minuto)

```bash
git clone https://github.com/JairDevsen/Hackathon.git
cd Hackathon
uv sync
.\iniciar_sistema.bat
```
* **Interface Web:** http://localhost:8000
* **Swagger API Docs:** http://localhost:8000/docs
* **Rodar Testes Automatizados E2E:** `.\.venv\Scripts\python.exe test_pipeline.py`
