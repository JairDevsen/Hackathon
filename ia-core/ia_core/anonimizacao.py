"""Detecção de dados pessoais (campos + regex) e geração das caixas de tarja."""
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
RG = re.compile(r"\bRG\b[:\s]*[\d\.\-Xx]{6,12}")
CEP = re.compile(r"\b\d{5}-\d{3}\b")
TEL = re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
CID = re.compile(r"\bCID[:\s-]*[A-Z]\d{2}(?:\.\d)?\b")
PIS = re.compile(r"\bPIS[:\s/-]*\d{3}\.?\d{5}\.?\d{2}-?\d\b")
BANCO = re.compile(r"\b(?:AG[ÊE]NCIA|CONTA)[:\s]*\d{3,}[-\d]*", re.I)
NOME = re.compile(r"(?i:NOME|COLABORADOR|TITULAR|DESTINAT[ÁA]RIO|RECEBEDOR|EMPREGADO|TRABALHADOR|FUNCION[ÁA]RIO)[^:\n]{0,40}:\s*([A-ZÀ-Ú][A-Za-zÀ-ú' ]{4,60})")

ENDERECO = re.compile(r"(?:ENDERE[ÇC]O|RESID[ÊE]NCIA|DOMIC[ÍI]LIO)[^:\n]{0,20}:[ \t]*([^\n]{6,120})", re.I)
# padrões em que só o grupo 1 é o dado pessoal (o rótulo, como "Nome:", fica visível)
GRUPOS = [("NOME", NOME), ("ENDERECO", ENDERECO)]

LOGRADOURO = re.compile(r"\b(?:Rua|RUA|Avenida|AVENIDA|Av\.|AV\.|Travessa|TRAVESSA|Alameda|ALAMEDA|Praça|PRAÇA|Rodovia|RODOVIA|Estrada|ESTRADA)\s+[A-ZÀ-Ú][^\n|]{3,90}")

PADROES = [("CPF", CPF), ("CNPJ", CNPJ), ("RG", RG), ("CEP", CEP), ("TELEFONE", TEL), ("EMAIL", EMAIL), ("CID", CID), ("PIS", PIS), ("DADO_BANCARIO", BANCO), ("ENDERECO", LOGRADOURO)]


def mascarar(tipo: str, valor: str) -> str:
    d = re.sub(r"\D", "", valor)
    if tipo == "CPF" and len(d) == 11:
        return f"***.{d[3:6]}.{d[6:9]}-**"
    if tipo == "CNPJ":
        return "**.***.***/****-**"
    return "[" + tipo + " OCULTO]"


def detectar(texto: str) -> List[Dict]:
    """Lista de ocorrências {tipo, valor, mascarado}; `valor` não sai do IA Core (só o mascarado)."""
    out = []
    for tipo, rx in PADROES:
        for m in rx.finditer(texto):
            out.append({"tipo": tipo, "valor": m.group(0), "mascarado": mascarar(tipo, m.group(0))})
    for tipo, rx in GRUPOS:
        for m in rx.finditer(texto):
            out.append({"tipo": tipo, "valor": m.group(1).strip(), "mascarado": f"[{tipo} OCULTO]"})
    return out


def anonimizar_texto(texto: str) -> Tuple[str, List[Dict]]:
    itens = detectar(texto)
    res = texto
    for it in sorted(itens, key=lambda i: -len(i["valor"])):
        res = res.replace(it["valor"], it["mascarado"])
    publicos = [{"tipo": i["tipo"], "mascarado": i["mascarado"]} for i in itens]
    return res, publicos


def _linhas(palavras: List[list]) -> List[List[int]]:
    """Agrupa os índices das palavras em linhas (mesma faixa vertical), da esquerda para a direita."""
    ordem = sorted(range(len(palavras)), key=lambda i: (palavras[i][1] + palavras[i][3]) / 2)
    linhas: List[List[int]] = []
    for i in ordem:
        p = palavras[i]
        centro, alt = (p[1] + p[3]) / 2, max(p[3] - p[1], 1e-6)
        if linhas:
            u = palavras[linhas[-1][0]]
            if abs(centro - (u[1] + u[3]) / 2) <= alt * 0.6:
                linhas[-1].append(i)
                continue
        linhas.append([i])
    return [sorted(l, key=lambda j: palavras[j][0]) for l in linhas]


