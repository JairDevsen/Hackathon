#!/usr/bin/env python3
"""E2E da DESCOBERTA de tipos documentais pela IA (API + worker + IA Core com modelo falso + Postgres + Redis).

Fase 1 (banco recém-migrado e semeado): a IA reconhece um tipo que o catálogo não tinha, o backend o registra, e o segundo documento do mesmo
tipo é reconhecido localmente (Camada 1), sem nova chamada ao modelo. Fase 2 (depois de REINICIAR o IA Core): o tipo aprendido volta pelo
catálogo do backend e continua custando zero.

Passo a passo: suba o IA Core com o servidor falso (ver o cabeçalho de fake_openai.py), depois
  API=http://localhost:8080 python scripts/e2e_descoberta_tipos.py 1 /caminho/chamadas.log
  (reinicie o IA Core)
  API=http://localhost:8080 python scripts/e2e_descoberta_tipos.py 2 /caminho/chamadas.log"""
import os, sys, time, json
from e2e_smoke_lib import *
import fitz as _fz
FASE, LOG = sys.argv[1], sys.argv[2]
def chamadas(): return [json.loads(l) for l in open(LOG)] if os.path.exists(LOG) else []
def pdf(paginas):
    d = _fz.open()
    for linhas in paginas:
        pg = d.new_page(width=595, height=842)
        for i, l in enumerate(linhas): pg.insert_text((50, 80 + 22 * i), l, fontsize=11)
    b = d.tobytes(); d.close(); return b
def lote(nome, conteudo):
    r = c.post(f"{API}/batches", headers=H(rh), files={"file": (nome, conteudo)}); assert r.status_code == 202, r.text; bid = r.json()["id"]
    for _ in range(90):
        b = get(rh, f"/batches/{bid}")
        if b["status"].startswith("PROCESSADO") or b["status"] == "FALHOU": break
        time.sleep(1)
    assert b["status"].startswith("PROCESSADO"), (b["status"], b.get("erro")); return b
rh = login("rh@agrotech.demo", "Demo!Citadel#2026"); master = login("master@citadel.local", "Citadel!Master#2026")

