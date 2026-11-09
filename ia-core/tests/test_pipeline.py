"""Teste ponta a ponta do IA Core, sem rede: fatia o lote fictício, analisa, agrupa e confere o gabarito."""
import io, json, os, tempfile, zipfile

import pytest

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


def test_catalogo_tem_44_tipos():
    assert len(catalogo.CODIGOS) == 58


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


def test_cnpj_da_contratada_e_nao_da_contratante():
    """Um contrato cita duas empresas: o fornecedor é a CONTRATADA, mesmo quando a contratante vem primeiro."""
    from ia_core.extracao import extrair_campos
    t = ("CONTRATO DE PRESTACAO DE SERVICO\nCONTRATANTE: AGROTECH GARANHUNS LTDA, CNPJ 14.589.201/0001-80\n"
         "CONTRATADA: BRILHO LIMPEZA LTDA, CNPJ 11.222.333/0001-81\n")
    assert extrair_campos(t)["empresa_cnpj"] == "11222333000181"
    # sem rótulo de contratada, ignora o CNPJ rotulado como contratante
    t2 = "CONTRATANTE: AGROTECH LTDA CNPJ 14.589.201/0001-80\nEmpresa prestadora 11.222.333/0001-81"
    assert extrair_campos(t2)["empresa_cnpj"] == "11222333000181"
    # documento comum: primeiro CNPJ válido
    assert extrair_campos("CRF FGTS CNPJ: 14.589.201/0001-80")["empresa_cnpj"] == "14589201000180"


def test_tipos_de_risco_para_a_contratante():
    from ia_core import catalogo, schemas
    casos = {
        "APOLICE_SEGURO": "APOLICE DE SEGURO SEGURADORA PREMIO DO SEGURO RESPONSABILIDADE CIVIL",
        "AUTO_INFRACAO": "AUTO DE INFRACAO AUDITOR FISCAL DO TRABALHO FISCALIZACAO DO TRABALHO",
        "PROCESSO_JUDICIAL": "RECLAMACAO TRABALHISTA VARA DO TRABALHO RECLAMANTE RECLAMADA CITACAO",
        "RELATORIO_AUDITORIA": "RELATORIO DE AUDITORIA ACHADOS DA AUDITORIA NAO CONFORMIDADES IDENTIFICADAS",
    }
    for tipo, texto in casos.items():
        assert catalogo.classificar(texto)[0] == tipo, tipo
        assert "empresa_cnpj" in schemas.schema_do_tipo(tipo)["properties"], tipo  # o formulário manual permite corrigir o fornecedor


# ---------- provedores de IA (cliente simulado: sem rede e sem chave) ----------

def _png_branco():
    import io
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (300, 300), "white").save(b, "PNG"); return b.getvalue()


def _png_pagina():
    """Página com conteúdo (linhas escuras, como texto ilegível): não é em branco nem borrada, e o OCR não acha palavra de documento."""
    import io
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (800, 1000), "white"); d = ImageDraw.Draw(im)
    for y in range(60, 940, 28):
        for x in range(60, 740, 14):
            d.rectangle([x, y, x + 8, y + 12], fill="black")
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


class _FakeOpenAI:
    """Imita client.chat.completions.create e guarda os argumentos recebidos."""
    def __init__(self, respostas, falhar_em=()):
        self.chamadas, self._resp, self._falhar = [], list(respostas), set(falhar_em)
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kw):
        import json
        self.chamadas.append(kw)
        if kw["model"] in self._falhar:
            raise RuntimeError("404 model not found")
        corpo = self._resp.pop(0) if self._resp else {"tipo": "OUTRO", "inicia_documento": True, "confianca": 0.9}
        msg = type("M", (), {"content": json.dumps(corpo)})()
        return type("R", (), {"choices": [type("Ch", (), {"message": msg})()], "usage": type("U", (), {"total_tokens": 1234})()})()


def _provider_openai(fake):
    from ia_core.providers import OpenAIProvider
    p = OpenAIProvider("sk-teste"); p.client = fake; return p