# ---- dados que NÃO vêm depois de um rótulo na mesma linha: usam a posição das palavras na página ----
_ROTULO_NOME = {"NOME", "EMPREGADO", "TRABALHADOR", "FUNCIONARIO", "COLABORADOR", "TITULAR", "DESTINATARIO", "RECEBEDOR", "DEPENDENTE", "CONDUTOR", "RECLAMANTE"}
_ROTULO_ENDERECO = {"ENDERECO", "RESIDENCIA", "DOMICILIO", "LOGRADOURO"}
_ROTULO_NASC = {"NASCIMENTO", "NASC"}
_DATA = re.compile(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}$")
_NAO_NOME = {"LTDA", "EPP", "EIRELI", "ME", "SA", "CIA", "SERVICOS", "EMPRESA", "COMERCIO", "INDUSTRIA", "MATRIZ", "FILIAL", "DATA", "HORA", "TOTAL", "VALOR", "CPF", "CNPJ",
              "MATRICULA", "CARGO", "SETOR", "FUNCAO", "ADMISSAO", "DESLIGAMENTO", "COMPETENCIA", "REMUNERACAO", "SALARIO", "NUMERO", "PIS", "PASEP", "CTPS", "SERIE", "CEP",
              "BAIRRO", "MUNICIPIO", "CIDADE", "ESTADO", "TELEFONE", "EMAIL", "ASSINATURA", "ASSINADO", "TESTEMUNHA", "RUBRICA", "SIM", "NAO", "BRASIL", "FICTICIO", "AMOSTRA",
              "DOCUMENTO", "MODELO", "VALIDADE", "SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO", "DOMINGO"} | _ROTULO_NOME | _ROTULO_ENDERECO | _ROTULO_NASC
_nao_nome_completo = None


def _alfa(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(t).upper()) if c.isalpha() and not unicodedata.combining(c))


def _excluidas() -> set:
    global _nao_nome_completo
    if _nao_nome_completo is None:  # vocabulário do catálogo (títulos, rótulos de formulário) não é nome de pessoa
        from .orientacao import _VOCAB
        _nao_nome_completo = _NAO_NOME | set(_VOCAB)
    return _nao_nome_completo


def _partes(t: str) -> List[str]:
    return [x for x in re.split(r"[^A-Z]+", unicodedata.normalize("NFKD", str(t).upper()).encode("ascii", "ignore").decode()) if x]


def _corridas_de_nome(idx: List[int], palavras: List[list]) -> List[list]:
    """Caixas de sequências de PELO MENOS DUAS palavras que parecem nome de pessoa (alfabéticas, fora do vocabulário de formulário),
    com as ligações "da/de/dos/e" no meio. Uma palavra solta não é tarjada (evita cobrir títulos e rótulos)."""
    exc, caixas, run, nomes = _excluidas(), [], [], 0

    def fecha():
        nonlocal run, nomes
        while run and _alfa(palavras[run[-1]][4]).lower() in _LIGACOES:
            run.pop()  # a corrida não termina numa ligação
        if nomes >= 2 and run:
            xs = [palavras[k] for k in run]
            caixas.append([min(p[0] for p in xs), min(p[1] for p in xs), max(p[2] for p in xs), max(p[3] for p in xs), "NOME"])
        run, nomes = [], 0

    for k in idx:
        t = str(palavras[k][4])
        a = _alfa(t)
        if any(c.isdigit() for c in t) or len(a) < 2:
            fecha()
        elif a.lower() in _LIGACOES and run:
            run.append(k)
        elif len(a) >= 3 and a not in exc and t.replace("'", "").replace("-", "").isalpha():
            run.append(k)
            nomes += 1
        else:
            fecha()
    fecha()
    return caixas


