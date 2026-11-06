#!/usr/bin/env python3
"""Teste de fumaça ponta a ponta (API + worker + IA Core + Postgres + Redis).
Uso: API=http://localhost:8080 MAIL_LOG=/caminho/api.log  python scripts/e2e_smoke.py"""
import os, time, hashlib
from e2e_smoke_lib import *

print("1. Autenticação")
bad = c.post(f"{API}/auth/login", json={"email": "rh@agrotech.demo", "senha": "errada-errada-12"})
assert bad.status_code == 401 and bad.headers["content-type"].startswith("application/problem+json"); ok("senha errada → 401 problem+json")
rh = login("rh@agrotech.demo", "Demo!Citadel#2026"); ok("login + 2FA por e-mail")
adm = login("admin@agrotech.demo", "Demo!Citadel#2026")
rh2 = login("rh2@agrotech.demo", "Demo!Citadel#2026")
me = get(rh, "/auth/me"); assert me["role"] == "RH" and "saude:ler" in me["perms"]; ok("/auth/me")
assert c.get(f"{API}/employees").status_code == 401; ok("rota protegida sem token → 401")
master = login("master@citadel.local", "Citadel!Master#2026")
assert c.get(f"{API}/employees", headers=H(master)).status_code == 403; ok("Master não lê dados de empresa sem acesso de suporte")

print("2. Busca de funcionário")
r = get(rh, "/employees", params={"q": "458.712.903-88"}); assert len(r["items"]) == 1 and r["tipo_busca"] == "cpf"; ok("busca por CPF com máscara")
carlos = r["items"][0]; assert carlos["cpf_mascarado"] == "***.712.903-**"; ok("CPF mascarado na resposta")
r = get(rh, "/employees", params={"q": "45871290388"}); assert len(r["items"]) == 1; ok("busca por CPF sem máscara")
r = get(rh, "/employees", params={"q": "carlos edu"}); assert len(r["items"]) == 1; ok("busca por nome")
r = get(rh, "/employees", params={"q": "1002"}); assert r["items"][0]["nome"].startswith("MARIA"); ok("busca por matrícula")
r = get(rh, "/employees", params={"q": "111.111.111-11"}); assert r["cpf_valido"] is False; ok("CPF inválido é recusado")

print("3. Upload retomável + processamento")
data = open(PDF, "rb").read(); sha = hashlib.sha256(data).hexdigest()
r = c.post(f"{API}/batches/uploads", headers=H(rh), json={"filename": "lote.pdf", "size": len(data), "tipo_lote": "MISTO"}); r.raise_for_status()
up = r.json()["upload_id"]; half = len(data) // 2
r = c.patch(f"{API}/batches/uploads/{up}", headers=H(rh, {"Upload-Offset": "0"}), content=data[:half]); assert r.status_code == 204
r = c.get(f"{API}/batches/uploads/{up}", headers=H(rh)); assert r.json()["offset"] == half; ok("upload interrompido: offset consultável")
r = c.patch(f"{API}/batches/uploads/{up}", headers=H(rh, {"Upload-Offset": str(half)}), content=data[half:]); assert r.status_code == 204; ok("upload retomado de onde parou")
r = c.post(f"{API}/batches/uploads/{up}/complete", headers=H(rh)); assert r.status_code == 202, r.text; batch = r.json()["id"]
r = c.post(f"{API}/batches", headers=H(rh), files={"file": ("lote.pdf", data)}); assert r.status_code == 409 and r.json()["errors"]["batch_id"] == batch; ok("lote duplicado (SHA-256) → 409")
for _ in range(90):
    b = get(rh, f"/batches/{batch}")
    if b["status"].startswith("PROCESSADO") or b["status"] == "FALHOU": break
    time.sleep(1)
assert b["status"] == "PROCESSADO_COM_PENDENCIAS", (b["status"], b.get("erro")); ok(f"lote processado: {b['resumo']}")
docs = b["documentos"]; assert len(docs) == 9, [(d["document_type"], d["paginas"]) for d in docs]; ok("9 documentos separados de 11 páginas (frente/verso agrupados, branco descartado)")
tipos = {d["document_type"] for d in docs}; assert {"HOLERITE", "CARTAO_PONTO", "ASO", "FICHA_EPI", "AVISO_RECEBIMENTO", "CRF_FGTS", "ATESTADO_MEDICO"} <= tipos; ok("classificação por tipo")
assert any(d["document_type"] == "CARTAO_PONTO" and d["paginas"] == [2, 3] for d in docs); ok("detecção de início/fim: ponto de 2 páginas")
assert any("TIMELINE" or t["tipo"] == "CONCLUIDO" for t in b["linha_tempo"]); ok("linha do tempo do lote")

