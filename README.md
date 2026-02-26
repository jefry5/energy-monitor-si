# ⚡ Energy Monitor Pro v2 + Gemini AI

Este proyecto es un **Sistema Inteligente de Gestión y Monitoreo Energético** que utiliza una arquitectura moderna basada en microservicios, automatización con n8n e Inteligencia Artificial (Google Gemini) para detectar anomalías y predecir consumos en tiempo real.

## 🏗️ Arquitectura del Sistema

El sistema integra múltiples capas de tecnología para ofrecer una solución robusta y escalable:

*   **Simulador Pro v2 (Python)**: Genera lecturas realistas de sensores (kWh, Voltaje, Corriente, Temperatura) con perfiles de consumo horario y patrones de fallas.
*   **MQTT Broker (Mosquitto)**: Actúa como el puente de comunicación de baja latencia entre los sensores y el motor de automatización.
*   **n8n (Workflow Engine)**: El "cerebro" donde reside toda la lógica de negocio, detección de anomalías y orquestación de mensajes.
*   **Google Gemini AI**: Proporciona diagnósticos inteligentes de anomalías y genera predicciones de consumo basadas en datos históricos.
*   **PostgreSQL**: Base de datos relacional para el historial de consumos, registros de anomalías y estados del sistema.
*   **InfluxDB**: Almacenamiento optimizado para series de tiempo y análisis métrico profundo.
*   **Telegram Bot**: Interfaz de usuario intuitiva para consultas rápidas, reportes en PDF/CSV y alertas críticas.

## 🚀 Inicio Rápido

1.  **Requisitos**:
    *   Docker Desktop instalado y corriendo.
    *   Python 3.10+ (recomendado usar `venv`).
    *   Un Bot de Telegram (creado vía @BotFather).
    *   Google Gemini API Key.

2.  **Configuración**:
    Crea un archivo `.env` en la raíz con el siguiente formato:
    ```env
    GEMINI_API_KEY="..."
    TELEGRAM_TOKEN="..."
    TELEGRAM_CHAT_ID="..."
    
    POSTGRES_DB="energia_db"
    POSTGRES_USER="energia_user"
    POSTGRES_PASSWORD="..."
    ```

3.  **Lanzamiento Maestro**:
    Simplemente ejecuta el script de automatización en PowerShell:
    ```powershell
    .\INICIAR_PROYECTO.ps1
    ```
    *Este script levantará Docker, configurará las tablas de la BD, iniciará el túnel de Cloudflare y arrancará n8n.*

## 📱 Comandos de Telegram

*   `/start`: Abre el menú interactivo principal.
*   📊 **Estado en Vivo**: Visualiza la carga actual de todas las áreas con barras de progreso.
*   📈 **Reporte 24h**: Resumen detallado de consumo, costos estimados y emisiones de CO2.
*   🚨 **Ver Anomalías**: Listado de los últimos incidentes diagnosticados por la IA.
*   🧠 **Predicción IA**: Consulta a Gemini sobre el consumo esperado para las próximas 24 horas.
*   💾 **Exportar CSV**: Descarga el historial crudo para análisis externo.

## 🛠️ Tecnologías Utilizadas

*   **Backend**: Python 3.12 (paho-mqtt, psycopg2, influxdb-client)
*   **Automatización**: n8n v2.7.5 (Self-hosted)
*   **Infraestructura**: Docker & Docker-Compose
*   **Comunicación**: Protocolo MQTT
*   **IA**: Vertex AI / Google Gemini
*   **Seguridad**: Cloudflare Tunnels (acceso externo seguro sin abrir puertos)

## 📝 Licencia
Este proyecto fue desarrollado como una solución avanzada para monitoreo de energía en entornos universitarios e industriales.

---
✨ *Desarrollado con ❤️ para la eficiencia energética.*