def test_escolha_do_provedor(monkeypatch):
    import pytest
    from ia_core.providers import obter_provider
    for k in ("IA_PROVIDER", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert obter_provider().nome == "local-heuristico"
    monkeypatch.setenv("GEMINI_API_KEY", "g-teste")
    assert obter_provider().nome.startswith("gemini:")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")
    assert obter_provider().nome.startswith("openai:"), "com as duas chaves, a OpenAI tem prioridade"
    monkeypatch.setenv("IA_PROVIDER", "gemini")
    assert obter_provider().nome.startswith("gemini:"), "IA_PROVIDER explícito manda"
    monkeypatch.setenv("IA_PROVIDER", "local")
    assert obter_provider().nome == "local-heuristico"
    monkeypatch.delenv("OPENAI_API_KEY"); monkeypatch.setenv("IA_PROVIDER", "openai")
    with pytest.raises(RuntimeError):
        obter_provider()  # pedir a OpenAI sem chave falha na inicialização, em vez de cair em silêncio no motor local
    monkeypatch.setenv("IA_PROVIDER", "outra")
    with pytest.raises(RuntimeError):
        obter_provider()


def test_openai_visao_monta_o_pedido_e_normaliza():
    resp = {"tipo": "HOLERITE", "inicia_documento": True, "confianca": 0.93, "titulo": "Holerite", "cpf": "74602318860", "empresa_cnpj": "11222333000181",
            "extras": [{"chave": "salario_base", "valor": "2000,00"}]}
    fake = _FakeOpenAI([resp]); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    kw = fake.chamadas[0]
    assert kw["model"] == p.model and kw["response_format"] == {"type": "json_object"} and "temperature" not in kw
    partes = kw["messages"][0]["content"]
    assert partes[0]["type"] == "text" and "JSON Schema" in partes[0]["text"] and "HOLERITE" in partes[0]["text"]
    assert partes[1]["type"] == "image_url" and partes[1]["image_url"]["url"].startswith("data:image/webp;base64,")
    assert pg["tipo"] == "HOLERITE" and pg["confianca"] == 0.93 and pg["tokens"] == 1234 and pg["camada"].startswith("Camada 3")
    assert pg["campos"]["cpf"] == "74602318860" and pg["campos"]["salario_base"] == "2000,00"


def test_openai_texto_usa_modelo_leve_e_resposta_invalida_sobe_para_a_visao():
    fake = _FakeOpenAI([{"tipo": "NAO_EXISTE", "inicia_documento": True, "confianca": "alta"}]); p = _provider_openai(fake)
    pg = p.analisar(_png_branco(), 1, None, "texto livre sem pista nenhuma de documento " * 4, "MISTO")
    assert fake.chamadas[0]["model"] == p.lite and isinstance(fake.chamadas[0]["messages"][0]["content"], str)
    assert "NÃO o transcreva" in fake.chamadas[0]["messages"][0]["content"], "a Camada 2 não pede transcrição: o texto já existe"
    # resposta do modelo de texto sem confiança válida não é aceita: a página sobe para a visão (2ª chamada, com imagem)
    assert fake.chamadas[1]["model"] == p.model and isinstance(fake.chamadas[1]["messages"][0]["content"], list)
    assert pg["camada"].startswith("Camada 3") and pg["tipo"] == "OUTRO"


def test_pagina_em_branco_nao_chama_modelo():
    fake = _FakeOpenAI([]); p = _provider_openai(fake)
    pg = p.analisar(_png_branco(), 1, None, "", "MISTO")
    assert not fake.chamadas and pg["pagina_em_branco"] and pg["tokens"] == 0


def _png_folha(base=252, ruido=0, sombra=False, furos=False, numero=False, aviso=None):
    """Folha 'quase em branco' como sai de um scanner: papel levemente cinza, ruído, sombra de borda, furos de perfuração, só o número da página."""
    import io, random
    from PIL import Image, ImageDraw, ImageFont
    rnd = random.Random(7)
    im = Image.new("L", (1240, 1754), base); d = ImageDraw.Draw(im)
    for _ in range(ruido):
        d.point((rnd.randrange(1240), rnd.randrange(1754)), fill=max(base - rnd.randint(5, 25), 0))
    if sombra:
        d.rectangle((0, 0, 40, 1754), fill=120)
    if furos:
        for y in (300, 900, 1400):
            d.ellipse((30, y, 70, y + 40), fill=60)
    if numero:
        d.text((620, 1690), "3", fill=0, font=ImageFont.load_default(size=28))
    if aviso:
        d.text((200, 870), aviso, fill=0, font=ImageFont.load_default(size=30))
    b = io.BytesIO(); im.convert("RGB").save(b, "PNG"); return b.getvalue()


@pytest.mark.parametrize("folha", [
    dict(), dict(base=238, ruido=150000), dict(sombra=True), dict(furos=True), dict(numero=True), dict(ruido=40),
    dict(aviso="Esta pagina foi intencionalmente deixada em branco"),
])
def test_folha_vazia_e_descartada_e_nunca_vira_outro(folha):
    from ia_core.providers import LocalProvider
    pg = LocalProvider().analisar(_png_folha(**folha), 1, None, "", "MISTO")
    assert pg["pagina_em_branco"] and not pg["pagina_ilegivel"] and not pg.get("borrada")
    assert agrupar.agrupar({1: pg}) == []  # nenhum documento "OUTRO" sai de uma folha vazia


@pytest.mark.parametrize("texto_nativo", ["3", "- 2 -", "Página intencionalmente deixada em branco"])
def test_texto_nativo_so_de_numero_ou_aviso_nao_vira_documento(texto_nativo):
    from ia_core.providers import LocalProvider
    pg = LocalProvider().analisar(_png_folha(sombra=True), 4, None, texto_nativo, "MISTO")
    assert pg["pagina_em_branco"] and agrupar.agrupar({4: pg}) == []


def test_folha_vazia_no_meio_separa_documentos_e_some():
    cnh = "CARTEIRA NACIONAL DE HABILITACAO CPF 529.982.247-25 VALIDADE 10/11/2030 CNH"
    from ia_core.providers import LocalProvider
    lp = LocalProvider()
    a = {1: lp.analisar(_png_pagina(), 1, None, cnh, "MISTO"), 2: lp.analisar(_png_folha(furos=True), 2, None, "", "MISTO"),
         3: lp.analisar(_png_pagina(), 3, None, cnh, "MISTO")}
    docs = agrupar.agrupar(a)
    assert [d["paginas"] for d in docs] == [[1], [3]] and all(d["tipo"] != "OUTRO" for d in docs)


def test_pagina_com_texto_curto_e_tinta_nao_e_descartada_como_branca():
    """Manuscrito/foto que o OCR leu mal: tem tinta, então NÃO é em branco (vai à visão), mesmo que o OCR devolva quase nada."""
    from ia_core.providers import leitura_local
    pronta, texto, nativo = leitura_local(_png_pagina(), "")
    assert not (pronta and pronta["pagina_em_branco"])


def test_agrupar_descarta_aviso_de_branco_mesmo_que_o_provedor_nao_marque():
    pg = dict(tipo="OUTRO", inicia_documento=True, confianca=0.4, texto_ocr="Esta página foi intencionalmente deixada em branco", campos={},
              possui_manuscrito=False, pagina_ilegivel=False, multiplos_documentos_na_imagem=False, pagina_em_branco=False, titulo="Outro", tokens=0)
    assert agrupar.agrupar({1: pg}) == []


def test_openai_modelo_reserva_quando_o_principal_falha():
    fake = _FakeOpenAI([], falhar_em={"gpt-5-mini"}); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert [c["model"] for c in fake.chamadas] == ["gpt-5-mini", "gpt-5"] and pg["camada"].startswith("Camada 3")


def test_diagnostico_lista_cada_modelo_e_o_erro():
    class P(_FakeOpenAI):
        def create(self, **kw):
            if kw["model"] == "gpt-5-nano":
                raise RuntimeError("model_not_found")
            return type("R", (), {"choices": [type("Ch", (), {"message": type("M", (), {"content": "OK"})()})()], "usage": None})()
    r = _provider_openai(P([])).diagnosticar()
    por_modelo = {x["modelo"]: x for x in r}
    assert por_modelo["gpt-5-mini"]["ok"] and not por_modelo["gpt-5-nano"]["ok"] and "model_not_found" in por_modelo["gpt-5-nano"]["erro"]


def _pal(texto: str, y: float):
    """Palavras de uma linha, cada uma numa faixa horizontal própria (como o OCR devolve)."""
    return [[0.05 + i * 0.1, y, 0.05 + i * 0.1 + 0.08, y + 0.02, t] for i, t in enumerate(texto.split())]


def test_tarjas_a_partir_das_palavras_com_posicao():
    from ia_core.anonimizacao import caixas_de_nomes, caixas_de_palavras
    pal = _pal("CPF: 458.712.903-88", 0.10) + _pal("Endereço: Rua das Flores 123 Centro", 0.20) + _pal("Total 10,00", 0.30)
    por_tipo = {c[4]: c for c in caixas_de_palavras(pal)}
    assert set(por_tipo) == {"CPF", "ENDERECO"}
    assert por_tipo["CPF"][:4] == pytest.approx([0.15, 0.10, 0.23, 0.12])          # só a palavra do CPF, não o rótulo
    assert por_tipo["ENDERECO"][0] == pytest.approx(0.15) and por_tipo["ENDERECO"][2] > 0.5   # cobre o endereço inteiro, não o rótulo
    # nome conhecido, sem rótulo, com um erro de OCR; "da" liga as partes e a palavra solta "Maria" não vira tarja
    pal = _pal("Maria Fogaça da Silva Total", 0.40) + _pal("Maria", 0.50)
    caixas = caixas_de_nomes(pal, ["Maria Fogaça da Silva"])
    assert len(caixas) == 1 and caixas[0][:2] == pytest.approx([0.05, 0.40]) and caixas[0][2] == pytest.approx(0.43)
    assert caixas_de_nomes(_pal("Mario Fogaca", 0.1), ["Maria Fogaça"])  # tolera pequenos erros de OCR


def test_copia_anonimizada_de_pagina_escaneada_tem_tarja_ou_recusa(monkeypatch):
    import fitz
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (600, 800), "white").save(buf, "PNG"); png = buf.getvalue()
    pagina = {"imagem": png, "texto": "", "palavras": [], "caixas": []}
    # página só com imagem: lê por OCR (simulado) e tarja o CPF encontrado, em qualquer das passadas
    passadas = [[], _pal("CPF: 458.712.903-88", 0.10), []]
    monkeypatch.setattr(render, "_ocr", lambda _png: passadas)
    pdf = render.gerar_pdf("anonimizado", "x", [pagina])
    pix = fitz.open(stream=pdf, filetype="pdf")[0].get_pixmap(dpi=150)
    x, y = int(pix.width * 0.19), int(pix.height * 0.11)
    assert pix.pixel(x, y)[:3] == (0, 0, 0) and pix.pixel(int(pix.width * 0.5), int(pix.height * 0.5))[:3] == (255, 255, 255)
    assert fitz.open(stream=pdf, filetype="pdf")[0].get_text().strip() == ""   # sem camada de texto
    # sem OCR disponível: recusa com mensagem clara, em vez de entregar um documento "anonimizado" sem tarja
    def sem_tesseract(*a, **k):
        raise FileNotFoundError("tesseract")
    monkeypatch.undo()
    monkeypatch.setattr(render.subprocess, "run", sem_tesseract)
    with pytest.raises(render.RenderErro, match="OCR local indisponível"):
        render.gerar_pdf("anonimizado", "x", [pagina])


