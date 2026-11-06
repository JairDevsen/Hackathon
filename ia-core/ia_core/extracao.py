"""Extração por regex a partir do texto (motor local) e utilidades de datas/CPF."""
import re
from datetime import date
from typing import Dict, Optional

from .catalogo import norm

CPF_RE = re.compile(r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b")
CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
DATA_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
MESES = {m: i + 1 for i, m in enumerate("JANEIRO FEVEREIRO MARCO ABRIL MAIO JUNHO JULHO AGOSTO SETEMBRO OUTUBRO NOVEMBRO DEZEMBRO".split())}


def cpf_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s or "")
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def iso(d: str, m: str, a: str) -> Optional[str]:
    try:
        return date(int(a), int(m), int(d)).isoformat()
    except ValueError:
        return None


def cnpj_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s or "")
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        soma = sum(int(d[i]) * pesos[len(pesos) - n + i] for i in range(n))
        r = soma % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


_CNPJ_NUM = r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})"
_ROTULO_PRESTADORA = re.compile(r"(?:CONTRATADA|PRESTADORA|FORNECEDORA?|TERCEIRIZADA|EMPREGADOR|RAZAO SOCIAL|EMPRESA)\b[^\n]{0,140}?CNPJ[^\d]{0,14}" + _CNPJ_NUM)
_ROTULO_CONTRATANTE = re.compile(r"CONTRATANTE\b[^\n]{0,140}?CNPJ[^\d]{0,14}" + _CNPJ_NUM)


def cnpj_da_empresa(texto: str) -> Optional[str]:
    t = norm(texto)
    for m in _ROTULO_PRESTADORA.finditer(t):
        if cnpj_valido(m.group(1)):
            return re.sub(r"\D", "", m.group(1))
    contratantes = {re.sub(r"\D", "", m.group(1)) for m in _ROTULO_CONTRATANTE.finditer(t)}
    validos = [re.sub(r"\D", "", m.group(0)) for m in CNPJ_RE.finditer(texto) if cnpj_valido(m.group(0))]
    for c in validos:
        if c not in contratantes:
            return c
    if validos:
        return validos[0]
    todos = [re.sub(r"\D", "", m.group(0)) for m in CNPJ_RE.finditer(texto)]
    return todos[0] if todos else None


def extrair_campos(texto: str) -> Dict[str, Optional[str]]:
    t = norm(texto)
    out: Dict[str, Optional[str]] = {}
    # CPF: prefere o primeiro CPF válido; senão o primeiro encontrado
    cpfs = [m.group(0) for m in CPF_RE.finditer(texto)]
    cpf = next((c for c in cpfs if cpf_valido(c)), cpfs[0] if cpfs else None)
    out["cpf"] = re.sub(r"\D", "", cpf) if cpf else None
    m = re.search(r"(?:NOME(?: DO (?:COLABORADOR|FUNCIONARIO|EMPREGADO|TITULAR|CONDUTOR))?|COLABORADOR(?: TERCEIRIZADO)?|TITULAR|FUNCIONARIO|EMPREGADO)\s*(?:\([^)]*\))?\s*[:\-]\s*([A-Z][A-Z' ]{4,60}?)(?=\s*(?:\||\n|$|CPF|RG|MATRICULA|FUNCAO|CARGO))", t)
    if not m:
        m = re.search(r"\bEU,\s*([A-Z][A-Z ]{4,60}?)\s*,", t)
    out["nome"] = m.group(1).strip().title() if m else None
    m = re.search(r"MATRICULA\s*[:\-]?\s*(\d{3,10})", t)
    out["matricula"] = m.group(1) if m else None
    comp = None
    m = re.search(r"(?:COMPETENCIA|REFERENCIA|MES/ANO)\s*[:\-]?\s*(\d{2})/(\d{4})", t)
    if m:
        comp = f"{m.group(2)}-{m.group(1)}"
    else:
        m = re.search(r"(?:COMPETENCIA|REFERENCIA)\s*[:\-]?\s*(" + "|".join(MESES) + r")\s*(?:/|DE)\s*(\d{4})", t)
        if m:
            comp = f"{m.group(2)}-{MESES[m.group(1)]:02d}"
    out["competencia"] = comp
    # horas extras: total apurado no cartão de ponto (HH:MM) e valor pago no holerite (R$)
    m = re.search(r"HORAS EXTRAS\s*[:\-]\s*(\d{1,3})[:hH](\d{2})", t)
    out["horas_extras"] = f"{int(m.group(1)):02d}:{m.group(2)}" if m else None
    m = re.search(r"HORAS EXTRAS[^\n]{0,24}R\$\s*([\d\.]+,\d{2})", t)
    out["pagamento_horas_extras"] = m.group(1) if m else None
    # empresa: CNPJ e razão social. Um contrato cita DUAS empresas: vale a CONTRATADA/prestadora/fornecedora (o risco é dela),
    # não a contratante. Sem rótulo, o primeiro CNPJ válido.
    out["empresa_cnpj"] = cnpj_da_empresa(texto)
    m = re.search(r"(?:EMPRESA|EMPREGADOR|RAZAO SOCIAL|CONTRATADA|PRESTADORA)\s*[:\-]\s*([A-Z0-9][A-Z0-9 .&\-]{4,60}?)(?=\s*(?:\||\n|$|CNPJ|CPF))", t)
    out["empresa_nome"] = m.group(1).strip() if m else None
    m = DATA_RE.search(texto)
    out["data_documento"] = iso(*m.groups()) if m else None
    m = re.search(r"(?:VALIDADE|VALIDO ATE|VENCIMENTO|VAL\.?)\s*(?:CNH)?\s*[:\-]?\s*(\d{2})/(\d{2})/(\d{4})", t)
    out["validade_ate"] = iso(*m.groups()) if m else None
    return out
