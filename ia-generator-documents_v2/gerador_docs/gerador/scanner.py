"""Simula digitalização: papel, tinta, inclinação, sombra, ruído, perda de resolução, fotocópia e JPEG."""
from __future__ import annotations

import io
import random

import cv2
import numpy as np
from PIL import Image

NIVEIS = {
    #         rotação  ruído  blur          jpeg     escala_min
    "leve":  (0.6,     3.0,   (0.0, 0.4),   (88, 95), 0.95),
    "media": (1.6,     6.0,   (0.3, 0.8),   (65, 85), 0.75),
    "forte": (3.5,     10.0,  (0.6, 1.3),   (40, 65), 0.55),
}


def digitalizar(img: Image.Image, rng: random.Random, nivel: str = "media") -> Image.Image:
    rot_max, ruido, (b0, b1), (q0, q1), esc_min = NIVEIS[nivel]
    np_rng = np.random.default_rng(rng.randrange(2**32))
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w = a.shape[:2]

    # 1. papel: tom amarelado/acinzentado + textura de baixa frequência
    g = rng.uniform(0.96, 1.0)
    tom = np.array([1.0, g, g * rng.uniform(0.88, 1.0)], dtype=np.float32)  # branco, amarelado ou acinzentado (nunca rosado)
    textura = cv2.GaussianBlur(np_rng.normal(0, 1, (h // 8, w // 8)).astype(np.float32), (0, 0), 3)
    textura = cv2.resize(textura, (w, h)) * rng.uniform(2, 6)
    a = a * tom - textura[..., None]

    # 2. espalhamento da tinta
    sigma = rng.uniform(b0, b1)
    if sigma > 0.05:
        a = cv2.GaussianBlur(a, (0, 0), sigma)

    # 3. sombra de tampa/lombada em uma borda
    if rng.random() < 0.5:
        largura = int(w * rng.uniform(0.03, 0.10))
        grad = np.ones(w, dtype=np.float32)
        grad[:largura] = np.linspace(rng.uniform(0.55, 0.8), 1.0, largura)
        if rng.random() < 0.5:
            grad = grad[::-1]
        a *= grad[None, :, None]

    # 4. furos de grampo/arquivo
    if rng.random() < 0.25:
        for yy in (int(h * 0.42), int(h * 0.58)):
            cv2.circle(a, (int(w * 0.045), yy), 16, (60, 60, 60), -1)

    # 5. inclinação e leve perspectiva (folha torta no scanner)
    ang = rng.uniform(-rot_max, rot_max)
    m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    borda = rng.choice([(245, 245, 245), (40, 40, 40), (200, 200, 200)])
    a = cv2.warpAffine(a, m, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=borda)
    if nivel == "forte" and rng.random() < 0.5:
        d = w * 0.02
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[rng.uniform(0, d), rng.uniform(0, d)], [w - rng.uniform(0, d), rng.uniform(0, d)],
                          [w - rng.uniform(0, d), h - rng.uniform(0, d)], [rng.uniform(0, d), h - rng.uniform(0, d)]])
        a = cv2.warpPerspective(a, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=borda)

    # 6. ruído e sujeira
    a += np_rng.normal(0, ruido, a.shape).astype(np.float32)
    n_pontos = int(rng.uniform(20, 120) * (ruido / 5))
    for _ in range(n_pontos):
        cv2.circle(a, (rng.randrange(w), rng.randrange(h)), rng.randint(1, 3), (rng.uniform(20, 90),) * 3, -1)

    a = np.clip(a, 0, 255).astype(np.uint8)

    # 7. fotocópia (preto e branco contrastado) ou escala de cinza
    sorteio = rng.random()
    if sorteio < 0.2:
        g = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
        g = cv2.convertScaleAbs(g, alpha=1.5, beta=-60)
        a = cv2.cvtColor(g, cv2.COLOR_GRAY2RGB)
    elif sorteio < 0.5:
        a = cv2.cvtColor(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)

    # 8. perda de resolução (scanner de baixa qualidade)
    esc = rng.uniform(esc_min, 1.0)
    if esc < 0.98:
        p = cv2.resize(a, (int(w * esc), int(h * esc)), interpolation=cv2.INTER_AREA)
        a = cv2.resize(p, (w, h), interpolation=cv2.INTER_LINEAR)

    # 9. compressão JPEG
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, format="JPEG", quality=rng.randint(q0, q1))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def foto_celular(img: Image.Image, rng: random.Random) -> Image.Image:
    """Página fotografada sobre uma mesa: perspectiva, fundo, luz irregular, sombra de mão/celular."""
    np_rng = np.random.default_rng(rng.randrange(2**32))
    pg = np.asarray(img.convert("RGB").resize((1240, 1754))).astype(np.float32)
    H, W = 2000, 1500
    base = np.array(rng.choice([(120, 85, 55), (165, 130, 95), (70, 70, 75), (190, 190, 185), (40, 45, 60)]), dtype=np.float32)
    fundo = np.ones((H, W, 3), np.float32) * base
    veios = cv2.GaussianBlur(np_rng.normal(0, 1, (H, W // 6)).astype(np.float32), (0, 0), 2)
    fundo += cv2.resize(veios, (W, H))[..., None] * rng.uniform(6, 14)
    h, w = pg.shape[:2]
    m = 0.06
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    cx, cy = W * rng.uniform(0.47, 0.53), H * rng.uniform(0.47, 0.53)
    esc = rng.uniform(0.80, 0.92)
    hw, hh = W * esc / 2, H * esc / 2
    dst = np.float32([[cx - hw + rng.uniform(-m, m) * W, cy - hh + rng.uniform(-m, m) * H],
                      [cx + hw + rng.uniform(-m, m) * W, cy - hh + rng.uniform(-m, m) * H],
                      [cx + hw + rng.uniform(-m, m) * W, cy + hh + rng.uniform(-m, m) * H],
                      [cx - hw + rng.uniform(-m, m) * W, cy + hh + rng.uniform(-m, m) * H]])
    M_ = cv2.getPerspectiveTransform(src, dst)
    folha = cv2.warpPerspective(pg, M_, (W, H))
    mascara = cv2.warpPerspective(np.ones((h, w), np.float32), M_, (W, H))[..., None]
    a = folha * mascara + fundo * (1 - mascara)
    # iluminação: gradiente + vinheta + sombra
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = rng.uniform(0, 2 * np.pi)
    grad = 1 + rng.uniform(0.08, 0.22) * ((xx / W - 0.5) * np.cos(ang) + (yy / H - 0.5) * np.sin(ang))
    vinheta = 1 - 0.18 * (((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) * 2)
    a *= (grad * vinheta)[..., None]
    if rng.random() < 0.6:
        sombra = np.zeros((H, W), np.float32)
        cv2.ellipse(sombra, (int(rng.uniform(0, W)), int(rng.choice([rng.uniform(-200, 200), rng.uniform(H - 200, H + 200)]))),
                    (int(W * rng.uniform(0.25, 0.45)), int(H * rng.uniform(0.15, 0.3))), rng.uniform(0, 180), 0, 360, 1, -1)
        a *= (1 - cv2.GaussianBlur(sombra, (0, 0), 70) * rng.uniform(0.25, 0.45))[..., None]
    a += np_rng.normal(0, rng.uniform(3, 7), a.shape).astype(np.float32)
    a = np.clip(a, 0, 255).astype(np.uint8)
    if rng.random() < 0.3:  # tremida
        k = rng.choice([5, 7, 9])
        ker = np.zeros((k, k), np.float32)
        ker[k // 2, :] = 1 / k
        a = cv2.filter2D(a, -1, cv2.warpAffine(ker, cv2.getRotationMatrix2D((k / 2, k / 2), rng.uniform(0, 180), 1), (k, k)))
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, format="JPEG", quality=rng.randint(55, 85))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def capturar(img: Image.Image, rng: random.Random, nivel: str = "media", p_celular: float = 0.15,
             p_cabeca_para_baixo: float = 0.03) -> tuple[Image.Image, dict]:
    """Escolhe a forma de captura da página e devolve a imagem + metadados para o gabarito."""
    if rng.random() < p_celular:
        out, modo = foto_celular(img, rng), "foto_celular"
    else:
        out, modo = digitalizar(img, rng, nivel), f"scanner_{nivel}"
    rot = 0
    if rng.random() < p_cabeca_para_baixo:
        out, rot = out.rotate(180), 180
    return out, {"captura": modo, "rotacao": rot}