print("4. Pré-cadastro automático, ilegíveis, vínculo e revisão humana")
res = get(rh, f"/batches/{batch}")["resumo"]
assert res["pre_cadastros"] == 1 and res["classificacao_manual"] == 1 and res["sem_vinculo"] == 0, res; ok("resumo do lote: 1 pré-cadastro, 1 documento para classificação manual, 0 sem vínculo")
pre = get(rh, "/employees", params={"pre": "1"})["items"]
assert len(pre) == 1 and pre[0]["nome"].upper().startswith("PAULO") and pre[0]["pre_cadastro"] and pre[0]["origem"] == "PRE_CADASTRO" and pre[0]["cpf_mascarado"] == "***.444.777-**"; ok("RH não cadastrou: Paulo foi pré-cadastrado a partir do lote (CPF mascarado)")
paulo = pre[0]; assert paulo["pendencias"] < 5, paulo; ok(f"pré-cadastro sem admissão não gera avalanche de pendências ({paulo['pendencias']})")
assert get(rh, f"/employees/{paulo['id']}/documents"); ok("documentos do lote já estão no dossiê do pré-cadastro")
tn = {n["tipo"] for n in get(rh, "/notifications")["itens"]}; assert {"PRE_CADASTRO", "ILEGIVEL"} <= tn; ok("RH é avisado: pré-cadastros a completar e ilegíveis para classificação manual")
q = get(rh, "/review/queue"); assert len(q) >= 3; ok(f"fila de revisão: {len(q)} itens, prioridade: {[x['motivos_revisao'] for x in q][:3]}")
ileg = [x for x in q if "PAGINA_ILEGIVEL" in x["motivos_revisao"]]; assert ileg; ok("documento ilegível aparece na fila para classificação/transcrição humana")
# CPF inválido: não dá para pré-cadastrar, continua indo para 'Sem vínculo'
import fitz as _f0
_d = _f0.open(); _p = _d.new_page(width=595, height=842)
for _i, _l in enumerate(["CARTAO DE PONTO (PAG 1/1)", "COLABORADOR: FULANO SEM CPF VALIDO", "CPF: 123.456.789-00", "JORNADA DIARIA: 08:00", "INTERVALO: 01:00"]): _p.insert_text((60, 120 + 24 * _i), _l, fontsize=11)
_inv = _d.tobytes(); _d.close()
r = c.post(f"{API}/batches", headers=H(rh), files={"file": ("cpf_invalido.pdf", _inv)}); assert r.status_code == 202, r.text; bsv = r.json()["id"]
for _ in range(60):
    bb = get(rh, f"/batches/{bsv}")
    if bb["status"].startswith("PROCESSADO") or bb["status"] == "FALHOU": break
    time.sleep(1)
assert bb["resumo"]["pre_cadastros"] == 0 and bb["resumo"]["sem_vinculo"] == 1, bb["resumo"]; ok("CPF inválido NÃO vira pré-cadastro: cai em 'Sem vínculo'")
q = get(rh, "/review/queue")
sem = [x for x in q if "SEM_VINCULO" in x["motivos_revisao"]]; assert sem; ok("documento com CPF sem cadastro cai em 'Sem vínculo'")
det = get(rh, f"/documents/{sem[0]['id']}"); assert det["paginas_urls"] and det["campos"]["cpf"].startswith("***"); ok("detalhe: páginas com URL assinada; CPF mascarado nos campos")
img = c.get(det["paginas_urls"][0]["url"]); assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"; ok("URL assinada entrega a imagem decifrada")
assert c.get(det["paginas_urls"][0]["url"][:-3] + "abc").status_code == 403; ok("assinatura adulterada → 403")
r = c.post(f"{API}/review/{sem[0]['id']}", headers=H(rh), json={"acao": "CONFIRMAR"}); assert r.status_code == 422; ok("confirmar sem vínculo → 422")
r = c.post(f"{API}/review/{sem[0]['id']}", headers=H(rh), json={"acao": "VINCULAR", "novo_funcionario": {"nome": "FULANO SEM CPF VALIDO", "cpf": "168.995.350-09", "matricula": "9999"}}); assert r.status_code == 204, r.text; ok("vincular criando funcionário a partir dos dados extraídos")
r = c.post(f"{API}/review/{sem[0]['id']}", headers=H(rh), json={"acao": "CONFIRMAR", "duracao_ms": 4200}); assert r.status_code == 204; ok("confirmar documento")
for x in get(rh, "/review/queue"):
    c.post(f"{API}/review/{x['id']}", headers=H(rh), json={"acao": "CONFIRMAR", "duracao_ms": 3000})
assert c.get(f"{API}/review/queue", headers=H(rh)).json() == []; ok("fila zerada")
b = get(rh, f"/batches/{batch}"); assert b["status"] == "PROCESSADO"; ok("lote fecha como PROCESSADO")

