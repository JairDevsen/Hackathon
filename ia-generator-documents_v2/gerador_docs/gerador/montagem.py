"""Monta lotes (PDF multipágina) por perfil e escreve os gabaritos (CSV por página + JSON por lote)."""
from __future__ import annotations

import csv
import dataclasses
import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

from . import documentos as D
from . import documentos_rh as R
from . import extras
from ._ia_core import sch
from .canvas import Folha, fmt_data
from .conferencia import conferir
from .pdf_nativo import analisar, escrever_pdf
from .scanner import capturar
from .universo import Empregado, Universo, gerar_universo

T = sch.TipoDocumento
VERSAO = "2.0.0"
NCS = {**D.NCS, **R.NCS_RH}
PERFIS = ["admissao", "mensal", "desligamento", "ocorrencias", "recebimento_ar", "misto"]


@dataclass
class Config:
    qtd_lotes: int = 10
    paginas: tuple[int, int] = (8, 40)
    degradacao: str = "misto"     # leve | media | forte | misto
    taxa_nc: float = 0.2
    perfil: str = "sortear"       # um de PERFIS ou "sortear"
    embaralhar: float = 0.3       # prob. de o lote vir com documentos fora da ordem natural
    paginas_em_branco: float = 0.05
    fora_de_ordem: float = 0.15   # prob. de um documento multipágina ter uma página trocada
    intercalar: float = 0.15      # prob. de um documento multipágina ter outro documento no meio
    taxa_defeito: float = 0.08    # prob. de cada campo manuscrito ter rasura/corretivo/riscado/fora da linha
    taxa_branco: float = 0.03     # prob. de um campo opcional ficar em branco
    extras: float = 0.25          # grampo, clipe, post-it, dobra, carimbo de recebido
    p_celular: float = 0.12       # página fotografada com celular
    p_cabeca_para_baixo: float = 0.03
    p_pdf_nativo: float = 0.15    # prob. de um documento elegível vir como PDF nativo (texto selecionável, sem scanner)
    salvar_png: bool = False
    seed: int = 42


# Tipos que costumam sair direto de um sistema como PDF (holerite, certidões, guias, contrato...).
# Formulários preenchidos à mão, AR, carteira de trabalho e fichas antigas não entram.
TIPOS_PDF_NATIVO = {T.HOLERITE, T.CARTAO_PONTO, T.GUIA_FGTS, T.CRF_FGTS, T.CNDT, T.CND_FEDERAL, T.DARF, T.TRCT,
                    T.CONTRATO_TRABALHO, T.NOTIFICACAO_EMPREGADO, T.ORDEM_SERVICO_SST, T.ADVERTENCIA_SUSPENSAO,
                    T.COMPROVANTE_PAGAMENTO, T.OUTRO}
LIMITE_RASTER_NATIVO = 0.02  # acima disso a página tem escrita à mão demais para ser um PDF de sistema


def pode_ser_nativo(doc) -> bool:
    if doc.tipo not in TIPOS_PDF_NATIVO:
        return False
    if doc.tipo == T.CARTAO_PONTO and doc.dados.forma_registro != "ELETRONICO":
        return False
    if doc.tipo == T.ADVERTENCIA_SUSPENSAO and doc.dados.forma != "IMPRESSA":
        return False
    for p in doc.paginas:
        a = analisar(p)
        if a is None or a.fracao_raster > LIMITE_RASTER_NATIVO:
            return False
    return True


# ------------------------------------------------------------------ helpers
def _nc(rng, tipo, taxa):
    op = list(NCS.get(tipo, {}))
    return rng.choice(op) if op and rng.random() < taxa else None


def _meta(doc, e: Empregado | None, comp: str | None, cnpj: str):
    doc.meta = {"cpf": e.cpf if e else None, "empregado": e.nome if e else None, "competencia": comp, "empresa_cnpj": cnpj}
    return doc


def _desligado(rng, u: Universo, e: Empregado, comp: str) -> Empregado:
    if e.desligado_em and e.desligado_em[:7] == comp:
        return e
    a, m = map(int, comp.split("-"))
    e2 = dataclasses.replace(e, desligado_em=date(a, m, rng.randint(5, 28)).isoformat())
    for c in u.competencias:
        u.meses[(e2.cpf, c)] = u.meses[(e.cpf, c)]
    return e2