def _pg(tipo, texto, conf=0.9, inicia=True):
    return {"tipo": tipo, "texto_ocr": texto, "confianca": conf, "inicia_documento": inicia, "campos": {}}


def test_contrato_nao_e_separado_quando_a_pagina_1_veio_ilegivel_ou_com_outro_tipo():
    # página 1 lida como OUTRO (rotacionada/ruim), páginas 2 e 3 trazem o marcador "Página X/3" mas com tipo lido diferente
    docs = agrupar.agrupar({
        1: _pg("OUTRO", "texto sem sentido x7 q", 0.4),
        2: _pg("CONTRATO_TRABALHO", "Página 2/3 CLÁUSULA 7 o EMPREGADO se compromete", 0.7),
        3: _pg("DECLARACAO_VT", "Página 3/3 CLÁUSULA 10 Aplicam-se as disposições", 0.6),
        4: _pg("CONTRATO_TRABALHO", "Página 1/3 CONTRATO INDIVIDUAL DE TRABALHO cláusula primeira", 0.95),  # outro contrato: abre documento novo
    })
    assert [d["paginas"] for d in docs] == [[1, 2, 3], [4]]
    assert docs[0]["tipo"] == "CONTRATO_TRABALHO"   # o tipo vem da melhor leitura, não da página ilegível


def test_trct_e_termo_de_quitacao_ficam_juntos_em_qualquer_ordem():
    trct = _pg("TRCT", "TERMO DE RESCISÃO DO CONTRATO DE TRABALHO verbas rescisórias CPF 783.015.694-84", 0.95)
    quit_ = _pg("CONTRATO_TRABALHO", "TERMO DE QUITAÇÃO DE RESCISÃO DO CONTRATO DE TRABALHO CPF 783.015.694-84", 0.8)
    assert [d["paginas"] for d in agrupar.agrupar({1: trct, 2: quit_, 3: _pg("HOLERITE", "holerite", 0.9)})] == [[1, 2], [3]]
    assert [d["paginas"] for d in agrupar.agrupar({1: quit_, 2: trct})] == [[1, 2]]                       # termo antes da página principal
    assert [d["paginas"] for d in agrupar.agrupar({1: trct, 2: _pg("ASO", "aso", 0.9), 3: quit_})] == [[1, 3], [2]]   # outra página no meio, mesmo CPF
    outro = _pg("TRCT", "TERMO DE RESCISÃO DO CONTRATO DE TRABALHO CPF 111.444.777-35", 0.95)
    assert [d["paginas"] for d in agrupar.agrupar({1: trct, 2: outro})] == [[1], [2]]                      # dois TRCT seguidos continuam separados


def test_ar_frente_e_verso_pelo_numero_do_objeto_mesmo_longe():
    frente = _pg("AVISO_RECEBIMENTO", "AVISO DE RECEBIMENTO FICT 829 320 540 AR DESTINATÁRIO", 0.9)
    verso = _pg("AVISO_RECEBIMENTO", "FICT 829 320 540 AR DADOS DO RECEBIMENTO CARIMBO", 0.9)
    outro = _pg("AVISO_RECEBIMENTO", "AVISO DE RECEBIMENTO FICT 401 953 344 AR DESTINATÁRIO", 0.9)
    assert [d["paginas"] for d in agrupar.agrupar({1: frente, 2: outro, 3: verso})] == [[1, 3], [2]]
    assert [d["paginas"] for d in agrupar.agrupar({1: frente, 2: outro})] == [[1], [2]]
    # folha com frente e verso na mesma página já está completa: o AR seguinte não é anexado a ela
    completa = _pg("AVISO_RECEBIMENTO", "AVISO DE RECEBIMENTO FICT 111 222 333 AR DADOS DO RECEBIMENTO", 0.9)
    assert [d["paginas"] for d in agrupar.agrupar({1: completa, 2: outro})] == [[1], [2]]


def test_marcadores_de_pagina():
    from ia_core.paginacao import marcador_de_pagina
    assert marcador_de_pagina("CLÁUSULA 1 — Página 2/3") == (2, 3) and marcador_de_pagina("Folha 2/2") == (2, 2)
    assert marcador_de_pagina("(PAG 1/2)") == (1, 2) and marcador_de_pagina("fls. 3 de 5") == (3, 5)
    assert marcador_de_pagina("Folha 3/2") is None and marcador_de_pagina("página 1/1") is None and marcador_de_pagina("data 05/06") is None


