"""Envio de callbacks ao backend Go: assinados com HMAC, idempotentes e com reenvio/backoff."""
import hashlib
import hmac
import json
import os
import time

import httpx


def assinar(secret: str, ts: str, corpo: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + corpo, hashlib.sha256).hexdigest()


def enviar(url: str, payload: dict, idem: str, tentativas: int = 4) -> bool:
    secret = os.environ.get("IA_CALLBACK_SECRET", "dev-callback-secret")
    corpo = json.dumps(payload, ensure_ascii=False).encode()
    espera = 1.0
    for _ in range(tentativas):
        ts = str(int(time.time()))
        try:
            r = httpx.post(url, content=corpo, timeout=30, headers={"Content-Type": "application/json", "X-Timestamp": ts, "X-Signature": assinar(secret, ts, corpo), "Idempotency-Key": idem})
            if r.status_code < 300:
                return True
            if r.status_code in (400, 401, 403):
                return False
        except httpx.HTTPError:
            pass
        time.sleep(espera)
        espera *= 2
    return False
