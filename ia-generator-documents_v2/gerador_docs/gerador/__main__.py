"""CLI do gerador de documentos trabalhistas FICTÍCIOS.

  python -m gerador lotes   --qtd 10 --perfil sortear --paginas 8-40 --saida saida/
  python -m gerador amostra --tipo PEDIDO_DEMISSAO --qtd 3 --saida amostras/
  python -m gerador tipos
"""
from __future__ import annotations

import argparse
import dataclasses
import random
from pathlib import Path

from . import documentos as D
from . import documentos_rh as R
from ._ia_core import sch
from .canvas import Folha
from .conferencia import conferir
from .montagem import PERFIS, Config, gerar
from .scanner import capturar
from .universo import gerar_universo

T = sch.TipoDocumento


def renderizar(tipo, rng, u, nc=None):
    """Gera um documento avulso de qualquer tipo."""
    emp = rng.choice(u.empresas)
    e = rng.choice(u.empregados_de(emp.cnpj))
    comp = rng.choice(u.competencias)
    if tipo in (T.TRCT, T.PEDIDO_DEMISSAO) and not e.desligado_em:
        e = dataclasses.replace(e, desligado_em=f"{u.competencias[-1]}-15")
        for c in u.competencias:
            u.meses[(e.cpf, c)] = u.meses[(rng.choice(u.empregados_de(emp.cnpj)).cpf, c)]
    tabela = {
        T.HOLERITE: lambda: D.holerite(rng, u, e, emp, comp, nc), T.CARTAO_PONTO: lambda: D.cartao_ponto(rng, u, e, emp, comp, nc),
        T.CRF_FGTS: lambda: D.certidao(rng, u, emp, tipo, nc), T.CNDT: lambda: D.certidao(rng, u, emp, tipo, nc),
        T.CND_FEDERAL: lambda: D.certidao(rng, u, emp, tipo, nc), T.GUIA_FGTS: lambda: D.guia_fgts(rng, u, emp, comp),
        T.COMPROVANTE_PAGAMENTO: lambda: D.comprovante(rng, u, e, emp, comp), T.FICHA_EPI: lambda: D.ficha_epi(rng, u, e, emp, nc),
        T.ASO: lambda: D.aso(rng, u, e, emp, nc), T.TRCT: lambda: D.trct(rng, u, e, emp, nc),
        T.AVISO_RECEBIMENTO: lambda: D.aviso_recebimento(rng, u, e, emp, nc), T.OUTRO: lambda: D.outro(rng, u, emp, comp),
        T.NOTIFICACAO_EMPREGADO: lambda: R.notificacao(rng, u, e, emp, "Notificação nº 12/2026", gerar_data(u)),
        T.PEDIDO_DEMISSAO: lambda: R.pedido_demissao(rng, u, e, emp, nc), T.ATESTADO_MEDICO: lambda: R.atestado_medico(rng, u, e, emp, nc),
        T.DECLARACAO_MANUSCRITA: lambda: R.declaracao_manuscrita(rng, u, e, emp, nc), T.RECIBO_AVULSO: lambda: R.recibo_avulso(rng, u, e, emp, nc),
        T.JUSTIFICATIVA_FALTA: lambda: R.justificativa_falta(rng, u, e, emp, nc), T.ADVERTENCIA_SUSPENSAO: lambda: R.advertencia(rng, u, e, emp, nc),
        T.CTPS_ANOTACAO: lambda: R.ctps_anotacao(rng, u, e, emp, nc), T.FICHA_REGISTRO: lambda: R.ficha_registro(rng, u, e, emp, nc),
        T.LISTA_PRESENCA: lambda: R.lista_presenca(rng, u, emp, nc), T.ORDEM_SERVICO_SST: lambda: R.ordem_servico(rng, u, e, emp, nc),
        T.DECLARACAO_VALE_TRANSPORTE: lambda: R.declaracao_vt(rng, u, e, emp, nc),
        T.DECLARACAO_DEPENDENTES: lambda: R.declaracao_dependentes(rng, u, e, emp, nc),
        T.RECIBO_BENEFICIO: lambda: R.recibo_beneficio(rng, u, e, emp, comp, nc), T.FERIAS: lambda: R.ferias(rng, u, e, emp, nc),
        T.CHECKLIST_INTEGRACAO: lambda: R.checklist(rng, u, e, emp, nc), T.TERMO_RESPONSABILIDADE: lambda: R.termo_responsabilidade(rng, u, e, emp, nc),
        T.OCORRENCIA_ACIDENTE: lambda: R.ocorrencia_acidente(rng, u, e, emp, nc), T.CONTRATO_TRABALHO: lambda: R.contrato_trabalho(rng, u, e, emp, nc),
        T.DARF: lambda: R.darf(rng, u, emp, comp, nc),
    }
    doc = tabela[tipo]()
    if doc.meia_pagina:
        doc.paginas = [D.folha_de_comprovantes(rng, [doc])]
    return doc


