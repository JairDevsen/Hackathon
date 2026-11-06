-- Pré-cadastro automático, documentos lançados manualmente, dicas de reenvio e indicadores de risco trabalhista.
ALTER TABLE employees
  ADD COLUMN pre_cadastro boolean NOT NULL DEFAULT false,
  ADD COLUMN origem text NOT NULL DEFAULT 'MANUAL' CHECK (origem IN ('MANUAL','IMPORTACAO','PRE_CADASTRO','REVISAO'));
ALTER TABLE documents
  ADD COLUMN origem text NOT NULL DEFAULT 'IA' CHECK (origem IN ('IA','MANUAL'));
ALTER TABLE batches
  ADD COLUMN dica_funcionario_id uuid REFERENCES employees(id) ON DELETE SET NULL,
  ADD COLUMN dica_tipo text,
  ADD COLUMN substitui_documento_id uuid REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE tenants ADD COLUMN pre_cadastro_automatico boolean NOT NULL DEFAULT true;

CREATE TABLE risk_indicators (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id uuid REFERENCES employees(id) ON DELETE CASCADE,   -- nulo = documento da empresa
  document_id uuid REFERENCES documents(id) ON DELETE CASCADE,
  codigo text NOT NULL,
  severidade text NOT NULL CHECK (severidade IN ('ALTO','MEDIO','BAIXO')),
  categoria text NOT NULL,
  titulo text NOT NULL,
  descricao text NOT NULL,
  base_legal text,
  referencia text NOT NULL DEFAULT '',
  status text NOT NULL DEFAULT 'ABERTO' CHECK (status IN ('ABERTO','IGNORADO')),
  justificativa text,
  criado_em timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX risk_uq ON risk_indicators (tenant_id,
  coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(document_id,'00000000-0000-0000-0000-000000000000'::uuid), codigo, referencia);
CREATE INDEX risk_status ON risk_indicators (tenant_id, status, severidade);
ALTER TABLE risk_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_indicators FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON risk_indicators
  USING (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid OR current_setting('app.bypass', true) = 'on')
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid OR current_setting('app.bypass', true) = 'on');
GRANT SELECT, INSERT, UPDATE, DELETE ON risk_indicators TO citadel_app;
