"""
Suíte de Testes Fim a Fim (E2E) — Document AI Factory
Responsável na Equipe: Thaynara (Dev 6 - Squad 3)
"""
from backend.main import (
    on_startup,
    api_list_jobs,
    api_trigger_demo_preset,
    api_resume_failed_job,
    api_human_review_document,
)
from backend.schemas import RevisaoHumanaInput, TipoDocumento


def run_e2e_verification():
    print("=== INICIANDO BATERIA DE TESTES E2E - DOCUMENT AI FACTORY ===")
    on_startup()
    jobs = api_list_jobs()
    assert len(jobs) >= 1, "Falha: Lote inicial não foi criado"
    j0 = jobs[0]
    print(
        f"[OK] 1. Lote Inicial: {j0['job_id']} | "
        f"Páginas: {j0['completed_pages']}/{j0['total_pages']} | "
        f"Documentos separados: {len(j0['documents'])}"
    )
    for d in j0["documents"]:
        print(
            f"     -> {d['id']} | Tipo: {d['tipo']} | Págs Agrupadas: {d['paginas']} | "
            f"Confiança: {d['confianca']} | Manuscrito: {d['possui_manuscrito']} | "
            f"Itens LGPD Mascarados: {len(d['dados_sensiveis_lgpd'])}"
        )

    # 2. Testar Simulação de Falha na Página 4
    j_fail = api_trigger_demo_preset("simular_falha")
    assert j_fail["status"] == "INTERRUPTED_FAILURE"
    assert j_fail["failed_page"] == 4
    assert j_fail["completed_pages"] == 3
    print(
        f"[OK] 2. Simulação de Queda: {j_fail['job_id']} | "
        f"Status: {j_fail['status']} | Parou na Pág: {j_fail['failed_page']} | "
        f"Checkpoints Salvos: Págs 1 a {j_fail['completed_pages']}"
    )

    # 3. Testar Retomada após Falha (continua da página 4 até a 6)
    j_resumed = api_resume_failed_job(j_fail["job_id"])
    assert j_resumed["completed_pages"] == 6
    assert len(j_resumed["documents"]) == 4
    print(
        f"[OK] 3. Retomada após Falha Concluída: {j_resumed['job_id']} | "
        f"Páginas Concluídas: {j_resumed['completed_pages']}/{j_resumed['total_pages']} | "
        f"Documentos Finais: {len(j_resumed['documents'])}"
    )

    # 4. Testar Fila de Revisão Humana (HITL)
    hitl_docs = [d for d in j_resumed["documents"] if d["needs_review"]]
    assert len(hitl_docs) >= 1
    doc_to_review = hitl_docs[0]
    j_reviewed = api_human_review_document(
        doc_to_review["id"],
        RevisaoHumanaInput(
            tipo=TipoDocumento(doc_to_review["tipo"]),
            texto_ocr=doc_to_review["texto_ocr"] + "\n[VALIDADO MANUALMENTE PELO OPERADOR HITL]",
            revisado_por="Davi / Thaynara (Operador HITL)",
        ),
    )
    assert j_reviewed["status"] == "COMPLETED"
    print(
        f"[OK] 4. Revisão Humana (HITL) aprovada para {doc_to_review['id']}! "
        f"Status final do lote: {j_reviewed['status']}"
    )
    print("=== TODOS OS REQUISITOS E DIFERENCIAIS PASSARAM COM 100% DE SUCESSO! ===")


if __name__ == "__main__":
    run_e2e_verification()
