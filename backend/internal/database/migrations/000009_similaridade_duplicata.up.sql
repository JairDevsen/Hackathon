-- Limite de similaridade (texto lido por OCR) a partir do qual dois documentos do mesmo tipo e da mesma pessoa/empresa são
-- considerados o MESMO documento escaneado de formas diferentes. Padrão 85%; o cliente ajusta, nunca abaixo de 70%.
ALTER TABLE tenants ADD COLUMN similaridade_duplicata numeric(3,2) NOT NULL DEFAULT 0.85 CHECK (similaridade_duplicata BETWEEN 0.70 AND 1.00);
