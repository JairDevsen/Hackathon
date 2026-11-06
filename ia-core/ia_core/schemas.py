"""Schemas Pydantic dos campos extraídos por tipo (viram o JSON Schema do formulário de revisão)."""
from typing import Dict, List, Optional, Type
from pydantic import BaseModel, Field


class CamposBase(BaseModel):
    cpf: Optional[str] = Field(None, description="CPF do titular (somente dígitos ou com máscara)")
    nome: Optional[str] = Field(None, description="Nome completo do titular")
    matricula: Optional[str] = Field(None, description="Matrícula do funcionário")
    competencia: Optional[str] = Field(None, description="Competência AAAA-MM")
    data_documento: Optional[str] = Field(None, description="Data do documento (AAAA-MM-DD)")
    validade_ate: Optional[str] = Field(None, description="Validade (AAAA-MM-DD)")
    empresa_nome: Optional[str] = Field(None, description="Empresa do documento (empregador, terceirizada ou fornecedora)")
    empresa_cnpj: Optional[str] = Field(None, description="CNPJ da empresa do documento (somente dígitos); agrupa os documentos por fornecedor")


class CamposAR(CamposBase):
    codigo_rastreio: Optional[str] = None
    remetente: Optional[str] = None
    destinatario: Optional[str] = None
    endereco_entrega: Optional[str] = None
    data_entrega_manuscrita: Optional[str] = None
    nome_recebedor_manuscrito: Optional[str] = None
    documento_recebedor_manuscrito: Optional[str] = None
    assinatura_detectada: Optional[bool] = None


class CamposHolerite(CamposBase):
    empregador: Optional[str] = None
    pagamento_horas_extras: Optional[str] = Field(None, description="Valor de horas extras pago no mês (R$)")
    salario_base: Optional[str] = None
    liquido_a_receber: Optional[str] = None
    fgts_depositado: Optional[str] = None
    fgts_devido: Optional[str] = None


class CamposPonto(CamposBase):
    jornada_diaria: Optional[str] = Field(None, description="Jornada diária HH:MM")
    horas_extras_total: Optional[str] = Field(None, description="Total de horas extras no mês HH:MM")
    intervalo: Optional[str] = Field(None, description="Intervalo HH:MM")
    horas_extras: Optional[str] = None


class CamposASO(CamposBase):
    tipo_exame: Optional[str] = Field(None, description="admissional, periódico, demissional...")
    resultado: Optional[str] = Field(None, description="APTO ou INAPTO")
    medico_crm: Optional[str] = None


class CamposTreinamento(CamposBase):
    norma: Optional[str] = Field(None, description="NR-10, NR-35...")
    carga_horaria: Optional[str] = None


class CamposCertidao(CamposBase):
    cnpj: Optional[str] = None
    numero: Optional[str] = None


class CamposCNH(CamposBase):
    numero_registro: Optional[str] = None
    categoria: Optional[str] = None


class CamposRG(CamposBase):
    numero_rg: Optional[str] = Field(None, description="Número do RG")
    orgao_emissor: Optional[str] = None
    data_nascimento: Optional[str] = Field(None, description="AAAA-MM-DD")


class CamposEPI(CamposBase):
    certificado_aprovacao: Optional[str] = Field(None, description="Número do CA do equipamento")
    equipamentos: Optional[str] = Field(None, description="EPIs entregues")
    assinatura_detectada: Optional[bool] = None


class CamposAtestado(CamposBase):
    cid: Optional[str] = None
    dias_afastamento: Optional[str] = None
    medico_crm: Optional[str] = None


class CamposContratoTrabalho(CamposBase):
    cargo: Optional[str] = None
    salario: Optional[str] = None
    data_admissao: Optional[str] = Field(None, description="AAAA-MM-DD")
    assinatura_detectada: Optional[bool] = None


class CamposTRCT(CamposBase):
    data_desligamento: Optional[str] = Field(None, description="AAAA-MM-DD")
    motivo: Optional[str] = None
    valor_liquido: Optional[str] = None
    assinatura_detectada: Optional[bool] = None


class CamposFerias(CamposBase):
    periodo_aquisitivo: Optional[str] = None
    inicio_gozo: Optional[str] = Field(None, description="AAAA-MM-DD")
    dias: Optional[str] = None
    assinatura_detectada: Optional[bool] = None


class CamposApolice(CamposBase):
    seguradora: Optional[str] = None
    numero_apolice: Optional[str] = None
    cobertura: Optional[str] = Field(None, description="Responsabilidade civil, vida em grupo, acidentes pessoais...")
    vigencia_inicio: Optional[str] = Field(None, description="AAAA-MM-DD")
    valor_segurado: Optional[str] = None


class CamposAutoInfracao(CamposBase):
    orgao_autuante: Optional[str] = Field(None, description="MTE, MPT, Receita, Prefeitura...")
    numero_auto: Optional[str] = None
    infracoes: Optional[str] = Field(None, description="Resumo das infrações apontadas")
    valor_multa: Optional[str] = None


