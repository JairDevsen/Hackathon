"""Teste ponta a ponta do IA Core, sem rede: fatia o lote fictício, analisa, agrupa e confere o gabarito."""
import json, os, tempfile, zipfile

from ia_core import agrupar, catalogo, fatiar, render
from ia_core.providers import LocalProvider
from tools.gerador_docs import gerador


def _rodar(pdf: bytes):
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "l.pdf"); open(src, "wb").write(pdf)
        z = os.path.join(d, "o.zip"); fatiar.fatiar(src, "l.pdf", z)
        zf = zipfile.ZipFile(z)
        man = json.loads(zf.read("manifest.json"))["paginas"]
        prov, analises, ant = LocalProvider(), {}, None
        for p in man:
            a = dict(prov.analisar(zf.read(f"pages/{p['numero']:04d}.png"), p["numero"], ant, p["texto_embutido"], "MISTO"))
            analises[p["numero"]] = a; ant = a
        return man, zf.namelist(), agrupar.agrupar(analises)


def test_catalogo_tem_32_tipos():
    assert len(catalogo.CODIGOS) == 32


def test_lote_misto_separa_e_classifica():
    pdf, gab = gerador.lote_rh_misto()
    man, nomes, docs = _rodar(pdf)
    assert len(man) == 11
    assert "thumbs/0001.webp" in nomes
    real = {tuple(d["paginas"]): d for d in docs}
    for g in gab:
        d = real.get(tuple(g["paginas"]))
        assert d is not None, f"documento {g} não foi separado: {list(real)}"
        assert d["tipo"] == g["tipo"], (g, d["tipo"])
        if "cpf" in g:
            assert d["campos"]["cpf"] == g["cpf"]
    assert (2, 3) in real  # frente e verso do cartão de ponto agrupados
    assert 5 not in [p for d in docs for p in d["paginas"]]  # página em branco descartada


def test_nao_conformidades_e_revisao():
    pdf, _ = gerador.lote_rh_misto()
    _, _, docs = _rodar(pdf)
    por = {tuple(d["paginas"]): d for d in docs}
    ponto = {n["codigo"] for n in por[(2, 3)]["nao_conformidades"]}
    assert {"JORNADA_ACIMA_10H", "INTERVALO_INFERIOR_1H"} <= ponto
    assert "FGTS_DIVERGENTE" in {n["codigo"] for n in por[(7,)]["nao_conformidades"]}
    assert "CERTIDAO_VENCIDA" in {n["codigo"] for n in por[(9,)]["nao_conformidades"]}
    assert por[(8,)]["confianca"] < 0.75  # AR rasurado vai para revisão


def test_anonimizacao_irreversivel():
    import fitz
    pdf, _ = gerador.lote_rh_misto()
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "l.pdf"); open(src, "wb").write(pdf)
        z = os.path.join(d, "o.zip"); fatiar.fatiar(src, "l.pdf", z)
        zf = zipfile.ZipFile(z)
        p = json.loads(zf.read("manifest.json"))["paginas"][0]
        assert p["caixas"], "deveria detectar CPF/nome na página 1"
        out = render.gerar_pdf("anonimizado", "x", [{"imagem": zf.read("pages/0001.png"), "texto": p["texto_embutido"], "palavras": p["palavras"], "caixas": p["caixas"]}])
    doc = fitz.open(stream=out, filetype="pdf")
    assert "458.712.903-88" not in doc[0].get_text() and "458712903" not in doc[0].get_text()  # sem camada de texto
    pes = render.gerar_pdf("pesquisavel", "x", [{"imagem": zf.read("pages/0001.png"), "texto": p["texto_embutido"], "palavras": p["palavras"], "caixas": []}])
    txt = fitz.open(stream=pes, filetype="pdf")[0].get_text()
    assert "458.712.903-88" in txt  # camada de texto invisível permite buscar (Ctrl+F) no próprio PDF


def test_extrai_empresa_e_cnpj_dinamicamente():
    from ia_core.extracao import cnpj_valido, extrair_campos
    c = extrair_campos("CONTRATADA: ACME SERVICOS LTDA\nCNPJ: 11.222.333/0001-81\nCOLABORADOR: JOSE DA SILVA\nCPF: 529.982.247-25")
    assert c["empresa_nome"] == "ACME SERVICOS LTDA" and c["empresa_cnpj"] == "11222333000181"
    assert c["cpf"] == "52998224725" and c["nome"] == "Jose Da Silva"
    assert cnpj_valido("11.222.333/0001-81") and not cnpj_valido("11.222.333/0001-82")


def test_checklist_e_telemetria_no_lote_misto():
    pdf, _ = gerador.lote_rh_misto()
    _, _, docs = _rodar(pdf)
    por = {tuple(d["paginas"]): d for d in docs}
    aso = {i["regra"]: i["status"] for i in por[(4,)]["checklist"]}
    assert aso["NR-07 · Parecer médico"] == "OK" and aso["NR-07 · Periodicidade (12 meses)"] == "OK"
    epi = {i["regra"]: i["status"] for i in por[(6,)]["checklist"]}
    assert epi["NR-06 · Certificado de Aprovação (CA)"] == "OK" and epi["Assinatura identificada"] == "OK"
    crf = {i["regra"]: i["status"] for i in por[(9,)]["checklist"]}
    assert crf["Validade vigente"] == "FALHA"          # certidão vencida
    ar = {i["regra"]: i["status"] for i in por[(8,)]["checklist"]}
    assert ar["Legibilidade da leitura"] == "REVISAO_HUMANA"
    f = por[(2, 3)]["finops"]
    assert f["camada_roteamento"].startswith("Camada 1") and f["tokens_consumidos"] == 0 and f["economia_estimada_pct"] == 100.0
    assert por[(9,)]["campos"]["empresa_cnpj"] == "14589201000180"


