-- Checklist de conformidade por documento (validade, assinatura, NR-07/NR-06...) calculado pelo IA Core.
ALTER TABLE documents ADD COLUMN checklist jsonb NOT NULL DEFAULT '[]';
CREATE INDEX pages_hash ON pages (tenant_id, hash_sha256) WHERE hash_sha256 IS NOT NULL;
