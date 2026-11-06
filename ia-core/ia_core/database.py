"""
Módulo de Persistência e Resiliência (Retomada após Falha)
Responsável na Equipe: Lennarth (Dev 5 - Squad 2)
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

DB_PATH = Path(__file__).resolve().parent / "storage" / "factory_state.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            status TEXT NOT NULL,
            total_pages INTEGER NOT NULL,
            completed_pages INTEGER NOT NULL DEFAULT 0,
            failed_page INTEGER,
            failure_reason TEXT,
            engine_mode TEXT NOT NULL DEFAULT 'GEMINI_MULTIMODAL',
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS job_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            status TEXT NOT NULL,
            image_path TEXT NOT NULL,
            redacted_image_path TEXT NOT NULL,
            raw_page_analysis_json TEXT,
            processed_at TEXT,
            error_message TEXT,
            UNIQUE(job_id, page_number)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            doc_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def create_job(job_id: str, filename: str, total_pages: int, engine_mode: str, pages_info: List[Dict[str, Any]]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cur.execute(
        """
        INSERT INTO jobs (job_id, filename, status, total_pages, completed_pages, engine_mode, created_at)
        VALUES (?, ?, ?, ?, 0, ?, ?)
        """,
        (job_id, filename, "PROCESSING", total_pages, engine_mode, now),
    )
    for p in pages_info:
        cur.execute(
            """
            INSERT INTO job_pages (job_id, page_number, status, image_path, redacted_image_path)
            VALUES (?, ?, 'PENDING', ?, ?)
            """,
            (job_id, p["page_number"], p["image_path"], p["redacted_image_path"]),
        )
    conn.commit()
    conn.close()


def update_page_status(
    job_id: str,
    page_number: int,
    status: str,
    analysis_dict: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%H:%M:%S") if status == "COMPLETED" else None
    analysis_json = json.dumps(analysis_dict, ensure_ascii=False) if analysis_dict else None
    cur.execute(
        """
        UPDATE job_pages
        SET status = ?,
            raw_page_analysis_json = COALESCE(?, raw_page_analysis_json),
            processed_at = COALESCE(?, processed_at),
            error_message = ?
        WHERE job_id = ? AND page_number = ?
        """,
        (status, analysis_json, now, error_message, job_id, page_number),
    )
    cur.execute(
        "SELECT COUNT(*) as cnt FROM job_pages WHERE job_id = ? AND status = 'COMPLETED'",
        (job_id,),
    )
    completed_cnt = cur.fetchone()["cnt"]
    cur.execute(
        "UPDATE jobs SET completed_pages = ? WHERE job_id = ?",
        (completed_cnt, job_id),
    )
    conn.commit()
    conn.close()


def mark_job_failed(job_id: str, failed_page: int, reason: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE jobs
        SET status = 'INTERRUPTED_FAILURE',
            failed_page = ?,
            failure_reason = ?
        WHERE job_id = ?
        """,
        (failed_page, reason, job_id),
    )
    conn.commit()
    conn.close()


def save_job_documents(job_id: str, documents: List[Dict[str, Any]], final_status: str = "COMPLETED") -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM documents WHERE job_id = ?", (job_id,))
    for doc in documents:
        cur.execute(
            "INSERT INTO documents (doc_id, job_id, doc_json) VALUES (?, ?, ?)",
            (doc["id"], job_id, json.dumps(doc, ensure_ascii=False)),
        )
    cur.execute(
        """
        UPDATE jobs
        SET status = ?, failed_page = NULL, failure_reason = NULL
        WHERE job_id = ?
        """,
        (final_status, job_id),
    )
    conn.commit()
    conn.close()


def update_single_document(doc_id: str, updated_doc: Dict[str, Any]) -> Optional[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT job_id FROM documents WHERE doc_id = ?", (doc_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    job_id = row["job_id"]
    cur.execute(
        "UPDATE documents SET doc_json = ? WHERE doc_id = ?",
        (json.dumps(updated_doc, ensure_ascii=False), doc_id),
    )
    conn.commit()
    conn.close()
    return job_id


def get_job_full(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    job_row = cur.fetchone()
    if not job_row:
        conn.close()
        return None

    cur.execute("SELECT * FROM job_pages WHERE job_id = ? ORDER BY page_number ASC", (job_id,))
    page_rows = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT doc_json FROM documents WHERE job_id = ?", (job_id,))
    docs = [json.loads(r["doc_json"]) for r in cur.fetchall()]
    conn.close()

    job_dict = dict(job_row)
    job_dict["pages"] = page_rows
    job_dict["documents"] = docs
    return job_dict


def list_all_jobs() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT job_id FROM jobs ORDER BY rowid DESC")
    ids = [r["job_id"] for r in cur.fetchall()]
    conn.close()
    return [get_job_full(jid) for jid in ids if jid]
