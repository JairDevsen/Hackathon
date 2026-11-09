"""Agrupamento determinístico de páginas em documentos a partir dos rótulos por página."""
from typing import Dict, List

from .anonimizacao import anonimizar_texto
import re

from . import checklist as _cl
from .catalogo import COMPLEMENTOS, TIPOS, dados_tipo_ia, norm, registrar_tipo
from .extracao import aviso_em_branco
from .paginacao import cpfs_do_texto, ids_de_documento, marcador_de_pagina
from .validacoes import validar

CUSTO_POR_1K_TOKENS_BRL = 0.0004
BASELINE_TOKENS_VISION = 1500  # referência: página inteira enviada como imagem sem otimização
CAMADA_PADRAO = "Camada 1: Texto nativo + regex local (custo zero)"


def _nivel(camada: str) -> int:
    m = re.search(r"Camada (\d)", camada or "")
    return int(m.group(1)) if m else 1


def _novo(tipo: str, a: dict) -> dict:
    return {"tipo": tipo, "paginas": [], "textos": [], "confs": [], "campos": {}, "manuscrito": False, "ilegivel": False, "multi": False, "tokens": 0,
            "titulo": a.get("titulo", ""), "camadas": [], "shas": [], "borrada": False, "total": 0, "complemento": False, "so_complemento": False, "ids": set(), "cpfs": set(), "melhor": (-1.0, tipo)}


def _complemento_de(texto: str) -> str:
    """Tipo do documento que esta página completa (verso, termo anexo), pelas frases de COMPLEMENTOS; "" se não for o caso."""
    t = norm(texto)
    colado = t.replace(" ", "")  # o OCR costuma perder espaços entre palavras ("geralquitação")
    for frase, tipo in COMPLEMENTOS.items():
        # só é complemento puro se a página NÃO traz o título do próprio tipo: uma folha com frente e verso (AR) já está completa
        if (frase in t or frase.replace(" ", "") in colado) and TIPOS[tipo]["pistas"][0] not in t:
            return tipo
    return ""


def _outro_documento(g: dict, ids: set) -> bool:
    """Os dois lados trazem número de documento legível e ele difere: são documentos distintos (ex.: dois ARs seguidos)."""
    return bool(ids and g["ids"] and not ids & g["ids"])


def _continua(n, a, tipo, mk, comp, ids, cpfs, grupos, abertos, ultimo):
    """(documento ao qual a página `n` pertence, ou None para abrir um novo; tipo a usar). Regras na docstring de `agrupar`."""
    if mk and mk[0] > 1:  # "Página 2/3": a contagem manda, mesmo que o tipo lido da página 1 seja outro
        for c in (ultimo, abertos.get(tipo)):
            if not c:
                continue
            mesmo_total = c["total"] == mk[1] and len(c["paginas"]) < mk[1]   # o documento já declarou ter este total de páginas
            so_pela_contagem = len(c["paginas"]) == mk[0] - 1 and (c["tipo"] in (tipo, "OUTRO") or c["melhor"][0] < 0.6)
            if mesmo_total or so_pela_contagem:   # sem total declarado, não cola em documento de outro tipo bem identificado
                return c, tipo
        return None, tipo
    if mk:  # "Página 1/N" começa documento
        return None, tipo
    if ids:  # mesmo número de documento (objeto do AR): frente e verso se encontram mesmo longe um do outro
        alvo = next((g for g in reversed(grupos) if g["ids"] & ids and len(g["paginas"]) < 6), None)
        if alvo:
            return alvo, tipo
    if comp:
        if ultimo and ultimo["tipo"] == comp and not ultimo["complemento"] and ultimo["paginas"][-1] == n - 1 and not _outro_documento(ultimo, ids):
            return ultimo, comp
        # fora de ordem ou com outra página no meio: liga pelo CPF do trabalhador; sem CPF legível, só se houver um único
        # candidato muito próximo (até 2 páginas antes)
        livres = [g for g in grupos if g["tipo"] == comp and not g["complemento"] and not _outro_documento(g, ids)]
        por_cpf = [g for g in livres if g["cpfs"] & cpfs]
        perto = [g for g in livres if n - g["paginas"][-1] <= 2]
        return (por_cpf[-1] if por_cpf else perto[0] if len(perto) == 1 else None), comp
    if (ultimo and ultimo["so_complemento"] and ultimo["tipo"] == tipo and ultimo["paginas"][-1] == n - 1
            and not _outro_documento(ultimo, ids) and (not ultimo["cpfs"] or not cpfs or ultimo["cpfs"] & cpfs)):
        return ultimo, tipo  # o termo anexo veio ANTES da página principal do mesmo documento
    if not a.get("inicia_documento", True):
        return (ultimo if ultimo and ultimo["tipo"] == tipo else abertos.get(tipo)), tipo
    return None, tipo


