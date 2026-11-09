"""Schemas Pydantic usados como `response_schema` do Gemini.

Regras para o schema funcionar bem com o Gemini:
- Sem valores default nos campos (todos obrigatórios; use `X | None` para "pode faltar").
- Sem `dict` livre; use listas de objetos.
- Descrições curtas em `Field(description=...)`: o modelo lê e usa como instrução.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tipos de documento (comece com os mais frequentes; o resto cai em OUTRO)
# ---------------------------------------------------------------------------
class TipoDocumento(str, Enum):
    HOLERITE = "HOLERITE"
    CARTAO_PONTO = "CARTAO_PONTO"
    GUIA_FGTS = "GUIA_FGTS"
    CRF_FGTS = "CRF_FGTS"
    CNDT = "CNDT"
    CND_FEDERAL = "CND_FEDERAL"
    TRCT = "TRCT"
    ASO = "ASO"
    FICHA_EPI = "FICHA_EPI"
    COMPROVANTE_PAGAMENTO = "COMPROVANTE_PAGAMENTO"
    AVISO_RECEBIMENTO = "AVISO_RECEBIMENTO"
    NOTIFICACAO_EMPREGADO = "NOTIFICACAO_EMPREGADO"
    PEDIDO_DEMISSAO = "PEDIDO_DEMISSAO"
    ATESTADO_MEDICO = "ATESTADO_MEDICO"
    DECLARACAO_MANUSCRITA = "DECLARACAO_MANUSCRITA"
    RECIBO_AVULSO = "RECIBO_AVULSO"
    JUSTIFICATIVA_FALTA = "JUSTIFICATIVA_FALTA"
    ADVERTENCIA_SUSPENSAO = "ADVERTENCIA_SUSPENSAO"
    CTPS_ANOTACAO = "CTPS_ANOTACAO"
    FICHA_REGISTRO = "FICHA_REGISTRO"
    LISTA_PRESENCA = "LISTA_PRESENCA"
    ORDEM_SERVICO_SST = "ORDEM_SERVICO_SST"
    DECLARACAO_VALE_TRANSPORTE = "DECLARACAO_VALE_TRANSPORTE"
    DECLARACAO_DEPENDENTES = "DECLARACAO_DEPENDENTES"
    RECIBO_BENEFICIO = "RECIBO_BENEFICIO"
    FERIAS = "FERIAS"
    CHECKLIST_INTEGRACAO = "CHECKLIST_INTEGRACAO"
    TERMO_RESPONSABILIDADE = "TERMO_RESPONSABILIDADE"
    OCORRENCIA_ACIDENTE = "OCORRENCIA_ACIDENTE"
    CONTRATO_TRABALHO = "CONTRATO_TRABALHO"
    DARF = "DARF"
    OUTRO = "OUTRO"


# Pistas visuais de cada tipo: entram no prompt de classificação.
DESCRICAO_TIPOS: dict[TipoDocumento, str] = {
    TipoDocumento.HOLERITE: "Recibo/demonstrativo de pagamento de salário (contracheque). Colunas de código, descrição, referência, vencimentos/proventos e descontos; base FGTS/INSS; valor líquido.",
    TipoDocumento.CARTAO_PONTO: "Cartão/espelho/folha de ponto. Tabela diária com datas e horários de entrada, saída e intervalo; pode ser manuscrito, cartão mecânico ou relatório de REP eletrônico.",
    TipoDocumento.GUIA_FGTS: "Guia do FGTS Digital (GFD) ou guia/boleto de recolhimento de FGTS, com competência, valor e identificador; pode trazer autenticação bancária.",
    TipoDocumento.CRF_FGTS: "Certificado de Regularidade do FGTS (CRF) emitido pela Caixa, com validade e número de certificação.",
    TipoDocumento.CNDT: "Certidão Negativa (ou Positiva) de Débitos Trabalhistas emitida pela Justiça do Trabalho/TST.",
    TipoDocumento.CND_FEDERAL: "Certidão de débitos relativos a créditos tributários federais e dívida ativa da União (Receita Federal/PGFN).",
    TipoDocumento.TRCT: "Termo de Rescisão do Contrato de Trabalho (ou Termo de Quitação/Homologação), com causa do afastamento, verbas rescisórias e deduções.",
    TipoDocumento.ASO: "Atestado de Saúde Ocupacional: tipo de exame (admissional, periódico, demissional etc.), riscos, médico/CRM e conclusão apto/inapto.",
    TipoDocumento.FICHA_EPI: "Ficha de controle de entrega de Equipamento de Proteção Individual, com datas, itens, número do CA e assinatura do empregado.",
    TipoDocumento.COMPROVANTE_PAGAMENTO: "Comprovante bancário de transferência/PIX/TED/pagamento (ex.: comprovante de salário ou de quitação de guia).",
    TipoDocumento.AVISO_RECEBIMENTO: "Aviso de Recebimento (AR) postal: cartão com destinatário, remetente, código do objeto, tentativas de entrega, motivos de devolução, data, nome e assinatura do recebedor e carimbo da unidade de entrega.",
    TipoDocumento.NOTIFICACAO_EMPREGADO: "Carta/notificação da empresa ao empregado (convocação para retorno, abandono de emprego, comunicado), normalmente enviada com AR.",
    TipoDocumento.PEDIDO_DEMISSAO: "Carta de próprio punho do empregado pedindo demissão ('venho por meio desta solicitar meu desligamento...'), com data e assinatura.",
    TipoDocumento.ATESTADO_MEDICO: "Atestado médico em receituário de clínica/consultório: texto manuscrito com dias de afastamento, carimbo e CRM do médico.",
    TipoDocumento.DECLARACAO_MANUSCRITA: "Declaração de próprio punho do empregado (residência, dependentes, não acúmulo de emprego ou outra), com data e assinatura.",
    TipoDocumento.RECIBO_AVULSO: "Recibo simples (bloco ou folha) de adiantamento, vale ou diária: 'Recebi de ... a quantia de R$ ...', valor por extenso e assinatura.",
    TipoDocumento.JUSTIFICATIVA_FALTA: "Justificativa de falta ou atraso escrita pelo empregado ou em formulário, com data da ocorrência, motivo e visto da chefia.",
    TipoDocumento.ADVERTENCIA_SUSPENSAO: "Advertência ou suspensão disciplinar (impressa ou manuscrita) com motivo, ciência do empregado ('Estou ciente' ou 'Recuso-me a assinar') e testemunhas.",
    TipoDocumento.CTPS_ANOTACAO: "Página pequena de carteira de trabalho física (layout genérico) com anotações de contrato, alteração salarial ou férias e carimbo da empresa.",
    TipoDocumento.FICHA_REGISTRO: "Ficha ou folha de livro de registro de empregado, com espaço de foto 3x4, dados pessoais, admissão, cargo e salário.",
    TipoDocumento.LISTA_PRESENCA: "Lista de presença de treinamento (NR), com tema, data, instrutor e linhas de participantes com nome, CPF e assinatura.",
    TipoDocumento.ORDEM_SERVICO_SST: "Ordem de serviço de segurança e saúde do trabalho (NR-1) descrevendo riscos e medidas da função, com ciência assinada.",
    TipoDocumento.DECLARACAO_VALE_TRANSPORTE: "Declaração de opção ou renúncia ao vale-transporte, com endereço residencial e linhas de ônibus utilizadas.",
    TipoDocumento.DECLARACAO_DEPENDENTES: "Declaração de dependentes para salário-família/IRRF com nomes, parentesco e datas de nascimento.",
    TipoDocumento.RECIBO_BENEFICIO: "Recibo de entrega de vale-transporte, vale-refeição ou vale-alimentação, com competência, quantidade, valor e assinatura.",
    TipoDocumento.FERIAS: "Aviso de férias ou recibo de férias (bloco de formulário), com período aquisitivo, período de gozo, valores e assinatura.",
    TipoDocumento.CHECKLIST_INTEGRACAO: "Check-list de integração ou liberação de acesso do empregado, com itens marcados e assinaturas.",
    TipoDocumento.TERMO_RESPONSABILIDADE: "Termo de responsabilidade por ferramentas, uniforme, crachá ou equipamentos entregues ao empregado.",
    TipoDocumento.OCORRENCIA_ACIDENTE: "Ficha/relato de ocorrência de acidente ou quase-acidente (rascunho que antecede a CAT), com data, hora, local, descrição e testemunha.",
    TipoDocumento.CONTRATO_TRABALHO: "Contrato individual de trabalho (experiência ou prazo indeterminado), várias páginas com cláusulas, rubricas e assinaturas.",
    TipoDocumento.DARF: "Documento de arrecadação de tributos federais (DARF/DCTFWeb) com período de apuração, código da receita, valor e eventual autenticação ou anotação 'pago em'.",
    TipoDocumento.OUTRO: "Qualquer documento que não se encaixe claramente nos tipos acima, páginas em branco ou capas.",
}


# ---------------------------------------------------------------------------
# Etapa 1: separação + classificação (rótulo por página)
# ---------------------------------------------------------------------------
class RotuloPagina(BaseModel):
    pagina: int = Field(description="Número da página, exatamente como no rótulo 'PÁGINA N' que precede a imagem.")
    tipo: TipoDocumento
    inicia_documento: bool = Field(description="true se esta página é a primeira de um novo documento; false se continua o documento da página anterior.")
    multiplos_documentos: bool = Field(description="true se a mesma imagem contém mais de um documento distinto (ex.: dois holerites lado a lado).")
    legivel: bool = Field(description="false se a página está cortada, borrada ou ilegível a ponto de impedir a leitura dos dados principais.")
    confianca: float = Field(description="Confiança na classificação, de 0.0 a 1.0.")
    justificativa: str = Field(description="Até 15 palavras com os elementos visuais que definiram o tipo.")


class ResultadoClassificacao(BaseModel):
    paginas: list[RotuloPagina]


# ---------------------------------------------------------------------------
# Etapa 2: extração por tipo
# ---------------------------------------------------------------------------
class _Controle(BaseModel):
    campos_ilegiveis: list[str] = Field(description="Nomes dos campos que existem no documento mas não puderam ser lidos com segurança.")
    observacoes: str | None = Field(description="Rasuras, carimbos, divergências ou outras observações relevantes. null se nada a observar.")


class _Empregador(BaseModel):
    empregador_razao_social: str | None
    empregador_cnpj: str | None = Field(description="Somente dígitos (14).")


class _Empregado(BaseModel):
    empregado_nome: str | None
    empregado_cpf: str | None = Field(description="Somente dígitos (11).")


# --- Holerite ---------------------------------------------------------------
class ItemHolerite(BaseModel):
    codigo: str | None
    descricao: str
    referencia: str | None = Field(description="Quantidade/percentual/horas da coluna referência, como texto.")
    provento: float | None
    desconto: float | None


class Holerite(_Controle, _Empregador, _Empregado):
    matricula: str | None
    cargo: str | None
    competencia: str | None = Field(description="Mês de referência no formato AAAA-MM.")
    salario_base: float | None
    itens: list[ItemHolerite]
    total_proventos: float | None
    total_descontos: float | None
    valor_liquido: float | None
    base_calculo_inss: float | None
    base_calculo_fgts: float | None
    valor_fgts_mes: float | None
    assinatura_empregado_presente: bool


# --- Cartão de ponto --------------------------------------------------------
class RegistroPonto(BaseModel):
    data: str = Field(description="AAAA-MM-DD.")
    marcacoes: list[str] = Field(description="Horários na ordem em que aparecem, formato HH:MM (entrada, saída intervalo, retorno, saída...).")
    ocorrencia: str | None = Field(description="Folga, falta, feriado, atestado, férias etc. null se dia normal.")


class CartaoPonto(_Controle, _Empregador, _Empregado):
    matricula: str | None
    periodo_inicio: str | None = Field(description="AAAA-MM-DD.")
    periodo_fim: str | None = Field(description="AAAA-MM-DD.")
    forma_registro: str | None = Field(description="MANUAL, MECANICO ou ELETRONICO.")
    registros: list[RegistroPonto]
    assinatura_empregado_presente: bool


# --- Guia FGTS --------------------------------------------------------------
class GuiaFGTS(_Controle, _Empregador):
    anotacao_manuscrita: str | None = Field(description="Anotação feita à mão na guia (ex.: 'pago em 18/10'). null se não houver.")
    identificador_guia: str | None
    competencia: str | None = Field(description="AAAA-MM.")
    data_vencimento: str | None = Field(description="AAAA-MM-DD.")
    valor_total: float | None
    data_pagamento: str | None = Field(description="AAAA-MM-DD, se houver autenticação/comprovante de pagamento.")
    autenticacao_bancaria_presente: bool


# --- Certidões (CRF, CNDT, CND) --------------------------------------------
class SituacaoCertidao(str, Enum):
    NEGATIVA = "NEGATIVA"
    POSITIVA = "POSITIVA"
    POSITIVA_COM_EFEITO_DE_NEGATIVA = "POSITIVA_COM_EFEITO_DE_NEGATIVA"
    REGULAR = "REGULAR"
    IRREGULAR = "IRREGULAR"
    NAO_IDENTIFICADA = "NAO_IDENTIFICADA"


class Certidao(_Controle, _Empregador):
    numero_certidao: str | None
    data_emissao: str | None = Field(description="AAAA-MM-DD.")
    data_validade: str | None = Field(description="AAAA-MM-DD.")
    situacao: SituacaoCertidao
    codigo_controle: str | None


# --- TRCT -------------------------------------------------------------------
class TRCT(_Controle, _Empregador, _Empregado):
    empregado_pis: str | None = Field(description="Somente dígitos.")
    data_admissao: str | None = Field(description="AAAA-MM-DD.")
    data_aviso_previo: str | None = Field(description="AAAA-MM-DD.")
    data_afastamento: str | None = Field(description="AAAA-MM-DD.")
    causa_afastamento: str | None
    codigo_afastamento: str | None
    remuneracao_fins_rescisorios: float | None
    total_bruto: float | None
    total_deducoes: float | None
    valor_liquido: float | None
    assinatura_empregado_presente: bool
    assinatura_empregador_presente: bool


# --- ASO --------------------------------------------------------------------
class TipoExameASO(str, Enum):
    ADMISSIONAL = "ADMISSIONAL"
    PERIODICO = "PERIODICO"
    RETORNO_AO_TRABALHO = "RETORNO_AO_TRABALHO"
    MUDANCA_DE_RISCO = "MUDANCA_DE_RISCO"
    DEMISSIONAL = "DEMISSIONAL"
    NAO_IDENTIFICADO = "NAO_IDENTIFICADO"


class ASO(_Controle, _Empregador, _Empregado):
    funcao: str | None
    tipo_exame: TipoExameASO
    data_exame: str | None = Field(description="AAAA-MM-DD.")
    riscos_ocupacionais: list[str]
    conclusao: str | None = Field(description="APTO ou INAPTO.")
    medico_nome: str | None
    medico_crm: str | None


# --- Ficha de EPI -----------------------------------------------------------
class EntregaEPI(BaseModel):
    data: str | None = Field(description="AAAA-MM-DD.")
    descricao: str
    quantidade: int | None
    numero_ca: str | None = Field(description="Número do Certificado de Aprovação, somente dígitos.")


class FichaEPI(_Controle, _Empregador, _Empregado):
    funcao: str | None
    entregas: list[EntregaEPI]
    assinatura_empregado_presente: bool


# --- Comprovante bancário ---------------------------------------------------
class ComprovantePagamento(_Controle):
    banco: str | None
    data_pagamento: str | None = Field(description="AAAA-MM-DD.")
    valor: float | None
    pagador_nome: str | None
    pagador_documento: str | None = Field(description="CPF/CNPJ somente dígitos.")
    favorecido_nome: str | None
    favorecido_documento: str | None = Field(description="CPF/CNPJ somente dígitos.")
    finalidade: str | None
    autenticacao: str | None


# --- Aviso de Recebimento (AR) -------------------------------------------
class TentativaEntrega(BaseModel):
    data: str | None = Field(description="AAAA-MM-DD.")
    hora: str | None = Field(description="HH:MM.")


class AvisoRecebimento(_Controle):
    codigo_objeto: str | None
    conteudo: str | None = Field(description="Conteúdo/documento declarado no AR (ex.: 'Notificação nº 12/2026').")
    data_postagem: str | None = Field(description="AAAA-MM-DD.")
    unidade_postagem: str | None
    destinatario_nome: str | None
    destinatario_endereco: str | None = Field(description="Logradouro e número.")
    destinatario_bairro: str | None
    destinatario_municipio: str | None
    destinatario_uf: str | None
    destinatario_cep: str | None = Field(description="Somente dígitos (8).")
    remetente_nome: str | None
    remetente_endereco: str | None
    remetente_cep: str | None = Field(description="Somente dígitos (8).")
    tentativas: list[TentativaEntrega]
    entregue: bool = Field(description="true se há data de entrega e recebedor; false se foi devolvido.")
    motivo_devolucao: str | None = Field(description="Motivo assinalado (ex.: MUDOU-SE, DESCONHECIDO, RECUSADO, AUSENTE, NAO_PROCURADO, ENDERECO_INSUFICIENTE, NAO_EXISTE_NUMERO, FALECIDO, OUTROS). null se entregue.")
    data_entrega: str | None = Field(description="AAAA-MM-DD.")
    data_devolucao: str | None = Field(description="AAAA-MM-DD em que o AR foi devolvido ao remetente, se não entregue.")
    recebedor_nome: str | None
    recebedor_documento: str | None = Field(description="Número do documento de identidade do recebedor, somente dígitos e letras.")
    assinatura_recebedor_presente: bool
    carimbo_unidade_presente: bool


# ===========================================================================
# Documentos manuscritos e formulários de RH
# ===========================================================================
class _Assinado(BaseModel):
    data_documento: str | None = Field(description="Data escrita no documento, AAAA-MM-DD.")
    assinatura_empregado_presente: bool


class NotificacaoEmpregado(_Controle, _Empregador, _Empregado):
    assunto: str | None = Field(description="CONVOCACAO_RETORNO, ABANDONO_EMPREGO ou OUTRO.")
    data_documento: str | None = Field(description="AAAA-MM-DD.")
    prazo_dias: int | None


class PedidoDemissao(_Controle, _Empregador, _Empregado, _Assinado):
    cumprira_aviso_previo: bool | None = Field(description="true se diz que cumprirá o aviso, false se pede dispensa do aviso, null se não menciona.")


class AtestadoMedico(_Controle):
    paciente_nome: str | None
    data_atendimento: str | None = Field(description="AAAA-MM-DD.")
    dias_afastamento: int | None
    cid_informado: bool = Field(description="true se há um código CID escrito (não transcreva o código).")
    medico_nome: str | None
    medico_crm: str | None
    carimbo_presente: bool
    assinatura_medico_presente: bool


class DeclaracaoManuscrita(_Controle, _Empregado, _Assinado):
    assunto: str | None = Field(description="RESIDENCIA, DEPENDENTES, NAO_ACUMULO_EMPREGO ou OUTRO.")
    endereco: str | None = Field(description="Endereço declarado, quando houver.")


class ReciboAvulso(_Controle):
    tipo_pagamento: str | None = Field(description="ADIANTAMENTO, VALE, DIARIA ou OUTRO.")
    valor: float | None
    valor_por_extenso: str | None
    recebedor_nome: str | None
    recebedor_cpf: str | None = Field(description="Somente dígitos.")
    pagador_nome: str | None
    referente_a: str | None
    data_documento: str | None = Field(description="AAAA-MM-DD.")
    assinatura_recebedor_presente: bool


class JustificativaFalta(_Controle, _Empregado, _Assinado):
    tipo_ocorrencia: str | None = Field(description="FALTA ou ATRASO.")
    data_ocorrencia: str | None = Field(description="AAAA-MM-DD.")
    motivo: str | None
    visto_chefia_presente: bool


class AdvertenciaSuspensao(_Controle, _Empregador, _Empregado):
    medida: str | None = Field(description="ADVERTENCIA ou SUSPENSAO.")
    forma: str | None = Field(description="IMPRESSA ou MANUSCRITA.")
    data_documento: str | None = Field(description="AAAA-MM-DD.")
    motivo: str | None
    dias_suspensao: int | None
    ciencia: str | None = Field(description="CIENTE (empregado assinou), RECUSA (recusou-se a assinar) ou SEM_CIENCIA.")
    assinatura_empregado_presente: bool
    quantidade_testemunhas: int


class CTPSAnotacao(_Controle, _Empregador):
    tipo_anotacao: str | None = Field(description="CONTRATO, ALTERACAO_SALARIAL, FERIAS ou OUTRA.")
    data_anotacao: str | None = Field(description="AAAA-MM-DD (data de admissão, da alteração ou do início das férias).")
    cargo: str | None
    salario: float | None
    ferias_inicio: str | None = Field(description="AAAA-MM-DD.")
    ferias_fim: str | None = Field(description="AAAA-MM-DD.")
    carimbo_presente: bool
    assinatura_empregador_presente: bool


class FichaRegistro(_Controle, _Empregador, _Empregado):
    empregado_pis: str | None
    matricula: str | None
    data_admissao: str | None = Field(description="AAAA-MM-DD.")
    cargo: str | None
    salario: float | None
    foto_presente: bool


class Participante(BaseModel):
    nome: str | None
    cpf: str | None = Field(description="Somente dígitos.")
    assinatura_presente: bool


class ListaPresenca(_Controle, _Empregador):
    treinamento: str | None
    data: str | None = Field(description="AAAA-MM-DD.")
    carga_horaria_horas: float | None
    instrutor: str | None
    participantes: list[Participante]


class OrdemServicoSST(_Controle, _Empregador, _Empregado, _Assinado):
    funcao: str | None
    riscos: list[str]


class LinhaTransporte(BaseModel):
    linha: str | None
    tarifa: float | None
    viagens_por_dia: int | None


class DeclaracaoValeTransporte(_Controle, _Empregador, _Empregado, _Assinado):
    opcao: str | None = Field(description="OPTANTE ou NAO_OPTANTE.")
    endereco_residencial: str | None
    linhas: list[LinhaTransporte]


class Dependente(BaseModel):
    nome: str | None
    parentesco: str | None
    data_nascimento: str | None = Field(description="AAAA-MM-DD.")


class DeclaracaoDependentes(_Controle, _Empregador, _Empregado, _Assinado):
    dependentes: list[Dependente]


class ReciboBeneficio(_Controle, _Empregador, _Empregado, _Assinado):
    beneficio: str | None = Field(description="VALE_TRANSPORTE, VALE_REFEICAO ou VALE_ALIMENTACAO.")
    competencia: str | None = Field(description="AAAA-MM.")
    quantidade: int | None
    valor_total: float | None


class Ferias(_Controle, _Empregador, _Empregado, _Assinado):
    subtipo: str | None = Field(description="AVISO ou RECIBO.")
    aquisitivo_inicio: str | None = Field(description="AAAA-MM-DD.")
    aquisitivo_fim: str | None = Field(description="AAAA-MM-DD.")
    gozo_inicio: str | None = Field(description="AAAA-MM-DD.")
    gozo_fim: str | None = Field(description="AAAA-MM-DD.")
    dias: int | None
    valor_liquido: float | None


class ItemChecklist(BaseModel):
    descricao: str
    marcado: bool


class ChecklistIntegracao(_Controle, _Empregador, _Empregado, _Assinado):
    itens: list[ItemChecklist]
    assinatura_responsavel_presente: bool


class ItemEntregue(BaseModel):
    descricao: str
    quantidade: int | None


class TermoResponsabilidade(_Controle, _Empregador, _Empregado, _Assinado):
    itens: list[ItemEntregue]


class OcorrenciaAcidente(_Controle, _Empregador, _Empregado, _Assinado):
    tipo: str | None = Field(description="ACIDENTE ou QUASE_ACIDENTE.")
    data_ocorrencia: str | None = Field(description="AAAA-MM-DD.")
    hora: str | None = Field(description="HH:MM.")
    local: str | None
    descricao: str | None = Field(description="Resumo do relato, sem diagnósticos.")
    houve_afastamento: bool | None
    testemunha_nome: str | None


class ContratoTrabalho(_Controle, _Empregador, _Empregado):
    modalidade: str | None = Field(description="EXPERIENCIA ou PRAZO_INDETERMINADO.")
    prazo_dias: int | None
    data_inicio: str | None = Field(description="AAAA-MM-DD.")
    cargo: str | None
    salario: float | None
    jornada: str | None
    rubricas_em_todas_paginas: bool
    assinatura_empregado_presente: bool
    assinatura_empregador_presente: bool
    quantidade_testemunhas: int


class DARF(_Controle, _Empregador):
    periodo_apuracao: str | None = Field(description="AAAA-MM.")
    codigo_receita: str | None
    data_vencimento: str | None = Field(description="AAAA-MM-DD.")
    valor_total: float | None
    anotacao_manuscrita: str | None
    autenticacao_bancaria_presente: bool


# Tipo -> schema de extração (OUTRO não é extraído)
MODELOS_EXTRACAO: dict[TipoDocumento, type[BaseModel]] = {
    TipoDocumento.HOLERITE: Holerite,
    TipoDocumento.CARTAO_PONTO: CartaoPonto,
    TipoDocumento.GUIA_FGTS: GuiaFGTS,
    TipoDocumento.CRF_FGTS: Certidao,
    TipoDocumento.CNDT: Certidao,
    TipoDocumento.CND_FEDERAL: Certidao,
    TipoDocumento.TRCT: TRCT,
    TipoDocumento.ASO: ASO,
    TipoDocumento.FICHA_EPI: FichaEPI,
    TipoDocumento.COMPROVANTE_PAGAMENTO: ComprovantePagamento,
    TipoDocumento.AVISO_RECEBIMENTO: AvisoRecebimento,
    TipoDocumento.NOTIFICACAO_EMPREGADO: NotificacaoEmpregado,
    TipoDocumento.PEDIDO_DEMISSAO: PedidoDemissao,
    TipoDocumento.ATESTADO_MEDICO: AtestadoMedico,
    TipoDocumento.DECLARACAO_MANUSCRITA: DeclaracaoManuscrita,
    TipoDocumento.RECIBO_AVULSO: ReciboAvulso,
    TipoDocumento.JUSTIFICATIVA_FALTA: JustificativaFalta,
    TipoDocumento.ADVERTENCIA_SUSPENSAO: AdvertenciaSuspensao,
    TipoDocumento.CTPS_ANOTACAO: CTPSAnotacao,
    TipoDocumento.FICHA_REGISTRO: FichaRegistro,
    TipoDocumento.LISTA_PRESENCA: ListaPresenca,
    TipoDocumento.ORDEM_SERVICO_SST: OrdemServicoSST,
    TipoDocumento.DECLARACAO_VALE_TRANSPORTE: DeclaracaoValeTransporte,
    TipoDocumento.DECLARACAO_DEPENDENTES: DeclaracaoDependentes,
    TipoDocumento.RECIBO_BENEFICIO: ReciboBeneficio,
    TipoDocumento.FERIAS: Ferias,
    TipoDocumento.CHECKLIST_INTEGRACAO: ChecklistIntegracao,
    TipoDocumento.TERMO_RESPONSABILIDADE: TermoResponsabilidade,
    TipoDocumento.OCORRENCIA_ACIDENTE: OcorrenciaAcidente,
    TipoDocumento.CONTRATO_TRABALHO: ContratoTrabalho,
    TipoDocumento.DARF: DARF,
}
