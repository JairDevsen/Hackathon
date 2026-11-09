"""Roteador do funil: decide, para cada página, qual camada resolve — a mais barata que dá conta, sem perder qualidade.

  Camada 1  texto da página (nativo ou OCR local) + regras: custo zero.
  Camada 2  modelo leve sobre o TEXTO (sem imagem, sem transcrição): ~uma ordem de grandeza mais barato que a visão.
  Camada 3  modelo multimodal sobre a IMAGEM: só para o que o texto não resolve (manuscrito, formulário postal, OCR ruim).

Medido sobre OCR real do gerador (lotes de scanner leve a forte), a classificação local acerta ~99% das páginas com confiança
≥ 0,85; o que falta é a EXTRAÇÃO (CPF e competência). Por isso a Camada 1 só fecha a página quando o tipo é seguro E os campos
que o tipo exige foram achados; o resto sobe de camada. As regras são puras (sem rede) para serem medidas offline."""
import re
from dataclasses import dataclass
from typing import Iterable, List

from .catalogo import DOCS_DA_EMPRESA, DOCS_MENSAIS
from .orientacao import palavras_reconhecidas
from .extracao import cpf_valido

LIMIAR_LOCAL = 0.85       # confiança mínima da classificação local para fechar na Camada 1
CONF_MINIMA_MODELO = 0.70  # resposta do modelo de texto abaixo disso sobe para a visão
MIN_LETRAS = 100          # texto menor que isto não sustenta uma análise (cabeçalho solto, rodapé)
MIN_RECONHECIDAS = 6      # palavras do vocabulário documental no texto lido: abaixo disso o OCR é ruído


@dataclass(frozen=True)
class Rota:
    camada: int
    motivo: str


def texto_legivel(texto: str, nativo: bool) -> bool:
    """Texto nativo basta com tamanho; texto de OCR também precisa conter palavras de documento (senão é ruído de imagem)."""
    letras = len(re.findall(r"[A-Za-zÀ-ÿ]", texto or ""))
    if letras < MIN_LETRAS:
        return False
    return nativo or palavras_reconhecidas(texto) >= MIN_RECONHECIDAS


def campos_faltando(tipo: str, campos: dict, inicia_documento: bool) -> List[str]:
    """Campos que o tipo exige e a leitura não trouxe. Só a primeira página do documento é cobrada (o verso não repete o cabeçalho)."""
    if not inicia_documento:
        return []
    falta = []
    if tipo not in DOCS_DA_EMPRESA and not cpf_valido(str(campos.get("cpf") or "")):
        falta.append("cpf")
    if tipo in DOCS_MENSAIS and not campos.get("competencia"):
        falta.append("competencia")
    return falta


def decidir(local: dict, texto: str, nativo: bool, tipos_visao: Iterable[str]) -> Rota:
    """Rota de uma página a partir da leitura local (`local` = análise do motor de regras sobre `texto`)."""
    if local["tipo"] in tipos_visao or local.get("possui_manuscrito") or local.get("pagina_ilegivel"):
        return Rota(3, "manuscrito, formulário ou rasura: só a imagem resolve")
    if not texto_legivel(texto, nativo):
        return Rota(3, "texto lido sem qualidade")
    falta = campos_faltando(local["tipo"], local.get("campos") or {}, bool(local.get("inicia_documento", True)))
    if local["confianca"] >= LIMIAR_LOCAL:
        if "cpf" in falta:
            # texto nativo sem CPF não tem CPF na imagem também; no OCR o dígito pode ter sido perdido e a imagem mostra
            return Rota(2 if nativo else 3, "CPF não encontrado no texto")
        if falta:
            return Rota(2, "campos que as regras não acharam: " + ", ".join(falta))
        return Rota(1, "")
    return Rota(2, "classificação local incerta")


def precisa_subir(resposta: dict, local: dict, texto: str, nativo: bool) -> str:
    """Depois da Camada 2: devolve o motivo para subir à visão, ou '' se a resposta do modelo de texto vale."""
    if resposta.get("pagina_ilegivel") or resposta.get("multiplos_documentos_na_imagem"):
        return "modelo de texto reportou página ilegível ou com vários documentos"
    try:
        if float(resposta.get("confianca", 1)) < CONF_MINIMA_MODELO:
            return "confiança baixa do modelo de texto"
    except (TypeError, ValueError):
        return "confiança inválida"
    tem_cpf = cpf_valido(str(resposta.get("cpf") or "")) or cpf_valido(str(local.get("campos", {}).get("cpf") or ""))
    tn = resposta.get("tipo_novo") if isinstance(resposta.get("tipo_novo"), dict) else None
    da_empresa = str(tn.get("escopo", "")).upper() == "EMPRESA" if tn else local["tipo"] in DOCS_DA_EMPRESA  # tipo que a IA acabou de nomear traz o próprio escopo
    if not nativo and not da_empresa and resposta.get("inicia_documento", True) and not tem_cpf:
        return "CPF não lido no texto do OCR"
    return ""
