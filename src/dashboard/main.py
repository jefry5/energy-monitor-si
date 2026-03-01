import json
import logging
import math
import os
import random
import sys
import time
import asyncio
import threading
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Final, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import psycopg2
import psycopg2.extras

load_dotenv()


# ──────────────────────────────────────────────
# PostgreSQL helper
# ──────────────────────────────────────────────
def _get_pg_conn():
    """Return a new psycopg2 connection using env vars."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "energy_monitor"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def _run_migrations():
    """Ensure all required tables exist with correct column names.

    Handles both fresh databases AND pre-existing volumes with old column names.
    Strategy:
      1. CREATE TABLE IF NOT EXISTS (handles fresh DBs)
      2. Rename old columns to match n8n workflow expectations
      3. ADD COLUMN IF NOT EXISTS for missing columns
      4. Create indexes (using correct column names)
      5. Seed relay_states
    """

    # Step 1: Create tables if they don't exist (fresh DB)
    create_tables = """
    CREATE TABLE IF NOT EXISTS anomalias (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        area VARCHAR(100) NOT NULL,
        dispositivo VARCHAR(100) NOT NULL,
        valor_kwh DECIMAL(10,4) NOT NULL,
        ema_kwh DECIMAL(10,4) NOT NULL,
        desviacion DECIMAL(8,2) NOT NULL,
        severidad VARCHAR(20) NOT NULL,
        recomendacion TEXT,
        accion_tomada VARCHAR(50) DEFAULT 'pendiente',
        causa_raiz VARCHAR(100) DEFAULT NULL,
        correlacion_id INTEGER DEFAULT NULL,
        resuelto_en TIMESTAMPTZ DEFAULT NULL,
        metodo_deteccion VARCHAR(50) DEFAULT 'ema'
    );
    CREATE TABLE IF NOT EXISTS fallas_sensor (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        dispositivo VARCHAR(100) NOT NULL,
        tipo_falla VARCHAR(50) NOT NULL,
        descripcion TEXT,
        resuelto BOOLEAN DEFAULT FALSE
    );
    CREATE TABLE IF NOT EXISTS ema_estado (
        area VARCHAR(100) PRIMARY KEY,
        ema_actual DECIMAL(10,4) NOT NULL,
        contador INTEGER NOT NULL DEFAULT 0,
        ultima_vez TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS energy_history (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        area VARCHAR(100) NOT NULL,
        reading DECIMAL(10,4) NOT NULL,
        ema DECIMAL(10,4) NOT NULL,
        severity VARCHAR(20) NOT NULL DEFAULT 'Normal'
    );
    CREATE TABLE IF NOT EXISTS relay_states (
        area VARCHAR(100) PRIMARY KEY,
        estado VARCHAR(20) NOT NULL DEFAULT 'ENCENDIDO',
        motivo VARCHAR(200) DEFAULT NULL,
        ultimo_cambio TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        cambiado_por VARCHAR(100) DEFAULT 'sistema'
    );
    CREATE TABLE IF NOT EXISTS agent_decisions (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        agent_name VARCHAR(100) NOT NULL,
        decision_type VARCHAR(100) NOT NULL,
        area VARCHAR(100) DEFAULT NULL,
        input_data JSONB DEFAULT NULL,
        output_data JSONB DEFAULT NULL,
        action_taken TEXT DEFAULT NULL,
        confidence DECIMAL(5,4) DEFAULT NULL,
        execution_time_ms INTEGER DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS incidentes (
        id SERIAL PRIMARY KEY,
        anomalia_id INTEGER DEFAULT NULL,
        timestamp_apertura TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        timestamp_cierre TIMESTAMPTZ DEFAULT NULL,
        area VARCHAR(100) NOT NULL,
        severidad VARCHAR(20) NOT NULL,
        estado VARCHAR(30) NOT NULL DEFAULT 'abierto',
        kwh_al_abrir DECIMAL(10,4) NOT NULL,
        kwh_al_cerrar DECIMAL(10,4) DEFAULT NULL,
        resolucion_automatica BOOLEAN DEFAULT FALSE,
        notas TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS mantenimiento_preventivo (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        area VARCHAR(100) NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        tendencia_diaria_pct DECIMAL(6,3),
        dias_detectados INTEGER DEFAULT 0,
        ema_inicio DECIMAL(10,4),
        ema_actual DECIMAL(10,4),
        prioridad VARCHAR(20) DEFAULT 'media',
        estado VARCHAR(30) DEFAULT 'pendiente',
        recomendacion TEXT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        anomalia_id INTEGER DEFAULT NULL,
        incidente_id INTEGER DEFAULT NULL,
        usuario VARCHAR(100) NOT NULL,
        tipo VARCHAR(30) NOT NULL,
        comentario TEXT DEFAULT NULL,
        chat_id BIGINT DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS correlaciones (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        areas TEXT[] NOT NULL,
        tipo VARCHAR(50) NOT NULL,
        causa_inferida VARCHAR(100) DEFAULT NULL,
        descripcion TEXT DEFAULT NULL,
        anomalia_ids INTEGER[] DEFAULT NULL,
        severidad_consolidada VARCHAR(20) DEFAULT 'Advertencia'
    );
    CREATE TABLE IF NOT EXISTS alert_history (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        area VARCHAR(100) NOT NULL,
        tipo_alerta VARCHAR(50) DEFAULT NULL,
        hash_contenido VARCHAR(64) DEFAULT NULL,
        agente_origen VARCHAR(100) DEFAULT NULL,
        dedup_key VARCHAR(128) UNIQUE DEFAULT NULL,
        severidad VARCHAR(20) DEFAULT NULL,
        kwh DECIMAL(10,4) DEFAULT NULL
    );
    """

    # Step 2: Rename old columns to match n8n workflows (idempotent DO blocks)
    rename_columns = """
    -- agent_decisions: agente → agent_name
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='agent_decisions' AND column_name='agente')
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='agent_decisions' AND column_name='agent_name')
        THEN
            ALTER TABLE agent_decisions RENAME COLUMN agente TO agent_name;
        END IF;
    END $$;

    -- incidentes: inicio → timestamp_apertura
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='inicio')
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='timestamp_apertura')
        THEN
            ALTER TABLE incidentes RENAME COLUMN inicio TO timestamp_apertura;
        END IF;
    END $$;

    -- incidentes: fin → timestamp_cierre
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='fin')
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='timestamp_cierre')
        THEN
            ALTER TABLE incidentes RENAME COLUMN fin TO timestamp_cierre;
        END IF;
    END $$;

    -- incidentes: kwh_inicio → kwh_al_abrir
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='kwh_inicio')
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='kwh_al_abrir')
        THEN
            ALTER TABLE incidentes RENAME COLUMN kwh_inicio TO kwh_al_abrir;
        END IF;
    END $$;

    -- incidentes: kwh_fin → kwh_al_cerrar
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='kwh_fin')
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='incidentes' AND column_name='kwh_al_cerrar')
        THEN
            ALTER TABLE incidentes RENAME COLUMN kwh_fin TO kwh_al_cerrar;
        END IF;
    END $$;
    """

    # Step 3: Add missing columns to pre-existing tables
    add_columns = """
    ALTER TABLE alert_history ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(128) DEFAULT NULL;
    ALTER TABLE alert_history ADD COLUMN IF NOT EXISTS severidad VARCHAR(20) DEFAULT NULL;
    ALTER TABLE alert_history ADD COLUMN IF NOT EXISTS kwh DECIMAL(10,4) DEFAULT NULL;

    -- Fix NOT NULL on legacy columns that orchestrator doesn't always provide
    ALTER TABLE alert_history ALTER COLUMN tipo_alerta DROP NOT NULL;
    ALTER TABLE alert_history ALTER COLUMN hash_contenido DROP NOT NULL;
    ALTER TABLE alert_history ALTER COLUMN tipo_alerta SET DEFAULT 'energia';
    ALTER TABLE alert_history ALTER COLUMN hash_contenido SET DEFAULT 'auto';

    ALTER TABLE mantenimiento_preventivo ADD COLUMN IF NOT EXISTS ema_inicio DECIMAL(10,4) DEFAULT NULL;
    ALTER TABLE mantenimiento_preventivo ADD COLUMN IF NOT EXISTS ema_actual DECIMAL(10,4) DEFAULT NULL;
    ALTER TABLE correlaciones ADD COLUMN IF NOT EXISTS causa_inferida VARCHAR(100) DEFAULT NULL;

    -- Ensure dedup_key has unique constraint (may already exist)
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'alert_history_dedup_key_key')
        THEN
            ALTER TABLE alert_history ADD CONSTRAINT alert_history_dedup_key_key UNIQUE (dedup_key);
        END IF;
    END $$;
    """

    # Step 4: Drop old indexes that reference old column names, then create correct ones
    fix_indexes = """
    -- Drop index on old column name if it exists
    DROP INDEX IF EXISTS idx_agent_decisions_agent;

    -- Create all indexes
    CREATE INDEX IF NOT EXISTS idx_anomalias_timestamp ON anomalias (timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_anomalias_area ON anomalias (area);
    CREATE INDEX IF NOT EXISTS idx_anomalias_severidad ON anomalias (severidad);
    CREATE INDEX IF NOT EXISTS idx_history_timestamp ON energy_history (timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_history_area ON energy_history (area);
    CREATE INDEX IF NOT EXISTS idx_agent_decisions_ts ON agent_decisions (timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent ON agent_decisions (agent_name);
    CREATE INDEX IF NOT EXISTS idx_incidentes_estado ON incidentes (estado);
    CREATE INDEX IF NOT EXISTS idx_incidentes_area ON incidentes (area);
    CREATE INDEX IF NOT EXISTS idx_feedback_tipo ON feedback (tipo);
    CREATE INDEX IF NOT EXISTS idx_correlaciones_ts ON correlaciones (timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_alert_history_hash ON alert_history (hash_contenido);
    CREATE INDEX IF NOT EXISTS idx_alert_history_area_ts ON alert_history (area, timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_mantenimiento_area ON mantenimiento_preventivo (area);
    CREATE INDEX IF NOT EXISTS idx_mantenimiento_estado ON mantenimiento_preventivo (estado);
    """

    # Step 5: Seed relay_states
    seed = """
    INSERT INTO relay_states (area, estado) VALUES
        ('laboratorio_computo', 'ENCENDIDO'),
        ('aulas_teoricas', 'ENCENDIDO'),
        ('biblioteca', 'ENCENDIDO'),
        ('cafeteria', 'ENCENDIDO'),
        ('oficinas_admin', 'ENCENDIDO'),
        ('sala_servidores', 'ENCENDIDO'),
        ('estacionamiento', 'ENCENDIDO'),
        ('auditorio', 'ENCENDIDO'),
        ('gimnasio', 'ENCENDIDO'),
        ('laboratorio_quimica', 'ENCENDIDO')
    ON CONFLICT (area) DO NOTHING;
    """

    steps = [
        ("create_tables", create_tables),
        ("rename_columns", rename_columns),
        ("add_columns", add_columns),
        ("fix_indexes", fix_indexes),
        ("seed_data", seed),
    ]

    for attempt in range(1, 11):
        try:
            conn = _get_pg_conn()
            conn.autocommit = True
            cur = conn.cursor()
            for step_name, sql in steps:
                cur.execute(sql)
            cur.close()
            conn.close()
            return True
        except Exception as exc:
            if attempt < 10:
                time.sleep(2)
            else:
                print(f"[MIGRATION] FAILED after 10 attempts: {exc}", file=sys.stderr)
                return False


# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("EnergySimProWeb")

# ──────────────────────────────────────────────
# Enums & Config
# ──────────────────────────────────────────────
class SimMode(str, Enum):
    NORMAL          = "normal"
    ANOMALY         = "anomaly"
    SENSOR_FAILURE  = "sensor_failure"
    GRADUAL_DRIFT   = "gradual_drift"
    INTERMITTENT    = "intermittent"
    FLOOD           = "flood"
    NIGHT_ANOMALY   = "night_anomaly"

class Severity(str, Enum):
    NORMAL      = "Normal"
    WARNING     = "Warning"
    CRITICAL    = "Critical"

class RelayState(str, Enum):
    ENCENDIDO = "ENCENDIDO"
    APAGADO   = "APAGADO"

@dataclass
class AreaProfile:
    base: float
    nocturno: float
    std_pct: float = 0.10
    peak_hour: int = 10
    peak_factor: float = 1.20
    devices: int = 1
    floor: int = 1

@dataclass
class SensorReading:
    area: str
    kwh: float
    timestamp: str
    modo: str
    sensor_id: str
    voltage: float
    current: float
    power_factor: float
    temperature_c: float
    humidity_pct: float
    quality: str
    device_count: int
    floor: int
    sequence: int
    relay_state: str = "ENCENDIDO"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

AREAS: Final[Dict[str, AreaProfile]] = {
    "laboratorio_computo": AreaProfile(base=8.5,  nocturno=1.2,  std_pct=0.08, peak_hour=14, peak_factor=1.30, devices=40, floor=2),
    "aulas_teoricas":      AreaProfile(base=3.2,  nocturno=0.4,  std_pct=0.12, peak_hour=10, peak_factor=1.15, devices=12, floor=1),
    "biblioteca":          AreaProfile(base=4.8,  nocturno=0.8,  std_pct=0.07, peak_hour=11, peak_factor=1.10, devices=20, floor=3),
    "cafeteria":           AreaProfile(base=6.1,  nocturno=1.5,  std_pct=0.15, peak_hour=12, peak_factor=1.45, devices=15, floor=1),
    "oficinas_admin":      AreaProfile(base=3.9,  nocturno=0.3,  std_pct=0.09, peak_hour=9,  peak_factor=1.20, devices=18, floor=4),
    "sala_servidores":     AreaProfile(base=12.0, nocturno=11.5, std_pct=0.03, peak_hour=15, peak_factor=1.05, devices=8,  floor=2),
    "estacionamiento":     AreaProfile(base=1.2,  nocturno=0.6,  std_pct=0.20, peak_hour=8,  peak_factor=1.10, devices=30, floor=0),
    "auditorio":           AreaProfile(base=5.5,  nocturno=0.2,  std_pct=0.25, peak_hour=16, peak_factor=1.60, devices=6,  floor=1),
    "gimnasio":            AreaProfile(base=4.2,  nocturno=0.5,  std_pct=0.18, peak_hour=17, peak_factor=1.35, devices=10, floor=1),
    "laboratorio_quimica": AreaProfile(base=7.8,  nocturno=2.1,  std_pct=0.10, peak_hour=13, peak_factor=1.25, devices=22, floor=3),
}

# ──────────────────────────────────────────────
# Global App State (Mutable)
# ──────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.area_modes: Dict[str, SimMode] = {a: SimMode("normal") for a in AREAS}
        self.relay_states: Dict[str, RelayState] = {a: RelayState.ENCENDIDO for a in AREAS}
        self.relay_reasons: Dict[str, str] = {a: "" for a in AREAS}
        self.relay_changed_by: Dict[str, str] = {a: "sistema" for a in AREAS}
        # Default to a faster interval for web demo purposes (e.g., 2 seconds)
        self.interval_sec: float = float(os.getenv("SIM_INTERVAL", "2.0"))
        self.running: bool = True
        # Alert dedup cache: hash -> timestamp
        self.recent_alerts: Dict[str, str] = {}
        # Feedback log in-memory (fallback)
        self.feedback_log: List[dict] = []

state = AppState()

# Environment settings
BROKER: Final[str] = os.getenv("MQTT_BROKER", "localhost")
PORT: Final[int] = int(os.getenv("MQTT_PORT", "1883"))
USERNAME: Final[str] = os.getenv("MQTT_USER", "")
PASSWORD: Final[str] = os.getenv("MQTT_PASS", "")
QOS: Final[int] = int(os.getenv("MQTT_QOS", "0"))
TOPIC_PREFIX: Final[str] = os.getenv("TOPIC_PREFIX", "edificio")
BUILDING_ID: Final[str] = os.getenv("BUILDING_ID", "edificio_principal")

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _gaussian_noise(mean: float, std_pct: float) -> float:
    factor = random.gauss(1.0, std_pct)
    return max(0.01, mean * factor)

def _seasonal_factor() -> float:
    month = datetime.now().month
    seasonal = {12: 1.05, 1: 1.05, 2: 1.04, 3: 1.02, 4: 1.00, 5: 0.99, 6: 0.97, 7: 0.96, 8: 0.97, 9: 0.98, 10: 1.00, 11: 1.02}
    return seasonal.get(month, 1.0)

def _hourly_factor(profile: AreaProfile) -> float:
    hour = datetime.now().hour + datetime.now().minute / 60.0
    distance = abs(hour - profile.peak_hour)
    if distance > 12:
        distance = 24 - distance
    bell = math.exp(-0.5 * (distance / 3.0) ** 2)
    return 1.0 + (profile.peak_factor - 1.0) * bell

def _is_night() -> bool:
    h = datetime.now().hour
    return h < 6 or h >= 22

def _simulate_env() -> tuple[float, float]:
    hour = datetime.now().hour
    temp = 18 + 10 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 0.5)
    temp = round(max(15.0, min(35.0, temp)), 1)
    hum = 75 - 35 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 1.5)
    hum = round(max(20.0, min(95.0, hum)), 1)
    return temp, hum

def _simulate_electrical(kwh: float) -> tuple[float, float, float]:
    voltage = round(random.gauss(220.0, 2.0), 1)
    pf = round(random.uniform(0.85, 0.98), 3)
    current = round((kwh * 1000) / (voltage * pf), 2)
    return voltage, current, pf

# ──────────────────────────────────────────────
# Reading generator
# ──────────────────────────────────────────────
class SensorSimulator:
    def __init__(self) -> None:
        self._drift: Dict[str, float] = {a: 1.0 for a in AREAS}
        self._seq:   Dict[str, int]   = {a: 0   for a in AREAS}
        self._intermittent_skip: Dict[str, bool] = {}

    def _base_kwh(self, area: str, profile: AreaProfile) -> float:
        base = profile.nocturno if _is_night() else profile.base
        return base * _hourly_factor(profile) * _seasonal_factor()

    def get_reading(self, area: str, profile: AreaProfile) -> Optional[SensorReading]:
        self._seq[area] += 1
        now_utc = datetime.now(timezone.utc).isoformat()
        temp, hum = _simulate_env()
        tags: List[str] = []

        # ── Check relay state — if OFF, produce zero reading ──
        if state.relay_states.get(area) == RelayState.APAGADO:
            return SensorReading(
                area=area, kwh=0.0, timestamp=now_utc,
                modo="relay_off", sensor_id=f"{BUILDING_ID}_{area}_s{profile.floor:02d}",
                voltage=0.0, current=0.0, power_factor=0.0,
                temperature_c=temp, humidity_pct=hum, quality="relay_off",
                device_count=0, floor=profile.floor,
                sequence=self._seq[area],
                relay_state=RelayState.APAGADO.value,
                tags=["relay_off"],
            )

        mode = state.area_modes.get(area, SimMode.NORMAL)

        if mode == SimMode.SENSOR_FAILURE:
            return None

        if mode == SimMode.INTERMITTENT:
            skip = self._intermittent_skip.get(area, False)
            self._intermittent_skip[area] = not skip
            if skip:
                return None
            tags.append("intermittent_recovery")

        base = self._base_kwh(area, profile)

        if mode == SimMode.GRADUAL_DRIFT:
            self._drift[area] = min(self._drift[area] + 0.02, 3.0)
            kwh = round(_gaussian_noise(base * self._drift[area], profile.std_pct), 4)
            tags.append(f"drift_factor:{self._drift[area]:.2f}")
            quality = "degraded" if self._drift[area] > 1.5 else "ok"

        elif mode == SimMode.ANOMALY:
            kwh = round(_gaussian_noise(base * 2.8, 0.05), 4)
            tags.append("spike_anomaly")
            quality = "degraded"

        elif mode == SimMode.NIGHT_ANOMALY and _is_night():
            kwh = round(_gaussian_noise(base * 3.5, 0.05), 4)
            tags.append("night_spike")
            quality = "degraded"

        else:
            kwh = round(_gaussian_noise(base, profile.std_pct), 4)
            quality = "ok"

        voltage, current, pf = _simulate_electrical(kwh)

        return SensorReading(
            area=area, kwh=kwh, timestamp=now_utc, modo=mode.value,
            sensor_id=f"{BUILDING_ID}_{area}_s{profile.floor:02d}",
            voltage=voltage, current=current, power_factor=pf,
            temperature_c=temp, humidity_pct=hum, quality=quality,
            device_count=profile.devices, floor=profile.floor,
            sequence=self._seq[area],
            relay_state=state.relay_states.get(area, RelayState.ENCENDIDO).value,
            tags=tags,
        )

# ──────────────────────────────────────────────
# WebSockets and Broadcast Queue
# ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.remove(connection)

manager = ConnectionManager()
broadcast_queue = asyncio.Queue()

async def broadcast_worker():
    while True:
        msg = await broadcast_queue.get()
        await manager.broadcast(msg)
        broadcast_queue.task_done()

# ──────────────────────────────────────────────
# MQTT Command Handler (Bidirectional)
# ──────────────────────────────────────────────
_mqtt_client_ref: Optional[mqtt.Client] = None

def _on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        log.info("✅  MQTT connected — subscribing to control topics")
        client.subscribe(f"{TOPIC_PREFIX}/+/comando", qos=QOS)
        client.subscribe(f"{TOPIC_PREFIX}/system/comando", qos=QOS)
    else:
        log.error("❌  MQTT connection failed: %s", reason_code)

def _on_mqtt_message(client, userdata, msg):
    """Process incoming control commands."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        topic = msg.topic
        parts = topic.split("/")
        area = parts[1] if len(parts) >= 3 and parts[1] != "system" else None
        accion = payload.get("accion", "").lower()
        motivo = payload.get("motivo", "comando_externo")
        origen = payload.get("origen", "n8n")
        
        log.info("📨  Command: %s on %s from %s", accion, area or "system", origen)
        
        if accion in ("cortar_energia", "corte_emergencia", "apagar"):
            targets = [area] if area and area in AREAS else list(AREAS.keys())
            for a in targets:
                state.relay_states[a] = RelayState.APAGADO
                state.relay_reasons[a] = motivo
                state.relay_changed_by[a] = origen
            # ACK
            ack = {"area": area or "system", "relay_state": "APAGADO", "motivo": motivo, "ts": datetime.now(timezone.utc).isoformat()}
            client.publish(f"{TOPIC_PREFIX}/system/relay_ack", json.dumps(ack), qos=QOS)
            
        elif accion in ("restaurar_energia", "encender", "restablecer"):
            targets = [area] if area and area in AREAS else list(AREAS.keys())
            for a in targets:
                state.relay_states[a] = RelayState.ENCENDIDO
                state.relay_reasons[a] = motivo
                state.relay_changed_by[a] = origen
            ack = {"area": area or "system", "relay_state": "ENCENDIDO", "motivo": motivo, "ts": datetime.now(timezone.utc).isoformat()}
            client.publish(f"{TOPIC_PREFIX}/system/relay_ack", json.dumps(ack), qos=QOS)
            
    except Exception as e:
        log.error("Error processing MQTT command: %s", e)


# ──────────────────────────────────────────────
# Background Simulation Thread
# ──────────────────────────────────────────────
def simulation_loop(loop: asyncio.AbstractEventLoop):
    global _mqtt_client_ref
    client = mqtt.Client(
        client_id=f"sensor_sim_web_{random.randint(1000,9999)}",
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)
    
    # Bidirectional MQTT callbacks
    client.on_connect = _on_mqtt_connect
    client.on_message = _on_mqtt_message
    
    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
        mqtt_connected = True
        _mqtt_client_ref = client
    except Exception as e:
        log.error(f"Cannot reach broker: {e}. Running simulation locally anyway...")
        mqtt_connected = False

    sim = SensorSimulator()

    while state.running:
        iterations = 10 if SimMode.FLOOD in state.area_modes.values() else 1
        for _ in range(iterations):
            total_kwh = 0.0
            published = 0

            for area, profile in AREAS.items():
                r = sim.get_reading(area, profile)
                if not r:
                    continue

                topic = f"{TOPIC_PREFIX}/{area}/consumo"
                payload_dict = r.to_dict()
                payload = json.dumps(payload_dict)

                if mqtt_connected:
                    client.publish(topic, payload, qos=QOS)

                total_kwh += r.kwh
                published += 1

                mode = state.area_modes.get(area, SimMode.NORMAL)
                log_line = f"[{mode.value}] {area} {r.kwh:.2f} kWh | V:{r.voltage:.1f} I:{r.current:.2f}A Q:{r.quality}"
                log.info(log_line)
                
                # Send to WebSockets
                asyncio.run_coroutine_threadsafe(
                    broadcast_queue.put({
                        "type": "reading",
                        "data": payload_dict,
                        "log": log_line
                    }), 
                    loop
                )

            summary_data = {
                "building_id": BUILDING_ID,
                "total_kwh": round(total_kwh, 4),
                "areas_reporting": published,
                "areas_total": len(AREAS),
                "mode": "mixed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if mqtt_connected:
                client.publish(f"{TOPIC_PREFIX}/summary", json.dumps(summary_data), qos=QOS)
            
            asyncio.run_coroutine_threadsafe(
                broadcast_queue.put({
                    "type": "summary",
                    "data": summary_data
                }), 
                loop
            )

        time.sleep(state.interval_sec)

    if mqtt_connected:
        client.loop_stop()
        client.disconnect()


# ──────────────────────────────────────────────
# FastAPI App
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run DB migrations (creates missing tables on every startup)
    log.info("🔄  Running database migrations...")
    if _run_migrations():
        log.info("✅  Database schema up to date")
    else:
        log.error("❌  Database migration failed — some features may not work")

    # Startup logic
    asyncio.create_task(broadcast_worker())
    
    loop = asyncio.get_running_loop()
    thread = threading.Thread(target=simulation_loop, args=(loop,), daemon=True)
    thread.start()
    
    yield
    
    # Shutdown logic
    state.running = False

app = FastAPI(title="Energy Monitor Dashboard Pro Web", lifespan=lifespan)

@app.get("/")
def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(index_path)

@app.get("/api/config")
def get_config():
    return {
        "area_modes": {a: m.value for a, m in state.area_modes.items()},
        "interval_sec": state.interval_sec,
        "areas": list(AREAS.keys()),
        "modes": [m.value for m in SimMode]
    }

class ConfigUpdate(BaseModel):
    area_modes: Optional[Dict[str, str]] = None
    interval_sec: Optional[float] = None

@app.post("/api/config")
def update_config(config: ConfigUpdate):
    if config.area_modes is not None:
        for a, m in config.area_modes.items():
            if a in state.area_modes or a == "all":
                if a == "all":
                    for k in state.area_modes:
                        state.area_modes[k] = SimMode(m)
                else:
                    state.area_modes[a] = SimMode(m)
    if config.interval_sec is not None:
        state.interval_sec = max(1.0, min(config.interval_sec, 60.0))
    return {"status": "ok", "current": get_config()}


# ──────────────────────────────────────────────
# Relay Control API
# ──────────────────────────────────────────────
class RelayCommand(BaseModel):
    area: str
    accion: str             # "cortar_energia" | "restaurar_energia"
    motivo: str = ""
    origen: str = "dashboard"

@app.get("/api/relays")
def get_relay_states():
    """Get current state of all virtual relays."""
    return {
        area: {
            "estado": state.relay_states[area].value,
            "motivo": state.relay_reasons.get(area, ""),
            "cambiado_por": state.relay_changed_by.get(area, "sistema"),
        }
        for area in AREAS
    }

@app.post("/api/relays")
def control_relay(cmd: RelayCommand):
    """Control a virtual relay via REST API (also publishes MQTT command)."""
    if cmd.area != "all" and cmd.area not in AREAS:
        raise HTTPException(status_code=404, detail=f"Area '{cmd.area}' not found")
    
    targets = list(AREAS.keys()) if cmd.area == "all" else [cmd.area]
    new_state = RelayState.APAGADO if cmd.accion in ("cortar_energia", "apagar") else RelayState.ENCENDIDO
    
    for a in targets:
        state.relay_states[a] = new_state
        state.relay_reasons[a] = cmd.motivo
        state.relay_changed_by[a] = cmd.origen
    
    # Also publish via MQTT so the standalone simulator picks it up
    if _mqtt_client_ref:
        mqtt_payload = json.dumps({
            "accion": cmd.accion,
            "motivo": cmd.motivo,
            "origen": cmd.origen,
        })
        for a in targets:
            _mqtt_client_ref.publish(f"{TOPIC_PREFIX}/{a}/comando", mqtt_payload, qos=QOS)
    
    return {"status": "ok", "affected": targets, "new_state": new_state.value}


# ──────────────────────────────────────────────
# Agent Status API  (reads from PostgreSQL — n8n agents)
# ──────────────────────────────────────────────
AGENT_NAMES = ["orchestrator", "diagnosis", "correlation", "maintenance", "resolution", "reports"]

@app.get("/api/agents")
def get_agent_status():
    """Get live status and stats for all n8n-based agents from PostgreSQL."""
    stats: Dict[str, dict] = {
        name: {"decisions": 0, "last_active": None, "status": "idle"}
        for name in AGENT_NAMES
    }
    try:
        conn = _get_pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT agent_name,
                   COUNT(*)                      AS decisions,
                   MAX(timestamp)                 AS last_active
            FROM agent_decisions
            GROUP BY agent_name
        """)
        for row in cur.fetchall():
            name = row["agent_name"]
            if name in stats:
                stats[name]["decisions"] = row["decisions"]
                la = row["last_active"]
                stats[name]["last_active"] = la.isoformat() if la else None
                # Consider "active" if last decision < 5 min ago
                if la and (datetime.now(timezone.utc) - la).total_seconds() < 300:
                    stats[name]["status"] = "active"
        cur.close()
        conn.close()
    except Exception as exc:
        log.warning("Could not query agent_decisions: %s", exc)
    return stats

@app.post("/api/agents/{agent_name}/trigger")
def trigger_agent(agent_name: str):
    """Manually trigger an n8n agent via its webhook (for testing/demo)."""
    if agent_name not in AGENT_NAMES:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    import urllib.request, urllib.error
    n8n_url = os.getenv("N8N_URL", "http://n8n:5678")
    url = f"{n8n_url}/webhook/agent-{agent_name}"
    payload = json.dumps({
        "area": "laboratorio_computo",
        "kwh": 0,
        "ema": 0,
        "severidad": "Normal",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modo": "manual_trigger",
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        log.warning("Agent trigger failed: %s", exc)
    return {"status": "triggered", "agent": agent_name}


# ──────────────────────────────────────────────
# Feedback Loop API  (persists to PostgreSQL)
# ──────────────────────────────────────────────
class FeedbackInput(BaseModel):
    anomalia_id: Optional[int] = None
    incidente_id: Optional[int] = None
    usuario: str = "operador"
    tipo: str              # "resuelto" | "falso_positivo" | "correcto" | "incorrecto"
    comentario: str = ""

@app.post("/api/feedback")
def submit_feedback(fb: FeedbackInput):
    """Submit operator feedback for an anomaly/incident."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "anomalia_id": fb.anomalia_id,
        "incidente_id": fb.incidente_id,
        "usuario": fb.usuario,
        "tipo": fb.tipo,
        "comentario": fb.comentario,
    }
    # Persist to PostgreSQL
    try:
        conn = _get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO feedback (anomalia_id, incidente_id, usuario, tipo, comentario)
            VALUES (%s, %s, %s, %s, %s)
        """, (fb.anomalia_id, fb.incidente_id, fb.usuario, fb.tipo, fb.comentario))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        log.warning("Could not persist feedback: %s", exc)
    # Also keep in-memory for quick access
    state.feedback_log.append(entry)
    log.info("📝  Feedback received: %s for anomalia=%s", fb.tipo, fb.anomalia_id)
    return {"status": "ok", "feedback": entry}

@app.get("/api/feedback")
def get_feedback():
    """Get recent feedback entries from PostgreSQL."""
    try:
        conn = _get_pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM feedback ORDER BY timestamp DESC LIMIT 50")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Could not query feedback: %s", exc)
        return state.feedback_log


# ──────────────────────────────────────────────
# Incidents & Maintenance API  (n8n agent data)
# ──────────────────────────────────────────────
@app.get("/api/incidents")
def get_incidents():
    """Get active and recent incidents managed by the resolution agent."""
    try:
        conn = _get_pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM incidentes
            ORDER BY inicio DESC LIMIT 20
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Could not query incidentes: %s", exc)
        return []

@app.get("/api/maintenance")
def get_maintenance():
    """Get pending maintenance recommendations from the maintenance agent."""
    try:
        conn = _get_pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM mantenimiento_preventivo
            ORDER BY timestamp DESC LIMIT 20
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Could not query mantenimiento_preventivo: %s", exc)
        return []

@app.get("/api/correlations")
def get_correlations():
    """Get recent cross-area correlation events."""
    try:
        conn = _get_pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM correlaciones
            ORDER BY timestamp DESC LIMIT 20
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Could not query correlaciones: %s", exc)
        return []


# ──────────────────────────────────────────────
# MQTT Publish API (for n8n/external systems)
# ──────────────────────────────────────────────
class MqttPublishRequest(BaseModel):
    topic: str
    payload: dict

@app.post("/api/mqtt/publish")
def mqtt_publish(req: MqttPublishRequest):
    """Publish a message to MQTT via REST API (bridge for n8n)."""
    if not _mqtt_client_ref:
        raise HTTPException(status_code=503, detail="MQTT not connected")
    _mqtt_client_ref.publish(req.topic, json.dumps(req.payload), qos=QOS)
    return {"status": "published", "topic": req.topic}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
            # Just keep connection open to push data
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
