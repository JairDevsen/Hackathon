"""Provedores de análise de página. Interface única para trocar/comparar modelos sem mexer na API Go."""
import base64
import io
import json
import logging
import os
import re
import time
from typing import Dict, List, Optional, Protocol

from PIL import Image

from .catalogo import CODIGOS, TIPOS, classificar, norm
from .extracao import extrair_campos
from .qualidade_img import analisar_imagem

CONTINUACAO = re.compile(r"PAG(?:INA)?\.?\s*(\d+)\s*/\s*(\d+)|\bVERSO\b|CONTINUACAO|CONTINUA NO VERSO")
BAIXA_QUALIDADE = re.compile(r"ILEGIVEL|RASURA|BORRAD|ILEG[ÍI]VEL")


CAMADA_1 = "Camada 1: Texto nativo + regex local (custo zero)"
CAMADA_2 = "Camada 2: modelo de texto sobre o texto extraído"
CAMADA_3 = "Camada 3: modelo multimodal (imagem reduzida em WebP)"
# tipos em que o texto nativo não basta (manuscrito, formulários postais, exames): vão direto para a visão
TIPOS_VISAO = {"AVISO_RECEBIMENTO", "DOCUMENTO_MANUSCRITO", "ASO", "FICHA_EPI", "ATESTADO_MEDICO"}


class Pagina(dict):
    """analise da página: tipo, inicia_documento, confianca, texto_ocr, campos, possui_manuscrito, pagina_ilegivel,
    multiplos_documentos_na_imagem, pagina_em_branco, titulo, motivo, tokens"""


class Provider(Protocol):
    nome: str

    def analisar(self, imagem: bytes, numero: int, anterior: Optional[dict], texto_embutido: str, tipo_lote: str) -> Pagina: ...


def pagina_borrada(q: dict) -> "Pagina":
    return Pagina(tipo="OUTRO", inicia_documento=True, confianca=0.2, texto_ocr="", campos={}, possui_manuscrito=False, pagina_ilegivel=True, borrada=True,
                  multiplos_documentos_na_imagem=False, pagina_em_branco=False, titulo="Imagem borrada", motivo=f"imagem borrada (nitidez {q['nitidez']})", tokens=0, camada=CAMADA_1)


class LocalProvider:
    """Motor determinístico: usa o texto REAL da página (camada de texto do PDF ou OCR, quando disponível).
    Serve para desenvolvimento, testes e como linha de base da tela 'Qualidade da IA'."""

    nome = "local-heuristico"

    def analisar(self, imagem, numero, anterior, texto_embutido, tipo_lote):
        texto = (texto_embutido or "").strip()
        if not texto:
            q = analisar_imagem(imagem)  # página de imagem (sem camada de texto): confere nitidez antes de tudo
            if q["borrada"]:
                return pagina_borrada(q)
            texto = _ocr_se_disponivel(imagem)
            if len(re.sub(r"\W", "", texto)) < 8:
                if q["branco"]:
                    return Pagina(tipo="OUTRO", inicia_documento=True, confianca=0.35, texto_ocr="", campos={}, possui_manuscrito=False, pagina_ilegivel=False,
                                  multiplos_documentos_na_imagem=False, pagina_em_branco=True, titulo="Página em branco", motivo="página em branco", tokens=0, camada=CAMADA_1)
                # há conteúdo mas nenhum OCR disponível: NÃO descartar como branco; vai para revisão humana
                return Pagina(tipo="OUTRO", inicia_documento=True, confianca=0.3, texto_ocr="", campos={}, possui_manuscrito=False, pagina_ilegivel=True,
                              multiplos_documentos_na_imagem=False, pagina_em_branco=False, titulo="Página sem texto reconhecido", motivo="sem OCR disponível", tokens=0, camada=CAMADA_1)
        if len(re.sub(r"\W", "", texto)) < 8:
            return Pagina(tipo="OUTRO", inicia_documento=True, confianca=0.35, texto_ocr=texto, campos={}, possui_manuscrito=False,
                          pagina_ilegivel=not texto, multiplos_documentos_na_imagem=False, pagina_em_branco=not texto, titulo="Página em branco ou ilegível",
                          motivo="sem texto reconhecível", tokens=0, camada=CAMADA_1)
        tipo, conf = classificar(texto)
        t = norm(texto)
        ilegivel = bool(BAIXA_QUALIDADE.search(t))
        if ilegivel:
            conf = min(conf, 0.58)
        cont = False
        m = CONTINUACAO.search(t)
        if m and anterior and anterior.get("tipo") == tipo:
            cont = not (m.group(1) and int(m.group(1)) == 1)
        campos = extrair_campos(texto)
        return Pagina(tipo=tipo, inicia_documento=not cont, confianca=conf, texto_ocr=texto, campos=campos,
                      possui_manuscrito=bool(re.search(r"MANUSCRIT|PROPRIO PUNHO|A CANETA|RUBRICA", t)), pagina_ilegivel=ilegivel,
                      multiplos_documentos_na_imagem=False, pagina_em_branco=False, titulo=TIPOS[tipo]["nome"], motivo="rasura/ilegibilidade" if ilegivel else "", tokens=0,
                      camada=CAMADA_1 if texto_embutido else "Camada 1: OCR local + regex (custo zero)")


