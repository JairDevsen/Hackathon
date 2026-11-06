#!/usr/bin/env python3
"""Cria segredos locais sem colocá-los no terminal ou no repositório."""

import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
KEY = ROOT / "secrets" / "jwt_ed25519.pem"
LENGTHS = {
    "POSTGRES_PASSWORD": 24,
    "APP_DB_PASSWORD": 24,
    "REDIS_PASSWORD": 24,
    "S3_SECRET_KEY": 24,
    "KEK_HEX": 32,
    "HMAC_KEY_HEX": 32,
    "IA_CORE_API_KEY": 24,
    "IA_CALLBACK_SECRET": 32,
    "MASTER_PASSWORD": 24,
}
HOST_IDS = {"APP_UID": str(os.getuid()), "APP_GID": str(os.getgid())}
PLACEHOLDERS = {"", "troque-me", "troque-me-com-32-caracteres"}


def main() -> None:
    os.umask(0o077)
    if ENV.is_symlink():
        raise SystemExit("O arquivo .env não pode ser um link simbólico")
    if ENV.exists() and os.getuid() == 0:
        raise SystemExit("Execute make keys como usuário não-root: o mesmo usuário executará a API e o worker no Docker")
    KEY.parent.mkdir(mode=0o700, exist_ok=True)
    KEY.parent.chmod(0o700)
    if KEY.is_symlink():
        raise SystemExit("A chave JWT não pode ser um link simbólico")
    if not KEY.exists():
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(KEY)],
            check=True,
        )
    KEY.chmod(0o600)

    if not ENV.exists():
        print("Chave JWT pronta em secrets/. Para produção, copie .env.example para .env e execute make keys novamente.")
        return

    staging = ROOT / "var" / "staging"
    staging.mkdir(parents=True, mode=0o700, exist_ok=True)
    staging.chmod(0o700)

    original = ENV.read_text(encoding="utf-8")
    lines = []
    seen = set()
    changed = []
    for line in original.splitlines(keepends=True):
        match = re.match(r"^([A-Z][A-Z0-9_]*)=(.*?)(\r?\n)?$", line)
        if not match or (match.group(1) not in LENGTHS and match.group(1) not in HOST_IDS):
            lines.append(line)
            continue
        name, value, newline = match.groups()
        seen.add(name)
        current = value.split("#", 1)[0].strip().strip('"\'')
        if current not in PLACEHOLDERS:
            lines.append(line)
            continue
        comment = value[value.index("#") :] if "#" in value else ""
        secret = HOST_IDS[name] if name in HOST_IDS else secrets.token_hex(LENGTHS[name])
        lines.append(f"{name}={secret}{'  ' + comment if comment else ''}{newline or ''}")
        changed.append(name)
    for name, length in LENGTHS.items():
        if name not in seen:
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(f"{name}={secrets.token_hex(length)}\n")
            changed.append(name)
    for name, value in HOST_IDS.items():
        if name not in seen:
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(f"{name}={value}\n")
            changed.append(name)

    fd, temporary = tempfile.mkstemp(prefix=".env.", dir=ROOT)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.writelines(lines)
        os.chmod(temporary, 0o600)
        os.replace(temporary, ENV)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Chave JWT e .env prontos (permissão 600)." + (" Preenchidos: " + ", ".join(changed) + "." if changed else " Nenhum valor substituído."))


if __name__ == "__main__":
    main()
