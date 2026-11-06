"""Catálogo dos 44 tipos documentais do IA Core (mesmo código do `document_types` do backend Go)."""
import re
import unicodedata
from typing import Dict, List, Optional


def norm(s: str) -> str:
    """Maiúsculas, sem acentos, espaços normalizados (para casar pistas)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[ \t]+", " ", s.upper())


# codigo -> (nome, pistas textuais, exige_assinatura)
TIPOS: Dict[str, dict] = {
    "CONTRATO_TRABALHO": dict(nome="Contrato de trabalho", pistas=["CONTRATO DE TRABALHO", "CONTRATO INDIVIDUAL DE TRABALHO", r"\bEMPREGADOR\b", r"\bEMPREGADO\b", "PERIODO DE EXPERIENCIA", "CLAUSULA PRIMEIRA", "FICA CONTRATADO"], assina=True),
    "FICHA_REGISTRO": dict(nome="Ficha de registro", pistas=["FICHA DE REGISTRO", "REGISTRO DE EMPREGADO", "LIVRO DE REGISTRO"], assina=False),
    "CTPS": dict(nome="CTPS", pistas=["CARTEIRA DE TRABALHO", r"\bCTPS\b", "ALTERACOES DE SALARIO", "GOZOU FERIAS DE", "ANOTACOES GERAIS", "ANOTACOES DA CTPS", "DATA DE SAIDA", "DATA DE ADMISSAO", "DATA ADMISSAO", r"\bMUNICIPIO\b", r"\bREMUNERACAO\b"], assina=False),
    "RG": dict(nome="RG", pistas=["REGISTRO GERAL", "CARTEIRA DE IDENTIDADE", r"\bSSP\b"], assina=False),
    "CNH": dict(nome="CNH", pistas=["HABILITACAO", r"\bCNH\b", "SENATRAN", r"\bDETRAN\b"], assina=False),
    "COMPROVANTE_RESIDENCIA": dict(nome="Comprovante de residência", pistas=["COMPROVANTE DE RESIDENCIA", "FATURA DE ENERGIA", "CONTA DE LUZ", "CONTA DE AGUA", "COMPESA", "NEOENERGIA"], assina=False),
    "DECLARACAO_VT": dict(nome="Declaração de vale-transporte", pistas=["VALE-TRANSPORTE", "VALE TRANSPORTE", "DECLARACAO DE VT", "DECLARACAO DE VALE-TRANSPORTE", "DECLARACAO DE VALE TRANSPORTE", "OPCAO PELO VALE"], assina=True),
    "ORDEM_SERVICO": dict(nome="Ordem de serviço (NR-01)", pistas=["ORDEM DE SERVICO", "NR-01", "NR 01", "RISCOS OCUPACIONAIS"], assina=True),
    "ASO": dict(nome="ASO", pistas=["ATESTADO DE SAUDE OCUPACIONAL", r"\bASO\b", "PCMSO", "NR-07", "NR-7"], assina=False),
    "FICHA_EPI": dict(nome="Ficha de EPI", pistas=["FICHA DE EPI", "FICHA DE ENTREGA DE EPI", "EQUIPAMENTO DE PROTECAO INDIVIDUAL", "NR-06", "NR 06"], assina=True),
    "TREINAMENTO_NR": dict(nome="Certificado de treinamento NR", pistas=["CERTIFICADO DE TREINAMENTO", "CERTIFICADO DE CONCLUSAO", "NR-35", "NR-10", "NR-33", "CARGA HORARIA", "RECICLAGEM"], assina=False),
    "ATESTADO_MEDICO": dict(nome="Atestado médico", pistas=["ATESTADO MEDICO", r"\bCID\b", "DIAS DE REPOUSO", "AFASTAMENTO"], assina=False),
    "CAT_ACIDENTE": dict(nome="CAT / acidente", pistas=["COMUNICACAO DE ACIDENTE", "ACIDENTE DE TRABALHO", r"\bCAT\b", "RELATO DE OCORRENCIA", "QUASE-ACIDENTE", "QUASE ACIDENTE", "DESCRICAO DO OCORRIDO", "HOUVE AFASTAMENTO"], assina=False),
    "HOLERITE": dict(nome="Holerite", pistas=["RECIBO DE PAGAMENTO", "HOLERITE", "CONTRACHEQUE", "SALARIO BASE", "LIQUIDO A RECEBER", r"\bINSS\b"], assina=False),
    "CARTAO_PONTO": dict(nome="Cartão de ponto", pistas=["CARTAO DE PONTO", "FOLHA DE PONTO", "REGISTRO DE PONTO", r"\bJORNADA\b", r"\bENTRADA\b", r"\bSAIDA\b", r"\bDSR\b", r"\bFOLGA\b", "RUBRICA / OCORRENCIA"], assina=False),
    "RECIBO_BENEFICIOS": dict(nome="Recibo de benefícios", pistas=["RECIBO DE BENEFICIOS", "VALE-ALIMENTACAO", "VALE REFEICAO", "CESTA BASICA", "RECIBO DE VALE-TRANSPORTE", "RECIBO DE VALE-REFEICAO", "RECIBO DE VALE-ALIMENTACAO", "RECIBO DE VALE TRANSPORTE", "RECEBI DA EMPRESA ACIMA OS BENEFICIOS", "VALOR UNITARIO"], assina=True),
    "RECIBO_FERIAS": dict(nome="Recibo de férias", pistas=["RECIBO DE FERIAS", "AVISO DE FERIAS", "PERIODO AQUISITIVO"], assina=True),
    "ADVERTENCIA": dict(nome="Advertência", pistas=["ADVERTENCIA", "ADVERTIDO", "ADVERTENCIA DISCIPLINAR", "FICA V.SA. ADVERTIDO"], assina=True),
    "SUSPENSAO": dict(nome="Suspensão", pistas=["SUSPENSAO DISCIPLINAR", "FICA SUSPENSO", "SUSPENSAO DO CONTRATO", "DIAS DE SUSPENSAO"], assina=True),
    "TRCT": dict(nome="TRCT", pistas=["TERMO DE RESCISAO", r"\bTRCT\b", "RESCISAO DO CONTRATO DE TRABALHO"], assina=True),
    "AVISO_PREVIO": dict(nome="Aviso prévio", pistas=["AVISO PREVIO"], assina=True),
    "PEDIDO_DEMISSAO": dict(nome="Pedido de demissão", pistas=["PEDIDO DE DEMISSAO"], assina=True),
    "AVISO_RECEBIMENTO": dict(nome="Aviso de recebimento (AR)", pistas=["AVISO DE RECEBIMENTO", "CORREIOS", "CODIGO DE RASTREAMENTO", r"\bBR\d{9}BR\b"], assina=False),
    "DOCUMENTO_MANUSCRITO": dict(nome="Documento manuscrito", pistas=["DE PROPRIO PUNHO", "PROPRIO PUNHO", "TERMO MANUSCRITO"], assina=False),
    "CRF_FGTS": dict(nome="CRF do FGTS", pistas=["CERTIFICADO DE REGULARIDADE DO FGTS", r"\bCRF\b"], assina=False),
    "CNDT": dict(nome="CNDT", pistas=["CERTIDAO NEGATIVA DE DEBITOS TRABALHISTAS", r"\bCNDT\b"], assina=False),
    "CND_FEDERAL": dict(nome="CND federal", pistas=["CERTIDAO NEGATIVA DE DEBITOS RELATIVOS", "RECEITA FEDERAL", "CERTIDAO NEGATIVA", r"\bCND\b"], assina=False),
    "GUIA_FGTS": dict(nome="Guia de FGTS", pistas=["GUIA DO FGTS", "FGTS DIGITAL", "GUIA DE RECOLHIMENTO DO FGTS", r"\bGFIP\b", "GUIA DO FGTS DIGITAL", "VALOR A RECOLHER", "IDENTIFICADOR DA GUIA", r"\bGFD\b"], assina=False),
    "DARF": dict(nome="DARF", pistas=[r"\bDARF\b", "DOCUMENTO DE ARRECADACAO DE RECEITAS FEDERAIS", "DOCUMENTO DE ARRECADACAO DE TRIBUTOS FEDERAIS", "CODIGO DA RECEITA", "PERIODO DE APURACAO", "VALOR DO PRINCIPAL"], assina=False),
    "LISTA_PRESENCA": dict(nome="Lista de presença", pistas=["LISTA DE PRESENCA", "PRESENCA EM TREINAMENTO", "NOME (LETRA LEGIVEL)", "LISTA DE FREQUENCIA", "REGISTRO DE PRESENCA", r"\bINSTRUTOR\b"], assina=False),
    "CONTRATO_PRESTACAO_SERVICO": dict(nome="Contrato de prestação de serviço", pistas=["CONTRATO DE PRESTACAO DE SERVICO", "INSTRUMENTO PARTICULAR", "PRESTADORA", "CONTRATANTE"], assina=True),
    # tipos de RH que o gerador de documentos fictícios produz e que não tinham equivalente
    "COMPROVANTE_PAGAMENTO": dict(nome="Comprovante de pagamento", pistas=["COMPROVANTE DE TRANSFERENCIA", "COMPROVANTE DE PAGAMENTO", "COMPROVANTE DE PIX", "COMPROVANTE DE TED", "COMPROVANTE DE DEPOSITO", "ID DA TRANSACAO", r"\bFAVORECIDO\b", r"\bPAGADOR\b", "AUTENTICACAO BANCARIA"], assina=False),
    "NOTIFICACAO_EMPREGADO": dict(nome="Notificação ao empregado", pistas=["NOTIFICACAO AO EMPREGADO", r"\bNOTIFICACAO N", "FICA V.SA. CONVOCADO", "AUSENCIA AO TRABALHO SEM JUSTIFICATIVA", "RETORNAR AS SUAS ATIVIDADES", "ABANDONO DE EMPREGO", r"\bCONVOCADO\b", "NOTIFICACAO EXTRAJUDICIAL"], assina=False),
    "DECLARACAO_MANUSCRITA": dict(nome="Declaração manuscrita", pistas=["POR SER VERDADE", "FIRMO A PRESENTE DECLARACAO", "DECLARO QUE RESIDO", "DECLARO QUE POSSUO", "DECLARO QUE NAO ACUMULO", "NAO ACUMULO EMPREGO", "DECLARACAO DE RESIDENCIA", r"\bDECLARACAO\b"], assina=False),
    "RECIBO_AVULSO": dict(nome="Recibo avulso (adiantamento, vale, diária)", pistas=["RECEBI(EMOS) DE", "RECEBI DE", "A QUANTIA DE", "ADIANTAMENTO SALARIAL", "VALE AVULSO", r"\bDIARIA\b", "REFERENTE A", r"\bRECIBO\b"], assina=False),
    "JUSTIFICATIVA_FALTA": dict(nome="Justificativa de falta", pistas=["JUSTIFICAR MINHA FALTA", "JUSTIFICATIVA DE FALTA", "JUSTIFICATIVA DE AUSENCIA", "PECO A COMPREENSAO", "MINHA AUSENCIA", "FALTA NO DIA", "AUSENCIA / ATRASO", "DATA DA OCORRENCIA", "VISTO DA CHEFIA IMEDIATA", r"\bJUSTIFICATIVA\b"], assina=False),
    "DECLARACAO_DEPENDENTES": dict(nome="Declaração de dependentes", pistas=["DECLARACAO DE DEPENDENTES", "SALARIO-FAMILIA", "SALARIO FAMILIA", "NOME DO DEPENDENTE", r"\bPARENTESCO\b", r"\bIRRF\b", "DEPENDENTE(S)"], assina=True),
    "CHECKLIST_INTEGRACAO": dict(nome="Checklist de integração", pistas=["CHECK-LIST DE INTEGRACAO", "CHECKLIST DE INTEGRACAO", "LIBERACAO DE ACESSO", "CRACHA DE IDENTIFICACAO", "CADASTRO BIOMETRICO", "APRESENTACAO DAS NORMAS INTERNAS", "ORIENTACAO SOBRE ROTAS DE FUGA"], assina=False),
    "TERMO_RESPONSABILIDADE": dict(nome="Termo de responsabilidade", pistas=["TERMO DE RESPONSABILIDADE", "COMPROMETENDO-ME A ZELAR", "RECEBI OS ITENS ABAIXO", "AUTORIZANDO O DESCONTO", "DEVOLVE-LOS", "ZELAR POR SUA CONSERVACAO"], assina=True),
    # documentos da empresa terceirizada/fornecedora que revelam risco para a contratante
    "APOLICE_SEGURO": dict(nome="Apólice de seguro", pistas=["APOLICE DE SEGURO", "SEGURADORA", "PREMIO DO SEGURO", "VIGENCIA DA APOLICE", "SEGURO DE VIDA EM GRUPO", "RESPONSABILIDADE CIVIL", r"\bAPOLICE\b"], assina=False),
    "AUTO_INFRACAO": dict(nome="Auto de infração / fiscalização", pistas=["AUTO DE INFRACAO", "AUDITOR FISCAL DO TRABALHO", "MINISTERIO PUBLICO DO TRABALHO", "FISCALIZACAO DO TRABALHO", "TERMO DE AJUSTAMENTO DE CONDUTA", "NOTIFICACAO FISCAL"], assina=False),
    "PROCESSO_JUDICIAL": dict(nome="Citação / processo judicial", pistas=["RECLAMACAO TRABALHISTA", "VARA DO TRABALHO", "TRIBUNAL REGIONAL DO TRABALHO", r"\bRECLAMANTE\b", r"\bRECLAMADA\b", r"\bCITACAO\b", "NUMERO DO PROCESSO"], assina=False),
    "RELATORIO_AUDITORIA": dict(nome="Relatório de auditoria / diligência", pistas=["RELATORIO DE AUDITORIA", "RELATORIO DE DILIGENCIA", "AUDITORIA DE FORNECEDOR", "ACHADOS DA AUDITORIA", "NAO CONFORMIDADES IDENTIFICADAS"], assina=False),
    "OUTRO": dict(nome="Outro", pistas=[], assina=False),
}

CODIGOS: List[str] = list(TIPOS.keys())
assert len(CODIGOS) == 44, "o catálogo deve ter exatamente 44 tipos"

# Mapeamento dos códigos do protótipo antigo.
LEGADO = {
    "AVISO_RECEBIMENTO_CORREIOS": "AVISO_RECEBIMENTO", "ASO_SAUDE_OCUPACIONAL": "ASO", "FICHA_EPI_MANUSCRITA": "FICHA_EPI",
    "CARTAO_PONTO_TRABALHISTA": "CARTAO_PONTO", "CERTIDAO_NEGATIVA_CND": "CND_FEDERAL", "CONTRATO": "CONTRATO_PRESTACAO_SERVICO",
    "NOTA_FISCAL": "OUTRO", "OUTROS": "OUTRO", "COMPROVANTE_RESIDENCIA": "COMPROVANTE_RESIDENCIA",
}


def pontuar(texto: str) -> Dict[str, int]:
    t = norm(texto)
    out: Dict[str, int] = {}
    for cod, d in TIPOS.items():
        s = 0
        for p in d["pistas"]:
            if re.search(p if p.startswith(r"\b") else re.escape(p), t):
                # peso 3 para pistas longas (mais específicas); numa palavra isolada (\bPALAVRA\b) o tamanho é o da palavra, sem os \b
                miolo = p[2:-2] if p.startswith(r"\b") and p.endswith(r"\b") and re.fullmatch(r"[A-Z ]+", p[2:-2]) else p
                s += 3 if len(miolo) > 12 else 1
        if s:
            out[cod] = s
    return out


def classificar(texto: str) -> (str, float):
    sc = pontuar(texto)
    if not sc:
        return "OUTRO", 0.4
    ordem = sorted(sc.items(), key=lambda kv: -kv[1])
    top, s1 = ordem[0]
    s2 = ordem[1][1] if len(ordem) > 1 else 0
    conf = min(0.98, 0.62 + 0.09 * min(s1, 4))
    if s1 - s2 < 2:
        conf -= 0.14
    return top, round(max(conf, 0.45), 2)


# Códigos usados pelo gerador de documentos fictícios (ia-generator-documents) -> códigos deste catálogo.
# Serve para medir a cobertura (acerto de classificação) comparando o gabarito do gerador com o que o sistema reconhece.
# Quando o gerador agrupa dois tipos (ADVERTENCIA_SUSPENSAO), ambos os códigos daqui são aceitos.
GERADOR = {
    "CTPS_ANOTACAO": {"CTPS"}, "ORDEM_SERVICO_SST": {"ORDEM_SERVICO"}, "DECLARACAO_VALE_TRANSPORTE": {"DECLARACAO_VT"},
    "RECIBO_BENEFICIO": {"RECIBO_BENEFICIOS"}, "FERIAS": {"RECIBO_FERIAS"}, "OCORRENCIA_ACIDENTE": {"CAT_ACIDENTE"},
    "ADVERTENCIA_SUSPENSAO": {"ADVERTENCIA", "SUSPENSAO"},
}


def codigos_equivalentes(codigo_do_gerador: str) -> set:
    """Códigos do sistema que valem como acerto para um tipo do gerador."""
    return GERADOR.get(codigo_do_gerador, {codigo_do_gerador})
