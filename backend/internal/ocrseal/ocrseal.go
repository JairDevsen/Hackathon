// Package ocrseal cifra, com a chave de dados (DEK) da empresa, o conteúdo lido dos documentos por OCR.
//
// O texto lido contém tudo que está nas páginas (CPF inteiro, nomes, endereços, saúde). Ele não pode ficar em claro no
// banco: um dump, um backup ou uma leitura indevida expõe os documentos mesmo com os arquivos cifrados. Aqui o texto
// completo, as palavras com posição e a análise de cada página são gravados como AES-GCM; o que continua em claro são
// dados estruturados já mascarados (campos com CPF ***.456.789-**, texto anonimizado) usados em filtros e na busca.
package ocrseal

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"

	"github.com/jackc/pgx/v5"

	"github.com/agreser-innovations/citadel-ia/backend/pkg/crypto"
)

// Finalidades (entram no AAD: um texto cifrado para um uso não abre em outro).
const (
	Texto   = "texto"    // texto completo do documento
	Palavra = "palavras" // palavras com posição de uma página
	Nativo  = "nativo"   // texto embutido no PDF
	Analise = "analise"  // texto e campos da análise de uma página
)

// Sealer cifra e decifra para UMA empresa.
type Sealer struct {
	dek    []byte
	tenant string
}

func New(dek []byte, tenantID string) *Sealer { return &Sealer{dek: dek, tenant: tenantID} }

// ForTx abre a DEK da empresa dentro de uma transação já aberta para ela.
func ForTx(ctx context.Context, tx pgx.Tx, kr *crypto.Keyring, tenantID string) (*Sealer, error) {
	var wrapped []byte
	if err := tx.QueryRow(ctx, `SELECT dek_wrapped FROM tenants WHERE id=$1`, tenantID).Scan(&wrapped); err != nil {
		return nil, err
	}
	dek, err := kr.DEK(tenantID, wrapped)
	if err != nil {
		return nil, err
	}
	return New(dek, tenantID), nil
}

func (s *Sealer) aad(finalidade string) []byte { return []byte("ocr|" + finalidade + "|" + s.tenant) }

// Bytes cifra; vazio continua vazio (nada a proteger).
func (s *Sealer) Bytes(finalidade string, plain []byte) ([]byte, error) {
	if len(plain) == 0 {
		return nil, nil
	}
	return crypto.Seal(s.dek, plain, s.aad(finalidade))
}

// Text cifra um texto.
func (s *Sealer) Text(finalidade, plain string) ([]byte, error) {
	return s.Bytes(finalidade, []byte(plain))
}

// OpenText decifra. Entrada vazia devolve vazio.
func (s *Sealer) OpenText(finalidade string, sealed []byte) (string, error) {
	if len(sealed) == 0 {
		return "", nil
	}
	b, err := crypto.Open(s.dek, sealed, s.aad(finalidade))
	return string(b), err
}

// PlainOrOpen devolve o texto: decifrado se houver cifra; senão, o valor antigo em claro (linhas anteriores à criptografia).
func (s *Sealer) PlainOrOpen(finalidade string, sealed []byte, legacy string) (string, error) {
	if len(sealed) > 0 {
		return s.OpenText(finalidade, sealed)
	}
	return legacy, nil
}

// campos da análise de uma página que carregam conteúdo do documento
var sensiveis = []string{"texto_ocr", "campos"}

const chaveEnc = "enc"

// ProtectAnalise tira do JSON da análise o texto lido e os campos extraídos e os guarda cifrados em "enc". O resto
// (tipo, confiança, camada, tokens...) segue em claro e continua consultável em SQL.
func (s *Sealer) ProtectAnalise(raw []byte) ([]byte, error) {
	if len(raw) == 0 {
		return raw, nil
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil, err
	}
	if _, jaProtegida := m[chaveEnc]; jaProtegida {
		return raw, nil
	}
	conteudo := map[string]json.RawMessage{}
	for _, k := range sensiveis {
		if v, ok := m[k]; ok {
			conteudo[k] = v
			delete(m, k)
		}
	}
	if len(conteudo) == 0 {
		return raw, nil
	}
	j, _ := json.Marshal(conteudo)
	sealed, err := s.Bytes(Analise, j)
	if err != nil {
		return nil, err
	}
	m[chaveEnc], _ = json.Marshal(base64.StdEncoding.EncodeToString(sealed))
	return json.Marshal(m)
}

// RevealAnalise é o inverso: devolve o JSON completo. Análises antigas (sem "enc") passam como estão.
func (s *Sealer) RevealAnalise(raw []byte) ([]byte, error) {
	if len(raw) == 0 {
		return raw, nil
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil, err
	}
	enc, ok := m[chaveEnc]
	if !ok {
		return raw, nil
	}
	var b64 string
	if err := json.Unmarshal(enc, &b64); err != nil {
		return nil, err
	}
	sealed, err := base64.StdEncoding.DecodeString(b64)
	if err != nil {
		return nil, err
	}
	plain, err := crypto.Open(s.dek, sealed, s.aad(Analise))
	if err != nil {
		return nil, err
	}
	var conteudo map[string]json.RawMessage
	if err := json.Unmarshal(plain, &conteudo); err != nil {
		return nil, err
	}
	delete(m, chaveEnc)
	for k, v := range conteudo {
		m[k] = v
	}
	return json.Marshal(m)
}

// AnaliseTexto devolve só o texto lido de uma análise (protegida ou antiga).
func (s *Sealer) AnaliseTexto(raw []byte) (string, error) {
	full, err := s.RevealAnalise(raw)
	if err != nil || len(full) == 0 {
		return "", err
	}
	var a struct {
		Texto string `json:"texto_ocr"`
	}
	if err := json.Unmarshal(full, &a); err != nil {
		return "", errors.New("análise inválida")
	}
	return a.Texto, nil
}