def test_pagina_de_cabeca_para_baixo_e_lida_girada():
    from PIL import Image, ImageDraw
    from ia_core import orientacao
    def ocr(png):  # OCR simulado: só "entende" a página quando ela está na orientação certa
        return "CONTRATO DE TRABALHO EMPREGADOR EMPREGADO CLAUSULA PRIMEIRA PERIODO ASSINATURA " if orientacao.Image.open(io.BytesIO(png)).getpixel((5, 5)) == (255, 255, 255) else "esed opeJab ldwa oy yhqd lxqz xxxxxxxxxxxxxxxxxxxxx"
    im = Image.new("RGB", (40, 60), "white"); ImageDraw.Draw(im).rectangle([0, 0, 10, 10], fill=(0, 0, 0)); b = io.BytesIO(); im.save(b, "PNG")
    graus, texto = orientacao.melhor_orientacao(b.getvalue(), ocr)   # o canto preto no topo-esquerdo: a página está rotacionada
    assert graus != 0 and "CONTRATO" in texto
    assert orientacao.melhor_orientacao(orientacao.girar(b.getvalue(), 180), lambda png: "CONTRATO DE TRABALHO EMPREGADOR EMPREGADO CLAUSULA PRIMEIRA PERIODO ")[0] == 0


def test_ars_seguidos_com_numeros_diferentes_nao_se_juntam_mesmo_sem_o_titulo_legivel():
    # o OCR perdeu o título "AVISO DE RECEBIMENTO" da 2ª página (parece só um verso), mas o número do objeto é outro
    ar1 = _pg("AVISO_RECEBIMENTO", "AVISO DE RECEBIMENTO FICT 768 342 779 AR DESTINATÁRIO", 0.98)
    ar2 = _pg("AVISO_RECEBIMENTO", "AVISO DE RECEBI FICT 895 304 592 AR DADOS DO RECEBIMENTO", 0.98)
    assert [d["paginas"] for d in agrupar.agrupar({1: ar1, 2: ar2})] == [[1], [2]]
    # termo anexo antes da página principal, com o número do objeto de outro AR: também não junta
    verso_primeiro = _pg("AVISO_RECEBIMENTO", "FICT 480 258 155 AR DADOS DO RECEBIMENTO", 0.9)
    assert [d["paginas"] for d in agrupar.agrupar({1: verso_primeiro, 2: _pg("AVISO_RECEBIMENTO", "AVISO DE RECEBIMENTO FICT 701 317 286 AR", 0.9)})] == [[1], [2]]


def test_pagina_2_de_2_nao_cola_em_documento_de_outro_tipo_bem_identificado():
    recibo = _pg("RECIBO_BENEFICIOS", "RECIBO DE BENEFÍCIOS vale alimentação", 0.95)
    ponto2 = _pg("CARTAO_PONTO", "FOLHA DE PONTO INDIVIDUAL Folha 2/2", 0.9)
    assert [d["paginas"] for d in agrupar.agrupar({1: recibo, 2: ponto2})] == [[1], [2]]
    from ia_core.paginacao import marcador_de_pagina
    assert marcador_de_pagina("FOLHA DE PONTO INDIVIDUAL | Folha 212") == (2, 2) and marcador_de_pagina("Folha 1/2") == (1, 2)
    assert marcador_de_pagina("Folha 113") == (1, 3)           # leitura plausível
    assert marcador_de_pagina("Folha 312") is None              # 3 de 2: impossível


def test_fatiar_guarda_a_imagem_da_pagina_escaneada_na_orientacao_correta(monkeypatch):
    import fitz
    from PIL import Image, ImageDraw
    from ia_core import orientacao
    # página só de imagem; o canto preto no topo-esquerdo marca "de cabeça para baixo" para o OCR simulado
    def ocr(png):
        topo_esq = Image.open(io.BytesIO(png)).convert("RGB").getpixel((3, 3))
        return "CONTRATO DE TRABALHO EMPREGADOR EMPREGADO CLAUSULA PRIMEIRA PERIODO ASSINATURA " if topo_esq == (255, 255, 255) else "esed opeJab ldwa oy yhqd lxqz xxxxxxxxxxxxxxxxxxxxx"
    monkeypatch.setattr(orientacao, "ocr_texto", ocr)
    im = Image.new("RGB", (300, 400), "white"); ImageDraw.Draw(im).rectangle([0, 0, 20, 20], fill=(0, 0, 0))
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "u.pdf"); buf = io.BytesIO(); im.save(buf, "PNG")
        doc = fitz.open(); pg = doc.new_page(width=300, height=400); pg.insert_image(pg.rect, stream=buf.getvalue()); doc.save(pdf)
        z = os.path.join(d, "o.zip"); fatiar.fatiar(pdf, "u.pdf", z)
        zf = zipfile.ZipFile(z); m = json.loads(zf.read("manifest.json"))["paginas"][0]
        assert m["rotacao_corrigida"] == 180
        assert Image.open(io.BytesIO(zf.read("pages/0001.png"))).convert("RGB").getpixel((3, 3)) == (255, 255, 255)  # imagem guardada já girada
        # página já na posição certa não é mexida
        buf2 = io.BytesIO(); Image.new("RGB", (300, 400), "white").save(buf2, "PNG")
        doc2 = fitz.open(); p2 = doc2.new_page(width=300, height=400); p2.insert_image(p2.rect, stream=buf2.getvalue()); doc2.save(os.path.join(d, "v.pdf"))
        z2 = os.path.join(d, "o2.zip"); fatiar.fatiar(os.path.join(d, "v.pdf"), "v.pdf", z2)
        assert json.loads(zipfile.ZipFile(z2).read("manifest.json"))["paginas"][0]["rotacao_corrigida"] == 0


def test_endpoint_anonimizar_remove_cpf_e_endereco():
    from fastapi.testclient import TestClient
    from ia_core.main import app
    r = TestClient(app).post("/anonimizar", json={"texto": "Nome: MARIA SOUZA LIMA\nCPF 458.712.903-88\nEndereço: Rua das Flores 123"}, headers={"X-IACore-Key": os.environ.get("IA_CORE_API_KEY", "dev-ia-core-key")})
    assert r.status_code == 200, r.text
    t = r.json()["texto_anonimizado"]
    assert "458.712.903-88" not in t and "MARIA SOUZA" not in t and "Rua das Flores" not in t and "***.712.903-**" in t


