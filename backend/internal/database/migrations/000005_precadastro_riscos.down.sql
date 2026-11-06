DROP TABLE IF EXISTS risk_indicators;
ALTER TABLE tenants DROP COLUMN IF EXISTS pre_cadastro_automatico;
ALTER TABLE batches DROP COLUMN IF EXISTS dica_funcionario_id, DROP COLUMN IF EXISTS dica_tipo, DROP COLUMN IF EXISTS substitui_documento_id;
ALTER TABLE documents DROP COLUMN IF EXISTS origem;
ALTER TABLE employees DROP COLUMN IF EXISTS pre_cadastro, DROP COLUMN IF EXISTS origem;
