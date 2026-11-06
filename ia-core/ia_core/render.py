"""PDF do documento: original | pesquisável (camada de texto invisível posicionada) | anonimizado (tarja queimada na imagem)."""
import io
from typing import Dict, List, Optional

import fitz
from PIL import Image, ImageDraw


class RenderErro(Exception):
    pass


def _tarjar(png: bytes, caixas: List[list]) -> bytes:
    im = Image.open(io.BytesIO(png)).convert("RGB")
    d = ImageDraw.Draw(im)
    W, H = im.size
    for c in caixas:
        x0, y0, x1, y1 = c[0] * W, c[1] * H, c[2] * W, c[3] * H
        pad = 2
        d.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=(0, 0, 0))  # irreversível: os pixels são substituídos
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def gerar_pdf(modo: str, titulo: str, paginas: List[Dict]) -> bytes:
    """paginas: [{imagem: bytes, texto, palavras, caixas}]"""
    out = fitz.open()
    for p in paginas:
        png = p["imagem"]
        palavras = p.get("palavras") or []
        caixas = p.get("caixas") or []
        if modo == "anonimizado":
            if not palavras and not p.get("texto"):
                # sem OCR não há como saber onde estão os dados pessoais: recusar é mais seguro que fingir anonimizar
                raise RenderErro("OCR com caixas indisponível para esta página: não é possível garantir a anonimização")
            png = _tarjar(png, caixas)
        im = Image.open(io.BytesIO(png))
        w, h = im.size
        pg = out.new_page(width=w * 72 / 150, height=h * 72 / 150)
        pg.insert_image(pg.rect, stream=png)
        if modo == "pesquisavel":
            _camada_texto(pg, palavras, p.get("texto", ""))
        # no modo anonimizado a camada de texto NÃO é criada (refeita sem dados pessoais = sem texto original)
    if modo == "anonimizado":
        out.set_metadata({"title": "Cópia anonimizada", "author": "", "creator": "Citadel IA", "producer": "Citadel IA"})  # metadados removidos
    else:
        out.set_metadata({"title": titulo or "", "creator": "Citadel IA", "producer": "Citadel IA"})
    b = out.tobytes(deflate=True, garbage=3)
    out.close()
    return b


def _camada_texto(pg: "fitz.Page", palavras: List[list], texto: str) -> None:
    W, H = pg.rect.width, pg.rect.height
    if palavras:
        for x0, y0, x1, y1, t in palavras:
            alt = max((y1 - y0) * H, 4)
            pg.insert_text((x0 * W, y1 * H - alt * 0.2), str(t), fontsize=alt * 0.85, render_mode=3)  # 3 = invisível
        return
    # modo degradado (sem caixas de OCR): linhas distribuídas na página
    linhas = [l for l in texto.splitlines() if l.strip()]
    if not linhas:
        return
    passo = (H * 0.9) / max(len(linhas), 1)
    for i, l in enumerate(linhas):
        pg.insert_text((W * 0.05, H * 0.05 + (i + 1) * passo), l[:200], fontsize=min(passo * 0.8, 10), render_mode=3)
