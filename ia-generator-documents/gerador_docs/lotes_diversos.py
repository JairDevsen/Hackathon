"""Gera N lotes DIFERENTES entre si, com gabarito exato.

O comando `python -m gerador lotes` sorteia empresa, perfil e competência de um único universo (3 empresas, 3 meses,
os mesmos empregados), então os lotes se parecem. Aqui cada lote tem o seu próprio universo e os seus próprios parâmetros:

  - empresa, CNPJ, endereço, segmento e empregados (nomes, CPFs, cargos) próprios, sem repetir entre lotes;
  - competência (mês) distribuída ao longo do último ano;
  - perfil em rodízio (admissão, mensal, desligamento, ocorrências, recebimento de AR e misto), em ordem embaralhada;
  - tamanho (nº de páginas) e nível de degradação do scanner distintos;
  - taxas de não conformidade, rasura, extras (grampo, clipe, post-it), foto de celular, página invertida,
    documentos fora de ordem, intercalados e em branco sorteadas por lote.

Uso:  python lotes_diversos.py --qtd 30 --saida ../lotes_demo_30
"""
import argparse
import csv
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from gerador.montagem import Config, PERFIS, montar_lote
from gerador.universo import gerar_universo


def parametros(i: int, seed: int, perfil: str, paginas: int, degradacao: str, hoje: date) -> Config:
    """Parâmetros do lote `i`: tudo que não é fixo vem de um sorteio próprio do lote."""
    r = random.Random(seed * 1000 + i)
    return Config(
        qtd_lotes=1, paginas=(paginas, paginas), degradacao=degradacao, perfil=perfil,
        taxa_nc=round(r.uniform(0.10, 0.40), 2), taxa_defeito=round(r.uniform(0.03, 0.20), 2),
        taxa_branco=round(r.uniform(0.01, 0.06), 2), extras=round(r.uniform(0.10, 0.45), 2),
        p_celular=round(r.uniform(0.03, 0.30), 2), p_cabeca_para_baixo=round(r.uniform(0.0, 0.08), 2),
        embaralhar=round(r.uniform(0.10, 0.60), 2), paginas_em_branco=round(r.uniform(0.02, 0.10), 2),
        fora_de_ordem=round(r.uniform(0.05, 0.30), 2), intercalar=round(r.uniform(0.05, 0.30), 2),
        seed=seed * 1000 + i,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera lotes fictícios diferentes entre si")
    ap.add_argument("--qtd", type=int, default=30)
    ap.add_argument("--paginas", default="8-25", help="faixa de páginas; cada lote recebe um tamanho diferente dentro dela")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--saida", type=Path, default=Path("saida_diversos"))
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.paginas.split("-"))
    ordem = random.Random(a.seed)

    # rodízios embaralhados: todos os perfis/níveis aparecem, e tamanhos distintos sempre que a faixa permitir
    perfis = [PERFIS[k % len(PERFIS)] for k in range(a.qtd)]
    niveis = [["leve", "media", "forte", "misto"][k % 4] for k in range(a.qtd)]
    tamanhos = [lo + (k * 7) % (hi - lo + 1) for k in range(a.qtd)]
    for lista in (perfis, niveis, tamanhos):
        ordem.shuffle(lista)

    (a.saida / "lotes").mkdir(parents=True, exist_ok=True)
    (a.saida / "gabarito").mkdir(exist_ok=True)
    (a.saida / "universos").mkdir(exist_ok=True)
    base = date.today().replace(day=15)
    todas_linhas, resumo, tipos_total = [], [], Counter()

    for i in range(1, a.qtd + 1):
        hoje = base - timedelta(days=30 * ((i * 5) % 12))  # competência diferente ao longo do último ano
        cfg = parametros(i, a.seed, perfis[i - 1], tamanhos[i - 1], niveis[i - 1], hoje)
        nome = f"lote_{i:04d}.pdf"
        # A conferência de fidelidade do gerador recusa lotes cujo gabarito diverge do desenho (por exemplo, um relato longo
        # que não cabe nas linhas do formulário). Nesse caso sorteamos de novo, com a mesma empresa e os mesmos parâmetros.
        for tentativa in range(10):
            u = gerar_universo(cfg.seed, n_empresas=1, empregados_por_empresa=(8, 16), n_competencias=2, hoje=hoje)
            rng = random.Random(cfg.seed + tentativa * 7919)
            try:
                paginas, linhas, lj = montar_lote(rng, u, cfg, nome)
                break
            except AssertionError as erro:
                print(f"  {nome}: tentativa {tentativa + 1} recusada pela conferência ({str(erro)[:110]}...)", flush=True)
        else:
            raise SystemExit(f"{nome}: nenhuma das 10 tentativas passou na conferência de fidelidade")
        lj["tentativas"] = tentativa + 1
        fixa = "D:" + u.data_referencia.replace("-", "") + "000000Z"
        paginas[0].save(a.saida / "lotes" / nome, save_all=True, append_images=paginas[1:], resolution=200,
                        creationDate=fixa, modDate=fixa, title=f"{nome} - AMOSTRA - documentos ficticios")
        lj["parametros"] = {k: v for k, v in cfg.__dict__.items() if k not in ("qtd_lotes", "salvar_png")}
        (a.saida / "gabarito" / f"{nome[:-4]}.json").write_text(json.dumps(lj, ensure_ascii=False, indent=2), encoding="utf-8")
        (a.saida / "universos" / f"{nome[:-4]}.json").write_text(json.dumps(u.para_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        todas_linhas += linhas
        tipos = Counter(d["tipo"] for d in lj["documentos"])
        tipos_total.update(tipos)
        emp = u.empresas[0]
        resumo.append({"arquivo": nome, "perfil": lj["perfil"], "empresa": emp.razao_social, "cnpj": emp.cnpj, "competencia": lj["competencia"],
                       "paginas": lj["total_paginas"], "documentos": lj["total_documentos"], "degradacao": lj["degradacao"],
                       "tipos_distintos": len(tipos), "tipos": " ".join(f"{t}x{n}" for t, n in sorted(tipos.items()))})
        print(f"{nome}: {lj['perfil']:15s} {lj['total_paginas']:3d} págs {lj['total_documentos']:3d} docs  {emp.razao_social[:38]:38s} {lj['competencia']}  {lj['degradacao']}", flush=True)

    with (a.saida / "gabarito.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "pagina", "tipo", "documento", "pagina_do_documento", "inicia_documento", "multiplos_documentos", "rotacao", "captura"])
        w.writerows(todas_linhas)
    with (a.saida / "resumo_lotes.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(resumo[0]))
        w.writeheader()
        w.writerows(resumo)
    (a.saida / "manifesto.json").write_text(json.dumps({
        "seed": a.seed, "lotes": resumo, "documentos_por_tipo": dict(tipos_total),
        "aviso": "Todos os dados são fictícios; todas as páginas levam a marca 'AMOSTRA – DOCUMENTO FICTÍCIO'."}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{a.qtd} lotes em {a.saida}  |  empresas distintas: {len({r['cnpj'] for r in resumo})}  |  perfis: {dict(Counter(r['perfil'] for r in resumo))}")


if __name__ == "__main__":
    main()
