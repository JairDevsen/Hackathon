"""Elementos físicos sobre a página: grampo, clipe, post-it, dobra, carimbo de recebimento."""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .canvas import Escritor, Folha, fonte_impressa

NOTAS_POSTIT = ["conferir", "urgente!", "ver c/ RH", "pago", "falta assinar", "2ª via", "arquivar", "ok - conferido", "devolver", "lançar"]


def grampo(img: Image.Image, rng: random.Random) -> None:
    d = ImageDraw.Draw(img)
    x, y = rng.randint(40, 110), rng.randint(40, 110)
    ang = rng.uniform(-0.8, -0.3)
    comp = rng.randint(70, 95)
    x2, y2 = x + comp * np.cos(ang), y + comp * np.sin(ang)
    d.line([(x + 3, y + 4), (x2 + 3, y2 + 4)], fill=(120, 120, 120), width=6)  # sombra
    d.line([(x, y), (x2, y2)], fill=(185, 188, 195), width=5)
    d.line([(x, y - 2), (x2, y2 - 2)], fill=(235, 238, 242), width=1)


def clipe(img: Image.Image, rng: random.Random) -> None:
    camada = Image.new("RGBA", (120, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    cor = rng.choice([(150, 152, 160, 255), (60, 90, 170, 255), (190, 60, 60, 255)])
    d.rounded_rectangle([20, 10, 100, 290], radius=40, outline=cor, width=7)
    d.rounded_rectangle([38, 40, 82, 230], radius=22, outline=cor, width=7)
    camada = camada.rotate(rng.uniform(-12, 12), expand=True, resample=Image.BICUBIC)
    sombra = camada.filter(ImageFilter.GaussianBlur(4))
    x = rng.randint(int(img.width * 0.15), int(img.width * 0.75))
    img.paste((90, 90, 90), (x + 6, -150 + 8), sombra)
    img.paste(camada, (x, -150), camada)


def post_it(img: Image.Image, rng: random.Random) -> str:
    lado = rng.randint(260, 340)
    nota = Folha(rng, (lado, lado), rng.choice([(255, 242, 140), (255, 200, 210), (190, 240, 170)]))
    nota.taxa_defeito = 0
    texto = rng.choice(NOTAS_POSTIT)
    esc = Escritor.aleatorio(rng, "pressa")
    nota.linhas_mao(20, int(lado * 0.38), lado - 40, texto, esc, tam=48)
    rgba = nota.img.convert("RGBA").rotate(rng.uniform(-10, 10), expand=True, resample=Image.BICUBIC)
    sombra = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    sombra.putalpha(rgba.getchannel("A").point(lambda a: 60 if a else 0).filter(ImageFilter.GaussianBlur(6)))
    # canto superior direito ou margem inferior, para não cobrir os dados
    x = img.width - rgba.width - rng.randint(5, 60)
    y = rng.choice([rng.randint(5, 60), img.height - rgba.height - rng.randint(70, 140)])
    img.paste(sombra, (x + 8, y + 10), sombra)
    img.paste(rgba, (x, y), rgba)
    return texto


def dobra(img: Image.Image, rng: random.Random) -> None:
    """Vinco de papel dobrado em três (ou ao meio): faixa de luz e sombra."""
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    for frac in rng.choice([[1 / 3, 2 / 3], [0.5]]):
        y = int(h * frac + rng.uniform(-30, 30))
        perfil = np.ones(h, dtype=np.float32)
        largura = rng.randint(14, 30)
        for i in range(-largura, largura):
            if 0 <= y + i < h:
                perfil[y + i] = 1 - 0.13 * np.exp(-((i + 4) ** 2) / 30) + 0.05 * np.exp(-((i - 6) ** 2) / 40)
        a *= perfil[:, None, None]
    img.paste(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))


def carimbo_recebido(img: Image.Image, rng: random.Random, data: str) -> None:
    f = Folha(rng, img.size)
    f.img = img
    f.d = ImageDraw.Draw(img)
    x = rng.choice([img.width * 0.78, img.width * 0.25])
    f.carimbo(x, rng.randint(170, 320), ["RECEBIDO", data, "SETOR DE CONTRATOS"], cor=rng.choice([(40, 60, 140), (150, 40, 40)]))


def aplicar(img: Image.Image, rng: random.Random, prob: float, data_recebimento: str) -> list[str]:
    """Aplica extras com probabilidade `prob` cada (sobre a página já finalizada). Retorna os nomes aplicados."""
    feitos = []
    if rng.random() < prob:
        grampo(img, rng)
        feitos.append("grampo")
    if rng.random() < prob * 0.6:
        clipe(img, rng)
        feitos.append("clipe")
    if rng.random() < prob * 0.5:
        feitos.append(f"post_it:{post_it(img, rng)}")
    if rng.random() < prob * 0.7:
        dobra(img, rng)
        feitos.append("dobra")
    if rng.random() < prob * 0.5:
        carimbo_recebido(img, rng, data_recebimento)
        feitos.append("carimbo_recebido")
    return feitos