def _valor_do_rotulo(linhas: List[List[int]], li: int, fim: int, palavras: List[list], tipo: str) -> List[list]:
    """O valor de um rótulo ("Nome", "Endereço", "Nascimento") pode estar à direita, na mesma linha, ou na linha logo abaixo (formulários
    com o rótulo em cima do campo). Cobre os dois lugares."""
    ultimo = palavras[linhas[li][fim]]
    alt = max(ultimo[3] - ultimo[1], 1e-6)
    candidatos = [[k for k in linhas[li][fim + 1:]]]
    for lj in range(li + 1, min(li + 3, len(linhas))):  # primeira linha abaixo (até ~2,4 alturas de distância)
        w0 = palavras[linhas[lj][0]]
        if (w0[1] + w0[3]) / 2 - ultimo[3] > 2.4 * alt:
            break
        seg = [k for k in linhas[lj] if ultimo[0] - 0.20 <= palavras[k][0] <= ultimo[2] + 0.45]  # o rótulo pode ter várias palavras ("Data de nascimento")
        if seg:
            candidatos.append(seg)
            break
    caixas = []
    for seg in candidatos:
        if tipo == "NOME":
            caixas += _corridas_de_nome(seg, palavras)
        elif tipo == "ENDERECO" and seg:
            xs = [palavras[k] for k in seg]
            caixas.append([min(p[0] for p in xs), min(p[1] for p in xs), max(p[2] for p in xs), max(p[3] for p in xs), "ENDERECO"])
        elif tipo == "NASCIMENTO":
            caixas += [palavras[k][:4] + ["NASCIMENTO"] for k in seg if _DATA.match(str(palavras[k][4]).strip(".,:;"))]
    return caixas


def _unicas(caixas: List[list]) -> List[list]:
    vistos, out = set(), []
    for c in caixas:
        k = tuple(round(v, 3) for v in c[:4]) + (c[4],)
        if k not in vistos:
            vistos.add(k)
            out.append(c)
    return out


def _colunas_de_tabela(caixas: List[list], palavras: List[list]) -> List[list]:
    """Se uma coluna de tabela tem vários CPFs (ou nomes) tarjados, as células dessa coluna entre eles também são dado pessoal,
    mesmo quando o OCR errou aquela célula e nenhuma expressão a reconheceu."""
    extra: List[list] = []
    for tipo in ("CPF", "NOME"):
        bs = sorted([c for c in caixas if c[4] == tipo], key=lambda c: c[0])
        grupos: List[List[list]] = []
        for c in bs:  # agrupa por alinhamento à esquerda (a mesma coluna)
            if grupos and abs(grupos[-1][0][0] - c[0]) <= 0.03:
                grupos[-1].append(c)
            else:
                grupos.append([c])
        for g in grupos:
            if len(g) < 3:
                continue
            x0, x1 = min(c[0] for c in g) - 0.02, max(c[2] for c in g) + 0.02
            y0, y1 = min(c[1] for c in g) - 0.005, max(c[3] for c in g) + 0.005
            for w in palavras:
                if not (y0 <= (w[1] + w[3]) / 2 <= y1 and x0 <= w[0] and w[2] <= x1):
                    continue
                t = str(w[4])
                digitos = sum(ch.isdigit() for ch in t)
                if (tipo == "CPF" and digitos >= 4) or (tipo == "NOME" and digitos == 0 and len(_alfa(t)) >= 3 and _alfa(t) not in _excluidas()):
                    extra.append(w[:4] + [tipo])
    return extra


def caixas_por_posicao(palavras: List[list]) -> List[list]:
    """Dados pessoais que o texto corrido não revela, por estarem em tabelas ou em formulários com o rótulo acima do valor:

      1. na linha de um CPF, o nome da pessoa (listas de trabalhadores: CPF, nome, valor);
      2. o valor de rótulos de nome, endereço e nascimento, à direita OU na linha de baixo."""
    if not palavras:
        return []
    linhas = _linhas(palavras)
    caixas: List[list] = []
    for li, idx in enumerate(linhas):
        texto = " ".join(str(palavras[k][4]) for k in idx)
        if CPF.search(texto):
            caixas += _corridas_de_nome(idx, palavras)
        for pos, k in enumerate(idx):
            partes = _partes(palavras[k][4])
            for conjunto, tipo in ((_ROTULO_NOME, "NOME"), (_ROTULO_ENDERECO, "ENDERECO"), (_ROTULO_NASC, "NASCIMENTO")):
                if any(x in conjunto for x in partes):
                    caixas += _valor_do_rotulo(linhas, li, pos, palavras, tipo)
    # nome à direita de um CPF, numa faixa em torno do próprio CPF: em página inclinada o OCR separa o CPF e o nome da mesma linha
    for w in palavras:
        if CPF.search(str(w[4])):
            alt = max(w[3] - w[1], 1e-6)
            cy = (w[1] + w[3]) / 2
            faixa = sorted([k for k, p in enumerate(palavras) if p[0] >= w[2] - 0.01 and abs((p[1] + p[3]) / 2 - cy) <= 0.8 * alt], key=lambda k: palavras[k][0])
            caixas += _corridas_de_nome(faixa, palavras)
    return _unicas(caixas)  # a mesma caixa pode vir de duas regras


