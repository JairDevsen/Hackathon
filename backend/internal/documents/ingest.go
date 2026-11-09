// Package documents: ingestão do resultado do IA Core, vínculo documento↔funcionário,
// regras de revisão humana e ações de revisão.
package documents

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/iacore"
	"github.com/agreser-innovations/citadel-ia/backend/internal/ocrseal"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cnpj"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/cpf"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/crypto"
	"github.com/jackc/pgx/v5"
)

type Ingestor struct {
	KR *crypto.Keyring
	// Anonimizar devolve o texto sem dados pessoais (IA Core). Usado ao dividir/juntar documentos, quando o texto é refeito.
	// Se for nil ou falhar, o documento fica sem texto anonimizado (e portanto fora da busca) até ser reprocessado.
	Anonimizar func(ctx context.Context, texto string) (string, error)
}

// Hints vêm do lote de "lançar documento legível": ligam o documento ao funcionário/tipo e substituem um documento ilegível.
type Hints struct{ EmployeeID, Tipo, Substitui *string }

type Summary struct {
	Fornecedores int      `json:"fornecedores_pre_cadastrados"` // fornecedores/terceirizadas criados a partir do CNPJ lido nos documentos
	PreCadastros int      `json:"pre_cadastros"`                // funcionários criados automaticamente a partir dos documentos
	Ilegiveis    int      `json:"classificacao_manual"`         // documentos ilegíveis/sem tipo que exigem classificação manual
	Documentos   int      `json:"documentos"`
	AutoAprovado int      `json:"auto_aprovados"`
	Revisao      int      `json:"para_revisao"`
	Duplicados   int      `json:"duplicados"` // documentos iguais escaneados de outra forma, descartados (restauráveis)
	SemVinculo   int      `json:"sem_vinculo"`
	Paginas      int      `json:"paginas"`
	EmBranco     int      `json:"paginas_em_branco"`     // folhas vazias (sombra, furos, ruído, só o número da página) ou separadoras: ignoradas, não viram documento
	TiposNovos   []string `json:"tipos_novos,omitempty"` // nomes dos tipos documentais que a IA reconheceu pela primeira vez neste lote
	Tokens       int64    `json:"tokens"`
	CustoCent    int64    `json:"custo_centavos"`
}

type typeInfo struct {
	Escopo      string
	Saude       bool
	Validade    *int
	Nome        string
	NaoRevisado bool // criado pela IA e ainda não confirmado pelo Master
}

func loadTypes(ctx context.Context, tx pgx.Tx) (map[string]typeInfo, error) {
	rows, err := tx.Query(ctx, `SELECT codigo, escopo, sensivel_saude, validade_padrao_dias, nome, (origem='IA' AND revisado_em IS NULL) FROM document_types`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]typeInfo{}
	for rows.Next() {
		var c string
		var t typeInfo
		if err := rows.Scan(&c, &t.Escopo, &t.Saude, &t.Validade, &t.Nome, &t.NaoRevisado); err != nil {
			return nil, err
		}
		out[c] = t
	}
	return out, rows.Err()
}

func str(m map[string]any, k string) string {
	if v, ok := m[k]; ok && v != nil {
		return strings.TrimSpace(fmt.Sprint(v))
	}
	return ""
}

func dateOrNil(s string) *string {
	if s == "" {
		return nil
	}
	for _, l := range []string{"2006-01-02", "02/01/2006"} {
		if t, err := time.Parse(l, s); err == nil {
			d := t.Format("2006-01-02")
			return &d
		}
	}
	return nil
}

