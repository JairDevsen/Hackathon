"""Validações determinísticas sobre os dados extraídos. A IA lê; quem confere é o código."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pydantic import BaseModel

from .schemas import (ASO, TRCT, AdvertenciaSuspensao, AtestadoMedico, AvisoRecebimento, CartaoPonto, Certidao,
                      ContratoTrabalho, FichaEPI, Holerite, ListaPresenca, ReciboAvulso, SituacaoCertidao)

TOLERANCIA = 0.05  # R$ de arredondamento


@dataclass
class Alerta:
    campo: str
    mensagem: str
    severidade: str  # "erro" | "atencao"


def cpf_valido(cpf: str | None) -> bool:
    if not cpf or len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(cpf[i]) * (n + 1 - i) for i in range(n))
        if (s * 10 % 11) % 10 != int(cpf[n]):
            return False
    return True


def cnpj_valido(cnpj: str | None) -> bool:
    if not cnpj or len(cnpj) != 14 or not cnpj.isdigit() or cnpj == cnpj[0] * 14:
        return False
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        s = sum(int(cnpj[i]) * pesos[i + 13 - n] for i in range(n))
        dv = 0 if s % 11 < 2 else 11 - s % 11
        if dv != int(cnpj[n]):
            return False
    return True


def _data(s: str | None) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except ValueError:
        return None


def _min(hhmm: str) -> int | None:
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _comuns(d: BaseModel, out: list[Alerta]) -> None:
    cpf = getattr(d, "empregado_cpf", None)
    if cpf is not None and not cpf_valido(cpf):
        out.append(Alerta("empregado_cpf", f"CPF inválido: {cpf}", "erro"))
    cnpj = getattr(d, "empregador_cnpj", None)
    if cnpj is not None and not cnpj_valido(cnpj):
        out.append(Alerta("empregador_cnpj", f"CNPJ inválido: {cnpj}", "erro"))
    for campo in getattr(d, "campos_ilegiveis", []) or []:
        out.append(Alerta(campo, "campo ilegível no documento", "atencao"))


def validar(d: BaseModel, hoje: date | None = None) -> list[Alerta]:
    hoje = hoje or date.today()
    out: list[Alerta] = []
    _comuns(d, out)

    if isinstance(d, Holerite):
        prov = sum(i.provento or 0 for i in d.itens)
        desc = sum(i.desconto or 0 for i in d.itens)
        if d.total_proventos is not None and abs(prov - d.total_proventos) > TOLERANCIA:
            out.append(Alerta("total_proventos", f"soma dos itens {prov:.2f} ≠ total {d.total_proventos:.2f}", "erro"))
        if d.total_descontos is not None and abs(desc - d.total_descontos) > TOLERANCIA:
            out.append(Alerta("total_descontos", f"soma dos itens {desc:.2f} ≠ total {d.total_descontos:.2f}", "erro"))
        if None not in (d.total_proventos, d.total_descontos, d.valor_liquido):
            if abs(d.total_proventos - d.total_descontos - d.valor_liquido) > TOLERANCIA:
                out.append(Alerta("valor_liquido", "proventos − descontos ≠ líquido", "erro"))
        if d.base_calculo_fgts and d.valor_fgts_mes is not None:
            esperado = round(d.base_calculo_fgts * 0.08, 2)
            if abs(esperado - d.valor_fgts_mes) > TOLERANCIA:
                out.append(Alerta("valor_fgts_mes", f"FGTS {d.valor_fgts_mes:.2f} ≠ 8% da base ({esperado:.2f}); conferir se é aprendiz (2%)", "atencao"))
        if not d.assinatura_empregado_presente:
            out.append(Alerta("assinatura_empregado_presente", "holerite sem assinatura do empregado", "atencao"))

    elif isinstance(d, CartaoPonto):
        for r in d.registros:
            mins = [m for m in map(_min, r.marcacoes) if m is not None]
            if len(mins) >= 2 and len(mins) % 2 == 0:
                trabalhado = sum(mins[i + 1] - mins[i] for i in range(0, len(mins), 2))
                if trabalhado > 10 * 60:
                    out.append(Alerta("registros", f"{r.data}: jornada de {trabalhado / 60:.1f}h (> 10h)", "erro"))
                if len(mins) >= 4 and trabalhado > 6 * 60 and (mins[2] - mins[1]) < 60:
                    out.append(Alerta("registros", f"{r.data}: intervalo de {mins[2] - mins[1]} min (< 1h)", "erro"))
            elif len(mins) % 2 == 1:
                out.append(Alerta("registros", f"{r.data}: número ímpar de marcações", "atencao"))
            # Ponto britânico: muitos dias com horários idênticos é indício de invalidade
        horarios = [tuple(r.marcacoes) for r in d.registros if r.marcacoes]
        if len(horarios) >= 10 and len(set(horarios)) <= 2:
            out.append(Alerta("registros", "horários praticamente invariáveis (possível ponto britânico)", "atencao"))
        if not d.assinatura_empregado_presente:
            out.append(Alerta("assinatura_empregado_presente", "cartão de ponto sem assinatura", "atencao"))

    elif isinstance(d, Certidao):
        validade = _data(d.data_validade)
        if validade is None:
            out.append(Alerta("data_validade", "validade não identificada", "atencao"))
        elif validade < hoje:
            out.append(Alerta("data_validade", f"certidão vencida em {validade:%d/%m/%Y}", "erro"))
        if d.situacao in (SituacaoCertidao.POSITIVA, SituacaoCertidao.IRREGULAR):
            out.append(Alerta("situacao", f"certidão {d.situacao.value}", "erro"))

    elif isinstance(d, TRCT):
        if None not in (d.total_bruto, d.total_deducoes, d.valor_liquido):
            if abs(d.total_bruto - d.total_deducoes - d.valor_liquido) > TOLERANCIA:
                out.append(Alerta("valor_liquido", "bruto − deduções ≠ líquido", "erro"))
        if not d.assinatura_empregado_presente:
            out.append(Alerta("assinatura_empregado_presente", "TRCT sem assinatura do empregado", "erro"))

    elif isinstance(d, ASO):
        if (d.conclusao or "").upper() == "INAPTO":
            out.append(Alerta("conclusao", "empregado considerado INAPTO", "erro"))
        if not d.medico_crm:
            out.append(Alerta("medico_crm", "ASO sem CRM do médico", "atencao"))

    elif isinstance(d, FichaEPI):
        for e in d.entregas:
            if not e.numero_ca:
                out.append(Alerta("entregas", f"EPI '{e.descricao}' sem número de CA", "atencao"))
        if not d.assinatura_empregado_presente:
            out.append(Alerta("assinatura_empregado_presente", "ficha de EPI sem assinatura", "erro"))

    elif isinstance(d, AvisoRecebimento):
        if not d.entregue:
            out.append(Alerta("motivo_devolucao", f"objeto não entregue ({d.motivo_devolucao or 'motivo não assinalado'})", "erro"))
        else:
            if not d.assinatura_recebedor_presente:
                out.append(Alerta("assinatura_recebedor_presente", "AR entregue sem assinatura do recebedor", "erro"))
            if not d.recebedor_nome:
                out.append(Alerta("recebedor_nome", "AR sem nome legível do recebedor", "atencao"))
            if _data(d.data_entrega) is None:
                out.append(Alerta("data_entrega", "AR sem data de entrega", "erro"))
        if not d.carimbo_unidade_presente:
            out.append(Alerta("carimbo_unidade_presente", "AR sem carimbo da unidade de entrega", "atencao"))

    elif isinstance(d, AtestadoMedico):
        if not d.medico_crm:
            out.append(Alerta("medico_crm", "atestado sem CRM do médico", "erro"))
        if not d.assinatura_medico_presente:
            out.append(Alerta("assinatura_medico_presente", "atestado sem assinatura do médico", "erro"))

    elif isinstance(d, AdvertenciaSuspensao):
        if d.ciencia == "RECUSA" and d.quantidade_testemunhas < 2:
            out.append(Alerta("quantidade_testemunhas", "recusa de ciência sem duas testemunhas", "erro"))
        if d.ciencia == "SEM_CIENCIA":
            out.append(Alerta("ciencia", "medida disciplinar sem ciência do empregado", "erro"))

    elif isinstance(d, ContratoTrabalho):
        if not d.rubricas_em_todas_paginas:
            out.append(Alerta("rubricas_em_todas_paginas", "contrato sem rubrica em todas as páginas", "atencao"))
        if not d.assinatura_empregado_presente:
            out.append(Alerta("assinatura_empregado_presente", "contrato sem assinatura do empregado", "erro"))

    elif isinstance(d, ListaPresenca):
        faltam = [p.nome or "?" for p in d.participantes if not p.assinatura_presente]
        if faltam:
            out.append(Alerta("participantes", f"{len(faltam)} participante(s) sem assinatura", "atencao"))
        for p in d.participantes:
            if p.cpf and not cpf_valido(p.cpf):
                out.append(Alerta("participantes", f"CPF inválido na lista: {p.cpf}", "erro"))

    elif isinstance(d, ReciboAvulso):
        if not d.assinatura_recebedor_presente:
            out.append(Alerta("assinatura_recebedor_presente", "recibo sem assinatura de quem recebeu", "erro"))

    # regra genérica: documentos de RH que exigem assinatura do empregado
    if not isinstance(d, (Holerite, CartaoPonto, TRCT, FichaEPI, ContratoTrabalho, AdvertenciaSuspensao)) and \
            getattr(d, "assinatura_empregado_presente", True) is False:
        out.append(Alerta("assinatura_empregado_presente", "documento sem assinatura do empregado", "erro"))

    return out