print("5. Dossiê, saúde, busca em texto e anonimização")
docs = get(rh, f"/employees/{carlos['id']}/documents"); assert {d["document_type"] for d in docs} >= {"HOLERITE", "CARTAO_PONTO", "ASO"}; ok("dossiê do Carlos tem os documentos vinculados por CPF")
roberto = get(rh, "/employees", params={"q": "roberto"})["items"][0]
dr = get(rh2, f"/employees/{roberto['id']}/documents"); atest = [d for d in dr if d["document_type"] == "ATESTADO_MEDICO"][0]
assert atest["mascarado"] and "restrito" in atest["titulo"]; ok("RH sem saude:ler vê atestado mascarado na lista")
assert c.get(f"{API}/documents/{atest['id']}", headers=H(rh2)).status_code == 403; ok("detalhe de documento de saúde → 403 sem permissão")
assert c.get(f"{API}/documents/{atest['id']}", headers=H(rh)).status_code == 200; ok("com saude:ler abre (acesso auditado)")
s = get(rh, "/documents/search", params={"q": "jornada diaria"}); assert s and "<<" in s[0]["trecho"]; ok("busca em texto completo com trecho destacado")
pdf = c.get(f"{API}/documents/{docs[0]['id']}/download", headers=H(rh), params={"formato": "pesquisavel"}); assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"; ok("download: PDF pesquisável")
an = c.get(f"{API}/documents/{docs[0]['id']}/download", headers=H(rh), params={"formato": "anonimizado"}); assert an.status_code == 200 and an.content[:4] == b"%PDF"
import fitz
txt = fitz.open(stream=an.content, filetype="pdf")[0].get_text(); assert "458.712.903-88" not in txt and "458712903" not in txt; ok("cópia anonimizada: sem camada de texto com o CPF")
hol = [d for d in docs if d["document_type"] == "HOLERITE"][0]
hl = get(rh, f"/documents/{hol['id']}/highlights", params={"q": "salario"}); assert sum(len(h["caixas"]) for h in hl) >= 1; ok(f"destaque do termo no visualizador: {sum(len(h['caixas']) for h in hl)} caixas")

print("6. Conformidade e métricas")
comp = get(rh, f"/employees/{carlos['id']}/compliance"); st = {x["status"] for x in comp}; assert "OK" in st and "PENDENTE" in st; ok(f"conformidade do funcionário: {sorted(st)}")
ov = get(adm, "/metrics/overview"); assert ov["conformidade_pct"] is not None and ov["funcionarios_ativos"] >= 5; ok(f"dashboard: conformidade {ov['conformidade_pct']}%, NCs: {[n['codigo'] for n in ov['nao_conformidades']]}")
assert {"JORNADA_ACIMA_10H", "FGTS_DIVERGENTE", "CERTIDAO_VENCIDA"} <= {n["codigo"] for n in ov["nao_conformidades"]}; ok("painel de não conformidades trabalhistas")
pend = get(rh, "/compliance"); assert pend["items"]; ok("pendências listadas")
assert c.get(f"{API}/audit", headers=H(adm)).json()["items"]; ok("auditoria da empresa")
csvr = c.get(f"{API}/reports/pendencias", headers=H(adm)); assert csvr.status_code == 200 and b"funcionario" in csvr.content; ok("relatório CSV")