def caixas_de_palavras(palavras: List[list]) -> List[list]:
    """Caixas de tarja [x0,y0,x1,y1,tipo] (frações da página) a partir das palavras com posição (OCR ou texto nativo).

    Não depende de buscar texto na página: reconstrói o texto linha a linha, detecta os dados pessoais com as mesmas
    expressões de `detectar` e cobre as palavras que o trecho atravessa (uma caixa por linha)."""
    if not palavras:
        return []
    partes, trechos, pos = [], [], 0  # trechos: (início, fim, índice da palavra)
    for linha in _linhas(palavras):
        for j in linha:
            t = str(palavras[j][4])
            trechos.append((pos, pos + len(t), j))
            partes.append(t + " ")
            pos += len(t) + 1
        partes[-1] = partes[-1][:-1] + "\n"  # fim de linha: o NOME não atravessa linhas
    texto = "".join(partes)
    achados = [(tipo, m.start(), m.end()) for tipo, rx in PADROES for m in rx.finditer(texto)]
    achados += [(tipo, m.start(1), m.end(1)) for tipo, rx in GRUPOS for m in rx.finditer(texto)]
    caixas = []
    for tipo, ini, fim in achados:
        por_linha: Dict[int, list] = {}
        for a, b, j in trechos:
            if a < fim and b > ini:
                x0, y0, x1, y1 = palavras[j][:4]
                cx = por_linha.setdefault(round((y0 + y1) / 2, 3), [x0, y0, x1, y1])
                cx[0], cx[1], cx[2], cx[3] = min(cx[0], x0), min(cx[1], y0), max(cx[2], x1), max(cx[3], y1)
        for c in por_linha.values():
            if tipo == "ENDERECO":  # o OCR costuma ler só parte do endereço: cobre até o fim da linha
                c[2] = max(c[2], 0.93)
            caixas.append(c + [tipo])
    todas = _unicas(caixas + caixas_por_posicao(palavras))
    # colunas de tabela: precisa enxergar as caixas de AMBAS as regras (os CPFs vêm do texto corrido; os nomes, da posição)
    return _unicas(todas + _colunas_de_tabela(todas, palavras))


_LIGACOES = {"da", "de", "do", "das", "dos", "e"}


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(t).lower()) if c.isalnum() and not unicodedata.combining(c))


def caixas_de_nomes(palavras: List[list], termos: List[str]) -> List[list]:
    """Tarja nomes que o sistema já conhece (por exemplo, o do funcionário), onde quer que apareçam na página, mesmo sem
    rótulo "Nome:" e com pequenos erros de OCR. Só cobre sequências de ao menos duas palavras do nome (ex.: nome e sobrenome)."""
    conhecidos = {_norm(t) for nome in termos for t in str(nome).split() if len(_norm(t)) >= 3 and _norm(t) not in _LIGACOES}
    if not palavras or not conhecidos:
        return []

    def eh_nome(t: str) -> bool:
        n = _norm(t)
        return len(n) >= 3 and (n in conhecidos or (len(n) >= 5 and any(len(c) >= 5 and SequenceMatcher(None, n, c).ratio() >= 0.8 for c in conhecidos)))

    caixas = []
    for linha in _linhas(palavras):
        i = 0
        while i < len(linha):
            if not eh_nome(palavras[linha[i]][4]):
                i += 1
                continue
            j, fim, n_nomes = i, i, 0
            while j < len(linha):
                t = palavras[linha[j]][4]
                if eh_nome(t):
                    fim, n_nomes = j, n_nomes + 1
                elif _norm(t) not in _LIGACOES:
                    break
                j += 1
            if n_nomes >= 2:
                cx = [palavras[linha[k]] for k in range(i, fim + 1)]
                caixas.append([min(p[0] for p in cx), min(p[1] for p in cx), max(p[2] for p in cx), max(p[3] for p in cx), "NOME"])
            i = fim + 1
    return caixas
