"""Validações trabalhistas: alertas por documento e não conformidades (painel do administrador)."""
import re
from datetime import date
from typing import Dict, List, Tuple

from .catalogo import TIPOS, norm
from .extracao import cpf_valido


def _hhmm(s: str) -> float:
    m = re.match(r"(\d{1,2})[:hH](\d{2})", s)
    return int(m.group(1)) + int(m.group(2)) / 60 if m else 0.0


def _valor(s: str) -> float:
    s = re.sub(r"[^\d,]", "", s or "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def validar(tipo: str, texto: str, campos: Dict, hoje: date = None) -> Tuple[List[dict], List[dict]]:
    hoje = hoje or date.today()
    t = norm(texto)
    alertas: List[dict] = []
    ncs: List[dict] = []

    def nc(codigo: str, desc: str, sev: str = "aviso"):
        ncs.append({"codigo": codigo, "descricao": desc})
        alertas.append({"severidade": sev, "codigo": codigo, "mensagem": desc})

    if campos.get("cpf") and not cpf_valido(campos["cpf"]):
        alertas.append({"severidade": "aviso", "codigo": "CPF_INVALIDO", "mensagem": "CPF com dígito verificador inválido"})
    val = campos.get("validade_ate")
    if val:
        try:
            dv = date.fromisoformat(val)
            if dv < hoje:
                br = dv.strftime("%d/%m/%Y")
                if tipo in ("CRF_FGTS", "CNDT", "CND_FEDERAL"):
                    nc("CERTIDAO_VENCIDA", f"Certidão vencida em {br}", "erro")
                else:
                    alertas.append({"severidade": "erro", "codigo": "DOCUMENTO_VENCIDO", "mensagem": f"Documento vencido em {br}"})
        except ValueError:
            pass
    if TIPOS.get(tipo, {}).get("assina") and not re.search(r"ASSINAD|ASSINATURA|RUBRICA", t):
        nc("DOCUMENTO_SEM_ASSINATURA", "Documento sem assinatura identificada")
    if tipo == "CARTAO_PONTO":
        m = re.search(r"JORNADA(?: DIARIA)?\s*[:\-]?\s*(\d{1,2}[:hH]\d{2})", t)
        if m and _hhmm(m.group(1)) > 10:
            nc("JORNADA_ACIMA_10H", f"Jornada diária de {m.group(1)} excede 10 horas")
        m = re.search(r"INTERVALO\s*[:\-]?\s*(\d{1,2}[:hH]\d{2})", t)
        if m and _hhmm(m.group(1)) < 1:
            nc("INTERVALO_INFERIOR_1H", f"Intervalo intrajornada de {m.group(1)} é menor que 1 hora")
        if "PONTO BRITANICO" in t or "HORARIOS IDENTICOS" in t:
            nc("PONTO_BRITANICO", "Marcações idênticas todos os dias (ponto britânico)")
    if tipo in ("HOLERITE", "GUIA_FGTS"):
        a = re.search(r"FGTS DEPOSITADO\s*[:\-]?\s*R?\$?\s*([\d\.,]+)", t)
        b = re.search(r"FGTS DEVIDO\s*[:\-]?\s*R?\$?\s*([\d\.,]+)", t)
        if a and b and abs(_valor(a.group(1)) - _valor(b.group(1))) > 0.01:
            nc("FGTS_DIVERGENTE", f"FGTS depositado (R$ {a.group(1)}) difere do devido (R$ {b.group(1)})", "erro")
    if "RECUSOU" in t and "ASSINAR" in t and "TESTEMUNHA" not in t:
        nc("RECUSA_SEM_TESTEMUNHAS", "Recusa de ciência sem assinatura de testemunhas")
    return alertas, ncs