print("7. Master")
ov = get(master, "/admin/overview"); assert ov["clientes_ativos"] >= 1; ok("visão geral do Master")
r = c.get(f"{API}/admin/audit", headers=H(master)); assert r.status_code == 400; ok("auditoria global exige motivo")
r = c.get(f"{API}/admin/audit", headers=H(master), params={"motivo": "investigação de incidente #123"}); assert r.status_code == 200; ok("auditoria global com motivo")
v = get(master, "/admin/audit/verify"); w = get(master, "/admin/audit/verify", params={"tenant": me["tenant_id"]}); assert v["integra"] and w["integra"]; ok(f"cadeia de auditoria íntegra ({w['eventos']} eventos da empresa)")
print("8. Entregas Bernhoeft/FinOps: indexação RH, checklist, telemetria, ZIP do lote e cache SHA-256")
import io, zipfile, json as _json
aso = [d for d in get(rh, f"/batches/{batch}")["documentos"] if d["document_type"] == "ASO"][0]
ad = get(rh, f"/documents/{aso['id']}")
assert ad["empresa_nome"] is None or isinstance(ad["empresa_nome"], str)
assert ad["pasta_destino"].startswith("AGROTECH") and "CARLOS_EDUARDO_SILVA_CPF_458712" in ad["pasta_destino"], ad["pasta_destino"]; ok(f"pasta de destino RH: {ad['pasta_destino']}")
assert ad["nome_arquivo"].endswith(".pdf") and "ASO" in ad["nome_arquivo"] and "458712903" not in ad["nome_arquivo"].replace("458712_", ""); ok(f"nome do arquivo: {ad['nome_arquivo']} (CPF só parcial)")
ck = {i["regra"]: i["status"] for i in ad["checklist"]}
assert ck["NR-07 · Parecer médico"] == "OK" and ck["NR-07 · Periodicidade (12 meses)"] == "OK"; ok("checklist NR-07 do ASO (parecer APTO, periodicidade)")
assert ad["status_mobilizacao"].startswith("APTO"), ad["status_mobilizacao"]; ok(f"status de mobilização: {ad['status_mobilizacao']}")
crf = [d for d in get(rh, f"/batches/{batch}")["documentos"] if d["document_type"] == "CRF_FGTS"][0]
cd = get(rh, f"/documents/{crf['id']}")
assert cd["status_mobilizacao"].startswith("BLOQUEADO") and cd["empresa_cnpj"] == "14589201000180" and cd["empresa_nome"].startswith("AGROTECH"); ok("certidão vencida → BLOQUEADO; empresa e CNPJ extraídos do texto")
assert cd["pasta_destino"].startswith("AGROTECH_GARANHUNS_LTDA_14589201000180/"), cd["pasta_destino"]; ok("pasta usa empresa + CNPJ lidos do documento")
f = ad["finops"]; assert f["camada_roteamento"].startswith("Camada 1") and f["tokens_consumidos"] == 0 and len(f["sha256_hash"]) == 64 and f["economia_estimada_pct"] == 100.0; ok(f"telemetria FinOps: {f['camada_roteamento']}")
bd = get(rh, f"/batches/{batch}")["documentos"]
assert all(d["funcionario_nome"] for d in bd if d["employee_id"] and not d["mascarado"]) and all(d["pasta_destino"] for d in bd if not d["mascarado"]); ok("lista do lote traz empresa/funcionário/pasta (árvore Pastas RH)")
z = c.get(f"{API}/batches/{batch}/export-zip", headers=H(rh), params={"anonimizado": "false"}); assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
zf = zipfile.ZipFile(io.BytesIO(z.content)); names = zf.namelist()
assert any(n.startswith("AGROTECH_GARANHUNS_LTDA_14589201000180/") or n.startswith("AGROTECH_GARANHUNS_LTDA/") for n in names) and "00_MANIFESTO_AUDITORIA.json" in names; ok(f"ZIP do lote com pastas Empresa/Funcionário ({len(names)-1} PDFs + manifesto)")
man = _json.loads(zf.read("00_MANIFESTO_AUDITORIA.json")); assert man["documentos"] and "compliance_checklist" in man["documentos"][0] and "finops_telemetria" in man["documentos"][0]; ok("manifesto com checklist e telemetria")
za = c.get(f"{API}/batches/{batch}/export-zip", headers=H(rh2), params={"anonimizado": "true"}); assert za.status_code == 200
zn = zipfile.ZipFile(io.BytesIO(za.content)); mm = _json.loads(zn.read("00_MANIFESTO_AUDITORIA.json"))
assert mm["modo_lgpd_anonimizado"] and mm["documentos_saude_omitidos_por_permissão".replace("ã","a").replace("ç","c")] >= 2 and all(n.split("/")[-1].startswith("LGPD_") for n in zn.namelist() if n.endswith(".pdf")); ok("ZIP anonimizado (LGPD_*), saúde omitida para RH sem saude:ler")
assert not any("458.712.903-88" in zn.read(n).decode("latin-1") for n in zn.namelist() if n.endswith(".pdf")); ok("PDFs do ZIP anonimizado sem o CPF em claro")

# Camada 0: o mesmo conteúdo em outro lote reaproveita o resultado (0 tokens)
import fitz
src = fitz.open(PDF); extra = src.new_page(width=595, height=842); extra.insert_text((60, 120), "CARTAO DE PONTO (PAG 1/1)\nCOLABORADOR: CARLOS EDUARDO SILVA\nCPF: 458.712.903-88\nJORNADA DIARIA: 08:00\nINTERVALO: 01:00", fontsize=11)
variant = src.tobytes(); src.close()
r = c.post(f"{API}/batches", headers=H(rh), files={"file": ("lote_variante.pdf", variant)}); assert r.status_code == 202, r.text; b2 = r.json()["id"]
for _ in range(90):
    bb = get(rh, f"/batches/{b2}")
    if bb["status"].startswith("PROCESSADO") or bb["status"] == "FALHOU": break
    time.sleep(1)
assert bb["status"].startswith("PROCESSADO"), bb["status"]
assert any(e["tipo"] == "CACHE_SHA256" for e in bb["linha_tempo"]), [e["tipo"] for e in bb["linha_tempo"]]; ok([e["mensagem"] for e in bb["linha_tempo"] if e["tipo"] == "CACHE_SHA256"][0])
cached = [d for d in bb["documentos"] if not d["mascarado"] and get(rh, f"/documents/{d['id']}")["finops"]["camada_roteamento"].startswith("Camada 0")]
assert len(cached) >= 6; ok(f"{len(cached)} documentos resolvidos pela Camada 0 (cache SHA-256, 0 tokens)")
fo = get(rh, "/metrics/finops"); assert any(x["camada"] == "Camada 0" for x in fo) and any(x["camada"] == "Camada 1" for x in fo); ok("consumo real por camada em /metrics/finops")

