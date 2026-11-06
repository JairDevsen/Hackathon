"""Checklist de conformidade por documento (validade, assinatura, NR-07/NR-06/NR-35...).
Cada item: {regra, status: OK|FALHA|ALERTA|REVISAO_HUMANA, detalhe}."""
import re
from datetime import date, timedelta
from typing import Dict, List

from .catalogo import TIPOS, norm


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def montar(tipo: str, texto: str, campos: Dict, confianca: float, ilegivel: bool = False, limiar: float = 0.75, hoje: date = None, borrada: bool = False) -> List[dict]:
    hoje = hoje or date.today()
    t = norm(texto)
    out: List[dict] = []
    add = lambda regra, status, detalhe: out.append({"regra": regra, "status": status, "detalhe": detalhe})

    if borrada:
        add("Legibilidade da leitura", "FALHA", "Imagem borrada: não foi possível ler o documento. Solicite o reenvio com imagem mais nítida")
    elif ilegivel or confianca < limiar:
        add("Legibilidade da leitura", "REVISAO_HUMANA", f"Confiança {confianca:.0%} abaixo do limiar ({limiar:.0%}): requer analista")
    else:
        add("Legibilidade da leitura", "OK", f"Confiança {confianca:.0%}")

    val = _d(campos.get("validade_ate"))
    if val:
        dias = (val - hoje).days
        if dias < 0:
            add("Validade vigente", "FALHA", f"Vencido em {val.strftime('%d/%m/%Y')}")
        elif dias <= 30:
            add("Validade vigente", "ALERTA", f"Vence em {dias} dia(s) ({val.strftime('%d/%m/%Y')})")
        else:
            add("Validade vigente", "OK", f"Válido até {val.strftime('%d/%m/%Y')}")

    if TIPOS.get(tipo, {}).get("assina"):
        if re.search(r"ASSINAD|ASSINATURA|RUBRICA", t):
            add("Assinatura identificada", "OK", "Assinatura/rubrica presente no documento")
        else:
            add("Assinatura identificada", "FALHA", "Nenhuma assinatura identificada")

    data = _d(campos.get("data_documento"))
    if tipo == "ASO":
        if "INAPTO" in t:
            add("NR-07 · Parecer médico", "FALHA", "Parecer INAPTO para a função")
        elif re.search(r"\bAPTO\b", t):
            add("NR-07 · Parecer médico", "OK", "Parecer APTO para a função")
        else:
            add("NR-07 · Parecer médico", "ALERTA", "Parecer não identificado")
        add("NR-07 · Médico responsável (CRM)", "OK" if re.search(r"CRM", t) else "ALERTA", "CRM identificado" if "CRM" in t else "CRM não identificado")
        if data:
            idade = (hoje - data).days
            add("NR-07 · Periodicidade (12 meses)", "OK" if idade <= 365 else "FALHA", f"Emitido há {idade} dia(s)")
    elif tipo == "FICHA_EPI":
        m = re.search(r"\bCA\s*(?:N[O°.]*)?\s*(\d{3,6})", t)
        add("NR-06 · Certificado de Aprovação (CA)", "OK" if m else "ALERTA", f"CA {m.group(1)} identificado" if m else "Número do CA não identificado")
    elif tipo == "TREINAMENTO_NR":
        m = re.search(r"NR[- ]?(\d{1,2})", t)
        add("Norma do treinamento", "OK" if m else "ALERTA", f"NR-{m.group(1)}" if m else "Norma não identificada")
        if data and not val:
            idade = (hoje - data).days
            add("Reciclagem (24 meses)", "OK" if idade <= 730 else "FALHA", f"Realizado há {idade} dia(s)")
    return out
