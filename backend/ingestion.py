"""
Módulo de Ingestão e Fatiamento de Arquivos de Grande Porte
Responsável na Equipe: Luis Miguel (Dev 3 - Squad 2)
"""
from pathlib import Path
from typing import List, Dict, Any
import zipfile
import io
import fitz  # PyMuPDF
from PIL import Image, ImageSequence
from .anonymizer import generate_redacted_image

STORAGE_ROOT = Path(__file__).resolve().parent / "storage"


def slice_batch_to_pages(job_id: str, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Recebe um arquivo de lote (PDF multipágina, TIFF multipágina, ZIP de imagens ou imagem avulsa),
    separa cada página como PNG individual de alta nitidez e cria a versão anonimizada inicial.
    """
    job_dir = STORAGE_ROOT / "pages" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    ext = filename.lower().split(".")[-1] if "." in filename else ""
    pages_info: List[Dict[str, Any]] = []

    if ext == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for idx in range(len(doc)):
            page_num = idx + 1
            page = doc.load_page(idx)
            pix = page.get_pixmap(dpi=160)
            img_path = job_dir / f"page_{page_num}.png"
            redacted_path = job_dir / f"page_{page_num}_redacted.png"
            pix.save(str(img_path))

            embedded_text = page.get_text("text") or ""
            redaction_boxes = _infer_redaction_boxes(embedded_text, page_num)
            generate_redacted_image(img_path, redacted_path, redaction_boxes)

            pages_info.append({
                "page_number": page_num,
                "image_path": str(img_path),
                "redacted_image_path": str(redacted_path),
                "embedded_text": embedded_text.strip(),
            })
        doc.close()

    elif ext == "zip":
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            img_names = sorted([
                n for n in zf.namelist()
                if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"))
            ])
            for idx, name in enumerate(img_names):
                page_num = idx + 1
                raw_img = Image.open(io.BytesIO(zf.read(name))).convert("RGB")
                img_path = job_dir / f"page_{page_num}.png"
                redacted_path = job_dir / f"page_{page_num}_redacted.png"
                raw_img.save(img_path, format="PNG")
                generate_redacted_image(img_path, redacted_path)
                pages_info.append({
                    "page_number": page_num,
                    "image_path": str(img_path),
                    "redacted_image_path": str(redacted_path),
                    "embedded_text": "",
                })

    else:
        # Imagem única ou TIFF multipágina
        img = Image.open(io.BytesIO(file_bytes))
        for idx, frame in enumerate(ImageSequence.Iterator(img)):
            page_num = idx + 1
            rgb_frame = frame.convert("RGB")
            img_path = job_dir / f"page_{page_num}.png"
            redacted_path = job_dir / f"page_{page_num}_redacted.png"
            rgb_frame.save(img_path, format="PNG")
            generate_redacted_image(img_path, redacted_path)
            pages_info.append({
                "page_number": page_num,
                "image_path": str(img_path),
                "redacted_image_path": str(redacted_path),
                "embedded_text": "",
            })

    return pages_info


def _infer_redaction_boxes(text: str, page_num: int):
    upper = text.upper()
    if "AVISO DE RECEBIMENTO" in upper or "CORREIOS" in upper or "BR984512390BR" in upper:
        return [
            (0.06, 0.30, 0.72, 0.42, "LGPD: DESTINATARIO / ENDERECO"),
            (0.06, 0.68, 0.88, 0.78, "LGPD: ASSINATURA MANUSCRITA DO RECEBEDOR"),
            (0.06, 0.80, 0.85, 0.89, "LGPD: NOME E RG MANUSCRITO TARJADOS"),
        ]
    if "HABILITACAO" in upper or "CNH" in upper or "DETRAN" in upper:
        return [
            (0.07, 0.24, 0.78, 0.31, "LGPD: NOME DO CONDUTOR"),
            (0.07, 0.36, 0.62, 0.43, "LGPD: CPF E RG TARJADOS"),
            (0.07, 0.65, 0.65, 0.74, "LGPD: FILIACAO / DADOS PESSOAIS"),
        ]
    if "MANUSCRITO" in upper or "DECLARACAO" in upper or "PUNHO" in upper:
        return [
            (0.07, 0.32, 0.88, 0.44, "LGPD: IDENTIFICACAO MANUSCRITA"),
            (0.07, 0.70, 0.76, 0.84, "LGPD: RUBRICA / ASSINATURA MANUAL"),
        ]
    return [
        (0.07, 0.24, 0.74, 0.31, "LGPD: TITULAR / PARTE CONTRATANTE"),
        (0.07, 0.34, 0.56, 0.41, "LGPD: CPF / CNPJ / RG PROTEGIDO"),
        (0.07, 0.75, 0.70, 0.83, "LGPD: ASSINATURA DIGITALIZADA"),
    ]
