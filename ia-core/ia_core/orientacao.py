"""Orientação da página: páginas escaneadas de cabeça para baixo (ou de lado) saem do OCR como lixo e viram "OUTRO",
o que quebra o agrupamento do documento. Aqui a página é lida de novo girada, só quando o primeiro OCR não parece texto."""
import io
import re
from typing import Callable, Tuple

from PIL import Image

from .catalogo import TIPOS, norm

_COMUNS = ("PARA COM POR UMA DOS DAS NOS NAS DATA NOME EMPRESA DOCUMENTO VALOR TOTAL NUMERO ASSINATURA EMPREGADO EMPREGADOR "
           "TRABALHADOR DECLARO CONFORME PERIODO CONTRATO CLAUSULA PAGINA FOLHA SERVICOS LTDA ENDERECO RUA AVENIDA CIDADE ESTADO "
           "SALARIO FUNCAO CARGO ADMISSAO RECEBIMENTO ENTREGA UNIDADE ATESTADO MEDICO EXAME").split()
_VOCAB = set(_COMUNS) | {w for d in TIPOS.values() for p in d["pistas"] for w in re.findall(r"[A-Z]{4,}", p.replace("\\b", " "))}
LIMIAR = 5  # palavras reconhecíveis: abaixo disso o texto lido não parece uma página legível


def ocr_texto(png: bytes) -> str:
    """OCR local (Tesseract via PyMuPDF). Sem Tesseract devolve vazio (a página vai para revisão)."""
    try:
        import fitz

        pix = fitz.Pixmap(png)
        doc = fitz.open()
        page = doc.new_page(width=pix.width, height=pix.height)
        page.insert_image(page.rect, stream=png)
        tp = page.get_textpage_ocr(language="por", dpi=150, full=True)
        return page.get_text("text", textpage=tp)
    except Exception:
        return ""


def palavras_reconhecidas(texto: str) -> int:
    return sum(1 for w in re.findall(r"[A-Z]{3,}", norm(texto)) if w in _VOCAB)


def girar(png: bytes, graus: int) -> bytes:
    im = Image.open(io.BytesIO(png)).convert("RGB").rotate(graus, expand=True)  # sentido anti-horário
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def endireitar(png: bytes, largura_ocr: int = 1100) -> Tuple[bytes, int]:
    """(imagem na orientação correta, graus aplicados). Descobre a orientação numa cópia reduzida (rápido) e gira a imagem
    original, sem perder resolução. Sem Tesseract ou sem texto reconhecível, devolve a imagem como veio."""
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width > largura_ocr:
        im = im.resize((largura_ocr, round(im.height * largura_ocr / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "PNG")
    graus, _ = melhor_orientacao(b.getvalue(), ocr_texto)
    return (girar(png, graus), graus) if graus else (png, 0)


def melhor_orientacao(png: bytes, ocr: Callable[[bytes], str]) -> Tuple[int, str]:
    """(graus, texto): lê a página como veio e, se o texto não parece legível, tenta 180°, 90° e 270°; fica com a melhor leitura.
    Página em branco ou sem texto nenhum não é girada (não há o que ganhar)."""
    texto = ocr(png)
    pontos = palavras_reconhecidas(texto)
    if pontos >= LIMIAR or len(re.findall(r"[A-Za-z]", texto)) < 25:
        return 0, texto
    melhor = (0, texto, pontos)
    for graus in (180, 90, 270):
        t = ocr(girar(png, graus))
        pt = palavras_reconhecidas(t)
        if pt > melhor[2]:
            melhor = (graus, t, pt)
        if pt >= LIMIAR:
            break
    # só troca se a leitura girada for claramente melhor (evita girar manuscrito/ruído por acaso)
    if melhor[0] and melhor[2] >= LIMIAR and melhor[2] >= pontos + 3:
        return melhor[0], melhor[1]
    return 0, texto
