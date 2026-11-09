"""PDF do documento: original | pesquisável (camada de texto invisível posicionada) | anonimizado (tarja queimada na imagem)."""
import io
import os
import subprocess
import tempfile
from typing import Dict, List, Optional

import fitz
from PIL import Image, ImageDraw, ImageOps

from .anonimizacao import caixas_de_nomes, caixas_de_palavras


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


def _ocr_passada(img: Image.Image, psm: str) -> List[list]:
    """Uma passada do Tesseract (TSV): palavras com posição em frações da página."""
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, "p.png")
        img.save(arq)
        r = subprocess.run(["tesseract", arq, "stdout", "-l", "por", "--psm", psm, "tsv"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "falha no Tesseract").strip()[:200])
    W, H = img.size
    palavras = []
    for linha in r.stdout.splitlines()[1:]:
        c = linha.split("\t")
        if len(c) >= 12 and c[0] == "5" and c[11].strip():
            x, y, w, h = (int(v) for v in c[6:10])
            palavras.append([x / W, y / H, (x + w) / W, (y + h) / H, c[11].strip()])
    return palavras


def _ocr(png: bytes) -> List[List[list]]:
    """Lê a imagem por OCR local em várias passadas (tons de cinza e contraste, com leiaute de bloco e de texto solto).

    O OCR de páginas escaneadas é instável (inclinação, ruído, carimbos): um dado que uma passada erra, outra costuma ler.
    Por isso devolve as palavras de cada passada; as tarjas são a união das detecções. Falha se o Tesseract não existir."""
    try:
        im = Image.open(io.BytesIO(png)).convert("L")
        if im.width < 1650:  # ~200 dpi em A4: tamanho em que o Tesseract lê melhor texto pequeno
            im = im.resize((1650, round(im.height * 1650 / im.width)), Image.LANCZOS)
        contraste = ImageOps.autocontrast(im, cutoff=2)
        return [_ocr_passada(im, "6"), _ocr_passada(contraste, "6"), _ocr_passada(contraste, "11")]
    except Exception as e:
        raise RenderErro("não foi possível localizar os dados pessoais desta página (OCR local indisponível: instale o Tesseract com o idioma português); a cópia anonimizada não foi gerada para não expor dados") from e


def gerar_pdf(modo: str, titulo: str, paginas: List[Dict], termos: Optional[List[str]] = None) -> bytes:
    """paginas: [{imagem: bytes, texto, palavras, caixas}]; termos: nomes já conhecidos a tarjar (modo anonimizado)."""
    out = fitz.open()
    for p in paginas:
        png = p["imagem"]
        palavras = p.get("palavras") or []
        caixas = p.get("caixas") or []
        if modo == "anonimizado":
            # página escaneada (só imagem): lê a imagem para saber onde estão os dados pessoais. Sem OCR não há como
            # anonimizar; recusar é mais seguro que entregar um documento "anonimizado" sem tarja.
            passadas = [palavras] if palavras and p.get("texto_nativo") else ([palavras] if palavras else []) + _ocr(png)
            extra = [c for pal in passadas for c in caixas_de_palavras(pal) + caixas_de_nomes(pal, termos or [])]
            # as caixas guardadas no fatiamento podem estar incompletas; a detecção é refeita sobre as palavras com posição
            png = _tarjar(png, list(caixas) + extra)
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
