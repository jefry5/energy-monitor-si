"""
Energy Monitor Simulator Pro v2
================================
Advanced MQTT sensor simulator with realistic patterns, multiple failure modes,
gradual anomalies, seasonal profiles, and structured logging.
"""

import json
import logging
import math
import os
import random
import signal
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Final, List, Optional

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("simulator.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("EnergySimPro")


# ──────────────────────────────────────────────
# Enums & Config
# ──────────────────────────────────────────────
class SimMode(str, Enum):
    NORMAL          = "normal"
    ANOMALY         = "anomaly"
    SENSOR_FAILURE  = "sensor_failure"
    GRADUAL_DRIFT   = "gradual_drift"    # consumo sube lentamente (falla mecánica)
    INTERMITTENT    = "intermittent"     # lecturas que aparecen y desaparecen
    FLOOD           = "flood"            # ráfaga de mensajes (test de carga)
    NIGHT_ANOMALY   = "night_anomaly"    # pico solo en horario nocturno


class Severity(str, Enum):
    NORMAL      = "Normal"
    WARNING     = "Warning"
    CRITICAL    = "Critical"


# ──────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────
@dataclass
class AreaProfile:
    base: float                 # kWh diurno base
    nocturno: float             # kWh nocturno base
    std_pct: float = 0.10       # variabilidad estándar (±%)
    peak_hour: int = 10         # hora de mayor consumo
    peak_factor: float = 1.20   # multiplicador en hora pico
    devices: int = 1            # cantidad de dispositivos simulados
    floor: int = 1              # piso (metadata)


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
    quality: str                # "ok" | "degraded" | "failed"
    device_count: int
    floor: int
    sequence: int               # número de lectura para detectar gaps
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────
# Area Profiles — ampliados con metadata real
# ──────────────────────────────────────────────
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
# Environment
# ──────────────────────────────────────────────
BROKER:        Final[str]      = os.getenv("MQTT_BROKER", "localhost")
PORT:          Final[int]      = int(os.getenv("MQTT_PORT", "1883"))
USERNAME:      Final[str]      = os.getenv("MQTT_USER", "")
PASSWORD:      Final[str]      = os.getenv("MQTT_PASS", "")
MODE:          Final[SimMode]  = SimMode(os.getenv("SIM_MODE", "normal"))
ANOMALY_AREA:  Final[str]      = os.getenv("ANOMALY_AREA", "auditorio")
INTERVAL_SEC:  Final[float]    = float(os.getenv("SIM_INTERVAL", "30"))
QOS:           Final[int]      = int(os.getenv("MQTT_QOS", "1"))   # 0 | 1 | 2
TOPIC_PREFIX:  Final[str]      = os.getenv("TOPIC_PREFIX", "edificio")
BUILDING_ID:   Final[str]      = os.getenv("BUILDING_ID", "edificio_principal")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _gaussian_noise(mean: float, std_pct: float) -> float:
    """Returns mean * gaussian_factor (more realistic than uniform)."""
    factor = random.gauss(1.0, std_pct)
    return max(0.01, mean * factor)


def _seasonal_factor() -> float:
    """Slight seasonal adjustment based on month (Peru climate)."""
    month = datetime.now().month
    # Verano (Dec-Mar) +5%, Invierno (Jun-Sep) -3%
    seasonal = {12: 1.05, 1: 1.05, 2: 1.04, 3: 1.02,
                4: 1.00, 5: 0.99, 6: 0.97, 7: 0.96,
                8: 0.97, 9: 0.98, 10: 1.00, 11: 1.02}
    return seasonal.get(month, 1.0)


def _hourly_factor(profile: AreaProfile) -> float:
    """Smooth sinusoidal curve peaking at profile.peak_hour."""
    hour = datetime.now().hour + datetime.now().minute / 60.0
    # Gaussian bell centered at peak_hour, width ~3h
    distance = abs(hour - profile.peak_hour)
    if distance > 12:
        distance = 24 - distance
    bell = math.exp(-0.5 * (distance / 3.0) ** 2)
    return 1.0 + (profile.peak_factor - 1.0) * bell


def _is_night() -> bool:
    h = datetime.now().hour
    return h < 6 or h >= 22


def _simulate_env() -> tuple[float, float]:
    """Returns (temperature_c, humidity_pct) with realistic daily cycle."""
    hour = datetime.now().hour
    # Temperatura: 18°C nocturno → 28°C mediodía
    temp = 18 + 10 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 0.5)
    temp = round(max(15.0, min(35.0, temp)), 1)
    # Humedad: 40% mediodía → 75% nocturno
    hum = 75 - 35 * math.sin(math.pi * (hour - 6) / 12) + random.gauss(0, 1.5)
    hum = round(max(20.0, min(95.0, hum)), 1)
    return temp, hum