if FASE == "1":

    print("A. migração: catálogo com os 14 tipos estáticos novos e colunas origem/pistas")
    tipos = {t["codigo"]: t for t in get(rh, "/document-types")}
    assert len(tipos) == 58 and {"NOTA_FISCAL", "CARTAO_CNPJ", "TITULO_ELEITOR", "PROTOCOLO_ENTREGA", "ALVARA_LICENCA"} <= set(tipos), len(tipos)
    assert all(t["origem"] == "CATALOGO" for t in tipos.values()); ok("58 tipos, todos curados")

    print("B. IA descobre um tipo novo (Termo de confidencialidade)")
    nda1 = pdf([["TERMO DE CONFIDENCIALIDADE E SIGILO", "Pelo presente instrumento, o COLABORADOR compromete-se a manter sigilo das informacoes da empresa.", "Nome: JOSE ALVES DA SILVA", "CPF: 746.023.188-60", "Local e data: Recife, 05/11/2026", "Assinatura do colaborador: ________________"]])
    b1 = lote("nda1.pdf", nda1)
    d1 = b1["documentos"]; assert len(d1) == 1 and d1[0]["document_type"] == "TERMO_DE_CONFIDENCIALIDADE", [(d["document_type"]) for d in d1]
    assert b1["resumo"]["tipos_novos"] == ["Termo de confidencialidade"], b1["resumo"]; ok(f"documento classificado como {d1[0]['document_type']}, resumo: {b1['resumo']['tipos_novos']}")
    cat = {t["codigo"]: t for t in get(master, "/admin/document-types")}
    t = cat["TERMO_DE_CONFIDENCIALIDADE"]; assert t["origem"] == "IA" and t["escopo"] == "FUNCIONARIO" and t["categoria"] == "ADMISSAO", t
    assert "TERMO DE CONFIDENCIALIDADE E SIGILO" in t["pistas"] and not any("INVENTADA" in p for p in t["pistas"]) and len(t["pistas"]) == 2, t["pistas"]; ok(f"catálogo global: origem IA, pistas conferidas no texto {t['pistas']} (a inventada foi barrada)")
    assert t["documentos"] == 1; ok("catálogo conta os documentos do tipo")
    sch = get(rh, "/document-types/TERMO_DE_CONFIDENCIALIDADE/schema"); assert "cpf" in sch["properties"]; ok("formulário de revisão disponível para o tipo novo")
    al = [a for a in (get(rh, f"/documents/{d1[0]['id']}").get("alertas") or []) if a["codigo"] == "TIPO_IA"]; assert al, "alerta TIPO_IA"; ok("documento traz o alerta informativo TIPO_IA")
    n_antes = len(chamadas()); assert n_antes >= 1, n_antes

    print("C. segundo documento do mesmo tipo: reconhecido localmente, sem chamar o modelo")
    nda2 = pdf([["TERMO DE CONFIDENCIALIDADE E SIGILO", "O colaborador compromete-se a manter sigilo de toda informacao a que tiver acesso na empresa e apos o desligamento.", "Nome: MARIA FERNANDA COSTA", "CPF: 529.982.247-25", "Local e data: Recife, 06/11/2026", "Assinatura do colaborador: ________________"]])
    b2 = lote("nda2.pdf", nda2)
    d2 = b2["documentos"]; assert len(d2) == 1 and d2[0]["document_type"] == "TERMO_DE_CONFIDENCIALIDADE", [(d["document_type"]) for d in d2]
    assert not b2["resumo"].get("tipos_novos"), b2["resumo"]
    assert len(chamadas()) == n_antes, (n_antes, len(chamadas())); ok("sem nenhuma chamada nova ao modelo: o tipo foi aprendido (Camada 1, custo zero)")
    det = get(rh, f"/documents/{d2[0]['id']}"); camada = (det.get("finops") or {}).get("camada_roteamento", ""); assert camada.startswith("Camada 1"), camada; ok(camada)

    print("D. folha separadora e folha em branco não viram documento")
    sep = pdf([["SEPARADOR DE DOCUMENTOS", "Competencia 03/2026"], ["TERMO DE CONFIDENCIALIDADE E SIGILO", "O colaborador compromete-se a manter sigilo.", "Nome: JOSE ALVES DA SILVA", "CPF: 746.023.188-60"], ["Esta pagina foi intencionalmente deixada em branco"]])
    b3 = lote("sep.pdf", sep); assert len(b3["documentos"]) == 1 and b3["resumo"]["paginas_em_branco"] == 2, (len(b3["documentos"]), b3["resumo"]); ok("2 folhas ignoradas, 1 documento")

    print("E. Master confirma o tipo")
    assert t["revisado_em"] is None
    assert c.patch(f"{API}/admin/document-types/{t['id']}", headers=H(master), json={"revisado": True, "nome": "Termo de confidencialidade (NDA)"}).status_code == 204
    t2 = {x["codigo"]: x for x in get(master, "/admin/document-types")}["TERMO_DE_CONFIDENCIALIDADE"]
    assert t2["origem"] == "IA" and t2["revisado_em"] and t2["nome"].endswith("(NDA)") and t2["pistas"] == t["pistas"]; ok("tipo confirmado e renomeado; a origem IA e as pistas aprendidas continuam")
    print("OK — descoberta de tipos ponta a ponta")
else:
    antes = len(chamadas())
    nda3 = pdf([["TERMO DE CONFIDENCIALIDADE E SIGILO", "O colaborador compromete-se a manter sigilo das informacoes confidenciais da empresa contratante.", "Nome: JULIANA PEREIRA LIMA", "CPF: 529.982.247-25", "Local e data: Recife, 07/11/2026"]])
    r = c.post(f"{API}/batches", headers=H(rh), files={"file": ("nda3.pdf", nda3)}); assert r.status_code == 202, r.text; bid = r.json()["id"]
    for _ in range(90):
        b = get(rh, f"/batches/{bid}")
        if b["status"].startswith("PROCESSADO") or b["status"] == "FALHOU": break
        time.sleep(1)
    assert b["status"].startswith("PROCESSADO"), b["status"]
    assert [d["document_type"] for d in b["documentos"]] == ["TERMO_DE_CONFIDENCIALIDADE"], b["documentos"]
    assert len(chamadas()) == antes, (antes, len(chamadas())); ok("IA Core reiniciado: o tipo aprendido voltou pelo catálogo do backend e o documento fechou na Camada 1, sem modelo")
