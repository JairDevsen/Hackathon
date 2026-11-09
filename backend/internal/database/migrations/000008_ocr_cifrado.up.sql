-- O texto lido por OCR (CPF inteiro, nomes, endereços) passa a ser gravado cifrado com a chave de dados da empresa.
-- As colunas antigas em claro continuam existindo só para ler linhas anteriores; o aplicativo deixa de gravar nelas e a
-- rotina de migração dos dados (ocrseal.Backfill, executada na subida da API) cifra e limpa o que já existia.

ALTER TABLE pages
  ADD COLUMN texto_cifrado bytea,           -- texto embutido no PDF
  ADD COLUMN palavras_cifradas bytea,       -- palavras com posição (JSON)
  ADD COLUMN texto_len integer NOT NULL DEFAULT 0;  -- tamanho do texto embutido (saber se a página tem camada de texto, sem abrir)

ALTER TABLE documents ADD COLUMN texto_ocr_cifrado bytea;

-- A busca em texto completo não pode indexar o OCR em claro (o índice conteria CPF e nomes). Passa a usar o texto
-- anonimizado: CPF, CNPJ, nome, endereço e demais dados pessoais detectados já saem substituídos por máscaras.
DROP INDEX IF EXISTS documents_tsv;
ALTER TABLE documents DROP COLUMN tsv;
ALTER TABLE documents ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', f_unaccent(coalesce(texto_anonimizado, '')))) STORED;
CREATE INDEX documents_tsv ON documents USING gin (tsv);
