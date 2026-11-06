@echo off
title Document AI Factory - Hack Garanhuns Tech 2026
echo ======================================================================
echo   INICIANDO DOCUMENT AI FACTORY (BACKEND FASTAPI + INTERFACE WEB)
echo   Acesse no navegador: http://localhost:8000
echo   Documentacao Swagger da API: http://localhost:8000/docs
echo ======================================================================
start http://localhost:8000
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