// FindEmployee vincula pelo CPF (hash cego), matrícula ou nome por similaridade (≥ 0,85).
// how: CPF | MATRICULA | NOME (nome exige revisão) | "" (sem vínculo).
func (i *Ingestor) FindEmployee(ctx context.Context, tx pgx.Tx, tenantID, cpfRaw, matricula, nome string) (id *string, how string, err error) {
	if d := cpf.Clean(cpfRaw); len(d) == 11 {
		var e string
		if err = tx.QueryRow(ctx, `SELECT id::text FROM employees WHERE tenant_id=$1 AND cpf_hash=$2`, tenantID, i.KR.Blind(tenantID, d)).Scan(&e); err == nil {
			return &e, "CPF", nil
		} else if err != pgx.ErrNoRows {
			return nil, "", err
		}
		// Um CPF válido desconhecido não pode ser associado por nome ou matrícula a outro CPF.
		if cpf.Valid(d) {
			return nil, "", nil
		}
	}
	if matricula != "" {
		var e string
		if err = tx.QueryRow(ctx, `SELECT id::text FROM employees WHERE tenant_id=$1 AND matricula=$2`, tenantID, matricula).Scan(&e); err == nil {
			return &e, "MATRICULA", nil
		} else if err != pgx.ErrNoRows {
			return nil, "", err
		}
	}
	if len(nome) >= 5 {
		rows, qerr := tx.Query(ctx, `SELECT id::text, similarity(f_unaccent(lower(nome)), f_unaccent(lower($2))) s FROM employees
		  WHERE tenant_id=$1 AND f_unaccent(lower(nome)) % f_unaccent(lower($2)) ORDER BY s DESC LIMIT 2`, tenantID, nome)
		if qerr != nil {
			return nil, "", qerr
		}
		defer rows.Close()
		var ids []string
		var sc []float64
		for rows.Next() {
			var e string
			var s float64
			rows.Scan(&e, &s)
			ids, sc = append(ids, e), append(sc, s)
		}
		if len(ids) > 0 && sc[0] >= 0.85 && (len(ids) == 1 || sc[0]-sc[1] >= 0.1) {
			return &ids[0], "NOME", nil
		}
	}
	return nil, "", nil
}

func slug(s string) string {
	s = strings.ToUpper(strings.TrimSpace(s))
	r := strings.NewReplacer(" ", "_", "/", "-", ".", "", "Á", "A", "À", "A", "Ã", "A", "Â", "A", "É", "E", "Ê", "E", "Í", "I", "Ó", "O", "Õ", "O", "Ô", "O", "Ú", "U", "Ç", "C")
	return r.Replace(s)
}