def _simulate_electrical(kwh: float) -> tuple[float, float, float]:
    """Returns (voltage_v, current_a, power_factor) from kWh."""
    voltage = round(random.gauss(220.0, 2.0), 1)
    pf = round(random.uniform(0.85, 0.98), 3)
    # P = V * I * PF  →  I = P / (V * PF)  (kWh como proxy de kW instantáneo)
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
        """Returns baseline kWh with time-of-day + seasonal factors."""
        base = profile.nocturno if _is_night() else profile.base
        return base * _hourly_factor(profile) * _seasonal_factor()

    def get_reading(self, area: str, profile: AreaProfile) -> Optional[SensorReading]:
        self._seq[area] += 1
        now_utc = datetime.now(timezone.utc).isoformat()
        temp, hum = _simulate_env()
        tags: List[str] = []

        # ── Mode: sensor failure ────────────────
        if MODE == SimMode.SENSOR_FAILURE and area == ANOMALY_AREA:
            log.warning("[SENSOR_FAILURE] Dropping reading for %s", area)
            return None

        # ── Mode: intermittent ──────────────────
        if MODE == SimMode.INTERMITTENT and area == ANOMALY_AREA:
            skip = self._intermittent_skip.get(area, False)
            self._intermittent_skip[area] = not skip
            if skip:
                log.warning("[INTERMITTENT] Skipping reading for %s", area)
                return None
            tags.append("intermittent_recovery")

        base = self._base_kwh(area, profile)

        # ── Mode: gradual drift ─────────────────
        if MODE == SimMode.GRADUAL_DRIFT and area == ANOMALY_AREA:
            self._drift[area] = min(self._drift[area] + 0.02, 3.0)
            kwh = round(_gaussian_noise(base * self._drift[area], profile.std_pct), 4)
            tags.append(f"drift_factor:{self._drift[area]:.2f}")
            quality = "degraded" if self._drift[area] > 1.5 else "ok"

        # ── Mode: anomaly (spike) ───────────────
        elif MODE == SimMode.ANOMALY and area == ANOMALY_AREA:
            kwh = round(_gaussian_noise(base * 2.8, 0.05), 4)
            tags.append("spike_anomaly")
            quality = "degraded"

        # ── Mode: night anomaly ─────────────────
        elif MODE == SimMode.NIGHT_ANOMALY and area == ANOMALY_AREA and _is_night():
            kwh = round(_gaussian_noise(base * 3.5, 0.05), 4)
            tags.append("night_spike")
            quality = "degraded"

        # ── Normal reading ──────────────────────
        else:
            kwh = round(_gaussian_noise(base, profile.std_pct), 4)
            quality = "ok"

        voltage, current, pf = _simulate_electrical(kwh)

        return SensorReading(
            area=area,
            kwh=kwh,
            timestamp=now_utc,
            modo=MODE.value,
            sensor_id=f"{BUILDING_ID}_{area}_s{profile.floor:02d}",
            voltage=voltage,
            current=current,
            power_factor=pf,
            temperature_c=temp,
            humidity_pct=hum,
            quality=quality,
            device_count=profile.devices,
            floor=profile.floor,
            sequence=self._seq[area],
            tags=tags,
        )


