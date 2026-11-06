# Gerador de documentos trabalhistas fictícios: manuscritos, preenchidos à mão e escaneados

Gera lotes em PDF com **32 tipos de documento** de RH e de terceirização, cada um com **gabarito exato**.
O gabarito informa o tipo de cada página, onde cada documento começa e termina, o CPF, a competência, os valores de cada campo, as não conformidades e os defeitos de escrita.
Use para medir a separação, a classificação e a extração do IA Core.

> **Dados 100% fictícios.** Empresas, pessoas, CPFs e CNPJs saem de geradores de teste (dígitos verificadores válidos).
> Toda página leva "AMOSTRA – DOCUMENTO FICTÍCIO" num canto, no rodapé e numa diagonal bem leve.
> Não há brasões, logotipos nem elementos de segurança oficiais. A carteira de trabalho usa um layout genérico,
> a foto 3x4 é uma silhueta sem rosto, e os códigos levam o prefixo `FICT`.

## Instalação
```bash
# estrutura esperada:  projeto/ia_core/   projeto/gerador_docs/
pip install pydantic faker pillow opencv-python-headless numpy pypdfium2 pytest
cd gerador_docs
```

## Uso
```bash
python -m gerador tipos                                   # lista tipos e não conformidades
python -m gerador lotes --qtd 30 --perfil sortear --paginas 10-40 --saida saida/
python -m gerador lotes --qtd 10 --perfil recebimento_ar --paginas 15-30 --saida saida_ar/
python -m gerador amostra --tipo ATESTADO_MEDICO --qtd 3 --saida amostras/
python -m gerador amostra --tipo PEDIDO_DEMISSAO --celular --taxa-defeito 0.3 --saida amostras/
python -m gerador amostra --tipo ADVERTENCIA_SUSPENSAO --nc recusa_sem_testemunhas --limpo --saida amostras/
```
Principais opções de `lotes`:

| Opção | O que controla | Padrão |
|---|---|---|
| `--perfil` | admissao, mensal, desligamento, ocorrencias, recebimento_ar, misto ou sortear | `sortear` |
| `--taxa-nc` | chance de cada documento ter uma não conformidade | 0.2 |
| `--taxa-defeito` | chance de cada campo manuscrito ter defeito (rasura, corretivo etc.) | 0.08 |
| `--extras` | chance de grampo, clipe, post-it, dobra ou carimbo "RECEBIDO" | 0.25 |
| `--celular` | chance de a página ser foto de celular | 0.12 |
| `--cabeca-para-baixo` | chance de a página estar invertida | 0.03 |
| `--embaralhar` | chance de os documentos virem fora da ordem natural | 0.3 |
| `--png` | também salva cada página como PNG | – |

Velocidade: cerca de 1 página por segundo em CPU.

## Tipos de documento
**A. Totalmente manuscritos:** PEDIDO_DEMISSAO · ATESTADO_MEDICO (receituário, letra de médico, carimbo, CRM) · DECLARACAO_MANUSCRITA
(residência, dependentes, não acúmulo) · RECIBO_AVULSO (adiantamento, vale, diária; valor por extenso) · JUSTIFICATIVA_FALTA ·
ADVERTENCIA_SUSPENSAO (versão manuscrita, com "Estou ciente" ou "Recusou-se a assinar" e testemunhas) · CTPS_ANOTACAO (carteira aberta, layout genérico)

**B. Formulário impresso preenchido à mão:** CARTAO_PONTO · FICHA_EPI · FICHA_REGISTRO (com foto 3x4 colada) · LISTA_PRESENCA (uma letra
por participante) · ASO · ORDEM_SERVICO_SST · DECLARACAO_VALE_TRANSPORTE · DECLARACAO_DEPENDENTES · RECIBO_BENEFICIO (VT/VR/VA) ·
FERIAS (aviso ou recibo em bloco) · CHECKLIST_INTEGRACAO · TERMO_RESPONSABILIDADE · OCORRENCIA_ACIDENTE · AVISO_RECEBIMENTO (AR)

**C. Impressos com assinatura, visto ou carimbo:** HOLERITE · CONTRATO_TRABALHO (3 páginas, rubricas) · TRCT · GUIA_FGTS e DARF
(anotação "pago em…" e autenticação) · ADVERTENCIA_SUSPENSAO impressa · NOTIFICACAO_EMPREGADO · CRF_FGTS · CNDT · CND_FEDERAL ·
COMPROVANTE_PAGAMENTO · OUTRO (capa, separador, ofício, página em branco)