def test_impressao_do_motor_muda_com_o_provedor_e_o_modelo():
    from ia_core.impressao import impressao_motor
    class P:  # provedor de mentira
        def __init__(self, nome, model="m", fallback="f", lite="l"): self.nome, self.model, self.fallback, self.lite = nome, model, fallback, lite
    a = impressao_motor(P("openai:gpt-5-mini"))
    assert a == impressao_motor(P("openai:gpt-5-mini")), "deve ser estável entre chamadas"
    assert a != impressao_motor(P("openai:gpt-5")), "outro provedor/modelo = outro motor"
    assert a != impressao_motor(P("openai:gpt-5-mini", lite="outro")), "modelo da Camada 2 também conta"
    assert impressao_motor(LocalProvider()) != a
    assert a.startswith("openai:gpt-5-mini|")


def test_analise_leva_a_impressao_do_motor_e_o_health_a_informa():
    from fastapi.testclient import TestClient
    from ia_core import main
    h = TestClient(main.app).get("/health").json()
    assert h["motor"] == main.MOTOR and h["motor"].startswith(main.PROVIDER.nome + "|")


def test_tarja_por_posicao_nome_em_tabela_e_valor_abaixo_do_rotulo():
    from ia_core.anonimizacao import caixas_de_palavras
    def linha(y, *textos, x0=0.05):
        out, x = [], x0
        for t in textos:
            out.append([x, y, x + 0.012 * len(t) + 0.01, y + 0.02, t]); x = out[-1][2] + 0.01
        return out
    # 1) tabela de trabalhadores: CPF + nome + valor na mesma linha; o cabeçalho e o valor não são tarjados
    pal = linha(0.10, "CPF", "Trabalhador", "Remuneração") + linha(0.14, "123.456.789-09", "ARTHUR", "MIGUEL", "RIBEIRO", "3.675,46") + linha(0.18, "987.654.321-00", "ASAFE", "ALMEIDA", "DIAS", "2.673,99")
    cx = caixas_de_palavras(pal)
    nomes = [c for c in cx if c[4] == "NOME"]
    assert len(nomes) == 2 and {round(c[1], 2) for c in nomes} == {0.14, 0.18}
    assert not any(c[1] == 0.10 for c in cx), "o cabeçalho da tabela não é dado pessoal"
    # 2) formulário com o rótulo EM CIMA do campo (nome, endereço e nascimento)
    pal = linha(0.30, "Empregado") + linha(0.325, "ISABELA", "AZEVEDO", "JESUS") \
        + linha(0.40, "Endereço") + linha(0.425, "Rua", "Alves", "Mendonça,", "1985", "Vila", "Betânia") \
        + linha(0.50, "Data", "de", "nascimento") + linha(0.525, "02/08/1982")
    por_tipo = {}
    for c in caixas_de_palavras(pal):
        por_tipo.setdefault(c[4], []).append(c)
    assert "NOME" in por_tipo and abs(por_tipo["NOME"][0][1] - 0.325) < 1e-6 and "ENDERECO" in por_tipo and "NASCIMENTO" in por_tipo
    # 3) palavra solta de formulário não vira nome
    from ia_core.anonimizacao import caixas_por_posicao
    assert not caixas_por_posicao(linha(0.2, "Nome:") + linha(0.23, "Assinatura"))


def test_tarja_propaga_pela_coluna_quando_o_ocr_errou_uma_celula_e_cobre_logradouro_sem_rotulo():
    from ia_core.anonimizacao import anonimizar_texto, caixas_de_palavras
    def linha(y, *textos, x0=0.05):
        out, x = [], x0
        for t in textos:
            out.append([x, y, x + 0.012 * len(t) + 0.01, y + 0.02, t]); x = out[-1][2] + 0.01
        return out
    # 4 linhas de uma lista de trabalhadores; na 3ª o OCR errou o CPF ("709+135.624-16"): nenhuma regex o reconhece
    pal = (linha(0.10, "123.456.789-09", "ARTHUR", "MIGUEL", "RIBEIRO") + linha(0.14, "987.654.321-00", "ASAFE", "ALMEIDA", "DIAS")
           + linha(0.18, "709+135.624-16", "SARAH", "ALMEIDA", "GONCALVES") + linha(0.22, "111.444.777-35", "JULIA", "FOGACA", "BARBOSA"))
    cx = caixas_de_palavras(pal)
    linha3 = [c for c in cx if abs(c[1] - 0.18) < 1e-6]
    assert {c[4] for c in linha3} >= {"CPF", "NOME"}, f"a 3ª linha deve ser tarjada por inteiro (CPF e nome): {linha3}"
    # endereço sem o rótulo "Endereço:", logo abaixo de um CPF
    texto = "Ao Sr. MARIA JULIA\nCPF 458.712.903-88\nRua Vieira Cunha, 1493 - Vila Nova Cachoeirinha\nCEP 55200-000"
    anon, _ = anonimizar_texto(texto)
    assert "Vieira Cunha" not in anon and "[ENDERECO OCULTO]" in anon
    assert any(c[4] == "ENDERECO" for c in caixas_de_palavras(linha(0.3, "Rua", "Vieira", "Cunha,", "1493", "Vila", "Nova")))


# ---------- funil em camadas: roteador, extração sobre OCR e execução paralela ----------

def _cpf_valido_de(base9: str) -> str:
    d = [int(c) for c in base9]
    for n in (9, 10):
        d.append((sum(d[i] * (n + 1 - i) for i in range(n)) * 10) % 11 % 10)
    return "".join(map(str, d))


CPF_OK = _cpf_valido_de("746023188")
HOLERITE_TXT = ("EMPRESA: ALFA SERVICOS LTDA  RECIBO DE PAGAMENTO DE SALARIO  Referente ao Mês: Abril/2026  "
                f"Nome do Funcionário: MARIA DA SILVA  CPF: {CPF_OK[:3]}.{CPF_OK[3:6]}.{CPF_OK[6:9]}-{CPF_OK[9:]}  SALARIO BASE 2.000,00  INSS 160,00  "
                "TOTAL DE DESCONTOS 160,00  VALOR LIQUIDO A RECEBER 1.840,00  DATA 05/05/2026  ASSINATURA DO EMPREGADO  DEPARTAMENTO CARGO FUNCAO ADMISSAO")


def test_competencia_e_cpf_sobre_texto_de_ocr():
    from ia_core.extracao import competencia_do_texto, cpf_do_texto
    assert competencia_do_texto("Referente ao Més: Abril/2026") == "2026-04"
    assert competencia_do_texto("Pagamento de salário 04/2026") == "2026-04"
    assert competencia_do_texto("Competência\n04/2026") == "2026-04"  # valor na linha seguinte ao rótulo
    assert competencia_do_texto("Período:91/04/2026 a 30/04/2026") == "2026-04"  # o OCR errou o dia, o mês continua certo
    assert competencia_do_texto("Período: 01/04/2026 a 30/06/2026") is None  # período de vários meses não é uma competência
    assert competencia_do_texto("Competência: 13/2026") is None
    mascarado = f"{CPF_OK[:3]} {CPF_OK[3:6]} {CPF_OK[6:9]} {CPF_OK[9:]}"
    assert cpf_do_texto("CPF " + mascarado) == CPF_OK  # separadores perdidos pelo OCR
    assert cpf_do_texto("cpf: " + CPF_OK.replace("0", "O")) == CPF_OK  # zero lido como letra O, junto do rótulo
    assert cpf_do_texto("matrícula " + CPF_OK[:10] + "9") is None  # dígito verificador errado não vira CPF