# ──────────────────────────────────────────────
# MQTT callbacks
# ──────────────────────────────────────────────
def _on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        log.info("✅  Connected to MQTT broker %s:%s", BROKER, PORT)
        # Publish a "system online" event
        client.publish(
            f"{TOPIC_PREFIX}/system/status",
            json.dumps({"status": "online", "building": BUILDING_ID,
                        "mode": MODE.value, "ts": datetime.now(timezone.utc).isoformat()}),
            qos=QOS,
            retain=True,
        )
    else:
        log.error("❌  Connection failed with code %s", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        log.warning("⚠️  Unexpected disconnect (code=%s). Will retry…", reason_code)


def _on_publish(client, userdata, mid, reason_code, properties):
    pass  # Silence ACK noise; remove `pass` and add log.debug if needed


# ──────────────────────────────────────────────
# Publisher
# ──────────────────────────────────────────────
def publish_batch(client: mqtt.Client, sim: SensorSimulator) -> None:
    """Publishes one reading per area. In FLOOD mode, sends 10x."""
    iterations = 10 if MODE == SimMode.FLOOD else 1

    for _ in range(iterations):
        total_kwh = 0.0
        published = 0

        for area, profile in AREAS.items():
            reading = sim.get_reading(area, profile)
            if reading is None:
                continue

            topic = f"{TOPIC_PREFIX}/{area}/consumo"
            payload = json.dumps(reading.to_dict())

            result = client.publish(topic, payload, qos=QOS)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                log.error("Publish error on %s: %s", topic, result.rc)
                continue

            total_kwh += reading.kwh
            published += 1
            log.info("[%s] %-25s %.4f kWh  |  V:%.1f  I:%.2fA  PF:%.3f  Q:%s",
                     MODE.value, area, reading.kwh,
                     reading.voltage, reading.current,
                     reading.power_factor, reading.quality)

        # Summary message per batch
        summary = {
            "building_id": BUILDING_ID,
            "total_kwh": round(total_kwh, 4),
            "areas_reporting": published,
            "areas_total": len(AREAS),
            "mode": MODE.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client.publish(f"{TOPIC_PREFIX}/summary", json.dumps(summary), qos=QOS)
        log.info("📊  Batch summary — Total: %.4f kWh | %d/%d areas",
                 total_kwh, published, len(AREAS))


# ──────────────────────────────────────────────
# Graceful shutdown
# ──────────────────────────────────────────────
_running = True

def _handle_signal(sig, frame):
    global _running
    log.info("🛑  Signal %s received. Shutting down…", sig)
    _running = False


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main() -> None:
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log.info("=" * 60)
    log.info("  Energy Monitor Simulator Pro v2")
    log.info("  Building : %s", BUILDING_ID)
    log.info("  Mode     : %s", MODE.value)
    log.info("  Broker   : %s:%s  (QoS=%s)", BROKER, PORT, QOS)
    log.info("  Areas    : %d", len(AREAS))
    log.info("  Interval : %ss", INTERVAL_SEC)
    log.info("=" * 60)

    client = mqtt.Client(
        client_id=f"sensor_sim_{BUILDING_ID}",
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    # Last Will Testament: marca el sistema como offline si cae sin avisar
    client.will_set(
        f"{TOPIC_PREFIX}/system/status",
        json.dumps({"status": "offline", "building": BUILDING_ID,
                    "ts": datetime.now(timezone.utc).isoformat()}),
        qos=1,
        retain=True,
    )

    client.on_connect    = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_publish    = _on_publish

    # Retry connection loop
    while _running:
        try:
            client.connect(BROKER, PORT, keepalive=60)
            break
        except (ConnectionRefusedError, OSError) as e:
            log.error("Cannot reach broker (%s). Retrying in 10s…", e)
            time.sleep(10)

    client.loop_start()
    sim = SensorSimulator()
    cycle = 0

    try:
        while _running:
            cycle += 1
            log.info("── Cycle #%d ─────────────────────────────", cycle)
            publish_batch(client, sim)
            time.sleep(INTERVAL_SEC)
    finally:
        client.publish(
            f"{TOPIC_PREFIX}/system/status",
            json.dumps({"status": "offline", "building": BUILDING_ID,
                        "ts": datetime.now(timezone.utc).isoformat()}),
            qos=1, retain=True,
        )
        client.loop_stop()
        client.disconnect()
        log.info("✅  Simulator stopped cleanly after %d cycles.", cycle)


if __name__ == "__main__":
    main()