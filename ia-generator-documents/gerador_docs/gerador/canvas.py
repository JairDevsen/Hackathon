"""Primitivas de desenho: texto impresso, letra de mão, tabelas, assinaturas, carimbos e marca d'água.

Tudo é desenhado em A4 a 200 dpi (1654 x 2339 px).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DPI = 200
A4 = (1654, 2339)
DIR_FONTES = Path(__file__).resolve().parents[1] / "fontes"

# estilo -> [(fonte, fator de tamanho para altura visual parecida)]
ESTILOS = {
    "forma": [("PatrickHand-Regular.ttf", 1.05), ("Kalam-Regular.ttf", 0.95), ("ArchitectsDaughter.ttf", 0.85),
              ("GochiHand.ttf", 1.0), ("IndieFlower-Regular.ttf", 1.0)],
    "cursiva": [("DancingScript.ttf", 1.0), ("HomemadeApple.ttf", 0.72), ("CedarvilleCursive.ttf", 0.9),
                ("LaBelleAurore.ttf", 0.9), ("Kristi.ttf", 1.25)],
    "pressa": [("ReenieBeanie.ttf", 1.25), ("NothingYouCouldDo.ttf", 0.85), ("WaitingfortheSunrise.ttf", 1.0),
               ("JustAnotherHand.ttf", 1.35), ("ShadowsIntoLight.ttf", 1.05), ("Caveat.ttf", 1.25)],
    "medico": [("Zeyada.ttf", 1.25), ("MrDafoe.ttf", 1.0), ("ReenieBeanie.ttf", 1.2), ("LaBelleAurore.ttf", 0.9)],
}
TINTAS = [(25, 35, 120), (20, 20, 25), (30, 50, 150), (15, 25, 80)]  # azul, preta, azul claro, azul escuro
GRAFITE = (85, 85, 90)

MARCA_DAGUA = "AMOSTRA – DOCUMENTO FICTÍCIO"
RODAPE = "AMOSTRA – DOCUMENTO FICTÍCIO · gerado para testes de software · sem validade jurídica"
DEFEITOS = ["riscado", "rasura", "corretivo", "fora_da_linha"]


# Registro do que foi desenhado (usado pela conferência do gabarito)
_REGISTRO: list[list[str]] = []


_FOLHAS: list[list] = []


class registrar:
    """with registrar() as reg: ... -> reg.itens recebe todo texto/assinatura/carimbo desenhado no bloco
    e reg.folhas todas as Folhas criadas (para coletar os defeitos de escrita)."""
    def __enter__(self):
        self.itens: list[str] = []
        self.folhas: list = []
        _REGISTRO.append(self.itens)
        _FOLHAS.append(self.folhas)
        return self

    def __exit__(self, *exc):
        _REGISTRO.remove(self.itens)
        _FOLHAS.remove(self.folhas)


def _log(s: str) -> None:
    for r in _REGISTRO:
        r.append(s)


@lru_cache(maxsize=256)
def fonte(nome: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(DIR_FONTES / nome), max(6, int(tam)))


def fonte_impressa(tam: int, bold: bool = False, mono: bool = False, condensada: bool = False):
    nome = "DejaVuSansMono.ttf" if mono else "DejaVuSans-Bold.ttf" if bold else "DejaVuSansCondensed.ttf" if condensada else "DejaVuSans.ttf"
    return fonte(nome, tam)


@dataclass
class Escritor:
    """Estilo de letra de uma pessoa: o mesmo escritor preenche o documento inteiro."""
    fonte: str
    tinta: tuple[int, int, int]
    inclinacao: float  # graus
    tremor: float      # 0..1.5
    escala: float
    estilo: str = "forma"
    caixa_alta: bool = False
    lapis: bool = False

    @classmethod
    def aleatorio(cls, rng: random.Random, estilo: str | None = None) -> "Escritor":
        estilo = estilo or rng.choices(["forma", "cursiva", "pressa"], [0.42, 0.30, 0.28])[0]
        f, fator = rng.choice(ESTILOS[estilo])
        lapis = estilo != "medico" and rng.random() < 0.07
        tremor = {"forma": (0.3, 0.8), "cursiva": (0.3, 0.8), "pressa": (0.8, 1.3), "medico": (1.0, 1.5)}[estilo]
        incl = rng.uniform(-14, -4) if estilo in ("pressa", "medico") else rng.uniform(-7, 3)
        return cls(f, GRAFITE if lapis else rng.choice(TINTAS), incl, rng.uniform(*tremor), fator * rng.uniform(0.9, 1.1),
                   estilo, estilo == "forma" and rng.random() < 0.3, lapis)


def brl(v: float) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_cpf(c: str) -> str:
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c


def fmt_cnpj(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c


def fmt_data(iso: str | None) -> str:
    if not iso:
        return ""
    a, m, d = iso.split("-")
    return f"{d}/{m}/{a}"


def _alterar(s: str, rng: random.Random) -> str:
    """Versão 'errada' do texto, escrita antes da correção."""
    pos = [i for i, c in enumerate(s) if c.isalnum()]
    if not pos:
        return s + "x"
    i = rng.choice(pos)
    c = s[i]
    novo = str((int(c) + rng.randint(1, 8)) % 10) if c.isdigit() else rng.choice("aeiourlnst")
    return s[:i] + novo + s[i + 1:]


class Folha:
    taxa_defeito_padrao = 0.0  # ajustado pela montagem do lote
    taxa_branco_padrao = 0.0

    def __init__(self, rng: random.Random, tamanho: tuple[int, int] = A4, fundo=(255, 255, 255)):
        self.rng = rng
        self.img = Image.new("RGB", tamanho, fundo)
        self.d = ImageDraw.Draw(self.img)
        self.w, self.h = tamanho
        self.taxa_defeito = Folha.taxa_defeito_padrao
        self.taxa_branco = Folha.taxa_branco_padrao
        self.defeitos: list[dict] = []
        for lst in _FOLHAS:
            lst.append(self)

    def talvez(self, valor, campo: str):
        """Campo opcional que o preenchedor pode deixar em branco. Use o retorno no gabarito."""
        if valor is not None and self.rng.random() < self.taxa_branco:
            self.defeitos.append({"defeito": "campo_em_branco", "campo": campo})
            return None
        return valor

    # ------------------------------------------------------------ impresso
    def texto(self, xy, s: str, tam=26, bold=False, mono=False, cond=False, cor=(15, 15, 15), anchor="la", max_w=None):
        f = fonte_impressa(tam, bold, mono, cond)
        while max_w and f.getlength(s) > max_w and tam > 10:
            tam -= 1
            f = fonte_impressa(tam, bold, mono, cond)
        self.d.text(xy, s, font=f, fill=cor, anchor=anchor)
        _log(s)
        return f.getlength(s)

    def paragrafo(self, x, y, largura, s: str, tam=24, entrelinha=1.45, **kw) -> int:
        f = fonte_impressa(tam, kw.get("bold", False))
        linha = ""
        for palavra in s.split():
            teste = f"{linha} {palavra}".strip()
            if f.getlength(teste) > largura:
                self.texto((x, y), linha, tam, **kw)
                y += int(tam * entrelinha)
                linha = palavra
            else:
                linha = teste
        if linha:
            self.texto((x, y), linha, tam, **kw)
            y += int(tam * entrelinha)
        return y

    def caixa(self, x0, y0, x1, y1, largura=2, cor=(30, 30, 30), preenchimento=None):
        self.d.rectangle([x0, y0, x1, y1], outline=cor, width=largura, fill=preenchimento)

    def linha(self, x0, y0, x1, y1, largura=2, cor=(30, 30, 30)):
        self.d.line([x0, y0, x1, y1], fill=cor, width=largura)

    def campo(self, x0, y0, x1, y1, rotulo: str, valor: str | None, escritor: Escritor | None = None, tam_valor=30, mono=False):
        """Caixa com rótulo pequeno no canto e valor impresso (escritor=None) ou à mão."""
        self.caixa(x0, y0, x1, y1)
        self.texto((x0 + 8, y0 + 5), rotulo, 17, cond=True, cor=(60, 60, 60))
        if valor:
            if escritor:
                self.mao((x0 + 14, y1 - 14), valor, escritor, tam=tam_valor + 6, max_w=x1 - x0 - 24)
            else:
                self.texto((x0 + 12, y1 - 12), valor, tam_valor - 4, mono=mono, anchor="ls", max_w=x1 - x0 - 22)

    def checkbox(self, x, y, rotulo: str, marcado: bool, escritor: Escritor | None, tam=24):
        self.caixa(x, y, x + 28, y + 28, 2)
        self.texto((x + 40, y + 2), rotulo, tam)
        if marcado:
            _log(f"<marcado:{rotulo}>")
        if marcado and escritor:
            self.mao((x + 1, y + 30), "X", escritor, tam=44)
        elif marcado:
            self.texto((x + 5, y), "X", 26, bold=True)

    # ------------------------------------------------------------ manuscrito
    def mao(self, xy, s: str, esc: Escritor, tam=36, max_w=None, sem_defeito=False) -> float:
        """Escreve à mão. Com taxa_defeito > 0, às vezes escreve errado e corrige (riscado, rasura, corretivo)
        ou escreve fora da linha. O valor final legível é sempre `s` (é o que vai para o gabarito)."""
        if esc.caixa_alta:
            s = s.upper()
        rng = self.rng
        if sem_defeito or len(s.strip()) < 2 or rng.random() >= self.taxa_defeito:
            return self._mao(xy, s, esc, tam, max_w)
        defeito = rng.choice(DEFEITOS)
        self.defeitos.append({"defeito": defeito, "texto": s})
        x, y = xy
        alt = tam * esc.escala
        if defeito == "fora_da_linha":
            inc = esc.inclinacao
            esc.inclinacao += rng.choice([-1, 1]) * rng.uniform(3, 7)
            w = self._mao((x + rng.uniform(-10, 25), y + rng.uniform(-0.45, 0.3) * alt), s, esc, tam, max_w)
            esc.inclinacao = inc
            return w
        if defeito == "corretivo":
            est = fonte(esc.fonte, int(alt)).getlength(s) * 1.1 + 20
            if max_w:
                est = min(est, max_w + 10)
            self.d.rounded_rectangle([x - 8, y - alt * 0.85, x + est, y + alt * 0.25], radius=8,
                                     fill=(250, 250, 246), outline=(205, 205, 200), width=2)
            return self._mao(xy, s, esc, tam, max_w)
        errado = _alterar(s, rng)
        meio_w = (max_w * 0.45) if max_w else None
        w1 = self._mao(xy, errado, esc, tam * (0.8 if max_w else 1), meio_w)
        if defeito == "riscado":
            yy = y - alt * 0.3
            self.d.line([(x - 4, yy + rng.uniform(-3, 3)), (x + w1 + 4, yy + rng.uniform(-3, 3))], fill=esc.tinta, width=3)
        else:  # rasura: rabisco por cima
            pts, xx = [], x - 4
            while xx < x + w1 + 4:
                pts += [(xx, y - alt * rng.uniform(0.6, 0.8)), (xx + 6, y + rng.uniform(-2, 4))]
                xx += rng.uniform(7, 11)
            self.d.line(pts, fill=esc.tinta, width=3)
        resto = (max_w - w1 - alt * 0.4) if max_w else None
        return w1 + alt * 0.4 + self._mao((x + w1 + alt * 0.4, y), s, esc, tam * (0.8 if max_w else 1),
                                          max(resto, 60) if resto is not None else None)

    def _mao(self, xy, s: str, esc: Escritor, tam=36, max_w=None) -> float:
        """Escreve à mão caractere a caractere, com variação de tamanho, linha de base, rotação e pressão.
        xy é o ponto inicial da linha de base."""
        _log(s)
        tam = tam * esc.escala
        base_f = fonte(esc.fonte, int(tam))
        estimada = base_f.getlength(s) * 1.07 + len(s) * tam * 0.02  # inclui o espaçamento irregular
        if max_w and estimada > max_w:
            tam *= max_w / estimada
        x, y = xy
        rng = self.rng
        deriva = 0.0
        for ch in s:
            t = tam * (1 + rng.uniform(-0.07, 0.07) * esc.tremor)
            f = fonte(esc.fonte, int(t))
            avanco = f.getlength(ch)
            if ch != " ":
                lado = int(t * 2.2)
                glifo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
                alfa = rng.randint(110, 175) if esc.lapis else rng.randint(185, 255)
                ImageDraw.Draw(glifo).text((lado * 0.25, lado * 0.7), ch, font=f, fill=(*esc.tinta, alfa), anchor="ls")
                ang = -esc.inclinacao + rng.uniform(-4, 4) * esc.tremor
                glifo = glifo.rotate(ang, resample=Image.BICUBIC, center=(lado * 0.25, lado * 0.7))
                deriva += rng.uniform(-0.6, 0.6) * esc.tremor
                deriva = max(-4, min(4, deriva))
                dy = rng.uniform(-2.2, 2.2) * esc.tremor + deriva
                self.img.paste(glifo, (int(x - lado * 0.25), int(y + dy - lado * 0.7)), glifo)
            x += avanco * (1 + rng.uniform(-0.05, 0.08)) + t * 0.02
        return x - xy[0]

    def assinatura(self, x0, y0, x1, y1, esc: Escritor, nome: str | None = None):
        """Rubrica sintética: uma inicial manuscrita + traços em curva."""
        _log("<assinatura>")
        rng = self.rng
        camada = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        meio = (y0 + y1) / 2
        x = x0 + rng.uniform(0, (x1 - x0) * 0.15)
        if nome:
            inicial = nome.strip()[0].upper()
            f = fonte(esc.fonte, int((y1 - y0) * 0.9 * esc.escala))
            d.text((x, meio + (y1 - y0) * 0.25), inicial, font=f, fill=(*esc.tinta, 235), anchor="ls")
            x += f.getlength(inicial) * 0.8
        pontos = []
        fim = x0 + (x1 - x0) * rng.uniform(0.6, 0.95)
        n = rng.randint(14, 26)
        amp = (y1 - y0) * rng.uniform(0.18, 0.38)
        freq = rng.uniform(2.5, 5.5)
        for i in range(n + 1):
            t = i / n
            px = x + (fim - x) * t
            py = meio + amp * math.sin(t * freq * math.pi + rng.uniform(-0.4, 0.4)) * (1 - 0.5 * t)
            pontos.append((px, py))
        d.line(pontos, fill=(*esc.tinta, 230), width=rng.randint(2, 4), joint="curve")
        if rng.random() < 0.7:  # traço de sublinhado
            yy = meio + amp * 1.1
            d.line([(x0 + (x1 - x0) * 0.1, yy + rng.uniform(-6, 6)), (fim + 20, yy + rng.uniform(-8, 8))], fill=(*esc.tinta, 220), width=2)
        self.img.paste(camada, (0, 0), camada)

    def carimbo(self, cx, cy, linhas: list[str], cor=(70, 40, 140)):
        _log("<carimbo>")
        for l in linhas:
            _log(l)
        rng = self.rng
        f = fonte_impressa(22, bold=True)
        larg = int(max(f.getlength(l) for l in linhas)) + 40
        alt = len(linhas) * 32 + 30
        c = Image.new("RGBA", (larg + 20, alt + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        alfa = rng.randint(120, 185)
        d.rounded_rectangle([10, 10, larg + 10, alt + 10], radius=14, outline=(*cor, alfa), width=4)
        for i, l in enumerate(linhas):
            d.text((larg / 2 + 10, 34 + i * 32), l, font=f, fill=(*cor, alfa), anchor="mm")
        c = c.rotate(rng.uniform(-9, 9), expand=True, resample=Image.BICUBIC)
        self.img.paste(c, (int(cx - c.width / 2), int(cy - c.height / 2)), c)

    # ------------------------------------------------------------ tabela
    def tabela(self, x, y, larguras: list[int], alt_linha: int, cabecalho: list[str], linhas: list[list[str]],
               escritor: Escritor | None = None, cols_mao: set[int] | None = None, tam=22, mono=False) -> int:
        total = sum(larguras)
        self.caixa(x, y, x + total, y + alt_linha, 2, preenchimento=(235, 235, 235))
        cx = x
        for w, h in zip(larguras, cabecalho):
            self.texto((cx + w / 2, y + alt_linha / 2), h, tam - 2, bold=True, anchor="mm", max_w=w - 8)
            cx += w
        y += alt_linha
        for row in linhas:
            cx = x
            for i, (w, val) in enumerate(zip(larguras, row)):
                self.caixa(cx, y, cx + w, y + alt_linha, 1)
                if val:
                    if escritor and cols_mao and i in cols_mao:
                        self.mao((cx + 8, y + alt_linha - 8), val, escritor, tam=alt_linha * 0.85, max_w=w - 14)
                    else:
                        self.texto((cx + 8, y + alt_linha / 2), val, tam, mono=mono, anchor="lm", max_w=w - 14)
                cx += w
            y += alt_linha
        return y

    # ------------------------------------------------------------ segurança
    def linhas_mao(self, x, y, largura, texto: str, esc: Escritor, tam=40, entrelinha=1.55, pautado: bool = False) -> int:
        """Parágrafo manuscrito com quebra de linha. Retorna o y seguinte."""
        f = fonte(esc.fonte, int(tam * esc.escala))
        linha_h = int(tam * entrelinha)
        atual = ""
        for palavra in texto.split():
            teste = f"{atual} {palavra}".strip()
            if f.getlength(teste) * 1.12 > largura and atual:
                self.mao((x + self.rng.uniform(-6, 10), y), atual, esc, tam, max_w=largura)
                y += linha_h
                atual = palavra
            else:
                atual = teste
        if atual:
            self.mao((x + self.rng.uniform(-6, 10), y), atual, esc, tam, max_w=largura)
            y += linha_h
        return y

    def pautar(self, y0: int, passo: int, margem_esq: int = 160, cor=(150, 175, 215)):
        """Folha de caderno/bloco pautado."""
        for y in range(y0, self.h - 80, passo):
            self.linha(0, y, self.w, y, 2, cor)
        self.linha(margem_esq, 0, margem_esq, self.h, 2, (225, 120, 120))

    def finalizar(self) -> Image.Image:
        """Marca 'AMOSTRA – DOCUMENTO FICTÍCIO' discreta (canto + rodapé + diagonal bem leve). Chamado em TODA página."""
        lado = int((self.w ** 2 + self.h ** 2) ** 0.5)
        camada = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        tam = max(30, int(self.w * 0.048))
        f = fonte_impressa(tam, bold=True)
        n = max(1, round(self.h / 900))
        for i in range(n):
            dy = (i - (n - 1) / 2) * min(self.w, self.h) * 0.55
            d.text((lado / 2, lado / 2 + dy), MARCA_DAGUA, font=f, fill=(120, 120, 120, 22), anchor="mm")
        camada = camada.rotate(32, resample=Image.BICUBIC)
        x0, y0 = (lado - self.w) // 2, (lado - self.h) // 2
        camada = camada.crop((x0, y0, x0 + self.w, y0 + self.h))
        self.img.paste(camada, (0, 0), camada)
        tam_r = max(12, min(18, int(self.w / 90)))
        self.texto((self.w / 2, self.h - 22 - tam_r), RODAPE, tam_r, cor=(110, 110, 110), anchor="mm", max_w=self.w - 40)
        tag = fonte_impressa(tam_r, bold=True)
        lw = tag.getlength(MARCA_DAGUA) + 16
        self.d.rectangle([self.w - lw - 14, 10, self.w - 14, 14 + tam_r * 1.6], outline=(150, 150, 150), width=1)
        self.d.text((self.w - lw - 6, 13), MARCA_DAGUA, font=tag, fill=(130, 130, 130))
        self.img.info["ficticio"] = True
        return self.img
