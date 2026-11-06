"""Conferência do gabarito: cada valor do gabarito precisa ter sido de fato desenhado na página,
e os campos obrigatórios de cada tipo não podem estar vazios (exceto quando o vazio é intencional)."""
from __future__ import annotations

import functools
import re
import unicodedata

from ._ia_core import sch
from .canvas import brl, registrar
from .universo import MESES, nome_mes

T = sch.TipoDocumento

# Campos categóricos (códigos/enum) ou derivados: não aparecem literalmente na página
NAO_LITERAIS = {
    "situacao", "tipo_exame", "forma_registro", "motivo_devolucao", "assunto", "tipo_pagamento", "tipo_ocorrencia",
    "medida", "forma", "ciencia", "tipo_anotacao", "opcao", "beneficio", "subtipo", "tipo", "modalidade", "entregue",
    "cid_informado", "houve_afastamento", "cumprira_aviso_previo", "foto_presente", "marcado", "rubricas_em_todas_paginas",
    "quantidade_testemunhas", "campos_ilegiveis", "observacoes", "autenticacao_bancaria_presente",
}
# Por tipo: caminhos que não são impressos literalmente
NAO_LITERAIS_TIPO = {
    T.CARTAO_PONTO: {"registros.data"},  # a folha manual mostra só o dia
}
# Campos que podem ser nulos por regra de negócio (além dos deixados em branco de propósito)
PODEM_SER_NULOS = {
    "*": {"observacoes", "campos_ilegiveis"},
    T.HOLERITE: {"itens.codigo", "itens.provento", "itens.desconto", "itens.referencia"},
    T.CARTAO_PONTO: {"empregado_cpf", "registros.ocorrencia"},
    T.GUIA_FGTS: {"data_pagamento", "anotacao_manuscrita"},
    T.CRF_FGTS: {"codigo_controle"}, T.CNDT: {"codigo_controle"}, T.CND_FEDERAL: {"numero_certidao"},
    T.TRCT: {"data_aviso_previo"},
    T.ASO: {"medico_crm"},
    T.FICHA_EPI: {"entregas.numero_ca"},
    T.AVISO_RECEBIMENTO: {"motivo_devolucao", "data_entrega", "data_devolucao", "recebedor_nome", "recebedor_documento"},
    T.DARF: {"anotacao_manuscrita"},
    T.PEDIDO_DEMISSAO: {"empregador_cnpj", "cumprira_aviso_previo"},
    T.DECLARACAO_MANUSCRITA: {"endereco"},
    T.JUSTIFICATIVA_FALTA: {"empregado_cpf"},
    T.ADVERTENCIA_SUSPENSAO: {"empregado_cpf", "empregador_cnpj", "dias_suspensao"},
    T.CTPS_ANOTACAO: {"cargo", "salario", "ferias_inicio", "ferias_fim"},
    T.RECIBO_BENEFICIO: {"empregado_cpf"},
    T.FERIAS: {"empregador_cnpj", "empregado_cpf", "valor_liquido"},
    T.CHECKLIST_INTEGRACAO: {"empregado_cpf"},
    T.OCORRENCIA_ACIDENTE: {"empregado_cpf", "data_documento"},
    T.CONTRATO_TRABALHO: {"prazo_dias"},
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def _candidatos(campo: str, v) -> list[str]:
    if isinstance(v, float):
        c = [brl(v), f"{v:.2f}", f"{v:.1f}"]
        if v.is_integer():
            c.append(str(int(v)))
        return c
    if isinstance(v, int):
        return [str(v), f"{v:02d}"]
    s = str(v)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        a, m, d = s.split("-")
        mes = MESES[int(m) - 1].lower()
        return [f"{d}{m}{a}", f"{d}{m}{a[2:]}", f"{d} de {mes} de {a}"]
    if re.fullmatch(r"\d{4}-\d{2}", s):
        a, m = s.split("-")
        return [f"{m}{a}", f"{m}{a[2:]}", nome_mes(s)]
    return [s]


def _folhas(obj, caminho=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _folhas(v, f"{caminho}.{k}" if caminho else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _folhas(v, caminho)
    else:
        yield caminho, obj


def conferir(doc) -> list[str]:
    """Lista de problemas (vazia = gabarito fiel ao que foi desenhado)."""
    if doc.dados is None:
        return []
    problemas = []
    texto = norm("".join(doc.registro))
    brancos = {d.get("campo") for d in doc.defeitos if d["defeito"] == "campo_em_branco"}
    nulos_ok = PODEM_SER_NULOS["*"] | PODEM_SER_NULOS.get(doc.tipo, set()) | brancos
    ignorar = NAO_LITERAIS_TIPO.get(doc.tipo, set())
    nomes_nc = {nc["regra"] for nc in doc.nao_conformidades}
    for caminho, v in _folhas(doc.dados.model_dump(mode="json")):
        folha = caminho.split(".")[-1]
        if v is None or v == "":
            if caminho not in nulos_ok and folha not in nulos_ok and folha not in NAO_LITERAIS and not nomes_nc:
                problemas.append(f"campo obrigatório vazio: {caminho}")
            continue
        if folha in NAO_LITERAIS or caminho in ignorar:
            continue
        if isinstance(v, bool):
            if v and folha.startswith("assinatura") and "<assinatura>" not in doc.registro:
                problemas.append(f"{caminho}=true mas nenhuma assinatura foi desenhada")
            if v and folha.startswith("carimbo") and "<carimbo>" not in doc.registro:
                problemas.append(f"{caminho}=true mas nenhum carimbo foi desenhado")
            continue
        if not any(norm(c) and norm(c) in texto for c in _candidatos(folha, v)):
            problemas.append(f"valor não desenhado: {caminho}={v!r}")
    return problemas


def registrado(fn):
    """Decorador dos renderizadores: guarda o registro do que foi desenhado e os defeitos de escrita."""
    @functools.wraps(fn)
    def w(*a, **k):
        with registrar() as reg:
            doc = fn(*a, **k)
        doc.registro = reg.itens
        doc.defeitos = [d for f in reg.folhas for d in f.defeitos]
        return doc
    return w
