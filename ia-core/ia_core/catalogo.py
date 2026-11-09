"""Catálogo de tipos documentais do IA Core (mesmo código do `document_types` do backend Go).

Dois níveis: os tipos ESTÁTICOS abaixo (curados, com pistas textuais) e os tipos DESCOBERTOS pela IA durante a leitura (`origem="IA"`),
registrados em tempo de execução com `registrar_tipo`: o modelo nomeia o tipo e aponta frases que o identificam; as frases viram pistas locais,
e as próximas páginas do mesmo tipo fecham na Camada 1, sem custo de modelo."""
import os
import re
import threading
import unicodedata
from typing import Dict, List, Optional


# Páginas que completam um documento, mesmo sem marcador "Página 2/2": frase (sem acento, maiúscula) -> tipo do documento que completam.
# Usadas no agrupamento: a página entra no documento anterior do mesmo tipo em vez de abrir um documento novo.
COMPLEMENTOS = {
    "TERMO DE QUITACAO": "TRCT",
    "PLENA E GERAL QUITACAO": "TRCT",
    "DADOS DO RECEBIMENTO": "AVISO_RECEBIMENTO",
}


def norm(s: str) -> str:
    """Maiúsculas, sem acentos, espaços normalizados (para casar pistas)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[ \t]+", " ", s.upper())


# codigo -> (nome, pistas textuais, exige_assinatura)
TIPOS: Dict[str, dict] = {
    "CONTRATO_TRABALHO": dict(nome="Contrato de trabalho", pistas=["CONTRATO DE TRABALHO", "CONTRATO INDIVIDUAL DE TRABALHO", r"\bEMPREGADOR\b", r"\bEMPREGADORA\b", r"\bEMPREGADO\b", r"\bCLAUSULA \d+\b", "PERIODO DE EXPERIENCIA", "CLAUSULA PRIMEIRA", "FICA CONTRATADO"], assina=True),
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
    "CARTAO_PONTO": dict(nome="Cartão de ponto", pistas=["CARTAO DE PONTO", "ESPELHO DE PONTO", "FOLHA DE PONTO", "REGISTRO DE PONTO", r"\bJORNADA\b", r"\bENTRADA\b", r"\bSAIDA\b", r"\bDSR\b", r"\bFOLGA\b", "RUBRICA / OCORRENCIA"], assina=False),
    "RECIBO_BENEFICIOS": dict(nome="Recibo de benefícios", pistas=["RECIBO DE BENEFICIOS", "VALE-ALIMENTACAO", "VALE REFEICAO", "CESTA BASICA", "RECIBO DE VALE-TRANSPORTE", "RECIBO DE VALE-REFEICAO", "RECIBO DE VALE-ALIMENTACAO", "RECIBO DE VALE TRANSPORTE", "RECEBI DA EMPRESA ACIMA OS BENEFICIOS", "VALOR UNITARIO"], assina=True),
    "RECIBO_FERIAS": dict(nome="Recibo de férias", pistas=["RECIBO DE FERIAS", "AVISO DE FERIAS", "PERIODO AQUISITIVO"], assina=True),
    "ADVERTENCIA": dict(nome="Advertência", pistas=["ADVERTENCIA", "ADVERTIDO", "ADVERTENCIA DISCIPLINAR", "FICA V.SA. ADVERTIDO"], assina=True),
    "SUSPENSAO": dict(nome="Suspensão", pistas=["SUSPENSAO DISCIPLINAR", "FICA SUSPENSO", "SUSPENSAO DO CONTRATO", "DIAS DE SUSPENSAO"], assina=True),
    "TRCT": dict(nome="TRCT", pistas=["TERMO DE RESCISAO", r"\bTRCT\b", "RESCISAO DO CONTRATO DE TRABALHO", "TERMO DE QUITACAO", "VERBAS RESCISORIAS", "DISCRIMINACAO DAS VERBAS", "PLENA E GERAL QUITACAO"], assina=True),
    "AVISO_PREVIO": dict(nome="Aviso prévio", pistas=["AVISO PREVIO"], assina=True),
    "PEDIDO_DEMISSAO": dict(nome="Pedido de demissão", pistas=["PEDIDO DE DEMISSAO"], assina=True),
    "AVISO_RECEBIMENTO": dict(nome="Aviso de recebimento (AR)", pistas=["AVISO DE RECEBIMENTO", "CORREIOS", "CODIGO DE RASTREAMENTO", r"\bBR\d{9}BR\b", "DADOS DO RECEBIMENTO", "MATRICULA DO CARTEIRO"], assina=False),
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
    # tipos comuns de admissão e de documentação de terceirizadas que faltavam (o que ainda escapar, a IA descobre: ver `propor_tipo`)
    "CPF_CARTAO": dict(nome="CPF (comprovante)", pistas=["CADASTRO DE PESSOAS FISICAS", "CADASTRO DE PESSOA FISICA", "COMPROVANTE DE SITUACAO CADASTRAL NO CPF"], assina=False),
    "TITULO_ELEITOR": dict(nome="Título de eleitor", pistas=["TITULO DE ELEITOR", "TITULO ELEITORAL", "ZONA ELEITORAL", "JUSTICA ELEITORAL"], assina=False),
    "CERTIDAO_CIVIL": dict(nome="Certidão de nascimento ou casamento", pistas=["CERTIDAO DE NASCIMENTO", "CERTIDAO DE CASAMENTO", "REGISTRO CIVIL DAS PESSOAS NATURAIS", "OFICIAL DE REGISTRO CIVIL"], assina=False),
    "COMPROVANTE_ESCOLARIDADE": dict(nome="Comprovante de escolaridade", pistas=["HISTORICO ESCOLAR", "DECLARACAO DE ESCOLARIDADE", "CERTIFICADO DE ESCOLARIDADE", "CONCLUSAO DO ENSINO", "ENSINO MEDIO COMPLETO", "DIPLOMA DE"], assina=False),
    "CERTIFICADO_RESERVISTA": dict(nome="Certificado de reservista", pistas=["CERTIFICADO DE RESERVISTA", "CERTIFICADO DE DISPENSA DE INCORPORACAO", "ALISTAMENTO MILITAR", "SERVICO MILITAR"], assina=False),
    "ACORDO_JORNADA": dict(nome="Acordo de compensação / banco de horas", pistas=["ACORDO DE COMPENSACAO", "ACORDO INDIVIDUAL DE COMPENSACAO", "ACORDO DE BANCO DE HORAS", "COMPENSACAO DE JORNADA", "ACORDO DE PRORROGACAO"], assina=True),
    "NOTA_FISCAL": dict(nome="Nota fiscal / NFS-e", pistas=["NOTA FISCAL DE SERVICO", "NOTA FISCAL ELETRONICA", r"\bNFS-?E\b", r"\bDANFE\b", "CHAVE DE ACESSO", "NOTA FISCAL FATURA"], assina=False),
    "CARTAO_CNPJ": dict(nome="Cartão CNPJ", pistas=["COMPROVANTE DE INSCRICAO E DE SITUACAO CADASTRAL", "CADASTRO NACIONAL DA PESSOA JURIDICA", "NATUREZA JURIDICA", "DESCRICAO DA ATIVIDADE ECONOMICA"], assina=False),
    "CONTRATO_SOCIAL": dict(nome="Contrato social / alteração contratual", pistas=["CONTRATO SOCIAL", "ALTERACAO CONTRATUAL", "JUNTA COMERCIAL", "CAPITAL SOCIAL", "REQUERIMENTO DE EMPRESARIO"], assina=False),
    "GUIA_INSS": dict(nome="Guia de INSS (GPS / DAE eSocial)", pistas=["GUIA DA PREVIDENCIA SOCIAL", "DOCUMENTO DE ARRECADACAO DO ESOCIAL", r"\bGPS\b", r"\bDAE\b"], assina=False),
    "PROGRAMA_SST": dict(nome="PGR / LTCAT / laudo de SST", pistas=["PROGRAMA DE GERENCIAMENTO DE RISCOS", "LAUDO TECNICO DAS CONDICOES", "INVENTARIO DE RISCOS", r"\bPGR\b", r"\bPPRA\b", r"\bLTCAT\b"], assina=False),
    "PROTOCOLO_ENTREGA": dict(nome="Capa / protocolo de documentação mensal", pistas=["DOCUMENTACAO MENSAL", "PROTOCOLO DE ENTREGA", "CAPA DA DOCUMENTACAO", "RELACAO DE DOCUMENTOS ENTREGUES", "RELACAO DE DOCUMENTOS"], assina=False),
    "OFICIO": dict(nome="Ofício / comunicado da empresa", pistas=[r"\bOFICIO\b", r"\bOFICIO N"], assina=False),
    "ALVARA_LICENCA": dict(nome="Alvará / licença de funcionamento", pistas=["ALVARA DE FUNCIONAMENTO", "LICENCA DE FUNCIONAMENTO", "ALVARA DE LICENCA", "AUTO DE VISTORIA DO CORPO DE BOMBEIROS", r"\bAVCB\b"], assina=False),
    "OUTRO": dict(nome="Outro", pistas=[], assina=False),
}

CODIGOS: List[str] = list(TIPOS.keys())  # os tipos estáticos; os descobertos pela IA entram em TIPOS em tempo de execução

# Mapeamento dos códigos do protótipo antigo.
LEGADO = {
    "AVISO_RECEBIMENTO_CORREIOS": "AVISO_RECEBIMENTO", "ASO_SAUDE_OCUPACIONAL": "ASO", "FICHA_EPI_MANUSCRITA": "FICHA_EPI",
    "CARTAO_PONTO_TRABALHISTA": "CARTAO_PONTO", "CERTIDAO_NEGATIVA_CND": "CND_FEDERAL", "CONTRATO": "CONTRATO_PRESTACAO_SERVICO",
    "NOTA_FISCAL": "NOTA_FISCAL", "OUTROS": "OUTRO", "COMPROVANTE_RESIDENCIA": "COMPROVANTE_RESIDENCIA",
}


def _colado(s: str) -> str:
    return re.sub(r"\s+", "", s)


def pontuar(texto: str) -> Dict[str, int]:
    t = norm(texto)
    tc = _colado(t)  # o OCR cola ou parte palavras ("Recibode pagamento"): as pistas longas também são procuradas sem espaços
    out: Dict[str, int] = {}
    for cod, d in list(TIPOS.items()):  # cópia: a IA pode registrar um tipo novo em outra thread
        s = 0
        for p in d["pistas"]:
            achou = bool(re.search(p if p.startswith(r"\b") else re.escape(p), t))
            if not achou and not p.startswith(r"\b") and len(p) >= 14:
                achou = _colado(p) in tc
            if achou:
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
    if TIPOS[top].get("origem") == ORIGEM_IA:  # pistas aprendidas pela IA: duas frases fecham sozinhas na Camada 1; uma só pede conferência do modelo
        conf = min(conf, 0.86 if s1 >= 6 else 0.75)
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


# Tipos que pertencem à EMPRESA (terceirizada/fornecedor/contratante), não a uma pessoa: não têm CPF do funcionário.
DOCS_DA_EMPRESA = {"CRF_FGTS", "CNDT", "CND_FEDERAL", "GUIA_FGTS", "DARF", "CONTRATO_PRESTACAO_SERVICO", "APOLICE_SEGURO", "AUTO_INFRACAO",
                   "PROCESSO_JUDICIAL", "RELATORIO_AUDITORIA", "LISTA_PRESENCA", "OUTRO", "NOTA_FISCAL", "CARTAO_CNPJ", "CONTRATO_SOCIAL", "GUIA_INSS",
                   "PROGRAMA_SST", "PROTOCOLO_ENTREGA", "OFICIO", "ALVARA_LICENCA"}
# Tipos que só valem para um mês: sem a competência o documento não cumpre a exigência mensal.
DOCS_MENSAIS = {"HOLERITE", "CARTAO_PONTO", "GUIA_FGTS", "DARF", "COMPROVANTE_PAGAMENTO", "RECIBO_BENEFICIOS", "GUIA_INSS", "PROTOCOLO_ENTREGA"}


# ---------------------------------------------------------------------------------------------------------------------------
# Tipos descobertos pela IA
# ---------------------------------------------------------------------------------------------------------------------------
ORIGEM_IA = "IA"
CATEGORIAS = ("ADMISSAO", "MENSAL", "SAUDE_SEGURANCA", "DISCIPLINAR", "DESLIGAMENTO", "EMPRESA", "OUTROS")
MAX_TIPOS_IA = int(os.environ.get("IA_MAX_TIPOS_AUTOMATICOS", "150"))  # teto de tipos criados pela IA (evita catálogo inflado por nomes soltos)
_TRAVA = threading.Lock()
_GENERICOS = {"OUTRO", "OUTROS", "DOCUMENTO", "DOCUMENTOS", "PAGINA", "PAGINAS", "DESCONHECIDO", "NAO IDENTIFICADO", "SEM TITULO", "SEM TIPO", "TEXTO",
              "IMAGEM", "FOTO", "ILEGIVEL", "FORMULARIO", "DECLARACAO", "COMUNICADO", "CARTA", "TERMO", "RECIBO", "CERTIFICADO", "CERTIDAO", "RELATORIO",
              "AVISO", "FICHA", "LISTA", "SEPARADOR", "CAPA", "FOLHA", "EM BRANCO", "ANEXO", "COMPROVANTE"}
_PARTICULAS = {"DE", "DO", "DA", "DOS", "DAS", "E", "EM", "PARA", "POR", "A", "O", "AO", "COM", "NO", "NA"}


def _tokens(nome: str) -> set:
    return {t for t in re.findall(r"[A-Z0-9]+", norm(nome)) if t not in _PARTICULAS}


def codigo_de(nome: str) -> str:
    """Código estável a partir do nome: 'Nota fiscal de serviço' -> NOTA_FISCAL_DE_SERVICO (maiúsculas, sem acento, até 40 caracteres)."""
    c = re.sub(r"[^A-Z0-9]+", "_", norm(nome)).strip("_")
    return c[:40].rstrip("_")


def nome_valido(nome: str) -> bool:
    """Nome que a IA propôs é um NOME DE TIPO (genérico e curto), não uma instância: sem número longo, e-mail, CPF/CNPJ nem só uma palavra vaga."""
    n = (nome or "").strip()
    if not 4 <= len(n) <= 60 or not re.search(r"[A-Za-zÀ-ÿ]{3}", n):
        return False
    if re.search(r"\d{5,}|@|\d{3}\.\d{3}\.\d{3}|\d{2}\.\d{3}\.\d{3}/", n):
        return False
    nn = norm(n).strip(" .:-/")
    return nn not in _GENERICOS and len(_tokens(n)) >= 1 and codigo_de(n) not in ("", "OUTRO")


def tipo_existente(nome: str) -> Optional[str]:
    """Código de um tipo que já cobre o nome proposto (mesmo código, mesmo nome ou palavras quase iguais), ou None. Evita duplicar 'Nota fiscal'
    e 'Nota fiscal de serviço' como dois tipos."""
    cod = codigo_de(nome)
    if cod in TIPOS and cod != "OUTRO":
        return cod
    alvo = _tokens(nome)
    if not alvo:
        return None
    melhor, nota = None, 0.0
    for c, d in list(TIPOS.items()):
        if c == "OUTRO":
            continue
        t_nome, t_cod = _tokens(d["nome"]), _tokens(c.replace("_", " "))
        j = max(len(alvo & t) / len(alvo | t) for t in (t_nome, t_cod) if t) if (t_nome or t_cod) else 0.0
        if any(len(t) >= 2 and (t <= alvo or alvo <= t) for t in (t_nome, t_cod)):
            j = max(j, 0.8)  # um nome contido no outro, com ao menos duas palavras ("nota fiscal" em "nota fiscal de serviço")
        if j > nota:
            melhor, nota = c, j
    return melhor if nota >= 0.7 else None


def pistas_validas(pistas, texto: str) -> List[str]:
    """Pistas propostas pela IA que valem como regra local: frases do próprio documento (conferidas no texto lido, para barrar invenção),
    sem número, de 8 a 60 caracteres, e que não coincidem com pistas de outro tipo (ambiguidade)."""
    n, nc = norm(texto), _colado(norm(texto))
    out: List[str] = []
    for p in pistas or []:
        pn = re.sub(r"\s+", " ", norm(str(p))).strip(" .:;-/|")
        if not 8 <= len(pn) <= 60 or re.search(r"\d{3,}", pn) or pn in out:
            continue
        if pn not in n and _colado(pn) not in nc:
            continue  # a IA "lembrou" uma frase que não está na página
        if pontuar(pn):
            continue  # já casa com outro tipo do catálogo: não serve para distinguir este
        out.append(pn)
    return out[:4]


def registrar_tipo(codigo: str, nome: str, pistas=None, escopo: str = "FUNCIONARIO", categoria: str = "OUTROS", assina: bool = False, origem: str = ORIGEM_IA) -> bool:
    """Inclui (ou atualiza as pistas de) um tipo descoberto. Devolve False se o código for inválido, colidir com um tipo estático ou passar do teto."""
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,39}", codigo or "") or codigo == "OUTRO":
        return False
    escopo = escopo if escopo in ("FUNCIONARIO", "EMPRESA") else "FUNCIONARIO"
    categoria = categoria if categoria in CATEGORIAS else "OUTROS"
    with _TRAVA:
        atual = TIPOS.get(codigo)
        if atual is not None and atual.get("origem") != ORIGEM_IA:
            return False  # tipo estático: não se sobrescreve
        if atual is None and sum(1 for d in TIPOS.values() if d.get("origem") == ORIGEM_IA) >= MAX_TIPOS_IA:
            return False
        antigas = list(atual["pistas"]) if atual else []
        novas = antigas + [x for x in (pistas or []) if x not in antigas]
        TIPOS[codigo] = dict(nome=(atual or {}).get("nome") or nome.strip(), pistas=novas[:6], assina=assina, origem=origem, escopo=escopo, categoria=categoria)
        (DOCS_DA_EMPRESA.add if escopo == "EMPRESA" else DOCS_DA_EMPRESA.discard)(codigo)
        (DOCS_MENSAIS.add if categoria == "MENSAL" else DOCS_MENSAIS.discard)(codigo)
    return True


def dados_tipo_ia(codigo: str) -> Optional[dict]:
    """Descrição de um tipo descoberto pela IA (para o backend registrá-lo no catálogo), ou None se o tipo é do catálogo estático."""
    d = TIPOS.get(codigo)
    if not d or d.get("origem") != ORIGEM_IA:
        return None
    return dict(codigo=codigo, nome=d["nome"], escopo=d.get("escopo", "FUNCIONARIO"), categoria=d.get("categoria", "OUTROS"), pistas=list(d["pistas"]))


def propor_tipo(nome: str, pistas, texto: str, escopo: str = "FUNCIONARIO", categoria: str = "OUTROS") -> Optional[str]:
    """A IA leu um documento legível que nenhum tipo cobre e deu um nome: devolve o código a usar (um tipo que já existe e equivale, ou um novo
    registrado agora), ou None se a proposta não presta (nome vago, instância no lugar do tipo, catálogo cheio)."""
    if not nome_valido(nome):
        return None
    existente = tipo_existente(nome)
    if existente:
        return existente
    codigo = codigo_de(nome)
    if not registrar_tipo(codigo, nome, pistas_validas(pistas, texto), escopo, categoria):
        return None
    return codigo
