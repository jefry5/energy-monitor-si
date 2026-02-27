#!/bin/sh
# ============================================================
#  n8n entrypoint wrapper
#  Lee la URL del túnel Cloudflare del volumen compartido
#  y arranca n8n con WEBHOOK_URL en su entorno usando 'env'.
# ============================================================

URL_FILE="/shared/webhook_url.txt"

if [ -s "$URL_FILE" ]; then
    TUNNEL_URL="$(cat "$URL_FILE" | tr -d '\n\r ')"
    echo "[n8n-init] WEBHOOK_URL=$TUNNEL_URL"
    # Usar 'env' para pasar la variable al proceso hijo
    exec env WEBHOOK_URL="$TUNNEL_URL" /docker-entrypoint.sh
else
    echo "[n8n-init] ADVERTENCIA: No se encontró URL del túnel"
    exec /docker-entrypoint.sh
fi
