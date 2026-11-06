-- Tipos de RH que o gerador de documentos fictícios produz e que o catálogo ainda não cobria.
INSERT INTO document_types (codigo, nome, categoria, sensivel_saude, escopo, validade_padrao_dias, retencao_padrao_dias) VALUES
 ('COMPROVANTE_PAGAMENTO','Comprovante de pagamento','MENSAL',false,'FUNCIONARIO',NULL,1825),
 ('NOTIFICACAO_EMPREGADO','Notificação ao empregado','DISCIPLINAR',false,'FUNCIONARIO',NULL,1825),
 ('DECLARACAO_MANUSCRITA','Declaração manuscrita','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('RECIBO_AVULSO','Recibo avulso (adiantamento, vale, diária)','MENSAL',false,'FUNCIONARIO',NULL,1825),
 ('JUSTIFICATIVA_FALTA','Justificativa de falta','DISCIPLINAR',false,'FUNCIONARIO',NULL,1825),
 ('DECLARACAO_DEPENDENTES','Declaração de dependentes','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('CHECKLIST_INTEGRACAO','Checklist de integração','ADMISSAO',false,'FUNCIONARIO',NULL,1825),
 ('TERMO_RESPONSABILIDADE','Termo de responsabilidade','ADMISSAO',false,'FUNCIONARIO',NULL,1825);
