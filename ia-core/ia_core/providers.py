"""Provedores de análise de página. Interface única para trocar/comparar modelos sem mexer na API Go."""
import base64
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from PIL import Image

from .catalogo import ORIGEM_IA, TIPOS, classificar, dados_tipo_ia, norm, propor_tipo
from .extracao import extrair_campos
from .qualidade_img import TINTA_MARCA, analisar_imagem
from .orientacao import melhor_orientacao, ocr_texto
from .paginacao import marcador_de_pagina
from .extracao import aviso_em_branco, cpf_valido, sem_conteudo, so_marca_dagua
from .roteador import decidir, precisa_subir

CONTINUACAO = re.compile(r"PAG(?:INA)?\.?\s*(\d+)\s*/\s*(\d+)|\bVERSO\b|CONTINUACAO|CONTINUA NO VERSO")
BAIXA_QUALIDADE = re.compile(r"ILEGIVEL|RASURA|BORRAD|ILEG[ÍI]VEL")


CAMADA_1 = "Camada 1: Texto nativo + regex local (custo zero)"
CAMADA_1_OCR = "Camada 1: OCR local + regex (custo zero)"
CONF_TIPO_NOVO = float(os.environ.get("IA_CONF_TIPO_NOVO", "0.70"))  # confiança mínima da leitura para a IA criar um tipo documental novo
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


def pagina_em_branco(motivo: str = "página em branco") -> "Pagina":
    """Folha sem conteúdo: o agrupador a descarta (não vira documento, nem "OUTRO"), e a Camada 0 a lembra pelo hash."""
    return Pagina(tipo="OUTRO", inicia_documento=True, confianca=0.35, texto_ocr="", campos={}, possui_manuscrito=False, pagina_ilegivel=False,
                  multiplos_documentos_na_imagem=False, pagina_em_branco=True, titulo="Página em branco", motivo=motivo, tokens=0, camada=CAMADA_1)


def anexar_tipo_ia(pg: "Pagina") -> "Pagina":
    """Página de um tipo descoberto pela IA leva a descrição dele (`tipo_novo`): o backend registra o tipo no catálogo e, ao retomar um lote em
    outro processo, o IA Core o reaprende pelas análises já salvas."""
    d = dados_tipo_ia(pg.get("tipo", ""))
    if d:
        pg["tipo_novo"] = d
    return pg


def leitura_local(imagem: bytes, texto_embutido: str):
    """Lê a página sem rede: texto nativo, ou OCR (com correção de orientação) quando a página é só imagem.
    Devolve (pagina_pronta | None, texto, nativo). `pagina_pronta` é preenchida quando a página é EM BRANCO (inclusive só com sombra de
    borda, furos, ruído, número de página ou o aviso "intencionalmente em branco") ou BORRADA; nesses casos não há mais nada a fazer.
    Sem `pagina_pronta` e sem texto, a página tem conteúdo que o OCR não leu (manuscrito, foto): quem chama decide o destino."""
    texto = (texto_embutido or "").strip()
    if texto and not sem_conteudo(texto) and not so_marca_dagua(texto):
        return None, texto, True
    q = analisar_imagem(imagem)  # texto nativo vazio, só um número de página, aviso de "em branco" ou marca d'água: confere a imagem

    def vazia(t: str) -> bool:  # aviso de "em branco", ou só marca d'água numa folha quase sem tinta (um bilhete manuscrito tem mais tinta)
        return aviso_em_branco(t) or (so_marca_dagua(t) and q["tinta"] < TINTA_MARCA)

    if q["branco"] or vazia(texto):
        return pagina_em_branco(), "", False
    if q["borrada"] and q["tinta"] >= TINTA_MARCA:
        return pagina_borrada(q), "", False  # não gasta tokens com imagem ilegível
    _, lido = melhor_orientacao(imagem, _ocr_se_disponivel)  # página escaneada de cabeça para baixo é lida girada
    lido = (lido or "").strip()
    if vazia(lido):
        return pagina_em_branco("página sem conteúdo (só aviso ou marca d'água)"), "", False
    if q["borrada"]:  # quase sem tinta e o OCR não achou marca d'água: continua sendo imagem ilegível
        return pagina_borrada(q), "", False
    if sem_conteudo(lido):  # a imagem tem tinta mas o OCR não leu quase nada: pode ser manuscrito ou foto, NÃO se descarta
        return None, "", False
    return None, lido, False


