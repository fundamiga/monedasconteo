"""
historial_db.py — Base de datos local de respaldo para todos los conteos
========================================================================
Guarda una copia permanente de cada turno registrado (monedas, billetes,
trabajador, parqueadero, fecha y hora exacta).

Se almacena en el perfil del usuario (~/.conteo_cc358_historial.db),
por lo que persiste para siempre, incluso si se actualiza o reinstala el .exe.
"""

import os
import json
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.expanduser("~"), ".conteo_cc358_historial.db")


def _conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea la tabla de historial si no existe."""
    with _conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conteos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                fecha_turno TEXT NOT NULL,
                parqueadero TEXT NOT NULL,
                trabajador TEXT NOT NULL,
                hoja_tipo TEXT NOT NULL DEFAULT 'principal',
                monedas_json TEXT NOT NULL,
                billetes_json TEXT NOT NULL,
                total_monedas INTEGER NOT NULL DEFAULT 0,
                total_billetes INTEGER NOT NULL DEFAULT 0,
                total_turno INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trabajador ON conteos(trabajador)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fecha_turno ON conteos(fecha_turno)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON conteos(timestamp)")


def guardar_historial(fecha_turno, parqueadero, trabajador, monedas, billetes, hoja_tipo="principal"):
    """Guarda un conteo en la base de datos local permanente."""
    try:
        init_db()

        # Calcular totales
        valores_monedas = {
            "1000": 1000, "500": 500, "200a": 200, "200b": 200,
            "100a": 100, "100b": 100, "50a": 50, "50b": 50
        }
        valores_billetes = {
            "2000": 2000, "5000": 5000, "10000": 10000,
            "20000": 20000, "50000": 50000, "100000": 100000
        }

        tm = sum(int(monedas.get(k, 0) or 0) * v for k, v in valores_monedas.items())
        tb = sum(int(billetes.get(k, 0) or 0) * v for k, v in valores_billetes.items())
        tt = tm + tb

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with _conectar() as conn:
            conn.execute("""
                INSERT INTO conteos (
                    timestamp, fecha_turno, parqueadero, trabajador,
                    hoja_tipo, monedas_json, billetes_json,
                    total_monedas, total_billetes, total_turno
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                str(fecha_turno).strip(),
                str(parqueadero).strip(),
                str(trabajador).strip().upper(),
                str(hoja_tipo).lower(),
                json.dumps(monedas or {}),
                json.dumps(billetes or {}),
                tm, tb, tt
            ))
        return True
    except Exception as e:
        print(f"Error guardando en historial local: {e}")
        return False


def consultar_historial(filtro_trabajador="", filtro_fecha="", filtro_parqueadero="", limite=150):
    """Retorna los registros del historial ordenados del más reciente al más antiguo."""
    init_db()
    query = "SELECT * FROM conteos WHERE 1=1"
    params = []

    if filtro_trabajador.strip():
        query += " AND trabajador LIKE ?"
        params.append(f"%{filtro_trabajador.strip().upper()}%")

    if filtro_fecha.strip():
        query += " AND (fecha_turno LIKE ? OR timestamp LIKE ?)"
        params.append(f"%{filtro_fecha.strip()}%")
        params.append(f"%{filtro_fecha.strip()}%")

    if filtro_parqueadero.strip() and filtro_parqueadero != "TODOS":
        query += " AND parqueadero LIKE ?"
        params.append(f"%{filtro_parqueadero.strip()}%")

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limite)

    with _conectar() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def exportar_csv(ruta_archivo, filtro_trabajador="", filtro_fecha=""):
    """Exporta los registros del historial a un archivo CSV."""
    import csv
    registros = consultar_historial(filtro_trabajador, filtro_fecha, limite=10000)
    with open(ruta_archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID", "Fecha/Hora Registro", "Fecha Turno", "Parqueadero",
            "Trabajador", "Hoja", "Total Monedas", "Total Billetes", "Total Turno",
            "Monedas ($1000,$500,$200,$100,$50)", "Billetes"
        ])
        for r in registros:
            writer.writerow([
                r["id"], r["timestamp"], r["fecha_turno"], r["parqueadero"],
                r["trabajador"], r["hoja_tipo"], r["total_monedas"],
                r["total_billetes"], r["total_turno"],
                r["monedas_json"], r["billetes_json"]
            ])
    return len(registros)
