"""IA Core — serviço FastAPI: fatia lotes, separa/classifica/extrai por página (multimodal) e devolve por callback assinado."""
import hashlib
import hmac
import io
import logging
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.background import BackgroundTask

from . import agrupar, callback, catalogo, fatiar, render, schemas
from .providers import obter_provider

log = logging.getLogger("ia_core")
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Citadel IA · IA Core", version="1.0.0")
POOL = ThreadPoolExecutor(max_workers=int(os.environ.get("IA_WORKERS", "4")))
PROVIDER = obter_provider()
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


class JobIn(BaseModel):
    batch_id: str
    versao: int
    callback_url: str
    tipo_lote: str = "MISTO"
    paginas: List[PaginaIn]
    analises_previas: Dict[str, dict] = {}
    simular_falha_na_pagina: int = 0
    limiar_confianca: float = 0.75


class RenderPagina(BaseModel):
    image_url: str
    texto: str = ""
    palavras: Optional[list] = None
    caixas: Optional[list] = None


class RenderIn(BaseModel):
    modo: str
    titulo: str = ""
    paginas: List[RenderPagina]


@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER.nome, "tipos": len(catalogo.CODIGOS)}


@app.get("/schemas/{tipo}", dependencies=[Depends(auth)])
def schema(tipo: str):
    if tipo not in catalogo.TIPOS:
        raise HTTPException(404, "tipo desconhecido")
    return schemas.schema_do_tipo(tipo)


@app.get("/tipos", dependencies=[Depends(auth)])
def tipos():
    return [{"codigo": k, "nome": v["nome"]} for k, v in catalogo.TIPOS.items()]


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
    """Analisa páginas pendentes em sequência (a página anterior é contexto), com checkpoint por callback."""
    cb = job.callback_url
    base = {"batch_id": job.batch_id, "versao": job.versao}
    analises: Dict[int, dict] = {int(k): v for k, v in job.analises_previas.items()}
    anterior = None
    todas = sorted([(p.numero, p) for p in job.paginas] + [(n, None) for n in analises], key=lambda x: x[0])
    for numero, p in todas:
        if p is None:
            anterior = analises[numero]
            continue
        if job.simular_falha_na_pagina and numero == job.simular_falha_na_pagina:
            callback.enviar(cb, {**base, "evento": "falhou", "erro": f"queda simulada na página {numero} (demonstração de retomada)"}, f"{job.batch_id}:{job.versao}:falhou")
            return
        try:
            if DELAY_MS:  # gancho de teste de caos: deixa o lote lento o bastante para derrubar processos no meio
                time.sleep(DELAY_MS / 1000)
            img = _baixar(p.image_url)
            a = dict(PROVIDER.analisar(img, numero, anterior, p.texto_embutido, job.tipo_lote))
            a["sha256"] = hashlib.sha256(img).hexdigest()
            analises[numero] = a
            anterior = a
            callback.enviar(cb, {**base, "evento": "pagina", "numero": numero, "status": "OK", "analise": a}, f"{job.batch_id}:{job.versao}:pagina:{numero}")
        except Exception as e:  # noqa: BLE001
            log.exception("falha na página %d", numero)
            callback.enviar(cb, {**base, "evento": "pagina", "numero": numero, "status": "FALHOU", "erro": str(e)[:500]}, f"{job.batch_id}:{job.versao}:pagina:{numero}:falha")
            callback.enviar(cb, {**base, "evento": "falhou", "erro": f"página {numero}: {str(e)[:300]}", "paginas_falhas": [numero]}, f"{job.batch_id}:{job.versao}:falhou")
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
        paginas.append({"imagem": _baixar(p.image_url), "texto": p.texto, "palavras": p.palavras, "caixas": p.caixas})
    try:
        pdf = render.gerar_pdf(body.modo, body.titulo, paginas)
    except render.RenderErro as e:
        raise HTTPException(422, str(e))
    return Response(pdf, media_type="application/pdf")


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
