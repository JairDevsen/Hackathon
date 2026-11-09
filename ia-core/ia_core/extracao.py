"""Extração por regex a partir do texto (motor local) e utilidades de datas/CPF."""
import re
from datetime import date
from typing import Dict, Optional

from .catalogo import norm

CPF_RE = re.compile(r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b")
# o OCR troca pontos e traço por espaço ou os perde: "790.864 532 10", "790 864 532-10"
CPF_FLEX = re.compile(r"(?<![\d.])(\d{3})[.\s]{0,2}(\d{3})[.\s]{0,2}(\d{3})[\s\-.]{0,3}(\d{2})(?!\d)")
CPF_ROTULADO = re.compile(r"C\.?P\.?F\b[^0-9A-Za-z]{0,6}([0-9OoIl|SsB][0-9OoIl|SsB.\-\s]{9,17}[0-9OoIl|SsB])", re.I)
_DIGITO = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "s": "5", "B": "8"})
CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
DATA_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
MESES = {m: i + 1 for i, m in enumerate("JANEIRO FEVEREIRO MARCO ABRIL MAIO JUNHO JULHO AGOSTO SETEMBRO OUTUBRO NOVEMBRO DEZEMBRO".split())}


EM_BRANCO_FRASE = re.compile(r"(INTENCIONALMENTE|PROPOSITALMENTE)\s+(DEIXAD[AO]\s+)?EM\s+BRANCO|PAGINA\s+(EM\s+BRANCO|SEM\s+CONTEUDO)|"
                             r"(LEFT|INTENTIONALLY)\s+(INTENTIONALLY\s+)?BLANK|ESPACO\s+(DEIXADO\s+)?EM\s+BRANCO|"
                             r"SEPARADOR\s+DE\s+DOCUMENTOS?|FOLHA\s+(SEPARADORA|DE\s+SEPARACAO)|PAGINA\s+SEPARADORA")


def aviso_em_branco(texto: str) -> bool:
    """Aviso curto de "página intencionalmente deixada em branco" ou folha separadora de lote ("SEPARADOR DE DOCUMENTOS"): nenhuma das duas é
    documento. Um documento de verdade que só mencione isso no meio de um texto longo (120 letras e dígitos ou mais) não conta."""
    util = len(re.sub(r"\W", "", texto or ""))
    return 8 <= util < 120 and bool(EM_BRANCO_FRASE.search(norm(texto)))


MARCA_DAGUA = re.compile(r"AMOSTRA|FICTICI|CONFIDENCIAL|RASCUNHO|\bCOPIA\b|SEM VALIDADE JURIDICA")
_VOCAB_MARCA = set("AMOSTRA DOCUMENTO FICTICIO GERADO PARA TESTES SOFTWARE VALIDADE JURIDICA CONFIDENCIAL RASCUNHO COPIA".split())


def so_marca_dagua(texto: str) -> bool:
    """O texto lido é só a marca d'água/carimbo da folha ("AMOSTRA - DOCUMENTO FICTÍCIO", "CÓPIA", "RASCUNHO"): no máximo duas outras palavras
    de 5 letras ou mais (o OCR de marca inclinada deixa lixo curto). Só vale junto com a imagem quase sem tinta (ver `TINTA_MARCA`)."""
    n = norm(texto)
    if not MARCA_DAGUA.search(n):
        return False
    return len([w for w in re.findall(r"[A-Z]{5,}", n) if w not in _VOCAB_MARCA]) <= 2


def sem_conteudo(texto: str) -> bool:
    """O texto lido NÃO é de um documento: vazio, só um número de página/ruído (menos de 8 letras e dígitos) ou o aviso de "em branco"."""
    return len(re.sub(r"\W", "", texto or "")) < 8 or aviso_em_branco(texto)


def cpf_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s or "")
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def cpf_do_texto(texto: str) -> Optional[str]:
    """Primeiro CPF VÁLIDO do texto (só dígitos); aceita o que o OCR costuma estragar. O dígito verificador impede falso positivo.
    Sem nenhum válido, devolve None (quem quiser o primeiro 'parecido' usa CPF_RE)."""
    candidatos = [m.group(0) for m in CPF_RE.finditer(texto)]
    candidatos += ["".join(m.groups()) for m in CPF_FLEX.finditer(texto)]
    for m in CPF_ROTULADO.finditer(texto):  # "CPF: 79O.864.532-1O": dígitos lidos como letra só valem logo depois do rótulo
        candidatos.append(re.sub(r"\D", "", m.group(1).translate(_DIGITO)))
    return next((re.sub(r"\D", "", c) for c in candidatos if cpf_valido(c)), None)


_MES_NOME = "|".join(MESES)
_ROTULO_COMP = (r"(?:COMPETENCIA|REFERENTE AO MES|MES DE REFERENCIA|MES DE COMPETENCIA|MES/ANO|REFERENCIA|PERIODO DE APURACAO|PERIODO DE REFERENCIA|"
                r"PAGAMENTO DE SALARIO|SALARIO REFERENTE A|REF\.)")
_VALOR_COMP = r"[^0-9A-Z]{0,8}(?:DE\s+)?(?:(\d{1,2})\s*[/.\-]\s*(\d{4})|(" + _MES_NOME + r")\s*(?:/|DE|-)?\s*(\d{4}))"
_FAIXA = re.compile(r"PERIODO[^0-9]{0,12}\d{2}/(\d{2})/(\d{4})\s*(?:A|ATE|-)\s*\d{2}/(\d{2})/(\d{4})")


