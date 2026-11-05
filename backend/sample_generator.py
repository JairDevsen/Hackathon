"""
Gerador de Lotes Oficiais Bernhoeft (Gestão de Riscos com Terceiros, SST, Trabalhista e AR)
Responsável na Equipe: Thaynara (Dev 6 - Squad 3)
"""
from pathlib import Path
import fitz  # PyMuPDF

SAMPLES_DIR = Path(__file__).resolve().parent / "storage" / "samples"


def ensure_sample_batches() -> dict:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    lote1_path = SAMPLES_DIR / "Lote_Bernhoeft_Mobilizacao_GRT_AR_Manuscrito_6pags.pdf"
    lote2_path = SAMPLES_DIR / "Lote_Bernhoeft_CalculoJudicial_AR_Rasurado_2pags.pdf"

    _build_lote_1_bernhoeft(lote1_path)
    _build_lote_2_critico(lote2_path)

    return {
        "lote_completo": lote1_path,
        "lote_hitl": lote2_path,
    }


def _build_lote_1_bernhoeft(out_path: Path) -> None:
    doc = fitz.open()

    # =========================================================================
    # PÁGINA 1: CNH (FRENTE) - Mobilização de Terceiro Bernhoeft (Pág 1 de 2)
    # =========================================================================
    p1 = doc.new_page(width=595, height=842)
    p1.draw_rect(fitz.Rect(25, 25, 570, 817), color=(0.08, 0.38, 0.24), fill=(0.95, 0.99, 0.96), width=2)
    p1.draw_rect(fitz.Rect(25, 25, 570, 95), color=(0.06, 0.32, 0.20), fill=(0.06, 0.32, 0.20))
    p1.insert_text((45, 55), "DOSSIE DE MOBILIZACAO DE TERCEIROS (GRT BERNHOEFT)", fontsize=13, color=(1, 1, 1))
    p1.insert_text((45, 78), "CARTEIRA NACIONAL DE HABILITACAO - CNH (FRENTE - PAG 1/2)", fontsize=11, color=(0.8, 1, 0.85))

    p1.draw_rect(fitz.Rect(42, 185, 550, 245), color=(0.4, 0.6, 0.45), fill=(1, 1, 1))
    p1.insert_text((50, 202), "COLABORADOR TERCEIRIZADO (MOTORISTA / OPERADOR DE PLANTA)", fontsize=8, color=(0.3, 0.4, 0.3))
    p1.insert_text((50, 226), "CARLOS EDUARDO SILVA", fontsize=15, color=(0.05, 0.05, 0.05))

    p1.draw_rect(fitz.Rect(42, 285, 550, 345), color=(0.4, 0.6, 0.45), fill=(1, 1, 1))
    p1.insert_text((50, 302), "DOCUMENTO DE IDENTIDADE / ORGAO EMISSOR / CPF", fontsize=8, color=(0.3, 0.4, 0.3))
    p1.insert_text((50, 326), "RG: 7.891.234 SDS/PE    |    CPF: 458.712.903-44", fontsize=13, color=(0.05, 0.05, 0.05))

    p1.draw_rect(fitz.Rect(42, 370, 550, 440), color=(0.4, 0.6, 0.45), fill=(1, 1, 1))
    p1.insert_text((50, 390), "DATA NASCIMENTO: 14/08/1991    |    CATEGORIA HABILITACAO: AB", fontsize=11, color=(0.1, 0.1, 0.1))
    p1.insert_text((50, 418), "N REGISTRO: 04918273645        |    VALIDADE CNH: 10/11/2030 (APTO)", fontsize=11, color=(0.1, 0.1, 0.1))

    p1.draw_rect(fitz.Rect(42, 540, 550, 625), color=(0.4, 0.6, 0.45), fill=(1, 1, 1))
    p1.insert_text((50, 560), "PRESTADORA VINCULADA NO PORTAL DE TERCEIROS:", fontsize=9, color=(0.3, 0.4, 0.3))
    p1.insert_text((50, 585), "FORNECEDOR: AGROTECH SERVICOS & LOGISTICA LTDA (CNPJ 14.589.201/0001-88)", fontsize=10, color=(0.1, 0.1, 0.1))
    p1.insert_text((45, 790), "CONTINUA NO VERSO -> AGRUPAMENTO AUTOMATICO DE PAGINAS (1 E 2)", fontsize=9, color=(0.2, 0.4, 0.25))

    # =========================================================================
    # PÁGINA 2: CNH (VERSO) - Mobilização de Terceiro Bernhoeft (Pág 2 de 2)
    # =========================================================================
    p2 = doc.new_page(width=595, height=842)
    p2.draw_rect(fitz.Rect(25, 25, 570, 817), color=(0.08, 0.38, 0.24), fill=(0.95, 0.99, 0.96), width=2)
    p2.draw_rect(fitz.Rect(25, 25, 570, 90), color=(0.06, 0.32, 0.20), fill=(0.06, 0.32, 0.20))
    p2.insert_text((45, 55), "CARTEIRA NACIONAL DE HABILITACAO - CNH (VERSO - PAG 2/2)", fontsize=13, color=(1, 1, 1))
    p2.insert_text((45, 75), "VALIDACAO DE REQUISITO PARA ACESSO A PLANTA INDUSTRIAL - GRT", fontsize=10, color=(0.8, 1, 0.85))

    p2.draw_rect(fitz.Rect(42, 130, 550, 290), color=(0.4, 0.6, 0.45), fill=(1, 1, 1))
    p2.insert_text((55, 155), "OBSERVACOES DO CONDUTOR TERCEIRIZADO:", fontsize=10, color=(0.2, 0.3, 0.2))
    p2.insert_text((55, 185), "- EXERCE ATIVIDADE REMUNERADA (EAR) - NR-11 / NR-12 VALIDADO", fontsize=11, color=(0.05, 0.05, 0.05))
    p2.insert_text((55, 212), "- TITULAR: CARLOS EDUARDO SILVA | CPF: 458.712.903-44", fontsize=11, color=(0.05, 0.05, 0.05))
    p2.insert_text((55, 240), "- POLO OPERACIONAL: GARANHUNS / RECIFE - PE", fontsize=11, color=(0.05, 0.05, 0.05))

    p2.draw_rect(fitz.Rect(42, 620, 550, 710), color=(0.4, 0.6, 0.45), fill=(1, 1, 1))
    p2.insert_text((55, 645), "ASSINATURA DO PORTADOR: Carlos Eduardo Silva", fontsize=13, color=(0.05, 0.15, 0.55))
    p2.insert_text((55, 680), "FIM DO DOCUMENTO CNH (AGRUPADO NAS PAGINAS 1 E 2)", fontsize=9, color=(0.3, 0.3, 0.3))

    # =========================================================================
    # PÁGINA 3: AR DOS CORREIOS (NOTIFICAÇÃO DE COMPLIANCE TRABALHISTA BERNHOEFT)
    # =========================================================================
    p3 = doc.new_page(width=595, height=842)
    p3.draw_rect(fitz.Rect(25, 25, 570, 817), color=(0.75, 0.55, 0.05), fill=(1.0, 0.985, 0.90), width=2.5)
    p3.draw_rect(fitz.Rect(25, 25, 570, 95), color=(0.95, 0.78, 0.08), fill=(0.98, 0.82, 0.12))
    p3.insert_text((42, 55), "CORREIOS - AVISO DE RECEBIMENTO (AR) - AUDITORIA GRT", fontsize=15, color=(0.05, 0.15, 0.45))
    p3.insert_text((42, 78), "NOTIFICACAO DE PENDENCIA DOCUMENTAL / COMPLIANCE TRABALHISTA", fontsize=10, color=(0.1, 0.1, 0.2))

    p3.draw_rect(fitz.Rect(42, 115, 550, 195), color=(0.3, 0.3, 0.3), fill=(1, 1, 1))
    p3.insert_text((55, 138), "CODIGO DE RASTREAMENTO DO OBJETO (ETIQUETA AR):", fontsize=9, color=(0.3, 0.3, 0.3))
    p3.insert_text((55, 165), "BR 984 512 390 BR", fontsize=18, color=(0.05, 0.05, 0.05))
    for bx in range(310, 530, 6):
        w_bar = 3 if (bx % 12 == 0) else 1.5
        p3.draw_rect(fitz.Rect(bx, 130, bx + w_bar, 182), color=(0, 0, 0), fill=(0, 0, 0))

    p3.draw_rect(fitz.Rect(42, 245, 550, 355), color=(0.3, 0.3, 0.3), fill=(1, 1, 1))
    p3.insert_text((52, 265), "1. DESTINATARIO (FORNECEDOR TERCEIRIZADO AUDITADO):", fontsize=9, color=(0.3, 0.3, 0.3))
    p3.insert_text((52, 288), "ROBERTO ALMEIDA MENDES (PREPOSTO AGROTECH SERVICOS)", fontsize=12, color=(0, 0, 0))
    p3.insert_text((52, 312), "ENDERECO: Av. Santo Antonio, 412 - Centro - Garanhuns/PE", fontsize=11, color=(0.1, 0.1, 0.1))
    p3.insert_text((52, 336), "CEP: 55290-000   |   TELEFONE: (87) 99812-4410", fontsize=11, color=(0.1, 0.1, 0.1))

    p3.draw_rect(fitz.Rect(42, 370, 550, 460), color=(0.3, 0.3, 0.3), fill=(1, 1, 1))
    p3.insert_text((52, 392), "2. REMETENTE: BERNHOEFT - GESTAO DE RISCOS COM TERCEIROS & COMPLIANCE", fontsize=10, color=(0.1, 0.1, 0.1))
    p3.insert_text((52, 418), "3. TENTATIVAS DE ENTREGA:  [X] 1a (05/11/2026 as 14:20h)   [ ] 2a   [ ] 3a", fontsize=10, color=(0.1, 0.1, 0.1))
    p3.insert_text((52, 442), "CONTEUDO: NOTIFICACAO DE REGULARIZACAO FGTS / INSS / SST", fontsize=9, color=(0.05, 0.45, 0.15))

    p3.draw_rect(fitz.Rect(42, 565, 550, 655), color=(0.1, 0.2, 0.6), fill=(1, 1, 1), width=1.5)
    p3.insert_text((52, 585), "ASSINATURA DO RECEBEDOR (MANUSCRITO A CANETA):", fontsize=9, color=(0.2, 0.2, 0.2))
    p3.insert_text((65, 622), "Roberto A. Mendes   [Rubrica Manuscrita Confirmada]", fontsize=15, color=(0.05, 0.18, 0.72))
    p3.insert_text((380, 622), "DATA: 05/11/2026", fontsize=13, color=(0.05, 0.18, 0.72))

    p3.draw_rect(fitz.Rect(42, 670, 550, 755), color=(0.1, 0.2, 0.6), fill=(1, 1, 1), width=1.5)
    p3.insert_text((52, 690), "NOME LEGIVEL DO RECEBEDOR E N DOCUMENTO (ESCRITO A MAO):", fontsize=9, color=(0.2, 0.2, 0.2))
    p3.insert_text((60, 725), "Roberto Almeida Mendes  -  RG: 4.512.890 SSP/PE  CPF: 812.340.911-20", fontsize=12, color=(0.05, 0.18, 0.72))

    # =========================================================================
    # PÁGINA 4: FICHA DE EPI / DECLARAÇÃO TRABALHISTA MANUSCRITA (COM RASURA -> HITL)
    # =========================================================================
    p4 = doc.new_page(width=595, height=842)
    p4.draw_rect(fitz.Rect(25, 25, 570, 817), color=(0.6, 0.6, 0.6), fill=(0.99, 0.99, 0.97), width=1.5)
    for ly in range(120, 780, 32):
        p4.draw_line(fitz.Point(40, ly), fitz.Point(555, ly), color=(0.82, 0.88, 0.95), width=0.7)
    p4.draw_line(fitz.Point(68, 90), fitz.Point(68, 790), color=(0.92, 0.65, 0.65), width=1)

    p4.insert_text((78, 112), "TERMO MANUSCRITO DE ENTREGA DE EPI & APONTAMENTO DE HORAS (SST/GRT)", fontsize=11.5, color=(0.08, 0.18, 0.62))
    p4.insert_text((78, 176), "Eu, Maria Fernanda Costa, portadora do CPF 619.204.881-90", fontsize=13, color=(0.08, 0.18, 0.65))
    p4.insert_text((78, 208), "e RG 3.918.442 SDS-PE, colaboradora terceirizada, declaro de", fontsize=13, color=(0.08, 0.18, 0.65))
    p4.insert_text((78, 240), "proprio punho que recebi os Equipamentos de Protecao (NR-06):", fontsize=13, color=(0.08, 0.18, 0.65))
    p4.insert_text((78, 272), "- Capacete e Botina Seguranca CA n 41.890 + Luva Isolante.", fontsize=13, color=(0.08, 0.18, 0.65))
    p4.insert_text((78, 336), "Ressalva manuscrita com rasura no apontamento para Calculo Judicial:", fontsize=11.5, color=(0.55, 0.20, 0.15))
    p4.insert_text((78, 368), "Saldo de Horas Extras / Adicional Periculosidade: R$ 4.850,00 (rasurado)", fontsize=12, color=(0.55, 0.20, 0.15))
    p4.insert_text((78, 608), "Local e Data: Garanhuns, 05 de Novembro de 2026", fontsize=13, color=(0.08, 0.18, 0.65))
    p4.insert_text((78, 665), "Assinatura a mao da colaboradora: Maria Fernanda Costa", fontsize=14, color=(0.05, 0.12, 0.55))

    # =========================================================================
    # PÁGINA 5 e 6: CONTRATO DE TERCEIRIZAÇÃO & ANEXO SST/ASO (2 PÁGINAS AGRUPADAS)
    # =========================================================================
    p5 = doc.new_page(width=595, height=842)
    p5.draw_rect(fitz.Rect(30, 30, 565, 812), color=(0.2, 0.25, 0.35), fill=(1, 1, 1), width=1.5)
    p5.insert_text((50, 70), "CONTRATO DE PRESTACAO DE SERVICOS TERCEIRIZADOS (PAGINA 1/2)", fontsize=12.5, color=(0.1, 0.1, 0.2))
    p5.insert_text((50, 115), "PRESTADORA: AGROTECH GARANHUNS LTDA - CNPJ: 14.589.201/0001-88", fontsize=11, color=(0.1, 0.1, 0.1))
    p5.insert_text((50, 145), "RESPONSAVEL TECNICO: JOAO PEDRO CAVALCANTI - CPF: 309.441.872-15", fontsize=11, color=(0.1, 0.1, 0.1))
    p5.insert_text((50, 190), "CLAUSULA DE CONFORMIDADE TRABALHISTA E PREVIDENCIARIA (PADRAO BERNHOEFT):", fontsize=10.5, color=(0, 0, 0))
    p5.insert_text((50, 215), "A contratada obriga-se a apresentar mensalmente no Portal de Gestao de Terceiros", fontsize=10, color=(0.2, 0.2, 0.2))
    p5.insert_text((50, 235), "as guias FGTS Digital, eSocial, Folha Analitica (FOPAG), CNDs, ASO e Fichas EPI.", fontsize=10, color=(0.2, 0.2, 0.2))
    p5.insert_text((50, 770), "Continua na Pagina 2 do Contrato (Anexo de Assinaturas e Responsabilidade Subsidiaria)...", fontsize=9, color=(0.4, 0.4, 0.4))

    p6 = doc.new_page(width=595, height=842)
    p6.draw_rect(fitz.Rect(30, 30, 565, 812), color=(0.2, 0.25, 0.35), fill=(1, 1, 1), width=1.5)
    p6.insert_text((50, 70), "CONTRATO DE PRESTACAO DE SERVICOS TERCEIRIZADOS (PAGINA 2/2)", fontsize=12.5, color=(0.1, 0.1, 0.2))
    p6.insert_text((50, 115), "CLAUSULA QUINTA - PROTECAO DE DADOS (LGPD) E AUDITORIA CONTINUA:", fontsize=11, color=(0, 0, 0))
    p6.insert_text((50, 145), "Os dados pessoais e sensiveis dos colaboradores terceirizados sao anonimizados.", fontsize=10, color=(0.2, 0.2, 0.2))
    p6.draw_rect(fitz.Rect(50, 620, 540, 710), color=(0.4, 0.4, 0.4), fill=(0.98, 0.98, 0.98))
    p6.insert_text((65, 655), "ASSINATURA CONTRATADA: Joao Pedro Cavalcanti (CPF: 309.441.872-15)", fontsize=11, color=(0.05, 0.15, 0.5))
    p6.insert_text((65, 685), "FIM DO CONTRATO DE TERCEIRIZACAO (AGRUPADO: PAGINAS 5 E 6)", fontsize=9, color=(0.3, 0.3, 0.3))

    doc.save(str(out_path))
    doc.close()


