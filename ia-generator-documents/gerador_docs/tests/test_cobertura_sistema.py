"""O catálogo do sistema cobre os tipos que este gerador produz (ver cobertura_sistema.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cobertura_sistema as cs  # noqa: E402

RES = None


def _res():
    global RES
    if RES is None:
        RES = cs.medir(8)
    return RES


def test_todo_tipo_do_gerador_existe_no_catalogo_do_sistema():
    ausentes = [t for t, r in _res().items() if not r["existe_no_catalogo"]]
    assert not ausentes, f"tipos do gerador sem equivalente no sistema: {ausentes}"


def test_cada_tipo_e_reconhecido_na_maioria_das_amostras():
    fracos = {t: f"{r['acertos']}/{r['total']} {r['erros']}" for t, r in _res().items() if r["acertos"] / r["total"] < 0.75}
    assert not fracos, f"tipos com classificação fraca: {fracos}"


def test_acerto_geral_de_classificacao():
    res = _res()
    taxa = sum(r["acertos"] for r in res.values()) / sum(r["total"] for r in res.values())
    assert taxa >= 0.95, f"acerto geral {taxa:.1%} abaixo de 95%"
