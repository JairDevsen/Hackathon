"""Qualidade da imagem da página: distingue página EM BRANCO de página BORRADA (e mede a nitidez).
Heurística (variância do filtro de bordas): o limite é configurável e deve ser calibrado com digitalizações reais."""
import io
import os
from PIL import Image, ImageFilter, ImageStat

NITIDEZ_MIN = float(os.environ.get("IA_NITIDEZ_MIN", "600"))  # texto nítido ≈ 2000; desfoque forte ≈ 400 (amostras sintéticas)


def analisar_imagem(png: bytes) -> dict:
    im = Image.open(io.BytesIO(png)).convert("L")
    im.thumbnail((800, 800))
    w, h = im.size
    miolo = im.crop((8, 8, w - 8, h - 8)) if w > 32 and h > 32 else im  # o filtro de bordas gera artefato nas margens
    std = ImageStat.Stat(miolo).stddev[0]
    hist = miolo.histogram()
    escuros = sum(hist[:128]) / max(sum(hist), 1)
    branco = std < 3 and escuros < 0.003
    nitidez = ImageStat.Stat(miolo.filter(ImageFilter.FIND_EDGES)).var[0]
    return {"branco": branco, "nitidez": round(nitidez, 1), "borrada": (not branco) and nitidez < NITIDEZ_MIN}