def test_classificador_acha_pista_colada_pelo_ocr():
    from ia_core.catalogo import classificar
    assert classificar("Recibode pagamento desalário  LIQUIDO A RECEBER")[0] == "HOLERITE"
    assert classificar("ESPELHO DE PONTO Período 01/04/2026")[0] == "CARTAO_PONTO"


def test_roteador_decide_a_camada_mais_barata_que_resolve():
    from ia_core.providers import LocalProvider, TIPOS_VISAO
    from ia_core.roteador import campos_faltando, decidir
    loc = dict(LocalProvider().analisar(b"", 1, None, HOLERITE_TXT, "MISTO"))
    assert loc["tipo"] == "HOLERITE" and loc["campos"]["cpf"] == CPF_OK and loc["campos"]["competencia"] == "2026-04"
    assert decidir(loc, HOLERITE_TXT, False, TIPOS_VISAO).camada == 1
    # sem CPF: no OCR a imagem pode mostrá-lo (visão); no texto nativo o CPF simplesmente não existe (modelo de texto)
    sem_cpf = dict(loc, campos={**loc["campos"], "cpf": None})
    assert decidir(sem_cpf, HOLERITE_TXT, False, TIPOS_VISAO).camada == 3
    assert decidir(sem_cpf, HOLERITE_TXT, True, TIPOS_VISAO).camada == 2
    # sem competência num documento mensal: o modelo de texto lê "mês de referência" escrito de outro jeito
    assert decidir(dict(loc, campos={**loc["campos"], "competencia": None}), HOLERITE_TXT, False, TIPOS_VISAO).camada == 2
    # continuação de documento não é cobrada pelo cabeçalho
    assert campos_faltando("HOLERITE", {}, inicia_documento=False) == []
    # documento da empresa não precisa de CPF; manuscrito/formulário vai direto à visão; OCR ruidoso também
    assert campos_faltando("CRF_FGTS", {}, True) == []
    assert decidir(dict(loc, tipo="AVISO_RECEBIMENTO"), HOLERITE_TXT, False, TIPOS_VISAO).camada == 3
    assert decidir(dict(loc, confianca=0.5), "x y z " * 5, False, TIPOS_VISAO).camada == 3
    assert decidir(dict(loc, confianca=0.5), HOLERITE_TXT, False, TIPOS_VISAO).camada == 2


def test_escaneado_com_ocr_bom_fecha_na_camada_1_sem_chamar_modelo(monkeypatch):
    import ia_core.providers as pv
    fake = _FakeOpenAI([]); p = _provider_openai(fake)
    monkeypatch.setattr(pv, "_ocr_se_disponivel", lambda img: HOLERITE_TXT)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert not fake.chamadas and pg["camada"].startswith("Camada 1: OCR") and pg["tokens"] == 0
    assert pg["tipo"] == "HOLERITE" and pg["campos"]["cpf"] == CPF_OK and pg["campos"]["competencia"] == "2026-04"


def test_camada_2_nao_transcreve_e_reaproveita_o_texto_e_o_cpf_valido(monkeypatch):
    import ia_core.providers as pv
    texto = HOLERITE_TXT.replace("RECIBO DE PAGAMENTO", "DEMONSTRATIVO").replace("LIQUIDO A RECEBER", "A PAGAR")  # tipo incerto → modelo de texto
    monkeypatch.setattr(pv, "_ocr_se_disponivel", lambda img: texto)
    fake = _FakeOpenAI([{"tipo": "HOLERITE", "inicia_documento": True, "confianca": 0.9, "cpf": "11111111111", "nome": "Maria"}]); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert len(fake.chamadas) == 1 and fake.chamadas[0]["model"] == p.lite and "NÃO o transcreva" in fake.chamadas[0]["messages"][0]["content"]
    assert pg["camada"].startswith("Camada 2") and pg["texto_ocr"] == texto.strip()
    assert pg["campos"]["cpf"] == CPF_OK, "o CPF com dígito verificador válido lido pelas regras vence o CPF inválido do modelo"


def test_camada_2_com_baixa_confianca_sobe_para_a_visao_e_soma_os_tokens(monkeypatch):
    import ia_core.providers as pv
    texto = HOLERITE_TXT.replace("RECIBO DE PAGAMENTO", "DEMONSTRATIVO").replace("LIQUIDO A RECEBER", "A PAGAR")
    monkeypatch.setattr(pv, "_ocr_se_disponivel", lambda img: texto)
    fake = _FakeOpenAI([{"tipo": "OUTRO", "inicia_documento": True, "confianca": 0.4}, {"tipo": "HOLERITE", "inicia_documento": True, "confianca": 0.9, "cpf": CPF_OK}]); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert [c["model"] for c in fake.chamadas] == [p.lite, p.model] and pg["camada"].startswith("Camada 3") and pg["tokens"] == 2468


