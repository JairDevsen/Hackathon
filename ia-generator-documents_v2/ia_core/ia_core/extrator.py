"""Chamadas ao Gemini: classificação por janelas de páginas, agrupamento e extração estruturada.

Configuração por variáveis de ambiente (lidas pelo próprio SDK google-genai):
  Protótipo (AI Studio):  GEMINI_API_KEY=...
  Produção (Vertex AI):   GOOGLE_GENAI_USE_VERTEXAI=true  GOOGLE_CLOUD_PROJECT=...  GOOGLE_CLOUD_LOCATION=...
Opcionais: GEMINI_MODELO (padrão gemini-2.5-flash), GEMINI_MODELO_FALLBACK (padrão gemini-2.5-pro),
           GEMINI_CONCORRENCIA (padrão 4).

Contratos com o squad:
  - Dev 3 (fatiador) entrega list[Pagina] com a imagem de cada página.
  - Dev 5 (resiliência) persiste cada ResultadoJanela/ResultadoExtracao; as funções são idempotentes
    por janela/documento, então o /retry só precisa chamar de novo o que falhou.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass, field

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from . import prompts
from .schemas import (
    MODELOS_EXTRACAO,
    ResultadoClassificacao,
    RotuloPagina,
    TipoDocumento,
)

log = logging.getLogger("ia_core")

MODELO = os.getenv("GEMINI_MODELO", "gemini-2.5-flash")
MODELO_FALLBACK = os.getenv("GEMINI_MODELO_FALLBACK", "gemini-2.5-pro")
LIMIAR_CONFIANCA = 0.75
TAMANHO_JANELA = 8  # páginas por chamada de classificação


@dataclass
class Pagina:
    numero: int  # 1-based, número da página no lote
    conteudo: bytes
    mime_type: str = "image/png"


@dataclass
class Uso:
    tokens_entrada: int = 0
    tokens_saida: int = 0

    def somar(self, resp: types.GenerateContentResponse) -> None:
        meta = resp.usage_metadata
        if meta:
            self.tokens_entrada += meta.prompt_token_count or 0
            self.tokens_saida += meta.candidates_token_count or 0


@dataclass
class DocumentoDetectado:
    indice: int
    tipo: TipoDocumento
    paginas: list[int]
    confianca: float
    motivos_revisao: list[str] = field(default_factory=list)

    @property
    def revisar(self) -> bool:
        return bool(self.motivos_revisao)


@dataclass
class ResultadoExtracao:
    documento: DocumentoDetectado
    dados: BaseModel | None
    modelo_usado: str
    erro: str | None = None


class IACore:
    def __init__(self, client: genai.Client | None = None, concorrencia: int | None = None):
        self.client = client or genai.Client()
        self._sem = asyncio.Semaphore(concorrencia or int(os.getenv("GEMINI_CONCORRENCIA", "4")))
        self.uso = Uso()

    # ------------------------------------------------------------------ util
    async def _gerar(self, modelo: str, partes: list, sistema: str, schema: type[BaseModel]):
        config = types.GenerateContentConfig(
            system_instruction=sistema,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
        )
        for tentativa in range(5):
            try:
                async with self._sem:
                    resp = await self.client.aio.models.generate_content(
                        model=modelo, contents=partes, config=config
                    )
                self.uso.somar(resp)
                dados = resp.parsed if isinstance(resp.parsed, schema) else schema.model_validate_json(resp.text)
                return dados
            except errors.APIError as e:
                # 429 (cota) e 5xx são transitórios; o resto sobe.
                if e.code not in (429, 500, 502, 503, 504) or tentativa == 4:
                    raise
                espera = 2**tentativa + random.random()
                log.warning("Gemini %s, tentativa %d, aguardando %.1fs", e.code, tentativa + 1, espera)
                await asyncio.sleep(espera)

    @staticmethod
    def _partes(paginas: list[Pagina]) -> list:
        partes: list = []
        for p in paginas:
            partes.append(f"PÁGINA {p.numero}")
            partes.append(types.Part.from_bytes(data=p.conteudo, mime_type=p.mime_type))
        return partes

    # --------------------------------------------------------- etapa 1
    def janelas(self, paginas: list[Pagina]) -> list[tuple[Pagina | None, list[Pagina]]]:
        """Divide o lote em janelas; cada janela leva a última página da anterior como contexto."""
        res = []
        for i in range(0, len(paginas), TAMANHO_JANELA):
            contexto = paginas[i - 1] if i > 0 else None
            res.append((contexto, paginas[i : i + TAMANHO_JANELA]))
        return res

    async def classificar_janela(self, contexto: Pagina | None, alvo: list[Pagina]) -> list[RotuloPagina]:
        enviadas = ([contexto] if contexto else []) + alvo
        pedidas = [p.numero for p in alvo]
        partes = self._partes(enviadas) + [
            prompts.prompt_classificacao(pedidas, contexto.numero if contexto else None)
        ]
        res: ResultadoClassificacao = await self._gerar(
            MODELO, partes, prompts.SISTEMA_CLASSIFICACAO, ResultadoClassificacao
        )
        rotulos = {r.pagina: r for r in res.paginas if r.pagina in pedidas}
        faltando = [n for n in pedidas if n not in rotulos]
        if faltando:  # o modelo pulou páginas: marca para revisão em vez de falhar o lote
            log.warning("Páginas sem rótulo: %s", faltando)
            for n in faltando:
                rotulos[n] = RotuloPagina(
                    pagina=n, tipo=TipoDocumento.OUTRO, inicia_documento=True, multiplos_documentos=False,
                    legivel=False, confianca=0.0, justificativa="sem resposta do modelo",
                )
        return [rotulos[n] for n in pedidas]

    async def classificar_lote(self, paginas: list[Pagina]) -> list[RotuloPagina]:
        tarefas = [self.classificar_janela(c, a) for c, a in self.janelas(paginas)]
        resultados = await asyncio.gather(*tarefas)
        return [r for janela in resultados for r in janela]

    # --------------------------------------------------------- agrupamento
    @staticmethod
    def agrupar(rotulos: list[RotuloPagina]) -> list[DocumentoDetectado]:
        """Regra determinística: novo documento quando o modelo indica início ou o tipo muda."""
        docs: list[DocumentoDetectado] = []
        for r in sorted(rotulos, key=lambda x: x.pagina):
            novo = not docs or r.inicia_documento or r.tipo != docs[-1].tipo
            if novo:
                docs.append(DocumentoDetectado(len(docs) + 1, r.tipo, [r.pagina], r.confianca))
            else:
                docs[-1].paginas.append(r.pagina)
                docs[-1].confianca = min(docs[-1].confianca, r.confianca)
            d = docs[-1]
            if r.confianca < LIMIAR_CONFIANCA:
                d.motivos_revisao.append(f"pág {r.pagina}: confiança {r.confianca:.2f}")
            if r.multiplos_documentos:
                d.motivos_revisao.append(f"pág {r.pagina}: múltiplos documentos na imagem")
            if not r.legivel:
                d.motivos_revisao.append(f"pág {r.pagina}: ilegível")
        for d in docs:
            if d.tipo == TipoDocumento.OUTRO:
                d.motivos_revisao.append("tipo não reconhecido")
        return docs

    # --------------------------------------------------------- etapa 2
    async def extrair(self, doc: DocumentoDetectado, paginas: dict[int, Pagina]) -> ResultadoExtracao:
        schema = MODELOS_EXTRACAO.get(doc.tipo)
        if schema is None:
            return ResultadoExtracao(doc, None, "-", "tipo sem extração")
        partes = self._partes([paginas[n] for n in doc.paginas]) + [prompts.prompt_extracao(doc.tipo)]
        modelo = MODELO_FALLBACK if doc.revisar else MODELO  # páginas difíceis vão direto pro modelo maior
        try:
            dados = await self._gerar(modelo, partes, prompts.SISTEMA_EXTRACAO, schema)
            return ResultadoExtracao(doc, dados, modelo)
        except Exception as e:  # noqa: BLE001 - registra e deixa o /retry decidir
            log.exception("Falha extraindo documento %s", doc.indice)
            return ResultadoExtracao(doc, None, modelo, f"{type(e).__name__}: {e}")

    async def processar_lote(self, paginas: list[Pagina]) -> tuple[list[DocumentoDetectado], list[ResultadoExtracao]]:
        """Fluxo completo. Na API, prefira chamar as etapas separadas e persistir entre elas."""
        rotulos = await self.classificar_lote(paginas)
        docs = self.agrupar(rotulos)
        por_numero = {p.numero: p for p in paginas}
        extracoes = await asyncio.gather(*(self.extrair(d, por_numero) for d in docs))
        return docs, list(extracoes)