def _build_lote_2_critico(out_path: Path) -> None:
    doc = fitz.open()

    # Página 1: AR com caligrafia muito borrada / rasurada
    p1 = doc.new_page(width=595, height=842)
    p1.draw_rect(fitz.Rect(25, 25, 570, 817), color=(0.75, 0.35, 0.1), fill=(1.0, 0.97, 0.92), width=2)
    p1.insert_text((45, 60), "CORREIOS - AVISO DE RECEBIMENTO (AR) - NOTIFICACAO DE BLOQUEIO GRT", fontsize=13, color=(0.6, 0.1, 0.1))
    p1.insert_text((45, 130), "CODIGO RASTREIO: BR 441 009 812 BR", fontsize=15, color=(0.1, 0.1, 0.1))
    p1.insert_text((45, 270), "DESTINATARIO: ROBERTO ALMEIDA MENDES - CEP: 55290-000", fontsize=12, color=(0.1, 0.1, 0.1))
    p1.insert_text((45, 600), "ASSINATURA MANUSCRITA ILEGIVEL / BORRADA: [Riscos Ilegiveis a Caneta]", fontsize=13, color=(0.5, 0.2, 0.2))
    p1.insert_text((45, 700), "RG DO RECEBEDOR MANUSCRITO COM RASURA: 4.5??.??0 SSP/PE", fontsize=12, color=(0.6, 0.1, 0.1))

    # Página 2: ASO - Atestado de Saúde Ocupacional (SST Bernhoeft)
    p2 = doc.new_page(width=595, height=842)
    p2.draw_rect(fitz.Rect(25, 25, 570, 817), color=(0.1, 0.45, 0.55), fill=(0.97, 0.99, 1.0), width=2)
    p2.insert_text((45, 60), "ASO - ATESTADO DE SAUDE OCUPACIONAL (NR-07 / SST BERNHOEFT)", fontsize=13.5, color=(0.05, 0.25, 0.45))
    p2.insert_text((45, 180), "COLABORADOR: CARLOS EDUARDO SILVA | CPF: 458.712.903-44", fontsize=12, color=(0.1, 0.1, 0.1))
    p2.insert_text((45, 230), "FUNCAO: OPERADOR DE EMPILHADEIRA | RISCOS: RUIDO, ERGONOMICO", fontsize=11, color=(0.1, 0.1, 0.1))
    p2.insert_text((45, 280), "PARECER MEDICO OCUPACIONAL: [X] APTO PARA A FUNCAO (NR-11 / NR-35)", fontsize=12, color=(0.05, 0.45, 0.2))
    p2.insert_text((45, 360), "MEDICO DO TRABALHO: DR. HENRIQUE VASCONCELOS - CRM/PE 19.440", fontsize=11, color=(0.1, 0.1, 0.1))

    doc.save(str(out_path))
    doc.close()
