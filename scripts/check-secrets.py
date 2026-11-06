#!/usr/bin/env python3
"""Bloqueia arquivos e valores sensíveis no índice do Git sem imprimi-los."""

import subprocess
import sys
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(POSTGRES_PASSWORD|APP_DB_PASSWORD|REDIS_PASSWORD|S3_SECRET_KEY|"
    r"KEK_HEX|HMAC_KEY_HEX|IA_CORE_API_KEY|IA_CALLBACK_SECRET|MASTER_PASSWORD|"
    r"SMTP_PASS|GEMINI_API_KEY|OPENAI_API_KEY|AWS_SECRET_ACCESS_KEY)[ \t]*=[ \t]*(.*?)[ \t]*$",
    re.MULTILINE,
)
TOKEN = re.compile(r"(?:sk-|ghp_|github_pat_|AIza)[A-Za-z0-9_-]{20,}")
PRIVATE_KEY = re.compile(r"^-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----$", re.MULTILINE)
PUBLIC_VALUES = {"", "troque-me", "troque-me-com-32-caracteres"}


def forbidden(path: str) -> bool:
    name = Path(path).name.lower()
    parts = Path(path).parts
    if path == "secrets/.gitkeep":
        return False
    if "secrets" in parts:
        return True
    if name == ".env.example" or (name.startswith(".env.") and name.endswith(".example")):
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if name in {".npmrc", ".pypirc"}:
        return True
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")):
        return True
    if name.endswith(".json") and (
        name.startswith("gcp")
        or "credentials" in name
        or "service-account" in name
        or "service_account" in name
        or "secret" in name
    ):
        return True
    return False


def main() -> int:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    paths = [raw.decode("utf-8", errors="replace") for raw in result.stdout.split(b"\0") if raw]
    blocked = sorted(path for path in paths if forbidden(path))
    leaked = []
    for path in paths:
        if path in blocked:
            continue
        content = subprocess.run(
            ["git", "show", ":" + path], cwd=ROOT, check=True, capture_output=True
        ).stdout
        if b"\0" in content or len(content) > 2_000_000:
            continue
        source = content.decode("utf-8", errors="replace")
        if PRIVATE_KEY.search(source) or TOKEN.search(source):
            leaked.append(path)
            continue
        for match in ASSIGNMENT.finditer(source):
            value = match.group(2).split("#", 1)[0].strip().strip("\"'")
            if value and value not in PUBLIC_VALUES and not value.startswith(("${", "$", "<")):
                leaked.append(f"{path} ({match.group(1)})")
                break
    if blocked or leaked:
        print("Possíveis credenciais preparadas para commit:", file=sys.stderr)
        for path in blocked:
            print(f"  {path}", file=sys.stderr)
        for item in leaked:
            print(f"  {item}", file=sys.stderr)
        print("Remova o arquivo com git rm --cached <arquivo> ou apague o valor do texto e prepare a correção novamente.", file=sys.stderr)
        return 1
    print("Nenhuma credencial detectada no índice do Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
