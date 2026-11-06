"""Gera os assets da demonstração pública da landing: páginas (WebP) do lote fictício + resultado do processamento (JSON).
Uso: python -m tools.gerador_docs.exportar_demo ../frontend/public/demo"""
import io, json, os, sys, tempfile, zipfile
from PIL import Image

from ia_core import agrupar, catalogo, fatiar
from ia_core.providers import LocalProvider
from tools.gerador_docs import gerador

LIMIAR = 0.75


def main(dest: str):
    os.makedirs(dest, exist_ok=True)
    pdf, _ = gerador.lote_rh_misto()
    nomes = {v[1].replace(".", "").replace("-", ""): v[0].title() for v in gerador.FUNCIONARIOS.values()}
    cadastrados = {v[1].replace(".", "").replace("-", "") for k, v in gerador.FUNCIONARIOS.items() if k != "desconhecido"}
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "l.pdf"); open(src, "wb").write(pdf)
        z = os.path.join(d, "o.zip"); fatiar.fatiar(src, "l.pdf", z)
        zf = zipfile.ZipFile(z)
        man = json.loads(zf.read("manifest.json"))["paginas"]
        prov, an, ant = LocalProvider(), {}, None
        for p in man:
            png = zf.read(f"pages/{p['numero']:04d}.png")
            im = Image.open(io.BytesIO(png)).convert("RGB"); im.thumbnail((640, 900)); im.save(os.path.join(dest, f"p{p['numero']}.webp"), "WEBP", quality=72)
            a = dict(prov.analisar(png, p["numero"], ant, p["texto_embutido"], "MISTO")); an[p["numero"]] = a; ant = a
    docs = []
    for i, dc in enumerate(agrupar.agrupar(an)):
        cpf = dc["campos"].get("cpf") or ""
        motivos = []
        if dc["confianca"] < LIMIAR: motivos.append("Baixa confiança")
        if cpf and cpf not in cadastrados: motivos.append("Sem vínculo")
        docs.append({"id": i + 1, "tipo": catalogo.TIPOS[dc["tipo"]]["nome"], "paginas": dc["paginas"], "funcionario": (nomes.get(cpf) if cpf in cadastrados else None) if cpf else "Empresa",
                     "cpf_mascarado": f"***.{cpf[3:6]}.{cpf[6:9]}-**" if len(cpf) == 11 else None, "confianca": dc["confianca"], "status": "Aguardando revisão" if motivos else "Auto-aprovado",
                     "motivos": motivos, "alertas": [a["mensagem"] for a in dc["alertas"] if a["severidade"] != "info"], "campos": {k: v for k, v in dc["campos"].items() if v and k != "cpf"}})
    json.dump({"arquivo": "Lote_RH_Misto_11pags.pdf (fictício)", "paginas": len(man), "documentos": docs}, open(os.path.join(dest, "result.json"), "w"), ensure_ascii=False, indent=1)
    print(len(man), "páginas;", len(docs), "documentos ->", dest)


if __name__ == "__main__":
    main(sys.argv[1])
