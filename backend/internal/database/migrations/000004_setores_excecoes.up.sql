-- Setores, exceções por funcionário na obrigatoriedade documental e cadastro de funcionário configurável por empresa.
CREATE TABLE departments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  nome text NOT NULL, descricao text,
  ativo boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, nome)
);
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON departments
  USING (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid OR current_setting('app.bypass', true) = 'on')
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid OR current_setting('app.bypass', true) = 'on');
GRANT SELECT, INSERT, UPDATE, DELETE ON departments TO citadel_app;

ALTER TABLE employees
  ADD COLUMN department_id uuid REFERENCES departments(id) ON DELETE SET NULL,
  ADD COLUMN extra jsonb NOT NULL DEFAULT '{}';       -- campos personalizados definidos pela empresa

-- Obrigatoriedade passa a ter 4 níveis (precedência: funcionário > cargo > setor > todos). No máximo um escopo por linha.
ALTER TABLE requirements
  ADD COLUMN department_id uuid REFERENCES departments(id) ON DELETE CASCADE,
  ADD COLUMN employee_id uuid REFERENCES employees(id) ON DELETE CASCADE;
ALTER TABLE requirements ADD CONSTRAINT requirements_um_escopo CHECK (num_nonnulls(position_id, department_id, employee_id) <= 1);
DROP INDEX requirements_uq;
CREATE UNIQUE INDEX requirements_uq ON requirements (tenant_id,
  coalesce(position_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(department_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid),
  document_type_id, momento);

ALTER TABLE tenants ADD COLUMN config_cadastro jsonb NOT NULL DEFAULT '{
  "campos": {
    "matricula": {"ativo": true,  "obrigatorio": false},
    "admissao":  {"ativo": true,  "obrigatorio": false},
    "cargo":     {"ativo": true,  "obrigatorio": false},
    "setor":     {"ativo": true,  "obrigatorio": false},
    "unidade":   {"ativo": true,  "obrigatorio": false},
    "email":     {"ativo": true,  "obrigatorio": false},
    "telefone":  {"ativo": true,  "obrigatorio": false}
  },
  "personalizados": []
}';
