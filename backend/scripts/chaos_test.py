#!/usr/bin/env python3
"""Teste de caos: derruba (kill -9) o worker e o IA Core no meio de um lote de 60 páginas e confere que o lote
termina com exatamente os mesmos documentos do gabarito (sem duplicar e sem perder nada).
Requer: IA_PAGE_DELAY_MS=400 no IA Core, BATCH_STALL_SECONDS=15 e WATCHDOG_INTERVAL=10s no worker.
Uso: API=... MAIL_LOG=... IA_CMD='...' WORKER_CMD='...' python scripts/chaos_test.py"""
import os, signal, subprocess, sys, time, hashlib
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ia-core"))
import e2e_smoke_lib as lib
from tools.gerador_docs import gerador

pdf, gab = gerador.lote_grande(60)
rh = lib.login("rh@agrotech.demo", "Demo!Citadel#2026")
r = lib.c.post(f"{lib.API}/batches", headers=lib.H(rh), files={"file": ("lote_grande.pdf", pdf)}); assert r.status_code == 202, r.text
batch = r.json()["id"]; print("lote enviado:", batch)
t0 = time.time()
while True:
    b = lib.get(rh, f"/batches/{batch}")
    ok_pages = sum(1 for p in b["paginas"] if p["status"] == "OK")
    if ok_pages >= 15: break
    assert time.time() - t0 < 120, "o lote não avançou"; time.sleep(0.5)
print(f"{ok_pages}/60 páginas concluídas — derrubando worker e IA Core (kill -9)")
for pat in (os.environ["WORKER_PAT"], os.environ["IA_PAT"]):
    subprocess.run(["pkill", "-9", "-f", pat])
time.sleep(3)
b = lib.get(rh, f"/batches/{batch}"); print("estado com tudo fora do ar:", b["status"], f"({sum(1 for p in b['paginas'] if p['status']=='OK')} páginas OK no checkpoint)")
subprocess.Popen(os.environ["IA_CMD"], shell=True, stdout=open(os.environ["IA_LOG"], "a"), stderr=subprocess.STDOUT)
subprocess.Popen(os.environ["WORKER_CMD"], shell=True, stdout=open(os.environ["WORKER_LOG"], "a"), stderr=subprocess.STDOUT)
t0 = time.time()
while True:
    b = lib.get(rh, f"/batches/{batch}")
    if b["status"].startswith("PROCESSADO") or b["status"] == "FALHOU": break
    assert time.time() - t0 < 240, f"não terminou: {b['status']} {b.get('erro')}"; time.sleep(2)
print("status final:", b["status"], "| tentativas:", b["tentativas"])
for ev in b["linha_tempo"]: print("  ·", ev["tipo"], "-", ev["mensagem"])
real = sorted((d["document_type"], tuple(d["paginas"])) for d in b["documentos"])
esp = sorted((g["tipo"], tuple(g["paginas"])) for g in gab)
assert real == esp, f"documentos diferem do gabarito: {len(real)} vs {len(esp)}"
assert any(e["tipo"] == "RETOMADO" for e in b["linha_tempo"]), "a linha do tempo deveria registrar a retomada"
print(f"OK — {len(real)} documentos idênticos ao processamento sem falhas (gabarito), sem duplicar")
