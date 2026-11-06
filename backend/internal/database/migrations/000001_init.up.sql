-- Citadel IA · schema inicial. Toda tabela de negócio tem tenant_id + RLS.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$ SELECT public.unaccent('public.unaccent', $1) $$;

CREATE TABLE plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo text UNIQUE NOT NULL,
  nome text NOT NULL,
  porte text NOT NULL CHECK (porte IN ('PEQUENA','MEDIA','GRANDE')),
  quota_bytes bigint NOT NULL,
  quota_paginas_mes int NOT NULL,
  max_usuarios_rh int,            -- null = ilimitado
  max_funcionarios int,           -- null = ilimitado
  preco_mensal_centavos bigint,   -- null = sob consulta
  ativo boolean NOT NULL DEFAULT true
);

CREATE TABLE tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cnpj text UNIQUE NOT NULL,
  razao_social text NOT NULL,
  nome_fantasia text,
  endereco jsonb NOT NULL DEFAULT '{}',
  porte text NOT NULL CHECK (porte IN ('PEQUENA','MEDIA','GRANDE')),
  plano_id uuid REFERENCES plans(id),
  status text NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO','SUSPENSO','ENCERRADO')),
  dominios_email text[] NOT NULL DEFAULT '{}',
  responsavel_financeiro jsonb NOT NULL DEFAULT '{}',
  quota_bytes bigint NOT NULL,
  quota_paginas_mes int NOT NULL,
  max_usuarios_rh int,
  max_funcionarios int,
  bytes_usados bigint NOT NULL DEFAULT 0,
  limiar_confianca numeric(3,2) NOT NULL DEFAULT 0.75,
  politica_anonimizacao jsonb NOT NULL DEFAULT '{"auditoria_externa":["cpf","nome","endereco","saude"],"suporte":["cpf","nome","endereco","saude"],"exportacao":["cpf","nome"]}',
  dek_wrapped bytea NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  cnpj text, nome text NOT NULL, centro_custo text,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid REFERENCES tenants(id) ON DELETE CASCADE,  -- nulo = Master
  email text NOT NULL,
  nome text NOT NULL,
  role text NOT NULL CHECK (role IN ('MASTER','ADMIN_EMPRESA','RH')),
  perms text[] NOT NULL DEFAULT '{}',
  unit_scope uuid[] NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'CONVIDADO' CHECK (status IN ('CONVIDADO','ATIVO','INATIVO')),
  senha_hash text,
  ultimo_login timestamptz,
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_email_uq ON users (lower(email));

CREATE TABLE user_invites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash text UNIQUE NOT NULL,
  expira_em timestamptz NOT NULL,
  usado_em timestamptz
);

CREATE TABLE sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id uuid,
  familia uuid NOT NULL,
  dispositivo text, ip text,
  criado_em timestamptz NOT NULL DEFAULT now(),
  ultimo_uso timestamptz NOT NULL DEFAULT now(),
  expira_em timestamptz NOT NULL,
  revogado_em timestamptz
);
CREATE TABLE refresh_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  familia uuid NOT NULL,
  hash text UNIQUE NOT NULL,
  usado_em timestamptz,
  expira_em timestamptz NOT NULL,
  revogado_em timestamptz
);

CREATE TABLE positions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  nome text NOT NULL, cbo text, descricao text, segmento text,
  ativo boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, nome)
);

CREATE TABLE document_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  codigo text UNIQUE NOT NULL,
  nome text NOT NULL,
  categoria text NOT NULL,   -- ADMISSAO, MENSAL, SAUDE_SEGURANCA, DISCIPLINAR, DESLIGAMENTO, EMPRESA, OUTROS
  sensivel_saude boolean NOT NULL DEFAULT false,
  escopo text NOT NULL DEFAULT 'FUNCIONARIO' CHECK (escopo IN ('FUNCIONARIO','EMPRESA')),
  validade_padrao_dias int,
  retencao_padrao_dias int NOT NULL DEFAULT 1825
);

CREATE TABLE requirements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  position_id uuid REFERENCES positions(id) ON DELETE CASCADE,  -- nulo = todos
  document_type_id uuid NOT NULL REFERENCES document_types(id),
  momento text NOT NULL CHECK (momento IN ('ADMISSAO','MENSAL','ANUAL','PERIODICO','DESLIGAMENTO','EVENTO')),
  validade_dias int,
  antecedencia_alerta_dias int NOT NULL DEFAULT 30,
  obrigatorio boolean NOT NULL DEFAULT true,
  observacao text
);
CREATE UNIQUE INDEX requirements_uq ON requirements (tenant_id, coalesce(position_id,'00000000-0000-0000-0000-000000000000'::uuid), document_type_id, momento);

