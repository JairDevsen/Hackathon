package documents

import "github.com/agreser-innovations/citadel-ia/backend/pkg/crypto"

func sealCPF(dek []byte, digits, tenantID string) ([]byte, error) {
	return crypto.Seal(dek, []byte(digits), []byte("cpf|"+tenantID))
}
