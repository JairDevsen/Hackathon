"""Marcadores de paginação impressos no documento ("Página 2/3", "Folha 2/2", "(PAG 2/2)", "fls. 3 de 5")."""
import re
from typing import Optional, Tuple

from .catalogo import norm

_MARCADOR = re.compile(r"\b(?:PAGINAS?|PAG|PG|FOLHAS?|FLS?)\b\.?\s*(\d{1,3})\s*(?:/|DE)\s*(\d{1,3})\b")


# número que identifica UM documento e se repete em todas as suas páginas (ex.: objeto do AR: frente e verso)
_ID_CORREIOS = re.compile(r"\b[A-Z]{2}\s?(\d{9})\s?[A-Z]{2}\b")
_ID_FICT = re.compile(r"\bFICT[\s-]*(\d{3})[\s-]*(\d{3})[\s-]*(\d{3})[\s-]*AR\b")
_CPF = re.compile(r"(?<!\d)(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?!\d)")


def ids_de_documento(texto: str) -> set:
    t = norm(texto)
    return {"".join(m.groups()) for m in _ID_FICT.finditer(t)} | {m.group(1) for m in _ID_CORREIOS.finditer(t)}


def cpfs_do_texto(texto: str) -> set:
    return {"".join(m.groups()) for m in _CPF.finditer(texto or "")}


# o OCR costuma ler a barra como "1", "I", "l" ou "|": "Folha 2/2" vira "Folha 212". Só vale para total de um dígito.
_MARCADOR_BARRA_PERDIDA = re.compile(r"\b(?:PAGINAS?|PAG|PG|FOLHAS?|FLS?)\b\.?\s*([1-8])\s*[1IL|]\s*([2-9])\b")


def marcador_de_pagina(texto: str) -> Optional[Tuple[int, int]]:
    """(página, total) do primeiro marcador plausível do texto, ou None. Descarta leituras impossíveis (3/2, 0/5, total > 80)."""
    t = norm(texto)
    for m in _MARCADOR.finditer(t):
        x, y = int(m.group(1)), int(m.group(2))
        if 1 <= x <= y <= 80 and y >= 2:
            return x, y
    for m in _MARCADOR_BARRA_PERDIDA.finditer(t):
        x, y = int(m.group(1)), int(m.group(2))
        if x <= y:
            return x, y
    return None