// Ingest converte os documentos do IA Core em registros, aplicando vínculo e regras de revisão.
func (i *Ingestor) Ingest(ctx context.Context, tx pgx.Tx, tenantID, batchID string, unitID *string, limiar float64, docs []iacore.Documento, h Hints) (*Summary, []string, error) {
	types, err := loadTypes(ctx, tx)
	if err != nil {
		return nil, nil, err
	}
	var tenantNome string
	tx.QueryRow(ctx, `SELECT coalesce(nome_fantasia, razao_social) FROM tenants WHERE id=$1`, tenantID).Scan(&tenantNome)
	sum := &Summary{}
	affected := map[string]bool{}
	var autoPre bool
	tx.QueryRow(ctx, `SELECT pre_cadastro_automatico FROM tenants WHERE id=$1`, tenantID).Scan(&autoPre)
	var limiarDup float64 = 0.85 // similaridade do texto (OCR) acima da qual é o mesmo documento; ajustável pela empresa (0,70 a 1,00)
	_ = tx.QueryRow(ctx, `SELECT similaridade_duplicata::float8 FROM tenants WHERE id=$1`, tenantID).Scan(&limiarDup)
	novosFornecedores := map[string]bool{}
	var firstDoc string
	for n, d := range docs {
		tipo := d.Tipo
		if _, known := types[tipo]; !known && d.TipoNovo != nil && d.TipoNovo.Codigo == tipo {
			if created, nome := registrarTipoDescoberto(ctx, tx, d.TipoNovo); created {
				if t, err := loadTypes(ctx, tx); err == nil {
					types = t
				}
				sum.TiposNovos = append(sum.TiposNovos, nome)
			}
		}
		ti, ok := types[tipo]
		if !ok {
			tipo, ti = "OUTRO", types["OUTRO"]
		}
		if tipo == "OUTRO" && h.Tipo != nil {
			if t2, exists := types[*h.Tipo]; exists {
				tipo, ti = *h.Tipo, t2
			}
		}
		campos := d.Campos
		if campos == nil {
			campos = map[string]any{}
		}
		cpfDigits := cpf.Clean(str(campos, "cpf"))
		nome := str(campos, "nome")
		motivos := append([]string{}, d.MotivosRevisao...)
		alertas := d.Alertas
		// fornecedor/terceirizada: o CNPJ lido no documento agrupa tudo da mesma empresa
		supID, supNovo, err := i.ResolveSupplier(ctx, tx, tenantID, campos, autoPre, "PRE_CADASTRO")
		if err != nil {
			return nil, nil, err
		}
		// o mesmo empregador aparece com grafias diferentes ("Soluções Ltda", "SOLUCOES LTDA", nome de fantasia): sem CNPJ legível,
		// junta pelo nome a um fornecedor já cadastrado ou à própria empresa, para ficarem na mesma pasta e no mesmo grupo
		if lido := str(campos, "empresa_nome"); supID == nil && lido != "" {
			if supplierCNPJ(campos) == "" {
				if sid, razao, e := supplierByName(ctx, tx, tenantID, lido); e != nil {
					return nil, nil, e
				} else if sid != nil {
					supID, campos["empresa_nome_lida"], campos["empresa_nome"] = sid, lido, razao
				}
			}
			if supID == nil {
				canonico, e := ownCompanyName(ctx, tx, tenantID, lido)
				if e != nil {
					return nil, nil, e
				}
				if canonico != lido {
					campos["empresa_nome_lida"], campos["empresa_nome"] = lido, canonico
				}
			}
		}
		if supNovo && supID != nil && !novosFornecedores[*supID] {
			novosFornecedores[*supID] = true
			sum.Fornecedores++
			alertas = append(alertas, iacore.Alerta{Severidade: "info", Codigo: "FORNECEDOR_PRE_CADASTRO", Mensagem: "Fornecedor/terceirizada pré-cadastrado a partir do CNPJ deste documento: complete o cadastro"})
		}
		var empID *string
		how := ""
		if ti.Escopo == "FUNCIONARIO" {
			empID, how, err = i.FindEmployee(ctx, tx, tenantID, cpfDigits, str(campos, "matricula"), nome)
			if err != nil {
				return nil, nil, err
			}
			if cpfDigits != "" && !cpf.Valid(cpfDigits) {
				alertas = append(alertas, iacore.Alerta{Severidade: "aviso", Codigo: "CPF_INVALIDO", Mensagem: "CPF lido no documento tem dígito verificador inválido"})
				motivos = append(motivos, "CPF_INVALIDO")
			}
			// dados divergentes: o nome lido no documento não confere com o cadastro (ex.: CNH × RG de pessoas/ordens diferentes)
			if empID != nil && nome != "" {
				var cad string
				if tx.QueryRow(ctx, `SELECT nome FROM employees WHERE id=$1`, *empID).Scan(&cad) == nil {
					if bad, why := NameMismatch(nome, cad); bad {
						alertas = append(alertas, iacore.Alerta{Severidade: "aviso", Codigo: "DADOS_DIVERGENTES", Mensagem: fmt.Sprintf("Nome no documento (%q) difere do cadastro (%q): %s", nome, cad, why)})
						motivos = append(motivos, "DADOS_DIVERGENTES")
					}
				}
			}
		}
		if ti.Escopo == "FUNCIONARIO" && empID == nil && h.EmployeeID != nil { // o usuário disse de quem é o documento (lançamento de documento legível)
			var hintedHash string
			if err := tx.QueryRow(ctx, `SELECT cpf_hash FROM employees WHERE tenant_id=$1 AND id=$2`, tenantID, *h.EmployeeID).Scan(&hintedHash); err != nil {
				return nil, nil, err
			}
			if cpf.Valid(cpfDigits) && hintedHash != i.KR.Blind(tenantID, cpfDigits) {
				alertas = append(alertas, iacore.Alerta{Severidade: "erro", Codigo: "CPF_DIVERGENTE", Mensagem: "CPF da nova cópia difere do funcionário indicado: confirme o titular antes de vincular"})
				motivos = append(motivos, "CPF_DIVERGENTE")
			} else {
				empID, how = h.EmployeeID, "DICA"
			}
		}
		if how == "DICA" && nome != "" {
			var cad string
			if err := tx.QueryRow(ctx, `SELECT nome FROM employees WHERE tenant_id=$1 AND id=$2`, tenantID, *empID).Scan(&cad); err != nil {
				return nil, nil, err
			}
			if bad, why := NameMismatch(nome, cad); bad {
				alertas = append(alertas, iacore.Alerta{Severidade: "aviso", Codigo: "DADOS_DIVERGENTES", Mensagem: fmt.Sprintf("Nome na nova cópia (%q) difere do cadastro (%q): %s", nome, cad, why)})
				motivos = append(motivos, "DADOS_DIVERGENTES")
			}
		}
		// empregador do funcionário: o primeiro documento com CNPJ de fornecedor define; um documento de OUTRA empresa é divergência
		if empID != nil && supID != nil && ti.Escopo == "FUNCIONARIO" {
			var empSup *string
			if tx.QueryRow(ctx, `SELECT supplier_id::text FROM employees WHERE id=$1`, *empID).Scan(&empSup) == nil {
				switch {
				case empSup == nil:
					if _, err := tx.Exec(ctx, `UPDATE employees SET supplier_id=$2 WHERE id=$1`, *empID, *supID); err != nil {
						return nil, nil, err
					}
				case *empSup != *supID:
					alertas = append(alertas, iacore.Alerta{Severidade: "aviso", Codigo: "EMPREGADOR_DIVERGENTE", Mensagem: "A empresa (CNPJ) deste documento difere do empregador cadastrado para o funcionário"})
					motivos = append(motivos, "EMPREGADOR_DIVERGENTE")
				}
			}
		}
		// pré-cadastro automático: CPF válido + nome lido, sem vínculo, página legível
		if tipo != "OUTRO" && ti.Escopo == "FUNCIONARIO" && empID == nil && autoPre && cpf.Valid(cpfDigits) && nome != "" && !d.PaginaIlegivel && !d.MultiplosDocs {
			blocked, limitErr := i.limitReached(ctx, tx, tenantID)
			if limitErr != nil {
				return nil, nil, limitErr
			}
			if blocked {
				motivos = append(motivos, "LIMITE_FUNCIONARIOS")
				alertas = append(alertas, iacore.Alerta{Severidade: "aviso", Codigo: "LIMITE_FUNCIONARIOS", Mensagem: "Limite de funcionários do plano atingido; pré-cadastro não realizado"})
			} else {
				newID, err := i.CreateEmployee(ctx, tx, tenantID, NewEmployee{Nome: nome, CPF: cpfDigits, Matricula: str(campos, "matricula"), UnitID: unitID, Origem: "PRE_CADASTRO", Pre: true, SupplierID: supID})
				if err == nil {
					empID, how = &newID, "PRE_CADASTRO"
					sum.PreCadastros++
					alertas = append(alertas, iacore.Alerta{Severidade: "info", Codigo: "PRE_CADASTRO", Mensagem: "Funcionário pré-cadastrado automaticamente a partir deste documento: complete o cadastro."})
				} else {
					return nil, nil, fmt.Errorf("pré-cadastrar funcionário: %w", err)
				}
			}
		}
		if d.Confianca < limiar {
			motivos = append(motivos, "BAIXA_CONFIANCA")
		}
		if d.PaginaIlegivel {
			motivos = append(motivos, "PAGINA_ILEGIVEL")
		}
		if d.MultiplosDocs {
			motivos = append(motivos, "MULTIPLOS_DOCUMENTOS")
		}
		if tipo == "OUTRO" {
			motivos = append(motivos, "TIPO_OUTRO")
		} else if ti.NaoRevisado {
			alertas = append(alertas, iacore.Alerta{Severidade: "info", Codigo: "TIPO_IA", Mensagem: fmt.Sprintf("Tipo «%s» reconhecido pela IA a partir da leitura (fora do catálogo curado). O Master pode confirmar ou renomear.", ti.Nome)})
		}
		if ti.Escopo == "FUNCIONARIO" && empID == nil {
			motivos = append(motivos, "SEM_VINCULO")
			sum.SemVinculo++
		}
		if how == "NOME" {
			motivos = append(motivos, "VINCULO_POR_NOME")
		}
		for _, a := range alertas {
			if a.Severidade == "erro" {
				motivos = append(motivos, "ALERTA_ERRO")
				break
			}
		}
		comp, dataDoc, validade := str(campos, "competencia"), dateOrNil(str(campos, "data_documento")), dateOrNil(str(campos, "validade_ate"))
		// duplicidade: mesmo tipo + funcionário + competência de um documento já aprovado
		var dupOf *string
		if empID != nil && comp != "" {
			var x string
			if tx.QueryRow(ctx, `SELECT id::text FROM documents WHERE tenant_id=$1 AND employee_id=$2 AND document_type=$3 AND competencia=$4
			  AND status IN ('AUTO_APROVADO','REVISADO') ORDER BY criado_em DESC LIMIT 1`, tenantID, *empID, tipo, comp).Scan(&x) == nil {
				dupOf = &x
				motivos = append(motivos, "POSSIVEL_DUPLICATA")
				alertas = append(alertas, iacore.Alerta{Severidade: "aviso", Codigo: "POSSIVEL_DUPLICATA", Mensagem: "já existe documento aprovado do mesmo tipo e competência"})
			}
		}
		motivos = uniq(motivos)
		status := "AUTO_APROVADO"
		if len(motivos) > 0 {
			status = "AGUARDANDO_REVISAO"
			sum.Revisao++
		} else {
			sum.AutoAprovado++
		}
		// o CPF não fica em claro no jsonb: guardamos só a versão mascarada (hash cego no índice próprio)
		var cpfHash *string
		if len(cpfDigits) == 11 {
			h := i.KR.Blind(tenantID, cpfDigits)
			cpfHash = &h
			campos["cpf"] = cpf.Mask(cpfDigits)
		}
		// empresa: a lida no documento (razão social + CNPJ); se não houver, a empresa-cliente do tenant
		empFolder := slug(tenantNome)
		if en := str(campos, "empresa_nome"); en != "" {
			empFolder = slug(en)
			if c := cnpj.Clean(str(campos, "empresa_cnpj")); len(c) == 14 {
				empFolder += "_" + c
			}
		}
		refName := comp
		if refName == "" && dataDoc != nil {
			refName = *dataDoc
		}
		sufVal := ""
		if validade != nil {
			sufVal = "_VALIDO_" + *validade
		}
		pasta := empFolder + "/DOCUMENTOS_EMPRESA"
		fname := fmt.Sprintf("%02d_%s_%s%s.pdf", n+1, tipo, refName, sufVal)
		if nome != "" && ti.Escopo == "FUNCIONARIO" {
			suf := ""
			if len(cpfDigits) == 11 {
				suf = "_CPF_" + cpfDigits[:6] // só 6 dígitos: o CPF inteiro não deve aparecer em nome de arquivo/pasta
			}
			pasta = fmt.Sprintf("%s/%s%s", empFolder, slug(nome), suf)
			fname = fmt.Sprintf("%02d_%s_%s%s_%s%s.pdf", n+1, tipo, slug(nome), suf, refName, sufVal)
		}
		// duplicata de CONTEÚDO: o mesmo documento escaneado de outra forma (o hash da imagem não percebe). Só no fluxo normal: um
		// documento lançado como substituto/dica do usuário nunca é descartado por similaridade.
		var original *dupAchada
		if h.Substitui == nil && h.EmployeeID == nil && h.Tipo == nil {
			original, err = acharDuplicataDeConteudo(ctx, tx, tenantID, novoDoc{Tipo: tipo, Emp: empID, Sup: supID, CPFHash: cpfHash, Comp: comp,
				Data: deref(dataDoc), Validade: deref(validade), Texto: d.TextoAnonimizado, Confianca: d.Confianca}, limiarDup)
			if err != nil {
				return nil, nil, err
			}
		}
		// qual das cópias fica: a já revisada por uma pessoa; senão a de leitura mais confiável (empate: a que já estava)
		mantemNovo := original != nil && original.Status != "REVISADO" && d.Confianca > original.Confianca+0.02
		if original != nil && !mantemNovo {
			if status == "AGUARDANDO_REVISAO" {
				sum.Revisao--
			} else {
				sum.AutoAprovado--
			}
			if ti.Escopo == "FUNCIONARIO" && empID == nil {
				sum.SemVinculo--
			}
			status, motivos, dupOf = "REJEITADO", []string{"DUPLICATA_CONTEUDO"}, &original.ID
			alertas = append(alertas, iacore.Alerta{Severidade: "info", Codigo: "DUPLICATA_CONTEUDO", Mensagem: fmt.Sprintf("Mesmo conteúdo de outro documento já guardado (similaridade %.0f%%): descartado. Restaure se for um documento diferente.", original.Similaridade*100)})
		}
		cj, _ := json.Marshal(campos)
		aj, _ := json.Marshal(nz(alertas))
		mj, _ := json.Marshal(motivos)
		nj, _ := json.Marshal(nz(d.NaoConformidades))
		sj, _ := json.Marshal(nz(d.DadosSensiveis))
		fj, _ := json.Marshal(d.Finops)
		ckj, _ := json.Marshal(nz(d.Checklist))
		var id string
		// o texto lido (OCR) entra cifrado com a chave da empresa; texto_ocr em claro fica vazio
		sl, err := ocrseal.ForTx(ctx, tx, i.KR, tenantID)
		if err != nil {
			return nil, nil, fmt.Errorf("chave da empresa: %w", err)
		}
		textoCifrado, err := sl.Text(ocrseal.Texto, d.TextoOCR)
		if err != nil {
			return nil, nil, err
		}
		err = tx.QueryRow(ctx, `INSERT INTO documents (tenant_id, batch_id, employee_id, unit_id, document_type, titulo, competencia, data_documento, validade_ate,
		  paginas, confianca, status, campos, alertas, motivos_revisao, nao_conformidades, dados_sensiveis, finops, texto_ocr_cifrado, texto_anonimizado,
		  cpf_extraido_hash, nome_extraido, nome_arquivo, pasta_destino, possui_manuscrito, sensivel_saude, duplicata_de, checklist, supplier_id)
		  VALUES ($1,$2,$3,$4,$5,$6,nullif($7,''),$8::date,$9::date,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29) RETURNING id::text`,
			tenantID, batchID, empID, unitID, tipo, d.Titulo, comp, dataDoc, validade, intsToArr(d.Paginas), d.Confianca, status, cj, aj, mj, nj, sj, nullJSON(fj),
			textoCifrado, d.TextoAnonimizado, cpfHash, nome, fname, pasta, d.PossuiManuscrito, ti.Saude, dupOf, ckj, supID).Scan(&id)
		if err != nil {
			return nil, nil, fmt.Errorf("inserir documento: %w", err)
		}
		if firstDoc == "" {
			firstDoc = id
		}
		if status == "REJEITADO" { // cópia descartada: não conta como documento do lote, mas o custo de leitura foi real
			sum.Duplicados++
			if f := d.Finops; f != nil {
				if t, ok := f["tokens_consumidos"].(float64); ok {
					sum.Tokens += int64(t)
				}
				if c, ok := f["custo_estimado_brl"].(float64); ok {
					sum.CustoCent += int64(c * 100)
				}
			}
			continue
		}
		if mantemNovo { // a cópia nova é mais confiável: a que já estava guardada é que vira duplicata
			if _, err := tx.Exec(ctx, `UPDATE documents SET status='REJEITADO', motivos_revisao='["DUPLICATA_CONTEUDO"]', duplicata_de=$2, atualizado_em=now() WHERE id=$1`, original.ID, id); err != nil {
				return nil, nil, err
			}
			sum.Duplicados++
			if original.Batch == batchID { // estava neste mesmo lote: tira dos totais
				sum.Documentos--
				sum.Paginas -= original.Paginas
				if original.Status == "AGUARDANDO_REVISAO" {
					sum.Revisao--
				} else {
					sum.AutoAprovado--
				}
				if original.SemFuncionario && ti.Escopo == "FUNCIONARIO" {
					sum.SemVinculo--
				}
			}
		}
		for _, m := range motivos {
			if m == "PAGINA_ILEGIVEL" || m == "IMAGEM_BORRADA" || m == "TIPO_OUTRO" {
				sum.Ilegiveis++
				break
			}
		}
		if empID != nil {
			affected[*empID] = true
		}
		sum.Documentos++
		sum.Paginas += len(d.Paginas)
		if f := d.Finops; f != nil {
			if t, ok := f["tokens_consumidos"].(float64); ok {
				sum.Tokens += int64(t)
			}
			if c, ok := f["custo_estimado_brl"].(float64); ok {
				sum.CustoCent += int64(c * 100)
			}
		}
	}
	// documento legível lançado no lugar de um ilegível: o antigo sai de circulação e o novo guarda a ligação
	if h.Substitui != nil && firstDoc != "" {
		var oldEmp *string
		if tx.QueryRow(ctx, `SELECT employee_id::text FROM documents WHERE id=$1 AND tenant_id=$2 AND status<>'SUBSTITUIDO'`, *h.Substitui, tenantID).Scan(&oldEmp) == nil {
			var newEmp *string
			if err := tx.QueryRow(ctx, `SELECT employee_id::text FROM documents WHERE id=$1`, firstDoc).Scan(&newEmp); err != nil {
				return nil, nil, err
			}
			if oldEmp != nil && newEmp != nil && *oldEmp != *newEmp {
				var wasAuto bool
				if err := tx.QueryRow(ctx, `SELECT status='AUTO_APROVADO' FROM documents WHERE id=$1`, firstDoc).Scan(&wasAuto); err != nil {
					return nil, nil, err
				}
				if _, err := tx.Exec(ctx, `UPDATE documents SET status='AGUARDANDO_REVISAO',
				  motivos_revisao=motivos_revisao || '["CPF_DIVERGENTE"]'::jsonb,
				  alertas=alertas || '[{"severidade":"erro","codigo":"CPF_DIVERGENTE","mensagem":"A nova cópia pertence a outro funcionário; a anterior foi preservada."}]'::jsonb WHERE id=$1`, firstDoc); err != nil {
					return nil, nil, err
				}
				if wasAuto {
					sum.AutoAprovado--
					sum.Revisao++
				}
				return sum, mapKeys(affected), nil
			}
			if _, err := tx.Exec(ctx, `UPDATE documents SET substitui_id=$2, versao=(SELECT versao+1 FROM documents WHERE id=$2) WHERE id=$1`, firstDoc, *h.Substitui); err != nil {
				return nil, nil, err
			}
			var newStatus string
			if err := tx.QueryRow(ctx, `SELECT status FROM documents WHERE id=$1`, firstDoc).Scan(&newStatus); err != nil {
				return nil, nil, err
			}
			if newStatus == "AUTO_APROVADO" {
				if _, err := tx.Exec(ctx, `UPDATE documents SET status='SUBSTITUIDO', atualizado_em=now() WHERE id=$1`, *h.Substitui); err != nil {
					return nil, nil, err
				}
			}
			if oldEmp != nil {
				affected[*oldEmp] = true
			}
		}
	}
	var ids []string
	for k := range affected {
		ids = append(ids, k)
	}
	return sum, ids, nil
}