def competencia_do_texto(texto: str) -> Optional[str]:
    """AAAA-MM a partir de "Competência: 04/2026", "Referente ao Mês: Abril/2026", "Pagamento de salário 04/2026", do valor na linha
    seguinte ao rótulo, ou de um período que cobre um mês só ("Período: 01/04/2026 a 30/04/2026")."""
    t = norm(texto)
    for m in re.finditer(_ROTULO_COMP + _VALOR_COMP, t):
        if m.group(1):
            mes, ano = int(m.group(1)), m.group(2)
            if 1 <= mes <= 12:
                return f"{ano}-{mes:02d}"
        elif m.group(3):
            return f"{m.group(4)}-{MESES[m.group(3)]:02d}"
    m = _FAIXA.search(t)
    if m and m.group(1) == m.group(3) and m.group(2) == m.group(4) and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{m.group(1)}"
    return None


def iso(d: str, m: str, a: str) -> Optional[str]:
    try:
        return date(int(a), int(m), int(d)).isoformat()
    except ValueError:
        return None


def cnpj_valido(s: str) -> bool:
    d = re.sub(r"\D", "", s or "")
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        soma = sum(int(d[i]) * pesos[len(pesos) - n + i] for i in range(n))
        r = soma % 11
        if (0 if r < 2 else 11 - r) != int(d[n]):
            return False
    return True


_CNPJ_NUM = r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})"
_ROTULO_PRESTADORA = re.compile(r"(?:CONTRATADA|PRESTADORA|FORNECEDORA?|TERCEIRIZADA|EMPREGADOR|RAZAO SOCIAL|EMPRESA)\b[^\n]{0,140}?CNPJ[^\d]{0,14}" + _CNPJ_NUM)
_ROTULO_CONTRATANTE = re.compile(r"CONTRATANTE\b[^\n]{0,140}?CNPJ[^\d]{0,14}" + _CNPJ_NUM)


def cnpj_da_empresa(texto: str) -> Optional[str]:
    t = norm(texto)
    for m in _ROTULO_PRESTADORA.finditer(t):
        if cnpj_valido(m.group(1)):
            return re.sub(r"\D", "", m.group(1))
    contratantes = {re.sub(r"\D", "", m.group(1)) for m in _ROTULO_CONTRATANTE.finditer(t)}
    validos = [re.sub(r"\D", "", m.group(0)) for m in CNPJ_RE.finditer(texto) if cnpj_valido(m.group(0))]
    for c in validos:
        if c not in contratantes:
            return c
    if validos:
        return validos[0]
    todos = [re.sub(r"\D", "", m.group(0)) for m in CNPJ_RE.finditer(texto)]
    return todos[0] if todos else None


def extrair_campos(texto: str) -> Dict[str, Optional[str]]:
    t = norm(texto)
    out: Dict[str, Optional[str]] = {}
    # CPF: prefere o primeiro CPF válido; senão o primeiro encontrado
    cpfs = [m.group(0) for m in CPF_RE.finditer(texto)]
    cpf = cpf_do_texto(texto) or (cpfs[0] if cpfs else None)
    out["cpf"] = re.sub(r"\D", "", cpf) if cpf else None
    m = re.search(r"(?:NOME(?: DO (?:COLABORADOR|FUNCIONARIO|EMPREGADO|TITULAR|CONDUTOR))?|COLABORADOR(?: TERCEIRIZADO)?|TITULAR|FUNCIONARIO|EMPREGADO)\s*(?:\([^)]*\))?\s*[:\-]\s*([A-Z][A-Z' ]{4,60}?)(?=\s*(?:\||\n|$|CPF|RG|MATRICULA|FUNCAO|CARGO))", t)
    if not m:
        m = re.search(r"\bEU,\s*([A-Z][A-Z ]{4,60}?)\s*,", t)
    out["nome"] = m.group(1).strip().title() if m else None
    m = re.search(r"MATRICULA\s*[:\-]?\s*(\d{3,10})", t)
    out["matricula"] = m.group(1) if m else None
    comp = competencia_do_texto(texto)
    out["competencia"] = comp
    # horas extras: total apurado no cartão de ponto (HH:MM) e valor pago no holerite (R$)
    m = re.search(r"HORAS EXTRAS\s*[:\-]\s*(\d{1,3})[:hH](\d{2})", t)
    out["horas_extras"] = f"{int(m.group(1)):02d}:{m.group(2)}" if m else None
    m = re.search(r"HORAS EXTRAS[^\n]{0,24}R\$\s*([\d\.]+,\d{2})", t)
    out["pagamento_horas_extras"] = m.group(1) if m else None
    # empresa: CNPJ e razão social. Um contrato cita DUAS empresas: vale a CONTRATADA/prestadora/fornecedora (o risco é dela),
    # não a contratante. Sem rótulo, o primeiro CNPJ válido.
    out["empresa_cnpj"] = cnpj_da_empresa(texto)
    m = re.search(r"(?:EMPRESA|EMPREGADOR|RAZAO SOCIAL|CONTRATADA|PRESTADORA)\s*[:\-]\s*([A-Z0-9][A-Z0-9 .&\-]{4,60}?)(?=\s*(?:\||\n|$|CNPJ|CPF))", t)
    out["empresa_nome"] = m.group(1).strip() if m else None
    m = DATA_RE.search(texto)
    out["data_documento"] = iso(*m.groups()) if m else None
    m = re.search(r"(?:VALIDADE|VALIDO ATE|VENCIMENTO|VAL\.?)\s*(?:CNH)?\s*[:\-]?\s*(\d{2})/(\d{2})/(\d{4})", t)
    out["validade_ate"] = iso(*m.groups()) if m else None
    return out
