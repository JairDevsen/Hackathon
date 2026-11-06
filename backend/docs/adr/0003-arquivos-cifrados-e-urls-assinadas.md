# ADR 0003 — Arquivos cifrados pela aplicação; "URL pré-assinada" é da API

O IA Core precisa do arquivo em claro e o navegador também, mas o armazenamento guarda **só texto cifrado** (AES-256-GCM em segmentos de 1 MiB, DEK por empresa embrulhada pela KEK, AAD = tenant). Em vez de presign do S3, a API emite links `GET /api/v1/files/{token}` assinados por HMAC (60–120 s para o navegador; até 2 h para o IA Core), decifra em streaming e entrega. Vantagem: mesma lógica para S3 e disco, e nenhum objeto legível no bucket. Custo: a banda dos arquivos passa pela API.
