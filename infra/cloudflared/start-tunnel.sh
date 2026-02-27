#!/bin/sh
# ============================================================
#  EnergyCore v2 — Cloudflare Quick Tunnel
#  Inicia el túnel y escribe la URL HTTPS en /shared/webhook_url.txt
#  para que n8n la lea antes de arrancar.
# ============================================================

URL_FILE="/shared/webhook_url.txt"

# Limpiar URL anterior (importante en restart)
rm -f "$URL_FILE" 2>/dev/null || true

echo "================================================================"
echo " [cloudflared] Iniciando túnel hacia http://n8n:5678 ..."
echo "================================================================"

# Ejecutar cloudflared y leer su output línea por línea
cloudflared tunnel --no-autoupdate --url http://n8n:5678 2>&1 | while IFS= read -r line; do
    echo "[cloudflared] $line"

    # Intentar extraer la URL de trycloudflare.com
    if [ ! -f "$URL_FILE" ]; then
        URL=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' | head -1)
        if [ -n "$URL" ]; then
            echo "$URL" > "$URL_FILE"
            echo "================================================================"
            echo " [cloudflared] ✅ Túnel activo!"
            echo " [cloudflared]    URL: $URL"
            echo " [cloudflared]    Archivo: $URL_FILE"
            echo "================================================================"
        fi
    fi
done
