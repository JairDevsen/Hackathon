.PHONY: run worker test lint migrate seed
run:     ; go run ./cmd/api
worker:  ; go run ./cmd/worker
test:    ; go test -race ./...
lint:    ; go vet ./... && golangci-lint run
migrate: ; go run ./cmd/migrate
seed:    ; go run ./cmd/seed
