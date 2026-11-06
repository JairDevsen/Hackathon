DELETE FROM document_types WHERE codigo IN ('APOLICE_SEGURO','AUTO_INFRACAO','PROCESSO_JUDICIAL','RELATORIO_AUDITORIA');
DROP INDEX IF EXISTS risk_uq;
CREATE UNIQUE INDEX risk_uq ON risk_indicators (tenant_id,
  coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(document_id,'00000000-0000-0000-0000-000000000000'::uuid), codigo, referencia);
ALTER TABLE risk_indicators DROP COLUMN IF EXISTS supplier_id;
DROP INDEX IF EXISTS compliance_uq;
CREATE UNIQUE INDEX compliance_uq ON compliance_items (tenant_id, coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid), requirement_id, referencia);
ALTER TABLE compliance_items DROP COLUMN IF EXISTS supplier_id;
ALTER TABLE documents DROP COLUMN IF EXISTS supplier_id;
ALTER TABLE employees DROP COLUMN IF EXISTS supplier_id;
DROP TABLE IF EXISTS suppliers;
