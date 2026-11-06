"""Detecção de dados pessoais (campos + regex) e geração das caixas de tarja."""
import re
from typing import Dict, List, Tuple

CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
RG = re.compile(r"\bRG\b[:\s]*[\d\.\-Xx]{6,12}")
CEP = re.compile(r"\b\d{5}-\d{3}\b")
TEL = re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
CID = re.compile(r"\bCID[:\s-]*[A-Z]\d{2}(?:\.\d)?\b")
PIS = re.compile(r"\bPIS[:\s/-]*\d{3}\.?\d{5}\.?\d{2}-?\d\b")
BANCO = re.compile(r"\b(?:AG[ÊE]NCIA|CONTA)[:\s]*\d{3,}[-\d]*", re.I)
NOME = re.compile(r"(?:NOME|COLABORADOR|TITULAR|DESTINAT[ÁA]RIO|RECEBEDOR)[^:\n]{0,40}:\s*([A-ZÀ-Ú][A-Za-zÀ-ú' ]{4,60})")

PADROES = [("CPF", CPF), ("CNPJ", CNPJ), ("RG", RG), ("CEP", CEP), ("TELEFONE", TEL), ("EMAIL", EMAIL), ("CID", CID), ("PIS", PIS), ("DADO_BANCARIO", BANCO)]


def mascarar(tipo: str, valor: str) -> str:
    d = re.sub(r"\D", "", valor)
    if tipo == "CPF" and len(d) == 11:
        return f"***.{d[3:6]}.{d[6:9]}-**"
    if tipo == "CNPJ":
        return "**.***.***/****-**"
    return "[" + tipo + " OCULTO]"


def detectar(texto: str) -> List[Dict]:
    """Lista de ocorrências {tipo, valor, mascarado}; `valor` não sai do IA Core (só o mascarado)."""
    out = []
    for tipo, rx in PADROES:
        for m in rx.finditer(texto):
            out.append({"tipo": tipo, "valor": m.group(0), "mascarado": mascarar(tipo, m.group(0))})
    for m in NOME.finditer(texto):
        out.append({"tipo": "NOME", "valor": m.group(1).strip(), "mascarado": "[NOME OCULTO]"})
    return out


def anonimizar_texto(texto: str) -> Tuple[str, List[Dict]]:
    itens = detectar(texto)
    res = texto
    for it in sorted(itens, key=lambda i: -len(i["valor"])):
        res = res.replace(it["valor"], it["mascarado"])
    publicos = [{"tipo": i["tipo"], "mascarado": i["mascarado"]} for i in itens]
    return res, publicos