func mapKeys(m map[string]bool) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

func nz[T any](s []T) []T {
	if s == nil {
		return []T{}
	}
	return s
}
func nullJSON(b []byte) any {
	if string(b) == "null" {
		return nil
	}
	return b
}
func intsToArr(a []int) []int32 {
	o := make([]int32, len(a))
	for i, v := range a {
		o[i] = int32(v)
	}
	return o
}
func uniq(s []string) []string {
	seen := map[string]bool{}
	var o []string
	for _, x := range s {
		if !seen[x] {
			seen[x] = true
			o = append(o, x)
		}
	}
	return o
}

// MobilizationStatus resume a aptidão do documento: BLOQUEADO (qualquer FALHA ou rejeitado), EM ANÁLISE (revisão/alerta) ou APTO.
func MobilizationStatus(docStatus string, checklist []map[string]any) string {
	if docStatus == "REJEITADO" {
		return "BLOQUEADO PREVENTIVO (DOCUMENTO REJEITADO)"
	}
	alert := docStatus == "AGUARDANDO_REVISAO"
	for _, it := range checklist {
		switch fmt.Sprint(it["status"]) {
		case "FALHA":
			return "BLOQUEADO PREVENTIVO (NÃO CONFORMIDADE)"
		case "ALERTA", "REVISAO_HUMANA":
			alert = true
		}
	}
	if alert {
		return "EM ANÁLISE (AGUARDANDO REVISÃO)"
	}
	return "APTO PARA MOBILIZAÇÃO"
}