class LocalProvider:
    """Motor determinístico: usa o texto REAL da página (camada de texto do PDF ou OCR, quando disponível).
    Serve para desenvolvimento, testes e como linha de base da tela 'Qualidade da IA'."""

    nome = "local-heuristico"

    def analisar(self, imagem, numero, anterior, texto_embutido, tipo_lote):
        pronta, texto, nativo = leitura_local(imagem, texto_embutido)
        if pronta is not None:
            return pronta
        if not texto:
            # há conteúdo mas nenhum OCR disponível: NÃO descartar como branco; vai para revisão humana
            return Pagina(tipo="OUTRO", inicia_documento=True, confianca=0.3, texto_ocr="", campos={}, possui_manuscrito=False, pagina_ilegivel=True,
                          multiplos_documentos_na_imagem=False, pagina_em_branco=False, titulo="Página sem texto reconhecido", motivo="sem OCR disponível", tokens=0, camada=CAMADA_1)
        tipo, conf = classificar(texto)
        t = norm(texto)
        ilegivel = bool(BAIXA_QUALIDADE.search(t))
        if ilegivel:
            conf = min(conf, 0.58)
        cont = False
        mk = marcador_de_pagina(texto)
        if mk and anterior:  # "Página 2/3" continua o documento anterior; "Página 1/3" abre um novo (o agrupador confere o resto)
            cont = mk[0] > 1
        else:
            m = CONTINUACAO.search(t)
            if m and anterior and anterior.get("tipo") == tipo:
                cont = True
        campos = extrair_campos(texto)
        return Pagina(tipo=tipo, inicia_documento=not cont, confianca=conf, texto_ocr=texto, campos=campos,
                      possui_manuscrito=bool(re.search(r"MANUSCRIT|PROPRIO PUNHO|A CANETA|RUBRICA", t)), pagina_ilegivel=ilegivel,
                      multiplos_documentos_na_imagem=False, pagina_em_branco=False, titulo=TIPOS[tipo]["nome"], motivo="rasura/ilegibilidade" if ilegivel else "", tokens=0,
                      camada=CAMADA_1 if nativo else CAMADA_1_OCR)


def _ocr_se_disponivel(imagem: bytes) -> str:
    """OCR de imagem escaneada via Tesseract (se instalado). Sem Tesseract devolve vazio (a página vai para revisão)."""
    try:
        return ocr_texto(imagem)
    except Exception:
        return ""


MAX_PX = int(os.environ.get("IA_IMAGE_MAX_PX") or os.environ.get("GEMINI_IMAGE_MAX_PX") or "1024")
log = logging.getLogger("ia_core.providers")

PROMPT = """Você lê UMA página de um lote de documentos trabalhistas digitalizados (RH/DP de empresas terceirizadas no Brasil).
Tipos possíveis: {tipos}. Use OUTRO se não houver correspondência.
Responda no JSON do schema. Regras:
- inicia_documento=true se a página começa um novo documento; false se for verso/continuação do documento da página anterior (tipo anterior: {anterior}).
  Um documento pode ter várias páginas (contrato, TRCT com o termo de quitação, cartão de ponto, AR com frente e verso). Se a página traz
  "Página 2/3", "Folha 2/2" ou parece verso/anexo do documento anterior (cláusulas seguintes, assinaturas, termo de quitação, dados do
  recebimento), inicia_documento=false e use o MESMO tipo do documento a que pertence, não o que o texto da página sozinha sugere.
  "Página 1/N" ou um cabeçalho/título novo: inicia_documento=true.
{transcricao}
- cpf somente dígitos; competencia AAAA-MM; datas AAAA-MM-DD.
- empresa_nome e empresa_cnpj (somente dígitos): a empresa empregadora/contratada/prestadora citada no documento (não o funcionário).
- confianca de 0 a 1; abaixo de 0,7 se houver rasura, borrão, manuscrito duvidoso ou ilegibilidade.
- pagina_ilegivel=true se não for possível ler; multiplos_documentos_na_imagem=true se houver mais de um documento na mesma imagem.
- tem_assinatura=true se houver assinatura/rubrica física.
- pagina_em_branco=true se a folha não tem conteúdo de documento: vazia, só com sombra, ruído, furos, número de página ou o aviso "intencionalmente em branco".
  Uma página com texto ou manuscrito, mesmo curto ou ilegível, NÃO é em branco. Folha separadora ("Separador de documentos") também é pagina_em_branco=true.
- Se a página é um documento LEGÍVEL que não corresponde a nenhum tipo da lista, use tipo=OUTRO e preencha tipo_novo: nome (nome GENÉRICO e curto do
  tipo, como "Procuração" ou "Laudo de insalubridade"; nunca nome de pessoa ou empresa, número ou data), escopo (FUNCIONARIO se o documento é de uma
  pessoa/empregado; EMPRESA se é da empresa), categoria (ADMISSAO, MENSAL, SAUDE_SEGURANCA, DISCIPLINAR, DESLIGAMENTO, EMPRESA ou OUTROS) e pistas
  (2 a 4 frases curtas IMPRESSAS no documento que o identificam, copiadas exatamente). Se algum tipo da lista serve, use-o e deixe tipo_novo vazio.
Dica do tipo de lote enviado pelo RH (apenas contexto): {tipo_lote}."""
TRANSCREVER = "- Transcreva todo o texto impresso e manuscrito em texto_ocr."
NAO_TRANSCREVER = "- O texto da página já foi extraído e segue abaixo: NÃO o transcreva; deixe texto_ocr vazio."