CREATE TABLE employees (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  unit_id uuid REFERENCES units(id),
  cpf_cifrado bytea NOT NULL,
  cpf_hash text NOT NULL,
  cpf_mascarado text NOT NULL,
  nome text NOT NULL,
  matricula text,
  cargo_id uuid REFERENCES positions(id),
  admissao date, desligamento date,
  status text NOT NULL DEFAULT 'ATIVO' CHECK (status IN ('ATIVO','AFASTADO','DESLIGADO')),
  email text, telefone text,
  criado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, cpf_hash)
);
CREATE INDEX employees_nome_trgm ON employees USING gin (f_unaccent(lower(nome)) gin_trgm_ops);
CREATE INDEX employees_matricula ON employees (tenant_id, matricula);

CREATE TABLE batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  unit_id uuid REFERENCES units(id),
  enviado_por uuid REFERENCES users(id),
  arquivo_original text NOT NULL,
  storage_key text NOT NULL,
  sha256 text NOT NULL,
  bytes bigint NOT NULL,
  tipo_lote text NOT NULL DEFAULT 'MISTO',
  total_paginas int NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'RECEBIDO' CHECK (status IN ('RECEBIDO','PROCESSANDO','PROCESSADO','PROCESSADO_COM_PENDENCIAS','FALHOU')),
  versao int NOT NULL DEFAULT 1,
  tentativas int NOT NULL DEFAULT 0,
  erro text,
  ia_job_id text,
  resumo jsonb NOT NULL DEFAULT '{}',
  linha_tempo jsonb NOT NULL DEFAULT '[]',
  iniciado_em timestamptz, concluido_em timestamptz,
  heartbeat_em timestamptz NOT NULL DEFAULT now(),
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX batches_sha_uq ON batches (tenant_id, sha256) WHERE status <> 'FALHOU';

CREATE TABLE pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  batch_id uuid NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
  numero int NOT NULL,
  storage_key text NOT NULL, thumb_key text,
  rotacao int NOT NULL DEFAULT 0,
  captura text, hash_sha256 text, texto_embutido text,
  largura int, altura int,
  caixas jsonb NOT NULL DEFAULT '[]',     -- caixas de dados pessoais [x0,y0,x1,y1,rotulo] (relativas)
  palavras jsonb NOT NULL DEFAULT '[]',   -- palavras do OCR [x0,y0,x1,y1,texto] (relativas)
  proc_status text NOT NULL DEFAULT 'PENDENTE' CHECK (proc_status IN ('PENDENTE','PROCESSANDO','OK','FALHOU')),
  analise jsonb,           -- checkpoint da página
  erro text, tentativas int NOT NULL DEFAULT 0,
  processado_em timestamptz,
  UNIQUE (batch_id, numero)
);

CREATE TABLE documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  batch_id uuid REFERENCES batches(id) ON DELETE SET NULL,
  employee_id uuid REFERENCES employees(id) ON DELETE SET NULL,
  unit_id uuid REFERENCES units(id),
  document_type text NOT NULL REFERENCES document_types(codigo),
  titulo text,
  competencia text,            -- YYYY-MM
  data_documento date, validade_ate date,
  paginas int[] NOT NULL,
  confianca numeric(4,3) NOT NULL DEFAULT 0,
  status text NOT NULL CHECK (status IN ('AUTO_APROVADO','AGUARDANDO_REVISAO','REVISADO','REJEITADO','SUBSTITUIDO')),
  campos jsonb NOT NULL DEFAULT '{}',
  alertas jsonb NOT NULL DEFAULT '[]',
  motivos_revisao jsonb NOT NULL DEFAULT '[]',
  nao_conformidades jsonb NOT NULL DEFAULT '[]',
  dados_sensiveis jsonb NOT NULL DEFAULT '[]',
  finops jsonb,
  texto_ocr text NOT NULL DEFAULT '',
  texto_anonimizado text NOT NULL DEFAULT '',
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', f_unaccent(coalesce(texto_ocr,'')))) STORED,
  cpf_extraido_hash text, nome_extraido text,
  nome_arquivo text, pasta_destino text,
  possui_manuscrito boolean NOT NULL DEFAULT false,
  sensivel_saude boolean NOT NULL DEFAULT false,
  versao int NOT NULL DEFAULT 1,
  substitui_id uuid REFERENCES documents(id),
  duplicata_de uuid REFERENCES documents(id),
  retencao_vence_em date,
  criado_em timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX documents_emp ON documents (tenant_id, employee_id, document_type);
CREATE INDEX documents_status ON documents (tenant_id, status);
CREATE INDEX documents_batch ON documents (batch_id);
CREATE INDEX documents_tsv ON documents USING gin (tsv);

