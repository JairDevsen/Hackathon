-- Fornecedores e terceirizadas: o CNPJ lido nos documentos agrupa funcionários, documentos, conformidade e riscos
-- da empresa contratante (responsabilidade subsidiária: TST Súmula 331; Lei 6.019/74 art. 5º-A §5º).
CREATE TABLE suppliers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  cnpj text NOT NULL CHECK (cnpj ~ '^[0-9]{14}$'),
  razao_social text NOT NULL,
  nome_fantasia text,
  tipo text NOT NULL DEFAULT 'TERCEIRIZADA' CHECK (tipo IN ('TERCEIRIZADA','FORNECEDOR')),  -- TERCEIRIZADA tem empregados alocados; FORNECEDOR não
  status text NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO','INATIVO')),
  pre_cadastro boolean NOT NULL DEFAULT false,
  origem text NOT NULL DEFAULT 'MANUAL' CHECK (origem IN ('MANUAL','PRE_CADASTRO','REVISAO')),
  criticidade text NOT NULL DEFAULT 'MEDIA' CHECK (criticidade IN ('BAIXA','MEDIA','ALTA')),
  objeto text,
  contrato_inicio date,
  contrato_fim date,
  responsavel_nome text,
  responsavel_email text,
  criado_em timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, cnpj)
);
CREATE INDEX suppliers_nome_trgm ON suppliers USING gin (f_unaccent(lower(razao_social)) gin_trgm_ops);
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppliers FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON suppliers
  USING (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid OR current_setting('app.bypass', true) = 'on')
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid OR current_setting('app.bypass', true) = 'on');
GRANT SELECT, INSERT, UPDATE, DELETE ON suppliers TO citadel_app;

-- quem é o empregador (nulo = a própria empresa) e de quem é cada documento
ALTER TABLE employees ADD COLUMN supplier_id uuid REFERENCES suppliers(id) ON DELETE SET NULL;
ALTER TABLE documents ADD COLUMN supplier_id uuid REFERENCES suppliers(id) ON DELETE SET NULL;
CREATE INDEX employees_supplier ON employees (tenant_id, supplier_id);
CREATE INDEX documents_supplier ON documents (tenant_id, supplier_id, document_type);

-- conformidade e riscos por fornecedor
ALTER TABLE compliance_items ADD COLUMN supplier_id uuid REFERENCES suppliers(id) ON DELETE CASCADE;
DROP INDEX compliance_uq;
CREATE UNIQUE INDEX compliance_uq ON compliance_items (tenant_id,
  coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(supplier_id,'00000000-0000-0000-0000-000000000000'::uuid), requirement_id, referencia);
ALTER TABLE risk_indicators ADD COLUMN supplier_id uuid REFERENCES suppliers(id) ON DELETE CASCADE;
DROP INDEX risk_uq;
CREATE UNIQUE INDEX risk_uq ON risk_indicators (tenant_id,
  coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(supplier_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(document_id,'00000000-0000-0000-0000-000000000000'::uuid), codigo, referencia);

-- documentos que revelam risco para a contratante (além dos já existentes: CRF, CNDT, CND, guias, contrato)
INSERT INTO document_types (codigo, nome, categoria, sensivel_saude, escopo, validade_padrao_dias, retencao_padrao_dias) VALUES
 ('APOLICE_SEGURO','Apólice de seguro (responsabilidade civil / vida em grupo)','EMPRESA',false,'EMPRESA',365,1825),
 ('AUTO_INFRACAO','Auto de infração ou notificação de fiscalização','EMPRESA',false,'EMPRESA',NULL,7300),
 ('PROCESSO_JUDICIAL','Citação ou processo judicial (trabalhista)','EMPRESA',false,'EMPRESA',NULL,7300),
 ('RELATORIO_AUDITORIA','Relatório de auditoria ou diligência do fornecedor','EMPRESA',false,'EMPRESA',NULL,1825);

