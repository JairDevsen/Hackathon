"""Cálculos trabalhistas simplificados (fictícios, apenas para coerência entre documentos)."""
from __future__ import annotations

import calendar
from datetime import date

from .universo import Empregado, Universo, faltas, minutos_extras

# Faixas progressivas aproximadas do INSS (empregado). Apenas para dados de teste.
FAIXAS_INSS = [(1518.00, 0.075), (2793.88, 0.09), (4190.83, 0.12), (8157.41, 0.14)]


def inss(base: float) -> float:
    total, anterior = 0.0, 0.0
    for teto, aliq in FAIXAS_INSS:
        if base <= anterior:
            break
        total += (min(base, teto) - anterior) * aliq
        anterior = teto
    return round(total, 2)


def holerite(u: Universo, e: Empregado, comp: str) -> dict:
    dias = u.meses[(e.cpf, comp)]
    hora = e.salario / 220
    he_min = minutos_extras(dias)
    he_valor = round(hora * 1.5 * he_min / 60, 2)
    n_faltas = faltas(dias)
    v_faltas = round(e.salario / 30 * n_faltas, 2)
    # no mês do desligamento não há holerite: o saldo de salário vai no TRCT
    base_sal = e.salario
    itens = [("001", "SALÁRIO BASE", "30,00", base_sal, None)]
    if he_valor:
        itens.append(("050", "HORAS EXTRAS 50%", f"{he_min // 60:02d}:{he_min % 60:02d}", he_valor, None))
    base = round(base_sal + he_valor - v_faltas, 2)
    v_inss = inss(base)
    v_vt = round(min(e.salario * 0.06, 220.0), 2)
    if v_faltas:
        itens.append(("210", "FALTAS", f"{n_faltas},00", None, v_faltas))
    itens.append(("901", "INSS", f"{v_inss / base * 100:.2f}".replace(".", ","), None, v_inss))
    itens.append(("920", "VALE TRANSPORTE", "6,00", None, v_vt))
    prov = round(sum(i[3] or 0 for i in itens), 2)
    desc = round(sum(i[4] or 0 for i in itens), 2)
    return {
        "itens": itens, "total_proventos": prov, "total_descontos": desc, "valor_liquido": round(prov - desc, 2),
        "base_inss": base, "base_fgts": base, "fgts": round(base * 0.08, 2), "salario_base": e.salario,
    }


def quinto_dia_util(comp: str) -> date:
    a, m = map(int, comp.split("-"))
    a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    n, d = 0, 0
    while n < 5:
        d += 1
        if date(a, m, d).weekday() < 6:  # sábado conta como dia útil para pagamento de salário
            n += 1
    return date(a, m, d)


def vencimento_fgts(comp: str) -> date:
    a, m = map(int, comp.split("-"))
    a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    d = date(a, m, 20)
    while d.weekday() >= 5:
        d = date(a, m, d.day - 1)
    return d


def rescisao(e: Empregado, causa_codigo: str) -> dict:
    deslig = date.fromisoformat(e.desligado_em)
    adm = date.fromisoformat(e.admissao)
    s = e.salario
    saldo = round(s / 30 * deslig.day, 2)
    meses_total = (deslig.year - adm.year) * 12 + deslig.month - adm.month + (1 if deslig.day >= 15 else 0)
    meses_ferias = max(1, meses_total % 12)
    ferias = round(s / 12 * meses_ferias, 2)
    terco = round(ferias / 3, 2)
    meses_13 = deslig.month if deslig.day >= 15 else deslig.month - 1
    d13 = round(s / 12 * max(meses_13, 1), 2)
    verbas = [("Saldo de salário", saldo), ("Férias proporcionais", ferias), ("1/3 constitucional de férias", terco),
              ("13º salário proporcional", d13)]
    if causa_codigo == "SJ2":
        verbas.append(("Aviso prévio indenizado", s))
    deducoes = [("INSS sobre saldo de salário", inss(saldo)), ("INSS sobre 13º salário", inss(d13))]
    bruto = round(sum(v for _, v in verbas), 2)
    ded = round(sum(v for _, v in deducoes), 2)
    ultimo = calendar.monthrange(deslig.year, deslig.month)[1]
    return {"verbas": verbas, "deducoes": deducoes, "bruto": bruto, "deducoes_total": ded,
            "liquido": round(bruto - ded, 2), "ultimo_dia_mes": ultimo}
