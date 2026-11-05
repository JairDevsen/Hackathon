from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TipoDocumento(str, Enum):
    AR_CORREIOS = "AVISO_RECEBIMENTO_CORREIOS"
    DOCUMENTO_MANUSCRITO = "DOCUMENTO_MANUSCRITO"
    ASO_SST = "ASO_SAUDE_OCUPACIONAL"
    FICHA_EPI = "FICHA_EPI_MANUSCRITA"
    CARTAO_PONTO = "CARTAO_PONTO_TRABALHISTA"
    CND_FISCAL = "CERTIDAO_NEGATIVA_CND"
    CNH = "CNH"
    RG = "RG"
    COMPROVANTE_RESIDENCIA = "COMPROVANTE_RESIDENCIA"
    CONTRATO = "CONTRATO"
    NOTA_FISCAL = "NOTA_FISCAL"
    HOLERITE = "HOLERITE"
    OUTROS = "OUTROS"


class StatusPagina(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StatusJob(str, Enum):
    PROCESSING = "PROCESSING"
    INTERRUPTED_FAILURE = "INTERRUPTED_FAILURE"
    COMPLETED = "COMPLETED"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class CamposAR(BaseModel):
    codigo_rastreio: str = Field(default="", description="Código de rastreamento dos Correios (ex: BR984512390BR)")
    remetente: str = Field(default="", description="Nome/empresa remetente (ex: Bernhoeft Compliance / Notificações)")
    destinatario: str = Field(default="", description="Fornecedor Terceirizado ou Colaborador notificado")
    endereco_entrega: str = Field(default="", description="Endereço completo de entrega")
    data_entrega_manuscrita: str = Field(default="", description="Data preenchida à mão no recebimento")
    nome_recebedor_manuscrito: str = Field(default="", description="Nome legível preenchido à caneta pelo recebedor")
    documento_recebedor_manuscrito: str = Field(default="", description="RG ou CPF do recebedor escrito à mão")
    assinatura_detectada: bool = Field(default=True, description="Indica se há rubrica/assinatura física no campo do recebedor")
    tentativas_entrega: int = Field(default=1, description="Número de tentativas marcadas no AR")


class ItemSensivelLGPD(BaseModel):
    tipo: str = Field(description="CPF, RG, TELEFONE, NOME_PESSOAL, DADO_MEDICO_ASO, ASSINATURA")
    valor_original_preview: str = Field(description="Trecho identificado")
    valor_mascarado: str = Field(description="Valor anonimizado conforme LGPD")
    pagina: int = Field(description="Página onde o dado sensível aparece")


class RegraComplianceGRT(BaseModel):
    regra: str = Field(description="Nome da regra de negócio Bernhoeft GRT (ex: Validade Normativa, Assinatura Manuscrita)")
    aprovado: bool = Field(description="True se cumpriu o requisito de mobilização")
    detalhe: str = Field(description="Explicação técnica da validação")


class TelemetriaFinOps(BaseModel):
    camada_roteamento: str = Field(description="Camada do funil que resolveu o documento (Camada 0 Hash, Camada 1 PyMuPDF, Camada 2 OCR Local, Camada 3 Gemini Flex)")
    sha256_hash: str = Field(description="Hash criptográfico para deduplicação de documentos repetidos")
    tokens_consumidos: int = Field(description="Tokens reais gastos na inferência")
    tokens_economizados: int = Field(description="Tokens poupados pelo roteamento inteligente")
    custo_estimado_brl: float = Field(description="Custo em R$ deste documento")


class DocumentoExtraidoSchema(BaseModel):
    """Schema estruturado retornado pelo motor Gemini Multimodal para a esteira Bernhoeft."""
    id: str = Field(description="Identificador único do documento no lote (ex: doc-01)")
    tipo: TipoDocumento = Field(description="Classificação automática do tipo documental")
    vertical_bernhoeft: str = Field(
        default="Gestão de Riscos com Terceiros (GRT)",
        description="Vertical de negócio Bernhoeft: GRT / Mobilização, BPO Trabalhista & Fiscal, ou Cálculos Judiciais",
    )
    status_mobilizacao: str = Field(
        default="LIBERADO PARA CATRACA / MOBILIZAÇÃO",
        description="Status de conformidade Bernhoeft (LIBERADO PARA CATRACA, BLOQUEIO PREVENTIVO GRT)",
    )
    nome_arquivo_separado: str = Field(
        default="",
        description="Nome padronizado do PDF recortado deste documento (ex: 01_CNH_Pags_1_a_2.pdf)",
    )
    titulo_resumo: str = Field(description="Título amigável identificando o documento")
    pagina_inicial: int = Field(description="Página de início deste documento no lote (1-based)")
    pagina_final: int = Field(description="Página de término deste documento no lote (1-based)")
    paginas: List[int] = Field(description="Lista de páginas agrupadas que compõem este documento")
    confianca: float = Field(description="Score de confiança entre 0.0 e 1.0")
    needs_review: bool = Field(description="True se confiança < 0.78 ou caligrafia crítica duvidosa")
    review_status: str = Field(default="PENDING_REVIEW", description="AUTO_APPROVED, PENDING_REVIEW, HUMAN_APPROVED")
    review_reason: Optional[str] = Field(default=None, description="Motivo pelo qual caiu na fila do Analista Bernhoeft")
    possui_manuscrito: bool = Field(default=False, description="True se contém escrita à mão / caligrafia cursiva")
    texto_ocr: str = Field(description="Texto completo extraído (impresso + manuscrito)")
    texto_ocr_anonimizado: str = Field(default="", description="Texto OCR com dados PII/SST mascarados pela LGPD")
    campos_ar: Optional[CamposAR] = Field(default=None, description="Preenchido se tipo == AVISO_RECEBIMENTO_CORREIOS")
    dados_sensiveis_lgpd: List[ItemSensivelLGPD] = Field(default_factory=list, description="Itens anonimizados pela camada LGPD")
    compliance_checklist: List[RegraComplianceGRT] = Field(default_factory=list, description="Checklist de Mobilização e Compliance GRT Bernhoeft")
    finops_telemetria: Optional[TelemetriaFinOps] = Field(default=None, description="Métricas de economia de tokens do Funil de 5 Camadas")
    revisado_por: Optional[str] = Field(default=None)
    notas_revisao: Optional[str] = Field(default=None)


class RevisaoHumanaInput(BaseModel):
    tipo: TipoDocumento
    texto_ocr: str
    revisado_por: str = "Analista GRT Bernhoeft (Davi)"
    notas_revisao: Optional[str] = "Conformidade validada manualmente — Colaborador liberado para mobilização"
    campos_ar: Optional[Dict[str, Any]] = None
