"""Roda o IA Core sobre uma pasta de documentos de teste e mede o acerto.

Uso:
  export GEMINI_API_KEY="<sua-chave>"
  python scripts/avaliar.py amostras/ --saida resultados/

Gabarito opcional (amostras/gabarito.csv), uma linha por página:
  arquivo,pagina,tipo,inicia_documento
  lote01.pdf,1,HOLERITE,1
  lote01.pdf,2,HOLERITE,0
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ia_core import IACore, Pagina, validar  # noqa: E402
from ia_core.prompts import VERSAO_PROMPT  # noqa: E402

LADO_MAX = 3072  # o Gemini reduz acima disso; reduzir antes economiza upload


def _png(img: Image.Image) -> bytes:
    img = img.convert("RGB")
    img.thumbnail((LADO_MAX, LADO_MAX))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def carregar_paginas(arq: Path) -> list[Pagina]:
    """Versão simples do fatiador (o oficial é do Dev 3)."""
    if arq.suffix.lower() == ".pdf":
        pdf = pdfium.PdfDocument(arq)
        return [Pagina(i + 1, _png(pdf[i].render(scale=200 / 72).to_pil())) for i in range(len(pdf))]
    img = Image.open(arq)
    paginas, i = [], 0
    while True:  # TIFF multipágina
        paginas.append(Pagina(i + 1, _png(img.copy())))
        i += 1
        try:
            img.seek(i)
        except EOFError:
            return paginas


def carregar_gabarito(pasta: Path) -> dict[tuple[str, int], tuple[str, bool]]:
    g = pasta / "gabarito.csv"
    if not g.exists():
        return {}
    with g.open(encoding="utf-8") as f:
        return {(r["arquivo"], int(r["pagina"])): (r["tipo"], r["inicia_documento"] == "1") for r in csv.DictReader(f)}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", type=Path)
    ap.add_argument("--saida", type=Path, default=Path("resultados"))
    args = ap.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)

    ia = IACore()
    gabarito = carregar_gabarito(args.pasta)
    acertos_tipo = acertos_quebra = total = 0
    confusao: Counter = Counter()
    resumo = []

    exts = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    for arq in sorted(p for p in args.pasta.iterdir() if p.suffix.lower() in exts):
        paginas = carregar_paginas(arq)
        rotulos = await ia.classificar_lote(paginas)
        docs = ia.agrupar(rotulos)
        por_num = {p.numero: p for p in paginas}
        extracoes = await asyncio.gather(*(ia.extrair(d, por_num) for d in docs))

        saida = {"arquivo": arq.name, "versao_prompt": VERSAO_PROMPT, "paginas": [r.model_dump(mode="json") for r in rotulos], "documentos": []}
        for ex in extracoes:
            alertas = validar(ex.dados) if ex.dados else []
            saida["documentos"].append({
                "indice": ex.documento.indice, "tipo": ex.documento.tipo.value, "paginas": ex.documento.paginas,
                "confianca": ex.documento.confianca, "motivos_revisao": ex.documento.motivos_revisao,
                "modelo": ex.modelo_usado, "erro": ex.erro,
                "dados": ex.dados.model_dump(mode="json") if ex.dados else None,
                "alertas": [a.__dict__ for a in alertas],
            })
            resumo.append([arq.name, ex.documento.indice, ex.documento.tipo.value, ex.documento.paginas,
                           f"{ex.documento.confianca:.2f}", ex.documento.revisar, len(alertas), ex.erro or ""])
        (args.saida / f"{arq.stem}.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

        for r in rotulos:
            esperado = gabarito.get((arq.name, r.pagina))
            if esperado:
                total += 1
                acertos_tipo += r.tipo.value == esperado[0]
                acertos_quebra += r.inicia_documento == esperado[1]
                if r.tipo.value != esperado[0]:
                    confusao[(esperado[0], r.tipo.value)] += 1
        print(f"{arq.name}: {len(paginas)} págs -> {len(docs)} documentos")

    with (args.saida / "resumo.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "doc", "tipo", "paginas", "confianca", "revisar", "alertas", "erro"])
        w.writerows(resumo)

    print(f"\nTokens: entrada={ia.uso.tokens_entrada:,} saída={ia.uso.tokens_saida:,}")
    if total:
        print(f"Acerto de tipo por página:   {acertos_tipo / total:.1%} ({acertos_tipo}/{total})")
        print(f"Acerto de quebra de documento: {acertos_quebra / total:.1%}")
        for (esp, prev), n in confusao.most_common(10):
            print(f"  {esp} classificado como {prev}: {n}x")


if __name__ == "__main__":
    asyncio.run(main())
