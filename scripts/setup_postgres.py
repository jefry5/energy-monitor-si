
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    """Conecta a Postgres y ejecuta el script de inicializacion SQL."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "energy_db"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        conn.autocommit = True
        cur = conn.cursor()

        print("🐘 Conectado a PostgreSQL...")
        
        # Leer el archivo SQL
        sql_path = os.path.join(os.path.dirname(__file__), "init_postgres.sql")
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        # Ejecutar el script
        print("🛠️ Creando tablas e indices...")
        cur.execute(sql_script)
        
        print("✅ Base de datos PostgreSQL configurada correctamente.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error al configurar Postgres: {e}")

if __name__ == "__main__":
    setup_database()
