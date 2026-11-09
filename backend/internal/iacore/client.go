// Package iacore é o cliente HTTP do IA Core (Python/FastAPI + Gemini) e define o contrato dos callbacks.
package iacore

import (
	"bytes"
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"time"
)

type Client struct {
	BaseURL string
	APIKey  string
	HTTP    *http.Client
}

func New(base, key string) *Client {
	return &Client{BaseURL: base, APIKey: key, HTTP: &http.Client{Timeout: 10 * time.Minute}}
}

type PageRef struct {
	Numero        int    `json:"numero"`
	ImageURL      string `json:"image_url"`
	TextoEmbutido string `json:"texto_embutido,omitempty"`
}

type JobRequest struct {
	BatchID          string                     `json:"batch_id"`
	Versao           int                        `json:"versao"`
	CallbackURL      string                     `json:"callback_url"`
	TipoLote         string                     `json:"tipo_lote"`
	Paginas          []PageRef                  `json:"paginas"`
	AnalisesPrevias  map[string]json.RawMessage `json:"analises_previas,omitempty"`
	TiposExtras      []TipoNovo                 `json:"tipos_extras,omitempty"` // tipos que a IA já descobriu (catálogo do backend): o IA Core reaprende as pistas
	SimularFalhaNaPg int                        `json:"simular_falha_na_pagina,omitempty"`
	LimiarConfianca  float64                    `json:"limiar_confianca"`
}

// Callback é o corpo enviado pelo IA Core para /internal/ia/callback.
type Callback struct {
	Evento     string          `json:"evento"` // pagina | concluido | falhou
	BatchID    string          `json:"batch_id"`
	Versao     int             `json:"versao"`
	Numero     int             `json:"numero,omitempty"`
	Status     string          `json:"status,omitempty"` // OK | FALHOU
	Analise    json.RawMessage `json:"analise,omitempty"`
	Erro       string          `json:"erro,omitempty"`
	PagsFalhas []int           `json:"paginas_falhas,omitempty"`
	Documentos []Documento     `json:"documentos,omitempty"`
}

type Alerta struct {
	Severidade string `json:"severidade"` // erro | aviso | info
	Codigo     string `json:"codigo"`
	Mensagem   string `json:"mensagem"`
}

type NaoConformidade struct {
	Codigo    string `json:"codigo"`
	Descricao string `json:"descricao"`
}

// TipoNovo é um tipo documental que a IA descobriu ao ler um documento que o catálogo curado não cobria.
type TipoNovo struct {
	Codigo    string   `json:"codigo"`
	Nome      string   `json:"nome"`
	Escopo    string   `json:"escopo"`
	Categoria string   `json:"categoria"`
	Pistas    []string `json:"pistas"`
}

type Documento struct {
	Tipo             string            `json:"tipo"`
	TipoNovo         *TipoNovo         `json:"tipo_novo,omitempty"`
	Titulo           string            `json:"titulo"`
	Paginas          []int             `json:"paginas"`
	Confianca        float64           `json:"confianca"`
	Campos           map[string]any    `json:"campos"`
	Alertas          []Alerta          `json:"alertas"`
	MotivosRevisao   []string          `json:"motivos_revisao"`
	NaoConformidades []NaoConformidade `json:"nao_conformidades"`
	DadosSensiveis   []map[string]any  `json:"dados_sensiveis"`
	TextoOCR         string            `json:"texto_ocr"`
	TextoAnonimizado string            `json:"texto_anonimizado"`
	PossuiManuscrito bool              `json:"possui_manuscrito"`
	PaginaIlegivel   bool              `json:"pagina_ilegivel"`
	MultiplosDocs    bool              `json:"multiplos_documentos_na_imagem"`
	Finops           map[string]any    `json:"finops"`
	Checklist        []map[string]any  `json:"checklist"`
}

func (c *Client) do(ctx context.Context, method, path string, body any, out io.Writer) (*http.Response, error) {
	var rd io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		rd = bytes.NewReader(b)
	}
	req, _ := http.NewRequestWithContext(ctx, method, c.BaseURL+path, rd)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-IACore-Key", c.APIKey)
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return resp, fmt.Errorf("ia-core %s %s: %d %s", method, path, resp.StatusCode, string(b))
	}
	if out != nil {
		_, err = io.Copy(out, resp.Body)
	}
	return resp, err
}

