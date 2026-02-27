# Usamos Alpine (tiene sh, grep, etc.) y copiamos el binario
# de cloudflared desde la imagen oficial (que es scratch-based).
FROM cloudflare/cloudflared:latest AS cf-binary

FROM alpine:3.19
# Copiar solo el binario de cloudflared
COPY --from=cf-binary /usr/local/bin/cloudflared /usr/local/bin/cloudflared
# Herramientas necesarias para el script de captura de URL
RUN apk add --no-cache grep
