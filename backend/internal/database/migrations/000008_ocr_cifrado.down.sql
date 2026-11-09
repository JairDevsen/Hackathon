-- Atenção: o texto cifrado NÃO é decifrado de volta para as colunas em claro (a chave não está no banco).
DROP INDEX IF EXISTS documents_tsv;
ALTER TABLE documents DROP COLUMN tsv;
ALTER TABLE documents ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', f_unaccent(coalesce(texto_ocr, '')))) STORED;
CREATE INDEX documents_tsv ON documents USING gin (tsv);
ALTER TABLE documents DROP COLUMN texto_ocr_cifrado;
ALTER TABLE pages DROP COLUMN texto_len, DROP COLUMN palavras_cifradas, DROP COLUMN texto_cifrado;
