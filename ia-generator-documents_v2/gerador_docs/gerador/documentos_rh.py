"""Documentos de RH manuscritos, formulários preenchidos à mão e impressos assinados."""
from __future__ import annotations

import random
from datetime import date, timedelta

from faker import Faker
from PIL import Image, ImageDraw, ImageFilter

from . import calculos as calc
from ._ia_core import sch
from .canvas import A4, Escritor, Folha, brl, fmt_cnpj, fmt_cpf, fmt_data
from .conferencia import registrado
from .documentos import M, DocGerado, _cabecalho, _nc
from .universo import MESES, Empregado, Empresa, Universo

T = sch.TipoDocumento

NCS_RH = {
    T.PEDIDO_DEMISSAO: {"sem_assinatura": "assinatura_empregado_presente"},
    T.ATESTADO_MEDICO: {"atestado_sem_crm": "medico_crm"},
    T.DECLARACAO_MANUSCRITA: {"sem_assinatura": "assinatura_empregado_presente"},
    T.RECIBO_AVULSO: {"sem_assinatura": "assinatura_recebedor_presente"},
    T.JUSTIFICATIVA_FALTA: {"sem_assinatura": "assinatura_empregado_presente"},
    T.ADVERTENCIA_SUSPENSAO: {"recusa_sem_testemunhas": "quantidade_testemunhas", "sem_ciencia": "ciencia"},
    T.LISTA_PRESENCA: {"presenca_sem_assinatura": "participantes", "cpf_invalido": "participantes"},
    T.ORDEM_SERVICO_SST: {"sem_assinatura": "assinatura_empregado_presente"},
    T.DECLARACAO_VALE_TRANSPORTE: {"sem_assinatura": "assinatura_empregado_presente"},
    T.DECLARACAO_DEPENDENTES: {"sem_assinatura": "assinatura_empregado_presente"},
    T.RECIBO_BENEFICIO: {"sem_assinatura": "assinatura_empregado_presente"},
    T.FERIAS: {"sem_assinatura": "assinatura_empregado_presente"},
    T.CHECKLIST_INTEGRACAO: {"sem_assinatura": "assinatura_empregado_presente"},
    T.TERMO_RESPONSABILIDADE: {"sem_assinatura": "assinatura_empregado_presente"},
    T.OCORRENCIA_ACIDENTE: {"sem_assinatura": "assinatura_empregado_presente"},
    T.CONTRATO_TRABALHO: {"contrato_sem_rubrica": "rubricas_em_todas_paginas", "sem_assinatura": "assinatura_empregado_presente"},
}
DESCRICAO_NC_RH = {
    "atestado_sem_crm": "atestado sem CRM do médico", "recusa_sem_testemunhas": "recusa de ciência com menos de 2 testemunhas",
    "sem_ciencia": "medida disciplinar sem ciência", "presenca_sem_assinatura": "participante sem assinatura na lista",
    "contrato_sem_rubrica": "página do contrato sem rubrica",
}

# ------------------------------------------------------------------ utilitários
UNID = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze", "treze",
        "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
CEM = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]


