"""Importa os schemas e validações do ia_core (pasta irmã ou pacote instalado)."""
import sys
from pathlib import Path

try:
    import ia_core  # noqa: F401
except ImportError:
    irmao = Path(__file__).resolve().parents[2] / "ia_core"
    if not (irmao / "ia_core").exists():
        raise ImportError("ia_core não encontrado: coloque a pasta ia_core ao lado de gerador_docs ou instale-a")
    sys.path.insert(0, str(irmao))

from ia_core import schemas as sch  # noqa: E402
from ia_core import validacoes as val  # noqa: E402

__all__ = ["sch", "val"]