// Slice pede ao IA Core para fatiar o arquivo (URL assinada) e grava o ZIP (manifest + páginas + miniaturas) em dest.
func (c *Client) Slice(ctx context.Context, fileURL, filename, dest string) error {
	f, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = c.do(ctx, "POST", "/slice", map[string]any{"arquivo_url": fileURL, "filename": filename}, f)
	return err
}

func (c *Client) StartJob(ctx context.Context, req JobRequest, retry bool) error {
	path := "/jobs"
	if retry {
		path = "/retry"
	}
	_, err := c.do(ctx, "POST", path, req, io.Discard)
	return err
}

type RenderPage struct {
	ImageURL string          `json:"image_url"`
	Texto    string          `json:"texto,omitempty"`
	Palavras json.RawMessage `json:"palavras,omitempty"` // [x0,y0,x1,y1,texto] relativas (camada de texto posicionada)
	Caixas   json.RawMessage `json:"caixas,omitempty"`   // [x0,y0,x1,y1,rótulo] relativas (dados pessoais a tarjar)
	// TextoNativo: a página tem camada de texto no PDF (palavras exatas); sem ela, a cópia anonimizada depende de OCR.
	TextoNativo bool `json:"texto_nativo,omitempty"`
}

// Render devolve o PDF: modo original | pesquisavel | anonimizado.
// termos são nomes já conhecidos (ex.: do funcionário) que a cópia anonimizada tarja onde aparecerem.
func (c *Client) Render(ctx context.Context, modo, titulo string, pages []RenderPage, termos []string, out io.Writer) error {
	_, err := c.do(ctx, "POST", "/render", map[string]any{"modo": modo, "titulo": titulo, "paginas": pages, "termos": termos}, out)
	return err
}

// Motor devolve a impressão digital do motor de análise (provedor, modelos, regras e código). A Camada 0 só reaproveita
// análises feitas por esse mesmo motor.
func (c *Client) Motor(ctx context.Context) (string, error) {
	var b bytes.Buffer
	if _, err := c.do(ctx, "GET", "/health", nil, &b); err != nil {
		return "", err
	}
	var out struct {
		Motor string `json:"motor"`
	}
	if err := json.Unmarshal(b.Bytes(), &out); err != nil || out.Motor == "" {
		return "", fmt.Errorf("IA Core não informou o motor de análise")
	}
	return out.Motor, nil
}

// Anonymize devolve o texto sem dados pessoais (mesma regra usada na análise dos documentos).
func (c *Client) Anonymize(ctx context.Context, texto string) (string, error) {
	var b bytes.Buffer
	if _, err := c.do(ctx, "POST", "/anonimizar", map[string]any{"texto": texto}, &b); err != nil {
		return "", err
	}
	var out struct {
		Texto string `json:"texto_anonimizado"`
	}
	if err := json.Unmarshal(b.Bytes(), &out); err != nil {
		return "", err
	}
	return out.Texto, nil
}

// Schema devolve o JSON Schema (Pydantic) dos campos de um tipo documental.
func (c *Client) Schema(ctx context.Context, tipo string) (json.RawMessage, error) {
	var b bytes.Buffer
	if _, err := c.do(ctx, "GET", "/schemas/"+tipo, nil, &b); err != nil {
		return nil, err
	}
	return b.Bytes(), nil
}

// Quality executa o benchmark com lotes fictícios (tela "Qualidade da IA").
func (c *Client) Quality(ctx context.Context) (json.RawMessage, error) {
	var b bytes.Buffer
	if _, err := c.do(ctx, "POST", "/qualidade", map[string]any{}, &b); err != nil {
		return nil, err
	}
	return b.Bytes(), nil
}

// Sign assina o corpo do callback: HMAC-SHA256(secret, timestamp + "." + corpo).
func Sign(secret, ts string, body []byte) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte(ts + "."))
	m.Write(body)
	return "sha256=" + hex.EncodeToString(m.Sum(nil))
}

// VerifySignature confere assinatura e janela de 10 minutos (anti-replay).
func VerifySignature(secret, ts, sig string, body []byte) bool {
	t, err := strconv.ParseInt(ts, 10, 64)
	if err != nil || abs(time.Now().Unix()-t) > 600 {
		return false
	}
	return hmac.Equal([]byte(Sign(secret, ts, body)), []byte(sig))
}

func abs(x int64) int64 {
	if x < 0 {
		return -x
	}
	return x
}
