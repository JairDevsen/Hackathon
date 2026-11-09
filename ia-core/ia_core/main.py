"""IA Core — serviço FastAPI: fatia lotes, separa/classifica/extrai por página (multimodal) e devolve por callback assinado."""
import hashlib
import re
import hmac
import io
import logging
import os
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.background import BackgroundTask

from . import agrupar, callback, catalogo, fatiar, render, schemas
from .impressao import impressao_motor
from .providers import Pedido, obter_provider

log = logging.getLogger("ia_core")
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Citadel IA · IA Core", version="1.0.0")
POOL = ThreadPoolExecutor(max_workers=int(os.environ.get("IA_WORKERS", "4")))
# Chamadas aos modelos (rede): um único limite para o serviço todo, compartilhado por todos os lotes, para não estourar a cota do provedor
LLM_CONCORRENCIA = max(1, int(os.environ.get("IA_LLM_CONCURRENCY", "4")))
LLM_POOL = ThreadPoolExecutor(max_workers=LLM_CONCORRENCIA)
PROVIDER = obter_provider()
MOTOR = impressao_motor(PROVIDER)
DELAY_MS = int(os.environ.get("IA_PAGE_DELAY_MS", "0"))


def auth(x_iacore_key: Optional[str] = Header(None)):
    esperada = os.environ.get("IA_CORE_API_KEY", "dev-ia-core-key")
    # comparação em tempo constante (evita descobrir a chave por diferença de tempo de resposta)
    if not x_iacore_key or not hmac.compare_digest(x_iacore_key.encode(), esperada.encode()):
        raise HTTPException(401, "chave do IA Core inválida")


class SliceIn(BaseModel):
    arquivo_url: str
    filename: str


class PaginaIn(BaseModel):
    numero: int
    image_url: str
    texto_embutido: str = ""


class TipoExtra(BaseModel):
    """Tipo documental descoberto pela IA em lotes anteriores e já guardado no catálogo do backend: o IA Core o reaprende (pistas locais)."""
    codigo: str
    nome: str
    escopo: str = "FUNCIONARIO"
    categoria: str = "OUTROS"
    pistas: List[str] = []


class JobIn(BaseModel):
    batch_id: str
    versao: int
    callback_url: str
    tipo_lote: str = "MISTO"
    paginas: List[PaginaIn]
    analises_previas: Dict[str, dict] = {}
    tipos_extras: List[TipoExtra] = []
    simular_falha_na_pagina: int = 0
    limiar_confianca: float = 0.75


class RenderPagina(BaseModel):
    image_url: str
    texto: str = ""
    palavras: Optional[list] = None
    caixas: Optional[list] = None
    texto_nativo: bool = False  # a página tem camada de texto do PDF (palavras exatas, sem OCR)


class RenderIn(BaseModel):
    modo: str
    titulo: str = ""
    paginas: List[RenderPagina]
    termos: Optional[List[str]] = None  # nomes já conhecidos (ex.: do funcionário) a tarjar na cópia anonimizada


@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER.nome, "tipos": len(catalogo.TIPOS), "motor": MOTOR}


@app.get("/schemas/{tipo}", dependencies=[Depends(auth)])
def schema(tipo: str):
    if tipo not in catalogo.TIPOS and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,39}", tipo):
        raise HTTPException(404, "tipo desconhecido")
    return schemas.schema_do_tipo(tipo)  # tipo descoberto pela IA (ainda não carregado neste processo) usa os campos comuns


@app.get("/tipos", dependencies=[Depends(auth)])
def tipos():
    return [{"codigo": k, "nome": v["nome"], "origem": v.get("origem", "CATALOGO")} for k, v in list(catalogo.TIPOS.items())]


@app.post("/slice", dependencies=[Depends(auth)])
def slice_(body: SliceIn):
    """Baixa o original (URL assinada, em streaming para disco), fatia página a página e devolve um ZIP."""
    ext = os.path.splitext(body.filename.lower())[1] or ".bin"
    src = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        with httpx.stream("GET", body.arquivo_url, timeout=600) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes(1 << 20):
                src.write(chunk)
        src.close()
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        out.close()
        try:
            n = fatiar.fatiar(src.name, body.filename, out.name)
        except Exception as e:
            os.unlink(out.name)
            raise HTTPException(422, f"não foi possível fatiar o arquivo: {e}")
        log.info("fatiado %s: %d páginas", body.filename, n)
        return FileResponse(out.name, media_type="application/zip", background=BackgroundTask(os.unlink, out.name))
    finally:
        try:
            os.unlink(src.name)
        except OSError:
            pass


