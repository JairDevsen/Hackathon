"""IA Core. schemas e validacoes não dependem do SDK do Gemini; extrator é carregado sob demanda."""
from .schemas import MODELOS_EXTRACAO, TipoDocumento
from .validacoes import Alerta, validar

_LAZY = {"IACore", "Pagina", "DocumentoDetectado", "ResultadoExtracao"}


def __getattr__(nome):
    if nome in _LAZY:
        from . import extrator
        return getattr(extrator, nome)
    raise AttributeError(nome)


__all__ = ["IACore", "Pagina", "DocumentoDetectado", "ResultadoExtracao",
           "TipoDocumento", "MODELOS_EXTRACAO", "validar", "Alerta"]
