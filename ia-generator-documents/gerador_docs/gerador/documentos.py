"""Renderização de cada tipo de documento + gabarito (modelos Pydantic do ia_core) + não conformidades."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from PIL import Image
from pydantic import BaseModel

from . import calculos as calc
from ._ia_core import sch
from .canvas import A4, Escritor, Folha, brl, fmt_cnpj, fmt_cpf, fmt_data
from .universo import DiaTrabalho, Empregado, Empresa, Universo, gerar_mes, nome_mes

T = sch.TipoDocumento

# Não conformidades possíveis por tipo -> campo onde ia_core.validacoes deve acusar
NCS: dict = {
    T.HOLERITE: {"fgts_divergente": "valor_fgts_mes", "liquido_divergente": "valor_liquido",
                 "sem_assinatura": "assinatura_empregado_presente", "cpf_invalido": "empregado_cpf"},
    T.CARTAO_PONTO: {"jornada_excessiva": "registros", "intervalo_curto": "registros",
                     "ponto_britanico": "registros", "sem_assinatura": "assinatura_empregado_presente"},
    T.CRF_FGTS: {"certidao_vencida": "data_validade", "certidao_positiva": "situacao"},
    T.CNDT: {"certidao_vencida": "data_validade", "certidao_positiva": "situacao"},
    T.CND_FEDERAL: {"certidao_vencida": "data_validade", "certidao_positiva": "situacao"},
    T.TRCT: {"liquido_divergente": "valor_liquido", "sem_assinatura": "assinatura_empregado_presente"},
    T.ASO: {"aso_inapto": "conclusao", "aso_sem_crm": "medico_crm"},
    T.FICHA_EPI: {"epi_sem_ca": "entregas", "sem_assinatura": "assinatura_empregado_presente"},
    T.AVISO_RECEBIMENTO: {"ar_devolvido": "motivo_devolucao", "ar_sem_assinatura": "assinatura_recebedor_presente",
                          "ar_sem_carimbo": "carimbo_unidade_presente"},
}
DESCRICAO_NC = {
    "fgts_divergente": "FGTS do mês diferente de 8% da base", "liquido_divergente": "valor líquido não fecha com a soma",
    "sem_assinatura": "falta a assinatura do empregado", "cpf_invalido": "CPF impresso com dígito verificador errado",
    "jornada_excessiva": "dia com jornada acima de 10h", "intervalo_curto": "dia com intervalo menor que 1h",
    "ponto_britanico": "horários idênticos todos os dias", "certidao_vencida": "certidão fora da validade",
    "certidao_positiva": "certidão positiva / situação irregular", "aso_inapto": "ASO com conclusão INAPTO",
    "aso_sem_crm": "ASO sem CRM do médico", "epi_sem_ca": "EPI entregue sem número de CA",
    "ar_devolvido": "AR devolvido sem entrega ao destinatário", "ar_sem_assinatura": "AR entregue sem assinatura do recebedor",
    "ar_sem_carimbo": "AR sem carimbo da unidade de entrega",
}
DIAS_SEMANA = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
M = 90  # margem


@dataclass
class DocGerado:
    tipo: sch.TipoDocumento
    paginas: list[Image.Image]
    dados: BaseModel | None
    nao_conformidades: list[dict] = field(default_factory=list)
    meia_pagina: bool = False  # comprovantes: podem dividir a mesma folha
    cartoes: list = field(default_factory=list)  # AR: frente e verso como cartões soltos
    registro: list = field(default_factory=list)  # tudo que foi desenhado (conferência)
    defeitos: list = field(default_factory=list)


def _nc(nc: str | None) -> list[dict]:
    return [{"regra": nc, "descricao": DESCRICAO_NC[nc]}] if nc else []


def _cpf_errado(cpf: str) -> str:
    return cpf[:-1] + str((int(cpf[-1]) + 1) % 10)


def _cabecalho(f: Folha, empresa: Empresa, titulo: str, subtitulo: str | None = None, y=M) -> int:
    f.caixa(M, y, A4[0] - M, y + 150)
    f.texto((M + 20, y + 20), empresa.razao_social, 30, bold=True, max_w=880)
    f.texto((M + 20, y + 65), f"CNPJ: {fmt_cnpj(empresa.cnpj)}", 24)
    f.texto((M + 20, y + 100), f"{empresa.endereco} – {empresa.cidade}", 22, max_w=880)
    f.texto((A4[0] - M - 20, y + 30), titulo, 30, bold=True, anchor="ra", max_w=560)
    if subtitulo:
        f.texto((A4[0] - M - 20, y + 85), subtitulo, 24, anchor="ra", max_w=560)
    return y + 150


# =============================================================================== HOLERITE
def holerite(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, comp: str, nc: str | None) -> DocGerado:
    h = calc.holerite(u, e, comp)
    liquido_impresso = h["valor_liquido"] + (rng.choice([-1, 1]) * rng.uniform(30, 150) if nc == "liquido_divergente" else 0)
    liquido_impresso = round(liquido_impresso, 2)
    fgts_impresso = round(h["fgts"] - rng.uniform(15, 60), 2) if nc == "fgts_divergente" else h["fgts"]
    cpf_impresso = _cpf_errado(e.cpf) if nc == "cpf_invalido" else e.cpf
    assina = nc != "sem_assinatura"
    esc = Escritor.aleatorio(rng)
    f = Folha(rng)

    def via(y0: int, assinar: bool, rotulo_via: str):
        f.caixa(M, y0, A4[0] - M, y0 + 120)
        f.texto((M + 15, y0 + 15), u_emp.razao_social, 26, bold=True, max_w=900)
        f.texto((M + 15, y0 + 52), f"CNPJ: {fmt_cnpj(empresa.cnpj)}", 22, mono=True)
        f.texto((M + 15, y0 + 84), empresa.cidade, 20)
        f.texto((A4[0] - M - 15, y0 + 18), "Recibo de Pagamento de Salário", 26, bold=True, anchor="ra")
        f.texto((A4[0] - M - 15, y0 + 55), f"Referente ao Mês: {nome_mes(comp)}", 22, anchor="ra")
        f.texto((A4[0] - M - 15, y0 + 86), rotulo_via, 18, anchor="ra", cor=(90, 90, 90))
        y = y0 + 120
        xs = [M, M + 160, M + 760, M + 960, M + 1210, A4[0] - M]
        rot = ["Código", "Nome do Funcionário", "CBO", "Função", "Admissão"]
        val = [e.matricula, e.nome, e.cbo, e.cargo, fmt_data(e.admissao)]
        for i in range(5):
            f.campo(xs[i], y, xs[i + 1], y + 75, rot[i], val[i], tam_valor=24, mono=True)
        y += 75
        f.campo(M, y, M + 500, y + 70, "CPF", fmt_cpf(cpf_impresso), tam_valor=24, mono=True)
        f.campo(M + 500, y, A4[0] - M, y + 70, "Departamento", "OPERACIONAL – POSTO CONTRATANTE", tam_valor=24, mono=True)
        y += 82
        linhas = [[c, d, r, brl(p) if p else "", brl(dc) if dc else ""] for c, d, r, p, dc in h["itens"]]
        linhas += [[""] * 5] * (9 - len(linhas))
        y = f.tabela(M, y, [140, 600, 220, 257, 257], 40, ["Cód.", "Descrição", "Referência", "Vencimentos", "Descontos"],
                     linhas, tam=22, mono=True)
        f.campo(M + 960, y, M + 1217, y + 70, "Total de Vencimentos", brl(h["total_proventos"]), tam_valor=24, mono=True)
        f.campo(M + 1217, y, A4[0] - M, y + 70, "Total de Descontos", brl(h["total_descontos"]), tam_valor=24, mono=True)
        f.texto((M + 10, y + 20), "Declaro ter recebido a importância líquida discriminada neste recibo.", 20, max_w=850)
        y += 70
        f.campo(M + 960, y, A4[0] - M, y + 70, "Valor Líquido  ⇒", brl(liquido_impresso), tam_valor=28, mono=True)
        f.texto((M + 10, y + 20), "____/____/______", 24)
        f.linha(M + 300, y + 38, M + 900, y + 38, 1)
        f.texto((M + 600, y + 43), "Assinatura do Funcionário", 17, anchor="ma")
        if assinar:
            pag = calc.quinto_dia_util(comp)
            f.mao((M + 12, y + 36), f"{pag.day:02d}  {pag.month:02d}  {pag.year}", esc, tam=30)
            f.assinatura(M + 340, y - 30, M + 880, y + 36, esc, e.nome)
        y += 70
        bases = [("Salário Base", h["salario_base"]), ("Sal. Contr. INSS", h["base_inss"]), ("Base Cálc. FGTS", h["base_fgts"]),
                 ("F.G.T.S do Mês", fgts_impresso), ("Base Cálc. IRRF", round(h["base_inss"] - h["total_descontos"] + h["itens"][-1][4], 2)), ("Faixa IRRF", 0.0)]
        larg = (A4[0] - 2 * M) / len(bases)
        for i, (r, v) in enumerate(bases):
            f.campo(int(M + i * larg), y, int(M + (i + 1) * larg), y + 70, r, brl(v), tam_valor=22, mono=True)
        return y + 70

    u_emp = empresa
    fim = via(M, assina, "1ª via – Empresa")
    if rng.random() < 0.6:  # segunda via na mesma folha, como sai da impressora
        yc = fim + 60
        for x in range(M, A4[0] - M, 30):
            f.linha(x, yc, x + 15, yc, 2, (120, 120, 120))
        via(yc + 60, False, "2ª via – Empregado")

    dados = sch.Holerite(
        campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
        empregado_nome=e.nome, empregado_cpf=cpf_impresso, matricula=e.matricula, cargo=e.cargo, competencia=comp,
        salario_base=h["salario_base"],
        itens=[sch.ItemHolerite(codigo=c, descricao=d, referencia=r, provento=p, desconto=dc) for c, d, r, p, dc in h["itens"]],
        total_proventos=h["total_proventos"], total_descontos=h["total_descontos"], valor_liquido=liquido_impresso,
        base_calculo_inss=h["base_inss"], base_calculo_fgts=h["base_fgts"], valor_fgts_mes=fgts_impresso,
        assinatura_empregado_presente=assina,
    )
    return DocGerado(T.HOLERITE, [f.finalizar()], dados, _nc(nc))


# =============================================================================== CARTÃO DE PONTO
def cartao_ponto(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, comp: str, nc: str | None) -> DocGerado:
    if nc in ("jornada_excessiva", "intervalo_curto", "ponto_britanico"):
        u.meses[(e.cpf, comp)] = gerar_mes(rng, e, comp, nc)  # holerite gerado depois usa o mesmo mês
    dias: list[DiaTrabalho] = u.meses[(e.cpf, comp)]
    assina = nc != "sem_assinatura"
    manual = rng.random() < 0.65
    paginas = _ponto_manual(rng, e, empresa, comp, dias, assina) if manual else _ponto_eletronico(rng, e, empresa, comp, dias, assina)
    dados = sch.CartaoPonto(
        campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
        empregado_nome=e.nome, empregado_cpf=None if manual else e.cpf, matricula=e.matricula,
        periodo_inicio=dias[0].data, periodo_fim=dias[-1].data, forma_registro="MANUAL" if manual else "ELETRONICO",
        registros=[sch.RegistroPonto(data=d.data, marcacoes=d.marcacoes, ocorrencia=d.ocorrencia) for d in dias],
        assinatura_empregado_presente=assina,
    )
    return DocGerado(T.CARTAO_PONTO, paginas, dados, _nc(nc))


def _ponto_manual(rng, e: Empregado, empresa: Empresa, comp: str, dias: list[DiaTrabalho], assina: bool) -> list[Image.Image]:
    esc = Escritor.aleatorio(rng)
    a, m = comp.split("-")
    metades = [dias[:16], dias[16:]]
    paginas = []
    for n, parte in enumerate(metades, 1):
        f = Folha(rng)
        f.texto((A4[0] / 2, M), "FOLHA DE PONTO INDIVIDUAL", 38, bold=True, anchor="ma")
        f.texto((A4[0] - M, M + 10), f"Folha {n}/2", 22, anchor="ra")
        y = M + 70
        f.campo(M, y, 1100, y + 85, "Empregador", empresa.razao_social, tam_valor=24)
        f.campo(1100, y, A4[0] - M, y + 85, "CNPJ", fmt_cnpj(empresa.cnpj), tam_valor=24)
        y += 85
        f.campo(M, y, 1100, y + 95, "Nome do empregado", e.nome.title(), esc)
        f.campo(1100, y, A4[0] - M, y + 95, "Matrícula", e.matricula, esc)
        y += 95
        f.campo(M, y, 560, y + 95, "Função", e.cargo.title(), esc)
        f.campo(560, y, 1100, y + 95, "Período", f"{fmt_data(dias[0].data)} a {fmt_data(dias[-1].data)}", esc)
        f.campo(1100, y, A4[0] - M, y + 95, "Horário", f"{e.jornada[0]} às {e.jornada[3]}", esc)
        y += 120
        linhas = []
        for d in parte:
            dia = int(d.data[-2:])
            if d.marcacoes:
                linhas.append([f"{dia:02d}", *d.marcacoes, ""])
            else:
                linhas.append([f"{dia:02d}", "", "", "", "", d.ocorrencia or ""])
        alt = 82
        larg = [120, 250, 250, 250, 250, A4[0] - 2 * M - 1120]
        y_tab = y
        y = f.tabela(M, y, larg, alt, ["Dia", "Entrada", "Saída", "Entrada", "Saída", "Rubrica / Ocorrência"], linhas,
                     esc, cols_mao={1, 2, 3, 4, 5}, tam=24)
        if assina:  # rubrica diária nos dias trabalhados
            x_rub = M + sum(larg[:-1])
            for i, d in enumerate(parte):
                if d.marcacoes and rng.random() < 0.85:
                    yy = y_tab + alt * (i + 1)
                    f.assinatura(x_rub + 20, yy + 10, x_rub + 220, yy + alt - 10, esc)
        if n == 2:
            y += 60
            f.linha(M + 40, y + 90, M + 640, y + 90)
            f.texto((M + 340, y + 100), "Assinatura do empregado", 20, anchor="ma")
            f.linha(A4[0] - M - 640, y + 90, A4[0] - M - 40, y + 90)
            f.texto((A4[0] - M - 340, y + 100), "Visto do encarregado", 20, anchor="ma")
            if assina:
                f.assinatura(M + 60, y, M + 620, y + 85, esc, e.nome)
            f.assinatura(A4[0] - M - 620, y + 5, A4[0] - M - 80, y + 85, Escritor.aleatorio(rng), "Supervisor")
        paginas.append(f.finalizar())
    return paginas


def _ponto_eletronico(rng, e: Empregado, empresa: Empresa, comp: str, dias: list[DiaTrabalho], assina: bool) -> list[Image.Image]:
    f = Folha(rng)
    y = _cabecalho(f, empresa, "ESPELHO DE PONTO", f"Período: {fmt_data(dias[0].data)} a {fmt_data(dias[-1].data)}")
    f.campo(M, y, 900, y + 75, "Empregado", e.nome, tam_valor=24, mono=True)
    f.campo(900, y, 1200, y + 75, "Matrícula", e.matricula, tam_valor=24, mono=True)
    f.campo(1200, y, A4[0] - M, y + 75, "CPF", fmt_cpf(e.cpf), tam_valor=24, mono=True)
    y += 75
    f.campo(M, y, 900, y + 75, "Função", e.cargo, tam_valor=24, mono=True)
    f.campo(900, y, A4[0] - M, y + 75, "Horário contratual", " – ".join(e.jornada), tam_valor=24, mono=True)
    y += 95
    linhas = [[fmt_data(d.data), DIAS_SEMANA[date.fromisoformat(d.data).weekday()], "  ".join(d.marcacoes), d.ocorrencia or ""] for d in dias]
    y = f.tabela(M, y, [260, 130, 700, A4[0] - 2 * M - 1090], 46, ["Data", "Dia", "Marcações (REP)", "Ocorrência"], linhas, tam=22, mono=True)
    y += 40
    f.texto((M, y), "Reconheço como verdadeiras as marcações acima.", 22)
    f.linha(M + 700, y + 110, A4[0] - M - 80, y + 110)
    f.texto(((M + 700 + A4[0] - M - 80) / 2, y + 120), "Assinatura do empregado", 20, anchor="ma")
    if assina:
        f.assinatura(M + 720, y + 20, A4[0] - M - 100, y + 105, Escritor.aleatorio(rng), e.nome)
    return [f.finalizar()]


# =============================================================================== CERTIDÕES
def certidao(rng: random.Random, u: Universo, empresa: Empresa, tipo: sch.TipoDocumento, nc: str | None) -> DocGerado:
    hoje = date.fromisoformat(u.data_referencia)
    dias_val = 30 if tipo == T.CRF_FGTS else 180
    emissao = hoje - timedelta(days=dias_val + rng.randint(5, 60)) if nc == "certidao_vencida" else hoje - timedelta(days=rng.randint(1, 20))
    validade = emissao + timedelta(days=dias_val)
    positiva = nc == "certidao_positiva"
    codigo = f"FICT-{rng.randint(1000, 9999)}.{rng.randint(1000, 9999)}.{rng.randint(1000, 9999)}"
    numero = f"FICT-{rng.randint(10**7, 10**8 - 1)}/{emissao.year}"
    f = Folha(rng)
    f.texto((A4[0] / 2, M), "MODELO FICTÍCIO PARA TESTES – SEM VALOR LEGAL", 22, bold=True, anchor="ma", cor=(150, 40, 40))
    y = M + 120
    if tipo == T.CRF_FGTS:
        situacao = sch.SituacaoCertidao.IRREGULAR if positiva else sch.SituacaoCertidao.REGULAR
        f.texto((A4[0] / 2, y), "CERTIFICADO DE REGULARIDADE DO FGTS – CRF", 40, bold=True, anchor="ma")
        y += 140
        for r, v in [("Inscrição:", fmt_cnpj(empresa.cnpj)), ("Razão Social:", empresa.razao_social), ("Endereço:", f"{empresa.endereco} – {empresa.cidade}")]:
            f.texto((M + 60, y), r, 26, bold=True)
            f.texto((M + 330, y), v, 26, max_w=1100)
            y += 55
        y += 50
        texto = ("O Agente Operador do FGTS (fictício), no uso de suas atribuições, CERTIFICA que, nesta data, a empresa acima "
                 + ("NÃO se encontra em situação regular perante o Fundo de Garantia do Tempo de Serviço." if positiva
                    else "encontra-se em situação REGULAR perante o Fundo de Garantia do Tempo de Serviço – FGTS."))
        y = f.paragrafo(M + 60, y, A4[0] - 2 * M - 120, texto, 28) + 40
        f.texto((M + 60, y), f"Validade: {fmt_data(emissao.isoformat())} a {fmt_data(validade.isoformat())}", 30, bold=True)
        y += 70
        f.texto((M + 60, y), f"Certificação Número: {numero}", 26)
        y += 55
        f.texto((M + 60, y), f"Informação obtida em {fmt_data(emissao.isoformat())}, às {rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}", 24)
        num, cod = numero, None
    elif tipo == T.CNDT:
        situacao = sch.SituacaoCertidao.POSITIVA if positiva else sch.SituacaoCertidao.NEGATIVA
        f.texto((A4[0] / 2, y), "PODER JUDICIÁRIO – JUSTIÇA DO TRABALHO (MODELO FICTÍCIO)", 26, anchor="ma")
        y += 70
        f.texto((A4[0] / 2, y), f"CERTIDÃO {'POSITIVA' if positiva else 'NEGATIVA'} DE DÉBITOS TRABALHISTAS", 40, bold=True, anchor="ma")
        y += 130
        for r, v in [("Nome:", empresa.razao_social), ("CNPJ:", f"{fmt_cnpj(empresa.cnpj)} (matriz e filiais)"), ("Certidão nº:", numero),
                     ("Expedição:", f"{fmt_data(emissao.isoformat())}, às {rng.randint(8, 18):02d}:{rng.randint(0, 59):02d}"),
                     ("Validade:", f"{fmt_data(validade.isoformat())} – 180 (cento e oitenta) dias, contados da data de sua expedição.")]:
            f.texto((M + 60, y), r, 26, bold=True)
            y = f.paragrafo(M + 300, y, A4[0] - 2 * M - 360, v, 26) + 15
        y += 40
        texto = (f"Certifica-se que {empresa.razao_social}, inscrito(a) no CNPJ sob o nº {fmt_cnpj(empresa.cnpj)}, "
                 + ("CONSTA do Banco Nacional de Devedores Trabalhistas (fictício) com processos em fase de execução."
                    if positiva else "NÃO CONSTA do Banco Nacional de Devedores Trabalhistas (fictício)."))
        f.paragrafo(M + 60, y, A4[0] - 2 * M - 120, texto, 28)
        num, cod = numero, None
    else:
        situacao = sch.SituacaoCertidao.POSITIVA if positiva else sch.SituacaoCertidao.NEGATIVA
        f.texto((A4[0] / 2, y), "MINISTÉRIO DA FAZENDA (MODELO FICTÍCIO)", 26, anchor="ma")
        y += 70
        titulo = "CERTIDÃO POSITIVA DE DÉBITOS" if positiva else "CERTIDÃO NEGATIVA DE DÉBITOS"
        f.texto((A4[0] / 2, y), titulo, 40, bold=True, anchor="ma")
        f.texto((A4[0] / 2, y + 60), "RELATIVOS AOS TRIBUTOS FEDERAIS E À DÍVIDA ATIVA DA UNIÃO", 28, bold=True, anchor="ma")
        y += 180
        f.texto((M + 60, y), f"Nome: {empresa.razao_social}", 26, max_w=1300)
        f.texto((M + 60, y + 50), f"CNPJ: {fmt_cnpj(empresa.cnpj)}", 26)
        y += 150
        texto = ("Constam pendências em nome do sujeito passivo acima identificado no âmbito da Secretaria da Receita (fictícia)."
                 if positiva else "Ressalvado o direito de a Fazenda Nacional cobrar quaisquer dívidas que vierem a ser apuradas, "
                 "é certificado que não constam pendências em nome do sujeito passivo acima identificado.")
        y = f.paragrafo(M + 60, y, A4[0] - 2 * M - 120, texto, 28) + 60
        f.texto((M + 60, y), f"Emitida às {rng.randint(8, 18):02d}:{rng.randint(0, 59):02d} do dia {fmt_data(emissao.isoformat())}.", 26)
        f.texto((M + 60, y + 50), f"Válida até {fmt_data(validade.isoformat())}.", 26, bold=True)
        f.texto((M + 60, y + 100), f"Código de controle da certidão: {codigo}", 26)
        num, cod = None, codigo
    dados = sch.Certidao(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social,
                         empregador_cnpj=empresa.cnpj, numero_certidao=num, data_emissao=emissao.isoformat(),
                         data_validade=validade.isoformat(), situacao=situacao, codigo_controle=cod)
    return DocGerado(tipo, [f.finalizar()], dados, _nc(nc))


# =============================================================================== GUIA FGTS
def guia_fgts(rng: random.Random, u: Universo, empresa: Empresa, comp: str) -> DocGerado:
    trab = [(e, calc.holerite(u, e, comp)) for e in u.empregados_de(empresa.cnpj)
            if not (e.desligado_em and e.desligado_em[:7] == comp)]
    total = round(sum(h["fgts"] for _, h in trab), 2)
    venc = calc.vencimento_fgts(comp)
    ident = f"FICT{rng.randint(10**15, 10**16 - 1)}"
    pago = rng.random() < 0.7
    data_pag = venc - timedelta(days=rng.randint(0, 5)) if pago else None
    f = Folha(rng)
    f.texto((A4[0] / 2, M), "GUIA DO FGTS DIGITAL – GFD", 40, bold=True, anchor="ma")
    f.texto((A4[0] / 2, M + 60), "MODELO FICTÍCIO PARA TESTES – SEM VALOR PARA PAGAMENTO", 22, anchor="ma", cor=(150, 40, 40))
    y = M + 120
    f.campo(M, y, 1100, y + 80, "Empregador", empresa.razao_social, tam_valor=26)
    f.campo(1100, y, A4[0] - M, y + 80, "CNPJ", fmt_cnpj(empresa.cnpj), tam_valor=26)
    y += 80
    f.campo(M, y, 600, y + 80, "Competência", f"{comp[5:]}/{comp[:4]}", tam_valor=28)
    f.campo(600, y, 1100, y + 80, "Pagar até", fmt_data(venc.isoformat()), tam_valor=28)
    f.campo(1100, y, A4[0] - M, y + 80, "Valor a recolher (R$)", brl(total), tam_valor=30)
    y += 80
    f.campo(M, y, A4[0] - M, y + 80, "Identificador da guia", ident, tam_valor=28, mono=True)
    y += 110
    linhas = [[fmt_cpf(e.cpf), e.nome, brl(h["base_fgts"]), brl(h["fgts"])] for e, h in trab[:22]]
    y = f.tabela(M, y, [300, 680, 247, 247], 44, ["CPF", "Trabalhador", "Remuneração", "FGTS"], linhas, tam=20, mono=True)
    if len(trab) > 22:
        f.texto((M, y + 10), f"... e mais {len(trab) - 22} trabalhador(es)", 20)
    y += 60
    x = M + 100  # código de barras fictício
    while x < A4[0] - M - 100:
        larg = rng.choice([2, 3, 5])
        f.d.rectangle([x, y, x + larg, y + 110], fill=(10, 10, 10))
        x += larg + rng.choice([2, 3, 4])
    f.texto((A4[0] / 2, y + 125), f"FICT {ident[4:10]} {ident[10:]} {rng.randint(10**9, 10**10 - 1)}", 24, mono=True, anchor="ma")
    if pago:
        aut = f"BANCO FICTICIO 999  {fmt_data(data_pag.isoformat())}  AG 0{rng.randint(100, 999)}  R$ {brl(total)}  AUT {rng.randint(10**11, 10**12 - 1):X}"
        camada = Folha(rng, (1500, 60), (255, 255, 255))
        camada.texto((10, 10), aut, 26, mono=True, cor=(0, 0, 0))
        # autenticação mecânica: tinta roxa, levemente torta
        mascara = Image.eval(camada.img.convert("L"), lambda p: 255 - p).rotate(rng.uniform(-1.5, 1.5), expand=True)
        roxo = Image.new("RGB", mascara.size, (90, 40, 130))
        f.img.paste(roxo, (M + rng.randint(0, 80), A4[1] - 330), mascara)
    anotacao = None
    if rng.random() < 0.55:  # anotação à mão de quem pagou/conferiu
        anotacao = rng.choice([f"pago em {data_pag:%d/%m}" if pago else "pagar até dia 20",
                               f"pago {data_pag:%d/%m/%y}" if pago else "aguardando pagto", "conferido"])
        f.mao((A4[0] - M - 560, M + 260 + rng.randint(0, 40)), anotacao, Escritor.aleatorio(rng, "pressa"), tam=46, sem_defeito=True)
    dados = sch.GuiaFGTS(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                         anotacao_manuscrita=anotacao, identificador_guia=ident, competencia=comp, data_vencimento=venc.isoformat(), valor_total=total,
                         data_pagamento=data_pag.isoformat() if data_pag else None, autenticacao_bancaria_presente=pago)
    return DocGerado(T.GUIA_FGTS, [f.finalizar()], dados)


# =============================================================================== COMPROVANTE
def comprovante(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, comp: str) -> DocGerado:
    """Comprovante PIX de salário. Retorna meia folha; a montagem decide se junta dois na mesma página."""
    h = calc.holerite(u, e, comp)
    data = calc.quinto_dia_util(comp)
    aut = f"FICT-E{rng.randint(10**20, 10**21 - 1)}"
    f = Folha(rng, (1474, 1080))
    f.caixa(0, 0, 1473, 1079, 2, (180, 180, 180))
    f.texto((737, 40), "BANCO FICTÍCIO S.A.", 34, bold=True, anchor="ma")
    f.texto((737, 95), "Comprovante de Transferência PIX", 30, anchor="ma")
    y = 180
    for r, v in [("Data/Hora", f"{fmt_data(data.isoformat())} {rng.randint(7, 11):02d}:{rng.randint(0, 59):02d}"), ("Valor", f"R$ {brl(h['valor_liquido'])}"),
                 ("Finalidade", f"Pagamento de salário {comp[5:]}/{comp[:4]}"), ("", ""),
                 ("Pagador", empresa.razao_social), ("CNPJ do pagador", fmt_cnpj(empresa.cnpj)), ("", ""),
                 ("Favorecido", e.nome), ("CPF do favorecido", fmt_cpf(e.cpf)), ("Instituição", "BANCO FICTÍCIO DIGITAL"), ("", ""),
                 ("ID da transação", aut)]:
        if r:
            f.texto((70, y), r, 24, cor=(90, 90, 90))
            f.texto((480, y), v, 26, bold=r == "Valor", max_w=940)
        y += 62
    dados = sch.ComprovantePagamento(campos_ilegiveis=[], observacoes=None, banco="BANCO FICTÍCIO S.A.", data_pagamento=data.isoformat(),
                                     valor=h["valor_liquido"], pagador_nome=empresa.razao_social, pagador_documento=empresa.cnpj,
                                     favorecido_nome=e.nome, favorecido_documento=e.cpf,
                                     finalidade=f"Pagamento de salário {comp[5:]}/{comp[:4]}", autenticacao=aut)
    return DocGerado(T.COMPROVANTE_PAGAMENTO, [f.img], dados, meia_pagina=True)


def folha_de_comprovantes(rng: random.Random, docs: list[DocGerado]) -> Image.Image:
    """Cola 1 ou 2 comprovantes numa folha A4 (como cópia de comprovantes grampeados)."""
    f = Folha(rng)
    for i, d in enumerate(docs):
        recibo = d.paginas[0].rotate(rng.uniform(-2, 2), expand=True, fillcolor=(255, 255, 255))
        f.img.paste(recibo, (M + rng.randint(-10, 10), M + 30 + i * 1130 + rng.randint(-10, 10)))
    return f.finalizar()


# =============================================================================== FICHA DE EPI
EPIS = {
    "Limpeza e Conservação": ["Luva de látex", "Bota de PVC", "Avental impermeável", "Máscara PFF2", "Óculos de proteção"],
    "Vigilância Patrimonial": ["Colete balístico", "Protetor auricular plug", "Bota de segurança"],
    "Manutenção Predial": ["Luva isolante", "Capacete classe B", "Óculos de proteção", "Bota de segurança", "Cinto paraquedista"],
    "Portaria e Recepção": ["Protetor auricular plug", "Calçado de segurança"],
    "Copa e Cozinha": ["Luva térmica", "Avental", "Touca descartável", "Bota de PVC antiderrapante"],
}


def ficha_epi(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, nc: str | None) -> DocGerado:
    esc = Escritor.aleatorio(rng)
    hoje = date.fromisoformat(u.data_referencia)
    adm = date.fromisoformat(e.admissao)
    n = rng.randint(3, 9)
    datas = sorted(adm + timedelta(days=rng.randint(0, max(1, (hoje - adm).days - 5))) for _ in range(n))
    entregas = [sch.EntregaEPI(data=d.isoformat(), descricao=rng.choice(EPIS[empresa.segmento]), quantidade=rng.choice([1, 1, 2, 3]),
                               numero_ca=str(rng.randint(10000, 49999))) for d in datas]
    if nc == "epi_sem_ca":
        entregas[rng.randrange(n)].numero_ca = None
    assina = nc != "sem_assinatura"
    f = Folha(rng)
    y = _cabecalho(f, empresa, "FICHA DE ENTREGA DE EPI", "Equipamento de Proteção Individual")
    f.campo(M, y, 1100, y + 95, "Nome do empregado", e.nome.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "CPF", fmt_cpf(e.cpf), esc)
    y += 95
    f.campo(M, y, 1100, y + 95, "Função", e.cargo.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "Admissão", fmt_data(e.admissao), esc)
    y += 120
    termo = ("Declaro ter recebido gratuitamente os Equipamentos de Proteção Individual abaixo relacionados, comprometendo-me a "
             "utilizá-los apenas para a finalidade a que se destinam, responsabilizar-me por sua guarda e conservação e comunicar "
             "qualquer alteração que os torne impróprios para uso.")
    y = f.paragrafo(M, y, A4[0] - 2 * M, termo, 23) + 30
    linhas = [[fmt_data(x.data), str(x.quantidade), x.descricao, x.numero_ca or "", ""] for x in entregas]
    linhas += [[""] * 5] * (14 - len(linhas))
    larg = [230, 110, 620, 220, A4[0] - 2 * M - 1180]
    y_tab = y
    y = f.tabela(M, y, larg, 80, ["Data", "Qtd.", "Descrição do EPI", "Nº do CA", "Rubrica"], linhas, esc, cols_mao={0, 1, 2, 3}, tam=22)
    if assina:
        x_rub = M + sum(larg[:-1])
        for i in range(n):
            yy = y_tab + 80 * (i + 1)
            f.assinatura(x_rub + 15, yy + 8, x_rub + larg[-1] - 15, yy + 72, esc)
    y += 70
    f.mao((M, y + 50), f"{empresa.cidade.split('/')[0]}, {fmt_data(datas[-1].isoformat())}", esc, tam=34, max_w=650)
    f.linha(A4[0] - M - 700, y + 90, A4[0] - M - 40, y + 90)
    f.texto((A4[0] - M - 370, y + 100), "Assinatura do empregado", 20, anchor="ma")
    if assina:
        f.assinatura(A4[0] - M - 680, y, A4[0] - M - 60, y + 85, esc, e.nome)
    dados = sch.FichaEPI(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                         empregado_nome=e.nome.title(), empregado_cpf=e.cpf, funcao=e.cargo.title(), entregas=entregas,
                         assinatura_empregado_presente=assina)
    return DocGerado(T.FICHA_EPI, [f.finalizar()], dados, _nc(nc))


# =============================================================================== ASO
RISCOS = ["Físico (ruído)", "Químico", "Biológico", "Ergonômico", "Acidentes", "Ausência de risco específico"]
TIPOS_EXAME = [("ADMISSIONAL", "Admissional"), ("PERIODICO", "Periódico"), ("RETORNO_AO_TRABALHO", "Retorno ao trabalho"),
               ("MUDANCA_DE_RISCO", "Mudança de risco"), ("DEMISSIONAL", "Demissional")]


def aso(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, nc: str | None, tipo_exame: str | None = None) -> DocGerado:
    from faker import Faker
    fk = Faker("pt_BR")
    fk.seed_instance(rng.randrange(10**9))
    esc = Escritor.aleatorio(rng)
    hoje = date.fromisoformat(u.data_referencia)
    tipo_exame = tipo_exame or rng.choice(["ADMISSIONAL", "PERIODICO", "PERIODICO", "RETORNO_AO_TRABALHO"])
    data_exame = date.fromisoformat(e.admissao) - timedelta(days=rng.randint(1, 7)) if tipo_exame == "ADMISSIONAL" else \
        date.fromisoformat(e.desligado_em) if tipo_exame == "DEMISSIONAL" else hoje - timedelta(days=rng.randint(10, 300))
    riscos = rng.sample(RISCOS[:5], rng.randint(1, 2)) if rng.random() < 0.7 else [RISCOS[5]]
    apto = nc != "aso_inapto"
    medico = f"Dr(a). {fk.first_name()} {fk.last_name()}"
    crm = None if nc == "aso_sem_crm" else f"CRM-{rng.choice(['PE', 'PB', 'AL', 'BA'])} {rng.randint(5000, 39999)}"
    f = Folha(rng)
    f.texto((A4[0] / 2, M), "ATESTADO DE SAÚDE OCUPACIONAL – ASO", 40, bold=True, anchor="ma")
    f.texto((A4[0] / 2, M + 60), "(NR-7 – PCMSO)", 24, anchor="ma")
    y = M + 120
    f.campo(M, y, 1100, y + 80, "Empresa", empresa.razao_social, tam_valor=24)
    f.campo(1100, y, A4[0] - M, y + 80, "CNPJ", fmt_cnpj(empresa.cnpj), tam_valor=24)
    y += 80
    f.campo(M, y, 1100, y + 95, "Nome do trabalhador", e.nome.title(), esc)
    f.campo(1100, y, A4[0] - M, y + 95, "CPF", fmt_cpf(e.cpf), esc)
    y += 95
    f.campo(M, y, A4[0] - M, y + 95, "Função", e.cargo.title(), esc)
    y += 130
    f.texto((M, y), "Tipo de exame:", 28, bold=True)
    y += 55
    for i, (cod, rot) in enumerate(TIPOS_EXAME):
        f.checkbox(M + 20 + (i % 3) * 480, y + (i // 3) * 55, rot, cod == tipo_exame, esc)
    y += 150
    f.texto((M, y), "Riscos ocupacionais:", 28, bold=True)
    y += 55
    for i, r in enumerate(RISCOS):
        f.checkbox(M + 20 + (i % 2) * 720, y + (i // 2) * 55, r, r in riscos, esc)
    y += 200
    f.texto((M, y), "Conclusão: em cumprimento à NR-7, declaro que o trabalhador acima identificado está:", 26, max_w=1450)
    y += 60
    f.checkbox(M + 60, y, "APTO para a função", apto, esc, 28)
    f.checkbox(M + 760, y, "INAPTO para a função", not apto, esc, 28)
    y += 120
    f.campo(M, y, 1000, y + 95, "Médico responsável", medico, esc)
    f.campo(1000, y, A4[0] - M, y + 95, "CRM", crm or "", esc)
    y += 95
    f.campo(M, y, 600, y + 95, "Data do exame", fmt_data(data_exame.isoformat()), esc)
    y += 160
    f.carimbo(M + 380, y + 60, [medico.upper(), "MÉDICO DO TRABALHO", crm or "CLÍNICA FICTÍCIA"])
    f.assinatura(M + 120, y, M + 700, y + 90, esc, medico.split()[1])
    f.linha(M + 60, y + 130, M + 760, y + 130)
    f.texto((M + 410, y + 140), "Assinatura e carimbo do médico", 20, anchor="ma")
    f.linha(A4[0] - M - 650, y + 130, A4[0] - M - 40, y + 130)
    f.texto((A4[0] - M - 345, y + 140), "Ciente – assinatura do trabalhador", 20, anchor="ma")
    f.assinatura(A4[0] - M - 620, y + 35, A4[0] - M - 70, y + 120, Escritor.aleatorio(rng), e.nome)
    dados = sch.ASO(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                    empregado_nome=e.nome.title(), empregado_cpf=e.cpf, funcao=e.cargo.title(), tipo_exame=sch.TipoExameASO(tipo_exame),
                    data_exame=data_exame.isoformat(), riscos_ocupacionais=riscos, conclusao="APTO" if apto else "INAPTO",
                    medico_nome=medico, medico_crm=crm)
    return DocGerado(T.ASO, [f.finalizar()], dados, _nc(nc))


# =============================================================================== TRCT
CAUSAS = [("Despedida sem justa causa, pelo empregador", "SJ2"), ("Rescisão a pedido do empregado", "PD0"),
          ("Término do contrato de experiência", "RA2")]


def trct(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, nc: str | None) -> DocGerado:
    causa, cod = rng.choice(CAUSAS)
    r = calc.rescisao(e, cod)
    liquido = round(r["liquido"] + rng.uniform(40, 200), 2) if nc == "liquido_divergente" else r["liquido"]
    assina = nc != "sem_assinatura"
    deslig = date.fromisoformat(e.desligado_em)
    aviso = (deslig - timedelta(days=30)).isoformat() if cod != "RA2" else None
    manual = rng.random() < 0.35  # formulário preenchido à mão
    esc = Escritor.aleatorio(rng)
    v_esc = esc if manual else None
    f = Folha(rng)
    f.texto((A4[0] / 2, M), "TERMO DE RESCISÃO DO CONTRATO DE TRABALHO", 38, bold=True, anchor="ma")
    y = M + 70
    f.texto((M, y), "IDENTIFICAÇÃO DO EMPREGADOR", 22, bold=True)
    y += 35
    f.campo(M, y, 600, y + 85, "01 CNPJ/CEI", fmt_cnpj(empresa.cnpj), v_esc, mono=True)
    f.campo(600, y, A4[0] - M, y + 85, "02 Razão Social/Nome", empresa.razao_social, v_esc)
    y += 85
    f.campo(M, y, A4[0] - M, y + 85, "03 Endereço", f"{empresa.endereco} – {empresa.cidade}", v_esc)
    y += 110
    f.texto((M, y), "IDENTIFICAÇÃO DO TRABALHADOR", 22, bold=True)
    y += 35
    f.campo(M, y, 500, y + 85, "10 PIS/PASEP", e.pis, v_esc, mono=True)
    f.campo(500, y, A4[0] - M, y + 85, "11 Nome", e.nome, v_esc)
    y += 85
    f.campo(M, y, 500, y + 85, "17 CPF", fmt_cpf(e.cpf), v_esc, mono=True)
    f.campo(500, y, 1050, y + 85, "18 Data de nascimento", fmt_data((date.fromisoformat(e.admissao) - timedelta(days=rng.randint(7000, 16000))).isoformat()), v_esc)
    f.campo(1050, y, A4[0] - M, y + 85, "19 Função", e.cargo, v_esc)
    y += 110
    f.texto((M, y), "DADOS DO CONTRATO", 22, bold=True)
    y += 35
    f.campo(M, y, 1050, y + 85, "22 Causa do afastamento", causa, v_esc)
    f.campo(1050, y, A4[0] - M, y + 85, "23 Remuneração p/ fins rescisórios", brl(e.salario), v_esc, mono=True)
    y += 85
    f.campo(M, y, 440, y + 85, "24 Data de admissão", fmt_data(e.admissao), v_esc)
    f.campo(440, y, 830, y + 85, "25 Data do aviso prévio", fmt_data(aviso), v_esc)
    f.campo(830, y, 1220, y + 85, "26 Data de afastamento", fmt_data(e.desligado_em), v_esc)
    f.campo(1220, y, A4[0] - M, y + 85, "27 Cód. afastamento", cod, v_esc)
    y += 115
    f.texto((M, y), "DISCRIMINAÇÃO DAS VERBAS RESCISÓRIAS", 22, bold=True)
    y += 35
    meio = A4[0] / 2
    lv = [[n, brl(v)] for n, v in r["verbas"]] + [["", ""]] * (7 - len(r["verbas"]))
    ld = [[n, brl(v)] for n, v in r["deducoes"]] + [["", ""]] * (7 - len(r["deducoes"]))
    f.tabela(M, y, [480, int(meio - M - 480 - 10)], 62, ["Verbas", "Valor (R$)"], lv, v_esc, cols_mao={0, 1} if manual else None, tam=21)
    y2 = f.tabela(int(meio + 10), y, [450, int(A4[0] - M - meio - 460)], 62, ["Deduções", "Valor (R$)"], ld, v_esc, cols_mao={0, 1} if manual else None, tam=21)
    y = y2 + 20
    terco = (A4[0] - 2 * M) / 3
    for i, (rot, v) in enumerate([("TOTAL BRUTO", r["bruto"]), ("TOTAL DEDUÇÕES", r["deducoes_total"]), ("VALOR LÍQUIDO", liquido)]):
        f.campo(int(M + i * terco), y, int(M + (i + 1) * terco), y + 90, rot, brl(v), v_esc, tam_valor=30, mono=True)
    p1 = f.finalizar()

    # página 2: termo de quitação com assinaturas
    f = Folha(rng)
    f.texto((A4[0] / 2, M), "TERMO DE QUITAÇÃO DE RESCISÃO DO CONTRATO DE TRABALHO", 32, bold=True, anchor="ma")
    y = M + 100
    for rot, v in [("Empregador", f"{empresa.razao_social} – CNPJ {fmt_cnpj(empresa.cnpj)}"), ("Trabalhador", f"{e.nome} – CPF {fmt_cpf(e.cpf)}"),
                   ("Admissão / Afastamento", f"{fmt_data(e.admissao)}  /  {fmt_data(e.desligado_em)}"), ("Causa", f"{causa} ({cod})")]:
        f.texto((M, y), f"{rot}:", 26, bold=True)
        f.texto((M + 420, y), v, 26, max_w=1060)
        y += 60
    y += 40
    texto = (f"Foi realizada a rescisão do contrato de trabalho do trabalhador acima qualificado, nos termos do art. 477 da CLT, "
             f"sendo efetuado o pagamento das verbas rescisórias especificadas no TRCT, no valor líquido de R$ {brl(liquido)}, "
             f"o qual, devidamente assinado, dá plena e geral quitação dos valores nele discriminados.")
    y = f.paragrafo(M, y, A4[0] - 2 * M, texto, 27) + 120
    data_pag = min(deslig + timedelta(days=rng.randint(2, 9)), date.fromisoformat(u.data_referencia))
    f.mao((M, y), f"{empresa.cidade.split('/')[0]}, {fmt_data(data_pag.isoformat())}", esc, tam=38, max_w=900)
    y += 200
    for i, (rot, presente, nome) in enumerate([("Assinatura do empregador ou preposto", True, empresa.razao_social),
                                                ("Assinatura do trabalhador", assina, e.nome)]):
        x0 = M + i * 760
        f.linha(x0 + 20, y + 110, x0 + 680, y + 110)
        f.texto((x0 + 350, y + 120), rot, 20, anchor="ma")
        if presente:
            f.assinatura(x0 + 50, y + 10, x0 + 650, y + 105, Escritor.aleatorio(rng) if i == 0 else esc, nome)
    f.carimbo(M + 350, y + 260, [empresa.razao_social[:34], f"CNPJ {fmt_cnpj(empresa.cnpj)}"])
    p2 = f.finalizar()
    dados = sch.TRCT(campos_ilegiveis=[], observacoes=None, empregador_razao_social=empresa.razao_social, empregador_cnpj=empresa.cnpj,
                     empregado_nome=e.nome, empregado_cpf=e.cpf, empregado_pis=e.pis, data_admissao=e.admissao, data_aviso_previo=aviso,
                     data_afastamento=e.desligado_em, causa_afastamento=causa, codigo_afastamento=cod, remuneracao_fins_rescisorios=e.salario,
                     total_bruto=r["bruto"], total_deducoes=r["deducoes_total"], valor_liquido=liquido,
                     assinatura_empregado_presente=assina, assinatura_empregador_presente=True)
    return DocGerado(T.TRCT, [p1, p2], dados, _nc(nc))


# =============================================================================== OUTRO
def outro(rng: random.Random, u: Universo, empresa: Empresa, comp: str) -> DocGerado:
    f = Folha(rng)
    tipo = rng.choice(["branco", "capa", "separador", "oficio"])
    if tipo == "capa":
        esc = Escritor.aleatorio(rng)
        f.mao((M + 100, 600), "Documentação mensal", esc, tam=70)
        f.mao((M + 100, 760), empresa.razao_social.title(), esc, tam=50, max_w=1300)
        f.mao((M + 100, 900), f"Competência {comp[5:]}/{comp[:4]}", esc, tam=55)
        f.mao((M + 100, 1040), "Aos cuidados do setor de contratos", esc, tam=45)
    elif tipo == "separador":
        f.caixa(M + 200, 900, A4[0] - M - 200, 1300, 6)
        f.texto((A4[0] / 2, 1050), "SEPARADOR DE DOCUMENTOS", 52, bold=True, anchor="mm")
        f.texto((A4[0] / 2, 1150), f"Competência {comp[5:]}/{comp[:4]}", 36, anchor="mm")
    elif tipo == "oficio":
        y = _cabecalho(f, empresa, "OFÍCIO", f"Nº {rng.randint(10, 300)}/{comp[:4]}") + 120
        texto = (f"Prezados, encaminhamos em anexo a documentação trabalhista e previdenciária referente à competência "
                 f"{comp[5:]}/{comp[:4]}, em cumprimento às obrigações do contrato de prestação de serviços. "
                 f"Permanecemos à disposição para eventuais esclarecimentos.")
        y = f.paragrafo(M + 40, y, A4[0] - 2 * M - 80, texto, 30) + 100
        f.texto((M + 40, y), "Atenciosamente,", 30)
        f.assinatura(M + 40, y + 60, M + 640, y + 170, Escritor.aleatorio(rng), "Gerente")
        f.texto((M + 40, y + 200), "Departamento Pessoal", 26)
    return DocGerado(T.OUTRO, [f.finalizar()], None)


# =============================================================================== AVISO DE RECEBIMENTO (AR)
MOTIVOS_AR = [("MUDOU_SE", "Mudou-se"), ("ENDERECO_INSUFICIENTE", "Endereço insuficiente"), ("NAO_EXISTE_NUMERO", "Não existe o nº indicado"),
              ("DESCONHECIDO", "Desconhecido"), ("RECUSADO", "Recusado"), ("NAO_PROCURADO", "Não procurado"),
              ("AUSENTE", "Ausente"), ("FALECIDO", "Falecido"), ("OUTROS", "Outros")]
TOM_CARTAO = (250, 244, 218)


def _dia_util(d: date, rng: random.Random) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def aviso_recebimento(rng: random.Random, u: Universo, e: Empregado, empresa: Empresa, nc: str | None,
                      conteudo: str | None = None, data_postagem: date | None = None) -> DocGerado:
    """AR genérico (sem marca, cores ou formato de código de nenhuma empresa postal real), preenchido à mão
    pelo remetente (destinatário/conteúdo), pela agência (postagem), pelo carteiro (tentativas, motivo, data)
    e pelo recebedor (nome, documento, assinatura)."""
    from faker import Faker
    fk = Faker("pt_BR")
    fk.seed_instance(rng.randrange(10**9))
    hoje = date.fromisoformat(u.data_referencia)
    esc_rem, esc_cart, esc_rec = Escritor.aleatorio(rng), Escritor.aleatorio(rng), Escritor.aleatorio(rng)
    codigo = f"FICT {rng.randint(100, 999)} {rng.randint(100, 999)} {rng.randint(100, 999)} AR"
    dest = e.end
    rem = empresa.end
    conteudo = conteudo or f"Notificação nº {rng.randint(10, 400)}/{hoje.year}"
    unidade = f"AGÊNCIA FICTÍCIA {rem.municipio.upper()}"
    entregue = nc != "ar_devolvido"
    postagem = data_postagem or _dia_util(hoje - timedelta(days=rng.randint(8, 30)), rng)
    tentativas, d = [], postagem
    for _ in range(rng.randint(1, 2) if entregue else 3):
        d = _dia_util(d + timedelta(days=rng.randint(1, 3)), rng)
        tentativas.append((d, f"{rng.randint(8, 16):02d}:{rng.choice([0, 10, 15, 20, 30, 40, 45, 50]):02d}"))
    motivo = None if entregue else rng.choice(["AUSENTE", "MUDOU_SE", "DESCONHECIDO", "RECUSADO", "NAO_PROCURADO"])
    devolucao = _dia_util(tentativas[-1][0] + timedelta(days=rng.randint(1, 7)), rng) if not entregue else None
    proprio = rng.random() < 0.6
    recebedor = (e.nome if proprio else f"{fk.first_name()} {fk.last_name()}".upper()) if entregue else None
    rg = f"{rng.randint(1_000_000, 9_999_999)}" if entregue else None
    data_entrega = tentativas[-1][0] if entregue else None
    assina = entregue and nc != "ar_sem_assinatura"
    carimbo = nc != "ar_sem_carimbo"
    matricula_carteiro = f"{rng.randint(80, 99)}.{rng.randint(100, 999)}-{rng.randint(0, 9)}"
    cep = lambda c: f"{c[:5]}-{c[5:]}"  # noqa: E731

    W, H = A4[0] - 2 * M, 1060

    def cartao() -> Folha:
        c = Folha(rng, (W, H), TOM_CARTAO)
        c.d.rounded_rectangle([2, 2, W - 3, H - 3], radius=24, outline=(40, 40, 40), width=3)
        return c

    # ---------------- frente
    fr = cartao()
    fr.texto((30, 22), "AVISO DE RECEBIMENTO", 40, bold=True)
    fr.texto((32, 74), "AR  ·  MODELO FICTÍCIO – SEM VALOR POSTAL", 20, cor=(150, 40, 40))
    fr.caixa(W - 560, 20, W - 30, 130, 2)
    fr.texto((W - 545, 28), "Nº DO OBJETO", 17, cond=True, cor=(60, 60, 60))
    fr.texto((W - 295, 92), codigo, 30, mono=True, anchor="mm")
    x = W - 540
    while x < W - 50:  # código de barras falso
        larg = rng.choice([2, 3, 4])
        fr.d.rectangle([x, 108, x + larg, 125], fill=(20, 20, 20))
        x += larg + rng.choice([2, 3])
    y = 145
    fr.campo(30, y, 560, y + 75, "UNIDADE DE POSTAGEM", unidade, tam_valor=22)
    fr.campo(560, y, 900, y + 75, "DATA DE POSTAGEM", fmt_data(postagem.isoformat()), esc_cart)
    fr.campo(900, y, W - 30, y + 75, "CONTEÚDO / DOCUMENTO", conteudo, esc_rem, tam_valor=26)
    y += 92
    fr.texto((30, y), "DESTINATÁRIO", 22, bold=True)
    y += 32
    fr.campo(30, y, W - 30, y + 75, "Nome", e.nome.title(), esc_rem)
    fr.campo(30, y + 75, W - 30, y + 150, "Endereço (logradouro e número)", dest.linha, esc_rem)
    fr.campo(30, y + 150, 640, y + 225, "Bairro", dest.bairro, esc_rem)
    fr.campo(640, y + 225 - 75, 1060, y + 225, "Município", dest.municipio, esc_rem)
    fr.campo(1060, y + 150, 1180, y + 225, "UF", dest.uf, esc_rem)
    fr.campo(1180, y + 150, W - 30, y + 225, "CEP", cep(dest.cep), esc_rem)
    y += 243
    fr.texto((30, y), "REMETENTE – ENDEREÇO PARA DEVOLUÇÃO DO AR", 22, bold=True)
    y += 32
    etiqueta = rng.random() < 0.5  # remetente em etiqueta impressa ou à mão
    fr.campo(30, y, W - 30, y + 72, "Nome / Razão social", empresa.razao_social, None if etiqueta else esc_rem, tam_valor=26)
    fr.campo(30, y + 72, W - 430, y + 144, "Endereço", rem.completo, None if etiqueta else esc_rem, tam_valor=22)
    fr.campo(W - 430, y + 72, W - 30, y + 144, "CEP", cep(rem.cep), None if etiqueta else esc_rem, tam_valor=26)
    y += 160
    meio = W // 2 - 40
    fr.texto((30, y), "TENTATIVAS DE ENTREGA", 20, bold=True)
    fr.texto((meio + 20, y), "MOTIVO DE DEVOLUÇÃO", 20, bold=True)
    for i in range(3):
        yy = y + 36 + i * 60
        fr.texto((30, yy + 12), f"{i + 1}ª", 24, bold=True)
        fr.texto((90, yy + 12), "____/____/______", 24)
        fr.texto((400, yy + 12), "____:____ h", 24)
        if i < len(tentativas):
            dt, hr = tentativas[i]
            fr.mao((98, yy + 38), f"{dt.day:02d}   {dt.month:02d}   {dt.year}", esc_cart, tam=30, sem_defeito=True)
            fr.mao((410, yy + 38), f"{hr[:2]}  {hr[3:]}", esc_cart, tam=30, sem_defeito=True)
    for i, (cod, rot) in enumerate(MOTIVOS_AR):
        fr.checkbox(meio + 20 + (i % 2) * 330, y + 36 + (i // 2) * 38, rot, cod == motivo, esc_cart, tam=19)

    # ---------------- verso
    vs = cartao()
    vs.texto((30, 22), "DADOS DO RECEBIMENTO", 34, bold=True)
    vs.texto((W - 30, 30), codigo, 24, mono=True, anchor="ra")
    y = 90
    vs.caixa(30, y, W - 30, y + 180)
    vs.texto((40, y + 6), "ASSINATURA DO RECEBEDOR", 17, cond=True, cor=(60, 60, 60))
    if assina:
        vs.assinatura(120, y + 40, W - 350, y + 165, esc_rec, recebedor)
    y += 180
    vs.campo(30, y, W - 30, y + 90, "NOME LEGÍVEL DO RECEBEDOR", recebedor, esc_rec)
    y += 90
    vs.campo(30, y, W // 2, y + 90, "Nº DOCUMENTO DE IDENTIDADE", rg, esc_rec)
    vs.campo(W // 2, y, W - 30, y + 90, "DATA DE ENTREGA", fmt_data(data_entrega.isoformat()) if data_entrega else None, esc_cart)
    y += 90
    vs.campo(30, y, W - 30, y + 90, "NÃO ENTREGUE – DEVOLVIDO AO REMETENTE EM",
             fmt_data(devolucao.isoformat()) if devolucao else None, esc_cart)
    y += 90
    vs.caixa(30, y, W // 2, y + 300)
    vs.texto((40, y + 6), "RUBRICA E MATRÍCULA DO CARTEIRO", 17, cond=True, cor=(60, 60, 60))
    vs.assinatura(70, y + 50, W // 2 - 60, y + 170, esc_cart)
    vs.mao((70, y + 250), f"Mat. {matricula_carteiro}", esc_cart, tam=34, sem_defeito=True)
    vs.caixa(W // 2, y, W - 30, y + 300)
    vs.texto((W // 2 + 10, y + 6), "CARIMBO – UNIDADE DE ENTREGA", 17, cond=True, cor=(60, 60, 60))
    if carimbo:
        data_carimbo = data_entrega or devolucao
        vs.carimbo(W * 3 // 4, y + 165, [f"CDD FICTÍCIO {dest.municipio.upper()}"[:30], f"UNIDADE {rng.randint(100, 999)}",
                                          fmt_data(data_carimbo.isoformat())], cor=(40, 60, 130))
    dados = sch.AvisoRecebimento(
        campos_ilegiveis=[], observacoes=None, codigo_objeto=codigo, conteudo=conteudo, data_postagem=postagem.isoformat(),
        unidade_postagem=unidade, destinatario_nome=e.nome.title(), destinatario_endereco=dest.linha,
        destinatario_bairro=dest.bairro, destinatario_municipio=dest.municipio, destinatario_uf=dest.uf, destinatario_cep=dest.cep,
        remetente_nome=empresa.razao_social, remetente_endereco=rem.completo, remetente_cep=rem.cep,
        tentativas=[sch.TentativaEntrega(data=dt.isoformat(), hora=hr) for dt, hr in tentativas],
        entregue=entregue, motivo_devolucao=motivo, data_entrega=data_entrega.isoformat() if data_entrega else None,
        data_devolucao=devolucao.isoformat() if devolucao else None,
        recebedor_nome=recebedor, recebedor_documento=rg, assinatura_recebedor_presente=assina,
        carimbo_unidade_presente=carimbo,
    )
    doc = DocGerado(T.AVISO_RECEBIMENTO, [], dados, _nc(nc))
    doc.cartoes = [fr, vs]  # a montagem decide como os cartões vão para as folhas (frente+verso, frentes de vários ARs...)
    doc.paginas = folhas_de_cartoes(rng, [fr, vs]) if rng.random() < 0.5 else folhas_de_cartoes(rng, [fr]) + folhas_de_cartoes(rng, [vs])
    return doc


def folhas_de_cartoes(rng: random.Random, cartoes: list[Folha]) -> list[Image.Image]:
    """Até 2 cartões por folha A4, como quando se coloca vários ARs no vidro do scanner."""
    folhas = []
    for k in range(0, len(cartoes), 2):
        f = Folha(rng)
        for i, ct in enumerate(cartoes[k:k + 2]):
            if not ct.img.info.get("ficticio"):
                ct.finalizar()
            img = ct.img.rotate(rng.uniform(-1.8, 1.8), expand=True, fillcolor=(255, 255, 255))
            f.img.paste(img, (M - 20 + rng.randint(-15, 15), M - 30 + i * 1130 + rng.randint(-10, 10)))
        folhas.append(f.finalizar())
    return folhas


# ------------------------------------------------------------------ conferência automática
from .conferencia import registrado  # noqa: E402

for _n in ["holerite", "cartao_ponto", "certidao", "guia_fgts", "comprovante", "ficha_epi", "aso", "trct", "outro",
           "aviso_recebimento"]:
    globals()[_n] = registrado(globals()[_n])