def agrupar(analises: Dict[int, dict]) -> List[dict]:
    """analises: {numero: Pagina}. Páginas em branco separam documentos e são descartadas.

    A decisão de "esta página continua o documento anterior?" segue, nesta ordem (vale para qualquer provedor de IA):
      1. marcador impresso "Página 2/3": continua o documento aberto se a contagem fecha, mesmo que o tipo lido seja outro
         (a página 1 pode ter vindo ilegível ou rotacionada); "Página 1/3" abre um documento novo;
      2. página complementar conhecida (ex.: "Termo de quitação" do TRCT, "Dados do recebimento" do AR): entra no documento
         anterior daquele tipo e herda o tipo dele;
      3. inicia_documento=false informado pela análise: anexa ao último documento do mesmo tipo, mesmo que a página
         anterior seja de outro documento (frente e verso separados, página intercalada).
    O tipo final do documento é o da página lida com mais confiança (uma página ilegível não rebaixa o documento a "OUTRO")."""
    for a in analises.values():  # lote retomado em outro processo: reaprende os tipos que a IA descobriu nas páginas já analisadas
        tn = a.get("tipo_novo")
        if isinstance(tn, dict) and tn.get("codigo") and tn["codigo"] not in TIPOS:
            registrar_tipo(tn["codigo"], tn.get("nome", tn["codigo"]), tn.get("pistas"), tn.get("escopo", "FUNCIONARIO"), tn.get("categoria", "OUTROS"))
    grupos: List[dict] = []
    abertos: Dict[str, dict] = {}
    ultimo = None
    for n in sorted(analises):
        a = analises[n]
        if a.get("pagina_em_branco") or aviso_em_branco(a.get("texto_ocr", "")):  # folha vazia nunca vira documento (nem "OUTRO")
            ultimo = None
            continue
        tipo = a["tipo"]
        texto = a.get("texto_ocr", "")
        mk = marcador_de_pagina(texto)
        comp = _complemento_de(texto)
        ids, cpfs = ids_de_documento(texto), cpfs_do_texto(texto)
        alvo, tipo = _continua(n, a, tipo, mk, comp, ids, cpfs, grupos, abertos, ultimo)
        if alvo is None:
            alvo = _novo(tipo, a)
            grupos.append(alvo)
        elif comp:
            alvo["complemento"] = True
        if alvo["paginas"] == [] and comp:
            alvo["so_complemento"] = True
        elif alvo["so_complemento"] and not comp:
            alvo["so_complemento"] = False
        alvo["ids"] |= ids
        alvo["cpfs"] |= cpfs
        if mk:
            alvo["total"] = alvo["total"] or mk[1]
        alvo["paginas"].append(n)
        alvo["textos"].append(texto)
        conf = float(a.get("confianca", 0))
        alvo["confs"].append(conf)
        if tipo != "OUTRO" and conf > alvo["melhor"][0]:  # tipo e título do documento: o da melhor leitura
            alvo["melhor"] = (conf, tipo)
            alvo["tipo"], alvo["titulo"] = tipo, a.get("titulo", "") or alvo["titulo"]
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
        abertos[alvo["tipo"]] = alvo
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
            "tipo": g["tipo"], "tipo_novo": dados_tipo_ia(g["tipo"]), "titulo": g["titulo"] or TIPOS.get(g["tipo"], TIPOS["OUTRO"])["nome"], "paginas": g["paginas"], "confianca": conf,
            "campos": g["campos"], "alertas": alertas, "motivos_revisao": motivos, "nao_conformidades": ncs, "dados_sensiveis": sensiveis,
            "texto_ocr": texto, "texto_anonimizado": anon, "possui_manuscrito": g["manuscrito"], "pagina_ilegivel": g["ilegivel"],
            "multiplos_documentos_na_imagem": g["multi"],
            "checklist": _cl.montar(g["tipo"], texto, g["campos"], conf, g["ilegivel"], borrada=g["borrada"]),
            "finops": {"camada_roteamento": camada, "sha256_hash": next((x for x in g["shas"] if x), ""), "tokens_consumidos": g["tokens"],
                       "tokens_economizados": max(0, base - g["tokens"]), "economia_estimada_pct": economia,
                       "custo_estimado_brl": round(g["tokens"] / 1000 * CUSTO_POR_1K_TOKENS_BRL, 4)},
        })
    return docs
