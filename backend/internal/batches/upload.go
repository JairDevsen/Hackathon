package batches

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/agreser-innovations/citadel-ia/backend/internal/audit"
	"github.com/agreser-innovations/citadel-ia/backend/pkg/problem"
	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
)

const ChunkSize = 8 << 20

var allowedExt = map[string]bool{".pdf": true, ".tif": true, ".tiff": true, ".jpg": true, ".jpeg": true, ".png": true, ".heic": true, ".zip": true}

type UploadMeta struct {
	Tenant   string `json:"tenant"`
	User     string `json:"user"`
	Filename string `json:"filename"`
	UnitID   string `json:"unit_id"`
	TipoLote string `json:"tipo_lote"`
	Size     int64  `json:"size"`
	FailAt   int    `json:"fail_at"`
	IP       string `json:"ip"`
	// lançamento de documento legível: de quem é, que tipo é e qual documento ilegível ele substitui
	DicaFuncionarioID, DicaTipo, SubstituiDocumentoID string
}

func (s *Service) stagingPath(m *UploadMeta, id string) string {
	return filepath.Join(s.Cfg.UploadStagingDir, m.Tenant, id+".part")
}

func (s *Service) getMeta(ctx context.Context, id string) (*UploadMeta, error) {
	b, err := s.Redis.Get(ctx, "upl:"+id).Bytes()
	if err != nil {
		return nil, problem.NotFound("upload não encontrado ou expirado")
	}
	var m UploadMeta
	json.Unmarshal(b, &m)
	return &m, nil
}

