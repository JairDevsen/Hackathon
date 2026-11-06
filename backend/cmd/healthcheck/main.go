// Healthcheck para imagens distroless (sem curl/wget): sai com 0 se /healthz responder 200.
package main

import (
	"net/http"
	"os"
	"time"
)

func main() {
	addr := os.Getenv("HEALTH_URL")
	if addr == "" {
		addr = "http://127.0.0.1:8080/healthz"
	}
	c := http.Client{Timeout: 3 * time.Second}
	r, err := c.Get(addr)
	if err != nil || r.StatusCode != 200 {
		os.Exit(1)
	}
}
