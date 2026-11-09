# Como a IA do Citadel IA funciona

Este documento explica, do arquivo enviado até o indicador de risco na tela, **como o sistema lê, separa, classifica e avalia os documentos**, o que é feito por IA, o que é feito por regra, e quais são as camadas que decidem quando gastar (ou não) um modelo de IA.

Tudo aqui descreve o código atual. Onde algo **não foi validado** ou tem limite conhecido, está dito. A seção [Medições e limites](#18-medições-e-limites-o-que-foi-e-o-que-não-foi-validado) reúne os números.

## Sumário

1. [Visão geral](#1-visão-geral)
2. [O princípio: a IA lê, as regras decidem](#2-o-princípio-a-ia-lê-as-regras-decidem)
3. [Recebimento do lote](#3-recebimento-do-lote)
4. [Fatiamento das páginas](#4-fatiamento-das-páginas)
5. [O funil de camadas](#5-o-funil-de-camadas)
6. [OCR](#6-ocr)
7. [Reconhecimento: o tipo de cada página](#7-reconhecimento-o-tipo-de-cada-página)
8. [Extração de campos](#8-extração-de-campos)
9. [Separação: de páginas para documentos](#9-separação-de-páginas-para-documentos)
10. [Qualidade da imagem e orientação](#10-qualidade-da-imagem-e-orientação)
11. [Validações e checklist por documento](#11-validações-e-checklist-por-documento)
12. [Vínculo, pré-cadastro e revisão humana](#12-vínculo-pré-cadastro-e-revisão-humana)
13. [Conformidade: o que falta, vence ou está em dia](#13-conformidade-o-que-falta-vence-ou-está-em-dia)
14. [Indicadores de risco trabalhista](#14-indicadores-de-risco-trabalhista)
15. [Anonimização e proteção do texto lido](#15-anonimização-e-proteção-do-texto-lido)
16. [Resiliência do processamento](#16-resiliência-do-processamento)
17. [Custo e telemetria (FinOps)](#17-custo-e-telemetria-finops)
18. [Medições e limites](#18-medições-e-limites-o-que-foi-e-o-que-não-foi-validado)
19. [Configuração](#19-configuração)
20. [Onde está cada coisa no código](#20-onde-está-cada-coisa-no-código)

---

## 1. Visão geral

```
 PDF / imagem / ZIP / TIFF enviado pelo RH
        │
        ▼
┌─────────────────────────────  API Go  ─────────────────────────────┐
│ valida formato, tamanho, cota, antivírus · SHA-256 · guarda cifrado │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼
┌──────────────────────────  IA Core (Python)  ───────────────────────┐
│ FATIAR   página → PNG 150 dpi + miniatura + texto nativo + palavras │
│          (gira a página se estiver de cabeça para baixo)            │
│                                                                     │
│ ANALISAR uma página por vez, com o FUNIL de camadas:                │
│   Camada 0  mesma página já vista nesta empresa?  → reaproveita     │
│   Camada 1  texto nativo/OCR + regras locais      → custo zero      │
│   Camada 2  modelo leve sobre o TEXTO             → barato          │
│   Camada 3  modelo multimodal sobre a IMAGEM      → caro, só no fim │
│   → tipo, confiança, campos, início/continuação, legibilidade       │
│                                                                     │
│ AGRUPAR  páginas → documentos (marcadores, número do AR, anexos)    │
└───────────────────────────────┬─────────────────────────────────────┘
                                ▼  callback assinado (HMAC), idempotente
┌─────────────────────────────  API Go  ─────────────────────────────┐
│ VINCULAR  CPF (hash cego) → matrícula → nome · pré-cadastro · CNPJ  │
│ REVISAR   baixa confiança, ilegível, divergência → fila humana      │
│ CONFORMIDADE  exigências × documentos → pendente / a vencer / ok    │
│ INDICADORES   regras sobre os documentos → risco trabalhista        │
└─────────────────────────────────────────────────────────────────────┘
```

O IA Core é um serviço separado, em Python/FastAPI. A API Go cuida de tudo que é dado do negócio (empresas, funcionários, exigências, indicadores) e de segurança. O IA Core só recebe imagens, devolve análises e **nunca grava no banco**.

## 2. O princípio: a IA lê, as regras decidem

| Pergunta | Quem responde | Como |
|---|---|---|
| "Que documento é esta página?" | **IA** (ou regras locais) | classificação por página |
| "O que está escrito?" | **IA / OCR** | texto e campos extraídos |
| "Estas páginas formam um só documento?" | **Regras determinísticas** | marcadores, números, anexos |
| "De quem é este documento?" | **Regras** | CPF por hash cego, matrícula, nome |
| "O documento está vencido ou sem assinatura?" | **Regras** | datas e palavras no texto |
| "Falta algum documento exigido?" | **Regras** | exigências × documentos validados |
| "Há risco de reclamação trabalhista?" | **Regras** | catálogo de indicadores com base legal |

Consequências práticas:

- **Não há modelo de previsão estatística.** Os "indicadores de risco" não são probabilidades nem aprendizado de máquina: são regras explícitas, auditáveis, cada uma com a norma que a motiva. É deliberado: um indicador precisa poder ser explicado a um advogado.
- A IA só entra onde regras não bastam: ler manuscrito, carimbo, foto ruim, formulário com layout variável.
- Quando a IA erra, o erro aparece como **baixa confiança, divergência ou documento sem vínculo**, e vai para a fila de revisão humana, em vez de virar um indicador silencioso.

## 3. Recebimento do lote

Implementado na API Go (`backend/internal/batches/`).

1. **Upload retomável em partes.** Se a conexão cai, o cliente consulta o `offset` e continua de onde parou. Limite padrão de 500 MB (`MAX_UPLOAD_MB`).
2. **Validações:** formato (PDF, imagens, TIFF multipágina, ZIP de imagens, HEIC se `pillow-heif` estiver instalado), tamanho, cota mensal de páginas do plano e **duplicidade por SHA-256 do arquivo** (`batches.sha256`; mesmo arquivo → `409`). Esse hash do arquivo é diferente do hash de cada página, usado na Camada 0.
3. **Antivírus** ClamAV (`clamd`, INSTREAM), quando configurado.
4. **Armazenamento cifrado.** Todo objeto é gravado com AES-256-GCM em segmentos de 1 MiB, com uma chave de dados (DEK) por empresa, embrulhada por uma chave mestra (KEK). O IA Core acessa a imagem por **URLs assinadas por HMAC** de curta duração.
5. **Fila.** O lote vira uma tarefa (asynq/Redis). Um worker chama o IA Core e acompanha o andamento.

## 4. Fatiamento das páginas

`ia-core/ia_core/fatiar.py`. O IA Core recebe o arquivo e devolve, **página a página** (em streaming, sem carregar o arquivo inteiro na memória):

| Saída | Detalhe |
|---|---|
| Imagem PNG | renderizada a **150 dpi** (PDF) ou convertida (imagem/TIFF/HEIC) |
| Miniatura WebP | 360 px de largura, qualidade 70, usada nas listas |
| Texto embutido | texto digital do PDF, quando existe (sem OCR, sem custo) |
| Palavras com posição | cada palavra com sua caixa (frações da página), usada em destaque e tarja |
| Caixas de dado pessoal | onde estão CPF, CNPJ, nome etc., quando há texto nativo |
| Rotação corrigida | quantos graus a imagem foi girada (ver [seção 10](#10-qualidade-da-imagem-e-orientação)) |

Uma página **com texto embutido** é um PDF "digital": o texto é lido direto, sem OCR. Uma página **só com imagem** (PDF escaneado, foto) não tem texto: depende de OCR ou de modelo de visão.

## 5. O funil de camadas

A ideia central: **gastar o mínimo de IA possível sem perder qualidade**. Cada página percorre as camadas na ordem e **para na primeira que resolve**.

### Camada 0: cache por conteúdo (SHA-256)

Feita na API Go, antes de chamar o IA Core, e **baseada em um hash guardado no banco**. O sistema grava dois hashes SHA-256, com funções diferentes:

| Hash | Onde fica | De quê | Para quê |
|---|---|---|---|
| `batches.sha256` | tabela `batches` | do **arquivo inteiro** enviado | recusar upload duplicado (`409`); índice único por empresa |
| `pages.hash_sha256` | tabela `pages` | da **imagem de cada página** (o PNG guardado) e do texto embutido, quando há | **Camada 0**; índice `pages_hash (tenant_id, hash_sha256)` |

### Como o hash é gerado

1. O IA Core fatia o arquivo e produz, para cada página, um **PNG** (150 dpi para PDF; imagem convertida para as demais; já **endireitado**, ver [seção 10](#10-qualidade-da-imagem-e-orientação)).
2. A API Go, ao gravar esse PNG (cifrado) no armazenamento, calcula o **SHA-256 dos bytes do PNG** no mesmo fluxo de leitura, sem ler duas vezes.
3. Se a página **tem texto embutido** (camada de texto do PDF), a chave passa a ser `SHA-256( SHA-256(PNG) ‖ 0x00 ‖ texto embutido )`. Sem texto embutido (escaneado), é o SHA-256 puro do PNG.
4. O resultado vai para `pages.hash_sha256`.

Ou seja: o hash **não** é do arquivo original nem do nome; é do **conteúdo da página** (pixels e, quando existe, o texto embutido).

### Como o cache é consultado

Antes de chamar a IA, a API procura, **na mesma empresa**, uma página de **outro lote** com o mesmo `hash_sha256`, com análise concluída com sucesso (`proc_status='OK'`) **e feita pelo mesmo motor** (próxima seção). Se houver, **copia a análise** da mais recente: 0 tokens, instantâneo. A cópia marca `camada = Camada 0: Cache SHA-256`, zera os tokens e registra de qual lote veio (`reutilizada_de`). A busca nunca cruza empresas (isolamento por linha no banco). A análise copiada traz o texto e os campos **já cifrados** com a chave da mesma empresa.

### Como se garante que uma diferença mínima refaz a análise

Há **três travas**, e todas são verificadas no teste de ponta a ponta (seção 16 de `e2e_smoke.py`):

| Trava | O que impede | Testado |
|---|---|---|
| **SHA-256 dos pixels** | qualquer diferença na imagem. SHA-256 tem efeito avalanche: mudar **um bit** altera o hash inteiro. | um pixel, um canal de cor, um nível de diferença: análise refeita |
| **Texto embutido na chave** | mesma imagem com camada de texto diferente (por exemplo, o texto de OCR gravado por um scanner). Só a imagem não percebia isso. | mesma imagem, outro texto: análise refeita; imagem e texto iguais: reaproveitada |
| **Impressão digital do motor** | análise antiga produzida por **outro provedor, modelo, prompt, catálogo ou código**. Sem isso, depois de uma atualização das regras o sistema continuaria reaproveitando resultados que as regras novas já não dariam. | análise marcada com outro motor: não é reaproveitada |

**A impressão digital do motor** (`ia_core/impressao.py`) é um hash de: nome do provedor e dos três modelos (principal, reserva, texto), `IA_IMAGE_MAX_PX`, `IA_NITIDEZ_MIN` e o **conteúdo dos arquivos que definem o resultado** (catálogo, extração, validações, checklist, provedores, orientação, qualidade de imagem, paginação, anonimização, agrupamento e schemas). Cada análise sai marcada com ela (`analise.motor`) e `GET /health` a informa. **Qualquer alteração em qualquer desses arquivos, ou trocar de modelo, invalida o cache inteiro**, por escolha: reanalisar é só custo, reaproveitar análise obsoleta é erro silencioso. Se a API não conseguir saber o motor ativo, o cache fica desligado naquele lote (analisa tudo).

### O que o cache pode errar, e por quê

Por construção, o erro possível é sempre do lado seguro (**refazer sem necessidade**), nunca o contrário, exceto nos pontos abaixo:

- **Mesma página, bytes diferentes → refeita.** Uma nova digitalização da mesma folha, uma recompressão ou outro nível de zoom produzem pixels diferentes e **não** acertam o cache. Não há comparação aproximada. Custa tokens, não corretude.
- **Colisão de SHA-256:** teoricamente possível, na prática inviável (cerca de 2⁻¹²⁸ por par de páginas).
- **Diferença abaixo da resolução da renderização:** o hash vê o PNG a 150 dpi. Uma mudança vetorial em PDF digital que não altere **nenhum** pixel e não esteja no texto embutido não é vista. É um caso extremo, e a análise é feita em cima da mesma imagem, então o resultado é o mesmo.
- **Contexto de lote:** a análise depende em pequena parte do lote em que a página está (a página anterior e a "dica do tipo de lote" são contexto para o provedor de IA; no motor local, `inicia_documento` depende de existir uma página anterior). A análise copiada leva o contexto do lote de origem. O agrupamento por marcadores, números e anexos usa o **texto**, que é igual, e reduz bastante esse efeito, mas não o elimina.
- **Não há botão de "reanalisar sem cache".** Para forçar, é preciso mudar o motor (trocar modelo ou regras) ou apagar os lotes de origem da mesma página.

### Camada 1: leitura local (custo zero)

Roda no próprio IA Core, sem rede e sem modelo externo (`LocalProvider`):

1. **Texto**: usa o texto embutido do PDF; se a página é só imagem, confere a nitidez e tenta **OCR com Tesseract** (ver [seção 6](#6-ocr)).
2. **Classifica** por pistas de texto (ver [seção 7](#7-reconhecimento-o-tipo-de-cada-página)).
3. **Extrai campos** por expressões regulares (ver [seção 8](#8-extração-de-campos)).
4. **Detecta continuação** pelo marcador "Página 2/3" etc.

Resultado típico: documento digital com cabeçalho claro, como holerite, certidão ou guia, sai resolvido aqui com confiança alta. A página só fecha aqui se o **roteador** (abaixo) confirmar que os campos que o tipo exige também foram achados.

**Valores de confiança do motor local** (úteis para entender o que a tela mostra):

| Situação | Confiança |
|---|---|
| Classificação por pistas | `0,62 + 0,09 × min(pontos, 4)`, teto 0,98; menos 0,14 se o 2º colocado está a menos de 2 pontos; mínimo 0,45 |
| Nenhuma pista reconhecida | 0,40 (`OUTRO`) |
| Texto com marca de rasura/ilegibilidade | limitada a 0,58 |
| Página em branco (descartada, não vira documento) | 0,35 |
| **Página só de imagem, sem Tesseract** | **0,30** ("sem OCR disponível": vai para revisão, **não** é descartada como branca) |
| Imagem borrada | 0,20 |

### Quem decide a camada: o roteador

`ia-core/ia_core/roteador.py` reúne as regras (puras, sem rede, testáveis). Cada página passa por duas etapas: a **etapa local** (texto nativo ou OCR com correção de orientação, regras e decisão da camada) e, só se a local não resolver, a **chamada ao modelo**. O texto de **PDF escaneado também passa pela etapa local**: o OCR serve para fechar a página na Camada 1 ou alimentar a Camada 2, em vez de mandar tudo para a visão.

| Situação da página | Camada |
|---|---|
| Em branco | nenhuma: não chama modelo |
| Borrada | nenhuma: vai para revisão |
| Tipo que só a imagem resolve (aviso de recebimento, manuscrito, ASO, ficha de EPI, atestado), manuscrito ou rasura | **3** |
| Texto sem qualidade (menos de 100 letras, ou OCR com menos de 6 palavras de vocabulário documental) | **3** |
| Tipo seguro (confiança ≥ 0,85) **e** os campos que o tipo exige foram achados | **1** |
| Tipo seguro, mas faltou a competência (documento mensal) | **2** |
| Tipo seguro, mas **não achou CPF válido**: texto nativo | **2** (o CPF não está na imagem também) |
| Tipo seguro, mas **não achou CPF válido**: texto de OCR | **3** (o dígito pode ter se perdido no OCR; a imagem mostra) |
| Tipo incerto (confiança < 0,85) | **2** |

Só a **primeira página** do documento é cobrada pelos campos (o verso não repete o cabeçalho). Documentos da empresa (certidões, guias, apólice, contrato de prestação) não exigem CPF; holerite, cartão de ponto, guia de FGTS, DARF, comprovante de pagamento e recibo de benefícios exigem competência.

### Camada 2: modelo leve sobre o texto

Só existe com um provedor de IA externo. O modelo recebe **só o texto** (sem imagem), com o catálogo de tipos e a página anterior como contexto, e devolve JSON validado por schema. Duas economias a mais:

- **não transcreve**: o texto já foi extraído, então o prompt manda deixar `texto_ocr` vazio e o sistema usa o texto que já tinha (a transcrição é a maior parte do que o modelo produz, e a saída é a parte cara);
- **CPF conferido pelas regras**: se o CPF devolvido pelo modelo não passa no dígito verificador e as regras leram um que passa, vale o das regras.

A resposta **sobe para a Camada 3** quando o modelo reporta página ilegível ou com vários documentos, devolve confiança abaixo de 0,70 (ou inválida), ou quando, num texto de OCR, não há CPF válido nem nas regras nem na resposta. O gasto da Camada 2 descartada **conta** nos tokens da página.

### Camada 3: modelo multimodal sobre a imagem

É o último recurso e o mais caro:

- a imagem é **reduzida a no máximo 1024 px** no maior lado, em **WebP qualidade 80**, antes de ir para o modelo (só a cópia enviada é reduzida; o original continua guardado em resolução cheia);
- o modelo lê layout, texto, manuscrito, carimbos e assinaturas;
- se o **modelo principal** falha (indisponível, modelo inexistente), tenta o **modelo reserva**;
- se a resposta vem **ilegível, com mais de um documento na imagem ou confiança abaixo de 0,6**, chama de novo o **modelo reserva** (maior) e usa essa resposta.

### Chamadas ao modelo em paralelo

As chamadas à rede (Camadas 2 e 3) de um lote rodam **em paralelo**, com um limite único para o serviço todo (`IA_LLM_CONCURRENCY`, padrão 4), para não estourar a cota do provedor. A etapa local da página seguinte não espera a resposta da anterior (usa como contexto o tipo que as regras deram). Os **callbacks saem sempre em ordem de página**, então o checkpoint continua contíguo: se a página 7 falha, as páginas 1 a 6 já estão salvas e o retry recomeça da 7.

### Resumo das camadas

| Camada | Quando resolve | Custo | Precisa de |
|---|---|---|---|
| **0** Cache SHA-256 | página idêntica já vista na empresa | zero | nada |
| **1** Local (texto + regras + OCR) | tipo inequívoco (≥ 0,85) e campos exigidos achados | zero | Tesseract, para escaneados |
| **2** Modelo leve, texto | tipo incerto ou campo que as regras não acharam, com texto legível | baixo | chave OpenAI ou Gemini |
| **3** Modelo multimodal, imagem | manuscrito, formulário, OCR ruim, CPF não lido no OCR, dúvida | alto | chave OpenAI ou Gemini |

Sem nenhuma chave de IA, só as camadas 0 e 1 funcionam (motor local): o sistema continua útil para PDFs digitais, mas **não lê manuscrito e depende de Tesseract para escaneados**.

#### O que se mediu (OCR real do gerador, 403 páginas de 20 lotes, de scanner leve a forte e foto de celular)

Antes, com provedor externo, **100%** das páginas escaneadas iam para a Camada 3. Com o roteador (resultado em 12 lotes usados para ajustar e 8 lotes **que não foram olhados** durante o ajuste):

| | Ajuste (211 páginas) | Fora da amostra (192 páginas) |
|---|---|---|
| Camada 1 (custo zero) | 24% | 20% |
| Camada 2 (texto) | 11% | 16% |
| Camada 3 (visão) | 64% | 63% |
| Tipo correto nas páginas fechadas na Camada 1 | 98% (49/50) | 100% (39/39) |
| CPF correto nas páginas fechadas na Camada 1 | 33/33 | 25/26 (o outro é um comprovante com dois CPFs, o do favorecido e o do funcionário) |
| Competência correta, quando lida | 14/14 | 10/10 |

Os números dependem do **mix do gerador**, que tem muito aviso de recebimento, manuscrito e formulário (tipos que só a visão resolve). Num acervo mais digital, a fatia da Camada 1 sobe. A Camada 2 custa uma fração da 3 (texto curto, sem imagem, sem transcrição), mas **a proporção exata de custo não foi medida com cobrança real**: foi medida a distribuição por camada, não o gasto em reais.

### Escolha do provedor

Feita **na subida do IA Core** (`obter_provider`):

1. `IA_PROVIDER=openai|gemini|local` força a escolha (sem a chave correspondente, o serviço não sobe, em vez de cair em silêncio no motor local).
2. Sem `IA_PROVIDER`: **OpenAI** se houver `OPENAI_API_KEY`; senão **Gemini** se houver `GEMINI_API_KEY`; senão **local**.

O endpoint `GET /health` mostra o provedor ativo (`openai:<modelo>`, `gemini:<modelo>` ou `local-heuristico`) e `GET /diagnostico` faz uma chamada mínima a cada modelo configurado, mostrando erro de chave ou de nome de modelo **antes** de processar um lote.

| Provedor | Modelo principal (imagem) | Reserva | Texto (Camada 2) | Observação |
|---|---|---|---|---|
| OpenAI | `OPENAI_MODEL` = `gpt-5-mini` | `OPENAI_MODEL_FALLBACK` = `gpt-5` | `OPENAI_MODEL_LITE` = `gpt-5-nano` | saída em JSON mode com o schema no prompt; **nomes não confirmados com chave real** |
| Gemini | `GEMINI_MODEL` = `gemini-3.5-flash` | `gemini-3.6-flash` | `gemini-3.5-flash-lite` | saída estruturada por schema; tentativas automáticas em 429/5xx |

O funil, o roteamento, o modelo reserva e a normalização da resposta são **os mesmos** para os dois provedores; cada um só implementa a chamada.

### O que a IA devolve por página

Um objeto com: `tipo`, `inicia_documento`, `confianca` (0 a 1), `titulo`, `texto_ocr` (transcrição), `cpf`, `nome`, `empresa_nome`, `empresa_cnpj`, `matricula`, `competencia`, `data_documento`, `validade_ate`, `possui_manuscrito`, `tem_assinatura`, `pagina_ilegivel`, `multiplos_documentos_na_imagem`, `pagina_em_branco` e `extras` (pares chave/valor específicos do tipo). A resposta é **normalizada**: confiança limitada a 0–1; tipo fora do catálogo vira `OUTRO`; valores extras tolerados sem derrubar a página.

O prompt instrui o modelo sobre documentos de **várias páginas** ("Página 2/3", termo de quitação, verso do AR): deve marcar `inicia_documento=false` e usar o mesmo tipo do documento a que a página pertence.

## 6. OCR

OCR é o que transforma **imagem em texto**. No sistema ele aparece em quatro usos distintos, com motores diferentes:

| Uso | Motor | Onde |
|---|---|---|
| Ler uma página escaneada para classificar (motor local) | **Tesseract** (idioma `por`), via PyMuPDF | `providers.py` (`LocalProvider`) |
| Descobrir se a página está de cabeça para baixo | Tesseract numa cópia reduzida (~1100 px) | `orientacao.py` |
| Localizar dados pessoais para a **tarja** da cópia anonimizada | Tesseract em **3 passadas**, com palavras e posições | `render.py` |
| Texto das páginas lidas por modelo de IA | o **próprio modelo** transcreve em `texto_ocr` | `providers.py` (Camadas 2 e 3) |

Pontos importantes:

- **PDF digital não passa por OCR**: o texto vem do próprio PDF, exato e com posição por palavra.
- **PDF escaneado sem Tesseract e sem chave de IA** vira "página sem texto reconhecido" (confiança 0,30), vai para a fila de revisão e **não é descartada**.
- **O OCR local é instável** em escaneados inclinados, com ruído ou carimbo. Nenhum pré-processamento acerta tudo sozinho; por isso a cópia anonimizada usa 3 passadas e une o resultado. Mesmo assim, campos que o OCR não lê não são tarjados (ver [seção 15](#15-anonimização-e-proteção-do-texto-lido)).
- **O texto lido é dado sensível** (CPF inteiro, nomes, endereços). Ele é gravado **cifrado** no banco (ver [seção 15](#15-anonimização-e-proteção-do-texto-lido)).

### As três passadas de OCR da tarja

A página é lida como tons de cinza e como contraste ampliado (`autocontrast`), com dois modos de layout do Tesseract (`--psm 6`, blocos de texto; `--psm 11`, texto solto). Cada passada acerta campos que a outra erra; as tarjas são a **união** das detecções. A imagem é ampliada para ~1650 px de largura (cerca de 200 dpi em A4), onde o Tesseract lê melhor texto pequeno.

## 7. Reconhecimento: o tipo de cada página

### O catálogo: 58 tipos curados + os que a IA descobre

Definido em `ia-core/ia_core/catalogo.py` e espelhado na tabela `document_types` do banco. Cada tipo tem nome, **pistas de texto** e se costuma exigir assinatura. São 58 tipos curados e, além deles, os **tipos que a IA descobre** ao ler (próxima subseção).

| Grupo | Exemplos |
|---|---|
| Admissão e contrato | contrato de trabalho, ficha de registro, CTPS, termo de responsabilidade, declaração de dependentes |
| Folha e jornada | holerite, cartão de ponto, recibo de benefícios, recibo de férias, comprovante de pagamento |
| Saúde e segurança | ASO, atestado médico, ficha de EPI, treinamento de NR, ordem de serviço, CAT |
| Desligamento | TRCT, aviso prévio, pedido de demissão |
| Disciplina e rotina | advertência, suspensão, justificativa de falta, notificação ao empregado |
| Documentos pessoais de admissão | CPF (comprovante), título de eleitor, certidão de nascimento ou casamento, comprovante de escolaridade, certificado de reservista, acordo de compensação / banco de horas |
| Empresa terceirizada/fornecedora | CRF-FGTS, CNDT, CND federal, guia de FGTS, guia de INSS, DARF, contrato de prestação de serviço, contrato social, cartão CNPJ, nota fiscal, apólice de seguro, auto de infração, processo judicial, relatório de auditoria, PGR/LTCAT, alvará, ofício, capa/protocolo de documentação mensal |
| Comunicação | aviso de recebimento (AR) |
| Residual | `OUTRO` |

### Como o motor local classifica

Cada pista que aparece no texto (comparado sem acento e em maiúsculas) soma pontos: **3** para pista longa (mais específica, mais de 12 caracteres) e **1** para pista curta ou palavra isolada. O tipo com mais pontos vence. A **confiança** cai quando o segundo colocado está perto (margem menor que 2 pontos), porque a página é ambígua.

Exemplos: `"TERMO DE RESCISAO"` (3 pontos) e `"VERBAS RESCISORIAS"` (3) apontam para TRCT; `"AVISO DE RECEBIMENTO"` e `"DADOS DO RECEBIMENTO"` apontam para AR; `\bCTPS\b` (1) sozinho é pista fraca de CTPS.

Limite conhecido: classificação por pistas é frágil quando o OCR deturpa o texto ou quando o documento cita outro tipo (uma página de TRCT que menciona "CTPS" pode empatar). A saída é a confiança baixa e a revisão humana, não um chute.

### Como os modelos de IA classificam

Recebem a lista de códigos do catálogo (os curados e os já descobertos) e devolvem o tipo diretamente, com os mesmos campos. Um código fora do catálogo não vira `OUTRO` às cegas: vira uma **proposta de tipo novo** (ver abaixo). O tipo da página anterior vai no prompt como contexto ("tipo anterior"), o que ajuda a reconhecer continuações.

### Tipos descobertos pela IA (para não cair em "OUTRO")

Um documento legível que nenhum dos 58 tipos cobre não precisa virar `OUTRO` e esperar classificação humana. Os modelos (Camadas 2 e 3) devolvem, nesse caso, `tipo=OUTRO` **mais** `tipo_novo`: o **nome genérico** do tipo ("Procuração", "Laudo de insalubridade"), o **escopo** (de pessoa ou da empresa), a **categoria** e de 2 a 4 **pistas** (frases impressas no documento). O IA Core então:

1. **Reaproveita o que já existe.** Se o nome equivale a um tipo do catálogo ("Nota fiscal de serviço" é `NOTA_FISCAL`; "Guia de recolhimento do FGTS" é `GUIA_FGTS`), usa o existente em vez de criar um duplicado. A comparação é por palavras do nome e do código, com ao menos duas palavras em comum.
2. **Recusa o que não é nome de tipo.** Nome vago ("Documento", "Declaração", "Outro"), com número longo, e-mail, CPF ou CNPJ (a IA descreveu uma instância, não um tipo), ou fora de 4 a 60 caracteres. Também não cria tipo quando a confiança da leitura está abaixo de **0,70** (`IA_CONF_TIPO_NOVO`) ou a página é ilegível ou traz vários documentos.
3. **Confere as pistas no texto.** Uma pista só vale se a frase está **de fato na página lida** (barra "memória" do modelo), não tem número e não coincide com a pista de outro tipo. Sem pista válida o tipo ainda é criado, mas não aprende regra local.
4. **Registra o tipo.** O backend o grava no catálogo global (`origem = IA`, com as pistas) com validação própria e um teto de **150** tipos criados pela IA (`IA_MAX_TIPOS_AUTOMATICOS`). O documento já sai classificado, com um alerta informativo `TIPO_IA`, e o resumo do lote lista os tipos novos.

**Por que isso reduz custo.** As pistas aprendidas viram regras da Camada 1. Na próxima página do mesmo tipo, o classificador local a reconhece **sem chamar modelo**: duas pistas encontradas fecham sozinhas (confiança 0,86, o limite do tipo aprendido); uma só pede conferência do modelo de texto (0,75). O backend reenvia ao IA Core os tipos descobertos a cada lote (`tipos_extras`), então o aprendizado **sobrevive à reinicialização** do serviço e vale para todas as empresas.

**Quem confere.** Em *Plataforma → Catálogo* o Master vê os tipos marcados "IA · não revisado", pode **renomear** (o nome vale para todas as empresas) e **confirmar**; a confirmação não apaga o aprendizado. Tipos da IA não têm exigência cadastrada: o documento fica guardado, pesquisável e visível, e a empresa pode criar a exigência depois.

**Limites.** O catálogo é **global**: o nome do tipo (nunca o conteúdo) é visível a todas as empresas, por isso o nome é restrito a nome genérico. Um nome ruim aceito pela IA ("Laudo Insalubridade", sem preposição) é cosmético e se corrige pelo Master. Duas descobertas simultâneas do mesmo tipo com nomes diferentes podem gerar dois tipos; o Master unifica renomeando. **Só foi testado com um modelo simulado** (E2E `backend/scripts/e2e_descoberta_tipos.py`): a qualidade real das propostas de nome e de pista com OpenAI/Gemini não foi medida.

## 8. Extração de campos

`ia-core/ia_core/extracao.py` (regras) e o schema dos modelos (IA).

| Campo | Como o motor local obtém |
|---|---|
| **CPF** | primeiro CPF com **dígito verificador válido**, tolerando o que o OCR estraga: separadores trocados por espaço (`790.864 532 10`) e zero lido como letra O logo depois do rótulo "CPF". O dígito verificador impede falso positivo. Sem válido, o primeiro encontrado (e a validação gera alerta) |
| **CNPJ e razão social da empresa** | prefere o CNPJ rotulado como contratada/prestadora/fornecedora/empregador; **ignora o da contratante**; sem rótulo, o primeiro CNPJ com dígito verificador válido |
| **Nome** | após rótulos como "Nome", "Colaborador", "Empregado", "Titular"; ou "Eu, ..." |
| **Matrícula** | após "Matrícula" |
| **Competência** | `AAAA-MM` a partir de "Competência", "Referente ao Mês: Abril/2026", "Pagamento de salário 04/2026", "Período de apuração" (inclusive com o valor na **linha seguinte** ao rótulo), ou de um período que cobre um mês só ("01/04/2026 a 30/04/2026"). Antes só entendia "Competência: MM/AAAA" e acertava 13% das páginas de OCR; agora acerta 46% (o resto não traz o dado no texto lido) |
| **Data do documento / validade** | datas `dd/mm/aaaa` e rótulos "Validade", "Vencimento" |
| **Horas extras** | total no cartão de ponto (HH:MM) e valor pago no holerite (R$) |

O motor sabe distinguir **quem é o dono do risco** num contrato: ele cita duas empresas, e vale a contratada, porque é dela a responsabilidade trabalhista que se quer acompanhar.

Dados sensíveis dos campos são mascarados ao gravar: o CPF em `campos` vira `***.456.789-**`. O CPF completo só existe cifrado (AES-GCM) e como **hash cego** (HMAC) para busca.

## 9. Separação: de páginas para documentos

Um lote é uma pilha de páginas; **um documento pode ter várias páginas** e **várias páginas de documentos diferentes podem estar misturadas**. `ia-core/ia_core/agrupar.py` reúne as páginas, de forma determinística, e vale para **qualquer provedor**.

### Regras, em ordem de prioridade

Para cada página, decide-se se ela **continua o documento anterior** ou **abre um novo**:

1. **Marcador de paginação impresso.** "Página 2/3", "Folha 2/2", "(PAG 2/2)", "fls. 3 de 5". Se a contagem fecha, a página entra no documento aberto, **mesmo que o tipo lido seja outro**: a página 1 pode ter vindo ilegível ou rotacionada. "Página 1/N" sempre abre documento novo. O marcador tolera o erro comum de OCR que lê a barra como `1` ("Folha 212" é lida como 2 de 2). Totais impossíveis (3 de 2) são descartados. Sem total declarado, a página não é colada, só pela contagem, em um documento de **outro tipo bem identificado**.
2. **Número que identifica o documento.** O número do objeto do AR (`FICT 829 320 540 AR`, ou o código dos Correios `BR…BR`) aparece na frente e no verso: liga as páginas **mesmo longe uma da outra** (ARs intercalados). Se os dois lados têm número legível e ele **difere**, nunca são juntados.
3. **Páginas complementares conhecidas.** Frases que identificam uma página que completa outro documento:
   - "**Termo de quitação**" ou "plena e geral quitação" → completa o **TRCT**;
   - "**Dados do recebimento**" → completa o **AR**.

   A página entra no documento anterior daquele tipo, **antes ou depois** da página principal. Com outra página no meio, liga pelo **CPF** do trabalhador. Uma folha que traz o título do próprio tipo (AR com frente e verso na mesma folha) **já está completa** e não é anexada.
4. **`inicia_documento=false`** informado pelo provedor: anexa ao último documento **do mesmo tipo**.
5. Caso contrário, abre um documento novo.

### O que acontece depois de agrupar

- **Tipo e título do documento**: os da página lida com **mais confiança** (uma página ilegível não rebaixa um contrato a `OUTRO`).
- **Confiança do documento**: a da **pior página**. Um documento vale tanto quanto sua página mais frágil.
- **Páginas em branco** separam documentos e são **descartadas**: nunca viram documento, nem "OUTRO". O lote informa quantas foram ignoradas (`paginas_em_branco`). Como o agrupador também confere o aviso "intencionalmente em branco", a regra vale para qualquer provedor de IA. (Uma página com tinta que o OCR não leu **não** é tratada como branca; vai para revisão.)
- **Campos**: o primeiro valor não vazio encontrado entre as páginas.
- Para cada documento, o IA Core calcula **alertas**, **não conformidades**, **dados sensíveis**, **checklist**, **texto anonimizado** e **telemetria de tokens**.

### Correção humana

Na revisão, o RH pode **dividir** um documento em um ponto, **juntar** com o seguinte, mudar o tipo, vincular a outra pessoa ou rejeitar. Ao dividir ou juntar, o texto é refeito a partir das páginas e anonimizado de novo pelo IA Core.

### Limites conhecidos da separação

- **Folha com vários documentos** (por exemplo, dois ARs lado a lado numa só imagem) **não é recortada** automaticamente; é sinalizada (`MULTIPLOS_DOCUMENTOS`) e vai para revisão.
- **Frente e verso do AR em folhas diferentes, sem número de objeto legível**, podem ficar separados.
- **Cartão de ponto de duas páginas em que o OCR não lê nem "Folha 2/2"** fica separado.

## 10. Qualidade da imagem e orientação

### Nitidez, branco e borrão

`ia-core/ia_core/qualidade_img.py`, antes de gastar OCR ou IA numa página sem texto:

- **Em branco**: folha lisa (desvio padrão dos pixels < 3 e menos de 0,3% de escuros) **ou** com menos de **0,03% de tinta agrupada** no **miolo** da página (`IA_TINTA_MIN`). O miolo ignora 8% de cada lado e 5% em cima e embaixo; "escuro" é medido contra a cor do próprio papel; e "agrupada" só conta escuro que tem outro escuro por perto (traço de letra, assinatura, carimbo), de modo que **poeira e pontinhos de ruído**, que são isolados, não contam. Sombra de borda do scanner, furos de perfuração, grampo, ruído, poeira, cabeçalho/rodapé e número de página **não** fazem uma folha parecer ter conteúdo (antes, sombra e furos faziam a folha cair em "borrada" e virar um documento `OUTRO`). Medido nas 696 páginas dos 30 lotes de teste: a menor página real tem 0,0014 de tinta agrupada; a poeira, no máximo 0,00004.
- **Só marca d'água/carimbo** ("AMOSTRA - DOCUMENTO FICTÍCIO", "CÓPIA", "RASCUNHO"): o OCR lê só a marca **e** a folha tem menos de 0,2% de tinta (`IA_TINTA_MARCA`). Uma página real com carimbo tem muito mais tinta e segue para análise.
- **Texto que não é de documento**: menos de 8 letras e dígitos (um "3" solto), o aviso curto "página intencionalmente deixada em branco" ou a **folha separadora de lote** ("SEPARADOR DE DOCUMENTOS", "FOLHA SEPARADORA"), tudo com menos de 120 letras e dígitos. Folha separadora é artefato de digitalização, não documento: é descartada como a folha em branco. Texto curto com tinta na imagem **não** é descartado: pode ser manuscrito ou foto.
- **Borrada**: variância do filtro de bordas abaixo de **600** (`IA_NITIDEZ_MIN`). Texto nítido fica em torno de 2000; desfoque forte, em torno de 400. **Calibrado com amostras sintéticas**: pode ter falsos positivos e negativos em digitalizações reais, e o limite é configurável.

Página borrada **não gasta tokens**: recebe confiança 0,20, o alerta `IMAGEM_BORRADA` ("envie uma imagem mais nítida") e vai para revisão.

### Orientação: a página é girada de verdade

`ia-core/ia_core/orientacao.py`. Páginas escaneadas de cabeça para baixo (ou de lado) saem do OCR como lixo e viram `OUTRO`, o que quebra a classificação e o agrupamento. No fatiamento, para páginas **só de imagem**:

1. Lê a página reduzida e conta quantas **palavras reconhecíveis** aparecem (vocabulário do catálogo e palavras comuns de documentos trabalhistas).
2. Se o texto **não parece legível**, tenta **180°, 90° e 270°** e fica com a leitura melhor, **só se for claramente melhor** (evita girar manuscrito ou ruído por acaso).
3. A imagem **guardada** é girada: visualização, download e cópia anonimizada já saem na posição certa. O manifesto registra `rotacao_corrigida`.

Páginas em branco ou sem texto nenhum não são giradas. Custo: cerca de 1 s por página escaneada.

## 11. Validações e checklist por documento

Regras sobre o texto e os campos de cada documento (`validacoes.py` e `checklist.py`). Produzem **alertas** (aparecem no documento) e **não conformidades** (alimentam o painel e os indicadores).

| Regra | Condição | Resultado |
|---|---|---|
| CPF inválido | dígito verificador incorreto | alerta |
| Certidão vencida | CRF, CNDT ou CND com validade passada | não conformidade `CERTIDAO_VENCIDA` (erro) |
| Documento vencido | validade passada, demais tipos | alerta `DOCUMENTO_VENCIDO` (erro) |
| Sem assinatura | tipo que costuma ser assinado, sem "assinado/assinatura/rubrica" | `DOCUMENTO_SEM_ASSINATURA` |
| Jornada acima de 10 h | cartão de ponto com jornada diária > 10:00 | `JORNADA_ACIMA_10H` |
| Intervalo menor que 1 h | cartão de ponto | `INTERVALO_INFERIOR_1H` |
| Ponto britânico | marcações idênticas todos os dias | `PONTO_BRITANICO` |
| FGTS divergente | holerite/guia com FGTS depositado ≠ devido | `FGTS_DIVERGENTE` (erro) |
| Recusa sem testemunhas | "recusou ... assinar" sem "testemunha" | `RECUSA_SEM_TESTEMUNHAS` |

O **checklist** de cada documento mostra item por item: legibilidade (confiança contra o limiar), validade vigente (vencido, vence em até 30 dias, válido), assinatura e regras específicas, como **ASO** (parecer APTO/INAPTO, CRM do médico, emissão nos últimos 12 meses, NR-07), **ficha de EPI** (número do CA, NR-06) e **treinamento de NR** (norma e reciclagem em 24 meses). Cada item é `OK`, `FALHA`, `ALERTA` ou `REVISAO_HUMANA`.

## 12. Vínculo, pré-cadastro e revisão humana

Do callback do IA Core em diante, o trabalho é da API Go (`backend/internal/documents/ingest.go`).

### A quem pertence o documento

Para documentos de escopo "funcionário", em ordem:

1. **CPF** pelo **hash cego** (HMAC do CPF com chave da empresa): permite achar a pessoa sem guardar nem comparar CPF em claro. Um **CPF válido desconhecido nunca** é ligado a outra pessoa por nome ou matrícula.
2. **Matrícula**.
3. **Nome por similaridade** (trigramas, sem acento): só vincula com similaridade **≥ 0,85** e **margem de pelo menos 0,10** para o segundo candidato. Vínculo por nome sempre vai para revisão (`VINCULO_POR_NOME`).

Sem vínculo, o documento fica em **"Sem vínculo"** (`SEM_VINCULO`).

### Pré-cadastro automático

Se a empresa permitir, e o documento tiver **CPF válido e nome**, a página for legível e não houver vários documentos na imagem, o funcionário é **pré-cadastrado** com origem `PRE_CADASTRO`. Ele recebe um aviso de "complete o cadastro" e **não gera avalanche de pendências** retroativas: sem data de admissão, a conformidade mensal começa na primeira competência com documento.

### Fornecedores e terceirizadas

O **CNPJ lido no documento** agrupa tudo da mesma empresa (`ResolveSupplier`). O funcionário herda o empregador do primeiro documento; um documento de **outra** empresa para o mesmo funcionário gera `EMPREGADOR_DIVERGENTE`.

### O mesmo documento escaneado mais de uma vez (duplicata de conteúdo)

O SHA-256 da Camada 0 só reconhece páginas **idênticas byte a byte**. O mesmo documento escaneado duas ou três vezes, de formas diferentes (outra qualidade, inclinação, ruído), tem hashes diferentes mas o **mesmo conteúdo**. Para não guardar essas cópias, a ingestão compara o **texto lido por OCR** (`documents/similaridade.go`, `dupconteudo.go`):

1. **Candidatos:** documentos já guardados da mesma empresa, da **mesma pessoa** (ou ambos sem vínculo e com o mesmo CPF lido), do mesmo fornecedor, e com a mesma competência, data e validade quando ambos as têm. O **tipo não é exigido**: o mesmo documento escaneado pior pode ser lido como outro tipo (o OCR estraga o título).
2. **Similaridade do texto** (0 a 100%): comparação **por palavras**, tolerante a erro de OCR (palavra com poucas letras trocadas casa com a original; confusões como `ASS1NATURA`, `L1QUIDO` são tratadas como a palavra certa). Lixo de OCR (pedaços de 1 a 2 letras ou sem vogal) é ignorado.
3. **Trava de valores:** números e datas de 4 ou mais dígitos (quantias, datas, documentos) são comparados à parte e **não dependem do limite do cliente**. Duas versões com valores diferentes são documentos diferentes (por exemplo, um holerite retificado), por mais parecido que seja o modelo. Tolera-se só o que o erro de OCR explica: até 2 valores (ou 8%) divergentes.
4. **Limite do cliente:** padrão **85%**, ajustável em *Configurações*, **nunca abaixo de 70%**. Acima do limite (e passando as travas), é o mesmo documento. Com texto idêntico bastam 8 palavras; senão, o mínimo é 15.
5. **Qual cópia fica:** a que uma pessoa já revisou; senão, a de **leitura mais confiável**; no empate, a que já estava guardada.
6. **A outra cópia não é apagada:** vira `REJEITADO` com o motivo `DUPLICATA_CONTEUDO` e a ligação ao documento mantido (`duplicata_de`). Some do dossiê, da conformidade, dos indicadores e da busca, mas aparece no lote ("N duplicados descartados") com o botão **Restaurar**, que a devolve para a fila de revisão. O arquivo original do lote não é alterado.

**Calibração com OCR real** (Tesseract, 4 páginas escaneadas do gerador × 3 níveis de degradação: outro scanner leve, borrado/JPEG médio, ruído forte):

| Página | leve | médio | pior |
|---|---|---|---|
| Certidão (texto corrido) | 98% | 92% | 96% |
| Holerite | 91% | 82% | 63% |
| Guia com tabela de 56 valores | 81% | 87% | 82% (**bloqueada pela trava de valores**) |
| Cartão de ponto (tabela) | 69% | 58% | 45% |
| **Páginas diferentes entre si** | 19% a 32% | | |

Em um teste ponta a ponta com seis escaneamentos reais, os 3 da certidão viraram **1 documento guardado**; os 3 do cartão de ponto ficaram todos guardados, o que é o comportamento prudente para tabela.

**Limites:** com o padrão de 85%, escaneamentos muito degradados (holerite "médio", 82%) não são reconhecidos; o cliente pode baixar o limite (até 70%), aceitando mais risco. **Tabelas e cartões de ponto** têm OCR instável e raramente passam. Duas versões do mesmo documento com **no máximo 2 valores diferentes** podem ser tratadas como a mesma. Por isso o descarte é reversível.

### A mesma empresa escrita de jeitos diferentes

Quando o **CNPJ** é lido, ele agrupa tudo da empresa (fornecedor). Sem CNPJ legível, a decisão é pelo **nome**, que muda de documento para documento ("Aparecida Limpeza Soluções Ltda", "APARECIDA LIMPEZA SOLUCOES LTDA", "APARECIDA LIMPEZA DOMÉSTICA"). Na ingestão (`documents/empresa.go`):

1. **Chave do nome:** maiúsculas, sem acento nem pontuação e **sem o tipo societário** (Ltda, ME, EPP, S/A...). Duas grafias com a mesma chave são a mesma empresa.
2. **Fornecedor já cadastrado:** se o documento não traz CNPJ e a chave do nome é igual à de um fornecedor, o documento é ligado a ele.
3. **Própria empresa:** o nome lido é comparado com a razão social e o nome fantasia **do cadastro**. É a mesma empresa se as chaves são iguais, **ou** se começam pela mesma palavra e compartilham pelo menos duas palavras ("APARECIDA LIMPEZA DOMÉSTICA" × "Aparecida Limpeza Soluções Ltda"). Essa regra frouxa só vale contra o nome cadastrado da própria empresa; entre empresas desconhecidas, só a chave exata junta.
4. O nome passa a ser o do cadastro; a grafia lida fica em `campos.empresa_nome_lida`, e a pasta de destino usa o nome unificado.
5. Documentos já gravados são corrigidos na subida da API (idempotente). A tela de pastas também agrupa pela chave do nome.

Por isso o **nome da empresa no cadastro precisa estar correto**: ele é a âncora. Uma empresa diferente cujo nome comece igual e compartilhe duas palavras com o cadastro, e que não traga CNPJ legível, seria tratada como a própria empresa.

### Divergências e duplicidade

- Nome no documento diferente do cadastro → `DADOS_DIVERGENTES`.
- CPF da nova cópia diferente do funcionário indicado → `CPF_DIVERGENTE`.
- Mesmo tipo, funcionário e competência de um documento já aprovado → duplicidade/substituição.

### Quando vai para a revisão humana

Um documento sai como `AUTO_APROVADO` se **não** houver nenhum motivo; caso contrário fica `AGUARDANDO_REVISAO`. Os motivos:

| Motivo | Disparo |
|---|---|
| `BAIXA_CONFIANCA` | confiança do documento < limiar da empresa (**padrão 0,75**) |
| `PAGINA_ILEGIVEL`, `IMAGEM_BORRADA` | página sem leitura |
| `TIPO_OUTRO` | tipo não identificado |
| `SEM_VINCULO`, `VINCULO_POR_NOME` | pessoa não localizada ou só por nome |
| `DADOS_DIVERGENTES`, `CPF_DIVERGENTE`, `CPF_INVALIDO`, `EMPREGADOR_DIVERGENTE` | inconsistências |
| `MULTIPLOS_DOCUMENTOS` | mais de um documento na mesma imagem |
| `ALERTA_ERRO` | algum alerta de severidade "erro" |
| `LIMITE_FUNCIONARIOS` | plano não permite o pré-cadastro |

Ações do revisor: **confirmar, corrigir campos, mudar tipo, vincular, dividir, juntar, rejeitar, substituir o anterior**. Uma transcrição manual de original ilegível fica marcada como tal (`TRANSCRICAO_MANUAL`) e **não comprova sozinha** uma exigência.

## 13. Conformidade: o que falta, vence ou está em dia

`backend/internal/compliance/engine.go`. É o cruzamento entre **o que a empresa exige** e **o que está no dossiê**.

- **Exigências** (`requirements`) valem para **todos**, um **setor**, um **cargo** ou um **funcionário**. A mais específica vence: **funcionário > cargo > setor > todos**. Cada empresa define as suas.
- Cada exigência tem um **momento**: admissão, desligamento, periódico, anual, **mensal** ou por evento.
- O estado de cada item:
  - `PENDENTE`: não há documento validado;
  - `OK`: há documento e (se tem validade) está vigente;
  - `A_VENCER`: vence dentro da antecedência configurada;
  - `VENCIDO`: a validade passou.
- Exigências **mensais** geram um item por competência já encerrada, desde a admissão (ou desde a primeira competência com documento, no pré-cadastro), limitado a 35 meses, e até o desligamento.
- **Só documento com origem na IA/imagem comprova** uma exigência. Dado **digitado** manualmente (lançamento manual) pode acrescentar indicadores, mas **nunca prova presença** de um documento.
- A conformidade é **recalculada** a cada documento novo, correção ou vínculo, e uma rotina diária gera os alertas de vencimento.
- Para fornecedores, cada fornecedor tem o seu conjunto de itens (`recomputeSuppliers`).

## 14. Indicadores de risco trabalhista

`backend/internal/compliance/risk.go`. É a parte que mais se parece com "previsão", e vale ser preciso sobre o que ela **é**:

> **Indicadores são regras determinísticas, sem aprendizado de máquina e sem probabilidade.** Cada um sinaliza uma situação que costuma gerar reclamação trabalhista, com a **base legal** que a motiva. Servem para **triagem**: indicam onde o RH e o jurídico devem olhar primeiro. **Não são parecer jurídico nem prova de irregularidade.**

### Como são produzidos

Uma função pura (`deriveRisks`) recebe funcionários, documentos e itens vencidos e devolve os indicadores. Depois, `RecomputeRisks` grava no banco, **preserva os que o administrador marcou como ignorados** e **remove os que deixaram de existir** (documento corrigido ou substituído). São recalculados a cada mudança.

### Catálogo de indicadores

| Categoria | Indicador | Gravidade | Base |
|---|---|---|---|
| Jornada | Jornada acima de 10 h | alto | CLT art. 59 |
| | Intervalo intrajornada insuficiente | alto | CLT art. 71 |
| | Ponto com marcações uniformes | alto | TST Súmula 338 |
| Remuneração | FGTS depositado ≠ devido | alto | Lei 8.036/90 art. 15 |
| | Horas extras no ponto sem pagamento no holerite | médio | CLT art. 59 §1º, CF art. 7º XVI |
| | Ponto com horas extras e sem holerite da competência | médio | CLT art. 464 |
| Férias | Sem recibo de férias nos últimos 24 meses (vínculo > 23 meses) | médio | CLT art. 137 |
| Rescisão | TRCT datado > 10 dias após o desligamento | médio | CLT art. 477 §6º e §8º |
| | Sem TRCT validado 10 dias após o desligamento | médio | CLT art. 477 §6º e §8º |
| Registro | Há holerite/ponto mas nenhum contrato, ficha de registro ou CTPS | médio | CLT art. 29 |
| | Documento fora do período do vínculo (antes da admissão ou depois do desligamento) | médio | coerência de datas |
| Prova | Documento sem assinatura; recusa sem testemunhas; dados divergentes; imagem borrada; página ilegível; tipo não identificado; CPF inválido ou divergente; transcrição manual | médio/baixo/alto | CLT art. 464 e 818 |
| Segurança | ASO vencido; treinamento de NR vencido | médio | NR-7, NR-1 |
| Documental | Documento vencido; certidão vencida | médio | validade |

**Como a "previsão" de horas extras funciona**, como exemplo: o cartão de ponto da competência traz `horas_extras` (HH:MM) → procura o holerite **da mesma competência** → se não há holerite validado, `HOLERITE_AUSENTE_COM_PONTO`; se há mas sem pagamento de horas extras identificado, `HE_SEM_PAGAMENTO`. O texto do indicador pede explicitamente para **conferir o original**, porque a extração pode ter falhado.

### Indicadores de fornecedores e terceirizadas

Para a **contratante**, o risco é a **responsabilidade subsidiária** pelas obrigações trabalhistas da terceirizada (TST Súmula 331; Lei 6.019/74 art. 5º-A e 5º-B). Só entram fornecedores **ativos**:

| Indicador | Quando |
|---|---|
| Contrato ausente | sem contrato de prestação de serviço validado |
| Contrato vencido | contrato encerrado e ainda há funcionários ativos alocados |
| Certidão ausente | terceirizada (ou fornecedor com alocados) sem CRF-FGTS, CNDT ou CND federal |
| Guia de FGTS ausente | há holerite ou ponto da competência, mas nenhuma guia dessa competência |
| Autuação / fiscalização | existe um auto de infração em nome do fornecedor |
| Processo trabalhista | existe citação ou processo registrado |
| Auditoria de risco alto | relatório de auditoria classificou o risco como ALTO |

### Nível de exposição do fornecedor

Resume em um rótulo: **ALTA** se há indicador de gravidade alta **ou** exigência vencida; **MÉDIA** se há qualquer indicador ou exigência pendente; **BAIXA** se está tudo em dia. Um fornecedor com trabalhadores alocados é cobrado como terceirizada.

### O que os indicadores **não** fazem

- Não estimam valor de condenação nem chance de perder um processo.
- Não leem a lei: cada regra foi escrita à mão.
- Não substituem a conferência do original quando a leitura tem baixa confiança.
- Dependem da **qualidade da leitura**: se a IA não leu o campo, o indicador pode não disparar (falso negativo) ou disparar por ausência de dado (falso positivo).

## 15. Anonimização e proteção do texto lido

### Detecção de dado pessoal

`ia-core/ia_core/anonimizacao.py`. Padrões para **CPF, CNPJ, RG, CEP, telefone, e-mail, CID, PIS, dado bancário**, mais **nome** (após rótulos como Nome, Colaborador, Empregado, Titular, Destinatário) e **endereço** (após "Endereço", "Residência", "Domicílio"). O rótulo não diferencia maiúsculas de minúsculas.

**Regras por posição** (`caixas_por_posicao`, para o que o texto corrido não revela), aplicadas sobre as palavras com posição:

- **Nome na linha de um CPF**, também em uma faixa vertical em torno dele (em página inclinada o OCR separa o CPF e o nome da mesma linha da tabela): listas de trabalhadores.
- **Valor abaixo do rótulo**: "Empregado", "Trabalhador", "Nome", "Endereço", "Data de nascimento" com o campo na linha de baixo, como nos formulários de TRCT e de ponto.
- **Propagação por coluna de tabela**: se uma coluna tem 3 ou mais CPFs (ou nomes) tarjados, as células dessa coluna entre eles também são tarjadas, mesmo quando o OCR errou aquela célula (por exemplo `709+135.624-16`).
- **Logradouro sem rótulo** ("Rua ...", "Avenida ...", "Travessa ..."): a linha do endereço.
- Um nome só é tarjado como sequência de **pelo menos duas palavras** fora do vocabulário de formulário; uma palavra solta (rótulo, título) não é.

Máscaras: CPF `***.456.789-**`, CNPJ `**.***.***/****-**`, demais `[TIPO OCULTO]`. O **mesmo formato** é usado em todo o sistema.

### Cópia anonimizada (PDF com tarjas)

O PDF anonimizado é gerado **queimando a tarja preta na própria imagem** (os pixels são substituídos, então não é reversível), **sem camada de texto** e **sem metadados**. As tarjas vêm de:

1. as palavras com posição (texto nativo, ou OCR em 3 passadas para páginas escaneadas);
2. os **nomes já conhecidos** do documento (funcionário cadastrado), que são tarjados onde aparecerem, mesmo sem rótulo e com pequenos erros de OCR;
3. as caixas detectadas no fatiamento.

Se o OCR não está disponível, a cópia é **recusada** com uma mensagem clara, em vez de entregar um PDF "anonimizado" sem tarja.

**Quanto ainda aparece** (medido por OCR sobre a própria cópia anonimizada, em 4 lotes fictícios com os dados reais do gerador como gabarito): ainda legíveis depois da tarja, de tudo que o OCR leu no original, **nomes 1 de 71, CPF 1 de 53, endereços 0 de 5, CEP 0 de 4, PIS 0 de 2**. Antes das regras por posição eram 33 de 71 nomes e 5 de 5 endereços. A medida depende do OCR conseguir ler o dado no original e na cópia: um dado que o OCR não lê, um humano pode ler. **Data de nascimento não pôde ser medida** (o OCR não leu nenhuma nos originais).

**Excesso de tarja:** as regras preferem tarjar a mais. O endereço da própria empresa e valores ao lado de um endereço podem ser cobertos (a barra do endereço vai até a margem da página).

**Limite real:** o que o OCR não consegue ler (campo inclinado, ruído, manuscrito, carimbo) **não é tarjado**. Em documentos sensíveis, **revise a cópia antes de enviar a terceiros**.

### O texto lido fica cifrado

O texto completo do documento, o texto embutido do PDF, as palavras com posição e a análise de cada página (texto e campos) são gravados com **AES-256-GCM** e a chave de dados da empresa (`backend/internal/ocrseal`). O contexto autenticado (AAD) inclui a finalidade e a empresa: o texto cifrado de uma empresa não abre com a chave de outra, nem para outra finalidade. Lotes anteriores à criptografia são migrados na subida da API.

Seguem em claro, por serem estruturados e mascarados: `campos` (com CPF mascarado), `texto_anonimizado` e `dados_sensiveis`. Nomes e valores em `campos` (por exemplo, salário) **continuam em claro** porque alimentam filtros e a conformidade em SQL.

Consequência para a **busca em texto**: o índice não pode ser construído sobre texto cifrado, então é gerado a partir do **texto anonimizado**. Não se encontra um documento digitando o CPF; para achar uma pessoa por CPF, use a busca de funcionário (hash cego). O acesso de suporte recebe sempre só o texto anonimizado.

### Quando um provedor externo vê os dados

Com chave OpenAI ou Gemini, **imagens e textos das páginas que sobem às Camadas 2 e 3 saem para o serviço do provedor**. Isso exige uma decisão de tratamento de dados antes de usar com documentos reais. O motor local não envia nada para fora.

## 16. Resiliência do processamento

Um lote grande não pode se perder se um processo cair no meio.

- **Uma página por vez, com checkpoint.** A página anterior é contexto da seguinte. Cada análise é gravada **assim que termina**. Se o processo cair, o lote é retomado do ponto em que parou: só as páginas pendentes são reprocessadas; as concluídas voltam ao IA Core como "análises prévias".
- **Callbacks assinados e idempotentes.** O IA Core assina cada callback com HMAC-SHA256 sobre `timestamp.corpo` e uma chave de idempotência; a API confere a assinatura e rejeita reenvios fora da janela de 10 minutos. O envio tem 4 tentativas com espera crescente. Um callback repetido é ignorado.
- **Reprocessamento do lote.** Até **3 tentativas** com espera crescente (5 s, 10 s, ...). Esgotadas, o lote vira `FALHOU`, entra em **dead letters** e gera notificação.
- **Watchdog.** Lote sem progresso por **3 minutos** (worker ou IA Core travado) é reagendado.
- **Paralelismo.** Vários lotes correm em paralelo (`IA_WORKERS`, padrão 4); as páginas de um mesmo lote são sequenciais.
- **Verificado em teste de caos:** matar o worker e o IA Core no meio de um lote de 60 páginas e reiniciá-los produz **o mesmo resultado** do processamento sem interrupção.

## 17. Custo e telemetria (FinOps)

Cada página registra: **camada que resolveu**, **tokens consumidos**, hash SHA-256 e se foi reaproveitada do cache. Por documento, o sistema guarda tokens consumidos e economizados (referência: 1.500 tokens por página enviada inteira como imagem, sem otimização) e uma estimativa de economia.

A tela de FinOps tem também um **simulador** com a distribuição de referência `30% / 45% / 15% / 10%` nas camadas 0/1/2/3. **Essas frações e os preços são premissas do cenário, editáveis, e não resultados medidos.** O consumo **real** aparece ao lado, calculado dos lotes processados.

Referência medida (Gemini, 6 páginas fictícias impressas): **3 a 4,4 mil tokens por página**, incluindo a resposta estruturada, e 9 a 17 s por página. A redução de imagem para 1024 px baixa o custo, e a página **não** é reduzida no armazenamento.

## 18. Medições e limites: o que foi e o que não foi validado

### Medições

| O quê | Resultado |
|---|---|
| **Agrupamento** (motor local, 6 lotes fictícios do gerador, 143 documentos) | documentos de várias páginas separados ou juntados errado: **de 15 de 15 para 2 de 15**; documentos totalmente corretos (tipo e páginas iguais ao gabarito): **de 96 para 115**; nenhum documento de página única passou a ser juntado por engano |
| **Orientação** (3 lotes do gerador) | **8 de 9** páginas giradas a 180° foram endireitadas; nenhuma página normal foi girada. A que faltou é uma página quase vazia, só com marca d'água |
| **Cobertura de classificação** (texto desenhado pelo gerador, 25 amostras por tipo) | 800 de 800. **Mede só o texto exato do gerador, não o OCR** |
| **Gemini** (6 páginas fictícias impressas) | 6 de 6 tipos corretos, confiança 0,95 a 0,99, CPF e CNPJ lidos |
| **Roteador com o catálogo de 58 tipos** (OCR real, 403 págs.) | Camada 3 de 64%/63% para **57%/58%** (folhas separadoras e marcas d'água deixaram de chamar modelo); Camada 1 em 24%/20%, com tipo correto em 98% e 100% das páginas que ela fecha. Os 14 tipos curados novos não pioraram nenhuma classificação |
| **Resiliência** | resultado idêntico após matar worker e IA Core no meio de um lote de 60 páginas |

### O que **não** foi validado

- **OpenAI não foi executada com chave real.** O código tem testes com cliente simulado; os nomes de modelo padrão (`gpt-5-mini`, `gpt-5`, `gpt-5-nano`) **não foram confirmados**. Use `/diagnostico`.
- **Gemini foi validado em apenas 6 páginas impressas.** **Manuscrito e imagens ruins não foram testados.** Os modelos `2.5-*` foram fechados para chaves novas durante os testes; os nomes mudam com o tempo.
- **Erros de tipo no motor local:** nos mesmos 143 documentos, **26** tiveram tipo diferente do gabarito, por páginas ilegíveis, manuscritas ou muito degradadas que o motor local não lê. Com provedor de IA a leitura tende a melhorar, mas **isso não foi medido**.
- **Limiar de nitidez** calibrado só com amostras sintéticas.
- **Documentos reais** de cada operação precisam ser usados para calibrar limiares (confiança, nitidez) e revisar as pistas do catálogo.

### Limites estruturais

- O motor local **não lê PDF escaneado sem Tesseract** (confiança 0,30) e **não lê manuscrito**.
- A classificação local por pistas **tem confusões** entre tipos parecidos.
- A separação não recorta folhas com **vários documentos** na mesma imagem.
- Os indicadores **dependem da qualidade da leitura** e são **triagem**, não parecer jurídico.
- Dados enviados a OpenAI ou Gemini **saem do ambiente**; é preciso decidir isso antes de usar documentos reais.

## 19. Configuração

| Variável | Efeito | Padrão |
|---|---|---|
| `IA_PROVIDER` | força `openai`, `gemini` ou `local` | automático |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | liga o provedor correspondente (OpenAI tem prioridade) | vazio = motor local |
| `OPENAI_MODEL`, `_FALLBACK`, `_LITE` | modelos de imagem, reserva e texto da OpenAI | `gpt-5-mini`, `gpt-5`, `gpt-5-nano` |
| `GEMINI_MODEL`, `_FALLBACK`, `_LITE` | idem para o Gemini | `gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite` |
| `OPENAI_REASONING_EFFORT` | esforço de raciocínio, para modelos que aceitam | vazio |
| `OPENAI_BASE_URL` | endpoint compatível (Azure, proxy interno) | vazio |
| `IA_IMAGE_MAX_PX` | lado máximo da imagem enviada ao modelo (WebP q80) | 1024 |
| `IA_NITIDEZ_MIN` | limite de nitidez abaixo do qual a imagem é "borrada" | 600 |
| `IA_WORKERS` | lotes processados em paralelo no IA Core | 4 |
| `limiar_confianca` (por empresa) | abaixo disso o documento vai para revisão | 0,75 |
| `MAX_UPLOAD_MB` | tamanho máximo de upload | 500 |

Em desenvolvimento, as chaves ficam em `ia-core/.env.local` (ignorado pelo Git). Detalhes em [VARIAVEIS_AMBIENTE.md](VARIAVEIS_AMBIENTE.md).

## 20. Onde está cada coisa no código

| Assunto | Arquivo |
|---|---|
| Fatiamento, texto nativo, palavras | `ia-core/ia_core/fatiar.py` |
| Orientação da página | `ia-core/ia_core/orientacao.py` |
| Qualidade da imagem | `ia-core/ia_core/qualidade_img.py` |
| Provedores e funil de camadas | `ia-core/ia_core/providers.py` |
| Catálogo e classificação | `ia-core/ia_core/catalogo.py` |
| Extração de campos | `ia-core/ia_core/extracao.py` |
| Marcadores de paginação e números de documento | `ia-core/ia_core/paginacao.py` |
| Agrupamento em documentos | `ia-core/ia_core/agrupar.py` |
| Validações e checklist | `ia-core/ia_core/validacoes.py`, `checklist.py` |
| Anonimização e tarjas | `ia-core/ia_core/anonimizacao.py`, `render.py` |
| Fila, fatiamento, callbacks, retomada | `backend/internal/batches/service.go` |
| Cache SHA-256 (Camada 0) | `backend/internal/batches/service.go` |
| Vínculo, pré-cadastro, revisão | `backend/internal/documents/ingest.go`, `review.go` |
| Conformidade | `backend/internal/compliance/engine.go` |
| Indicadores de risco | `backend/internal/compliance/risk.go` |
| Criptografia do texto lido | `backend/internal/ocrseal/` |
| Simulador de FinOps | `frontend/src/lib/finops.ts` |

Para o fluxo completo do produto, a arquitetura e as decisões de segurança, veja também o [README](README.md), a [ESPECIFICACAO_FUNCIONAL.md](ESPECIFICACAO_FUNCIONAL.md) e os ADRs em `backend/docs/adr/`.