def test_reducao_para_1024_webp():
    import io
    from PIL import Image
    from ia_core.providers import _reduzir
    big = io.BytesIO(); Image.new("RGB", (2480, 3508), "white").save(big, "PNG")
    out, mime = _reduzir(big.getvalue(), 1024)
    im = Image.open(io.BytesIO(out))
    assert mime == "image/webp" and im.format == "WEBP" and max(im.size) == 1024
    assert abs(im.size[0] / im.size[1] - 2480 / 3508) < 0.01   # proporção preservada
    assert len(out) < len(big.getvalue())


def _pipeline_imagem(png: bytes):
    """Fatia uma IMAGEM (sem camada de texto), analisa e agrupa — como um scan/foto enviado pelo RH."""
    import io, json, os, tempfile, zipfile
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "foto.png"); open(src, "wb").write(png)
        z = os.path.join(d, "o.zip"); fatiar.fatiar(src, "foto.png", z)
        zf = zipfile.ZipFile(z)
        man = json.loads(zf.read("manifest.json"))["paginas"]
        a = dict(LocalProvider().analisar(zf.read("pages/0001.png"), 1, None, man[0]["texto_embutido"], "MISTO"))
        return a, agrupar.agrupar({1: a})


def _pagina_png(n: int) -> bytes:
    import io, zipfile
    pdf, _ = gerador.lote_rh_misto()
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "l.pdf"); open(src, "wb").write(pdf)
        z = os.path.join(d, "o.zip"); fatiar.fatiar(src, "l.pdf", z)
        return zipfile.ZipFile(z).read(f"pages/{n:04d}.png")


def test_imagem_borrada_nao_e_confundida_com_pagina_em_branco():
    import io
    from PIL import Image, ImageFilter
    blur = io.BytesIO(); Image.open(io.BytesIO(_pagina_png(1))).filter(ImageFilter.GaussianBlur(6)).save(blur, "PNG")
    a, docs = _pipeline_imagem(blur.getvalue())
    assert a["borrada"] and a["pagina_ilegivel"] and not a["pagina_em_branco"]      # NÃO pode ser descartada como branco
    assert len(docs) == 1                                                            # vira documento para a revisão humana
    d = docs[0]
    assert "IMAGEM_BORRADA" in d["motivos_revisao"]
    assert any(x["codigo"] == "IMAGEM_BORRADA" and x["severidade"] == "erro" and "mais nítida" in x["mensagem"] for x in d["alertas"])
    assert {i["regra"]: i["status"] for i in d["checklist"]}["Legibilidade da leitura"] == "FALHA"
    assert d["finops"]["tokens_consumidos"] == 0                                    # sem gastar tokens com imagem ilegível


def test_pagina_branca_de_imagem_continua_descartada():
    import io
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (1240, 1754), "white").save(b, "PNG")
    a, docs = _pipeline_imagem(b.getvalue())
    assert a["pagina_em_branco"] and not a.get("borrada") and docs == []


def test_imagem_nitida_sem_ocr_vai_para_revisao_e_nao_some():
    # sem Tesseract não há texto: a página tem conteúdo, então NUNCA pode ser tratada como branca
    from ia_core.providers import _ocr_se_disponivel
    png = _pagina_png(1)
    if _ocr_se_disponivel(png).strip():
        return  # ambiente com Tesseract: o texto é lido normalmente (coberto pelo pipeline normal)
    a, docs = _pipeline_imagem(png)
    assert a["pagina_ilegivel"] and not a["pagina_em_branco"] and not a.get("borrada") and len(docs) == 1


def test_extrai_horas_extras_do_ponto_e_pagamento_do_holerite():
    from ia_core.extracao import extrair_campos
    ponto = extrair_campos("CARTAO DE PONTO\nTOTAL DE HORAS EXTRAS: 44:00\nCOMPETENCIA: 10/2026")
    assert ponto["horas_extras"] == "44:00" and ponto["pagamento_horas_extras"] is None
    hol = extrair_campos("HOLERITE\nHORAS EXTRAS 50%: R$ 1.250,00\nLIQUIDO A RECEBER: R$ 2.050,30")
    assert hol["pagamento_horas_extras"] == "1.250,00" and hol["horas_extras"] is None
    assert extrair_campos("HOLERITE sem extras")["pagamento_horas_extras"] is None


def test_formularios_manuais_por_tipo():
    from ia_core.schemas import schema_do_tipo
    assert "certificado_aprovacao" in schema_do_tipo("FICHA_EPI")["properties"]
    assert "data_desligamento" in schema_do_tipo("TRCT")["properties"]
    assert "cid" in schema_do_tipo("ATESTADO_MEDICO")["properties"]
    assert "cpf" in schema_do_tipo("OUTRO")["properties"]  # tipos sem schema próprio caem no base