# ------------------------------------------------------------------ perfis
def _docs_admissao(rng, u, emp, comp, cfg, alvo=30):
    docs = []
    novos = u.empregados_de(emp.cnpj)[:]
    rng.shuffle(novos)
    for e in novos[:max(1, min(5, alvo // 12))]:
        g = lambda d: docs.append(_meta(d, e, None, emp.cnpj))  # noqa: E731
        g(R.contrato_trabalho(rng, u, e, emp, _nc(rng, T.CONTRATO_TRABALHO, cfg.taxa_nc)))
        g(R.ficha_registro(rng, u, e, emp))
        g(R.ctps_anotacao(rng, u, e, emp))
        g(D.aso(rng, u, e, emp, _nc(rng, T.ASO, cfg.taxa_nc), "ADMISSIONAL"))
        for fn, t in [(R.declaracao_vt, T.DECLARACAO_VALE_TRANSPORTE), (R.declaracao_dependentes, T.DECLARACAO_DEPENDENTES),
                      (R.ordem_servico, T.ORDEM_SERVICO_SST), (R.termo_responsabilidade, T.TERMO_RESPONSABILIDADE),
                      (R.checklist, T.CHECKLIST_INTEGRACAO)]:
            if rng.random() < 0.8:
                g(fn(rng, u, e, emp, _nc(rng, t, cfg.taxa_nc)))
        if rng.random() < 0.7:
            g(D.ficha_epi(rng, u, e, emp, _nc(rng, T.FICHA_EPI, cfg.taxa_nc)))
        if rng.random() < 0.6:
            g(R.declaracao_manuscrita(rng, u, e, emp, _nc(rng, T.DECLARACAO_MANUSCRITA, cfg.taxa_nc),
                                      rng.choice(["RESIDENCIA", "NAO_ACUMULO_EMPREGO"])))
    docs.append(_meta(R.lista_presenca(rng, u, emp, _nc(rng, T.LISTA_PRESENCA, cfg.taxa_nc)), None, None, emp.cnpj))
    return docs


def _docs_mensal(rng, u, emp, comp, cfg, alvo):
    docs = []
    for t in (T.CRF_FGTS, T.CNDT, T.CND_FEDERAL):
        if rng.random() < 0.8:
            docs.append(_meta(D.certidao(rng, u, emp, t, _nc(rng, t, cfg.taxa_nc)), None, None, emp.cnpj))
    docs.append(_meta(D.guia_fgts(rng, u, emp, comp), None, comp, emp.cnpj))
    if rng.random() < 0.7:
        docs.append(_meta(R.darf(rng, u, emp, comp), None, comp, emp.cnpj))
    pend = []
    for e in rng.sample(u.empregados_de(emp.cnpj), len(u.empregados_de(emp.cnpj))):
        if sum(len(d[0].paginas) if isinstance(d, list) else len(d.paginas) for d in docs) >= alvo:
            break
        if e.desligado_em and e.desligado_em[:7] == comp:
            continue
        g = lambda d, c=comp: docs.append(_meta(d, e, c, emp.cnpj))  # noqa: E731
        g(D.cartao_ponto(rng, u, e, emp, comp, _nc(rng, T.CARTAO_PONTO, cfg.taxa_nc)))
        g(D.holerite(rng, u, e, emp, comp, _nc(rng, T.HOLERITE, cfg.taxa_nc)))
        if rng.random() < 0.45:
            c = _meta(D.comprovante(rng, u, e, emp, comp), e, comp, emp.cnpj)
            pend.append(c)
            if len(pend) == 2 or rng.random() < 0.4:
                docs.append(pend if len(pend) > 1 else pend[0])
                pend = []
        if rng.random() < 0.4:
            g(R.recibo_beneficio(rng, u, e, emp, comp, _nc(rng, T.RECIBO_BENEFICIO, cfg.taxa_nc)))
        if rng.random() < 0.12:
            g(R.atestado_medico(rng, u, e, emp, _nc(rng, T.ATESTADO_MEDICO, cfg.taxa_nc)), None)
        if rng.random() < 0.12:
            g(R.justificativa_falta(rng, u, e, emp, _nc(rng, T.JUSTIFICATIVA_FALTA, cfg.taxa_nc)), None)
        if rng.random() < 0.1:
            g(R.recibo_avulso(rng, u, e, emp, _nc(rng, T.RECIBO_AVULSO, cfg.taxa_nc)), None)
        if rng.random() < 0.08:
            g(R.ferias(rng, u, e, emp, _nc(rng, T.FERIAS, cfg.taxa_nc)), None)
    if pend:
        docs.append(pend if len(pend) > 1 else pend[0])
    return docs


def _docs_desligamento(rng, u, emp, comp, cfg):
    docs = []
    for e0 in rng.sample(u.empregados_de(emp.cnpj), min(len(u.empregados_de(emp.cnpj)), rng.randint(1, 4))):
        e = _desligado(rng, u, e0, comp)
        g = lambda d, c=None: docs.append(_meta(d, e, c, emp.cnpj))  # noqa: E731
        if rng.random() < 0.5:
            g(R.pedido_demissao(rng, u, e, emp, _nc(rng, T.PEDIDO_DEMISSAO, cfg.taxa_nc)))
        else:
            numero = f"Notificação nº {rng.randint(10, 400)}/{comp[:4]}"
            dn = date.fromisoformat(e.desligado_em) - timedelta(days=rng.randint(10, 25))
            g(R.notificacao(rng, u, e, emp, numero, dn))
            g(D.aviso_recebimento(rng, u, e, emp, _nc(rng, T.AVISO_RECEBIMENTO, cfg.taxa_nc), numero, dn + timedelta(days=1)))
        g(D.trct(rng, u, e, emp, _nc(rng, T.TRCT, cfg.taxa_nc)), comp)
        if rng.random() < 0.7:
            g(D.aso(rng, u, e, emp, None, "DEMISSIONAL"))
        if rng.random() < 0.3:
            g(R.recibo_avulso(rng, u, e, emp))
    return docs


def _docs_ocorrencias(rng, u, emp, comp, cfg):
    docs = []
    for e in rng.sample(u.empregados_de(emp.cnpj), min(len(u.empregados_de(emp.cnpj)), rng.randint(3, 7))):
        g = lambda d: docs.append(_meta(d, e, None, emp.cnpj))  # noqa: E731
        escolha = rng.choice(["adv", "adv", "just", "atest", "acid", "os"])
        if escolha == "adv":
            g(R.advertencia(rng, u, e, emp, _nc(rng, T.ADVERTENCIA_SUSPENSAO, cfg.taxa_nc)))
        elif escolha == "just":
            g(R.justificativa_falta(rng, u, e, emp, _nc(rng, T.JUSTIFICATIVA_FALTA, cfg.taxa_nc)))
        elif escolha == "atest":
            g(R.atestado_medico(rng, u, e, emp, _nc(rng, T.ATESTADO_MEDICO, cfg.taxa_nc)))
            if rng.random() < 0.5:
                g(R.justificativa_falta(rng, u, e, emp))
        elif escolha == "acid":
            g(R.ocorrencia_acidente(rng, u, e, emp, _nc(rng, T.OCORRENCIA_ACIDENTE, cfg.taxa_nc)))
        else:
            g(R.ordem_servico(rng, u, e, emp, _nc(rng, T.ORDEM_SERVICO_SST, cfg.taxa_nc)))
    if rng.random() < 0.6:
        docs.append(_meta(R.lista_presenca(rng, u, emp, _nc(rng, T.LISTA_PRESENCA, cfg.taxa_nc)), None, None, emp.cnpj))
    return docs


def _docs_recebimento_ar(rng, u, emp, comp, cfg, alvo):
    """Lote de ARs que voltaram: vários ARs, às vezes com a cópia da notificação."""
    docs = []
    pessoas = rng.sample(u.empregados_de(emp.cnpj), len(u.empregados_de(emp.cnpj)))
    hoje = date.fromisoformat(u.data_referencia)
    while len(docs) < max(4, alvo // 2) and pessoas:
        e = pessoas.pop()
        numero = f"Notificação nº {rng.randint(10, 400)}/{hoje.year}"
        dp = hoje - timedelta(days=rng.randint(10, 40))
        if rng.random() < 0.3:
            docs.append(_meta(R.notificacao(rng, u, e, emp, numero, dp - timedelta(days=1)), e, None, emp.cnpj))
        docs.append(_meta(D.aviso_recebimento(rng, u, e, emp, _nc(rng, T.AVISO_RECEBIMENTO, max(cfg.taxa_nc, 0.3)), numero, dp),
                          e, None, emp.cnpj))
    return docs


# ------------------------------------------------------------------ folhas
@dataclass
class FolhaLote:
    img: Image.Image
    docs: list[tuple[int, int]]  # (índice do documento no lote, página dentro do documento)
    nativo: bool = False         # True = página de PDF nativo (vetor), sem captura nem extras


def _folhas(rng, itens, cfg) -> tuple[list[FolhaLote], list]:
    """Converte a lista de documentos (ou grupos de comprovantes) em folhas, aplicando as variações de lote."""
    docs, folhas = [], []
    ar_pendentes = []  # (idx, frente, verso): ARs que entram no vidro do scanner juntos

    def novo(doc):
        docs.append(doc)
        return len(docs)

    def descarregar_ars():
        if not ar_pendentes:
            return
        modo = rng.choice(["frente_verso", "frentes_depois_versos", "dois_por_folha"])
        if modo == "frente_verso":
            for idx, fr, vs in ar_pendentes:
                folhas.append(FolhaLote(D.folhas_de_cartoes(rng, [fr, vs])[0], [(idx, 1), (idx, 2)]))
        elif modo == "frentes_depois_versos":
            for k in range(0, len(ar_pendentes), 2):
                grupo = ar_pendentes[k:k + 2]
                folhas.append(FolhaLote(D.folhas_de_cartoes(rng, [g[1] for g in grupo])[0], [(g[0], 1) for g in grupo]))
            for k in range(0, len(ar_pendentes), 2):
                grupo = ar_pendentes[k:k + 2]
                folhas.append(FolhaLote(D.folhas_de_cartoes(rng, [g[2] for g in grupo])[0], [(g[0], 2) for g in grupo]))
        else:  # frente e verso de ARs diferentes misturados de 2 em 2
            for k in range(0, len(ar_pendentes), 2):
                grupo = ar_pendentes[k:k + 2]
                folhas.append(FolhaLote(D.folhas_de_cartoes(rng, [g[1] for g in grupo])[0], [(g[0], 1) for g in grupo]))
                folhas.append(FolhaLote(D.folhas_de_cartoes(rng, [g[2] for g in grupo])[0], [(g[0], 2) for g in grupo]))
        ar_pendentes.clear()

    agrupar_ars = sum(1 for i in itens if not isinstance(i, list) and i.tipo == T.AVISO_RECEBIMENTO) >= 3
    for it in itens:
        if isinstance(it, list):  # comprovantes na mesma folha
            descarregar_ars()
            if rng.random() < cfg.p_pdf_nativo and all(pode_ser_nativo(d) for d in it):
                for d in it:  # PDF do banco: cada comprovante é um PDF próprio, no tamanho do recibo
                    d.formato = "pdf_nativo"
                    folhas.append(FolhaLote(d.paginas[0], [(novo(d), 1)], nativo=True))
                continue
            idxs = [novo(d) for d in it]
            folhas.append(FolhaLote(D.folha_de_comprovantes(rng, it), [(i, 1) for i in idxs]))
            continue
        if it.tipo == T.AVISO_RECEBIMENTO and agrupar_ars:
            ar_pendentes.append((novo(it), *it.cartoes))
            if len(ar_pendentes) >= rng.choice([2, 4, 6]):
                descarregar_ars()
            continue
        descarregar_ars()
        idx = novo(it)
        nativo = rng.random() < cfg.p_pdf_nativo and pode_ser_nativo(it)
        if nativo:
            it.formato = "pdf_nativo"
        if it.meia_pagina:
            folhas.append(FolhaLote(it.paginas[0], [(idx, 1)], nativo=True) if nativo
                          else FolhaLote(D.folha_de_comprovantes(rng, [it]), [(idx, 1)]))
            continue
        pags = [FolhaLote(p, [(idx, k + 1)], nativo=nativo) for k, p in enumerate(it.paginas)]
        if len(pags) >= 2 and rng.random() < cfg.fora_de_ordem:  # uma página trocada de lugar
            i = rng.randrange(len(pags) - 1)
            pags[i], pags[i + 1] = pags[i + 1], pags[i]
            it.fora_de_ordem = True
        folhas.extend(pags)
    descarregar_ars()

    # intercalar: um documento de 1 página entra no meio de um documento multipágina
    if rng.random() < cfg.intercalar:
        multi = [i for i, d in enumerate(docs, 1) if len({p for f in folhas for (di, p) in f.docs if di == i}) >= 2]
        simples = [f for f in folhas if len(f.docs) == 1 and sum(1 for g in folhas if g.docs[0][0] == f.docs[0][0]) == 1]
        if multi and simples:
            alvo = rng.choice(multi)
            intruso = rng.choice([s for s in simples if s.docs[0][0] != alvo])
            folhas.remove(intruso)
            pos = [k for k, f in enumerate(folhas) if f.docs[0][0] == alvo]
            folhas.insert(pos[0] + 1, intruso)
            docs[alvo - 1].intercalado = True
    # páginas em branco no meio
    k = 0
    while k < len(folhas):
        if rng.random() < cfg.paginas_em_branco:
            branco = _branco(rng)
            folhas.insert(k + 1, FolhaLote(branco, [(novo(_doc_branco(branco)), 1)]))
            k += 1
        k += 1
    return folhas, docs


def _branco(rng) -> Image.Image:
    f = Folha(rng)
    return f.finalizar()


def _doc_branco(img):
    d = D.DocGerado(T.OUTRO, [img], None)
    d.meta = {"cpf": None, "empregado": None, "competencia": None, "empresa_cnpj": None}
    d.observacao = "página em branco"
    return d


# ------------------------------------------------------------------ lote
def montar_lote(rng: random.Random, u: Universo, cfg: Config, nome: str):
    Folha.taxa_defeito_padrao = cfg.taxa_defeito
    Folha.taxa_branco_padrao = cfg.taxa_branco
    perfil = rng.choice(PERFIS) if cfg.perfil == "sortear" else cfg.perfil
    emp = rng.choice(u.empresas)
    comp = rng.choice(u.competencias)
    alvo = rng.randint(*cfg.paginas)
    sub = perfil if perfil != "misto" else None
    itens = []
    while sum(len(i[0].paginas) if isinstance(i, list) else len(i.paginas) for i in itens) < alvo:
        p = sub or rng.choice(PERFIS[:-1])
        if p == "admissao":
            itens += _docs_admissao(rng, u, emp, comp, cfg, alvo if sub else 12)
        elif p == "mensal":
            itens += _docs_mensal(rng, u, emp, comp, cfg, alvo)
        elif p == "desligamento":
            itens += _docs_desligamento(rng, u, emp, comp, cfg)
        elif p == "ocorrencias":
            itens += _docs_ocorrencias(rng, u, emp, comp, cfg)
        else:
            itens += _docs_recebimento_ar(rng, u, emp, comp, cfg, alvo)
    if rng.random() < 0.4:
        capa = D.outro(rng, u, emp, comp)
        itens.insert(0, _meta(capa, None, comp, emp.cnpj))
    if rng.random() < cfg.embaralhar:
        rng.shuffle(itens)

    folhas, docs = _folhas(rng, itens, cfg)
    nivel = rng.choice(["leve", "media", "forte"]) if cfg.degradacao == "misto" else cfg.degradacao
    data_receb = fmt_data((date.fromisoformat(u.data_referencia) - timedelta(days=rng.randint(0, 5))).isoformat())
    paginas, linhas, info_paginas = [], [], []
    for n, fl in enumerate(folhas, 1):
        if fl.nativo:  # PDF nativo: vai como vetor, sem extras, sem scanner, sem rotação
            if not fl.img.info.get("ficticio"):
                fl.img.info["folha"].finalizar()
            feitos, cap = [], {"captura": "pdf_nativo", "rotacao": 0}
            paginas.append(("nativo", fl.img))
        else:
            img = fl.img.copy()
            assert fl.img.info.get("ficticio"), "página sem marca de amostra"
            feitos = extras.aplicar(img, rng, cfg.extras, data_receb)
            img, cap = capturar(img, rng, nivel, cfg.p_celular, cfg.p_cabeca_para_baixo)
            paginas.append(("imagem", img))
        idx0, pag0 = fl.docs[0]
        linhas.append([nome, n, docs[idx0 - 1].tipo.value, ";".join(str(i) for i, _ in fl.docs),
                       ";".join(str(p) for _, p in fl.docs), int(pag0 == 1), int(len({i for i, _ in fl.docs}) > 1),
                       cap["rotacao"], cap["captura"]])
        info_paginas.append({"pagina": n, "documentos": [{"indice": i, "pagina_do_documento": p} for i, p in fl.docs],
                             "formato": "pdf_nativo" if fl.nativo else "imagem", "texto_selecionavel": fl.nativo,
                             **cap, "extras": feitos})

    paginas_por_doc: dict[int, dict[int, int]] = {}
    for n, fl in enumerate(folhas, 1):
        for i, p in fl.docs:
            paginas_por_doc.setdefault(i, {})[p] = n
    docs_json = []
    for i, d in enumerate(docs, 1):
        problemas = conferir(d)
        if problemas:
            raise AssertionError(f"{nome} doc {i} {d.tipo.value}: gabarito diverge do desenho: {problemas}")
        logicas = list(dict.fromkeys(paginas_por_doc[i][k] for k in sorted(paginas_por_doc[i])))  # frente e verso na mesma folha = 1 página
        docs_json.append({
            "indice": i, "tipo": d.tipo.value, "paginas": logicas,
            "paginas_contiguas": logicas == list(range(logicas[0], logicas[0] + len(logicas))),
            "formato": getattr(d, "formato", "digitalizado"),
            "fora_de_ordem": getattr(d, "fora_de_ordem", False), "intercalado": getattr(d, "intercalado", False),
            **{k: v for k, v in getattr(d, "meta", {}).items()},
            "dados": d.dados.model_dump(mode="json") if d.dados else None,
            "nao_conformidades": [{**nc, "campo": NCS[d.tipo][nc["regra"]]} for nc in d.nao_conformidades],
            "defeitos_escrita": d.defeitos, "observacao": getattr(d, "observacao", None),
        })
    lote_json = {"arquivo": nome, "perfil": perfil, "empresa_cnpj": emp.cnpj, "competencia": comp, "degradacao": nivel,
                 "total_paginas": len(paginas), "total_documentos": len(docs),
                 "paginas_pdf_nativo": sum(1 for t, _ in paginas if t == "nativo"),
                 "paginas": info_paginas, "documentos": docs_json}
    return paginas, linhas, lote_json


def gerar(cfg: Config, saida: Path, universo: Universo | None = None) -> dict:
    rng = random.Random(cfg.seed)
    u = universo or gerar_universo(cfg.seed)
    (saida / "lotes").mkdir(parents=True, exist_ok=True)
    (saida / "gabarito").mkdir(exist_ok=True)
    gabarito, lotes = [], []
    tipos, ncs, perfis = Counter(), Counter(), Counter()
    nativas = 0
    for i in range(1, cfg.qtd_lotes + 1):
        nome = f"lote_{i:04d}.pdf"
        paginas, linhas, lj = montar_lote(rng, u, cfg, nome)
        # páginas digitalizadas (imagem) e de PDF nativo (vetor) no MESMO arquivo, na ordem do lote
        escrever_pdf(saida / "lotes" / nome, paginas, f"{nome} - AMOSTRA - documentos ficticios")
        if cfg.salvar_png:
            d = saida / "png" / nome[:-4]
            d.mkdir(parents=True, exist_ok=True)
            for n, (_, p) in enumerate(paginas, 1):
                p.convert("RGB").save(d / f"pagina_{n:03d}.png")
        (saida / "gabarito" / f"{nome[:-4]}.json").write_text(json.dumps(lj, ensure_ascii=False, indent=2), encoding="utf-8")
        gabarito += linhas
        tipos.update(d["tipo"] for d in lj["documentos"])
        ncs.update(nc["regra"] for d in lj["documentos"] for nc in d["nao_conformidades"])
        perfis[lj["perfil"]] += 1
        nativas += lj["paginas_pdf_nativo"]
        lotes.append({"arquivo": nome, "perfil": lj["perfil"], "paginas": lj["total_paginas"], "documentos": lj["total_documentos"]})
        print(f"{nome}: {lj['perfil']:15s} {lj['total_paginas']:3d} páginas ({lj['paginas_pdf_nativo']} em PDF nativo), "
              f"{lj['total_documentos']:3d} documentos")
    with (saida / "gabarito.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "pagina", "tipo", "documento", "pagina_do_documento", "inicia_documento",
                    "multiplos_documentos", "rotacao", "captura"])
        w.writerows(gabarito)
    (saida / "universo.json").write_text(json.dumps(u.para_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    manifesto = {"versao_gerador": VERSAO, "seed": cfg.seed, "config": {**cfg.__dict__, "paginas": list(cfg.paginas)},
                 "lotes": lotes, "perfis": dict(perfis), "paginas_pdf_nativo": nativas, "documentos_por_tipo": dict(tipos), "nao_conformidades": dict(ncs),
                 "aviso": "Todos os dados são fictícios; todas as páginas levam a marca 'AMOSTRA – DOCUMENTO FICTÍCIO'."}
    (saida / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto
