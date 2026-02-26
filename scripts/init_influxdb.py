import math
import os
import random
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Dict, Final

from dotenv import load_dotenv
from influxdb_client import InfluxDBClient
from influxdb_client import Point
from influxdb_client import WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()

# Configuration constants
INFLUX_URL: Final[str] = os.getenv('INFLUXDB_URL', 'http://localhost:8086')
INFLUX_TOKEN: Final[str] = os.getenv('INFLUXDB_TOKEN', 'mi-token-super-secreto-123')
INFLUX_ORG: Final[str] = os.getenv('INFLUXDB_ORG', 'universidad')
INFLUX_BUCKET: Final[str] = os.getenv('INFLUXDB_BUCKET', 'energia')

# Building area configurations (calibrated with Building Data Genome Project 2)
AREAS: Final[Dict[str, Dict[str, float]]] = {
    'laboratorio_computo': {'base': 8.5, 'nocturno': 1.2, 'pico': 14.0},
    'aulas_teoricas': {'base': 3.2, 'nocturno': 0.4, 'pico': 6.5},
    'biblioteca': {'base': 4.8, 'nocturno': 0.8, 'pico': 7.2},
    'cafeteria': {'base': 6.1, 'nocturno': 1.5, 'pico': 10.3},
    'oficinas_admin': {'base': 3.9, 'nocturno': 0.3, 'pico': 6.8},
    'sala_servidores': {'base': 12.0, 'nocturno': 11.5, 'pico': 14.0},
    'estacionamiento': {'base': 1.2, 'nocturno': 0.6, 'pico': 2.1},
    'auditorio': {'base': 5.5, 'nocturno': 0.2, 'pico': 18.0},
}

def get_consumption_by_hour(area_config: Dict[str, float], hour: int) -> float:
    """Calculates a realistic energy consumption profile based on time of day."""
    if 0 <= hour < 6:
        base = area_config['nocturno']
    elif 7 <= hour <= 9:
        base = area_config['base'] * (0.6 + 0.4 * (hour - 7) / 2)
    elif 10 <= hour <= 12:
        base = area_config['base']
    elif 13 <= hour <= 14:
        base = area_config['base'] * 0.85
    elif 15 <= hour <= 18:
        base = area_config['base']
    elif 19 <= hour <= 21:
        base = area_config['base'] * (0.9 - 0.15 * (hour - 19) / 2)
    else:
        base = area_config['nocturno']
        
    variation = 1 + random.uniform(-0.10, 0.10)
    return max(0.1, base * variation)

def load_historical_data(days: int = 7) -> None:
    """Populates InfluxDB with historical data for the last N days."""
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)
    total_points = 0

    print(f'Starting data population for the last {days} days...')

    current_ts = start_time
    points = []
    
    while current_ts < now:
        hour = current_ts.hour
        for area, cfg in AREAS.items():
            kwh = get_consumption_by_hour(cfg, hour)
            point = (
                Point('consumo_energetico')
                .tag('area', area)
                .tag('tipo', 'historico')
                .field('kwh', round(kwh, 4))
                .time(current_ts, WritePrecision.S)
            )
            points.append(point)
            total_points += 1
        current_ts += timedelta(minutes=30)

    try:
        print(f'Sending {total_points} points to InfluxDB in one batch...')
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
        print(f'Done! Successfully loaded historical data.')
    except Exception as e:
        print(f'❌ Error writing to InfluxDB: {e}')
    finally:
        client.close()


if __name__ == '__main__':
    load_historical_data(days=7)

