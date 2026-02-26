import os, random, math
from datetime import datetime, timedelta, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

load_dotenv()

# ── Configuración ────────────────────────────────────────────
INFLUX_URL   = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.getenv('INFLUXDB_TOKEN', 'mi-token-super-secreto-123')
INFLUX_ORG   = os.getenv('INFLUXDB_ORG',   'universidad')
INFLUX_BUCKET= os.getenv('INFLUXDB_BUCKET', 'energia')

# ── Áreas del edificio con consumo base en kWh ───────────────
# Valores calibrados con Building Data Genome Project 2
AREAS = {
    'laboratorio_computo':  {'base': 8.5,  'nocturno': 1.2, 'pico': 14.0},
    'aulas_teoricas':       {'base': 3.2,  'nocturno': 0.4, 'pico':  6.5},
    'biblioteca':           {'base': 4.8,  'nocturno': 0.8, 'pico':  7.2},
    'cafeteria':            {'base': 6.1,  'nocturno': 1.5, 'pico': 10.3},
    'oficinas_admin':       {'base': 3.9,  'nocturno': 0.3, 'pico':  6.8},
    'sala_servidores':      {'base': 12.0, 'nocturno':11.5, 'pico': 14.0},
    'estacionamiento':      {'base': 1.2,  'nocturno': 0.6, 'pico':  2.1},
    'auditorio':            {'base': 5.5,  'nocturno': 0.2, 'pico': 18.0},
}

def consumo_por_hora(area_cfg: dict, hora: int) -> float:
    '''Perfil de consumo realista por franja horaria.'''
    if 0 <= hora < 6:            # Madrugada: mínimo consumo
        base = area_cfg['nocturno']
    elif 7 <= hora <= 9:         # Inicio de jornada: rampa
        base = area_cfg['base'] * (0.6 + 0.4 * (hora - 7) / 2)
    elif 10 <= hora <= 12:       # Mañana: plena actividad
        base = area_cfg['base']
    elif 13 <= hora <= 14:       # Almuerzo: baja leve
        base = area_cfg['base'] * 0.85
    elif 15 <= hora <= 18:       # Tarde: actividad normal
        base = area_cfg['base']
    elif 19 <= hora <= 21:       # Noche: reducción gradual
        base = area_cfg['base'] * (0.9 - 0.15 * (hora - 19) / 2)
    else:                         # Noche tardía
        base = area_cfg['nocturno']
    # Añadir variabilidad del 10%
    return max(0.1, base * (1 + random.uniform(-0.10, 0.10)))

def cargar_historico(dias: int = 7):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    ahora = datetime.now(timezone.utc)
    inicio = ahora - timedelta(days=dias)
    total_puntos = 0

    print(f'Cargando {dias} días de datos históricos...')

    ts = inicio
    while ts < ahora:
        hora = ts.hour
        for area, cfg in AREAS.items():
            kwh = consumo_por_hora(cfg, hora)
            point = (
                Point('consumo_energetico')
                .tag('area', area)
                .tag('tipo', 'historico')
                .field('kwh', round(kwh, 4))
                .time(ts, WritePrecision.S)
            )
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            total_puntos += 1
        ts += timedelta(minutes=30)  # lectura cada 30 minutos en histórico

    client.close()
    print(f'✔ Cargados {total_puntos} puntos históricos en InfluxDB.')

if __name__ == '__main__':
    cargar_historico(dias=7)
