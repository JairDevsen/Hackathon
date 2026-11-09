-- Tipos documentais descobertos pela IA: o catálogo passa a registrar a origem (curado ou criado pela IA) e as frases que identificam o tipo,
-- que o IA Core reaprende como pistas locais (Camada 1, custo zero).
ALTER TABLE document_types
  ADD COLUMN origem text NOT NULL DEFAULT 'CATALOGO' CHECK (origem IN ('CATALOGO','IA')),
  ADD COLUMN pistas text[] NOT NULL DEFAULT '{}',
  ADD COLUMN criado_em timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN revisado_em timestamptz;  -- quando o Master confirmou o tipo criado pela IA (a origem continua IA: as pistas aprendidas seguem valendo)

-- tipos comuns de admissão e de documentação de terceirizadas que o catálogo ainda não cobria
INSERT INTO document_types (codigo, nome, categoria, sensivel_saude, escopo, validade_padrao_dias, retencao_padrao_dias) VALUES
 ('CPF_CARTAO','CPF (comprovante)','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('TITULO_ELEITOR','Título de eleitor','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('CERTIDAO_CIVIL','Certidão de nascimento ou casamento','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('COMPROVANTE_ESCOLARIDADE','Comprovante de escolaridade','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('CERTIFICADO_RESERVISTA','Certificado de reservista','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('ACORDO_JORNADA','Acordo de compensação / banco de horas','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('NOTA_FISCAL','Nota fiscal / NFS-e','EMPRESA',false,'EMPRESA',NULL,1825),
 ('CARTAO_CNPJ','Cartão CNPJ','EMPRESA',false,'EMPRESA',NULL,1825),
 ('CONTRATO_SOCIAL','Contrato social / alteração contratual','EMPRESA',false,'EMPRESA',NULL,1825),
 ('GUIA_INSS','Guia de INSS (GPS / DAE eSocial)','EMPRESA',false,'EMPRESA',NULL,1825),
 ('PROGRAMA_SST','PGR / LTCAT / laudo de SST','EMPRESA',false,'EMPRESA',365,1825),
 ('PROTOCOLO_ENTREGA','Capa / protocolo de documentação mensal','EMPRESA',false,'EMPRESA',NULL,1825),
 ('OFICIO','Ofício / comunicado da empresa','EMPRESA',false,'EMPRESA',NULL,1825),
 ('ALVARA_LICENCA','Alvará / licença de funcionamento','EMPRESA',false,'EMPRESA',365,1825);