def _ocr_se_disponivel(imagem: bytes) -> str:
    """OCR de imagem escaneada via Tesseract (se instalado). Sem Tesseract devolve vazio (a página vai para revisão)."""
    try:
        import fitz

        pix = fitz.Pixmap(imagem)
        doc = fitz.open()
        page = doc.new_page(width=pix.width, height=pix.height)
        page.insert_image(page.rect, stream=imagem)
        tp = page.get_textpage_ocr(language="por", dpi=150, full=True)
        return page.get_text("text", textpage=tp)
    except Exception:
        return ""


MAX_PX = int(os.environ.get("IA_IMAGE_MAX_PX") or os.environ.get("GEMINI_IMAGE_MAX_PX") or "1024")
log = logging.getLogger("ia_core.providers")

PROMPT = """Você lê UMA página de um lote de documentos trabalhistas digitalizados (RH/DP de empresas terceirizadas no Brasil).
Tipos possíveis: {tipos}. Use OUTRO se não houver correspondência.
Responda no JSON do schema. Regras:
- inicia_documento=true se a página começa um novo documento; false se for verso/continuação do documento da página anterior (tipo anterior: {anterior}).
- Transcreva todo o texto impresso e manuscrito em texto_ocr.
- cpf somente dígitos; competencia AAAA-MM; datas AAAA-MM-DD.
- empresa_nome e empresa_cnpj (somente dígitos): a empresa empregadora/contratada/prestadora citada no documento (não o funcionário).
- confianca de 0 a 1; abaixo de 0,7 se houver rasura, borrão, manuscrito duvidoso ou ilegibilidade.
- pagina_ilegivel=true se não for possível ler; multiplos_documentos_na_imagem=true se houver mais de um documento na mesma imagem.
- tem_assinatura=true se houver assinatura/rubrica física.
Dica do tipo de lote enviado pelo RH (apenas contexto): {tipo_lote}."""


class _Uso:
    """Consumo de tokens num formato único (o Gemini e a OpenAI devolvem objetos diferentes)."""

    def __init__(self, total: int = 0):
        self.total_token_count = int(total or 0)


