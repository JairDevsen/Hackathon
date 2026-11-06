"""Cobertura do sistema: o catálogo do IA Core reconhece cada tipo de documento que este gerador produz?

Para cada um dos 32 tipos, gera N documentos e classifica o TEXTO realmente desenhado em cada um (`doc.registro`)
com o classificador do sistema (`ia-core/ia_core/catalogo.py`). Compara com o gabarito, aceitando os códigos
equivalentes (`catalogo.GERADOR`), pois alguns tipos têm outro nome no sistema.

Uso:  python cobertura_sistema.py [N]        (padrão: 10 documentos por tipo)

Limites: mede o vocabulário do catálogo sobre o texto exato do gerador (sem OCR, sem imagem, documento inteiro e não página a
página). Não mede OCR nem Gemini, e o resultado tende a ser otimista em relação a documentos reais.
"""
import importlib.util
import random
import sys
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gerador.__main__ import T, renderizar  # noqa: E402
from gerador.universo import gerar_universo  # noqa: E402


def carregar_catalogo():
    """O sistema e o gerador têm, cada um, um pacote `ia_core`: carrega o catálogo do sistema por caminho."""
    caminho = HERE.parents[1] / "ia-core" / "ia_core" / "catalogo.py"
    spec = importlib.util.spec_from_file_location("catalogo_do_sistema", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def medir(n: int = 10, seed: int = 7) -> dict:
    cat = carregar_catalogo()
    universo = gerar_universo(seed)
    out = {}
    for tipo in T:
        rng = random.Random(zlib.crc32(tipo.value.encode()))  # determinístico entre execuções (hash() do Python varia)
        aceitos = cat.codigos_equivalentes(tipo.value)
        acertos, erros = 0, Counter()
        for _ in range(n):
            doc = renderizar(tipo, rng, universo)
            predito, _conf = cat.classificar("\n".join(doc.registro))
            if predito in aceitos:
                acertos += 1
            else:
                erros[predito] += 1
        out[tipo.value] = {"acertos": acertos, "total": n, "erros": dict(erros), "existe_no_catalogo": aceitos <= set(cat.TIPOS)}
    return out


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    res = medir(n)
    for tipo, r in res.items():
        marca = "✔" if r["acertos"] == r["total"] else "✘"
        print(f"{marca} {tipo:28s} {r['acertos']:3d}/{r['total']}  {r['erros'] or ''}")
    ok = sum(r["acertos"] for r in res.values())
    total = sum(r["total"] for r in res.values())
    print(f"\nTOTAL {ok}/{total} = {100 * ok / total:.1f}%")


if __name__ == "__main__":
    main()
