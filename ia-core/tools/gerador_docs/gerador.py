"""Gerador de lotes FICTÍCIOS com gabarito (marca "AMOSTRA"). Alimenta testes E2E, a demo e a tela "Qualidade da IA".
Nenhum documento real: nomes e CPFs são inventados (CPFs com dígitos verificadores válidos)."""
import os
import sys
from datetime import date, timedelta
from typing import Dict, List, Tuple

import fitz

HOJE = date.today()

FUNCIONARIOS = {
    "carlos": ("CARLOS EDUARDO SILVA", "458.712.903-88", "1001"),
    "maria": ("MARIA FERNANDA COSTA", "619.204.881-97", "1002"),
    "roberto": ("ROBERTO ALMEIDA MENDES", "812.340.911-78", "1003"),
    "joao": ("JOAO PEDRO CAVALCANTI", "309.441.872-42", "1004"),
    "desconhecido": ("PAULO HENRIQUE TORRES", "111.444.777-35", "9999"),
}
EMPRESA = ("AGROTECH GARANHUNS LTDA", "14.589.201/0001-80")


def _pagina(doc: "fitz.Document", titulo: str, linhas: List[str], cor=(0.38, 0.13, 0.72)):
    p = doc.new_page(width=595, height=842)
    p.draw_rect(fitz.Rect(25, 25, 570, 817), color=cor, width=1.5)
    p.draw_rect(fitz.Rect(25, 25, 570, 80), color=cor, fill=cor)
    p.insert_text((40, 60), titulo, fontsize=13, color=(1, 1, 1))
    y = 120
    for l in linhas:
        p.insert_text((45, y), l, fontsize=11, color=(0.08, 0.08, 0.1))
        y += 24
    p.insert_text((150, 500), "AMOSTRA", fontsize=70, color=(0.88, 0.85, 0.93), rotate=0, render_mode=0, overlay=False)
    p.insert_text((40, 805), "Documento fictício para demonstração - Citadel IA", fontsize=7, color=(0.5, 0.5, 0.5))


def _comp(offset_meses: int = 1) -> Tuple[str, str]:
    m = HOJE.month - offset_meses
    a = HOJE.year
    while m <= 0:
        m += 12
        a -= 1
    return f"{m:02d}/{a}", f"{a}-{m:02d}"