class LLMProvider:
    """Funil comum aos provedores de modelo externo: Camada 1 (local, custo zero) → 2 (modelo leve sobre o texto) → 3 (visão).

    Cada provedor implementa só `_chamar` (imagem), `_chamar_texto` e `_ping`; o roteamento, o modelo reserva e a
    normalização da resposta são iguais para todos."""

    nome = "llm"
    model = fallback = lite = ""

    def _schema(self):
        from pydantic import BaseModel, Field

        class Extra(BaseModel):
            chave: str
            valor: str

        class PaginaLLM(BaseModel):
            tipo: str
            inicia_documento: bool
            confianca: float
            titulo: str = ""
            texto_ocr: str = ""
            cpf: Optional[str] = None
            nome: Optional[str] = None
            empresa_nome: Optional[str] = None
            empresa_cnpj: Optional[str] = None
            matricula: Optional[str] = None
            competencia: Optional[str] = None
            data_documento: Optional[str] = None
            validade_ate: Optional[str] = None
            possui_manuscrito: bool = False
            tem_assinatura: bool = False
            pagina_ilegivel: bool = False
            multiplos_documentos_na_imagem: bool = False
            pagina_em_branco: bool = False
            extras: List[Extra] = Field(default_factory=list)

        return PaginaLLM

    def _chamar(self, model, imagem, prompt, mime):  # pragma: no cover - implementado pelo provedor
        raise NotImplementedError

    def _chamar_texto(self, model, texto, prompt):  # pragma: no cover
        raise NotImplementedError

    def _ping(self, model) -> str:  # pragma: no cover
        raise NotImplementedError

    def diagnosticar(self) -> list:
        """Chamada mínima (sem documento) a cada modelo configurado: mostra o que funciona, antes de processar um lote."""
        out = []
        for papel, m in (("principal (imagem)", self.model), ("texto (camada 2)", self.lite), ("reserva", self.fallback)):
            t = time.time()
            try:
                resp = self._ping(m)
                out.append({"papel": papel, "modelo": m, "ok": True, "ms": round(1000 * (time.time() - t)), "resposta": (resp or "")[:20]})
            except Exception as e:  # noqa: BLE001
                out.append({"papel": papel, "modelo": m, "ok": False, "ms": round(1000 * (time.time() - t)), "erro": f"{type(e).__name__}: {str(e)[:200]}"})
        return out

    def analisar(self, imagem, numero, anterior, texto_embutido, tipo_lote):
        """Funil: Camada 1 (texto nativo + regex, custo zero) → Camada 2 (modelo leve sobre o texto) → Camada 3 (visão)."""
        prompt = PROMPT.format(tipos=", ".join(CODIGOS), anterior=(anterior or {}).get("tipo", "nenhum (primeira página)"), tipo_lote=tipo_lote)
        texto = (texto_embutido or "").strip()
        if not texto:
            q = analisar_imagem(imagem)
            if q["borrada"]:
                return pagina_borrada(q)  # não gasta tokens com imagem ilegível
        if len(texto) >= 120:
            local = LocalProvider().analisar(imagem, numero, anterior, texto, tipo_lote)
            if local["tipo"] not in TIPOS_VISAO and not local["possui_manuscrito"] and not local["pagina_ilegivel"]:
                if local["confianca"] >= 0.85:
                    return local  # Camada 1: resolvido sem chamar a IA
                try:
                    d, uso = self._chamar_texto(self.lite, texto, prompt)
                    return self._normalizar(d, uso, CAMADA_2)
                except Exception as e:  # noqa: BLE001
                    log.warning("Camada 2 falhou (%s); subindo para visão", e)
        img, mime = _reduzir(imagem, MAX_PX)  # só a cópia enviada à IA é reduzida; o original fica guardado
        try:
            d, uso = self._chamar(self.model, img, prompt, mime)
        except Exception as e:  # noqa: BLE001  modelo principal indisponível (404/503 persistente): tenta o reserva uma vez
            if self.fallback == self.model:
                raise
            log.warning("modelo %s falhou (%s); tentando %s", self.model, str(e)[:120], self.fallback)
            d, uso = self._chamar(self.fallback, img, prompt, mime)
        # modelo reserva (maior) para páginas difíceis
        if d.get("pagina_ilegivel") or d.get("multiplos_documentos_na_imagem") or d.get("confianca", 1) < 0.6:
            try:
                d2, uso2 = self._chamar(self.fallback, img, prompt, mime)
                d, uso = d2, _soma(uso, uso2)
            except Exception:  # noqa: BLE001
                pass
        return self._normalizar(d, uso, CAMADA_3)

    def _normalizar(self, d, uso, camada):
        tokens = int(getattr(uso, "total_token_count", 0) or 0) if uso else 0
        tipo = d.get("tipo") if d.get("tipo") in CODIGOS else "OUTRO"
        campos = {k: d.get(k) for k in ("cpf", "nome", "matricula", "competencia", "data_documento", "validade_ate", "empresa_nome", "empresa_cnpj")}
        for e in d.get("extras") or []:
            if isinstance(e, dict) and e.get("chave"):
                campos[e["chave"]] = e.get("valor")
        if d.get("tem_assinatura"):
            campos["assinatura_detectada"] = True
        try:
            conf = max(0.0, min(1.0, float(d.get("confianca", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        return Pagina(tipo=tipo, inicia_documento=bool(d.get("inicia_documento", True)), confianca=conf, texto_ocr=d.get("texto_ocr") or "",
                      campos=campos, possui_manuscrito=bool(d.get("possui_manuscrito")), pagina_ilegivel=bool(d.get("pagina_ilegivel")),
                      multiplos_documentos_na_imagem=bool(d.get("multiplos_documentos_na_imagem")), pagina_em_branco=bool(d.get("pagina_em_branco")),
                      titulo=d.get("titulo") or TIPOS[tipo]["nome"], motivo="", tokens=tokens, camada=camada)


class GeminiProvider(LLMProvider):
    """Gemini multimodal lendo a IMAGEM (layout + texto + manuscrito + carimbos) com saída estruturada validada por schema."""

    def __init__(self, api_key: str, model: str = None, fallback: str = None):
        from google import genai
        from google.genai import types

        # 429/5xx passageiros (alta demanda) são tentados de novo com espera crescente antes de a página falhar
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=90_000, retry_options=types.HttpRetryOptions(attempts=4, initial_delay=1.5, max_delay=20.0, http_status_codes=[429, 500, 502, 503, 504])))
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.fallback = fallback or os.environ.get("GEMINI_MODEL_FALLBACK", "gemini-3.6-flash")
        self.lite = os.environ.get("GEMINI_MODEL_LITE", "gemini-3.5-flash-lite")
        self.nome = "gemini:" + self.model

    def _cfg(self):
        from google.genai import types

        return types.GenerateContentConfig(response_mime_type="application/json", response_schema=self._schema(), temperature=0.0)

    @staticmethod
    def _uso(r):
        u = getattr(r, "usage_metadata", None)
        return _Uso(getattr(u, "total_token_count", 0) if u else 0)

    def _chamar(self, model, imagem, prompt, mime):
        from google.genai import types

        r = self.client.models.generate_content(model=model, contents=[types.Part.from_bytes(data=imagem, mime_type=mime), prompt], config=self._cfg())
        return json.loads(r.text), self._uso(r)

    def _chamar_texto(self, model, texto, prompt):
        r = self.client.models.generate_content(model=model, contents=[prompt + "\n\nTEXTO DA PÁGINA (extraído do PDF):\n" + texto[:12000]], config=self._cfg())
        return json.loads(r.text), self._uso(r)

    def _ping(self, model):
        return self.client.models.generate_content(model=model, contents="Responda apenas com a palavra: OK").text


class OpenAIProvider(LLMProvider):
    """Modelos da OpenAI (chat com imagem) em modo JSON: mesmo funil do Gemini, resposta validada na normalização.

    Modelos por variável de ambiente (`OPENAI_MODEL`, `OPENAI_MODEL_LITE`, `OPENAI_MODEL_FALLBACK`): nomes de modelo mudam e
    ficam indisponíveis com o tempo; use `GET /diagnostico` do IA Core para conferir o que a sua chave aceita."""

    def __init__(self, api_key: str, model: str = None, fallback: str = None):
        from openai import OpenAI

        # tentativas automáticas em 429/5xx com espera crescente (o SDK já faz o backoff)
        self.client = OpenAI(api_key=api_key, timeout=90.0, max_retries=4, base_url=os.environ.get("OPENAI_BASE_URL") or None)
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5-mini")
        self.fallback = fallback or os.environ.get("OPENAI_MODEL_FALLBACK", "gpt-5")
        self.lite = os.environ.get("OPENAI_MODEL_LITE", "gpt-5-nano")
        self.esforco = os.environ.get("OPENAI_REASONING_EFFORT", "").strip()  # opcional: minimal|low|medium|high (só modelos que aceitam)
        self.nome = "openai:" + self.model

    def _instrucao(self, prompt: str) -> str:
        esquema = json.dumps(self._schema().model_json_schema(), ensure_ascii=False)
        return prompt + "\n\nResponda SOMENTE com um objeto JSON (sem texto fora do JSON) que siga este JSON Schema:\n" + esquema

    def _pedir(self, model, conteudo):
        args = dict(model=model, messages=[{"role": "user", "content": conteudo}], response_format={"type": "json_object"})
        if self.esforco:
            args["reasoning_effort"] = self.esforco
        r = self.client.chat.completions.create(**args)
        uso = _Uso(getattr(getattr(r, "usage", None), "total_tokens", 0))
        return json.loads(r.choices[0].message.content), uso

    def _chamar(self, model, imagem, prompt, mime):
        url = f"data:{mime};base64," + base64.b64encode(imagem).decode()
        return self._pedir(model, [{"type": "text", "text": self._instrucao(prompt)}, {"type": "image_url", "image_url": {"url": url}}])

    def _chamar_texto(self, model, texto, prompt):
        return self._pedir(model, self._instrucao(prompt) + "\n\nTEXTO DA PÁGINA (extraído do PDF):\n" + texto[:12000])

    def _ping(self, model):
        r = self.client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Responda apenas com a palavra: OK"}])
        return r.choices[0].message.content


def _soma(a, b):
    return _Uso(int(getattr(a, "total_token_count", 0) or 0) + int(getattr(b, "total_token_count", 0) or 0))


def _reduzir(imagem: bytes, maximo: int):
    """Reduz proporcionalmente (thumbnail) e comprime em WebP q=80: menos bytes enviados à API. Devolve (bytes, mime)."""
    im = Image.open(io.BytesIO(imagem))
    im.thumbnail((maximo, maximo))
    b = io.BytesIO()
    im.convert("RGB").save(b, "WEBP", quality=80)
    return b.getvalue(), "image/webp"


def obter_provider() -> "Provider":
    """Escolha do provedor na inicialização: `IA_PROVIDER` (openai|gemini|local) manda; sem ele, OPENAI_API_KEY tem prioridade
    sobre GEMINI_API_KEY; sem nenhuma chave, o motor local (texto nativo, OCR e regras)."""
    escolha = os.environ.get("IA_PROVIDER", "").strip().lower()
    oa = os.environ.get("OPENAI_API_KEY", "").strip()
    gm = os.environ.get("GEMINI_API_KEY", "").strip()
    if escolha not in ("", "local", "openai", "gemini"):
        raise RuntimeError(f"IA_PROVIDER inválido: {escolha!r} (use openai, gemini ou local)")
    if escolha == "local":
        return LocalProvider()
    if escolha == "openai" and not oa:
        raise RuntimeError("IA_PROVIDER=openai, mas OPENAI_API_KEY está vazia")
    if escolha == "gemini" and not gm:
        raise RuntimeError("IA_PROVIDER=gemini, mas GEMINI_API_KEY está vazia")
    if escolha == "openai" or (not escolha and oa):
        return OpenAIProvider(oa)
    if escolha == "gemini" or (not escolha and gm):
        return GeminiProvider(gm)
    return LocalProvider()
