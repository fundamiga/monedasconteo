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
import unicodedata
import re
from difflib import SequenceMatcher
from datetime import datetime

SUPABASE_URL = "https://upgrsqatxeokoagcwbks.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVwZ3JzcWF0eGVva29hZ2N3YmtzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ3NTM0NzUsImV4cCI6MjA5MDMyOTQ3NX0.b87zEqrr-dznnsOwX58mKHlVcgLjYEJkTTJwaf5-KCQ"

CACHE_FILE = os.path.join(os.path.expanduser("~"), ".conteo_cc358_nomina_cache.json")
CACHE_TRABAJADORES_FILE = os.path.join(os.path.expanduser("~"), ".conteo_cc358_trabajadores_cache.json")

# Constantes financieras
VALOR_ARL_TURNO = 2540      # $76.200 / 30 días = $2.540 por turno
VALOR_TURNO_DEFECTO = 23500  # Tarifa promedio si un trabajador no está registrado


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


# ── MÓDULO ESTIMADOR EN TIEMPO REAL (DÍA A DÍA) ─────────────────────────────

def sincronizar_trabajadores_supabase():
    """
    Descarga el catálogo completo de trabajadores y sus tarifas de turno
    desde Supabase para guardarlos en la caché local.
    Retorna (cantidad_descargada, error_o_None).
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/trabajadores?select=id,nombre,cargo,valor_turno,valor_hora_adicional"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        with open(CACHE_TRABAJADORES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return len(data), None
    except Exception as e:
        return 0, str(e)


def cargar_cache_trabajadores():
    """Carga los trabajadores desde la caché local o los descarga si no existen."""
    if not os.path.exists(CACHE_TRABAJADORES_FILE):
        count, err = sincronizar_trabajadores_supabase()
        if err or count == 0:
            return []

    try:
        with open(CACHE_TRABAJADORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def limpiar_texto_nombre(s):
    """Normaliza un nombre removiendo tildes, símbolos y espacios extra."""
    if not s:
        return ""
    norm = unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore').decode('utf-8')
    norm = re.sub(r'[^A-Z0-9\s]', ' ', norm.upper())
    return " ".join(norm.split())


def _score_coincidencia(nom1, nom2):
    """Calcula similitud por tokens exactos y similitud fonética/ortográfica."""
    t1 = set(nom1.split())
    t2 = set(nom2.split())
    exact = t1 & t2
    score = len(exact) * 2.0
    for w1 in t1 - exact:
        for w2 in t2 - exact:
            if SequenceMatcher(None, w1, w2).ratio() >= 0.8:
                score += 1.5
                break
    return score


def obtener_tarifa_trabajador(nombre_maquina, cache_trabajadores=None):
    """
    Busca la tarifa de turno de un trabajador en Supabase.
    Si no se encuentra coincidencia confiable, retorna la tarifa estándar ($23.500).
    Retorna (valor_turno, nombre_encontrado_en_supabase, cargo_en_supabase).
    """
    if cache_trabajadores is None:
        cache_trabajadores = cargar_cache_trabajadores()

    if not cache_trabajadores:
        return VALOR_TURNO_DEFECTO, "TARIFA ESTÁNDAR", "OTRO"

    c_m = limpiar_texto_nombre(nombre_maquina)
    if not c_m:
        return VALOR_TURNO_DEFECTO, "DESCONOCIDO", "OTRO"

    best_w = None
    best_score = 0.0

    for w in cache_trabajadores:
        c_sb = limpiar_texto_nombre(w.get("nombre"))
        sc = _score_coincidencia(c_m, c_sb)
        if sc > best_score:
            best_score = sc
            best_w = w

    if best_score >= 2.0 and best_w:
        v_turno = int(best_w.get("valor_turno") or VALOR_TURNO_DEFECTO)
        return v_turno, best_w.get("nombre", ""), best_w.get("cargo", "")

    return VALOR_TURNO_DEFECTO, "ESTÁNDAR", "OTRO"


def calcular_estimado_tiempo_real(turnos_filtrados, incluir_arl=True):
    """
    Calcula el balance y rentabilidad en tiempo real a partir de los turnos
    registrados en la máquina y las tarifas de Supabase.
    
    Genera además proyecciones a 15 días (quincena) y 30 días (mes).
    """
    cache_trab = cargar_cache_trabajadores()
    tarifas_cache_local = {}

    dias_unicos = set()
    por_parqueadero = {}

    tot_recaudo = 0
    tot_sueldos = 0
    tot_arl = 0
    tot_costo = 0

    for r in turnos_filtrados:
        f_str = str(r.get("fecha_turno") or "").strip()
        if f_str:
            dias_unicos.add(f_str)

        p_nom = str(r.get("parqueadero") or "DESCONOCIDO").strip().upper()
        p_nom = mapear_cargo_parqueadero(p_nom)

        t_nom = str(r.get("trabajador") or "").strip().upper()
        rec_turno = int(r.get("total_turno") or 0)

        # Buscar tarifa de la persona (con memoización rápida)
        if t_nom not in tarifas_cache_local:
            tarifa, nom_sb, _ = obtener_tarifa_trabajador(t_nom, cache_trab)
            tarifas_cache_local[t_nom] = tarifa
        else:
            tarifa = tarifas_cache_local[t_nom]

        arl_turno = VALOR_ARL_TURNO if incluir_arl else 0
        costo_turno = tarifa + arl_turno

        tot_recaudo += rec_turno
        tot_sueldos += tarifa
        tot_arl += arl_turno
        tot_costo += costo_turno

        if p_nom not in por_parqueadero:
            por_parqueadero[p_nom] = {
                "parqueadero": p_nom,
                "turnos": 0,
                "recaudo": 0,
                "sueldos": 0,
                "arl": 0,
                "costo_total": 0,
                "ganancia_neta": 0,
                "margen_pct": 0.0,
                "proy_quincena_15d": 0,
                "proy_mes_30d": 0,
                "estado": "EQUILIBRIO"
            }

        item = por_parqueadero[p_nom]
        item["turnos"] += 1
        item["recaudo"] += rec_turno
        item["sueldos"] += tarifa
        item["arl"] += arl_turno
        item["costo_total"] += costo_turno

    dias_count = max(1, len(dias_unicos))

    # Calcular ganancias, márgenes y proyecciones por parqueadero
    lista_parq = []
    for item in por_parqueadero.values():
        rec = item["recaudo"]
        costo = item["costo_total"]
        gn = rec - costo
        item["ganancia_neta"] = gn
        m_pct = round((gn * 100 / rec), 1) if rec > 0 else 0.0
        item["margen_pct"] = m_pct

        # Proyección basada en el promedio diario acumulado
        gn_diaria = gn / dias_count
        item["proy_quincena_15d"] = int(round(gn_diaria * 15))
        item["proy_mes_30d"] = int(round(gn_diaria * 30))

        if gn > 0 and m_pct >= 25:
            item["estado"] = "GANANCIA"
        elif gn >= 0:
            item["estado"] = "EQUILIBRIO"
        else:
            item["estado"] = "PÉRDIDA"

        lista_parq.append(item)

    lista_parq.sort(key=lambda x: x["ganancia_neta"], reverse=True)

    gn_total = tot_recaudo - tot_costo
    m_total_pct = round((gn_total * 100 / tot_recaudo), 1) if tot_recaudo > 0 else 0.0
    gn_diaria_total = gn_total / dias_count
    proy_15_total = int(round(gn_diaria_total * 15))
    proy_30_total = int(round(gn_diaria_total * 30))

    return {
        "por_parqueadero": lista_parq,
        "totales": {
            "total_recaudo": tot_recaudo,
            "total_sueldos": tot_sueldos,
            "total_arl": tot_arl,
            "total_costo": tot_costo,
            "ganancia_neta_total": gn_total,
            "margen_total_pct": m_total_pct,
            "proy_15_total": proy_15_total,
            "proy_30_total": proy_30_total,
        },
        "dias_con_datos": len(dias_unicos),
        "incluir_arl": incluir_arl
    }

