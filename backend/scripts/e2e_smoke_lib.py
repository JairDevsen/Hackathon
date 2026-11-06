#!/usr/bin/env python3
"""Teste de fumaça ponta a ponta (API + worker + IA Core + Postgres + Redis).
Uso: API=http://localhost:8080 MAIL_LOG=/caminho/api.log  python scripts/e2e_smoke.py
Lê o código 2FA do log do mailer (MAIL_DRIVER=log) ou do Mailpit (MAILPIT_URL)."""
import os, re, sys, time, json, hashlib
import httpx

API = os.environ.get("API", "http://localhost:8080") + "/api/v1"
MAIL_LOG = os.environ.get("MAIL_LOG", "")
MAILPIT = os.environ.get("MAILPIT_URL", "")
PDF = os.environ.get("LOTE_PDF", os.path.join(os.path.dirname(__file__), "../../ia-core/tools/gerador_docs/samples/Lote_RH_Misto_11pags.pdf"))
c = httpx.Client(timeout=60)
ok = lambda m: print("  ✔", m)


def codes_count(email):
    """Quantos e-mails COM código existem no log para o usuário (mesma regex usada para extrair)."""
    if not MAIL_LOG or MAILPIT: return 0
    return len(re.findall(r'"to":"%s".*?é: (\d{6})' % re.escape(email), open(MAIL_LOG).read().replace("\\n", " ")))


def code_from_mail(email, since=0):
    for _ in range(40):
        if MAILPIT:
            msgs = httpx.get(MAILPIT + "/api/v1/messages").json().get("messages", [])
            for m in msgs:
                if any(t["Address"] == email for t in m["To"]):
                    body = httpx.get(MAILPIT + f"/api/v1/message/{m['ID']}").json()["Text"]
                    mm = re.search(r"é: (\d{6})", body)
                    if mm: return mm.group(1)
        else:
            txt = open(MAIL_LOG).read()
            found = re.findall(r'"to":"%s".*?é: (\d{6})' % re.escape(email), txt.replace("\\n", " "))
            if len(found) > since: return found[-1]
        time.sleep(0.5)
    raise SystemExit("código 2FA não encontrado")


def login(email, senha):
    before = codes_count(email)
    r = c.post(f"{API}/auth/login", json={"email": email, "senha": senha}); r.raise_for_status()
    t = r.json()["mfa_ticket"]
    code = code_from_mail(email, before)
    r = c.post(f"{API}/auth/mfa/verify", json={"mfa_ticket": t, "code": code}); r.raise_for_status()
    return r.json()["access_token"]


def H(tok, extra=None): return {"Authorization": "Bearer " + tok, **(extra or {})}


def get(tok, path, **kw):
    r = c.get(API + path, headers=H(tok), **kw); assert r.status_code == 200, (path, r.status_code, r.text[:300]); return r.json()


