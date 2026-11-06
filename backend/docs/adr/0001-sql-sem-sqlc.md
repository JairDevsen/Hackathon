# ADR 0001 — SQL à mão com pgx e `json_agg` no lugar de sqlc

**Contexto:** o prompt pede `pgx + sqlc`. A maior parte das telas é leitura que devolve listas/objetos JSON ao frontend.
**Decisão:** consultas escritas em SQL e retornadas direto como JSON (`json_agg`/`row_to_json`), sem structs intermediárias; escrita com `pgx` parametrizado. Menos código e menos risco de divergência entre struct e tela.
**Consequências:** sem tipagem gerada das consultas (erros de coluna aparecem em execução: cobertos pelo E2E). Migrar para sqlc é viável tela a tela.