def gerar_data(u):
    from datetime import date, timedelta
    return date.fromisoformat(u.data_referencia) - timedelta(days=15)


def _amostra(args) -> None:
    rng = random.Random(args.seed)
    u = gerar_universo(args.seed)
    Folha.taxa_defeito_padrao = args.taxa_defeito
    Folha.taxa_branco_padrao = args.taxa_defeito / 3
    tipo = T(args.tipo)
    args.saida.mkdir(parents=True, exist_ok=True)
    for i in range(args.qtd):
        doc = renderizar(tipo, rng, u, args.nc)
        problemas = conferir(doc)
        if problemas:
            print("ATENÇÃO – gabarito diverge:", problemas)
        if args.nativo:
            from .pdf_nativo import escrever_pdf
            escrever_pdf(args.saida / f"{tipo.value.lower()}_{i + 1:02d}.pdf", [("nativo", p) for p in doc.paginas], tipo.value)
        for n, p in enumerate(doc.paginas, 1):
            if args.nativo:
                break
            img = p if args.limpo else capturar(p, rng, args.degradacao, 0.5 if args.celular else 0.0, 0.0)[0]
            img.save(args.saida / f"{tipo.value.lower()}_{i + 1:02d}_p{n}.png")
        if doc.dados:
            (args.saida / f"{tipo.value.lower()}_{i + 1:02d}.json").write_text(doc.dados.model_dump_json(indent=2), encoding="utf-8")
    print(f"{args.qtd} amostra(s) de {tipo.value} em {args.saida}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="gerador", description="Gerador de documentos trabalhistas FICTÍCIOS para testes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("lotes", help="gera lotes PDF + gabaritos")
    lp.add_argument("--qtd", type=int, default=10)
    lp.add_argument("--perfil", choices=PERFIS + ["sortear"], default="sortear")
    lp.add_argument("--paginas", default="8-40", help="faixa de páginas por lote, ex.: 8-40")
    lp.add_argument("--degradacao", choices=["leve", "media", "forte", "misto"], default="misto")
    lp.add_argument("--taxa-nc", type=float, default=0.2, help="prob. de não conformidade por documento")
    lp.add_argument("--taxa-defeito", type=float, default=0.08, help="prob. de rasura/corretivo/riscado por campo manuscrito")
    lp.add_argument("--extras", type=float, default=0.25, help="prob. de grampo/clipe/post-it/dobra por página")
    lp.add_argument("--celular", type=float, default=0.12, help="prob. de página fotografada com celular")
    lp.add_argument("--cabeca-para-baixo", type=float, default=0.03)
    lp.add_argument("--embaralhar", type=float, default=0.3)
    lp.add_argument("--pdf-nativo", type=float, default=0.15,
                    help="prob. de um documento elegível vir como PDF nativo (texto selecionável, sem scanner); 0 a 1")
    lp.add_argument("--png", action="store_true", help="salva também cada página como PNG")
    lp.add_argument("--seed", type=int, default=42)
    lp.add_argument("--saida", type=Path, default=Path("saida"))
    am = sub.add_parser("amostra", help="gera documentos avulsos de um tipo (PNG + JSON)")
    am.add_argument("--tipo", required=True, choices=[t.value for t in T])
    am.add_argument("--qtd", type=int, default=3)
    am.add_argument("--nc", default=None, help="força uma não conformidade, ex.: sem_assinatura")
    am.add_argument("--degradacao", choices=["leve", "media", "forte"], default="media")
    am.add_argument("--taxa-defeito", type=float, default=0.1)
    am.add_argument("--celular", action="store_true")
    am.add_argument("--limpo", action="store_true", help="sem simulação de captura")
    am.add_argument("--nativo", action="store_true", help="salva como PDF nativo (texto selecionável)")
    am.add_argument("--seed", type=int, default=7)
    am.add_argument("--saida", type=Path, default=Path("amostras"))
    sub.add_parser("tipos", help="lista tipos e não conformidades")
    args = ap.parse_args()
    if args.cmd == "lotes":
        a, b = map(int, args.paginas.split("-"))
        gerar(Config(qtd_lotes=args.qtd, paginas=(a, b), degradacao=args.degradacao, taxa_nc=args.taxa_nc, perfil=args.perfil,
                     embaralhar=args.embaralhar, taxa_defeito=args.taxa_defeito, extras=args.extras, p_celular=args.celular,
                     p_cabeca_para_baixo=args.cabeca_para_baixo, p_pdf_nativo=args.pdf_nativo,
                     salvar_png=args.png, seed=args.seed), args.saida)
    elif args.cmd == "amostra":
        _amostra(args)
    else:
        from .montagem import NCS
        for t in T:
            print(f"{t.value:28s} {', '.join(NCS.get(t, {})) or '-'}")


if __name__ == "__main__":
    main()