def lote_rh_misto() -> Tuple[bytes, List[dict]]:
    """11 páginas: frente/verso, página em branco, AR rasurado, certidão vencida, CPF sem cadastro, documento de saúde."""
    doc = fitz.open()
    g: List[dict] = []
    c_br, c_iso = _comp(1)
    n, cpf, mat = FUNCIONARIOS["carlos"]
    _pagina(doc, "RECIBO DE PAGAMENTO DE SALARIO (HOLERITE)", [f"EMPREGADOR: {EMPRESA[0]}", f"COLABORADOR: {n}", f"CPF: {cpf}  MATRICULA: {mat}", f"COMPETENCIA: {c_br}",
                                                                 "SALARIO BASE: R$ 2.450,00", "INSS: R$ 220,50", "FGTS DEPOSITADO: R$ 196,00  FGTS DEVIDO: R$ 196,00", "LIQUIDO A RECEBER: R$ 2.050,30"])
    g.append({"tipo": "HOLERITE", "paginas": [1], "cpf": cpf.replace(".", "").replace("-", ""), "competencia": c_iso})
    _pagina(doc, "CARTAO DE PONTO - FOLHA DE REGISTRO DE PONTO (PAG 1/2)", [f"COLABORADOR: {n}", f"CPF: {cpf}", f"COMPETENCIA: {c_br}", "JORNADA DIARIA: 11:30", "INTERVALO: 00:30", "ENTRADA 07:00  SAIDA 19:00"])
    _pagina(doc, "CARTAO DE PONTO - FOLHA DE REGISTRO DE PONTO (PAG 2/2)", [f"COLABORADOR: {n}", f"CPF: {cpf}", f"COMPETENCIA: {c_br}", "TOTAL DE HORAS EXTRAS: 44:00", "ASSINATURA DO COLABORADOR: Carlos E. Silva"])
    g.append({"tipo": "CARTAO_PONTO", "paginas": [2, 3], "cpf": cpf.replace(".", "").replace("-", ""), "competencia": c_iso})
    d_aso = (HOJE - timedelta(days=20)).strftime("%d/%m/%Y")
    _pagina(doc, "ASO - ATESTADO DE SAUDE OCUPACIONAL (NR-07 / PCMSO)", [f"COLABORADOR: {n}", f"CPF: {cpf}", "TIPO DE EXAME: PERIODICO", f"DATA: {d_aso}", "PARECER: APTO PARA A FUNCAO", "MEDICO DO TRABALHO: DR. HENRIQUE VASCONCELOS - CRM/PE 19440"])
    g.append({"tipo": "ASO", "paginas": [4], "cpf": cpf.replace(".", "").replace("-", "")})
    doc.new_page(width=595, height=842)  # página em branco (separador)
    n2, cpf2, mat2 = FUNCIONARIOS["maria"]
    _pagina(doc, "FICHA DE ENTREGA DE EPI (NR-06)", [f"COLABORADORA: {n2}", f"CPF: {cpf2}", "EQUIPAMENTO DE PROTECAO INDIVIDUAL: luva, botina, oculos CA 41890", f"DATA: {d_aso}", "ASSINATURA DA COLABORADORA: Maria F. Costa"])
    g.append({"tipo": "FICHA_EPI", "paginas": [6], "cpf": cpf2.replace(".", "").replace("-", "")})
    _pagina(doc, "RECIBO DE PAGAMENTO DE SALARIO (HOLERITE)", [f"EMPREGADOR: {EMPRESA[0]}", f"COLABORADOR: {n2}", f"CPF: {cpf2}  MATRICULA: {mat2}", f"COMPETENCIA: {c_br}",
                                                                 "SALARIO BASE: R$ 1.800,00", "FGTS DEPOSITADO: R$ 120,00  FGTS DEVIDO: R$ 144,00", "LIQUIDO A RECEBER: R$ 1.520,10"])
    g.append({"tipo": "HOLERITE", "paginas": [7], "cpf": cpf2.replace(".", "").replace("-", ""), "competencia": c_iso})
    n3, cpf3, _ = FUNCIONARIOS["roberto"]
    _pagina(doc, "CORREIOS - AVISO DE RECEBIMENTO (AR)", ["CODIGO DE RASTREAMENTO: BR441009812BR", "REMETENTE: CITADEL IA COMPLIANCE", f"DESTINATARIO: {n3}", "ENDERECO: Av. Santo Antonio, 412 - Garanhuns/PE - CEP 55290-000",
                                                         "ASSINATURA DO RECEBEDOR: [rubrica ilegivel / RASURA no campo]", f"DOCUMENTO DO RECEBEDOR: RG 4.5??.??0 (RASURA)  CPF: {cpf3}"])
    g.append({"tipo": "AVISO_RECEBIMENTO", "paginas": [8], "cpf": cpf3.replace(".", "").replace("-", "")})
    venc = (HOJE - timedelta(days=45)).strftime("%d/%m/%Y")
    _pagina(doc, "CERTIFICADO DE REGULARIDADE DO FGTS - CRF", [f"EMPREGADOR: {EMPRESA[0]}", f"CNPJ: {EMPRESA[1]}", f"VALIDADE: {venc}", "CERTIFICA-SE A REGULARIDADE PERANTE O FGTS"])
    g.append({"tipo": "CRF_FGTS", "paginas": [9]})
    n4, cpf4, _ = FUNCIONARIOS["desconhecido"]
    _pagina(doc, "RECIBO DE PAGAMENTO DE SALARIO (HOLERITE)", [f"EMPREGADOR: {EMPRESA[0]}", f"COLABORADOR: {n4}", f"CPF: {cpf4}", f"COMPETENCIA: {c_br}", "SALARIO BASE: R$ 3.100,00", "LIQUIDO A RECEBER: R$ 2.640,00"])
    g.append({"tipo": "HOLERITE", "paginas": [10], "cpf": cpf4.replace(".", "").replace("-", ""), "competencia": c_iso})
    _pagina(doc, "ATESTADO MEDICO", [f"COLABORADOR: {n3}", f"CPF: {cpf3}", "CID: M54.5", "DIAS DE REPOUSO: 3 (AFASTAMENTO)", f"DATA: {d_aso}", "CRM/PE 20311"])
    g.append({"tipo": "ATESTADO_MEDICO", "paginas": [11], "cpf": cpf3.replace(".", "").replace("-", "")})
    b = doc.tobytes()
    doc.close()
    return b, g


def lote_grande(paginas: int = 60) -> Tuple[bytes, List[dict]]:
    """Lote longo para o teste de caos (matar worker e IA Core no meio): holerite + cartão de ponto de 4 funcionários × meses."""
    doc = fitz.open()
    g: List[dict] = []
    pessoas = ["carlos", "maria", "roberto", "joao"]
    i = 0
    while len(doc) < paginas:
        for k in pessoas:
            if len(doc) >= paginas - 1:
                break
            n, cpf, mat = FUNCIONARIOS[k]
            c_br, c_iso = _comp(1 + i // len(pessoas))
            _pagina(doc, "RECIBO DE PAGAMENTO DE SALARIO (HOLERITE)", [f"COLABORADOR: {n}", f"CPF: {cpf}  MATRICULA: {mat}", f"COMPETENCIA: {c_br}", "SALARIO BASE: R$ 2.000,00", "LIQUIDO A RECEBER: R$ 1.700,00"])
            g.append({"tipo": "HOLERITE", "paginas": [len(doc)], "cpf": cpf.replace(".", "").replace("-", ""), "competencia": c_iso})
            _pagina(doc, "CARTAO DE PONTO (PAG 1/1)", [f"COLABORADOR: {n}", f"CPF: {cpf}", f"COMPETENCIA: {c_br}", "JORNADA DIARIA: 08:00", "INTERVALO: 01:00"])
            g.append({"tipo": "CARTAO_PONTO", "paginas": [len(doc)], "cpf": cpf.replace(".", "").replace("-", ""), "competencia": c_iso})
            i += 1
    b = doc.tobytes()
    doc.close()
    return b, g


def gravar_amostras(destino: str) -> Dict[str, str]:
    os.makedirs(destino, exist_ok=True)
    out = {}
    for nome, fn in (("Lote_RH_Misto_11pags.pdf", lote_rh_misto), ("Lote_Grande_60pags.pdf", lambda: lote_grande(60))):
        b, g = fn()
        p = os.path.join(destino, nome)
        with open(p, "wb") as f:
            f.write(b)
        out[nome] = p
    return out


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "samples")
    for k, v in gravar_amostras(dest).items():
        print(k, "->", v)
