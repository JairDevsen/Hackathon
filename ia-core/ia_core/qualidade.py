"""Tela 'Qualidade da IA': roda lotes fictícios com gabarito e mede separação, classificação e extração."""
import os
import tempfile
import time
import zipfile
import json
from collections import Counter, defaultdict

from . import agrupar, fatiar


def executar(provider) -> dict:
    from tools.gerador_docs import gerador

    resultados = []
    for nome, fn in (("Lote RH misto (11 págs)", gerador.lote_rh_misto), ("Lote grande (60 págs)", lambda: gerador.lote_grande(60))):
        pdf, gabarito = fn()
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "lote.pdf")
            open(src, "wb").write(pdf)
            z = os.path.join(d, "o.zip")
            fatiar.fatiar(src, "lote.pdf", z)
            zf = zipfile.ZipFile(z)
            man = json.loads(zf.read("manifest.json"))["paginas"]
            t0 = time.time()
            analises, anterior = {}, None
            for p in man:
                a = dict(provider.analisar(zf.read(f"pages/{p['numero']:04d}.png"), p["numero"], anterior, p["texto_embutido"], "MISTO"))
                analises[p["numero"]] = a
                anterior = a
            docs = agrupar.agrupar(analises)
            dur = time.time() - t0
        real = {tuple(d["paginas"]): d for d in docs}
        esp = {tuple(g["paginas"]): g for g in gabarito}
        sep_ok = sum(1 for k in esp if k in real)
        cls_ok, ext_ok, ext_tot = 0, 0, 0
        conf = defaultdict(Counter)
        por_tipo = defaultdict(lambda: [0, 0])
        for k, g in esp.items():
            r = real.get(k)
            pred = r["tipo"] if r else "(não separado)"
            conf[g["tipo"]][pred] += 1
            por_tipo[g["tipo"]][1] += 1
            if r and r["tipo"] == g["tipo"]:
                cls_ok += 1
                por_tipo[g["tipo"]][0] += 1
            if "cpf" in g:
                ext_tot += 1
                if r and (r["campos"].get("cpf") or "").replace(".", "").replace("-", "") == g["cpf"]:
                    ext_ok += 1
        n = max(len(esp), 1)
        resultados.append({"lote": nome, "paginas": len(man), "documentos_esperados": len(esp), "documentos_encontrados": len(real), "segundos": round(dur, 2),
                           "acuracia_separacao": round(sep_ok / n, 3), "acuracia_classificacao": round(cls_ok / n, 3), "acuracia_extracao_cpf": round(ext_ok / max(ext_tot, 1), 3),
                           "por_tipo": {t: {"acertos": v[0], "total": v[1]} for t, v in por_tipo.items()}, "matriz_confusao": {t: dict(c) for t, c in conf.items()}})
    return {"provider": provider.nome, "resultados": resultados}
