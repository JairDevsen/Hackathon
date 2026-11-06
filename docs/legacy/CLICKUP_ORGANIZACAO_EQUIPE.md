# 📋 Manual de Organização no ClickUp — Document AI Factory
**Hack Garanhuns Tech 2026 | Gestão de Equipe (Líder Lucas + 6 Devs)**

---

## ⚡ 1. Importação Rápida em 30 Segundos (CSV Atualizado com os Nomes Reais)
O arquivo de importação automática já foi atualizado com os nomes de cada integrante do time, prazos, prioridades e estimativas:

📁 **[`clickup_import_hackathon.csv`](file:///d:/Users/TUDO%20PC%20NOVO/Lucas/Antigravity/HACKATHON%20BEANHOFT/clickup_import_hackathon.csv)**

### Como Importar no ClickUp:
1. No ClickUp, clique no menu inferior esquerdo (**Settings** / Configurações).
2. Vá em **Import / Export** (Importar / Exportar).
3. Selecione **CSV / Excel**.
4. Faça upload do arquivo `clickup_import_hackathon.csv`.
5. Mapeie as colunas (Assignee -> Membro correspondente) e confirme.

---

## 👥 2. Divisão de Listas e Atribuições Oficiais

### 🎨 Lista 1: `Squad 1 - Frontend & UX`
| Integrante | Função Principal | Tarefas no ClickUp |
| :--- | :--- | :--- |
| **Jair** | Ingestão Visual & Document Viewer | • Setup Next.js + Tailwind + Lucide<br>• Componente Drag & Drop para arquivos pesados (PDF/imagens)<br>• Visualizador de documentos agrupados lado a lado (Imagem vs OCR) |
| **Davi** | Triagem Humana (HITL) & Revisão | • Tabela da Fila de Revisão Humana com Badges de Confiança<br>• Modal de edição rápida (alterar tipo de documento ou texto OCR)<br>• Toggle de modo anonimizado (LGPD) |

---

### ⚙️ Lista 2: `Squad 2 - Backend & IA Core`
| Integrante | Função Principal | Tarefas no ClickUp |
| :--- | :--- | :--- |
| **Luis Miguel** | Ingestão, Fatiamento & API Gateway | • Setup FastAPI e CORS<br>• Módulo de conversão PDF/TIFF em páginas PNG/JPEG (`PyMuPDF`)<br>• Endpoints `/api/upload` e `/api/jobs/{id}` com mock inicial |
| **Jamerson** | Motor Gemini Multimodal | • Configuração da SDK do Gemini Multimodal<br>• Schemas Pydantic estruturados (detecção de início/fim de doc + tipo + OCR)<br>• Pipeline de chunking e cálculo de confiança |
| **Lennarth** | Resiliência & Revisão Humana (HITL) | • Módulo de **Retomada após Falha** (SQLite gravando status página a página)<br>• Rota `/api/jobs/{id}/retry` para reprocessar apenas o que falhou<br>• Rota `/api/review/{id}` para registrar aprovação do operador humano |

---

### 🛡️ Lista 3: `Squad 3 - Segurança, Dados & QA`
| Integrante | Função Principal | Tarefas no ClickUp |
| :--- | :--- | :--- |
| **Thaynara** | Anonimização (LGPD) & Validação QA | • Módulo de anonimização: mascarar CPF, RG, telefones e nomes no OCR e tarjas na imagem<br>• Criar os **2 Lotes Oficiais da Demo**: Lote 1 (docs perfeitos agrupados) e Lote 2 (doc rasurado para cair na fila humana)<br>• Bateria de testes de ponta a ponta |

---

### 👑 Lista 4: `Liderança, Pitch & Demo`
| Integrante | Função Principal | Tarefas no ClickUp |
| :--- | :--- | :--- |
| **Lucas (Líder)** | Coordenação, Pitch & Blindagem | • Criação dos Slides da Apresentação (5 slides)<br>• Roteirização e ensaio da Demo de 3 minutos<br>• Gravação de vídeo de 1 min de backup da tela (caso o Wi-Fi oscile no palco)<br>• Blindagem de escopo e facilitação entre os squads |

---

## 💬 3. Mensagem Pronta para o Grupo da Equipe (Copiar & Colar)

```markdown
Fala pessoal! 🚀
Para organizarmos nossa entrega e vencermos o desafio Document AI Factory nessas 14h, nosso quadro no ClickUp já está estruturado com papéis bem definidos para cada um de nós:

🔹 Squad 1 (Front/UX):
• @Jair: Tela de Upload (Drag & Drop com barra de progresso) + Visualizador lado a lado de documentos agrupados e OCR
• @Davi: Painel da Fila de Revisão Humana (HITL com badges de confiança) + Modal de aprovação/edição

🔹 Squad 2 (Backend & IA Core):
• @Luis Miguel: API FastAPI + Ingestão e fatiador de PDFs/imagens em páginas
• @Jamerson: Motor Gemini Multimodal (Prompt estruturado Pydantic para separar início/fim de documentos, classificar e extrair OCR)
• @Lennarth: Resiliência/Retomada após Falha (gravação de status no SQLite) + Endpoint de revisão humana

🔹 Squad 3 (Segurança, Dados & QA):
• @Thaynara: Anonimização de Dados LGPD (tarjas e máscaras de PII) + Criação dos PDFs oficiais de teste da demo + Testes E2E

👑 Liderança & Pitch:
• @Lucas: Focado no Pitch, na narrativa dos jurados, nos slides, na blindagem de escopo e na gravação da demo de backup.

Já subi as tarefas no ClickUp com as horas estimadas. Quando iniciarem uma tarefa, alterem o status para IN PROGRESS. Vamos buscar esse 1º lugar! 🔥
```