def test_processar_em_paralelo_envia_os_callbacks_em_ordem_e_para_na_falha(monkeypatch):
    import threading, time
    from ia_core import main
    from ia_core.providers import Pagina, Pedido

    class Prov:
        nome = "teste"
        lento = False

        def preparar(self, img, numero, anterior, texto, tipo_lote):
            if numero == 2:  # a Camada 1 de uma página não espera as anteriores no modelo
                return Pagina(tipo="HOLERITE", inicia_documento=True, confianca=0.95, texto_ocr="", campos={}, camada="Camada 1: x", tokens=0)
            return Pedido(3, b"x", "", False, None, "", "", tipo_local="OUTRO")

        def executar(self, pedido):
            time.sleep(0.2 if pedido is not None and self.lento else 0)
            return Pagina(tipo="CNH", inicia_documento=True, confianca=0.9, texto_ocr="", campos={}, camada="Camada 3: y", tokens=10)

    def rodar(prov, n=6, falha_em=None):
        eventos = []
        monkeypatch.setattr(main, "PROVIDER", prov)
        monkeypatch.setattr(main, "_baixar", lambda url: b"img" + url.encode())
        monkeypatch.setattr(main.callback, "enviar", lambda cb, corpo, chave: eventos.append(corpo))
        job = main.JobIn(batch_id="b", versao=1, callback_url="http://cb", paginas=[main.PaginaIn(numero=i, image_url=str(i)) for i in range(1, n + 1)], simular_falha_na_pagina=falha_em or 0)
        main._processar(job)
        return eventos

    class Lento(Prov):
        lento = True
    ev = rodar(Lento())
    assert [e["numero"] for e in ev if e["evento"] == "pagina"] == [1, 2, 3, 4, 5, 6], "callbacks em ordem de página, mesmo com o modelo respondendo fora de ordem"
    assert ev[-1]["evento"] == "concluido" and all(e["analise"]["sha256"] and e["analise"]["motor"] for e in ev if e["evento"] == "pagina")

    class Quebra(Prov):
        lento = False

        def executar(self, pedido):
            if pedido.imagem == b"x" and not hasattr(self, "n"):
                self.n = 0
            self.n += 1
            if self.n == 3:
                raise RuntimeError("503 do provedor")
            return super().executar(pedido)
    ev = rodar(Quebra())
    paginas_ok = [e["numero"] for e in ev if e["evento"] == "pagina" and e["status"] == "OK"]
    assert paginas_ok == list(range(1, paginas_ok[-1] + 1)), "o checkpoint é contíguo: nada depois da página que falhou"
    assert ev[-1]["evento"] == "falhou" and ev[-2]["status"] == "FALHOU" and not any(e["evento"] == "concluido" for e in ev)
    ev = rodar(Prov(), n=6, falha_em=4)
    assert [e["numero"] for e in ev if e["evento"] == "pagina"] == [1, 2, 3] and ev[-1]["evento"] == "falhou"


def test_roteador_faz_parte_da_impressao_do_motor():
    """Mudar a regra de camadas muda a análise de uma página: o cache da Camada 0 não pode reaproveitar a feita pela regra antiga."""
    from ia_core import impressao
    assert "roteador.py" in impressao._ARQUIVOS and all(__import__("os").path.exists(__import__("os").path.join(impressao._AQUI, n)) for n in impressao._ARQUIVOS)


def test_folha_so_com_marca_dagua_e_descartada_mas_bilhete_manuscrito_nao():
    """'AMOSTRA - DOCUMENTO FICTÍCIO' sozinho numa folha vazia não é documento; a mesma marca sobre uma página com conteúdo não a descarta."""
    from ia_core.providers import leitura_local
    marca = "AMOSTRA - DOCUMENTO FICTÍCIO - gerado para testes de software - sem validade jurídica"
    pronta, _, _ = leitura_local(_png_folha(aviso="AMOSTRA"), marca)  # texto nativo só de marca + pouca tinta
    assert pronta and pronta["pagina_em_branco"]
    pronta, texto, nativo = leitura_local(_png_pagina(), marca)  # muita tinta: é uma página de verdade com carimbo
    assert not (pronta and pronta["pagina_em_branco"])


def test_poeira_e_marca_dagua_inclinada_nao_sao_documento_mas_traco_manuscrito_e():
    """Folha de scanner com poeira espalhada (pontinhos isolados) é vazia; um traço agrupado (manuscrito/assinatura) não é."""
    import io, random
    from PIL import Image, ImageDraw
    from ia_core.qualidade_img import analisar_imagem
    rnd = random.Random(3)
    poeira = Image.new("L", (1240, 1754), 250); d = ImageDraw.Draw(poeira)
    for _ in range(60):
        x, y = rnd.randrange(100, 1140), rnd.randrange(100, 1650); d.ellipse((x, y, x + 3, y + 3), fill=30)
    assinatura = Image.new("L", (1240, 1754), 250); d = ImageDraw.Draw(assinatura)
    d.line([(400, 900), (520, 860), (640, 920), (760, 870)], fill=20, width=5)
    def png(im): b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()
    assert analisar_imagem(png(poeira))["branco"]
    assert not analisar_imagem(png(assinatura))["branco"]


# ---- tipos documentais descobertos pela IA ------------------------------------------------------------------------------------
@pytest.fixture
def tipos_limpos():
    """Cada teste começa e termina sem tipos descobertos (o catálogo é um dicionário global do processo)."""
    from ia_core import catalogo as cat
    def limpar():
        for c in [c for c, d in cat.TIPOS.items() if d.get("origem") == cat.ORIGEM_IA]:
            cat.TIPOS.pop(c); cat.DOCS_DA_EMPRESA.discard(c); cat.DOCS_MENSAIS.discard(c)
    limpar(); yield cat; limpar()


TEXTO_PROCURACAO = "PROCURACAO PARTICULAR  Pelo presente instrumento, o OUTORGANTE nomeia o OUTORGADO para representá-lo perante a empresa. Local e data. Assinatura do outorgante " * 2


def _resposta_tipo_novo(**extra):
    base = {"tipo": "OUTRO", "inicia_documento": True, "confianca": 0.9, "titulo": "Procuração", "texto_ocr": TEXTO_PROCURACAO,
            "tipo_novo": {"nome": "Procuração", "escopo": "FUNCIONARIO", "categoria": "ADMISSAO", "pistas": ["Procuração particular", "outorgante nomeia", "frase que não está na página"]}}
    base.update(extra); return base


def test_ia_descobre_tipo_novo_e_aprende_pistas_locais(tipos_limpos):
    cat = tipos_limpos
    fake = _FakeOpenAI([_resposta_tipo_novo()]); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert pg["tipo"] == "PROCURACAO" and pg["titulo"] == "Procuração" and pg["tipo_novo"]["codigo"] == "PROCURACAO"
    assert pg["tipo_novo"]["pistas"] == ["PROCURACAO PARTICULAR", "OUTORGANTE NOMEIA"]  # a frase inventada pelo modelo é barrada
    assert cat.TIPOS["PROCURACAO"]["origem"] == "IA"
    # a próxima página do mesmo tipo é reconhecida localmente, sem modelo
    tipo, conf = cat.classificar("Procuração particular. O outorgante nomeia o outorgado para representá-lo.")
    assert tipo == "PROCURACAO" and conf >= 0.7


def test_pista_inventada_nao_vira_regra_local(tipos_limpos):
    cat = tipos_limpos
    assert cat.pistas_validas(["frase que nao esta na pagina", "PROCURACAO PARTICULAR", "x 12345 y"], "procuração particular do outorgante") == ["PROCURACAO PARTICULAR"]


def test_nome_generico_ou_instancia_nao_cria_tipo(tipos_limpos):
    cat = tipos_limpos
    for nome in ("Documento", "Outro", "Declaração", "Contrato de João da Silva CPF 529.982.247-25", "x", "Boleto 123456789012"):
        assert cat.propor_tipo(nome, [], "texto") is None, nome
    fake = _FakeOpenAI([_resposta_tipo_novo(tipo_novo={"nome": "Documento", "pistas": []})]); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert pg["tipo"] == "OUTRO" and "tipo_novo" not in pg