## Variações
| Grupo | Variações |
|---|---|
| Caligrafia | 24 fontes livres em 4 estilos (letra de forma, cursiva, pressa, médico), caneta azul ou preta, **lápis**; cada letra varia em tamanho, rotação, linha de base e pressão |
| Defeitos | **rasura** (rabisco + reescrita), **corretivo**, **texto riscado**, **campo em branco**, **escrita fora da linha** |
| Extras | carimbo torto, rubrica, **grampo**, **clipe**, **post-it** com recado, **dobra**, carimbo "RECEBIDO" |
| Captura | scanner leve, médio ou forte (inclinação, sombra, furos, ruído, fotocópia, baixa resolução, JPEG); **foto de celular** (mesa ao fundo, perspectiva, luz irregular, sombra, tremido); **página de cabeça para baixo** |
| Lote | perfis realistas, empregados misturados, **página fora de ordem**, **documento intercalado**, **páginas em branco**, comprovantes 2 por folha |

**Lotes de recebimento de AR (`--perfil recebimento_ar`)** trazem vários ARs, às vezes com a cópia da notificação, montados de três jeitos:
- frente e verso do mesmo AR na mesma folha;
- **frentes de 2 ARs numa folha e os versos na folha seguinte** (cada AR fica com páginas não contíguas);
- frentes e versos alternados de 2 em 2.

O AR traz: código do objeto, conteúdo, data e unidade de postagem, destinatário (logradouro, bairro, município, UF, CEP), remetente, até 3 tentativas com data e hora, motivo de devolução, data de entrega ou de devolução, nome, documento e assinatura do recebedor, rubrica e matrícula do carteiro e carimbo.

## Gabarito
```
saida/
  lotes/lote_0001.pdf
  gabarito.csv          uma linha por página (todos os lotes)
  gabarito/lote_0001.json
  universo.json         empresas e empregados fictícios
  manifesto.json        seed, config, contagens por tipo, perfil e não conformidade
```
**gabarito.csv:** `arquivo, pagina, tipo, documento, pagina_do_documento, inicia_documento, multiplos_documentos, rotacao, captura`.
Quando dois documentos dividem a folha (dois ARs, dois comprovantes), `documento` vale `3;4`. É compatível com `ia_core/scripts/avaliar.py`.

**gabarito/lote_XXXX.json:**
```json
{
  "arquivo": "lote_0001.pdf", "perfil": "recebimento_ar", "empresa_cnpj": "…", "competencia": "2026-09",
  "paginas": [{"pagina": 2, "documentos": [{"indice": 2, "pagina_do_documento": 1}, {"indice": 3, "pagina_do_documento": 1}],
               "captura": "scanner_media", "rotacao": 0, "extras": ["grampo", "post_it:conferir"]}],
  "documentos": [{
    "indice": 2, "tipo": "AVISO_RECEBIMENTO", "paginas": [2, 3], "paginas_contiguas": true,
    "fora_de_ordem": false, "intercalado": false,
    "cpf": "…", "empregado": "…", "competencia": null, "empresa_cnpj": "…",
    "dados": { "...": "campos no schema do ia_core para o tipo" },
    "nao_conformidades": [{"regra": "ar_devolvido", "descricao": "…", "campo": "motivo_devolucao"}],
    "defeitos_escrita": [{"defeito": "rasura", "texto": "Bernadete"}, {"defeito": "campo_em_branco", "campo": "empregado_cpf"}]
  }]
}
```
Com esses dados dá para medir:
- **separação**: `pagina_do_documento` e `inicia_documento`, inclusive com documentos não contíguos;
- **classificação**: `tipo`;
- **extração**: `dados`, comparado com o que o modelo devolver;
- **robustez**: erros cruzados com `captura`, `rotacao`, `extras` e `defeitos_escrita`.

## Garantia de fidelidade (conferência automática)
Todo texto, assinatura e carimbo desenhado fica registrado. Antes de gravar um lote, `conferencia.conferir()` verifica duas coisas:
- cada valor do gabarito foi de fato desenhado na página (datas e valores em qualquer formato: 05/11/2026, "05 de novembro de 2026", 1.234,56);
- nenhum campo obrigatório ficou vazio, exceto quando o vazio é intencional (campo em branco ou não conformidade registrados).

Se houver divergência, o lote **não é gravado**: o gerador para com o erro.

## Testes
```bash
python -m pytest -q tests           # ou: -n auto  (pytest-xdist)
```
São 107 testes:
- gabarito fiel nos 32 tipos, com e sem defeitos;
- cada não conformidade acusada no campo certo por `ia_core.validacoes`;
- os 6 perfis de lote com páginas e documentos consistentes;
- reprodutibilidade por seed;
- lote de AR com vários ARs completos.

## Limitações
- Cálculos (INSS, férias, 13º) aproximados: servem para coerência interna, não como referência legal.
- Layouts genéricos. O acerto medido com eles tende a sair otimista em relação a documentos reais; reserve documentos reais anonimizados para a medição final.
- O atestado não traz diagnóstico; o eventual CID é fictício e o schema registra só se há CID (`cid_informado`).
