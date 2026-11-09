"""Impressão digital do MOTOR de análise: provedor, modelos, regras e código que produzem a análise de uma página.

A Camada 0 (cache por SHA-256 da página) só pode reaproveitar uma análise feita pelo MESMO motor. Se o catálogo, as regras de
extração, o prompt, o modelo ou o código mudam, a impressão muda e as análises antigas deixam de valer: a página é analisada de
novo em vez de herdar um resultado produzido por regras que já não existem."""
import hashlib
import os

# arquivos cujo conteúdo define o resultado da análise de uma página
_ARQUIVOS = ("catalogo.py", "extracao.py", "validacoes.py", "checklist.py", "providers.py", "orientacao.py", "qualidade_img.py",
             "paginacao.py", "anonimizacao.py", "agrupar.py", "schemas.py", "roteador.py")
_AQUI = os.path.dirname(os.path.abspath(__file__))


def _codigo() -> str:
    h = hashlib.sha256()
    for nome in _ARQUIVOS:
        with open(os.path.join(_AQUI, nome), "rb") as f:
            h.update(nome.encode() + b"\0" + f.read() + b"\0")
    return h.hexdigest()


def impressao_motor(provider) -> str:
    """'provedor:modelo|código' — o que tiver de mudar para uma análise antiga deixar de valer."""
    ajustes = "|".join(str(getattr(provider, a, "")) for a in ("nome", "model", "fallback", "lite")) + "|" + \
        os.environ.get("IA_IMAGE_MAX_PX", "") + "|" + os.environ.get("IA_NITIDEZ_MIN", "")
    return f"{getattr(provider, 'nome', 'motor')}|{hashlib.sha256((ajustes + _codigo()).encode()).hexdigest()[:16]}"
