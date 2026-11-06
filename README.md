# Citadel AI — Hackathon Garanhuns Tech 2026 (Desafio 3)

Sistema ponta a ponta para ingestão de lotes documentais de grande porte, detecção automática de início/fim, agrupamento de páginas, classificação multimodal (incluindo **AR dos Correios** e **Documentos Escritos à Mão**), OCR pesquisável, **Fila de Revisão Humana (HITL)**, **Retomada após Falha** e **Anonimização de Dados Sensíveis (LGPD)**.

---

## 👥 Divisão Oficial da Equipe e Módulos do Código

| Integrante | Papel / Squad | Arquivo Principal no Repositório |
| :--- | :--- | :--- |
| **Lucas** | **Líder & Pitch** | [`PLANO_OPERACIONAL_HACKATHON.pdf`](PLANO_OPERACIONAL_HACKATHON.pdf) / [`CLICKUP_ORGANIZACAO_EQUIPE.md`](CLICKUP_ORGANIZACAO_EQUIPE.md) |
| **Jair** | **Dev 1 (Front/UX)** | [`frontend/index.html`](frontend/index.html) (Uploader Drag & Drop + Visor Lado a Lado + Busca OCR) |
| **Davi** | **Dev 2 (Front/HITL)** | [`frontend/index.html`](frontend/index.html) (Estação de Revisão Humana HITL + Toggle LGPD) |
| **Luis Miguel** | **Dev 3 (Backend/Ingestão)** | [`backend/ingestion.py`](backend/ingestion.py) & [`backend/main.py`](backend/main.py) (FastAPI + Fatiamento PDF/TIFF/ZIP) |
| **Jamerson** | **Dev 4 (Motor IA)** | [`backend/gemini_engine.py`](backend/gemini_engine.py) & [`backend/schemas.py`](backend/schemas.py) (Gemini 3.8 Flash Multimodal + AR & Manuscritos) |
| **Lennarth** | **Dev 5 (Resiliência)** | [`backend/database.py`](backend/database.py) (Checkpointing SQLite página a página + Retomada `/resume`) |
| **Thaynara** | **Dev 6 (LGPD & QA)** | [`backend/anonymizer.py`](backend/anonymizer.py) & [`backend/sample_generator.py`](backend/sample_generator.py) (Tarjas LGPD na imagem/texto + Lotes de Teste) |

---

## ⚡ Como Executar em 1 Clique

Basta dar duplo clique em **`iniciar_sistema.bat`** ou rodar no terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Depois abra no navegador:
- **Aplicação Completa:** http://localhost:8000
- **Documentação Interativa da API (Swagger):** http://localhost:8000/docs

---

## ✅ Checklist dos Requisitos e Diferenciais Cobertos

### Capacidades Mínimas:
1. **Detecção de início e fim de cada documento:** Identifica onde começa e termina cada documento dentro de um PDF multipágina.
2. **Agrupamento de páginas:** Junta frente e verso de CNH (Págs 1 e 2) e páginas de Contrato (Págs 5 e 6) em documentos únicos.
3. **Classificação por tipo documental:** Suporta `AVISO_RECEBIMENTO_CORREIOS` (AR), `DOCUMENTO_MANUSCRITO`, `CNH`, `RG`, `CONTRATO`, `COMPROVANTE_RESIDENCIA`, `NOTA_FISCAL`, `HOLERITE`.
4. **OCR pesquisável:** Transcreve texto impresso e **caligrafia manuscrita** com barra de busca e highlight amarelo em tempo real.
5. **Confiança e fila de revisão humana (HITL):** Score de confiança por documento e retenção automática de manuscritos rasurados para aprovação humana em 1 clique.

### Diferenciais Que Surpreendem:
1. **Modelos Multimodais (`gemini-3.8-flash`):** Extração conjunta visual + textual de formulários postais AR e escrita à mão via Interactions API com JSON Schema estrito.
2. **Retomada após falha:** Persistência transacional por página em SQLite (`factory_state.db`). Se o lote cair na página 4 de 6, o botão **Retomar Processamento** continua da página 4 sem reprocessar as páginas 1 a 3.
3. **Anonimização de dados (LGPD):** Mascaramento automático de CPF, RG, CNPJ, CEP, Telefones e Nomes Manuscritos no OCR e aplicação de **tarjas visuais na imagem** das páginas.
