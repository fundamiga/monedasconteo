"""
nomina_supabase.py — Integración con el Sistema de Nómina (Supabase)
===================================================================
Conecta con la base de datos de Supabase de Fundamiga para obtener
las liquidaciones de nómina, salarios por turno, ARL y horas extras,
y cruzarlas contra el recaudo de los parqueaderos.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime

SUPABASE_URL = "https://upgrsqatxeokoagcwbks.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVwZ3JzcWF0eGVva29hZ2N3YmtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ3NTM0NzUsImV4cCI6MjA5MDMyOTQ3NX0.b87zEqrr-dznnsOwX58mKHlVcgLjYEJkTTJwaf5-KCQ"

CACHE_FILE = os.path.join(os.path.expanduser("~"), ".conteo_cc358_nomina_cache.json")

MAPEO_CARGOS = {
    "5 - 6": "5 CON 6",
    "5 CON 6": "5 CON 6",
    "6 - 6": "6 CON 6",
    "6 CON 6": "6 CON 6",
    "CARTON C": "CARTON",
    "CARTON": "CARTON",
    "GUACANDA": "GUACANDA",
    "TERCERA": "GALERIA",
    "GALERIA": "GALERIA",
    "ROZO": "ROZO",
    "2 - 10": "2 CON 10",
    "2 CON 10": "2 CON 10",
    "MAYORISTA": "MAYORISTA",
    "GUABINAS": "GUABINAS",
    "BOLIVAR": "BOLIVAR",
    "CONTRATISTAS DE ADMINISTRACION": "ADMINISTRACION",
    "ADMINISTRACION": "ADMINISTRACION",
    "REMESAS": "REMESAS",
    "OPERARIO REMESAS": "REMESAS",
}

MESES_NOMBRES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def mapear_cargo_parqueadero(cargo_raw):
    """Normaliza el nombre del cargo al parqueadero estándar."""
    if not cargo_raw:
        return "OTRO"
    c = str(cargo_raw).strip().upper()
    return MAPEO_CARGOS.get(c, c)


def sincronizar_liquidaciones_supabase():
    """
    Descarga el historial completo de liquidaciones desde Supabase
    y lo almacena en la caché local para acceso ultra rápido y offline.
    Retorna (cantidad_descargada, mensaje_error_o_None).
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/historial_liquidaciones?select=*"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return len(data), None
    except Exception as e:
        return 0, str(e)


def cargar_cache_liquidaciones():
    """Carga las liquidaciones desde el archivo caché local."""
    if not os.path.exists(CACHE_FILE):
        count, err = sincronizar_liquidaciones_supabase()
        if err or count == 0:
            return []

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def obtener_resumen_nomina(mes=None, anio=2026, quincena="todos"):
    """
    Agrupa los costos de nómina por parqueadero según el mes y período consultado.
    Permite:
    - quincena='1ra'   -> Solo 1ra Quincena
    - quincena='2da'   -> Solo 2da Quincena
    - quincena='todos' -> Mes Completo (Suma 1ra Quincena + 2da Quincena)

    Retorna un diccionario estructurado con:
      - por_parqueadero: {
          '5 CON 6': {'q1': float, 'q2': float, 'total': float, 'personas': int, 'arl': float}, ...
        }
      - gastos_admin: {'q1': float, 'q2': float, 'total': float}
      - gastos_remesas: {'q1': float, 'q2': float, 'total': float}
      - total_general: {'q1': float, 'q2': float, 'total': float, 'total_personas': int}
      - quincenas_encontradas: lista de etiquetas de quincenas encontradas
    """
    liquidaciones = cargar_cache_liquidaciones()
    nom_mes = MESES_NOMBRES.get(mes, "").lower() if mes else ""

    por_parq = {}
    admin_q = {"q1": 0, "q2": 0, "total": 0}
    remesas_q = {"q1": 0, "q2": 0, "total": 0}
    tot_general = {"q1": 0, "q2": 0, "total": 0, "total_personas": 0}
    quincenas_vistas = set()

    for r in liquidaciones:
        q_txt = str(r.get("quincena") or "").lower()

        # Filtro de año
        if anio is not None and str(anio) not in q_txt:
            continue

        # Filtro de mes
        if nom_mes and nom_mes not in q_txt:
            continue

        # Identificar si es 1ra o 2da quincena
        es_q1 = "1ra" in q_txt or "primera" in q_txt
        es_q2 = "2da" in q_txt or "segunda" in q_txt

        # Filtro de quincena según solicitud
        if quincena == "1ra" and not es_q1:
            continue
        elif quincena == "2da" and not es_q2:
            continue

        quincenas_vistas.add(r.get("quincena") or "Sin quincena")

        p = r.get("persona") or {}
        cargo_raw = p.get("cargo", "")
        parq = mapear_cargo_parqueadero(cargo_raw)

        res = r.get("resultado") or {}
        neto = int(res.get("neto", 0) or 0)
        arl = int(res.get("descuentoSeguridad", 0) or 0)

        # Distribuir en Q1 o Q2
        def _sumar_a_dict(d, valor, q1_flag):
            if q1_flag:
                d["q1"] += valor
            else:
                d["q2"] += valor
            d["total"] += valor

        if parq == "ADMINISTRACION":
            _sumar_a_dict(admin_q, neto, es_q1)
        elif parq == "REMESAS":
            _sumar_a_dict(remesas_q, neto, es_q1)
        else:
            if parq not in por_parq:
                por_parq[parq] = {"q1": 0, "q2": 0, "total": 0, "arl": 0, "personas": 0}
            _sumar_a_dict(por_parq[parq], neto, es_q1)
            por_parq[parq]["arl"] += arl
            por_parq[parq]["personas"] += 1

        _sumar_a_dict(tot_general, neto, es_q1)
        tot_general["total_personas"] += 1

    return {
        "por_parqueadero": por_parq,
        "gastos_admin": admin_q,
        "gastos_remesas": remesas_q,
        "total_general": tot_general,
        "quincenas_encontradas": sorted(list(quincenas_vistas))
    }
