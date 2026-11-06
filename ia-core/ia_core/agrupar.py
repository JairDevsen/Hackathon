"""Agrupamento determinístico de páginas em documentos a partir dos rótulos por página."""
from typing import Dict, List

from .anonimizacao import anonimizar_texto
import re

from . import checklist as _cl
from .catalogo import TIPOS
from .validacoes import validar

CUSTO_POR_1K_TOKENS_BRL = 0.0004
BASELINE_TOKENS_VISION = 1500  # referência: página inteira enviada como imagem sem otimização
CAMADA_PADRAO = "Camada 1: Texto nativo + regex local (custo zero)"


def _nivel(camada: str) -> int:
    m = re.search(r"Camada (\d)", camada or "")
    return int(m.group(1)) if m else 1


def agrupar(analises: Dict[int, dict]) -> List[dict]:
    """analises: {numero: Pagina}. Páginas em branco separam documentos e são descartadas.
    Verso/continuação (inicia_documento=false) anexa ao último documento do mesmo tipo — mesmo que a página
    anterior seja de outro documento (frente e verso separados, página intercalada)."""
    grupos: List[dict] = []
    abertos: Dict[str, dict] = {}
    ultimo = None
    for n in sorted(analises):
        a = analises[n]
        if a.get("pagina_em_branco"):
            ultimo = None
            continue
        tipo = a["tipo"]
        alvo = None
        if not a.get("inicia_documento", True):
            alvo = ultimo if ultimo and ultimo["tipo"] == tipo else abertos.get(tipo)
        if alvo is None:
            alvo = {"tipo": tipo, "paginas": [], "textos": [], "confs": [], "campos": {}, "manuscrito": False, "ilegivel": False, "multi": False, "tokens": 0, "titulo": a.get("titulo", ""), "camadas": [], "shas": [], "borrada": False}
            grupos.append(alvo)
        alvo["paginas"].append(n)
        alvo["textos"].append(a.get("texto_ocr", ""))
        alvo["confs"].append(float(a.get("confianca", 0)))
        for k, v in (a.get("campos") or {}).items():
            if v and not alvo["campos"].get(k):
                alvo["campos"][k] = v
        alvo["manuscrito"] |= bool(a.get("possui_manuscrito"))
        alvo["ilegivel"] |= bool(a.get("pagina_ilegivel"))
        alvo["borrada"] |= bool(a.get("borrada"))
        alvo["multi"] |= bool(a.get("multiplos_documentos_na_imagem"))
        alvo["tokens"] += int(a.get("tokens", 0) or 0)
        alvo["camadas"].append(a.get("camada") or CAMADA_PADRAO)
        alvo["shas"].append(a.get("sha256") or "")
        abertos[tipo] = alvo
        ultimo = alvo
    docs = []
    for g in grupos:
        texto = "\n\n".join(g["textos"])
        alertas, ncs = validar(g["tipo"], texto, g["campos"])
        motivos = []
        if g["borrada"]:
            alertas.append({"severidade": "erro", "codigo": "IMAGEM_BORRADA", "mensagem": "Não foi possível realizar a leitura do documento. Envie uma imagem mais nítida."})
            motivos.append("IMAGEM_BORRADA")
        anon, sensiveis = anonimizar_texto(texto)
        conf = round(min(g["confs"]) if g["confs"] else 0.0, 3)  # o documento vale pela pior página
        camada = max(g["camadas"], key=_nivel) if g["camadas"] else CAMADA_PADRAO
        base = BASELINE_TOKENS_VISION * len(g["paginas"])
        economia = 100.0 if _nivel(camada) == 0 else round(min(100.0, max(0.0, 100.0 * (base - g["tokens"]) / base)), 1)
        docs.append({
            "tipo": g["tipo"], "titulo": g["titulo"] or TIPOS[g["tipo"]]["nome"], "paginas": g["paginas"], "confianca": conf,
            "campos": g["campos"], "alertas": alertas, "motivos_revisao": motivos, "nao_conformidades": ncs, "dados_sensiveis": sensiveis,
            "texto_ocr": texto, "texto_anonimizado": anon, "possui_manuscrito": g["manuscrito"], "pagina_ilegivel": g["ilegivel"],
            "multiplos_documentos_na_imagem": g["multi"],
            "checklist": _cl.montar(g["tipo"], texto, g["campos"], conf, g["ilegivel"], borrada=g["borrada"]),
            "finops": {"camada_roteamento": camada, "sha256_hash": next((x for x in g["shas"] if x), ""), "tokens_consumidos": g["tokens"],
                       "tokens_economizados": max(0, base - g["tokens"]), "economia_estimada_pct": economia,
                       "custo_estimado_brl": round(g["tokens"] / 1000 * CUSTO_POR_1K_TOKENS_BRL, 4)},
        })
    return docs
