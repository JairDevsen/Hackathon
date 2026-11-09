"""Qualidade da imagem da página: distingue página EM BRANCO de página BORRADA (e mede a nitidez).
Heurística (variância do filtro de bordas): o limite é configurável e deve ser calibrado com digitalizações reais."""
import io
import os
from PIL import Image, ImageChops, ImageFilter, ImageStat

NITIDEZ_MIN = float(os.environ.get("IA_NITIDEZ_MIN", "600"))  # texto nítido ≈ 2000; desfoque forte ≈ 400 (amostras sintéticas)


TINTA_MARCA = float(os.environ.get("IA_TINTA_MARCA", "0.002"))  # folha com só marca d'água/carimbo: tinta abaixo disto (a menor página real medida: 0,0029)
TINTA_MIN = float(os.environ.get("IA_TINTA_MIN", "0.0003"))  # fração de tinta AGRUPADA no miolo abaixo da qual a folha é vazia (menor página real medida: 0,0014; poeira: ≤ 0,00004)


def _tinta_no_miolo(im: Image.Image) -> tuple:
    """(tinta, tinta agrupada) no miolo da página: fração de pixels ESCUROS em relação ao fundo da própria folha. Ignora as margens (8% dos
    lados, 5% em cima e embaixo): sombra de borda do scanner, furos de perfuração, grampo, cabeçalho/rodapé e número de página não fazem uma
    folha ter conteúdo. A AGRUPADA só conta o escuro que tem outro escuro por perto (traço de letra, assinatura, carimbo): poeira e pontinhos
    de ruído, que são isolados, ficam de fora, e um bilhete manuscrito curto, não."""
    w, h = im.size
    mx, my = int(w * 0.08), int(h * 0.05)
    miolo = im.crop((mx, my, w - mx, h - my)) if w > 40 and h > 40 else im
    hist = miolo.histogram()
    total = max(sum(hist), 1)
    acum, fundo = 0, 255
    for v, n in enumerate(hist):  # mediana = cor do papel (pode ser cinza/amarelada)
        acum += n
        if acum >= total / 2:
            fundo = v
            break
    corte = max(min(fundo - 60, 200), 0)  # escuro de verdade: bem abaixo do papel (granulado do scanner fica de fora)
    escuro = miolo.point(lambda v: 255 if v < corte else 0)
    tinta = escuro.histogram()[255] / total
    if tinta == 0:
        return 0.0, 0.0
    vizinhanca = escuro.filter(ImageFilter.BoxBlur(4)).point(lambda v: 255 if v >= 20 else 0)  # janela 9x9 com ao menos ~8% de escuro
    return tinta, ImageChops.multiply(escuro, vizinhanca).histogram()[255] / total


def analisar_imagem(png: bytes) -> dict:
    im = Image.open(io.BytesIO(png)).convert("L")
    im.thumbnail((800, 800))
    w, h = im.size
    miolo = im.crop((8, 8, w - 8, h - 8)) if w > 32 and h > 32 else im  # o filtro de bordas gera artefato nas margens
    std = ImageStat.Stat(miolo).stddev[0]
    hist = miolo.histogram()
    escuros = sum(hist[:128]) / max(sum(hist), 1)
    tinta, agrupada = _tinta_no_miolo(im)
    branco = (std < 3 and escuros < 0.003) or agrupada < TINTA_MIN  # folha lisa, ou só com sombra de borda/furos/poeira/ruído/rodapé
    nitidez = ImageStat.Stat(miolo.filter(ImageFilter.FIND_EDGES)).var[0]
    return {"branco": branco, "nitidez": round(nitidez, 1), "tinta": round(tinta, 5), "agrupada": round(agrupada, 5), "borrada": (not branco) and nitidez < NITIDEZ_MIN}
