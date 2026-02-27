import json
import logging
import math
import os
import random
import sys
import time
import asyncio
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Final, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel
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
        # Default to a faster interval for web demo purposes (e.g., 2 seconds)
        self.interval_sec: float = float(os.getenv("SIM_INTERVAL", "2.0"))
        self.running: bool = True

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
            sequence=self._seq[area], tags=tags,
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
# Background Simulation Thread
# ──────────────────────────────────────────────
def simulation_loop(loop: asyncio.AbstractEventLoop):
    client = mqtt.Client(
        client_id=f"sensor_sim_web_{random.randint(1000,9999)}",
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)
    
    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
        mqtt_connected = True
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
app = FastAPI(title="Energy Monitor Dashboard Pro Web")

@app.on_event("startup")
async def startup_event():
    # Start the broadcast worker
    asyncio.create_task(broadcast_worker())
    
    # Start the simulation thread
    loop = asyncio.get_running_loop()
    thread = threading.Thread(target=simulation_loop, args=(loop,), daemon=True)
    thread.start()

@app.on_event("shutdown")
def shutdown_event():
    state.running = False

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
    # run inside scripts: uvicorn main:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