// CheckQuota bloqueia novos uploads quando a cota de armazenamento estoura (a leitura continua liberada).
func (s *Service) CheckQuota(ctx context.Context, tenantID string, add int64) error {
	var used, quota int64
	var st string
	err := s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT bytes_usados, quota_bytes, status FROM tenants WHERE id=$1`, tenantID).Scan(&used, &quota, &st)
	})
	if err != nil {
		return err
	}
	if st != "ATIVO" {
		return problem.Forbidden("empresa suspensa: uploads bloqueados")
	}
	if used+add > quota {
		return problem.New(403, "cota-excedida", fmt.Sprintf("cota de armazenamento excedida (%d de %d bytes). Novos uploads estão bloqueados; solicite upgrade de plano", used, quota))
	}
	return nil
}

func validName(name string) (string, error) {
	base := filepath.Base(strings.ReplaceAll(name, "\\", "/"))
	if !allowedExt[strings.ToLower(filepath.Ext(base))] {
		return "", problem.BadRequest("tipo de arquivo não suportado (use PDF, TIFF, JPG, PNG, HEIC ou ZIP de imagens)")
	}
	return base, nil
}

func (s *Service) InitUpload(ctx context.Context, m UploadMeta) (string, error) {
	name, err := validName(m.Filename)
	if err != nil {
		return "", err
	}
	m.Filename = name
	if m.Size <= 0 || m.Size > s.Cfg.MaxUploadBytes {
		return "", problem.New(413, "arquivo-grande", fmt.Sprintf("o arquivo deve ter entre 1 byte e %d MB", s.Cfg.MaxUploadBytes>>20))
	}
	if err := s.CheckQuota(ctx, m.Tenant, m.Size); err != nil {
		return "", err
	}
	if m.TipoLote == "" {
		m.TipoLote = "MISTO"
	}
	id := uuid.NewString()
	if err := os.MkdirAll(filepath.Dir(s.stagingPath(&m, id)), 0o750); err != nil {
		return "", err
	}
	b, _ := json.Marshal(m)
	return id, s.Redis.Set(ctx, "upl:"+id, b, 48*time.Hour).Err()
}

func (s *Service) Offset(ctx context.Context, tenantID, id string) (int64, *UploadMeta, error) {
	m, err := s.getMeta(ctx, id)
	if err != nil || m.Tenant != tenantID {
		return 0, nil, problem.NotFound("upload não encontrado")
	}
	st, err := os.Stat(s.stagingPath(m, id))
	if err != nil {
		return 0, m, nil
	}
	return st.Size(), m, nil
}

// AppendChunk acrescenta a parte no offset esperado (retomável: o cliente consulta o offset e continua).
func (s *Service) AppendChunk(ctx context.Context, tenantID, id string, offset int64, r io.Reader) (int64, error) {
	cur, m, err := s.Offset(ctx, tenantID, id)
	if err != nil {
		return 0, err
	}
	if offset != cur {
		return cur, problem.Conflict(fmt.Sprintf("offset esperado %d", cur))
	}
	f, err := os.OpenFile(s.stagingPath(m, id), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o640)
	if err != nil {
		return 0, err
	}
	defer f.Close()
	n, err := io.Copy(f, io.LimitReader(r, m.Size-cur+1))
	if cur+n > m.Size {
		return cur, problem.BadRequest("dados além do tamanho declarado")
	}
	return cur + n, err
}

func sniff(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	h := make([]byte, 12)
	f.Read(h)
	ok := strings.HasPrefix(string(h), "%PDF") || strings.HasPrefix(string(h), "II*\x00") || strings.HasPrefix(string(h), "MM\x00*") ||
		(h[0] == 0xFF && h[1] == 0xD8) || strings.HasPrefix(string(h), "\x89PNG") || strings.HasPrefix(string(h), "PK") || string(h[4:8]) == "ftyp"
	if !ok {
		return problem.BadRequest("o conteúdo do arquivo não corresponde a um formato suportado")
	}
	return nil
}

type Created struct {
	ID        string `json:"id"`
	Status    string `json:"status"`
	Duplicate bool   `json:"duplicado,omitempty"`
}

// Complete valida (tamanho, formato, SHA-256, duplicidade, antivírus), grava cifrado e enfileira o processamento.
func (s *Service) Complete(ctx context.Context, tenantID, userID, id string) (*Created, error) {
	if b, err := s.Redis.Get(ctx, "upl:done:"+id).Result(); err == nil {
		return &Created{ID: b, Status: "RECEBIDO"}, nil // idempotente
	}
	cur, m, err := s.Offset(ctx, tenantID, id)
	if err != nil {
		return nil, err
	}
	if cur != m.Size {
		return nil, problem.BadRequest(fmt.Sprintf("upload incompleto: %d de %d bytes", cur, m.Size))
	}
	path := s.stagingPath(m, id)
	defer os.Remove(path)
	c, err := s.finalize(ctx, tenantID, userID, m, path)
	if err == nil {
		s.Redis.Set(ctx, "upl:done:"+id, c.ID, 24*time.Hour)
		s.Redis.Del(ctx, "upl:"+id)
	}
	return c, err
}

// FinalizeFile cobre o envio simples (multipart): o arquivo já está em disco temporário.
func (s *Service) FinalizeFile(ctx context.Context, tenantID, userID string, m UploadMeta, path string) (*Created, error) {
	name, err := validName(m.Filename)
	if err != nil {
		return nil, err
	}
	m.Filename = name
	if m.TipoLote == "" {
		m.TipoLote = "MISTO"
	}
	st, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	m.Size = st.Size()
	if err := s.CheckQuota(ctx, tenantID, m.Size); err != nil {
		return nil, err
	}
	return s.finalize(ctx, tenantID, userID, &m, path)
}

func (s *Service) finalize(ctx context.Context, tenantID, userID string, m *UploadMeta, path string) (*Created, error) {
	if err := sniff(path); err != nil {
		return nil, err
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	h := sha256.New()
	io.Copy(h, f)
	f.Close()
	sha := hex.EncodeToString(h.Sum(nil))
	var dupID string
	s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		return tx.QueryRow(ctx, `SELECT id::text FROM batches WHERE tenant_id=$1 AND sha256=$2 AND status<>'FALHOU'`, tenantID, sha).Scan(&dupID)
	})
	if dupID != "" {
		p := problem.Conflict("este arquivo já foi enviado (SHA-256 idêntico)")
		p.Errors = map[string]any{"batch_id": dupID}
		return nil, p
	}
	if err := ScanClamAV(s.Cfg.ClamAVAddr, path); err != nil {
		return nil, problem.New(422, "arquivo-rejeitado", err.Error())
	}
	batchID := uuid.NewString()
	key := fmt.Sprintf("%s/%s/original/%s", tenantID, batchID, m.Filename)
	rf, _ := os.Open(path)
	defer rf.Close()
	if _, err := s.Vault.Put(ctx, tenantID, key, rf); err != nil {
		return nil, fmt.Errorf("gravar original: %w", err)
	}
	var unit any
	if m.UnitID != "" {
		unit = m.UnitID
	}
	err = s.DB.Tenant(ctx, tenantID, func(tx pgx.Tx) error {
		if m.SubstituiDocumentoID != "" {
			var oldEmp *string
			var oldType string
			if err := tx.QueryRow(ctx, `SELECT employee_id::text, document_type FROM documents WHERE tenant_id=$1 AND id=$2 AND status<>'SUBSTITUIDO'`, tenantID, m.SubstituiDocumentoID).Scan(&oldEmp, &oldType); err != nil {
				return problem.BadRequest("documento a substituir não encontrado nesta empresa")
			}
			if m.DicaFuncionarioID == "" && oldEmp != nil {
				m.DicaFuncionarioID = *oldEmp
			}
			if m.DicaTipo == "" && oldType != "OUTRO" {
				m.DicaTipo = oldType
			}
		}
		if m.DicaFuncionarioID != "" {
			var exists bool
			if err := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM employees WHERE tenant_id=$1 AND id=$2)`, tenantID, m.DicaFuncionarioID).Scan(&exists); err != nil || !exists {
				return problem.BadRequest("funcionário indicado não pertence à empresa")
			}
		}
		if m.DicaTipo != "" {
			var exists bool
			if err := tx.QueryRow(ctx, `SELECT EXISTS(SELECT 1 FROM document_types WHERE codigo=$1)`, m.DicaTipo).Scan(&exists); err != nil || !exists {
				return problem.BadRequest("tipo documental indicado é inválido")
			}
		}
		if _, err := tx.Exec(ctx, `INSERT INTO batches (id, tenant_id, unit_id, enviado_por, arquivo_original, storage_key, sha256, bytes, tipo_lote, dica_funcionario_id, dica_tipo, substitui_documento_id, linha_tempo)
		  VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,nullif($10,'')::uuid,nullif($11,''),nullif($12,'')::uuid, jsonb_build_array(jsonb_build_object('quando', now(), 'tipo','RECEBIDO','mensagem', 'arquivo recebido e verificado (SHA-256 ' || left($7,12) || '…)')))`,
			batchID, tenantID, unit, userID, m.Filename, key, sha, m.Size, m.TipoLote, m.DicaFuncionarioID, m.DicaTipo, m.SubstituiDocumentoID); err != nil {
			return err
		}
		tx.Exec(ctx, `UPDATE tenants SET bytes_usados=bytes_usados+$2 WHERE id=$1`, tenantID, m.Size)
		tx.Exec(ctx, `INSERT INTO storage_events (tenant_id, tipo, bytes, objeto, por) VALUES ($1,'UPLOAD',$2,$3,$4)`, tenantID, m.Size, key, userID)
		tx.Exec(ctx, `INSERT INTO usage_monthly (tenant_id, mes, bytes_total) VALUES ($1,to_char(now(),'YYYY-MM'),$2) ON CONFLICT (tenant_id, mes) DO UPDATE SET bytes_total=usage_monthly.bytes_total+$2`, tenantID, m.Size)
		tx.Exec(ctx, `INSERT INTO notifications (tenant_id, tipo, titulo, link)
		  SELECT $1,'COTA',$2,'/plano' FROM tenants WHERE id=$1 AND bytes_usados >= quota_bytes*0.8
		  AND NOT EXISTS (SELECT 1 FROM notifications WHERE tenant_id=$1 AND tipo='COTA' AND criado_em > now() - interval '1 day')`, tenantID, "Armazenamento acima de 80% da cota")
		return audit.Log(ctx, tx, audit.Event{TenantID: tenantID, Actor: userID, ActorRole: "RH", Acao: "UPLOAD_LOTE", Entidade: "batch", EntidadeID: batchID, IP: m.IP,
			Dados: map[string]any{"arquivo": m.Filename, "bytes": m.Size, "sha256": sha}})
	})
	if err != nil {
		return nil, err
	}
	if err := s.Enqueue(TaskPayload{TenantID: tenantID, BatchID: batchID, FailAt: m.FailAt}, 0); err != nil {
		return nil, fmt.Errorf("enfileirar: %w", err)
	}
	return &Created{ID: batchID, Status: "RECEBIDO"}, nil
}