CREATE TABLE reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  revisor_id uuid REFERENCES users(id),
  acao text NOT NULL,
  antes jsonb, depois jsonb,
  duracao_ms int,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE compliance_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  employee_id uuid REFERENCES employees(id) ON DELETE CASCADE,  -- nulo = escopo empresa
  requirement_id uuid NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
  referencia text NOT NULL,
  status text NOT NULL CHECK (status IN ('OK','PENDENTE','VENCIDO','A_VENCER','DISPENSADO')),
  vence_em date,
  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  justificativa_dispensa text,
  atualizado_em timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX compliance_uq ON compliance_items (tenant_id, coalesce(employee_id,'00000000-0000-0000-0000-000000000000'::uuid), requirement_id, referencia);
CREATE INDEX compliance_status ON compliance_items (tenant_id, status);

CREATE TABLE storage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  tipo text NOT NULL CHECK (tipo IN ('UPLOAD','DERIVADO','EXCLUSAO','RETENCAO')),
  bytes bigint NOT NULL, objeto text, por uuid,
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE usage_monthly (
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  mes text NOT NULL,
  paginas int NOT NULL DEFAULT 0, bytes_total bigint NOT NULL DEFAULT 0,
  docs int NOT NULL DEFAULT 0, revisoes int NOT NULL DEFAULT 0,
  tokens bigint NOT NULL DEFAULT 0, custo_ia_centavos bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, mes)
);

CREATE TABLE audit_log (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  ator uuid, ator_role text,
  acao text NOT NULL, entidade text, entidade_id text,
  dados jsonb NOT NULL DEFAULT '{}',
  ip text, ua text,
  prev_hash text NOT NULL, hash text NOT NULL,
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_tenant ON audit_log (tenant_id, id DESC);
CREATE OR REPLACE FUNCTION audit_imutavel() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit_log é imutável (somente INSERT)'; END $$;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_imutavel();
CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit_log FOR EACH STATEMENT EXECUTE FUNCTION audit_imutavel();

CREATE TABLE notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,  -- nulo = todos os admins/RH do tenant
  tipo text NOT NULL, titulo text NOT NULL, link text,
  lida_em timestamptz, criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  plano_id uuid NOT NULL REFERENCES plans(id),
  ciclo text NOT NULL DEFAULT 'MENSAL', status text NOT NULL DEFAULT 'ATIVA',
  inicio date NOT NULL DEFAULT current_date
);
CREATE TABLE invoices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  referencia text NOT NULL, valor_centavos bigint, status text NOT NULL DEFAULT 'ABERTA',
  vencimento date, criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE support_access (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  solicitado_por uuid NOT NULL REFERENCES users(id),
  motivo text NOT NULL,
  status text NOT NULL DEFAULT 'PENDENTE' CHECK (status IN ('PENDENTE','APROVADO','NEGADO','REVOGADO')),
  aprovado_por uuid, expira_em timestamptz,
  criado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE retention_policies (
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  document_type_id uuid NOT NULL REFERENCES document_types(id),
  dias int NOT NULL, acao text NOT NULL DEFAULT 'EXCLUIR' CHECK (acao IN ('EXCLUIR','ANONIMIZAR')),
  PRIMARY KEY (tenant_id, document_type_id)
);

CREATE TABLE ia_callbacks (
  chave text PRIMARY KEY, batch_id uuid NOT NULL, recebido_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE dead_letters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  batch_id uuid REFERENCES batches(id) ON DELETE CASCADE,
  tipo text NOT NULL, erro text NOT NULL, tentativas int NOT NULL,
  resolvido_em timestamptz, criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome text NOT NULL, email text NOT NULL, empresa text NOT NULL,
  porte text, funcionarios int, consentimento boolean NOT NULL, ip text,
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE audit_shares (   -- portal de auditoria externa
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  criado_por uuid REFERENCES users(id),
  token_hash text UNIQUE NOT NULL,
  escopo jsonb NOT NULL, expira_em timestamptz NOT NULL, revogado_em timestamptz,
  criado_em timestamptz NOT NULL DEFAULT now()
);

-- ===== RLS: isolamento por empresa (app.tenant_id) ou bypass explícito de sistema/Master =====
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['units','positions','requirements','employees','batches','pages','documents','reviews',
    'compliance_items','storage_events','usage_monthly','audit_log','notifications','subscriptions','invoices',
    'support_access','retention_policies','dead_letters','audit_shares','users'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY tenant_isolation ON %I USING (
        tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid
        OR current_setting('app.bypass', true) = 'on')
      WITH CHECK (
        tenant_id = nullif(current_setting('app.tenant_id', true),'')::uuid
        OR current_setting('app.bypass', true) = 'on')$p$, t);
  END LOOP;
END $$;

-- ===== Permissões do papel da aplicação =====
-- (o papel citadel_app é criado por cmd/migrate antes das migrações)
GRANT USAGE ON SCHEMA public TO citadel_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO citadel_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO citadel_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM citadel_app;