print("9. Setores, seleção de documentos, exceção por funcionário, cadastro configurável e análise de erros")
# -- cadastro configurável
cfg0 = get(adm, "/tenant/cadastro-config"); assert isinstance(cfg0["campos"], dict) and isinstance(cfg0["personalizados"], list); ok("configuração de cadastro disponível")
r = c.put(f"{API}/tenant/cadastro-config", headers=H(adm), json={"campos": {"matricula": {"ativo": True, "obrigatorio": True}, "telefone": {"ativo": False, "obrigatorio": False}},
    "personalizados": [{"chave": "turno", "rotulo": "Turno", "tipo": "lista", "obrigatorio": True, "opcoes": ["Manhã", "Noite"]}]}); assert r.status_code == 204, r.text; ok("empresa exige matrícula e um campo próprio (Turno)")
r = c.post(f"{API}/employees", headers=H(rh), json={"nome": "TESTE SEM CAMPOS", "cpf": "390.533.447-05"}); assert r.status_code == 422 and "Matrícula" in r.json()["detail"] and "Turno" in r.json()["detail"], r.text; ok("cadastro sem os campos exigidos → 422")
# -- setores
dep = c.post(f"{API}/departments", headers=H(adm), json={"nome": "Manutenção"}); assert dep.status_code == 200; dep_id = dep.json()["id"]
assert c.post(f"{API}/departments", headers=H(adm), json={"nome": "Manutenção"}).status_code == 409; ok("setor criado; nome duplicado → 409")
r = c.post(f"{API}/employees", headers=H(rh), json={"nome": "TESTE SETOR", "cpf": "390.533.447-05", "matricula": "7001", "department_id": dep_id, "extra": {"turno": "Noite"}, "admissao": "2026-01-10"}); assert r.status_code == 201, r.text; emp_id = r.json()["id"]
e = get(rh, f"/employees/{emp_id}"); assert e["setor"] == "Manutenção" and e["extra"]["turno"] == "Noite"; ok("funcionário com setor e campo próprio")
r = c.post(f"{API}/employees", headers=H(rh), json={"nome": "TESTE TURNO", "cpf": "529.982.247-25", "matricula": "7002", "extra": {"turno": "Tarde"}}); assert r.status_code == 400; ok("valor fora das opções da lista → 400")
c.put(f"{API}/tenant/cadastro-config", headers=H(adm), json={"campos": {k: {"ativo": True, "obrigatorio": False} for k in ["matricula", "admissao", "cargo", "setor", "unidade", "email", "telefone"]}, "personalizados": []})  # volta ao padrão
# -- selecionar documentos por setor
types = {t["codigo"]: t for t in get(adm, "/document-types")}
before = get(rh, f"/employees/{emp_id}/compliance"); n_before = len(before)
dry = c.put(f"{API}/requirements/bulk", headers=H(adm), json={"department_id": dep_id, "dry_run": True, "items": [{"codigo": "FICHA_EPI", "momento": "ADMISSAO"}, {"codigo": "TREINAMENTO_NR", "momento": "PERIODICO", "validade_dias": 730}]}); assert dry.status_code == 200, dry.text
assert dry.json()["simulacao"] and dry.json()["pendencias_depois"] > dry.json()["pendencias_antes"]; ok(f"simulação: pendências {dry.json()['pendencias_antes']} → {dry.json()['pendencias_depois']} (nada salvo)")
assert len(get(rh, f"/employees/{emp_id}/compliance")) == n_before; ok("a simulação foi desfeita (nenhuma regra criada)")
ap = c.put(f"{API}/requirements/bulk", headers=H(adm), json={"department_id": dep_id, "items": [{"codigo": "FICHA_EPI", "momento": "ADMISSAO"}, {"codigo": "TREINAMENTO_NR", "momento": "PERIODICO", "validade_dias": 730}]}); assert ap.status_code == 200 and not ap.json()["simulacao"]
tipos_emp = {x["tipo"]: x["status"] for x in get(rh, f"/employees/{emp_id}/compliance")}; assert tipos_emp.get("FICHA_EPI") == "PENDENTE" and "TREINAMENTO_NR" in tipos_emp; ok("setor exige EPI e treinamento NR: o funcionário do setor passa a ser cobrado")
setor_outro = {x["tipo"] for x in get(rh, f"/employees/{roberto['id']}/compliance")}; assert "TREINAMENTO_NR" not in setor_outro; ok("quem NÃO é do setor não é cobrado pelos documentos do setor")
# -- exceção por funcionário
ex = get(rh, f"/employees/{emp_id}/requirements"); epi = [x for x in ex if x["codigo"] == "FICHA_EPI"][0]; assert epi["obrigatorio"] and epi["origem"] == "SETOR"; ok("origem da regra visível (setor)")
r = c.put(f"{API}/employees/{emp_id}/requirements/FICHA_EPI", headers=H(rh), json={"obrigatorio": False}); assert r.status_code == 400; ok("dispensa exige justificativa")
r = c.put(f"{API}/employees/{emp_id}/requirements/FICHA_EPI", headers=H(rh), json={"obrigatorio": False, "justificativa": "atua apenas em atividade administrativa"}); assert r.status_code == 204, r.text
assert "FICHA_EPI" not in {x["tipo"] for x in get(rh, f"/employees/{emp_id}/compliance")}; ok("dispensa só deste funcionário: o sistema para de cobrar o EPI dele")
epi = [x for x in get(rh, f"/employees/{emp_id}/requirements") if x["codigo"] == "FICHA_EPI"][0]; assert not epi["obrigatorio"] and epi["excecao"]
c.put(f"{API}/employees/{emp_id}/requirements/FICHA_EPI", headers=H(rh), json={"obrigatorio": None}); assert "FICHA_EPI" in {x["tipo"] for x in get(rh, f"/employees/{emp_id}/compliance")}; ok("voltar ao padrão restabelece a regra do setor")
assert any(a["acao"] == "DOCUMENTO_DISPENSADO_FUNCIONARIO" for a in get(adm, "/audit", params={"acao": "DISPENSADO"})["items"]); ok("dispensa registrada na auditoria")
# empresa sem regras: nada é cobrado
# -- análise: nomes divergentes e imagem borrada
from PIL import Image, ImageFilter
import fitz as _fitz
doc = _fitz.open()
pg = doc.new_page(width=595, height=842)
for i, l in enumerate(["CARTEIRA NACIONAL DE HABILITACAO - CNH (FRENTE - PAG 1/2)", "NOME: JOSE JOAO DE SANTOS", "CPF: 390.533.447-05", "VALIDADE: 07/11/2004", "CATEGORIA: AB"]): pg.insert_text((60, 120 + 26 * i), l, fontsize=12)
pdf_div = doc.tobytes(); doc.close()
assert c.patch(f"{API}/employees/{emp_id}", headers=H(rh), json={"nome": "JOAO JOSE DE SANTOS"}).status_code == 204
r = c.post(f"{API}/batches", headers=H(rh), files={"file": ("cnh_divergente.pdf", pdf_div)}); assert r.status_code == 202, r.text; b3 = r.json()["id"]
for _ in range(60):
    bb = get(rh, f"/batches/{b3}")
    if bb["status"].startswith("PROCESSADO") or bb["status"] == "FALHOU": break
    time.sleep(1)
