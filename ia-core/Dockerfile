FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# Tesseract (português) para OCR posicionado de páginas escaneadas
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY ia_core ./ia_core
COPY tools ./tools
RUN useradd -r -u 10001 ia && chown -R ia /app
USER ia
EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=4s --retries=5 CMD curl -fs http://127.0.0.1:8001/health || exit 1
CMD ["uvicorn", "ia_core.main:app", "--host", "0.0.0.0", "--port", "8001"]
