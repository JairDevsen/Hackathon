"""Servidor FALSO compatível com a API de chat da OpenAI, para testar o IA Core sem chave nem custo.

Quando a página fala de "confidencialidade", responde como um modelo que RECONHECE um tipo documental novo (Termo de confidencialidade);
para o resto devolve OUTRO. Cada chamada recebida vai para o arquivo de log (uma linha JSON), para o teste contar quantas vezes o modelo foi usado.

Uso: python fake_openai.py /caminho/chamadas.log    (porta 9999)
     IA_PROVIDER=openai OPENAI_API_KEY=sk-fake OPENAI_BASE_URL=http://127.0.0.1:9999/v1  uvicorn ia_core.main:app --port 8001"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
LOG = sys.argv[1]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msg = corpo["messages"][0]["content"]
        texto = msg if isinstance(msg, str) else " ".join(p.get("text", "") for p in msg if p.get("type") == "text")
        com_imagem = not isinstance(msg, str)
        with open(LOG, "a") as f: f.write(json.dumps({"modelo": corpo["model"], "imagem": com_imagem, "confid": "CONFIDENCIALIDADE" in texto}) + "\n")
        if "CONFIDENCIALIDADE" in texto.upper():
            r = {"tipo": "OUTRO", "inicia_documento": True, "confianca": 0.92, "titulo": "Termo de confidencialidade", "texto_ocr": "",
                 "cpf": "746.023.188-60", "nome": "JOSE ALVES DA SILVA",
                 "tipo_novo": {"nome": "Termo de confidencialidade", "escopo": "FUNCIONARIO", "categoria": "ADMISSAO",
                               "pistas": ["Termo de confidencialidade e sigilo", "compromete-se a manter sigilo", "frase inventada que nao existe"]}}
        elif "Responda apenas com a palavra" in texto:
            r = None
        else:
            r = {"tipo": "OUTRO", "inicia_documento": True, "confianca": 0.9, "titulo": "Outro", "texto_ocr": ""}
        conteudo = "OK" if r is None else json.dumps(r)
        out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": corpo["model"],
                          "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": conteudo}}],
                          "usage": {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
HTTPServer(("127.0.0.1", 9999), H).serve_forever()
