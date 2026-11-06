#!/usr/bin/env python3
"""Refresh token rotativo + detecção de reuso (roubo) + step-up + sessões."""
import re, httpx
from e2e_smoke_lib import *

# login mantendo cookies
tok = login("rh@agrotech.demo", "Demo!Citadel#2026")
# o login helper usa o cliente global c: ele já guarda os cookies do refresh/CSRF
rt1 = c.cookies.get("citadel_rt"); csrf = c.cookies.get("citadel_csrf"); assert rt1 and csrf
r = c.post(f"{API}/auth/refresh", headers={"X-CSRF-Token": csrf}); assert r.status_code == 200, r.text; ok("refresh emite novo access token")
rt2 = c.cookies.get("citadel_rt"); assert rt2 != rt1; ok("refresh token foi rotacionado")
assert c.post(f"{API}/auth/refresh").status_code == 401; ok("sem CSRF → 401")
# reapresenta o token antigo (roubo): toda a família é revogada
thief = httpx.Client(timeout=30); thief.cookies.set("citadel_rt", rt1, path="/api/v1/auth/refresh"); thief.cookies.set("citadel_csrf", csrf)
r = thief.post(f"{API}/auth/refresh", headers={"X-CSRF-Token": csrf}); assert r.status_code == 401; ok("reuso do token antigo → 401")
r = c.post(f"{API}/auth/refresh", headers={"X-CSRF-Token": csrf}); assert r.status_code == 401; ok("família inteira revogada (o token legítimo também caiu)")
# step-up
tok = login("admin@agrotech.demo", "Demo!Citadel#2026")
r = c.post(f"{API}/exports/dossie/00000000-0000-0000-0000-000000000000", headers=H(tok)); assert r.status_code == 401 and r.headers.get("x-step-up-required") == "true"; ok("ação sensível sem step-up → 401 + X-Step-Up-Required")
before = codes_count("admin@agrotech.demo")
t = c.post(f"{API}/auth/step-up", headers=H(tok)).json()["ticket"]
code = code_from_mail("admin@agrotech.demo", before)
bad = c.post(f"{API}/auth/step-up", headers=H(tok), json={"ticket": t, "code": "000000"}); assert bad.status_code == 401; ok("código errado de step-up → 401")
st = c.post(f"{API}/auth/step-up", headers=H(tok), json={"ticket": t, "code": code}).json()["token"]
r = c.post(f"{API}/exports/dossie/00000000-0000-0000-0000-000000000000", headers=H(tok, {"X-Step-Up-Token": st})); assert r.status_code == 404; ok("com step-up a ação prossegue (404 do funcionário inexistente)")
# 5 tentativas erradas de 2FA invalidam o ticket
r = c.post(f"{API}/auth/login", json={"email": "rh@agrotech.demo", "senha": "Demo!Citadel#2026"}); tk = r.json()["mfa_ticket"]
for i in range(5): c.post(f"{API}/auth/mfa/verify", json={"mfa_ticket": tk, "code": "111111"})
code = code_from_mail("rh@agrotech.demo", codes_count("rh@agrotech.demo") - 1)
assert c.post(f"{API}/auth/mfa/verify", json={"mfa_ticket": tk, "code": code}).status_code == 401; ok("após 5 tentativas erradas o ticket é invalidado mesmo com o código certo")
rs = c.post(f"{API}/auth/mfa/resend", json={"mfa_ticket": tk}); assert rs.status_code in (401, 429); ok("reenvio respeita intervalo/ticket")
print("\nOK")
