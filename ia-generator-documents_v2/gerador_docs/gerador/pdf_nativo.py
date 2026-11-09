"""Exportação de páginas como PDF NATIVO (como sai de um sistema: texto vetorial e selecionável, sem scanner).

Como funciona:
  - cada Folha grava as operações vetoriais (texto impresso, caixas, linhas, código de barras);
  - o que NÃO é vetor (letra de mão, assinatura, carimbo, foto) é detectado comparando a página final
    com uma reprodução só-vetorial, e entra no PDF como imagem PNG transparente por cima do vetor;
  - a marca "AMOSTRA – DOCUMENTO FICTÍCIO" é desenhada como texto vetorial (diagonal + rodapé + canto).
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from .canvas import DPI, MARCA_DAGUA, fonte_impressa

PX = 72 / DPI  # pixel (200 dpi) -> ponto PDF
_FONTES: dict[str, str] = {}


def _fonte_rl(font) -> str:
    caminho = font.path
    if caminho not in _FONTES:
        nome = f"F{len(_FONTES)}"
        pdfmetrics.registerFont(TTFont(nome, caminho))
        _FONTES[caminho] = nome
    return _FONTES[caminho]


def _caixa(box):
    if len(box) == 2:
        (x0, y0), (x1, y1) = box
    else:
        x0, y0, x1, y1 = box
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _pontos(xy):
    if xy and isinstance(xy[0], (tuple, list)):
        return [tuple(p) for p in xy]
    return [(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)]


def _base(font, texto, x, y, anchor):
    """Converte o ponto de âncora do Pillow em (x à esquerda, y da linha de base) em pixels."""
    asc, desc = font.getmetrics()
    w = font.getlength(texto)
    h_anchor, v_anchor = anchor[0], anchor[1]
    x0 = x - (w / 2 if h_anchor == "m" else w if h_anchor == "r" else 0)
    if v_anchor == "a":
        yb = y + asc
    elif v_anchor == "m":
        yb = y + (asc - desc) / 2
    elif v_anchor == "d":
        yb = y - desc
    else:  # "s" (baseline)
        yb = y
    return x0, yb


def _marca_raster(folha, img: Image.Image) -> None:
    """Reproduz a marca do Folha.finalizar para a comparação (fica fora do overlay)."""
    lado = int((folha.w ** 2 + folha.h ** 2) ** 0.5)
    camada = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    f = fonte_impressa(max(30, int(folha.w * 0.048)), bold=True)
    n = max(1, round(folha.h / 900))
    for i in range(n):
        dy = (i - (n - 1) / 2) * min(folha.w, folha.h) * 0.55
        d.text((lado / 2, lado / 2 + dy), MARCA_DAGUA, font=f, fill=(120, 120, 120, 22), anchor="mm")
    camada = camada.rotate(32, resample=Image.BICUBIC)
    x0, y0 = (lado - folha.w) // 2, (lado - folha.h) // 2
    camada = camada.crop((x0, y0, x0 + folha.w, y0 + folha.h))
    img.paste(camada, (0, 0), camada)


def reproduzir_vetor(folha) -> Image.Image:
    img = Image.new("RGB", (folha.w, folha.h), folha.fundo)
    d = ImageDraw.Draw(img)
    for op in folha.ops:
        k = op[0]
        if k == "text":
            _, xy, texto, font, fill, anchor = op
            d.text(xy, texto, font=font, fill=fill, anchor=anchor)
        elif k == "rect":
            d.rectangle(op[1], outline=op[2], fill=op[3], width=op[4])
        elif k == "rrect":
            d.rounded_rectangle(op[1], radius=op[2], outline=op[3], fill=op[4], width=op[5])
        elif k == "line":
            d.line(op[1], fill=op[2], width=op[3])
        elif k == "ellipse":
            d.ellipse(op[1], outline=op[2], fill=op[3], width=op[4])
        elif k == "marca":
            _marca_raster(folha, img)
    return img


@dataclass
class Analise:
    overlay: Image.Image | None  # RGBA recortado
    posicao: tuple[int, int]
    fracao_raster: float          # fração da página que não é vetor


def analisar(img: Image.Image) -> Analise | None:
    """None se a imagem não veio de uma Folha com operações gravadas."""
    folha = img.info.get("folha")
    if folha is None or not folha.ops or folha.img is not img and folha.img.size != img.size:
        return None
    if "_analise_nativo" in img.info:
        return img.info["_analise_nativo"]
    final = np.asarray(img.convert("RGB")).astype(np.int16)
    vetor = np.asarray(reproduzir_vetor(folha)).astype(np.int16)
    mascara = np.abs(final - vetor).max(axis=2) > 24
    m = Image.fromarray((mascara * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
    mascara = np.asarray(m) > 0
    fr = float(mascara.mean())
    if not mascara.any():
        res = Analise(None, (0, 0), 0.0)
    else:
        ys, xs = np.where(mascara)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        rgba = np.dstack([final[y0:y1, x0:x1].astype(np.uint8), (mascara[y0:y1, x0:x1] * 255).astype(np.uint8)])
        res = Analise(Image.fromarray(rgba, "RGBA"), (int(x0), int(y0)), fr)
    img.info["_analise_nativo"] = res
    return res


def _cor(c, padrao=(0, 0, 0)):
    c = c if c is not None else padrao
    if isinstance(c, str):
        return (0, 0, 0)
    return tuple(v / 255 for v in c[:3])


def desenhar_pagina_nativa(cv: rl_canvas.Canvas, img: Image.Image) -> None:
    folha = img.info["folha"]
    W, H = folha.w * PX, folha.h * PX
    cv.setPageSize((W, H))
    Y = lambda y: H - y * PX  # noqa: E731
    if tuple(folha.fundo[:3]) != (255, 255, 255):
        cv.setFillColorRGB(*_cor(folha.fundo))
        cv.rect(0, 0, W, H, stroke=0, fill=1)
    for op in folha.ops:
        k = op[0]
        if k == "text":
            _, (x, y), texto, font, fill, anchor = op
            x0, yb = _base(font, texto, x, y, anchor)
            cv.setFillColorRGB(*_cor(fill))
            cv.setFont(_fonte_rl(font), font.size * PX)
            cv.drawString(x0 * PX, Y(yb), texto)
        elif k in ("rect", "rrect", "ellipse"):
            if k == "rrect":
                _, box, raio, outline, fill, width = op
            else:
                _, box, outline, fill, width = op
                raio = 0
            x0, y0, x1, y1 = _caixa(box)
            cv.setLineWidth(max(width, 1) * PX)
            if outline is not None:
                cv.setStrokeColorRGB(*_cor(outline))
            if fill is not None:
                cv.setFillColorRGB(*_cor(fill))
            st, fi = int(outline is not None), int(fill is not None)
            if k == "ellipse":
                cv.ellipse(x0 * PX, Y(y1), x1 * PX, Y(y0), stroke=st, fill=fi)
            elif raio:
                cv.roundRect(x0 * PX, Y(y1), (x1 - x0) * PX, (y1 - y0) * PX, raio * PX, stroke=st, fill=fi)
            else:
                cv.rect(x0 * PX, Y(y1), (x1 - x0) * PX, (y1 - y0) * PX, stroke=st, fill=fi)
        elif k == "line":
            _, xy, fill, width = op
            pts = _pontos(xy)
            cv.setStrokeColorRGB(*_cor(fill))
            cv.setLineWidth(max(width, 1) * PX)
            caminho = cv.beginPath()
            caminho.moveTo(pts[0][0] * PX, Y(pts[0][1]))
            for px_, py_ in pts[1:]:
                caminho.lineTo(px_ * PX, Y(py_))
            cv.drawPath(caminho, stroke=1, fill=0)
        elif k == "marca":
            f = fonte_impressa(max(30, int(folha.w * 0.048)), bold=True)
            cv.saveState()
            cv.setFillColorRGB(120 / 255, 120 / 255, 120 / 255)
            cv.setFillAlpha(22 / 255)
            cv.translate(W / 2, H / 2)
            cv.rotate(32)
            cv.setFont(_fonte_rl(f), f.size * PX)
            n = max(1, round(folha.h / 900))
            for i in range(n):
                dy = (i - (n - 1) / 2) * min(folha.w, folha.h) * 0.55
                cv.drawCentredString(0, -dy * PX - f.size * PX * 0.35, MARCA_DAGUA)
            cv.restoreState()
    a = analisar(img)
    if a and a.overlay is not None:  # letra de mão, assinatura, carimbo, foto
        buf = io.BytesIO()
        a.overlay.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        ow, oh = a.overlay.size
        cv.drawImage(ImageReader(buf), a.posicao[0] * PX, Y(a.posicao[1] + oh), ow * PX, oh * PX, mask="auto")
    cv.showPage()


def desenhar_pagina_imagem(cv: rl_canvas.Canvas, img: Image.Image, qualidade: int = 82) -> None:
    W, H = img.width * PX, img.height * PX
    cv.setPageSize((W, H))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=qualidade)
    buf.seek(0)
    cv.drawImage(ImageReader(buf), 0, 0, W, H)
    cv.showPage()


def escrever_pdf(caminho, paginas: list[tuple[str, Image.Image]], titulo: str = "") -> None:
    """paginas: lista de ("nativo"|"imagem", img). invariant=1 => mesma entrada gera o mesmo arquivo."""
    cv = rl_canvas.Canvas(str(caminho), invariant=1, pageCompression=1)
    cv.setTitle(titulo)
    cv.setAuthor("Gerador de documentos fictícios – AMOSTRA")
    for tipo, img in paginas:
        if tipo == "nativo":
            desenhar_pagina_nativa(cv, img)
        else:
            desenhar_pagina_imagem(cv, img)
    cv.save()
