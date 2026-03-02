<div align="center">

# ⚡ Energy Monitor SI

### Sistema Inteligente para el Monitoreo y Gestión del Consumo Energético

[![n8n](https://img.shields.io/badge/Orchestration-n8n-FF6D6D?style=for-the-badge&logo=n8n&logoColor=white)](https://n8n.io/)
[![Docker](https://img.shields.io/badge/Deploy-Docker_Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![InfluxDB](https://img.shields.io/badge/TimeSeries-InfluxDB-22ADF6?style=for-the-badge&logo=influxdb&logoColor=white)](https://www.influxdata.com/)
[![MQTT](https://img.shields.io/badge/Protocol-MQTT-660066?style=for-the-badge&logo=mqtt&logoColor=white)](https://mqtt.org/)
[![Telegram](https://img.shields.io/badge/Alerts-Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)

<br/>

> Plataforma multiagente orientada a eventos para la detección temprana de anomalías energéticas, clasificación de severidad, diagnóstico con LLM y respuesta operativa automática en entornos universitarios.

<br/>

[![UNMSM](https://img.shields.io/badge/Universidad-UNMSM-8B0000?style=flat-square)](https://www.unmsm.edu.pe/)
[![Curso](https://img.shields.io/badge/Curso-Sistemas_Inteligentes-4CAF50?style=flat-square)]()
[![Semestre](https://img.shields.io/badge/Semestre-2026--0-orange?style=flat-square)]()

</div>

---

## 📋 Tabla de Contenidos

- [Descripción General](#-descripción-general)
- [Arquitectura del Sistema](#️-arquitectura-del-sistema)
- [Stack Tecnológico](#-stack-tecnológico)
- [Módulo Inteligente](#-módulo-inteligente)
- [Agentes Especialistas](#-agentes-especialistas)
- [Workflows de n8n](#-workflows-de-n8n)
- [Modelo de Datos](#-modelo-de-datos)
- [Instalación y Despliegue](#-instalación-y-despliegue)
- [Configuración](#️-configuración)
- [Pruebas](#-pruebas)
- [Estructura del Repositorio](#-estructura-del-repositorio)
- [Equipo](#-equipo)

---

## 🔍 Descripción General

El consumo eléctrico en infraestructuras universitarias suele monitorearse de forma tardía y reactiva, con escasa trazabilidad para detectar derroches, fallas eléctricas o patrones anómalos. El costo correctivo se incurre cuando el incidente ya afectó el servicio.

**Energy Monitor SI** resuelve este problema mediante un sistema inteligente orientado a eventos que:

- 📡 **Observa** lecturas energéticas por área vía MQTT en tiempo real
- 📊 **Mantiene** una línea base adaptativa por Media Móvil Exponencial (EMA)
- 🚨 **Detecta y clasifica** desviaciones en tres niveles: `Normal`, `Advertencia` y `Crítico`
- 🤖 **Produce** diagnósticos textuales con Gemini LLM
- ⚡ **Coordina** respuestas automáticas o semiautomáticas mediante flujos n8n
- 🧠 **Crea memoria operacional** mediante tablas de historial, incidentes, correlaciones y decisiones de agentes

### Áreas Monitoreadas

El sistema cubre las siguientes áreas funcionales del edificio universitario:

| # | Área |
|---|------|
| 1 | Laboratorio de Cómputo |
| 2 | Aulas Teóricas |
| 3 | Biblioteca |
| 4 | Cafetería |
| 5 | Oficinas Administrativas |
| 6 | Sala de Servidores |
| 7 | Estacionamiento |
| 8 | Auditorio |
| 9 | Gimnasio |
| 10 | Laboratorio de Química |

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CAPA DE INGESTA                                  │
│  Simulador / Sensores IoT  ──►  Mosquitto (MQTT Broker)              │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  CAPA DE ORQUESTACIÓN (n8n)                          │
│                                                                      │
│   Energía-Monitor-Pro-v2                                             │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │  EMA Calc  →  Severidad  →  Diagnóstico LLM  →  Alertas │       │
│   └──────────────────────────────┬──────────────────────────┘       │
│                                  │                                   │
│              Agente-Orquestador  ▼                                   │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│   │Diagnóst. │ │Correlac. │ │Mantenim. │ │Resoluc.  │             │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
│                                                                      │
│   Watchdog  │  Reporte Diario  │  Telegram Bot Control              │
└─────────────────────────────────────────────────────────────────────┘
                    │                          │
          ┌─────────▼──────────┐    ┌─────────▼──────────┐
          │   PERSISTENCIA     │    │  SERVICIOS EXTERNOS │
          │  PostgreSQL        │    │  Gemini API (LLM)   │
          │  InfluxDB          │    │  Telegram Bot API   │
          └────────────────────┘    └────────────────────┘
```

---

## 🛠 Stack Tecnológico

| Componente | Tecnología | Función |
|---|---|---|
| **Orquestación** | n8n | Motor central de workflows y agentes |
| **Base de datos transaccional** | PostgreSQL | Historial operacional, incidentes, trazabilidad |
| **Series de tiempo** | InfluxDB | Métricas continuas de consumo |
| **Broker de mensajería** | Mosquitto (MQTT) | Transporte de lecturas IoT |
| **Diagnóstico IA** | Gemini API | Generación de diagnósticos JSON y análisis textual |
| **Notificaciones** | Telegram Bot API | Alertas, reportes e interacción operativa |
| **Dashboard local** | Python + custom | Control de simulación y relés por área |
| **Infraestructura** | Docker Compose | Orquestación de contenedores y servicios |

---

## 🧠 Módulo Inteligente

### Algoritmo de Línea Base — Media Móvil Exponencial (EMA)

El núcleo de decisión combina **cuatro capas** de inteligencia:

```
1. Línea base adaptativa (EMA)
2. Reglas explícitas de severidad
3. Enriquecimiento por agentes especialistas
4. Generación de texto por LLM (Gemini)
```

#### Fórmula de cálculo

```
          ┌ lectura_t         si es la primera lectura
EMA_t  =  ┤ EMA_(t-1)         si modo es anómalo o relay_off
          └ α·lectura_t + (1-α)·EMA_(t-1)  en operación normal

desviación_t = ((lectura_t - base_t) / base_t) × 100
```

> `α = 0.2` — Factor de suavizado. La base se congela en modos anómalos para no contaminar la línea base.

#### Umbrales de severidad

```
┌─────────────────────────────────────────────────────────┐
│  Lecturas 1–50    →  WARMUP  (siempre Normal)           │
│  Desviación ≤ 35%  →  ✅ NORMAL                         │
│  35% < desv ≤ 80%  →  ⚠️  ADVERTENCIA                  │
│  Desviación > 80%  →  🚨 CRÍTICO                        │
│  Desviación > 150% (no simulación, no servidores)       │
│                    →  ⛔ AUTO-CORTE DE EMERGENCIA        │
└─────────────────────────────────────────────────────────┘
```

#### Pseudocódigo del motor de decisión

```python
# Entrada: area, kwh, timestamp, modo
ema_anterior, contador = leer_estado(area)

if contador == 0:
    ema_nuevo = kwh
elif modo in ["anomalo", "relay_off"]:
    ema_nuevo = ema_anterior
    base = ema_anterior
else:
    ema_nuevo = alpha * kwh + (1 - alpha) * ema_anterior
    base = ema_nuevo

contador += 1
desviacion = (kwh - base) / base * 100

if contador <= 50:
    severidad = "Normal"
elif desviacion > 80:
    severidad = "Critico"
elif desviacion > 35:
    severidad = "Advertencia"
else:
    severidad = "Normal"

guardar_historial(area, kwh, ema_nuevo, severidad)

if severidad != "Normal":
    diagnostico = gemini.diagnosticar(area, kwh, base, severidad)
    registrar_anomalia(diagnostico)
    telegram.alertar(diagnostico)
    orquestador.enviar(evento)
```

---

## 🤖 Agentes Especialistas

El sistema implementa una arquitectura **multiagente** donde cada agente tiene responsabilidades específicas:

### 🔍 Agente de Diagnóstico
Analiza el historial de las últimas 24 horas y clasifica el patrón de consumo:

| Patrón | Descripción |
|---|---|
| `abnormally_low` | Consumo inusualmente bajo |
| `sustained` | Consumo alto sostenido |
| `accelerating` | Consumo en aceleración |
| `punctual` | Pico puntual |
| `moderate` | Desviación moderada |

### 🔗 Agente de Correlación
- Requiere **≥ 3 áreas anómalas** en una ventana de **5 minutos**
- Aplica **cooldown de 10 minutos** entre correlaciones
- Emite alerta consolidada con causa probable sistémica

### 🔧 Agente de Mantenimiento
- Detecta crecimiento promedio de **≥ 1.5% diario** durante **≥ 5 días**
- Descarta spikes mayores al 50% para evitar falsos positivos
- Genera órdenes preventivas con prioridad: `baja` → `media` → `alta` → `urgente`

### 🛠️ Agente de Resolución
| Condición | Acción |
|---|---|
| Consumo vuelve al 20% del EMA | ✅ Cierra incidente |
| Incidente supera 120 minutos | 🔺 Escala automáticamente |
| Estado intermedio | 👁️ Mantiene en observación |

### 📊 Agente de Reportes
Genera reportes automáticos en tres modalidades:
- **Turno** — al inicio de cada turno (06:00, 14:00, 22:00)
- **Post-incidente** — tras el cierre de un incidente crítico
- **Semanal** — resumen consolidado de 7 días

---

## ⚙️ Workflows de n8n

| Workflow | Trigger | Descripción |
|---|---|---|
| `Energía-Monitor-Pro-v2` | MQTT `edificio/+/consumo` | Ingesta, EMA, severidad, diagnóstico LLM, alertas y auto-corte |
| `Agente-Orquestador` | Webhook `agentorchestrator` | Deduplica alertas y enruta a agentes especialistas |
| `Agente-Diagnóstico` | Webhook `agentdiagnosis` | Clasifica patrones con contexto de 24h |
| `Agente-Correlación` | Webhook `agentcorrelation` | Consolida eventos en múltiples áreas simultáneas |
| `Agente-Mantenimiento` | Webhook `agentmaintenance` | Detecta degradación gradual y crea orden preventiva |
| `Agente-Resolución` | Webhook `agentresolution` | Abre, cierra o escala incidentes |
| `Agente-Reportes` | Webhook + cron 06/14/22h | Reportes de turno, post-incidente y semanal |
| `Monitor-Salud-Sistema` | Programado | Detecta sensores sin reportar y consumo persistente |
| `Reporte-DiarioAutomático` | Cron 08:00 | Reporte de 24h con análisis breve de IA |
| `Telegram-Bot-Control` | Telegram Trigger | Atención al operador, exportación, predicción y control operativo |

---

## 🗄️ Modelo de Datos

```sql
-- Línea base por área
ema_estado              (area, ema_valor, lectura_num, updated_at)

-- Lecturas registradas
energy_history          (id, area, kwh, ema, desviacion, severidad, modo, timestamp)

-- Eventos anómalos
anomalias               (id, area, kwh, base, severidad, diagnostico_json, timestamp)

-- Control de deduplicación
alert_history           (id, area, severidad, hash, created_at)

-- Incidentes multiárea
correlaciones           (id, areas, causa_probable, inicio, fin, estado)

-- Órdenes preventivas
mantenimiento_preventivo(id, area, prioridad, descripcion, estado, created_at)

-- Ciclo de vida de incidentes
incidentes              (id, area, severidad, apertura, cierre, estado, notas)

-- Auditoría de decisiones
agent_decisions         (id, agente, accion, contexto_json, timestamp)
```

---

## 🚀 Instalación y Despliegue

### Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/install/) instalados
- Cuenta de [Telegram](https://telegram.org/) para crear un Bot
- API Key de [Google Gemini](https://ai.google.dev/) (tier gratuito disponible)

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/jefry5/energy-monitor-si.git
cd energy-monitor-si
```

### Paso 2 — Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales (ver sección Configuración)
```

### Paso 3 — Levantar la infraestructura

```bash
docker compose up -d
```

Los siguientes servicios se iniciarán automáticamente:

| Servicio | Puerto | Descripción |
|---|---|---|
| n8n | `5678` | Motor de workflows |
| PostgreSQL | `5432` | Base de datos principal |
| InfluxDB | `8086` | Series de tiempo |
| Mosquitto | `1883` | Broker MQTT |
| Dashboard | `8080` | Panel de control local |
| Cloudflared | — | Túnel para webhooks externos |

### Paso 4 — Inicializar la base de datos

```bash
# Ejecutar el script de inicialización de tablas
docker exec -it energy-monitor-postgres psql -U postgres -d energydb -f /init/schema.sql
```

### Paso 5 — Importar workflows en n8n

1. Acceder a `http://localhost:5678`
2. Ir a **Settings → Import workflows**
3. Importar los 10 archivos `.json` desde la carpeta `n8n/workflows/`
4. Activar cada workflow y verificar los webhooks de los agentes

### Paso 6 — Verificar el sistema

```bash
# Publicar una lectura de prueba vía MQTT
mosquitto_pub -h localhost -t "edificio/laboratorio_computo/consumo" \
  -m '{"area":"laboratorio_computo","kwh":45.2,"timestamp":"2026-01-01T10:00:00Z","modo":"normal"}'
```

✅ Si el sistema está operativo, recibirás confirmación en Telegram y verás registros en PostgreSQL.

---

## ⚙️ Configuración

Edita el archivo `.env` con los siguientes valores:

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=energydb

# InfluxDB
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=your_influx_token
INFLUXDB_ORG=energy-monitor
INFLUXDB_BUCKET=energy

# MQTT
MQTT_HOST=mosquitto
MQTT_PORT=1883

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Gemini API
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-pro

# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your_n8n_password
```

---

## 🧪 Pruebas

El sistema incluye 7 escenarios de prueba funcional:

| Escenario | Preparación | Resultado Esperado |
|---|---|---|
| ✅ **Normal** | Lecturas dentro de banda histórica | EMA actualizado, sin alertas, historial registrado |
| 🚨 **Extremo** | Pico sostenido > 80% sobre la base | Clasificación Crítico, alerta en Telegram, fila en `anomalias` |
| ❌ **Erróneo** | Cortar publicación de un área | Watchdog reporta sensor ausente |
| 🔄 **Duplicado** | Repetir misma anomalía en < 5 min | Orquestador deduplica, fila en `alert_history` |
| 🔗 **Correlación** | Anomalías en ≥ 3 áreas en 5 min | Alerta consolidada, fila en `correlaciones` |
| 📉 **Degradación** | Crecimiento gradual por varios días | Orden preventiva en `mantenimiento_preventivo` |
| 🔓 **Resolución** | Área crítica vuelve a normalidad | Incidente cerrado o escalado en `incidentes` |

---

## 📁 Estructura del Repositorio

```
energy-monitor-si/
├── 📁 data/
│   ├── grafana/            # Configuración de dashboards Grafana
│   └── influxdb/           # Datos persistidos de InfluxDB
├── 📁 infra/
│   └── init/               # Scripts de inicialización de BD
├── 📁 n8n/
│   ├── data/               # Datos persistidos de n8n
│   └── workflows/          # 10 workflows exportados (.json)
│       ├── energia-monitor-pro-v2.json
│       ├── agente-orquestador.json
│       ├── agente-diagnostico.json
│       ├── agente-correlacion.json
│       ├── agente-mantenimiento.json
│       ├── agente-resolucion.json
│       ├── agente-reportes.json
│       ├── monitor-salud-sistema.json
│       ├── reporte-diario-automatico.json
│       └── telegram-bot-control.json
├── 📁 src/
│   ├── dashboard/          # Panel de control local
│   └── simulator/          # Simulador de sensores MQTT
├── 📁 venv/
├── 📄 .env.example
├── 📄 .gitignore
├── 📄 docker-compose.yml
├── 📄 README.md
├── 📄 requirements.txt
└── 📄 requirements-dashboard.txt
```

---

## 👥 Equipo

| Nombre | Rol |
|---|---|
| Jefferson Alexander Marquez Rosasco | Desarrollador |
| Cristian Ricardo Morales Damasco | Desarrollador |
| Alessandro Jesus Torres Tamariz | Desarrollador |
| Víctor Daniel Celadita Romero | Desarrollador |

**Docentes:** Gelber Christian Uscuchagua Flores · Herminio Paucar Curasma

**Institución:** Universidad Nacional Mayor de San Marcos — Facultad de Ingeniería de Sistemas e Informática

**Curso:** Sistemas Inteligentes · Semestre 2026-0 · Grupo 3

---

<div align="center">

Desarrollado con ❤️ para la **UNMSM** · Facultad de Ingeniería de Sistemas e Informática

</div>