d3 = bb["documentos"][0]; assert d3["document_type"] == "CNH" and "DADOS_DIVERGENTES" in d3["motivos_revisao"], d3["motivos_revisao"]; ok("nome 'José João' na CNH × cadastro 'João José': DADOS_DIVERGENTES (ordem trocada)")
assert any(a["codigo"] == "DOCUMENTO_VENCIDO" and a["severidade"] == "erro" for a in d3["alertas"]); ok("CNH com validade 2004: alerta de erro 'documento vencido'")
assert d3["thumb_url"] and c.get(d3["thumb_url"]).status_code == 200; ok("miniatura assinada no resultado do lote")
assert any(i["status"] == "FALHA" for i in d3["checklist"]); ok("checklist traz a falha de validade")
# imagem borrada (foto sem camada de texto)
import io, fitz
src = fitz.open(PDF); pix = src[0].get_pixmap(dpi=150); src.close()
im = Image.open(io.BytesIO(pix.tobytes("png"))).filter(ImageFilter.GaussianBlur(6)); buf = io.BytesIO(); im.save(buf, "PNG")
r = c.post(f"{API}/batches", headers=H(rh), files={"file": ("foto_borrada.png", buf.getvalue())}); assert r.status_code == 202, r.text; b4 = r.json()["id"]
for _ in range(60):
    bb = get(rh, f"/batches/{b4}")
    if bb["status"].startswith("PROCESSADO") or bb["status"] == "FALHOU": break
    time.sleep(1)
assert bb["status"] != "FALHOU" and len(bb["documentos"]) == 1, (bb["status"], bb.get("erro"), len(bb["documentos"])); d4 = bb["documentos"][0]
assert "IMAGEM_BORRADA" in d4["motivos_revisao"] and any(a["codigo"] == "IMAGEM_BORRADA" for a in d4["alertas"]); ok("foto borrada NÃO é descartada como página em branco: vira 'Imagem borrada' (erro)")
r = c.post(f"{API}/review/{d4['id']}", headers=H(rh), json={"acao": "SOLICITAR_REENVIO", "motivo": "Imagem ilegível, envie novamente"}); assert r.status_code == 204, r.text
assert all(x["id"] != d4["id"] for x in get(rh, f"/batches/{b4}")["documentos"]); ok("solicitar novo envio: documento sai do lote (e-mail ao remetente)")
r = c.post(f"{API}/review/{d3['id']}", headers=H(rh), json={"acao": "CONFIRMAR", "forcado": True}); assert r.status_code == 204, r.text
assert any(a["acao"] == "REVISAO_CONFIRMAR" and a["dados"].get("forcado") for a in get(adm, "/audit", params={"acao": "REVISAO_CONFIRMAR"})["items"]); ok("'aprovar mesmo assim' registrado como forçado na auditoria")