def _baixar(url: str) -> bytes:
    r = httpx.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def _processar(job: JobIn):
    """Analisa as páginas pendentes, com checkpoint por callback.

    Cada página passa por duas etapas: a LOCAL (texto/OCR, regras e decisão da camada; sequencial, a página anterior é contexto) e,
    quando a camada local não resolve, a chamada ao modelo (rede), que roda em paralelo com as demais páginas. Os callbacks saem
    sempre em ordem de página, então o checkpoint continua contíguo: se uma página falha, as anteriores já estão salvas."""
    cb = job.callback_url
    base = {"batch_id": job.batch_id, "versao": job.versao}
    for t in job.tipos_extras:  # tipos que a IA descobriu antes: as pistas aprendidas passam a valer na Camada 1 deste lote
        catalogo.registrar_tipo(t.codigo, t.nome, [catalogo.norm(p) for p in t.pistas], t.escopo, t.categoria)
    analises: Dict[int, dict] = {int(k): v for k, v in job.analises_previas.items()}
    provisorias: Dict[int, dict] = {}  # página ainda esperando o modelo: o tipo que as regras locais deram serve de contexto à seguinte
    fila: "deque" = deque()  # (numero, sha, Future | Pagina)
    janela = 2 * LLM_CONCORRENCIA
    todas = sorted([(p.numero, p) for p in job.paginas] + [(n, None) for n in analises], key=lambda x: x[0])
    em_duas_etapas = hasattr(PROVIDER, "preparar")

    def falhar(numero: int, erro: Exception) -> None:
        log.error("falha na página %d: %s", numero, erro)
        for _, _, f in fila:
            if isinstance(f, Future):
                f.cancel()
        callback.enviar(cb, {**base, "evento": "pagina", "numero": numero, "status": "FALHOU", "erro": str(erro)[:500]}, f"{job.batch_id}:{job.versao}:pagina:{numero}:falha")
        callback.enviar(cb, {**base, "evento": "falhou", "erro": f"página {numero}: {str(erro)[:300]}", "paginas_falhas": [numero]}, f"{job.batch_id}:{job.versao}:falhou")

    def despachar(bloquear: bool) -> bool:
        """Envia o callback das páginas prontas na frente da fila (todas, se `bloquear`; senão só enquanto a fila passa da janela)."""
        while fila and (isinstance(fila[0][2], dict) or fila[0][2].done() or bloquear or len(fila) > janela):
            numero, sha, r = fila.popleft()
            try:
                a = dict(r.result() if isinstance(r, Future) else r)
            except Exception as e:  # noqa: BLE001
                fila.appendleft((numero, sha, r))
                falhar(numero, e)
                return False
            a["sha256"] = sha
            a["motor"] = MOTOR  # a Camada 0 só reaproveita análises feitas por este mesmo motor
            analises[numero] = a
            provisorias.pop(numero, None)
            callback.enviar(cb, {**base, "evento": "pagina", "numero": numero, "status": "OK", "analise": a}, f"{job.batch_id}:{job.versao}:pagina:{numero}")
        return True

    anterior = None
    for numero, p in todas:
        if p is None:
            anterior = analises[numero]
            continue
        if job.simular_falha_na_pagina and numero == job.simular_falha_na_pagina:
            if despachar(True):
                callback.enviar(cb, {**base, "evento": "falhou", "erro": f"queda simulada na página {numero} (demonstração de retomada)"}, f"{job.batch_id}:{job.versao}:falhou")
            return
        try:
            if DELAY_MS:  # gancho de teste de caos: deixa o lote lento o bastante para derrubar processos no meio
                time.sleep(DELAY_MS / 1000)
            img = _baixar(p.image_url)
            sha = hashlib.sha256(img).hexdigest()
            r = PROVIDER.preparar(img, numero, anterior, p.texto_embutido, job.tipo_lote) if em_duas_etapas else PROVIDER.analisar(img, numero, anterior, p.texto_embutido, job.tipo_lote)
        except Exception as e:  # noqa: BLE001
            if despachar(True):  # o que veio antes da página com problema fica salvo
                falhar(numero, e)
            return
        if isinstance(r, Pedido):  # a chamada ao modelo segue em paralelo; a etapa local da próxima página não espera por ela
            fila.append((numero, sha, LLM_POOL.submit(PROVIDER.executar, r)))
            anterior = provisorias[numero] = {"tipo": r.tipo_local}
        else:
            fila.append((numero, sha, r))
            anterior = r
        if not despachar(False):
            return
    if not despachar(True):
        return
    docs = agrupar.agrupar(analises)
    callback.enviar(cb, {**base, "evento": "concluido", "documentos": docs}, f"{job.batch_id}:{job.versao}:concluido")


@app.post("/jobs", status_code=202, dependencies=[Depends(auth)])
def criar_job(job: JobIn):
    POOL.submit(_processar, job)
    return {"job_id": f"{job.batch_id}:{job.versao}", "paginas": len(job.paginas)}


@app.post("/retry", status_code=202, dependencies=[Depends(auth)])
def retry(job: JobIn):
    """Reprocessa só as páginas pendentes; as concluídas chegam em `analises_previas` (checkpoint) e não são refeitas."""
    return criar_job(job)


@app.post("/render", dependencies=[Depends(auth)])
def render_pdf(body: RenderIn):
    if body.modo not in ("original", "pesquisavel", "anonimizado"):
        raise HTTPException(400, "modo inválido")
    paginas = []
    for p in body.paginas:
        paginas.append({"imagem": _baixar(p.image_url), "texto": p.texto, "palavras": p.palavras, "caixas": p.caixas, "texto_nativo": p.texto_nativo})
    try:
        pdf = render.gerar_pdf(body.modo, body.titulo, paginas, body.termos)
    except render.RenderErro as e:
        raise HTTPException(422, str(e))
    return Response(pdf, media_type="application/pdf")


class AnonimizarIn(BaseModel):
    texto: str


@app.post("/anonimizar", dependencies=[Depends(auth)])
def anonimizar(body: AnonimizarIn):
    """Texto sem dados pessoais (mesma regra da análise). Usado quando a API refaz o texto de um documento dividido/juntado."""
    from .anonimizacao import anonimizar_texto
    return {"texto_anonimizado": anonimizar_texto(body.texto)[0]}


@app.get("/diagnostico", dependencies=[Depends(auth)])
def diagnostico():
    """Chamada mínima (sem documento) a cada modelo configurado: confere chave, nomes de modelo e disponibilidade."""
    if hasattr(PROVIDER, "diagnosticar"):
        return {"provider": PROVIDER.nome, "modelos": PROVIDER.diagnosticar()}
    return {"provider": PROVIDER.nome, "modelos": [], "aviso": "motor local: não há modelo externo configurado"}


@app.post("/qualidade", dependencies=[Depends(auth)])
def qualidade():
    from .qualidade import executar

    return executar(PROVIDER)
