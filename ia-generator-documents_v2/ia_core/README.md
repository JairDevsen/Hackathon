# IA Core (Dev 4): Gemini multimodal

Separação de lotes, classificação por tipo e extração estruturada (Pydantic) de documentos trabalhistas.

## Começar em 15 minutos

```bash
pip install google-genai pydantic pypdfium2 pillow
export GEMINI_API_KEY="<sua-chave-do-ai-studio>"  # protótipo (só com documentos fictícios/anonimizados)
mkdir amostras && cp <seus 20-30 documentos> amostras/
python scripts/avaliar.py amostras/ --saida resultados/
```

Para usar dados reais, troque para o Vertex AI (sem mudar o código):
```bash
export GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=seu-projeto GOOGLE_CLOUD_LOCATION=us-central1
```

## Arquivos
| Arquivo | O que tem |
|---|---|
| `ia_core/schemas.py` | Tipos de documento, pistas visuais, schemas de classificação e de extração por tipo |
| `ia_core/prompts.py` | System prompts e templates (versionados com `VERSAO_PROMPT`) |
| `ia_core/extrator.py` | `IACore`: classificação em janelas de 8 páginas, agrupamento, extração, retry 429/5xx |
| `ia_core/validacoes.py` | CPF/CNPJ, somas do holerite, FGTS 8%, jornada >10h, intervalo <1h, certidão vencida etc. |
| `scripts/avaliar.py` | Roda uma pasta, gera JSON por arquivo + `resumo.csv` e mede acerto contra `gabarito.csv` |

## Fluxo
1. **Classificação:** o lote vai em janelas de 8 páginas, cada uma levando a última página da janela anterior como contexto. O modelo devolve um rótulo por página: `tipo`, `inicia_documento`, `multiplos_documentos`, `legivel` e `confianca`.
2. **Agrupamento** (código, sem IA): abre um novo documento quando `inicia_documento=true` ou o tipo muda.
3. **Extração:** uma chamada por documento, com o schema do tipo. Documentos marcados para revisão vão direto para o modelo Pro.
4. **Validação:** `validar(dados)` devolve uma lista de `Alerta`.

## Contrato com o squad
- **Dev 3 (FastAPI/fatiador):** me entrega `list[Pagina(numero, conteudo_png, mime_type)]`, com páginas numeradas a partir de 1 e lado máximo de ~3072 px.
  Na rota `/jobs`, chamar `classificar_lote` → `agrupar` → `extrair` para cada documento.
- **Dev 5 (SQLite/retry):** cada janela de classificação e cada extração é independente e idempotente. Ele persiste o status por janela e por documento,
  e o `/retry` chama de novo só `classificar_janela(contexto, alvo)` ou `extrair(doc, paginas)` do que tiver falhado (`ResultadoExtracao.erro != None`).

## Ciclo de melhoria do prompt
1. Monte o `amostras/gabarito.csv` (arquivo, pagina, tipo, inicia_documento) para os 20–30 documentos.
2. Rode `avaliar.py` e anote o acerto de tipo e de quebra.
3. Olhe a matriz de confusão impressa no fim e ajuste a pista visual do tipo confundido em `DESCRICAO_TIPOS`.
4. Incremente `VERSAO_PROMPT` e rode de novo. Nunca mude o prompt sem medir.

Metas razoáveis para a demo: tipo ≥ 95%, quebra ≥ 90%, e nenhum valor inventado (campo ausente = `null`).