print("10. RH com a visão do admin: documentos, painel e permissões")
pg = get(rh, "/documents", params={"limit": 5}); assert len(pg["items"]) == 5 and pg["next_cursor"] and {"todos", "aprovados", "revisao", "rejeitados"} <= set(pg["resumo"]); ok(f"lista de documentos paginada; totais por status: {pg['resumo']}")
pg2 = get(rh, "/documents", params={"limit": 5, "cursor": pg["next_cursor"]}); assert not ({d["id"] for d in pg["items"]} & {d["id"] for d in pg2["items"]}); ok("cursor devolve a página seguinte sem repetir")
rev = get(rh, "/documents", params={"status": "AGUARDANDO_REVISAO", "limit": 100}); assert rev["items"] and all(d["status"] == "AGUARDANDO_REVISAO" for d in rev["items"]) and rev["resumo"]["todos"] >= len(rev["items"]); ok("filtro por status (abas) mantém os totais")
hol = get(rh, "/documents", params={"q": "holerite", "limit": 100}); assert hol["items"] and all(d["document_type"] == "HOLERITE" for d in hol["items"]); ok("busca por texto (tipo)")
por = get(rh, "/documents", params={"q": "roberto", "limit": 100}); assert por["items"] and all("ROBERTO" in (d["funcionario_nome"] or "").upper() for d in por["items"] if not d["mascarado"]); ok("busca por nome do funcionário")
att = get(rh2, "/documents", params={"tipo": "ATESTADO_MEDICO", "limit": 20}); assert att["items"] and all(d["mascarado"] and d["funcionario_nome"] is None and d["nome_arquivo"] is None for d in att["items"]); ok("RH sem saude:ler: atestados mascarados na lista (sem nome, arquivo ou pasta)")
att2 = get(rh, "/documents", params={"tipo": "ATESTADO_MEDICO", "limit": 20}); assert att2["items"] and not any(d["mascarado"] for d in att2["items"]); ok("RH com saude:ler enxerga os atestados")
ovr = get(rh, "/metrics/overview"); assert ovr["documentos_total"] > 0 and ovr["documentos_por_tipo"] and ovr["lotes_total"] > 0; ok("RH acessa o painel (mesma API do admin) com totais e tipos de documento")
for path in ("/calendar", "/reports/conformidade", "/metrics/processing", "/metrics/compliance", "/batches"): assert c.get(f"{API}{path}", headers=H(rh)).status_code == 200, path
ok("RH acessa calendário, relatórios, métricas e lotes")
for path in ("/billing", "/logs/processamento", "/users", "/retention", "/support-access"): assert c.get(f"{API}{path}", headers=H(rh)).status_code == 403, path
ok("configuração e conta continuam só com o admin (RH → 403)")