def test_tipo_novo_equivalente_a_um_do_catalogo_reaproveita_o_existente(tipos_limpos):
    cat = tipos_limpos
    assert cat.propor_tipo("Nota fiscal de serviço", [], "x") == "NOTA_FISCAL"
    assert cat.propor_tipo("Guia de recolhimento do FGTS", [], "x") == "GUIA_FGTS"
    assert not [c for c, d in cat.TIPOS.items() if d.get("origem") == "IA"]


def test_tipo_novo_so_com_confianca_alta_e_pagina_legivel(tipos_limpos):
    fake = _FakeOpenAI([_resposta_tipo_novo(confianca=0.5), _resposta_tipo_novo(confianca=0.5)]); p = _provider_openai(fake)
    assert p.analisar(_png_pagina(), 1, None, "", "MISTO")["tipo"] == "OUTRO"
    fake = _FakeOpenAI([_resposta_tipo_novo(pagina_ilegivel=True), _resposta_tipo_novo(pagina_ilegivel=True)]); p = _provider_openai(fake)
    assert p.analisar(_png_pagina(), 1, None, "", "MISTO")["tipo"] == "OUTRO"


def test_codigo_inventado_pelo_modelo_vira_tipo_novo(tipos_limpos):
    """O modelo ignorou a lista e devolveu um código próprio: em vez de OUTRO, o código vira o nome do tipo."""
    fake = _FakeOpenAI([_resposta_tipo_novo(tipo="LAUDO_INSALUBRIDADE", tipo_novo=None)]); p = _provider_openai(fake)
    pg = p.analisar(_png_pagina(), 1, None, "", "MISTO")
    assert pg["tipo"] == "LAUDO_INSALUBRIDADE" and pg["titulo"] == "Laudo Insalubridade" and pg["tipo_novo"]["pistas"] == []


def test_catalogo_de_tipos_da_ia_tem_teto_e_nao_sobrescreve_estatico(tipos_limpos, monkeypatch):
    cat = tipos_limpos
    assert not cat.registrar_tipo("HOLERITE", "Holerite falso", ["x"])  # tipo estático não é sobrescrito
    assert not cat.registrar_tipo("OUTRO", "Outro", [])
    monkeypatch.setattr(cat, "MAX_TIPOS_IA", 2)
    assert cat.registrar_tipo("TIPO_UM", "Tipo um") and cat.registrar_tipo("TIPO_DOIS", "Tipo dois")
    assert not cat.registrar_tipo("TIPO_TRES", "Tipo três") and cat.registrar_tipo("TIPO_UM", "Tipo um", ["OUTRA FRASE LONGA"])  # atualizar o que já existe pode


def test_tipo_da_ia_da_empresa_nao_exige_cpf_e_agrupador_carrega_tipo_novo(tipos_limpos):
    cat = tipos_limpos
    cat.registrar_tipo("LAUDO_AMBIENTAL", "Laudo ambiental", ["LAUDO AMBIENTAL DA OBRA"], escopo="EMPRESA", categoria="MENSAL")
    assert "LAUDO_AMBIENTAL" in cat.DOCS_DA_EMPRESA and "LAUDO_AMBIENTAL" in cat.DOCS_MENSAIS
    from ia_core.roteador import campos_faltando
    assert campos_faltando("LAUDO_AMBIENTAL", {}, True) == ["competencia"]
    pg = dict(tipo="LAUDO_AMBIENTAL", inicia_documento=True, confianca=0.9, texto_ocr="Laudo ambiental da obra. " * 10, campos={}, titulo="Laudo ambiental",
              possui_manuscrito=False, pagina_ilegivel=False, multiplos_documentos_na_imagem=False, pagina_em_branco=False, tokens=0, tipo_novo=cat.dados_tipo_ia("LAUDO_AMBIENTAL"))
    docs = agrupar.agrupar({1: pg})
    assert docs[0]["tipo"] == "LAUDO_AMBIENTAL" and docs[0]["tipo_novo"]["nome"] == "Laudo ambiental"
    # lote retomado em outro processo: o tipo some do catálogo e é reaprendido pelas análises salvas
    cat.TIPOS.pop("LAUDO_AMBIENTAL")
    docs = agrupar.agrupar({1: pg})
    assert docs[0]["tipo"] == "LAUDO_AMBIENTAL" and "LAUDO_AMBIENTAL" in cat.TIPOS


def test_precisa_subir_respeita_o_escopo_do_tipo_novo():
    from ia_core.roteador import precisa_subir
    local = {"tipo": "OUTRO", "campos": {}}
    resp = {"confianca": 0.9, "inicia_documento": True, "tipo_novo": {"nome": "Procuração", "escopo": "FUNCIONARIO"}}
    assert "CPF" in precisa_subir(resp, local, "texto", nativo=False)  # tipo de pessoa sem CPF lido no OCR: confere na imagem
    resp["tipo_novo"]["escopo"] = "EMPRESA"
    assert precisa_subir(resp, local, "texto", nativo=False) == ""


def test_separador_de_documentos_nao_vira_documento():
    from ia_core.providers import LocalProvider
    pg = LocalProvider().analisar(_png_pagina(), 1, None, "| SEPARADOR DE DOCUMENTOS | Competência 03/2026", "MISTO")
    assert pg["pagina_em_branco"] and agrupar.agrupar({1: pg}) == []


def test_tipos_novos_do_catalogo_estatico_reconhecem_documentos_comuns():
    from ia_core.catalogo import classificar
    casos = {"NOTA_FISCAL": "NOTA FISCAL DE SERVICO ELETRONICA NFS-e numero 123", "CARTAO_CNPJ": "COMPROVANTE DE INSCRICAO E DE SITUACAO CADASTRAL CADASTRO NACIONAL DA PESSOA JURIDICA",
             "TITULO_ELEITOR": "TITULO DE ELEITOR zona eleitoral secao", "CERTIDAO_CIVIL": "CERTIDAO DE NASCIMENTO registro civil das pessoas naturais",
             "PROGRAMA_SST": "PROGRAMA DE GERENCIAMENTO DE RISCOS PGR inventario de riscos", "ALVARA_LICENCA": "ALVARA DE FUNCIONAMENTO da prefeitura",
             "CONTRATO_SOCIAL": "CONTRATO SOCIAL junta comercial capital social", "OFICIO": "OFICIO N 12/2026 Assunto: regularizacao"}
    for esperado, texto in casos.items():
        assert classificar(texto)[0] == esperado, esperado
