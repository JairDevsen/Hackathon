import csv
import hashlib
import json
import random
import sys
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gerador.__main__ import renderizar  # noqa: E402
from gerador._ia_core import sch, val  # noqa: E402
from gerador.canvas import Folha  # noqa: E402
from gerador.conferencia import conferir  # noqa: E402
from gerador.montagem import NCS, PERFIS, Config, gerar  # noqa: E402
from gerador.universo import gerar_universo  # noqa: E402

T = sch.TipoDocumento
HOJE = date(2026, 11, 5)


@pytest.fixture(scope="module")
def u():
    return gerar_universo(11, hoje=HOJE)


@pytest.fixture(autouse=True)
def sem_defeitos():
    Folha.taxa_defeito_padrao = Folha.taxa_branco_padrao = 0.0
    yield
    Folha.taxa_defeito_padrao = Folha.taxa_branco_padrao = 0.0


@pytest.mark.parametrize("tipo", list(T))
def test_todo_tipo_tem_gabarito_fiel_ao_desenho(u, tipo):
    """Cada valor do gabarito aparece na página e nenhum campo obrigatório fica vazio (inclusive com rasuras e brancos)."""
    for s, taxa in [(0, 0.0), (1, 0.0), (2, 0.3), (3, 0.3)]:
        Folha.taxa_defeito_padrao, Folha.taxa_branco_padrao = taxa, taxa / 3
        doc = renderizar(tipo, random.Random(s), u)
        assert not conferir(doc), f"{tipo}: {conferir(doc)}"
        assert doc.paginas and all(p.info.get("ficticio") for p in doc.paginas), "página sem marca de amostra"
        if tipo != T.OUTRO:
            sch.MODELOS_EXTRACAO[tipo].model_validate(doc.dados.model_dump())


@pytest.mark.parametrize("tipo", [t for t in NCS])
def test_sem_nc_nao_gera_erro(u, tipo):
    for s in range(4):
        doc = renderizar(tipo, random.Random(s), u)
        erros = [a for a in val.validar(doc.dados, HOJE) if a.severidade == "erro"]
        assert not erros, f"{tipo}: {erros}"


@pytest.mark.parametrize("tipo,nc", [(t, nc) for t, ncs in NCS.items() for nc in ncs])
def test_nc_injetada_e_detectada(u, tipo, nc):
    doc = renderizar(tipo, random.Random(3), u, nc)
    campos = {a.campo for a in val.validar(doc.dados, HOJE)}
    assert NCS[tipo][nc] in campos, f"{tipo}/{nc} não acusado; alertas: {campos}"


@pytest.mark.parametrize("perfil", PERFIS)
def test_lote_por_perfil_gabarito_consistente(tmp_path, perfil):
    cfg = Config(qtd_lotes=1, paginas=(8, 14), perfil=perfil, seed=5, p_celular=0.3, extras=0.5, taxa_defeito=0.15)
    gerar(cfg, tmp_path, gerar_universo(5, hoje=HOJE))
    linhas = list(csv.DictReader((tmp_path / "gabarito.csv").open(encoding="utf-8")))
    lj = json.loads((tmp_path / "gabarito" / "lote_0001.json").read_text(encoding="utf-8"))
    n_pdf = len(pdfium.PdfDocument(tmp_path / "lotes" / "lote_0001.pdf"))
    assert n_pdf == len(linhas) == lj["total_paginas"]
    # toda página aponta para documentos existentes e todo documento aparece em alguma página
    vistos = set()
    for p in lj["paginas"]:
        for d in p["documentos"]:
            assert 1 <= d["indice"] <= lj["total_documentos"]
            vistos.add(d["indice"])
    assert vistos == set(range(1, lj["total_documentos"] + 1))
    for d in lj["documentos"]:
        assert all(1 <= p <= n_pdf for p in d["paginas"])
        if d["dados"]:
            sch.MODELOS_EXTRACAO[T(d["tipo"])].model_validate(d["dados"])


def test_reprodutibilidade(tmp_path):
    cfg = Config(qtd_lotes=1, paginas=(6, 10), seed=9)
    h = []
    for pasta in ("a", "b"):
        gerar(cfg, tmp_path / pasta, gerar_universo(9, hoje=HOJE))
        h.append(hashlib.sha256((tmp_path / pasta / "gabarito.csv").read_bytes()
                                + (tmp_path / pasta / "lotes" / "lote_0001.pdf").read_bytes()).hexdigest())
    assert h[0] == h[1]


def test_recebimento_ar_tem_varios_ar(tmp_path):
    gerar(Config(qtd_lotes=1, paginas=(16, 20), perfil="recebimento_ar", seed=31), tmp_path, gerar_universo(31, hoje=HOJE))
    lj = json.loads((tmp_path / "gabarito" / "lote_0001.json").read_text(encoding="utf-8"))
    ars = [d for d in lj["documentos"] if d["tipo"] == "AVISO_RECEBIMENTO"]
    assert len(ars) >= 4
    for d in ars:
        assert d["dados"]["codigo_objeto"] and d["dados"]["data_postagem"] and d["dados"]["destinatario_cep"]
