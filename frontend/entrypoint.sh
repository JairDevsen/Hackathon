#!/bin/sh
# Gera /config.js a partir das variáveis PUBLIC_* (configuração em tempo de execução, sem rebuild).
cat > /usr/share/nginx/html/config.js <<JS
window.__CONFIG__ = { API_URL: "${PUBLIC_API_URL:-}" };
JS
