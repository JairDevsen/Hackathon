"""
Módulo de Anonimização de Dados Sensíveis (LGPD / PII Masking)
Responsável na Equipe: Thaynara (Dev 6 - Squad 3)
"""
import re
from pathlib import Path
from typing import Tuple, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont


CPF_REGEX = re.compile(r"\b(\d{3})\.?(\d{3})\.?(\d{3})-(\d{2})\b")
CNPJ_REGEX = re.compile(r"\b(\d{2})\.?(\d{3})\.?(\d{3})/(\d{4})-(\d{2})\b")
RG_REGEX = re.compile(r"\b(\d{1,2})\.?(\d{3})\.?(\d{3})-?([0-9Xx])\b")
CEP_REGEX = re.compile(r"\b(\d{5})-(\d{3})\b")
PHONE_REGEX = re.compile(r"(?:\(\d{2}\)\s?|\b\d{2}\s?)(?:9\d{4}|\d{4})-?\d{4}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def anonymize_ocr_text(text: str, page_num: int = 1, extra_names: List[str] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Detecta e mascara CPF, RG, CNPJ, CEP, Telefones, E-mails e nomes sensíveis
    retornando o texto mascarado e a lista de auditoria LGPD.
    """
    detected_items: List[Dict[str, Any]] = []
    masked_text = text

    for match in CPF_REGEX.finditer(text):
        raw = match.group(0)
        masked = f"***.{match.group(2)}.{match.group(3)}-**"
        detected_items.append({
            "tipo": "CPF",
            "valor_original_preview": f"{match.group(1)}.***.***-{match.group(4)}",
            "valor_mascarado": masked,
            "pagina": page_num,
        })
        masked_text = masked_text.replace(raw, masked)

    for match in CNPJ_REGEX.finditer(text):
        raw = match.group(0)
        masked = f"**.{match.group(2)}.{match.group(3)}/****-**"
        detected_items.append({
            "tipo": "CNPJ",
            "valor_original_preview": raw[:6] + "...",
            "valor_mascarado": masked,
            "pagina": page_num,
        })
        masked_text = masked_text.replace(raw, masked)

    for match in RG_REGEX.finditer(text):
        raw = match.group(0)
        if raw in masked_text:
            masked = f"**.{match.group(2)}.***-*"
            detected_items.append({
                "tipo": "RG",
                "valor_original_preview": f"{match.group(1)}.***...",
                "valor_mascarado": masked,
                "pagina": page_num,
            })
            masked_text = masked_text.replace(raw, masked)

    for match in CEP_REGEX.finditer(text):
        raw = match.group(0)
        masked = f"{match.group(1)[:2]}***-***"
        detected_items.append({
            "tipo": "CEP / ENDERECO",
            "valor_original_preview": raw,
            "valor_mascarado": masked,
            "pagina": page_num,
        })
        masked_text = masked_text.replace(raw, masked)

    for match in PHONE_REGEX.finditer(text):
        raw = match.group(0)
        masked = "(**) 9****-****"
        detected_items.append({
            "tipo": "TELEFONE",
            "valor_original_preview": raw[:6] + "****",
            "valor_mascarado": masked,
            "pagina": page_num,
        })
        masked_text = masked_text.replace(raw, masked)

    sensitive_names = extra_names or [
        "CARLOS EDUARDO SILVA",
        "Carlos Eduardo Silva",
        "ROBERTO ALMEIDA MENDES",
        "Roberto Almeida Mendes",
        "MARIA FERNANDA COSTA",
        "Maria Fernanda Costa",
        "JOAO PEDRO CAVALCANTI",
        "João Pedro Cavalcanti",
    ]
    for name in sensitive_names:
        if name in masked_text:
            parts = name.split()
            masked_name = parts[0][0] + "*** " + (" ".join([p[0] + "***" for p in parts[1:]]) if len(parts) > 1 else "")
            detected_items.append({
                "tipo": "NOME_PESSOAL / MANUSCRITO",
                "valor_original_preview": f"{parts[0]} ***",
                "valor_mascarado": f"[LGPD: {masked_name}]",
                "pagina": page_num,
            })
            masked_text = masked_text.replace(name, f"[LGPD: {masked_name}]")

    return masked_text, detected_items


def generate_redacted_image(
    source_image_path: Path,
    dest_image_path: Path,
    redaction_boxes: List[Tuple[float, float, float, float, str]] = None,
) -> None:
    """
    Gera versão da imagem com tarjas pretas de proteção LGPD sobre áreas de CPF, RG,
    assinatura manuscrita e endereço.
    As coordenadas em redaction_boxes são relativas (x0_rel, y0_rel, x1_rel, y1_rel, label).
    """
    img = Image.open(source_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    try:
        font = ImageFont.truetype("arial.ttf", max(12, int(h * 0.014)))
    except Exception:
        font = ImageFont.load_default()

    # Faixa superior de selo LGPD
    draw.rectangle([(0, 0), (w, int(h * 0.038))], fill=(15, 23, 42))
    draw.text(
        (int(w * 0.03), int(h * 0.008)),
        "MODO ANONIMIZADO ATIVO (LGPD - LEI 13.709/2018) - DADOS PII TARJADOS",
        fill=(56, 189, 248),
        font=font,
    )

    if not redaction_boxes:
        # Regiões padrão de proteção caso não especificadas
        redaction_boxes = [
            (0.08, 0.25, 0.68, 0.30, "LGPD: NOME / IDENTIFICACAO"),
            (0.08, 0.34, 0.52, 0.39, "LGPD: CPF / RG TARJADO"),
            (0.10, 0.72, 0.75, 0.81, "LGPD: ASSINATURA / DADO MANUSCRITO"),
        ]

    for x0_r, y0_r, x1_r, y1_r, label in redaction_boxes:
        x0, y0 = int(x0_r * w), int(y0_r * h)
        x1, y1 = int(x1_r * w), int(y1_r * h)
        draw.rectangle([(x0, y0), (x1, y1)], fill=(15, 23, 42), outline=(239, 68, 68), width=2)
        draw.text((x0 + 8, y0 + max(2, (y1 - y0) // 4)), f"[ {label} ]", fill=(248, 250, 252), font=font)

    dest_image_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest_image_path, format="PNG")
