# ADR 0003 — Arquivos cifrados pela aplicação; "URL pré-assinada" é da API

O IA Core precisa do arquivo em claro e o navegador também, mas o armazenamento guarda **só texto cifrado** (AES-256-GCM em segmentos de 1 MiB, DEK por empresa embrulhada pela KEK, AAD = tenant). Em vez de presign do S3, a API emite links `GET /api/v1/files/{token}` assinados por HMAC (60–120 s para o navegador; até 2 h para o IA Core), decifra em streaming e entrega. Vantagem: mesma lógica para S3 e disco, e nenhum objeto legível no bucket. Custo: a banda dos arquivos passa pela API.


## Extensão: o texto lido (OCR) também é cifrado

Cifrar o arquivo e deixar o texto lido dele em claro no banco anula a proteção: o texto tem o CPF inteiro, nomes e endereços. O texto completo do documento, o texto embutido do PDF, as palavras com posição e a análise de cada página (texto e campos) são gravados com a mesma DEK por empresa (`internal/ocrseal`, AES-256-GCM, AAD = finalidade + empresa). Consequência para a busca: o índice `tsvector` não pode ser feito sobre texto cifrado, então é gerado a partir do **texto anonimizado**; a busca por CPF é feita pelo hash cego do funcionário. Os campos estruturados (`campos`, com CPF mascarado) seguem em claro porque alimentam filtros e a conformidade em SQL.