// limitReached informa se o plano já atingiu o máximo de funcionários ativos (o pré-cadastro então é pulado e o documento vai para "sem vínculo").
func (i *Ingestor) limitReached(ctx context.Context, tx pgx.Tx, tenantID string) (bool, error) {
	var max *int
	var n int
	if err := tx.QueryRow(ctx, `SELECT max_funcionarios FROM tenants WHERE id=$1`, tenantID).Scan(&max); err != nil {
		return true, err
	}
	if max == nil {
		return false, nil
	}
	if err := tx.QueryRow(ctx, `SELECT count(*) FROM employees WHERE tenant_id=$1 AND status<>'DESLIGADO'`, tenantID).Scan(&n); err != nil {
		return true, err
	}
	return n >= *max, nil
}

// maxTiposIA é o teto de tipos que a IA pode criar no catálogo global (evita inflar o catálogo com nomes soltos).
const maxTiposIA = 150

var reCodigoTipo = regexp.MustCompile(`^[A-Z][A-Z0-9_]{2,39}$`)

// TiposDescobertos devolve os tipos criados pela IA, para o IA Core reaprender as pistas locais (Camada 1) em cada lote.
func TiposDescobertos(ctx context.Context, tx pgx.Tx) []iacore.TipoNovo {
	rows, err := tx.Query(ctx, `SELECT codigo, nome, escopo, categoria, pistas FROM document_types WHERE origem='IA' ORDER BY criado_em LIMIT $1`, maxTiposIA)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var out []iacore.TipoNovo
	for rows.Next() {
		var t iacore.TipoNovo
		if rows.Scan(&t.Codigo, &t.Nome, &t.Escopo, &t.Categoria, &t.Pistas) == nil {
			out = append(out, t)
		}
	}
	return out
}