class CamposProcesso(CamposBase):
    numero_processo: Optional[str] = None
    vara_tribunal: Optional[str] = None
    reclamante: Optional[str] = None
    reclamada: Optional[str] = None
    valor_causa: Optional[str] = None
    contratante_citada: Optional[bool] = Field(None, description="A empresa contratante figura como responsável subsidiária?")


class CamposAuditoria(CamposBase):
    auditor: Optional[str] = None
    escopo: Optional[str] = None
    achados: Optional[str] = Field(None, description="Não conformidades e riscos apontados")
    nivel_risco: Optional[str] = Field(None, description="BAIXO, MEDIO ou ALTO")


class CamposComprovantePagamento(CamposBase):
    banco: Optional[str] = None
    data_pagamento: Optional[str] = Field(None, description="AAAA-MM-DD")
    valor: Optional[str] = Field(None, description="Valor pago (R$)")
    pagador_nome: Optional[str] = None
    pagador_documento: Optional[str] = Field(None, description="CPF/CNPJ do pagador")
    favorecido_nome: Optional[str] = None
    favorecido_documento: Optional[str] = Field(None, description="CPF/CNPJ do favorecido")
    finalidade: Optional[str] = Field(None, description="Ex.: pagamento de salário 10/2026")
    autenticacao: Optional[str] = Field(None, description="ID da transação / autenticação bancária")


class CamposNotificacao(CamposBase):
    assunto: Optional[str] = Field(None, description="Ex.: ausência ao trabalho, convocação para retorno")
    prazo_dias: Optional[str] = Field(None, description="Prazo para resposta, em dias")


class CamposDeclaracaoManuscrita(CamposBase):
    assunto: Optional[str] = Field(None, description="Residência, dependentes, não acúmulo de emprego...")
    endereco: Optional[str] = None


class CamposReciboAvulso(CamposBase):
    tipo_pagamento: Optional[str] = Field(None, description="Adiantamento, vale, diária...")
    valor: Optional[str] = Field(None, description="Valor (R$)")
    valor_por_extenso: Optional[str] = None
    recebedor_nome: Optional[str] = None
    pagador_nome: Optional[str] = None
    referente_a: Optional[str] = None


class CamposJustificativaFalta(CamposBase):
    tipo_ocorrencia: Optional[str] = Field(None, description="Falta ou atraso")
    data_ocorrencia: Optional[str] = Field(None, description="AAAA-MM-DD")
    motivo: Optional[str] = None
    visto_chefia_presente: Optional[bool] = None


class CamposDependentes(CamposBase):
    dependentes: Optional[str] = Field(None, description="Nome e parentesco de cada dependente")
    quantidade: Optional[str] = None


class CamposChecklistIntegracao(CamposBase):
    itens_marcados: Optional[str] = Field(None, description="Itens do checklist marcados")
    assinatura_responsavel_presente: Optional[bool] = None


class CamposTermoResponsabilidade(CamposBase):
    itens_entregues: Optional[str] = Field(None, description="Ferramentas, uniforme, crachá e quantidades")


class CamposOcorrencia(CamposBase):
    tipo: Optional[str] = Field(None, description="ACIDENTE ou QUASE_ACIDENTE")
    data_ocorrencia: Optional[str] = Field(None, description="AAAA-MM-DD")
    hora: Optional[str] = None
    local: Optional[str] = None
    descricao: Optional[str] = None
    houve_afastamento: Optional[bool] = None
    testemunha_nome: Optional[str] = None


SCHEMAS: Dict[str, Type[BaseModel]] = {
    "COMPROVANTE_PAGAMENTO": CamposComprovantePagamento, "NOTIFICACAO_EMPREGADO": CamposNotificacao, "DECLARACAO_MANUSCRITA": CamposDeclaracaoManuscrita,
    "RECIBO_AVULSO": CamposReciboAvulso, "JUSTIFICATIVA_FALTA": CamposJustificativaFalta, "DECLARACAO_DEPENDENTES": CamposDependentes,
    "CHECKLIST_INTEGRACAO": CamposChecklistIntegracao, "TERMO_RESPONSABILIDADE": CamposTermoResponsabilidade, "CAT_ACIDENTE": CamposOcorrencia,
    "APOLICE_SEGURO": CamposApolice, "AUTO_INFRACAO": CamposAutoInfracao, "PROCESSO_JUDICIAL": CamposProcesso, "RELATORIO_AUDITORIA": CamposAuditoria,
    "CNH": CamposCNH, "RG": CamposRG, "FICHA_EPI": CamposEPI, "ATESTADO_MEDICO": CamposAtestado,
    "CONTRATO_TRABALHO": CamposContratoTrabalho, "FICHA_REGISTRO": CamposContratoTrabalho, "TRCT": CamposTRCT, "RECIBO_FERIAS": CamposFerias,
    "AVISO_RECEBIMENTO": CamposAR,
    "HOLERITE": CamposHolerite,
    "CARTAO_PONTO": CamposPonto,
    "ASO": CamposASO,
    "TREINAMENTO_NR": CamposTreinamento,
    "CRF_FGTS": CamposCertidao, "CNDT": CamposCertidao, "CND_FEDERAL": CamposCertidao,
}


def schema_do_tipo(tipo: str) -> dict:
    return SCHEMAS.get(tipo, CamposBase).model_json_schema()