@dataclass
class Pedido:
    """O que falta resolver depois da etapa local: uma chamada de modelo (Camada 2 sobre o texto ou Camada 3 sobre a imagem)."""
    camada: int
    imagem: bytes
    texto: str
    nativo: bool
    local: Optional[dict]
    prompt_imagem: str
    prompt_texto: str
    tipo_local: str = "OUTRO"
    motivo: str = ""


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

        class TipoNovo(BaseModel):
            nome: str
            escopo: str = "FUNCIONARIO"
            categoria: str = "OUTROS"
            pistas: List[str] = Field(default_factory=list)

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
            tipo_novo: Optional[TipoNovo] = None
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

    def _prompts(self, anterior, tipo_lote):
        comum = dict(tipos=", ".join(list(TIPOS)), anterior=(anterior or {}).get("tipo", "nenhum (primeira página)"), tipo_lote=tipo_lote)
        return PROMPT.format(transcricao=TRANSCREVER, **comum), PROMPT.format(transcricao=NAO_TRANSCREVER, **comum)

    def preparar(self, imagem, numero, anterior, texto_embutido, tipo_lote):
        """Etapa LOCAL do funil (sem rede): lê o texto da página (nativo, ou OCR com correção de orientação), aplica as regras e decide a
        camada. Devolve a `Pagina` pronta (Camada 1, ou página em branco/borrada) ou um `Pedido` de chamada ao modelo."""
        pi, pt = self._prompts(anterior, tipo_lote)
        pronta, texto, nativo = leitura_local(imagem, texto_embutido)
        if pronta is not None:  # em branco ou borrada: não gasta modelo nenhum
            return pronta
        if not texto:  # há conteúdo que o OCR local não leu (manuscrito, foto): só a visão resolve
            return Pedido(3, imagem, "", False, None, pi, pt, motivo="sem texto lido")
        local = anexar_tipo_ia(LocalProvider().analisar(imagem, numero, anterior, texto, tipo_lote))  # com texto informado, não repete o OCR
        local["camada"] = CAMADA_1 if nativo else CAMADA_1_OCR
        rota = decidir(local, texto, nativo, TIPOS_VISAO)
        if rota.camada == 1:
            return local
        return Pedido(rota.camada, imagem, texto, nativo, local, pi, pt, tipo_local=local["tipo"], motivo=rota.motivo)

    def executar(self, pedido: "Pedido") -> "Pagina":
        """Etapa de REDE: Camada 2 (modelo leve sobre o texto), subindo para a 3 (visão) quando a resposta não é confiável."""
        uso = None
        if pedido.camada == 2:
            try:
                d, uso = self._chamar_texto(self.lite, pedido.texto, pedido.prompt_texto)
                motivo = precisa_subir(d, pedido.local, pedido.texto, pedido.nativo)
                if not motivo:
                    return self._finalizar(d, uso, CAMADA_2, pedido)
                log.info("Camada 2 -> 3 (%s)", motivo)
            except Exception as e:  # noqa: BLE001
                log.warning("Camada 2 falhou (%s); subindo para visão", e)
        img, mime = _reduzir(pedido.imagem, MAX_PX)  # só a cópia enviada à IA é reduzida; o original fica guardado
        try:
            d, uso3 = self._chamar(self.model, img, pedido.prompt_imagem, mime)
        except Exception as e:  # noqa: BLE001  modelo principal indisponível (404/503 persistente): tenta o reserva uma vez
            if self.fallback == self.model:
                raise
            log.warning("modelo %s falhou (%s); tentando %s", self.model, str(e)[:120], self.fallback)
            d, uso3 = self._chamar(self.fallback, img, pedido.prompt_imagem, mime)
        uso = _soma(uso, uso3) if uso else uso3  # o gasto da Camada 2 descartada também conta
        # modelo reserva (maior) para páginas difíceis
        if d.get("pagina_ilegivel") or d.get("multiplos_documentos_na_imagem") or d.get("confianca", 1) < 0.6:
            try:
                d2, uso2 = self._chamar(self.fallback, img, pedido.prompt_imagem, mime)
                d, uso = d2, _soma(uso, uso2)
            except Exception:  # noqa: BLE001
                pass
        return self._finalizar(d, uso, CAMADA_3, pedido)

    def analisar(self, imagem, numero, anterior, texto_embutido, tipo_lote):
        """Funil completo de uma página (as duas etapas em sequência)."""
        r = self.preparar(imagem, numero, anterior, texto_embutido, tipo_lote)
        return self.executar(r) if isinstance(r, Pedido) else r

    def _finalizar(self, d, uso, camada, pedido):
        """Normaliza a resposta e completa com o que as regras locais leram: CPF válido (dígito verificador) vale mais que o do modelo,
        e o texto já extraído é o texto_ocr da Camada 2 (o modelo não o transcreve)."""
        pg = self._normalizar(d, uso, camada)
        if camada == CAMADA_2 and not pg.get("texto_ocr"):
            pg["texto_ocr"] = pedido.texto
        loc = (pedido.local or {}).get("campos") or {}
        if loc.get("cpf") and cpf_valido(str(loc["cpf"])) and not cpf_valido(str(pg["campos"].get("cpf") or "")):
            pg["campos"]["cpf"] = loc["cpf"]
        for k in ("competencia", "validade_ate", "matricula"):  # o que o modelo não achou e as regras acharam
            if not pg["campos"].get(k) and loc.get(k):
                pg["campos"][k] = loc[k]
        self._descobrir_tipo(pg, d, pg.get("texto_ocr") or pedido.texto)
        return anexar_tipo_ia(pg)

    def _descobrir_tipo(self, pg, d, texto):
        """Documento legível que nenhum tipo cobre: a IA o nomeia (`tipo_novo`) e o tipo passa a existir no catálogo, com as frases que o
        identificam como pistas locais. Só vale com confiança alta e página legível; nome vago ou instância no lugar do tipo é recusado."""
        if pg["tipo"] != "OUTRO" or pg.get("pagina_em_branco") or pg.get("pagina_ilegivel") or pg.get("multiplos_documentos_na_imagem"):
            return
        if pg["confianca"] < CONF_TIPO_NOVO:
            return
        tn = d.get("tipo_novo") if isinstance(d.get("tipo_novo"), dict) else {}
        bruto = d.get("tipo") if d.get("tipo") not in (None, "", "OUTRO") and d.get("tipo") not in TIPOS else None  # o modelo inventou um código
        nome = (tn.get("nome") or (str(bruto).replace("_", " ").title() if bruto else "")).strip()
        if not nome:
            return
        codigo = propor_tipo(nome, tn.get("pistas") or [], texto or "", str(tn.get("escopo") or "FUNCIONARIO").upper(), str(tn.get("categoria") or "OUTROS").upper())
        if codigo:
            pg["tipo"] = codigo
            pg["titulo"] = TIPOS[codigo]["nome"]
            log.info("tipo documental %s (%s) reconhecido pela IA", codigo, "novo" if TIPOS[codigo].get("origem") == ORIGEM_IA else "do catálogo")

    def _normalizar(self, d, uso, camada):
        tokens = int(getattr(uso, "total_token_count", 0) or 0) if uso else 0
        tipo = d.get("tipo") if d.get("tipo") in TIPOS else "OUTRO"
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
