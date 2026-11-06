DROP INDEX IF EXISTS requirements_uq;
DELETE FROM requirements WHERE department_id IS NOT NULL OR employee_id IS NOT NULL;
ALTER TABLE requirements DROP CONSTRAINT IF EXISTS requirements_um_escopo, DROP COLUMN IF EXISTS department_id, DROP COLUMN IF EXISTS employee_id;
CREATE UNIQUE INDEX requirements_uq ON requirements (tenant_id, coalesce(position_id,'00000000-0000-0000-0000-000000000000'::uuid), document_type_id, momento);
ALTER TABLE employees DROP COLUMN IF EXISTS department_id, DROP COLUMN IF EXISTS extra;
ALTER TABLE tenants DROP COLUMN IF EXISTS config_cadastro;
DROP TABLE IF EXISTS departments;