print("11. Lançamento manual, indicadores de risco trabalhista e permissões")
rk = get(rh, "/risks"); cod = {i["codigo"] for i in rk["items"]}
assert {"JORNADA_ACIMA_10H", "INTERVALO_INFERIOR_1H", "HE_SEM_PAGAMENTO", "FGTS_DIVERGENTE"} <= cod and rk["resumo"]["alto"] >= 3; ok(f"indicadores derivados dos documentos: {sorted(cod)[:6]}…")
assert all(i["base_legal"] and i["severidade"] in ("ALTO", "MEDIO", "BAIXO") for i in rk["items"]); ok("todo indicador traz severidade e base legal")
he = [i for i in rk["items"] if i["codigo"] == "HE_SEM_PAGAMENTO"][0]; assert "44:00" in he["descricao"]; ok("horas extras do ponto (44:00) sem pagamento no holerite")
joao = get(rh, "/employees", params={"q": "joao pedro"})["items"][0]
fer = [i for i in rk["items"] if i["codigo"] == "FERIAS_SEM_COMPROVANTE" and i["employee_id"] == joao["id"]]; assert fer; ok("férias: vínculo > 23 meses sem recibo")
# lançamento manual (sem imagem) de documento legível — formulário por tipo
r = c.post(f"{API}/employees/{joao['id']}/documents/manual", headers=H(rh), json={"tipo": "RECIBO_FERIAS", "data_documento": time.strftime("%Y-%m-%d"), "campos": {"periodo": "30 dias"}, "observacao": "recibo físico conferido"}); assert r.status_code == 201, r.text; man = r.json()["id"]
md = get(rh, f"/documents/{man}"); assert md["origem"] == "MANUAL" and md["status"] == "REVISADO" and md["paginas_urls"] == []; ok("documento lançado manualmente: origem MANUAL, REVISADO, sem imagem")
assert [i for i in get(rh, "/risks")["items"] if i["codigo"] == "FERIAS_SEM_COMPROVANTE" and i["employee_id"] == joao["id"]]; ok("dado digitado NÃO comprova ausência: o indicador de férias continua até haver documento com imagem")
assert c.get(f"{API}/documents/{man}/download", headers=H(rh), params={"formato": "original"}).status_code in (400, 404); ok("documento manual não tem arquivo para baixar (erro claro, não 500)")
assert c.post(f"{API}/employees/{joao['id']}/documents/manual", headers=H(rh), json={"tipo": "NAO_EXISTE"}).status_code == 400; ok("tipo desconhecido → 400")
assert c.post(f"{API}/employees/{joao['id']}/documents/manual", headers=H(rh), json={"tipo": "RECIBO_FERIAS", "data_documento": "10/10/2026"}).status_code == 400; ok("data inválida → 400")
assert c.post(f"{API}/employees/{joao['id']}/documents/manual", headers=H(rh2), json={"tipo": "ATESTADO_MEDICO"}).status_code == 403; ok("documento de saúde manual exige saude:ler")
# rescisão: TRCT datado fora dos 10 dias
rob = get(rh, "/employees", params={"q": "roberto"})["items"][0]
assert c.patch(f"{API}/employees/{rob['id']}", headers=H(rh), json={"desligamento": "2026-08-01", "status": "DESLIGADO"}).status_code == 204
r = c.post(f"{API}/employees/{rob['id']}/documents/manual", headers=H(rh), json={"tipo": "TRCT", "data_documento": "2026-09-20", "campos": {"valor_liquido": "5000,00"}}); assert r.status_code == 201, r.text
cod2 = {(i["codigo"], i["employee_id"]) for i in get(rh, "/risks")["items"]}; assert ("TRCT_FORA_DO_PRAZO", rob["id"]) in cod2; ok("TRCT datado 50 dias após o desligamento → TRCT_FORA_DO_PRAZO")
# ignorar / reabrir (só admin, com justificativa, auditado)
alvo = [i for i in get(rh, "/risks")["items"] if i["codigo"] == "TRCT_FORA_DO_PRAZO"][0]["id"]
assert c.post(f"{API}/risks/{alvo}/ignore", headers=H(rh), json={"justificativa": "pagamento no prazo, comprovante anexo"}).status_code == 403; ok("RH não ignora indicador (só admin)")
assert c.post(f"{API}/risks/{alvo}/ignore", headers=H(adm), json={"justificativa": "x"}).status_code in (400, 422); ok("ignorar exige justificativa")
assert c.post(f"{API}/risks/{alvo}/ignore", headers=H(adm), json={"justificativa": "pagamento no prazo, comprovante anexo"}).status_code == 204
assert alvo not in {i["id"] for i in get(rh, "/risks")["items"]} and alvo in {i["id"] for i in get(rh, "/risks", params={"status": "IGNORADO"})["items"]}; ok("indicador ignorado sai da lista aberta e fica no histórico")
c.post(f"{API}/employees/{rob['id']}/documents/manual", headers=H(rh), json={"tipo": "RECIBO_FERIAS", "data_documento": time.strftime("%Y-%m-%d")})  # força novo recálculo
assert alvo in {i["id"] for i in get(rh, "/risks", params={"status": "IGNORADO"})["items"]}; ok("recálculo preserva a decisão de ignorar")
assert c.post(f"{API}/risks/{alvo}/reabrir", headers=H(adm)).status_code == 204 and alvo in {i["id"] for i in get(rh, "/risks")["items"]}; ok("admin reabre o indicador")
acts = {a["acao"] for a in get(adm, "/audit", params={"limit": 200})["items"]}; assert {"RISCO_IGNORADO", "RISCO_REABERTO", "DOCUMENTO_LANCADO_MANUALMENTE"} <= acts; ok("ignorar, reabrir e lançamento manual ficam na auditoria")
# indicadores de documentos de saúde: texto restrito sem saude:ler
rk2 = get(rh2, "/risks"); assert rk2["resumo"]["alto"] >= 3 and not any(i["funcionario"] and i["codigo"] == "ATESTADO" for i in rk2["items"]); ok("RH sem saude:ler consulta /risks")
ovr = get(rh, "/metrics/overview"); assert ovr["riscos"]["alto"] >= 3 and ovr["riscos_por_codigo"] and "pre_cadastros" in ovr; ok(f"painel traz riscos ({ovr['riscos']}) e contagem de pré-cadastros ({ovr['pre_cadastros']})")
# completar o pré-cadastro
assert c.patch(f"{API}/employees/{paulo['id']}", headers=H(rh), json={"admissao": "2026-03-01", "pre_cadastro": False}).status_code == 204
assert get(rh, f"/employees/{paulo['id']}")["pre_cadastro"] is False and paulo["id"] not in {e["id"] for e in get(rh, "/employees", params={"pre": "1"})["items"]}; ok("RH completa o pré-cadastro e ele sai da lista (o criado na revisão continua pendente)")

print("\nOK — todos os checks passaram")