// validarTipoNovo saneia o tipo que a IA propôs, porque o catálogo é compartilhado entre as empresas: o nome vale só como NOME DE TIPO (sem
// número longo, e-mail, CPF/CNPJ), o código segue o padrão, e escopo/categoria ficam dentro dos valores conhecidos.
func validarTipoNovo(t *iacore.TipoNovo) (iacore.TipoNovo, bool) {
	nome := strings.TrimSpace(t.Nome)
	if !reCodigoTipo.MatchString(t.Codigo) || t.Codigo == "OUTRO" || len([]rune(nome)) < 4 || len([]rune(nome)) > 60 || reInstancia.MatchString(nome) {
		return iacore.TipoNovo{}, false
	}
	out := iacore.TipoNovo{Codigo: t.Codigo, Nome: nome, Escopo: "FUNCIONARIO", Categoria: "OUTROS", Pistas: []string{}}
	if t.Escopo == "EMPRESA" {
		out.Escopo, out.Categoria = "EMPRESA", "EMPRESA"
	}
	if out.Escopo == "FUNCIONARIO" {
		switch t.Categoria {
		case "ADMISSAO", "MENSAL", "SAUDE_SEGURANCA", "DISCIPLINAR", "DESLIGAMENTO":
			out.Categoria = t.Categoria
		}
	}
	for _, p := range t.Pistas {
		if p = strings.TrimSpace(p); len([]rune(p)) >= 8 && len([]rune(p)) <= 60 && len(out.Pistas) < 6 {
			out.Pistas = append(out.Pistas, p)
		}
	}
	return out, true
}

