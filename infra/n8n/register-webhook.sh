#!/bin/sh
# ============================================================
#  webhook-init — Registra el webhook de Telegram en n8n
#  Este contenedor:
#  1. Espera que cloudflared tenga una URL HTTPS lista
#  2. Espera que n8n esté completamente disponible
#  3. Obtiene el webhook ID del Telegram Trigger desde n8n
#  4. Registra directamente el webhook con Telegram API
# ============================================================

URL_FILE="/shared/webhook_url.txt"
N8N_URL="http://n8n:5678"
N8N_USER="${N8N_BASIC_AUTH_USER:-admin}"
N8N_PASS="${N8N_BASIC_AUTH_PASSWORD:-admin123}"

echo "================================================================"
echo " [webhook-init] Iniciando registro automático de webhook"
echo "================================================================"

# 1. Esperar la URL de cloudflared
echo " [webhook-init] Esperando URL del túnel..."
elapsed=0
while [ ! -s "$URL_FILE" ] && [ $elapsed -lt 120 ]; do
    sleep 3; elapsed=$((elapsed + 3))
    echo " [webhook-init] ... ${elapsed}s"
done

if [ ! -s "$URL_FILE" ]; then
    echo " [webhook-init] ❌ Timeout esperando URL del túnel. Abortando."
    exit 1
fi

TUNNEL_URL=$(cat "$URL_FILE" | tr -d '[:space:]')
echo " [webhook-init] ✅ URL del túnel: $TUNNEL_URL"

# 2. Esperar que n8n esté listo
echo " [webhook-init] Esperando que n8n esté disponible..."
elapsed=0
while [ $elapsed -lt 120 ]; do
    STATUS=$(wget -q -O- --server-response "${N8N_URL}/healthz" 2>&1 | head -1)
    if echo "$STATUS" | grep -q "200"; then
        echo " [webhook-init] ✅ n8n está listo"
        break
    fi
    sleep 5; elapsed=$((elapsed + 5))
    echo " [webhook-init] ... ${elapsed}s (n8n aún iniciando)"
done

# 3. Esperar credenciales de n8n — necesario para la API
sleep 5

# 4. Registrar el webhook directamente en Telegram
if [ -z "$TELEGRAM_TOKEN" ]; then
    echo " [webhook-init] ⚠️  TELEGRAM_TOKEN no está definido. Saltando registro."
    exit 0
fi

# Obtener la lista de workflows para encontrar el webhook ID
echo " [webhook-init] Buscando workflows activos en n8n..."
WORKFLOWS=$(wget -q -O- --user="$N8N_USER" --password="$N8N_PASS" \
    "${N8N_URL}/api/v1/workflows" 2>/dev/null)

if [ -z "$WORKFLOWS" ]; then
    echo " [webhook-init] ⚠️  No se pudo conectar a n8n API. Intentando sin auth..."
    WORKFLOWS=$(wget -q -O- "${N8N_URL}/api/v1/workflows" 2>/dev/null)
fi

# Buscar el webhook ID del Telegram Trigger en los workflows
WEBHOOK_ID=$(echo "$WORKFLOWS" | grep -oE '"webhookId":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$WEBHOOK_ID" ]; then
    FULL_WEBHOOK_URL="${TUNNEL_URL}/webhook/${WEBHOOK_ID}/webhook"
    echo " [webhook-init] 🔗 Webhook URL: $FULL_WEBHOOK_URL"
    
    # Registrar webhook con Telegram
    RESULT=$(wget -q -O- \
        "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook?url=${FULL_WEBHOOK_URL}" 2>/dev/null)
    echo " [webhook-init] 📨 Respuesta de Telegram: $RESULT"
    
    if echo "$RESULT" | grep -q '"ok":true'; then
        echo " [webhook-init] ✅ ¡Webhook registrado exitosamente en Telegram!"
    else
        echo " [webhook-init] ⚠️  El registro automático falló. Verifica el token y el workflow."
    fi
else
    echo " [webhook-init] ⚠️  No se encontró webhook ID. Asegúrate de activar el workflow en n8n."
    echo " [webhook-init]    URL del túnel disponible: $TUNNEL_URL"
fi

echo "================================================================"
echo " [webhook-init] ✅ Proceso completado."
echo "================================================================"
