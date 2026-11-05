"""
API Principal FastAPI — Document AI Factory (Bernhoeft Edition)
Responsáveis na Equipe: Luis Miguel (API/Ingestão) & Lennarth (Resiliência/HITL)
"""
import os
import io
import json
import uuid
import zipfile
import fitz
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from .database import (
    init_db,
    create_job,
    get_job_full,
    list_all_jobs,
    update_single_document,
    save_job_documents,
)
from .ingestion import slice_batch_to_pages, STORAGE_ROOT
from .gemini_engine import process_or_resume_job, _build_compliance_checklist
from .sample_generator import ensure_sample_batches
from .anonymizer import anonymize_ocr_text
from .schemas import RevisaoHumanaInput

app = FastAPI(
    title="Document AI Factory API • Bernhoeft Edition — Hack Garanhuns Tech 2026",
    description="Pipeline Multimodal para Ingestão de Lotes GRT/SST, Recorte Físico de Documentos em PDF/ZIP, Reconhecimento de AR/Manuscritos, Funil FinOps 950k, Fila HITL, Retomada após Falha e Anonimização LGPD.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_HTML_PATH = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
SAMPLE_FILES: dict = {}


@app.on_event("startup")
def on_startup():
    global SAMPLE_FILES
    init_db()
    SAMPLE_FILES = ensure_sample_batches()
    existing_jobs = list_all_jobs()
    if not existing_jobs:
        _run_preset_batch("lote_completo", simulate_failure_at_page=None)


def _run_preset_batch(preset: str, simulate_failure_at_page: Optional[int] = None, api_key: Optional[str] = None) -> dict:
    sample_path = SAMPLE_FILES.get("lote_hitl" if preset == "lote_hitl" else "lote_completo")
    if not sample_path or not sample_path.exists():
        SAMPLE_FILES.update(ensure_sample_batches())
        sample_path = SAMPLE_FILES["lote_completo"]

    file_bytes = sample_path.read_bytes()
    filename = sample_path.name
    job_id = f"lote-{uuid.uuid4().hex[:6]}"

    pages_info = slice_batch_to_pages(job_id, file_bytes, filename)
    embedded_map = {p["page_number"]: p.get("embedded_text", "") for p in pages_info}
    engine_mode = "GEMINI_3.8_FLASH_MULTIMODAL" if (api_key or os.environ.get("GEMINI_API_KEY")) else "FUNIL_HIBRIDO_BERNHOEFT_950K"

    create_job(job_id, filename, len(pages_info), engine_mode, pages_info)
    job = process_or_resume_job(
        job_id,
        embedded_texts_by_page=embedded_map,
        simulate_failure_at_page=simulate_failure_at_page,
        custom_api_key=api_key,
    )
    return _serialize_job(job)


def _serialize_job(job: dict) -> dict:
    if not job:
        return {}
    job_id = job["job_id"]
    pages_out = []
    for p in job.get("pages", []):
        pnum = p["page_number"]
        pages_out.append({
            "page_number": pnum,
            "status": p["status"],
            "processed_at": p.get("processed_at"),
            "error_message": p.get("error_message"),
            "image_url": f"/api/pages/{job_id}/{pnum}?anonymized=false",
            "redacted_image_url": f"/api/pages/{job_id}/{pnum}?anonymized=true",
        })
    return {
        "job_id": job_id,
        "filename": job["filename"],
        "status": job["status"],
        "total_pages": job["total_pages"],
        "completed_pages": job["completed_pages"],
        "failed_page": job.get("failed_page"),
        "failure_reason": job.get("failure_reason"),
        "engine_mode": job.get("engine_mode", "FUNIL_HIBRIDO_BERNHOEFT_950K"),
        "created_at": job["created_at"],
        "pages": pages_out,
        "documents": job.get("documents", []),
    }


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    if FRONTEND_HTML_PATH.exists():
        return HTMLResponse(content=FRONTEND_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Document AI Factory Backend Online. Acesse /docs</h1>")


@app.get("/api/jobs")
def api_list_jobs():
    jobs = list_all_jobs()
    return [_serialize_job(j) for j in jobs if j]


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job_full(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    return _serialize_job(job)


@app.post("/api/jobs/upload")
async def api_upload_batch(
    file: UploadFile = File(...),
    simulate_failure_at_page: Optional[int] = Form(default=None),
    api_key: Optional[str] = Form(default=None),
):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    job_id = f"lote-{uuid.uuid4().hex[:6]}"
    filename = file.filename or "lote_digitalizado.pdf"
    pages_info = slice_batch_to_pages(job_id, file_bytes, filename)
    embedded_map = {p["page_number"]: p.get("embedded_text", "") for p in pages_info}
    engine_mode = "GEMINI_3.8_FLASH_LIVE" if (api_key or os.environ.get("GEMINI_API_KEY")) else "FUNIL_HIBRIDO_BERNHOEFT_950K"

    create_job(job_id, filename, len(pages_info), engine_mode, pages_info)
    job = process_or_resume_job(
        job_id,
        embedded_texts_by_page=embedded_map,
        simulate_failure_at_page=simulate_failure_at_page,
        custom_api_key=api_key,
    )
    return _serialize_job(job)


@app.post("/api/jobs/demo/{preset}")
def api_trigger_demo_preset(
    preset: str,
    api_key: Optional[str] = Query(default=None),
):
    if preset == "simular_falha":
        return _run_preset_batch("lote_completo", simulate_failure_at_page=4, api_key=api_key)
    elif preset == "lote_hitl":
        return _run_preset_batch("lote_hitl", simulate_failure_at_page=None, api_key=api_key)
    else:
        return _run_preset_batch("lote_completo", simulate_failure_at_page=None, api_key=api_key)


@app.post("/api/jobs/{job_id}/resume")
def api_resume_failed_job(job_id: str, api_key: Optional[str] = Query(default=None)):
    job = get_job_full(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    embedded_map = {}
    sample_path = SAMPLE_FILES.get("lote_completo")
    if sample_path and sample_path.exists() and job["total_pages"] == 6:
        pdf_doc = fitz.open(str(sample_path))
        for i in range(len(pdf_doc)):
            embedded_map[i + 1] = pdf_doc.load_page(i).get_text("text") or ""
        pdf_doc.close()

    updated = process_or_resume_job(
        job_id,
        embedded_texts_by_page=embedded_map,
        simulate_failure_at_page=None,
        custom_api_key=api_key,
    )
    return _serialize_job(updated)


@app.patch("/api/documents/{doc_id}/review")
def api_human_review_document(doc_id: str, payload: RevisaoHumanaInput):
    all_jobs = list_all_jobs()
    target_job = None
    target_doc = None
    for j in all_jobs:
        for d in j.get("documents", []):
            if d["id"] == doc_id:
                target_job = j
                target_doc = d
                break
        if target_doc:
            break

    if not target_doc or not target_job:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    target_doc["tipo"] = payload.tipo.value
    target_doc["texto_ocr"] = payload.texto_ocr
    masked_text, pii_items = anonymize_ocr_text(payload.texto_ocr, page_num=target_doc["pagina_inicial"])
    target_doc["texto_ocr_anonimizado"] = masked_text
    target_doc["dados_sensiveis_lgpd"] = pii_items
    target_doc["needs_review"] = False
    target_doc["confianca"] = 1.0
    target_doc["review_status"] = "HUMAN_APPROVED"
    target_doc["status_mobilizacao"] = "LIBERADO PARA CATRACA / MOBILIZAÇÃO (APROVADO ANALISTA GRT)"
    target_doc["revisado_por"] = payload.revisado_por
    target_doc["notas_revisao"] = payload.notas_revisao
    if payload.campos_ar is not None:
        target_doc["campos_ar"] = payload.campos_ar
    target_doc["compliance_checklist"] = _build_compliance_checklist(target_doc)

    update_single_document(doc_id, target_doc)

    refreshed = get_job_full(target_job["job_id"])
    still_needs_review = any(d.get("needs_review") for d in refreshed.get("documents", []))
    save_job_documents(
        target_job["job_id"],
        refreshed["documents"],
        final_status="NEEDS_HUMAN_REVIEW" if still_needs_review else "COMPLETED",
    )
    return _serialize_job(get_job_full(target_job["job_id"]))


@app.get("/api/documents/{doc_id}/pdf")
def api_download_split_document_pdf(doc_id: str, anonymized: bool = Query(default=False)):
    """
    Baixa o arquivo PDF recortado fisicamente contendo apenas as páginas agrupadas deste documento
    (em versão Original ou com Tarjas LGPD).
    """
    all_jobs = list_all_jobs()
    for j in all_jobs:
        for d in j.get("documents", []):
            if d["id"] == doc_id:
                job_id = j["job_id"]
                fname = d.get("nome_arquivo_separado") or f"{doc_id}.pdf"
                prefix = "LGPD_" if anonymized else ""
                pdf_path = STORAGE_ROOT / "split_pdfs" / job_id / f"{prefix}{fname}"
                if pdf_path.exists():
                    return FileResponse(
                        str(pdf_path),
                        media_type="application/pdf",
                        filename=f"{prefix}{fname}",
                    )
    raise HTTPException(status_code=404, detail="PDF separado do documento não encontrado")


@app.get("/api/jobs/{job_id}/export-zip")
def api_export_job_zip(job_id: str, anonymized: bool = Query(default=False)):
    """
    Exporta um pacote ZIP contendo todos os documentos separados e renomeados em PDF
    + Manifesto JSON de Auditoria e Compliance GRT Bernhoeft.
    """
    job = get_job_full(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Lote não encontrado")

    split_dir = STORAGE_ROOT / "split_pdfs" / job_id
    prefix = "LGPD_" if anonymized else ""
    mem_zip = io.BytesIO()

    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for doc in job.get("documents", []):
            fname = doc.get("nome_arquivo_separado") or f"{doc['id']}.pdf"
            target_pdf = split_dir / f"{prefix}{fname}"
            if target_pdf.exists():
                zf.write(str(target_pdf), arcname=f"{prefix}{fname}")

        manifest = {
            "empresa": "Bernhoeft - Gestão de Riscos com Terceiros & BPO",
            "job_id": job_id,
            "lote_origem": job["filename"],
            "modo_lgpd_anonimizado": anonymized,
            "total_paginas_lote": job["total_pages"],
            "total_documentos_separados": len(job.get("documents", [])),
            "documentos": [
                {
                    "id": d["id"],
                    "arquivo_pdf_gerado": f"{prefix}{d.get('nome_arquivo_separado', '')}",
                    "tipo": d["tipo"],
                    "vertical_bernhoeft": d.get("vertical_bernhoeft"),
                    "status_mobilizacao": d.get("status_mobilizacao"),
                    "paginas_agrupadas": d["paginas"],
                    "confianca": d["confianca"],
                    "finops_telemetria": d.get("finops_telemetria"),
                    "compliance_checklist": d.get("compliance_checklist"),
                    "texto_ocr": d["texto_ocr_anonimizado"] if anonymized else d["texto_ocr"],
                }
                for d in job.get("documents", [])
            ],
        }
        zf.writestr(
            "00_MANIFESTO_AUDITORIA_BERNHOEFT.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    mem_zip.seek(0)
    zip_filename = f"Dossie_Separado_{job_id}_{'LGPD' if anonymized else 'Original'}.zip"
    return StreamingResponse(
        mem_zip,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@app.get("/api/pages/{job_id}/{page_number}")
def api_get_page_image(job_id: str, page_number: int, anonymized: bool = Query(default=False)):
    job = get_job_full(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    for p in job.get("pages", []):
        if p["page_number"] == page_number:
            target_path = Path(p["redacted_image_path"] if anonymized else p["image_path"])
            if target_path.exists():
                return FileResponse(str(target_path), media_type="image/png")
    raise HTTPException(status_code=404, detail="Imagem da página não encontrada")


@app.get("/api/samples/{sample_key}")
def api_download_sample_pdf(sample_key: str):
    path = SAMPLE_FILES.get(sample_key)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo de amostra não encontrado")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)