// registrarTipoDescoberto cria no catálogo global um tipo que a IA reconheceu (há um teto de tipos criados).
func registrarTipoDescoberto(ctx context.Context, tx pgx.Tx, in *iacore.TipoNovo) (criado bool, nome string) {
	t, ok := validarTipoNovo(in)
	if !ok {
		return false, ""
	}
	var n int
	if tx.QueryRow(ctx, `SELECT count(*) FROM document_types WHERE origem='IA'`).Scan(&n) != nil || n >= maxTiposIA {
		return false, ""
	}
	ct, err := tx.Exec(ctx, `INSERT INTO document_types (codigo, nome, categoria, sensivel_saude, escopo, validade_padrao_dias, retencao_padrao_dias, origem, pistas)
	  VALUES ($1,$2,$3,false,$4,NULL,1825,'IA',$5) ON CONFLICT (codigo) DO NOTHING`, t.Codigo, t.Nome, t.Categoria, t.Escopo, t.Pistas)
	return err == nil && ct.RowsAffected() > 0, t.Nome
}

// reInstancia reconhece o que NÃO é nome de tipo: número longo, e-mail, CPF ou CNPJ (a IA descreveu um documento em vez de um tipo).
var reInstancia = regexp.MustCompile(`\d{5,}|@|\d{3}\.\d{3}\.\d{3}|\d{2}\.\d{3}\.\d{3}/`)