def _ate_mil(n: int) -> str:
    if n == 100:
        return "cem"
    partes = []
    if n >= 100:
        partes.append(CEM[n // 100])
        n %= 100
    if n >= 20:
        partes.append(DEZ[n // 10] + (f" e {UNID[n % 10]}" if n % 10 else ""))
    elif n:
        partes.append(UNID[n])
    return " e ".join(partes)


def extenso_reais(v: float) -> str:
    reais, cent = int(v), round((v - int(v)) * 100)
    partes = []
    if reais >= 1000:
        mil = reais // 1000
        partes.append("mil" if mil == 1 else f"{_ate_mil(mil)} mil")
        reais %= 1000
    if reais:
        partes.append(_ate_mil(reais))
    txt = " e ".join(partes) if partes else "zero"
    txt += " real" if int(v) == 1 else " reais"
    if cent:
        txt += f" e {_ate_mil(cent)} centavo{'s' if cent > 1 else ''}"
    return txt


def extenso_int(n: int) -> str:
    return _ate_mil(n) if n < 1000 else str(n)


def data_extenso(d: date) -> str:
    return f"{d.day:02d} de {MESES[d.month - 1].lower()} de {d.year}"


def _fk(rng: random.Random) -> Faker:
    fk = Faker("pt_BR")
    fk.seed_instance(rng.randrange(10**9))
    return fk


def _hoje(u: Universo) -> date:
    return date.fromisoformat(u.data_referencia)


def _papel_carta(rng: random.Random) -> tuple[Folha, int, int, int]:
    """Folha para texto de próprio punho: caderno pautado ou folha branca. Retorna (folha, x, y_inicial, passo)."""
    f = Folha(rng)
    if rng.random() < 0.55:
        passo = rng.choice([70, 76, 82])
        f.pautar(260, passo)
        return f, 200, 260 + passo - 12, passo
    return f, M + 40, M + 160, 82


def _assinatura_com_nome(f: Folha, x, y, esc: Escritor, nome: str, presente: bool, rotulo: str | None = None, largura=620):
    if presente:
        f.assinatura(x, y, x + largura, y + 100, esc, nome)
    f.linha(x - 10, y + 105, x + largura + 10, y + 105, 1)
    f.texto((x + largura / 2, y + 112), rotulo or nome.title(), 20, anchor="ma", max_w=largura)


def _doc(tipo, paginas, dados, nc):
    d = DocGerado(tipo, paginas, dados, [{"regra": nc, "descricao": DESCRICAO_NC_RH.get(nc) or _nc(nc)[0]["descricao"]}] if nc else [])
    return d


# ============================================================================ 1. pedido de demissão
@registrado
def pedido_demissao(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    f, x, y, passo = _papel_carta(rng)
    larg = A4[0] - x - M
    d = date.fromisoformat(e.desligado_em) - timedelta(days=30) if e.desligado_em else _hoje(u) - timedelta(days=rng.randint(1, 20))
    cumprir = rng.choice([True, False, None])
    cpf = f.talvez(e.cpf, "empregado_cpf")
    f.mao((x + larg * 0.35, y), f"{e.end.municipio}, {data_extenso(d)}", esc, tam=40)
    y += passo * 2
    f.mao((x, y), f"À {empresa.razao_social.title()}", esc, tam=40, max_w=larg)
    y += passo
    f.mao((x, y), "Departamento Pessoal", esc, tam=40)
    y += passo * 2
    f.mao((x + larg * 0.3, y), "Pedido de Demissão", esc, tam=46)
    y += passo * 2
    corpo = (f"Eu, {e.nome.title()}" + (f", portador(a) do CPF {fmt_cpf(cpf)}," if cpf else ",")
             + f" ocupante do cargo de {e.cargo.lower()}, venho por meio desta solicitar meu desligamento da empresa"
             + rng.choice([" por motivos pessoais.", " por ter recebido outra proposta de trabalho.", "."]))
    if cumprir is True:
        corpo += " Informo que irei cumprir o aviso prévio de 30 dias."
    elif cumprir is False:
        corpo += " Solicito a dispensa do cumprimento do aviso prévio."
    y = f.linhas_mao(x, y, larg, corpo, esc, tam=40, entrelinha=passo / 40)
    y += passo
    f.mao((x, y), rng.choice(["Atenciosamente,", "Sem mais,", "Grato(a),"]), esc, tam=40)
    y += passo * 2
    assina = nc != "sem_assinatura"
    if assina:
        f.assinatura(x + 60, y - 70, x + 700, y + 20, esc, e.nome)
    f.mao((x + 60, y + passo), e.nome.title(), esc, tam=36)
    dados = sch.PedidoDemissao(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social.title(),
                               empregador_cnpj=None, empregado_nome=e.nome.title(), empregado_cpf=cpf, data_documento=d.isoformat(),
                               assinatura_empregado_presente=assina, cumprira_aviso_previo=cumprir)
    return _doc(T.PEDIDO_DEMISSAO, [f.finalizar()], dados, nc)


# ============================================================================ 2. atestado médico
@registrado
def atestado_medico(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    fk = _fk(rng)
    esc = Escritor.aleatorio(rng, "medico")
    medico = f"Dr(a). {fk.first_name()} {fk.last_name()}"
    crm = None if nc == "atestado_sem_crm" else f"CRM-PE {rng.randint(5000, 39999)}"
    clinica = f"Clínica {fk.last_name()} – Medicina Geral"
    d = _hoje(u) - timedelta(days=rng.randint(3, 60))
    dias = rng.choice([1, 1, 2, 3, 3, 5, 7, 10, 15])
    cid = rng.random() < 0.5
    pequeno = rng.random() < 0.5  # receituário meia folha
    tam = (A4[0], A4[1] // 2 + 120) if pequeno else A4
    f = Folha(rng, tam)
    f.texto((f.w / 2, 60), clinica.upper(), 34, bold=True, anchor="ma")
    f.texto((f.w / 2, 110), f"(estabelecimento fictício) · {e.end.municipio}/PE · Tel. (00) 0000-{rng.randint(1000, 9999)}", 20, anchor="ma")
    f.linha(M, 150, f.w - M, 150, 3, (60, 90, 150))
    y = 230
    f.mao((f.w / 2 - 170, y), "ATESTADO", esc, tam=60, sem_defeito=True)
    y += 110
    texto = (f"Atesto para os devidos fins que {e.nome.title()} esteve sob meus cuidados nesta data, "
             f"necessitando de {dias} ({extenso_int(dias)}) dia{'s' if dias > 1 else ''} de afastamento de suas atividades "
             f"a partir de {fmt_data(d.isoformat())}.")
    y = f.linhas_mao(M + 40, y, f.w - 2 * M - 80, texto, esc, tam=44, entrelinha=1.7)
    if cid:
        f.mao((M + 40, y + 10), f"CID {rng.choice(['J06.9', 'A09', 'M54.5', 'R51', 'J11'])}", esc, tam=40, sem_defeito=True)
        y += 70
    y += 40
    f.mao((M + 40, y), f"{e.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
    ycar = min(y + 170, f.h - 230)
    f.carimbo(f.w - M - 330, ycar, [medico.upper(), "CLÍNICO GERAL", crm or "MÉDICO"], cor=rng.choice([(40, 60, 140), (60, 60, 60)]))
    f.assinatura(f.w - M - 620, ycar - 90, f.w - M - 60, ycar + 10, esc, medico.split()[1])
    dados = sch.AtestadoMedico(campos_ilegiveis=[], observacoes=None, paciente_nome=e.nome.title(), data_atendimento=d.isoformat(),
                               dias_afastamento=dias, cid_informado=cid, medico_nome=medico, medico_crm=crm, carimbo_presente=True,
                               assinatura_medico_presente=True)
    return _doc(T.ATESTADO_MEDICO, [f.finalizar()], dados, nc)


# ============================================================================ 3. declaração de próprio punho
@registrado
def declaracao_manuscrita(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None, assunto: str | None = None) -> DocGerado:
    fk = _fk(rng)
    esc = Escritor.aleatorio(rng)
    f, x, y, passo = _papel_carta(rng)
    larg = A4[0] - x - M
    assunto = assunto or rng.choice(["RESIDENCIA", "DEPENDENTES", "NAO_ACUMULO_EMPREGO"])
    d = _hoje(u) - timedelta(days=rng.randint(1, 200))
    cpf = f.talvez(e.cpf, "empregado_cpf")
    f.mao((x + larg * 0.33, y), "DECLARAÇÃO", esc, tam=54, sem_defeito=True)
    y += passo * 2
    ident = f"Eu, {e.nome.title()}" + (f", CPF {fmt_cpf(cpf)}," if cpf else ",")
    endereco = None
    if assunto == "RESIDENCIA":
        endereco = e.end.completo
        corpo = f"{ident} declaro para os devidos fins que resido no endereço {endereco}, CEP {e.end.cep[:5]}-{e.end.cep[5:]}."
    elif assunto == "DEPENDENTES":
        filhos = [f"{fk.first_name()} {e.nome.split()[-1].title()}" for _ in range(rng.randint(1, 3))]
        corpo = f"{ident} declaro que possuo como dependente(s): " + ", ".join(f"{n} (filho/a)" for n in filhos) + "."
    else:
        corpo = f"{ident} declaro para os devidos fins que não possuo outro vínculo empregatício além da empresa {empresa.razao_social.title()}."
    corpo += " Por ser verdade, firmo a presente declaração."
    y = f.linhas_mao(x, y, larg, corpo, esc, tam=40, entrelinha=passo / 40) + passo
    f.mao((x + larg * 0.3, y), f"{e.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
    y += passo * 2
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, x + 200, y, esc, e.nome, assina)
    dados = sch.DeclaracaoManuscrita(campos_ilegiveis=[], observacoes=None, empregado_nome=e.nome.title(), empregado_cpf=cpf,
                                     data_documento=d.isoformat(), assinatura_empregado_presente=assina, assunto=assunto, endereco=endereco)
    return _doc(T.DECLARACAO_MANUSCRITA, [f.finalizar()], dados, nc)


# ============================================================================ 4. recibo avulso
@registrado
def recibo_avulso(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    tipo = rng.choice(["ADIANTAMENTO", "VALE", "DIARIA"])
    d = _hoje(u) - timedelta(days=rng.randint(1, 90))
    if tipo == "ADIANTAMENTO":
        valor = round(e.salario * 0.4, 2)
        ref = f"adiantamento salarial de {MESES[d.month - 1].lower()}/{d.year}"
    elif tipo == "VALE":
        valor = float(rng.choice([50, 80, 100, 150, 200, 250]))
        ref = "vale (desconto em folha)"
    else:
        n = rng.randint(1, 5)
        valor = float(n * rng.choice([80, 90, 100, 120]))
        ref = f"{n} diária(s) de serviço"
    cpf = None
    f = Folha(rng)
    for via in range(2 if rng.random() < 0.4 else 1):  # bloco com 2 recibos por folha (canhoto)
        y0 = M + via * 1130
        f.caixa(M, y0, A4[0] - M, y0 + 1000, 3)
        f.texto((M + 30, y0 + 30), "RECIBO", 54, bold=True)
        f.texto((A4[0] - M - 470, y0 + 40), "R$", 40, bold=True)
        f.caixa(A4[0] - M - 410, y0 + 25, A4[0] - M - 30, y0 + 100, 2)
        if via == 0:
            f.mao((A4[0] - M - 390, y0 + 85), brl(valor), esc, tam=46)
        y = y0 + 190
        linhas = [("Recebi(emos) de", empresa.razao_social.title()), ("a quantia de", extenso_reais(valor)),
                  ("referente a", ref), ("", "")]
        for rot, val in linhas:
            if rot:
                f.texto((M + 30, y - 10), rot, 26, anchor="ls")
            f.linha(M + 290, y, A4[0] - M - 30, y, 1, (90, 90, 90))
            if val and via == 0:
                y_txt = y - 8
                f.mao((M + 300, y_txt), val, esc, tam=40, max_w=A4[0] - 2 * M - 340)
            y += 110
        if via == 0:
            cpf = f.talvez(e.cpf, "recebedor_cpf")
            f.mao((M + 30, y + 30), f"{e.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
            assina = nc != "sem_assinatura"
            if assina:
                f.assinatura(A4[0] - M - 700, y - 40, A4[0] - M - 80, y + 60, esc, e.nome)
            f.linha(A4[0] - M - 720, y + 65, A4[0] - M - 50, y + 65, 1)
            f.mao((A4[0] - M - 700, y + 140), e.nome.title(), esc, tam=34, max_w=640)
            if cpf:
                f.mao((A4[0] - M - 700, y + 210), f"CPF {fmt_cpf(cpf)}", esc, tam=34)
        else:
            f.texto((A4[0] / 2, y0 + 700), "(via em branco do bloco)", 22, anchor="mm", cor=(150, 150, 150))
    dados = sch.ReciboAvulso(campos_ilegiveis=[], observacoes=None, tipo_pagamento=tipo, valor=valor, valor_por_extenso=extenso_reais(valor),
                             recebedor_nome=e.nome.title(), recebedor_cpf=cpf, pagador_nome=empresa.razao_social.title(),
                             referente_a=ref, data_documento=d.isoformat(), assinatura_recebedor_presente=nc != "sem_assinatura")
    return _doc(T.RECIBO_AVULSO, [f.finalizar()], dados, nc)


# ============================================================================ 5. justificativa de falta/atraso
MOTIVOS_FALTA = ["consulta médica do filho", "problema com o transporte público", "ônibus quebrou no caminho",
                 "chuva forte e alagamento na rua", "precisei resolver problema no banco", "doença na família",
                 "comparecimento a audiência", "falecimento de parente"]


@registrado
def justificativa_falta(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    tipo = rng.choice(["FALTA", "ATRASO"])
    oc = _hoje(u) - timedelta(days=rng.randint(2, 60))
    d = oc + timedelta(days=rng.randint(0, 2))
    motivo = rng.choice(MOTIVOS_FALTA)
    assina = nc != "sem_assinatura"
    visto = rng.random() < 0.7
    if rng.random() < 0.5:  # formulário impresso
        f = Folha(rng)
        y = _cabecalho(f, empresa, "JUSTIFICATIVA", "Ausência / Atraso") + 40
        f.campo(M, y, 1100, y + 95, "Empregado", e.nome.title(), esc)
        f.campo(1100, y, A4[0] - M, y + 95, "Matrícula", e.matricula, esc)
        y += 130
        f.checkbox(M + 20, y, "Falta", tipo == "FALTA", esc, 28)
        f.checkbox(M + 300, y, "Atraso", tipo == "ATRASO", esc, 28)
        f.campo(M + 650, y - 25, A4[0] - M, y + 70, "Data da ocorrência", fmt_data(oc.isoformat()), esc)
        y += 110
        f.texto((M, y), "Motivo:", 26, bold=True)
        for i in range(4):
            f.linha(M, y + 90 + i * 80, A4[0] - M, y + 90 + i * 80, 1, (120, 120, 120))
        f.linhas_mao(M + 10, y + 80, A4[0] - 2 * M - 20, motivo.capitalize() + ".", esc, tam=42, entrelinha=80 / 42)
        y += 450
        f.mao((M, y), fmt_data(d.isoformat()), esc, tam=40)
        _assinatura_com_nome(f, M + 650, y - 60, esc, e.nome, assina, "Assinatura do empregado")
        y += 260
        _assinatura_com_nome(f, M + 650, y - 60, Escritor.aleatorio(rng), "Chefia", visto, "Visto da chefia imediata")
    else:  # bilhete de próprio punho
        f, x, y, passo = _papel_carta(rng)
        larg = A4[0] - x - M
        texto = (f"Eu, {e.nome.title()}, venho justificar {'minha falta' if tipo == 'FALTA' else 'meu atraso'} "
                 f"no dia {fmt_data(oc.isoformat())}, pois {motivo}. Peço a compreensão da empresa.")
        f.mao((x, y), f"{e.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
        y = f.linhas_mao(x, y + passo * 2, larg, texto, esc, tam=40, entrelinha=passo / 40) + passo * 2
        if assina:
            f.assinatura(x + 200, y - 80, x + 800, y + 10, esc, e.nome)
        f.mao((x + 220, y + passo), e.nome.title(), esc, tam=36)
        if visto:
            f.mao((x + 900, y + passo * 3), "ciente", Escritor.aleatorio(rng, "pressa"), tam=46, sem_defeito=True)
            f.assinatura(x + 900, y + passo * 3, x + 1300, y + passo * 4 + 20, Escritor.aleatorio(rng), "Chefia")
    dados = sch.JustificativaFalta(campos_ilegiveis=[], observacoes=None, empregado_nome=e.nome.title(), empregado_cpf=None,
                                   data_documento=d.isoformat(), assinatura_empregado_presente=assina, tipo_ocorrencia=tipo,
                                   data_ocorrencia=oc.isoformat(), motivo=motivo, visto_chefia_presente=visto)
    return _doc(T.JUSTIFICATIVA_FALTA, [f.finalizar()], dados, nc)


# ============================================================================ 6 e 25. advertência / suspensão
MOTIVOS_DISC = ["atrasos reiterados sem justificativa", "ausência injustificada ao serviço", "não utilização do EPI obrigatório",
                "abandono do posto de trabalho durante o expediente", "uso de celular em área proibida", "descumprimento de ordem do supervisor"]


@registrado
def advertencia(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    medida = rng.choice(["ADVERTENCIA", "ADVERTENCIA", "SUSPENSAO"])
    dias = rng.choice([1, 2, 3]) if medida == "SUSPENSAO" else None
    motivo = rng.choice(MOTIVOS_DISC)
    d = _hoje(u) - timedelta(days=rng.randint(2, 120))
    ciencia = "SEM_CIENCIA" if nc == "sem_ciencia" else rng.choices(["CIENTE", "RECUSA"], [0.75, 0.25])[0]
    if nc == "recusa_sem_testemunhas":
        ciencia = "RECUSA"
    n_test = (rng.choice([0, 1]) if nc == "recusa_sem_testemunhas" else 2) if ciencia == "RECUSA" else rng.choice([0, 0, 2])
    esc_sup, esc_emp = Escritor.aleatorio(rng), Escritor.aleatorio(rng)
    titulo = "ADVERTÊNCIA DISCIPLINAR" if medida == "ADVERTENCIA" else "SUSPENSÃO DISCIPLINAR"
    texto = (f"Sr(a). {e.nome.title()}, pela presente fica V.Sa. {'advertido(a)' if medida == 'ADVERTENCIA' else 'suspenso(a)'} "
             + (f"por {dias} ({extenso_int(dias)}) dia(s), " if dias else "")
             + f"em razão de {motivo}. Solicitamos que tal fato não se repita, sob pena de aplicação das demais medidas previstas na CLT.")
    manuscrita = rng.random() < 0.35
    if manuscrita:
        f, x, y, passo = _papel_carta(rng)
        larg = A4[0] - x - M
        f.mao((x + larg * 0.2, y), titulo.title(), esc_sup, tam=50, sem_defeito=True)
        y += passo * 2
        f.mao((x, y), f"Empresa: {empresa.razao_social.title()}", esc_sup, tam=38, max_w=larg)
        y = f.linhas_mao(x, y + passo * 2, larg, texto, esc_sup, tam=40, entrelinha=passo / 40)
        f.mao((x, y + passo // 2), f"{empresa.end.municipio}, {fmt_data(d.isoformat())}", esc_sup, tam=40)
        y += passo * 3
    else:
        f = Folha(rng)
        y = _cabecalho(f, empresa, titulo) + 80
        y = f.paragrafo(M + 20, y, A4[0] - 2 * M - 40, texto, 28, entrelinha=1.6) + 50
        f.texto((M + 20, y), f"{empresa.end.municipio}, {fmt_data(d.isoformat())}.", 28)
        y += 80
    x = M + 40
    _assinatura_com_nome(f, x, y, Escritor.aleatorio(rng), "Empresa", True, "Empregador / preposto", 560)
    y += 190
    assina_emp = ciencia == "CIENTE"
    if ciencia == "CIENTE":
        f.mao((x, y), rng.choice(["Estou ciente.", "Ciente.", "Ciente em"]) + f" {fmt_data(d.isoformat())}", esc_emp, tam=40)
        _assinatura_com_nome(f, x + 700, y - 60, esc_emp, e.nome, True, "Empregado(a)", 560)
    elif ciencia == "RECUSA":
        f.mao((x, y), "O(a) empregado(a) recusou-se a assinar.", esc_sup, tam=40)
    y += 190
    fk = _fk(rng)
    for i in range(n_test):
        nome_t = f"{fk.first_name()} {fk.last_name()}"
        _assinatura_com_nome(f, x + i * 720, y, Escritor.aleatorio(rng), nome_t, True, f"Testemunha {i + 1}: {nome_t}", 560)
    dados = sch.AdvertenciaSuspensao(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social if not manuscrita else empresa.razao_social.title(),
                                     empregador_cnpj=None if manuscrita else empresa.cnpj, empregado_nome=e.nome.title(), empregado_cpf=None,
                                     medida=medida, forma="MANUSCRITA" if manuscrita else "IMPRESSA", data_documento=d.isoformat(),
                                     motivo=motivo, dias_suspensao=dias, ciencia=ciencia, assinatura_empregado_presente=assina_emp,
                                     quantidade_testemunhas=n_test)
    return _doc(T.ADVERTENCIA_SUSPENSAO, [f.finalizar()], dados, nc)


# ============================================================================ 7. anotação em carteira (layout genérico)
@registrado
def ctps_anotacao(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    """Carteira aberta (duas páginas pequenas) num scanner A4. Layout GENÉRICO, sem brasão nem elementos oficiais."""
    esc = Escritor.aleatorio(rng, rng.choice(["forma", "cursiva"]))
    tipo = rng.choice(["CONTRATO", "ALTERACAO_SALARIAL", "FERIAS"])
    adm = date.fromisoformat(e.admissao)
    hoje = _hoje(u)
    pw, ph = 720, 1000
    pag = Folha(rng, (pw, ph), (246, 241, 226))
    pag.caixa(4, 4, pw - 5, ph - 5, 2, (150, 140, 120))
    titulos = {"CONTRATO": "CONTRATO DE TRABALHO", "ALTERACAO_SALARIAL": "ALTERAÇÕES DE SALÁRIO", "FERIAS": "FÉRIAS"}
    pag.texto((pw / 2, 30), titulos[tipo], 28, bold=True, anchor="ma")
    pag.texto((pw / 2, 68), "modelo genérico – não é documento oficial", 15, anchor="ma", cor=(150, 60, 60))
    cargo = salario = fi = ff = None
    y = 120
    if tipo == "CONTRATO":
        data_anot, cargo, salario = adm, e.cargo.title(), e.salario
        for rot, val in [("Empregador", empresa.razao_social.title()), ("CNPJ", fmt_cnpj(empresa.cnpj)),
                         ("Município", f"{empresa.end.municipio}/PE"), ("Cargo", cargo), ("Data admissão", fmt_data(adm.isoformat())),
                         ("Remuneração", f"R$ {brl(salario)} por mês")]:
            pag.texto((24, y), rot, 18, cor=(90, 80, 60))
            pag.linha(24, y + 80, pw - 24, y + 80, 1, (170, 160, 140))
            pag.mao((30, y + 72), val, esc, tam=34, max_w=pw - 60)
            y += 112
    elif tipo == "ALTERACAO_SALARIAL":
        data_anot = adm + timedelta(days=rng.randint(200, max(201, (hoje - adm).days)))
        salario = round(e.salario * rng.uniform(1.04, 1.12) / 10) * 10.0
        cargo = e.cargo.title()
        txt = f"Em {fmt_data(data_anot.isoformat())} passou a perceber R$ {brl(salario)} mensais, no cargo de {cargo}, por motivo de {rng.choice(['reajuste coletivo', 'promoção', 'mérito'])}."
        pag.linhas_mao(30, y + 60, pw - 60, txt, esc, tam=34, entrelinha=2.1)
        y += 560
    else:
        fi = adm + timedelta(days=365 + rng.randint(10, 200))
        if fi > hoje:
            fi = hoje - timedelta(days=rng.randint(30, 120))
        ff = fi + timedelta(days=29)
        data_anot = fi
        txt = (f"Gozou férias de {fmt_data(fi.isoformat())} a {fmt_data(ff.isoformat())}, referentes ao período aquisitivo "
               f"de {fmt_data(adm.isoformat())} a {fmt_data((adm + timedelta(days=364)).isoformat())}.")
        pag.linhas_mao(30, y + 60, pw - 60, txt, esc, tam=34, entrelinha=2.1)
        y += 560
    rs = empresa.razao_social.split()
    meio_nome = len(rs) // 2 + 1
    pag.carimbo(pw * 0.45, ph - 150, [" ".join(rs[:meio_nome]), " ".join(rs[meio_nome:]), f"CNPJ {fmt_cnpj(empresa.cnpj)}"])
    pag.assinatura(pw * 0.25, ph - 210, pw - 40, ph - 120, Escritor.aleatorio(rng), "Empregador")
    pag.finalizar()
    vazia = Folha(rng, (pw, ph), (246, 241, 226))
    vazia.caixa(4, 4, pw - 5, ph - 5, 2, (150, 140, 120))
    vazia.texto((pw / 2, 30), titulos[tipo], 28, bold=True, anchor="ma")
    for yy in range(160, ph - 80, 112):
        vazia.linha(24, yy, pw - 24, yy, 1, (170, 160, 140))
    vazia.finalizar()
    f = Folha(rng)
    x0, y0 = rng.randint(60, 120), rng.randint(80, 300)
    livro = Image.new("RGB", (pw * 2 + 10, ph + 10), (70, 80, 110))  # capa genérica aparecendo
    esquerda, direita = (pag.img, vazia.img) if rng.random() < 0.5 else (vazia.img, pag.img)
    livro.paste(esquerda, (5, 5))
    livro.paste(direita, (pw + 5, 5))
    sombra = Image.new("L", livro.size, 0)
    ImageDraw.Draw(sombra).rectangle([pw - 6, 0, pw + 16, ph + 10], fill=90)
    livro.paste((60, 60, 60), (0, 0), sombra.filter(ImageFilter.GaussianBlur(8)))
    livro = livro.rotate(rng.uniform(-3, 3), expand=True, fillcolor=(255, 255, 255))
    f.img.paste(livro, (x0, y0))
    dados = sch.CTPSAnotacao(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social.title() if tipo == "CONTRATO" else empresa.razao_social,
                             empregador_cnpj=empresa.cnpj, tipo_anotacao=tipo, data_anotacao=data_anot.isoformat(), cargo=cargo,
                             salario=salario, ferias_inicio=fi.isoformat() if fi else None, ferias_fim=ff.isoformat() if ff else None,
                             carimbo_presente=True, assinatura_empregador_presente=True)
    return _doc(T.CTPS_ANOTACAO, [f.finalizar()], dados, nc)


# ============================================================================ 10. ficha de registro com foto 3x4
def _foto_generica(rng) -> Image.Image:
    """Silhueta genérica (sem rosto) no lugar da foto 3x4."""
    w, h = 240, 320
    img = Image.new("RGB", (w, h), rng.choice([(200, 210, 225), (225, 225, 225), (210, 225, 210)]))
    d = ImageDraw.Draw(img)
    cor = (120, 125, 135)
    d.ellipse([w * 0.3, h * 0.18, w * 0.7, h * 0.55], fill=cor)
    d.ellipse([w * 0.1, h * 0.6, w * 0.9, h * 1.25], fill=cor)
    d.text((w / 2, h - 18), "FOTO", fill=(240, 240, 240), anchor="mm")
    return img.rotate(rng.uniform(-4, 4), expand=True, fillcolor=(255, 255, 255))


@registrado
def ficha_registro(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng, rng.choice(["forma", "cursiva"]))
    f = Folha(rng, fundo=(252, 249, 240))
    f.caixa(M - 30, M - 30, A4[0] - M + 30, A4[1] - M, 5, (60, 50, 40))
    f.texto((A4[0] / 2, M + 10), "FICHA DE REGISTRO DE EMPREGADO", 40, bold=True, anchor="ma")
    f.texto((A4[0] / 2, M + 65), f"Folha nº {rng.randint(1, 400):03d}", 24, anchor="ma")
    f.campo(M, M + 120, A4[0] - M, M + 200, "Empregador", f"{empresa.razao_social} – CNPJ {fmt_cnpj(empresa.cnpj)}", tam_valor=24)
    foto = rng.random() < 0.85
    fx, fy = A4[0] - M - 300, M + 240
    f.caixa(fx, fy, fx + 260, fy + 340, 2)
    if foto:
        img = _foto_generica(rng)
        f.img.paste(img, (fx + 10, fy + 8))
        f.d.rectangle([fx + 90, fy - 6, fx + 170, fy + 12], fill=(230, 225, 200))  # fita adesiva
    else:
        f.texto((fx + 130, fy + 170), "Foto 3x4", 24, anchor="mm", cor=(150, 150, 150))
    y = M + 240
    larg = fx - M - 20
    pis = f.talvez(e.pis, "empregado_pis")
    for rot, val in [("Nome", e.nome.title()), ("CPF", fmt_cpf(e.cpf)), ("PIS/PASEP", pis), ("Data de nascimento", fmt_data(e.nascimento))]:
        f.campo(M, y, M + larg, y + 85, rot, val, esc)
        y += 85
    y = max(y, fy + 360)
    linhas = [("Endereço", e.end.completo, A4[0] - M), ]
    f.campo(M, y, A4[0] - M, y + 90, "Endereço", e.end.completo, esc)
    y += 90
    f.campo(M, y, 700, y + 90, "Matrícula", e.matricula, esc)
    f.campo(700, y, A4[0] - M, y + 90, "Cargo", e.cargo.title(), esc)
    y += 90
    f.campo(M, y, 700, y + 90, "Data de admissão", fmt_data(e.admissao), esc)
    f.campo(700, y, A4[0] - M, y + 90, "Salário inicial", f"R$ {brl(e.salario)}", esc)
    y += 90
    f.campo(M, y, A4[0] - M, y + 90, "Horário de trabalho", " – ".join(e.jornada), esc)
    y += 130
    f.texto((M, y), "Observações / alterações:", 24, bold=True)
    for i in range(6):
        f.linha(M, y + 90 + i * 80, A4[0] - M, y + 90 + i * 80, 1, (150, 140, 130))
    y += 620
    _assinatura_com_nome(f, M + 40, y, esc, e.nome, True, "Assinatura do empregado", 600)
    _assinatura_com_nome(f, A4[0] - M - 640, y, Escritor.aleatorio(rng), "Empregador", True, "Empregador", 600)
    del linhas
    dados = sch.FichaRegistro(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                              empregado_nome=e.nome.title(), empregado_cpf=e.cpf, empregado_pis=pis, matricula=e.matricula,
                              data_admissao=e.admissao, cargo=e.cargo.title(), salario=e.salario, foto_presente=foto)
    return _doc(T.FICHA_REGISTRO, [f.finalizar()], dados, nc)


# ============================================================================ 11. lista de presença
TREINAMENTOS = [("NR-35 – Trabalho em Altura", 8), ("NR-10 – Segurança em Eletricidade", 40), ("NR-6 – Uso correto de EPI", 2),
                ("NR-23 – Prevenção e Combate a Incêndio", 4), ("NR-17 – Ergonomia", 2), ("Integração de SST", 4), ("NR-33 – Espaço Confinado", 16)]


@registrado
def lista_presenca(rng, u: Universo, empresa: Empresa, nc=None) -> DocGerado:
    fk = _fk(rng)
    tema, ch = rng.choice(TREINAMENTOS)
    d = _hoje(u) - timedelta(days=rng.randint(5, 200))
    instrutor = f"{fk.first_name()} {fk.last_name()}"
    pessoas = u.empregados_de(empresa.cnpj)[:]
    rng.shuffle(pessoas)
    pessoas = pessoas[:rng.randint(5, 14)]
    sem_ass = rng.randrange(len(pessoas)) if nc == "presenca_sem_assinatura" else None
    cpf_ruim = rng.randrange(len(pessoas)) if nc == "cpf_invalido" else None
    f = Folha(rng)
    y = _cabecalho(f, empresa, "LISTA DE PRESENÇA", "Treinamento") + 20
    f.campo(M, y, A4[0] - M, y + 75, "Treinamento", tema, tam_valor=26)
    y += 75
    f.campo(M, y, 600, y + 75, "Data", fmt_data(d.isoformat()), tam_valor=26)
    f.campo(600, y, 900, y + 75, "Carga horária", f"{ch} h", tam_valor=26)
    f.campo(900, y, A4[0] - M, y + 75, "Instrutor", instrutor, tam_valor=26)
    y += 100
    larg = [80, 640, 340, A4[0] - 2 * M - 1060]
    alt = 100
    y_tab = y
    f.tabela(M, y, larg, alt, ["Nº", "Nome (letra legível)", "CPF", "Assinatura"], [[str(i + 1), "", "", ""] for i in range(14)], tam=22)
    participantes = []
    for i, p in enumerate(pessoas):
        esc = Escritor.aleatorio(rng)
        yy = y_tab + alt * (i + 2) - 22
        f.mao((M + larg[0] + 10, yy), p.nome.title(), esc, tam=36, max_w=larg[1] - 20)
        cpf = p.cpf if i != cpf_ruim else p.cpf[:-1] + str((int(p.cpf[-1]) + 3) % 10)
        cpf = cpf if rng.random() > f.taxa_branco else None
        if cpf:
            f.mao((M + larg[0] + larg[1] + 10, yy), fmt_cpf(cpf), esc, tam=34, max_w=larg[2] - 20)
        else:
            f.defeitos.append({"defeito": "campo_em_branco", "campo": "participantes.cpf"})
        assina = i != sem_ass
        if assina:
            x0 = M + sum(larg[:3])
            f.assinatura(x0 + 15, yy - alt + 30, x0 + larg[3] - 15, yy + 10, esc, p.nome)
        participantes.append(sch.Participante(nome=p.nome.title(), cpf=cpf, assinatura_presente=assina))
    y = y_tab + alt * 15 + 50
    _assinatura_com_nome(f, A4[0] - M - 640, y, Escritor.aleatorio(rng), instrutor, True, f"Instrutor: {instrutor}", 600)
    dados = sch.ListaPresenca(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                              treinamento=tema, data=d.isoformat(), carga_horaria_horas=float(ch), instrutor=instrutor, participantes=participantes)
    return _doc(T.LISTA_PRESENCA, [f.finalizar()], dados, nc)


# ============================================================================ 13. ordem de serviço SST
RISCOS_FUNCAO = ["Ruído", "Queda de mesmo nível", "Queda de altura", "Choque elétrico", "Produtos químicos de limpeza",
                 "Postura inadequada", "Cortes e perfurações", "Agentes biológicos"]


@registrado
def ordem_servico(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    riscos = rng.sample(RISCOS_FUNCAO, rng.randint(2, 4))
    d = date.fromisoformat(e.admissao) + timedelta(days=rng.randint(0, 3))
    f = Folha(rng)
    y = _cabecalho(f, empresa, "ORDEM DE SERVIÇO", "Segurança e Saúde no Trabalho – NR-1") + 30
    f.campo(M, y, 1100, y + 80, "Empregado", e.nome, tam_valor=26)
    f.campo(1100, y, A4[0] - M, y + 80, "CPF", fmt_cpf(e.cpf), tam_valor=26)
    y += 80
    f.campo(M, y, A4[0] - M, y + 80, "Função", e.cargo, tam_valor=26)
    y += 120
    secoes = [("1. Riscos da função", "; ".join(riscos) + "."),
              ("2. Medidas de prevenção", "Seguir os procedimentos operacionais, manter o local limpo e organizado, sinalizar áreas de risco e "
               "comunicar imediatamente ao supervisor qualquer condição insegura."),
              ("3. EPIs obrigatórios", "Utilizar durante toda a jornada os equipamentos de proteção fornecidos e registrados na ficha de EPI."),
              ("4. Proibições", "É proibido executar tarefas para as quais não foi treinado, remover proteções de máquinas e "
               "permanecer em áreas restritas sem autorização."),
              ("5. Penalidades", "O descumprimento desta ordem de serviço constitui ato faltoso, sujeito às penalidades previstas em lei.")]
    for tit, txt in secoes:
        f.texto((M, y), tit, 27, bold=True)
        y = f.paragrafo(M + 20, y + 45, A4[0] - 2 * M - 40, txt, 25) + 25
    y += 30
    y = f.paragrafo(M, y, A4[0] - 2 * M, "Declaro ter recebido, lido e compreendido esta Ordem de Serviço, comprometendo-me a cumpri-la.", 25) + 60
    f.mao((M, y + 40), f"{empresa.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, A4[0] - M - 680, y - 30, esc, e.nome, assina, "Assinatura do empregado", 620)
    dados = sch.OrdemServicoSST(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                empregado_nome=e.nome, empregado_cpf=e.cpf, data_documento=d.isoformat(), assinatura_empregado_presente=assina,
                                funcao=e.cargo, riscos=riscos)
    return _doc(T.ORDEM_SERVICO_SST, [f.finalizar()], dados, nc)


# ============================================================================ 14. vale-transporte
@registrado
def declaracao_vt(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    optante = rng.random() < 0.75
    d = date.fromisoformat(e.admissao) + timedelta(days=rng.randint(0, 2))
    linhas = []
    if optante:
        for _ in range(rng.randint(1, 3)):
            linhas.append(sch.LinhaTransporte(linha=f"{rng.randint(10, 999):03d} – {e.end.bairro[:18]}/{rng.choice(['Centro', 'Terminal', 'Shopping'])}",
                                              tarifa=rng.choice([4.10, 4.30, 4.50, 4.80]), viagens_por_dia=2))
    f = Folha(rng)
    y = _cabecalho(f, empresa, "VALE-TRANSPORTE", "Declaração de opção") + 40
    f.campo(M, y, 1100, y + 95, "Empregado", e.nome.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "CPF", fmt_cpf(e.cpf), esc)
    y += 95
    f.campo(M, y, A4[0] - M, y + 95, "Endereço residencial", e.end.completo, esc)
    y += 140
    f.checkbox(M + 20, y, "OPTO pela utilização do vale-transporte", optante, esc, 26)
    f.checkbox(M + 20, y + 60, "NÃO OPTO pela utilização do vale-transporte", not optante, esc, 26)
    y += 150
    f.texto((M, y), "Linhas utilizadas no trajeto residência–trabalho–residência:", 25, bold=True)
    y += 50
    tab = [[l.linha, brl(l.tarifa), str(l.viagens_por_dia)] for l in linhas] + [["", "", ""]] * (5 - len(linhas))
    y = f.tabela(M, y, [900, 300, A4[0] - 2 * M - 1200], 85, ["Linha / trajeto", "Tarifa (R$)", "Viagens/dia"], tab, esc, cols_mao={0, 1, 2}, tam=22) + 50
    y = f.paragrafo(M, y, A4[0] - 2 * M, "Comprometo-me a utilizar o vale-transporte exclusivamente no deslocamento residência–trabalho e a "
                    "atualizar esta declaração sempre que houver mudança de endereço ou de trajeto.", 24) + 70
    f.mao((M, y + 40), f"{e.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, A4[0] - M - 680, y - 30, esc, e.nome, assina, "Assinatura do empregado", 620)
    dados = sch.DeclaracaoValeTransporte(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                         empregado_nome=e.nome.title(), empregado_cpf=e.cpf, data_documento=d.isoformat(),
                                         assinatura_empregado_presente=assina, opcao="OPTANTE" if optante else "NAO_OPTANTE",
                                         endereco_residencial=e.end.completo, linhas=linhas)
    return _doc(T.DECLARACAO_VALE_TRANSPORTE, [f.finalizar()], dados, nc)


# ============================================================================ 15. dependentes
@registrado
def declaracao_dependentes(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    fk = _fk(rng)
    esc = Escritor.aleatorio(rng)
    hoje = _hoje(u)
    deps = []
    if rng.random() < 0.4:
        deps.append(sch.Dependente(nome=f"{fk.first_name()} {fk.last_name()}", parentesco="Cônjuge",
                                   data_nascimento=(hoje - timedelta(days=rng.randint(20 * 365, 50 * 365))).isoformat()))
    for _ in range(rng.randint(0 if deps else 1, 3)):
        deps.append(sch.Dependente(nome=f"{fk.first_name()} {e.nome.split()[-1].title()}", parentesco=rng.choice(["Filho(a)", "Filho(a)", "Enteado(a)"]),
                                   data_nascimento=(hoje - timedelta(days=rng.randint(200, 17 * 365))).isoformat()))
    d = date.fromisoformat(e.admissao) + timedelta(days=rng.randint(0, 3))
    f = Folha(rng)
    y = _cabecalho(f, empresa, "DECLARAÇÃO DE DEPENDENTES", "Salário-família / IRRF") + 40
    f.campo(M, y, 1100, y + 95, "Empregado", e.nome.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "CPF", fmt_cpf(e.cpf), esc)
    y += 140
    tab = [[x.nome, x.parentesco, fmt_data(x.data_nascimento)] for x in deps] + [["", "", ""]] * (6 - len(deps))
    y = f.tabela(M, y, [800, 340, A4[0] - 2 * M - 1140], 90, ["Nome do dependente", "Parentesco", "Data de nascimento"], tab, esc, cols_mao={0, 1, 2}) + 60
    y = f.paragrafo(M, y, A4[0] - 2 * M, "Declaro, sob as penas da lei, que as informações acima são verdadeiras e comprometo-me a comunicar "
                    "qualquer alteração.", 24) + 70
    f.mao((M, y + 40), f"{e.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, A4[0] - M - 680, y - 30, esc, e.nome, assina, "Assinatura do empregado", 620)
    dados = sch.DeclaracaoDependentes(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                      empregado_nome=e.nome.title(), empregado_cpf=e.cpf, data_documento=d.isoformat(),
                                      assinatura_empregado_presente=assina, dependentes=deps)
    return _doc(T.DECLARACAO_DEPENDENTES, [f.finalizar()], dados, nc)


# ============================================================================ 16. recibo de VT / VR
@registrado
def recibo_beneficio(rng, u: Universo, e: Empregado, empresa: Empresa, comp: str, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    beneficio = rng.choice(["VALE_TRANSPORTE", "VALE_REFEICAO", "VALE_ALIMENTACAO"])
    nomes = {"VALE_TRANSPORTE": "VALE-TRANSPORTE", "VALE_REFEICAO": "VALE-REFEIÇÃO", "VALE_ALIMENTACAO": "VALE-ALIMENTAÇÃO"}
    qtd = rng.randint(20, 24) * (2 if beneficio == "VALE_TRANSPORTE" else 1)
    unit = rng.choice([4.30, 4.50]) if beneficio == "VALE_TRANSPORTE" else rng.choice([18.0, 22.0, 25.0])
    total = round(qtd * unit, 2)
    a, m = map(int, comp.split("-"))
    d = date(a, m, 1) - timedelta(days=rng.randint(1, 4))
    f = Folha(rng)
    y = _cabecalho(f, empresa, f"RECIBO DE {nomes[beneficio]}", f"Competência {comp[5:]}/{comp[:4]}") + 50
    f.campo(M, y, 1100, y + 95, "Empregado", e.nome.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "Matrícula", e.matricula, esc)
    y += 95
    f.campo(M, y, 500, y + 95, "Quantidade", str(qtd), esc)
    f.campo(500, y, 1000, y + 95, "Valor unitário (R$)", brl(unit), esc)
    f.campo(1000, y, A4[0] - M, y + 95, "Valor total (R$)", brl(total), esc)
    y += 150
    y = f.paragrafo(M, y, A4[0] - 2 * M, f"Recebi da empresa acima os benefícios discriminados, referentes à competência {comp[5:]}/{comp[:4]}.", 26) + 80
    f.mao((M, y + 40), fmt_data(d.isoformat()), esc, tam=40)
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, A4[0] - M - 680, y - 30, esc, e.nome, assina, "Assinatura do empregado", 620)
    dados = sch.ReciboBeneficio(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                empregado_nome=e.nome.title(), empregado_cpf=None, data_documento=d.isoformat(), assinatura_empregado_presente=assina,
                                beneficio=beneficio, competencia=comp, quantidade=qtd, valor_total=total)
    return _doc(T.RECIBO_BENEFICIO, [f.finalizar()], dados, nc)


# ============================================================================ 17. aviso / recibo de férias
@registrado
def ferias(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    adm = date.fromisoformat(e.admissao)
    hoje = _hoje(u)
    anos = max(1, (hoje - adm).days // 365)
    aq_i = adm + timedelta(days=365 * (anos - 1))
    aq_f = aq_i + timedelta(days=364)
    gi = min(aq_f + timedelta(days=rng.randint(30, 200)), hoje + timedelta(days=30))
    gf = gi + timedelta(days=29)
    subtipo = rng.choice(["AVISO", "RECIBO"])
    bruto = round(e.salario + e.salario / 3, 2)
    liquido = round(bruto - calc.inss(bruto), 2)
    d = gi - timedelta(days=30 if subtipo == "AVISO" else 2)
    manual = rng.random() < 0.6  # formulário de bloco preenchido à mão
    v = esc if manual else None
    f = Folha(rng, (A4[0], A4[1] // 2 + 200))
    for x in range(30, f.w - 30, 26):  # picote do bloco
        f.d.ellipse([x, 18, x + 8, 26], fill=(200, 200, 200))
    f.texto((f.w / 2, 50), f"{subtipo} DE FÉRIAS", 38, bold=True, anchor="ma")
    f.texto((f.w / 2, 100), empresa.razao_social, 24, anchor="ma")
    y = 150
    f.campo(M, y, 1100, y + 90, "Empregado", e.nome.title(), v)
    f.campo(1100, y, A4[0] - M, y + 90, "Matrícula", e.matricula, v)
    y += 90
    f.campo(M, y, 830, y + 90, "Período aquisitivo", f"{fmt_data(aq_i.isoformat())} a {fmt_data(aq_f.isoformat())}", v)
    f.campo(830, y, A4[0] - M, y + 90, "Período de gozo", f"{fmt_data(gi.isoformat())} a {fmt_data(gf.isoformat())}", v)
    y += 90
    f.campo(M, y, 500, y + 90, "Dias", "30", v)
    if subtipo == "RECIBO":
        f.campo(500, y, 1000, y + 90, "Férias + 1/3 (R$)", brl(bruto), v)
        f.campo(1000, y, A4[0] - M, y + 90, "Líquido (R$)", brl(liquido), v)
    y += 130
    frase = ("Comunicamos que suas férias serão concedidas no período acima." if subtipo == "AVISO"
             else f"Recebi a importância líquida de R$ {brl(liquido)} referente às férias acima.")
    y = f.paragrafo(M, y, A4[0] - 2 * M, frase, 25) + 60
    f.mao((M, y + 40), f"{empresa.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=38)
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, A4[0] - M - 680, y - 30, esc, e.nome, assina, "Ciente – empregado", 620)
    dados = sch.Ferias(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=None,
                       empregado_nome=e.nome.title(), empregado_cpf=None, data_documento=d.isoformat(), assinatura_empregado_presente=assina,
                       subtipo=subtipo, aquisitivo_inicio=aq_i.isoformat(), aquisitivo_fim=aq_f.isoformat(), gozo_inicio=gi.isoformat(),
                       gozo_fim=gf.isoformat(), dias=30, valor_liquido=liquido if subtipo == "RECIBO" else None)
    folha = Folha(rng)
    folha.img.paste(f.finalizar().rotate(rng.uniform(-1.5, 1.5), expand=True, fillcolor=(255, 255, 255)), (0, rng.randint(20, 120)))
    return _doc(T.FERIAS, [folha.finalizar()], dados, nc)


# ============================================================================ 18. check-list de integração
ITENS_CHECK = ["Crachá de identificação entregue", "Cadastro biométrico de acesso", "Apresentação das normas internas",
               "Treinamento de integração de SST", "Entrega de uniforme", "Entrega de EPI", "Apresentação ao supervisor do posto",
               "Orientação sobre rotas de fuga", "Senha do sistema de ponto", "Leitura do código de conduta"]


@registrado
def checklist(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc, esc_resp = Escritor.aleatorio(rng), Escritor.aleatorio(rng)
    d = date.fromisoformat(e.admissao) + timedelta(days=rng.randint(0, 5))
    itens = [sch.ItemChecklist(descricao=i, marcado=rng.random() < 0.85) for i in rng.sample(ITENS_CHECK, rng.randint(6, 10))]
    f = Folha(rng)
    y = _cabecalho(f, empresa, "CHECK-LIST DE INTEGRAÇÃO", "Liberação de acesso") + 40
    f.campo(M, y, 1100, y + 95, "Empregado", e.nome.title(), esc_resp)
    f.campo(1100, y, A4[0] - M, y + 95, "Data", fmt_data(d.isoformat()), esc_resp)
    y += 140
    for it in itens:
        f.checkbox(M + 20, y, it.descricao, it.marcado, esc_resp, 26)
        y += 70
    y += 80
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, M + 20, y, esc, e.nome, assina, "Empregado", 600)
    _assinatura_com_nome(f, A4[0] - M - 640, y, esc_resp, "Responsável", True, "Responsável pela integração", 600)
    dados = sch.ChecklistIntegracao(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                    empregado_nome=e.nome.title(), empregado_cpf=None, data_documento=d.isoformat(), assinatura_empregado_presente=assina,
                                    itens=itens, assinatura_responsavel_presente=True)
    return _doc(T.CHECKLIST_INTEGRACAO, [f.finalizar()], dados, nc)


# ============================================================================ 19. termo de responsabilidade
ITENS_TERMO = ["Camisa do uniforme", "Calça do uniforme", "Crachá funcional", "Rádio comunicador", "Lanterna", "Molho de chaves do posto",
               "Jogo de chaves de fenda", "Alicate universal", "Capa de chuva", "Bota de segurança"]


@registrado
def termo_responsabilidade(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    d = date.fromisoformat(e.admissao) + timedelta(days=rng.randint(0, 10))
    itens = [sch.ItemEntregue(descricao=i, quantidade=rng.choice([1, 1, 2, 3])) for i in rng.sample(ITENS_TERMO, rng.randint(2, 6))]
    f = Folha(rng)
    y = _cabecalho(f, empresa, "TERMO DE RESPONSABILIDADE", "Ferramentas, uniforme e crachá") + 40
    f.campo(M, y, 1100, y + 80, "Empregado", e.nome, tam_valor=26)
    f.campo(1100, y, A4[0] - M, y + 80, "CPF", fmt_cpf(e.cpf), tam_valor=26)
    y += 120
    y = f.paragrafo(M, y, A4[0] - 2 * M, "Recebi os itens abaixo em perfeito estado, comprometendo-me a zelar por sua conservação e a "
                    "devolvê-los ao término do contrato ou quando solicitado, autorizando o desconto em caso de perda ou dano por culpa.", 25) + 40
    tab = [[i.descricao, str(i.quantidade)] for i in itens] + [["", ""]] * (8 - len(itens))
    y = f.tabela(M, y, [1100, A4[0] - 2 * M - 1100], 80, ["Item", "Quantidade"], tab, esc, cols_mao={0, 1}) + 60
    f.mao((M, y + 40), f"{empresa.end.municipio}, {fmt_data(d.isoformat())}", esc, tam=40)
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, A4[0] - M - 680, y - 30, esc, e.nome, assina, "Assinatura do empregado", 620)
    dados = sch.TermoResponsabilidade(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                      empregado_nome=e.nome, empregado_cpf=e.cpf, data_documento=d.isoformat(), assinatura_empregado_presente=assina,
                                      itens=itens)
    return _doc(T.TERMO_RESPONSABILIDADE, [f.finalizar()], dados, nc)


# ============================================================================ 20. ocorrência de acidente / quase-acidente
RELATOS = [("ACIDENTE", "Escorregou no piso molhado próximo à copa e bateu o joelho no chão.", True),
           ("ACIDENTE", "Cortou o dedo ao manusear caixa com grampo solto no almoxarifado.", False),
           ("QUASE_ACIDENTE", "Escada portátil escorregou durante a troca de lâmpada, sem queda do trabalhador.", False),
           ("QUASE_ACIDENTE", "Fio desencapado encontrado próximo ao quadro de energia, isolado antes de contato.", False),
           ("ACIDENTE", "Torceu o tornozelo ao descer a escada de acesso ao estacionamento.", True)]


@registrado
def ocorrencia_acidente(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    fk = _fk(rng)
    esc = Escritor.aleatorio(rng, rng.choice(["pressa", "forma"]))
    tipo, relato, afast = rng.choice(RELATOS)
    afast = afast if tipo == "ACIDENTE" else False
    d = _hoje(u) - timedelta(days=rng.randint(1, 90))
    hora = f"{rng.randint(7, 17):02d}:{rng.choice([0, 10, 20, 30, 40, 50]):02d}"
    local = rng.choice(["Copa do 2º andar", "Almoxarifado", "Estacionamento", "Recepção", "Área técnica"])
    f = Folha(rng)
    test = f.talvez(f"{fk.first_name()} {fk.last_name()}", "testemunha_nome")
    y = _cabecalho(f, empresa, "RELATO DE OCORRÊNCIA", "Acidente / quase-acidente – rascunho p/ CAT") + 40
    f.campo(M, y, 1100, y + 95, "Empregado envolvido", e.nome.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "Matrícula", e.matricula, esc)
    y += 130
    f.checkbox(M + 20, y, "Acidente", tipo == "ACIDENTE", esc, 28)
    f.checkbox(M + 330, y, "Quase-acidente", tipo == "QUASE_ACIDENTE", esc, 28)
    y += 60
    f.campo(M, y, 600, y + 95, "Data", fmt_data(d.isoformat()), esc)
    f.campo(600, y, 900, y + 95, "Hora", hora, esc)
    f.campo(900, y, A4[0] - M, y + 95, "Local", local, esc)
    y += 140
    f.texto((M, y), "Descrição do ocorrido:", 26, bold=True)
    for i in range(5):
        f.linha(M, y + 95 + i * 80, A4[0] - M, y + 95 + i * 80, 1, (120, 120, 120))
    f.linhas_mao(M + 10, y + 85, A4[0] - 2 * M - 20, relato, esc, tam=42, entrelinha=80 / 42)
    y += 520
    f.texto((M, y), "Houve afastamento?", 26, bold=True)
    f.checkbox(M + 320, y, "Sim", afast, esc, 26)
    f.checkbox(M + 480, y, "Não", not afast, esc, 26)
    y += 80
    f.campo(M, y, A4[0] - M, y + 95, "Testemunha", test, esc)
    y += 180
    assina = nc != "sem_assinatura"
    _assinatura_com_nome(f, M + 20, y, esc, e.nome, assina, "Empregado", 600)
    _assinatura_com_nome(f, A4[0] - M - 640, y, Escritor.aleatorio(rng), "Técnico", True, "Técnico de segurança / supervisor", 600)
    dados = sch.OcorrenciaAcidente(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                   empregado_nome=e.nome.title(), empregado_cpf=None, data_documento=None, assinatura_empregado_presente=assina,
                                   tipo=tipo, data_ocorrencia=d.isoformat(), hora=hora, local=local, descricao=relato, houve_afastamento=afast,
                                   testemunha_nome=test)
    return _doc(T.OCORRENCIA_ACIDENTE, [f.finalizar()], dados, nc)


# ============================================================================ 22. contrato de trabalho (multipágina)
CLAUSULAS = [
    "O EMPREGADO prestará serviços na função indicada, obrigando-se a executar as tarefas compatíveis com sua condição pessoal.",
    "A jornada de trabalho será a indicada neste contrato, podendo ser prorrogada ou compensada nos termos da lei e do acordo coletivo.",
    "O EMPREGADO se compromete a cumprir o regulamento interno, as normas de segurança e as ordens de serviço da EMPREGADORA.",
    "Em caso de dano causado pelo EMPREGADO, fica a EMPREGADORA autorizada a efetuar o desconto da importância correspondente.",
    "O EMPREGADO poderá ser transferido para outro posto de trabalho, observadas as disposições legais aplicáveis.",
    "Aplicam-se a este contrato as disposições da Consolidação das Leis do Trabalho e da convenção coletiva da categoria.",
    "O EMPREGADO declara ter recebido cópia deste contrato e das normas internas, comprometendo-se a observá-las.",
]


@registrado
def contrato_trabalho(rng, u: Universo, e: Empregado, empresa: Empresa, nc=None) -> DocGerado:
    fk = _fk(rng)
    esc_emp, esc_rh = Escritor.aleatorio(rng), Escritor.aleatorio(rng)
    modalidade = rng.choice(["EXPERIENCIA", "PRAZO_INDETERMINADO"])
    prazo = rng.choice([45, 90]) if modalidade == "EXPERIENCIA" else None
    inicio = date.fromisoformat(e.admissao)
    jornada = f"{e.jornada[0]} às {e.jornada[1]} e {e.jornada[2]} às {e.jornada[3]}, de segunda a sexta-feira"
    sem_rubrica = rng.randrange(2) if nc == "contrato_sem_rubrica" else None
    assina = nc != "sem_assinatura"
    paginas = []
    n_pag = 3
    for p in range(n_pag):
        f = Folha(rng)
        y = M
        if p == 0:
            titulo = "CONTRATO DE TRABALHO " + ("POR PRAZO DETERMINADO (EXPERIÊNCIA)" if modalidade == "EXPERIENCIA" else "POR PRAZO INDETERMINADO")
            f.texto((A4[0] / 2, y), titulo, 30, bold=True, anchor="ma", max_w=A4[0] - 2 * M)
            y += 90
            intro = (f"Pelo presente instrumento, {empresa.razao_social}, CNPJ {fmt_cnpj(empresa.cnpj)}, com sede em {empresa.end.completo}, "
                     f"doravante EMPREGADORA, e {e.nome}, CPF {fmt_cpf(e.cpf)}, PIS {e.pis}, residente em {e.end.completo}, "
                     f"doravante EMPREGADO, celebram o presente contrato de trabalho mediante as cláusulas seguintes:")
            y = f.paragrafo(M, y, A4[0] - 2 * M, intro, 25, entrelinha=1.55) + 30
            dados_c = [f"CLÁUSULA 1ª – Função: {e.cargo}.", f"CLÁUSULA 2ª – Salário: R$ {brl(e.salario)} ({extenso_reais(e.salario)}) mensais.",
                       f"CLÁUSULA 3ª – Início: {fmt_data(inicio.isoformat())}" + (f", pelo prazo de {prazo} dias de experiência." if prazo else "."),
                       f"CLÁUSULA 4ª – Jornada: {jornada}."]
            for c in dados_c:
                y = f.paragrafo(M, y, A4[0] - 2 * M, c, 25, entrelinha=1.55) + 15
        else:
            f.texto((A4[0] - M, y), f"Página {p + 1}/{n_pag}", 20, anchor="ra")
            y += 50
        k0 = 0 if p == 0 else 3 * (p - 1) + 2
        for i, c in enumerate(CLAUSULAS[k0:k0 + (2 if p == 0 else 3)]):
            y = f.paragrafo(M, y + 10, A4[0] - 2 * M, f"CLÁUSULA {k0 + i + 5}ª – {c}", 25, entrelinha=1.55) + 15
        if p < n_pag - 1:
            f.texto((A4[0] - M, A4[1] - 200), "Rubricas:", 18, anchor="ra", cor=(100, 100, 100))
            if p != sem_rubrica:
                f.assinatura(A4[0] - M - 480, A4[1] - 190, A4[0] - M - 280, A4[1] - 110, esc_emp)
                f.assinatura(A4[0] - M - 260, A4[1] - 190, A4[0] - M - 40, A4[1] - 110, esc_rh)
        else:
            y += 60
            f.mao((M, y), f"{empresa.end.municipio}, {fmt_data(inicio.isoformat())}", esc_rh, tam=40)
            y += 120
            _assinatura_com_nome(f, M, y, esc_rh, "Empregadora", True, "EMPREGADORA", 600)
            _assinatura_com_nome(f, A4[0] - M - 620, y, esc_emp, e.nome, assina, "EMPREGADO", 600)
            f.carimbo(M + 300, y + 260, [empresa.razao_social[:30], f"CNPJ {fmt_cnpj(empresa.cnpj)}"])
            y += 400
            for i in range(2):
                nome_t = f"{fk.first_name()} {fk.last_name()}"
                _assinatura_com_nome(f, M + i * 760, y, Escritor.aleatorio(rng), nome_t, True, f"Testemunha: {nome_t}", 600)
        paginas.append(f.finalizar())
    dados = sch.ContratoTrabalho(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                 empregado_nome=e.nome, empregado_cpf=e.cpf, modalidade=modalidade, prazo_dias=prazo, data_inicio=inicio.isoformat(),
                                 cargo=e.cargo, salario=e.salario, jornada=jornada, rubricas_em_todas_paginas=sem_rubrica is None,
                                 assinatura_empregado_presente=assina, assinatura_empregador_presente=True, quantidade_testemunhas=2)
    return _doc(T.CONTRATO_TRABALHO, paginas, dados, nc)


# ============================================================================ 24. DARF (genérico)
@registrado
def darf(rng, u: Universo, empresa: Empresa, comp: str, nc=None) -> DocGerado:
    trab = [x for x in u.empregados_de(empresa.cnpj) if not (x.desligado_em and x.desligado_em[:7] == comp)]
    valor = round(sum(calc.holerite(u, x, comp)["base_inss"] for x in trab) * 0.20 + sum(calc.holerite(u, x, comp)["itens"][-2][4] for x in trab), 2)
    a, m = map(int, comp.split("-"))
    venc = date(a + (m == 12), m % 12 + 1, 20)
    while venc.weekday() >= 5:
        venc -= timedelta(days=1)
    pago = rng.random() < 0.7
    f = Folha(rng)
    f.texto((A4[0] / 2, M), "DOCUMENTO DE ARRECADAÇÃO DE TRIBUTOS FEDERAIS", 32, bold=True, anchor="ma")
    f.texto((A4[0] / 2, M + 55), "MODELO FICTÍCIO PARA TESTES – SEM VALOR PARA PAGAMENTO", 22, anchor="ma", cor=(150, 40, 40))
    y = M + 120
    meio = 1000
    f.campo(M, y, meio, y + 160, "01 Nome / Razão social", empresa.razao_social, tam_valor=26)
    campos_dir = [("02 Período de apuração", f"{comp[5:]}/{comp[:4]}"), ("03 CNPJ", fmt_cnpj(empresa.cnpj)), ("04 Código da receita", "1082"),
                  ("05 Número de referência", "–"), ("06 Data de vencimento", fmt_data(venc.isoformat())), ("07 Valor do principal", brl(valor)),
                  ("08 Multa", "0,00"), ("09 Juros", "0,00"), ("10 Valor total", brl(valor))]
    yy = y
    for rot, val in campos_dir:
        f.campo(meio, yy, A4[0] - M, yy + 80, rot, val, tam_valor=26, mono=True)
        yy += 80
    f.campo(M, y + 160, meio, yy, "Autenticação bancária (no verso ou nesta área)", None)
    anot = None
    if pago:
        txt = f"BANCO FICTICIO 999 {fmt_data((venc - timedelta(days=rng.randint(0, 4))).isoformat())} R$ {brl(valor)} AUT {rng.randint(10**9, 10**10):X}"
        f.texto((M + 20, y + 300), txt, 22, mono=True, cor=(90, 40, 130), max_w=meio - M - 40)
    if rng.random() < 0.5:
        anot = rng.choice([f"pago {fmt_data(venc.isoformat())[:5]}", "conferido", "lançado no sistema"])
        f.mao((M + 60, yy + 140), anot, Escritor.aleatorio(rng, "pressa"), tam=50, sem_defeito=True)
    dados = sch.DARF(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                     periodo_apuracao=comp, codigo_receita="1082", data_vencimento=venc.isoformat(), valor_total=valor,
                     anotacao_manuscrita=anot, autenticacao_bancaria_presente=pago)
    return _doc(T.DARF, [f.finalizar()], dados, nc)


# ============================================================================ notificação (acompanha AR)
@registrado
def notificacao(rng, u: Universo, e: Empregado, empresa: Empresa, numero: str, d: date, nc=None) -> DocGerado:
    assunto = rng.choice(["CONVOCACAO_RETORNO", "ABANDONO_EMPREGO", "CONVOCACAO_RETORNO"])
    prazo = rng.choice([2, 3, 5])
    f = Folha(rng)
    y = _cabecalho(f, empresa, "NOTIFICAÇÃO", numero) + 80
    f.texto((M, y), f"{empresa.end.municipio}, {data_extenso(d)}.", 26)
    y += 80
    for linha in [f"Ao(À) Sr(a). {e.nome}", f"CPF {fmt_cpf(e.cpf)}", e.end.completo, f"CEP {e.end.cep[:5]}-{e.end.cep[5:]}"]:
        f.texto((M, y), linha, 26, max_w=A4[0] - 2 * M)
        y += 42
    y += 60
    if assunto == "CONVOCACAO_RETORNO":
        txt = (f"Constatamos sua ausência ao trabalho sem justificativa. Fica V.Sa. convocado(a) a retornar às suas atividades ou "
               f"apresentar justificativa no prazo de {prazo} ({extenso_int(prazo)}) dias a contar do recebimento desta.")
    else:
        txt = (f"Diante de sua ausência prolongada e injustificada, notificamos V.Sa. a comparecer à empresa no prazo de {prazo} "
               f"({extenso_int(prazo)}) dias, sob pena de caracterização de abandono de emprego (art. 482, 'i', da CLT).")
    y = f.paragrafo(M, y, A4[0] - 2 * M, txt, 27, entrelinha=1.6) + 100
    _assinatura_com_nome(f, M, y, Escritor.aleatorio(rng), "Empresa", True, f"{empresa.razao_social} – Departamento Pessoal", 700)
    f.carimbo(M + 900, y + 60, [empresa.razao_social[:30], f"CNPJ {fmt_cnpj(empresa.cnpj)}"])
    dados = sch.NotificacaoEmpregado(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                                     empregado_nome=e.nome, empregado_cpf=e.cpf, assunto=assunto, data_documento=d.isoformat(), prazo_dias=prazo)
    return _doc(T.NOTIFICACAO_EMPREGADO, [f.finalizar()], dados, nc)
