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

        # Migración automática: corregir fechas antiguas de Septiembre que venían con /2/2026
        try:
            conn.execute("UPDATE conteos SET fecha_turno = REPLACE(fecha_turno, '/2/2026', '/9/2026') WHERE fecha_turno LIKE '%/2/2026'")
        except Exception:
            pass


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


def obtener_balance_estadisticas(mes=None, anio=None, quincena="todos", hoja_tipo="todas", filtro_trabajador="", filtro_parqueadero="", incluir_arl=True):
    """
    Calcula estadísticas, balances y conteo de apariciones por persona en un período.
    
    Parámetros:
      - mes: Número de mes (1 al 12) o None para todos los meses.
      - anio: Año (ej: 2026) o None.
      - quincena: '1ra' (días 1 al 15), '2da' (días 16 al 31) o 'todos' (mes completo).
      - hoja_tipo: 'todas', 'principal' o 'pruebas'.
      - filtro_trabajador: Texto para filtrar nombre de persona.
      - filtro_parqueadero: Nombre de parqueadero o '' para todos.
      - incluir_arl: Booleano para incluir el valor proporcional diario de ARL ($2.540/turno).
    """
    init_db()
    with _conectar() as conn:
        cursor = conn.execute("SELECT * FROM conteos ORDER BY id ASC")
        filas = [dict(r) for r in cursor.fetchall()]

    # Filtrar registros en Python para manejo robusto de fechas y formatos
    filtrados = []
    for r in filas:
        # Filtro hoja
        if hoja_tipo != "todas" and r.get("hoja_tipo", "").lower() != hoja_tipo.lower():
            continue

        # Filtro parqueadero
        if filtro_parqueadero and filtro_parqueadero != "TODOS":
            if filtro_parqueadero.upper() not in r.get("parqueadero", "").upper():
                continue

        # Filtro trabajador
        if filtro_trabajador.strip():
            if filtro_trabajador.strip().upper() not in r.get("trabajador", "").upper():
                continue

        # Parsear fecha turno (D/M/YYYY)
        f_str = str(r.get("fecha_turno", "")).strip()
        partes = f_str.split("/")
        if len(partes) >= 3:
            try:
                dia_reg = int(partes[0].strip())
                mes_reg = int(partes[1].strip())
                anio_reg = int(partes[2].strip())
            except Exception:
                continue

            # Validar año
            if anio is not None and anio_reg != int(anio):
                continue

            # Validar mes
            if mes is not None and mes_reg != int(mes):
                continue

            # Validar quincena
            if quincena == "1ra" and not (1 <= dia_reg <= 15):
                continue
            elif quincena == "2da" and not (16 <= dia_reg <= 31):
                continue

        filtrados.append(r)

    # Agrupar por trabajador
    trabajadores_map = {}
    parqueaderos_map = {}

    tot_general = 0
    tot_monedas = 0
    tot_billetes = 0

    for r in filtrados:
        t_nom = r.get("trabajador", "DESCONOCIDO").strip().upper()
        p_nom = r.get("parqueadero", "DESCONOCIDO").strip().upper()
        t_mon = int(r.get("total_monedas", 0) or 0)
        t_bil = int(r.get("total_billetes", 0) or 0)
        t_tur = int(r.get("total_turno", 0) or 0)

        tot_general += t_tur
        tot_monedas += t_mon
        tot_billetes += t_bil

        # Agrupación trabajador
        if t_nom not in trabajadores_map:
            trabajadores_map[t_nom] = {
                "trabajador": t_nom,
                "turnos": 0,
                "total_recaudo": 0,
                "total_monedas": 0,
                "total_billetes": 0,
                "parqueaderos": set(),
                "registros": []
            }
        trabajadores_map[t_nom]["turnos"] += 1
        trabajadores_map[t_nom]["total_recaudo"] += t_tur
        trabajadores_map[t_nom]["total_monedas"] += t_mon
        trabajadores_map[t_nom]["total_billetes"] += t_bil
        trabajadores_map[t_nom]["parqueaderos"].add(p_nom)
        trabajadores_map[t_nom]["registros"].append(r)

        # Agrupación parqueadero
        if p_nom not in parqueaderos_map:
            parqueaderos_map[p_nom] = {
                "parqueadero": p_nom,
                "turnos": 0,
                "total_recaudo": 0,
                "total_monedas": 0,
                "total_billetes": 0
            }
        parqueaderos_map[p_nom]["turnos"] += 1
        parqueaderos_map[p_nom]["total_recaudo"] += t_tur
        parqueaderos_map[p_nom]["total_monedas"] += t_mon
        parqueaderos_map[p_nom]["total_billetes"] += t_bil

    # Convertir a lista y calcular promedios
    lista_trabajadores = []
    for t_data in trabajadores_map.values():
        turnos = t_data["turnos"]
        promedio = (t_data["total_recaudo"] // turnos) if turnos > 0 else 0
        lista_trabajadores.append({
            "trabajador": t_data["trabajador"],
            "turnos": turnos,
            "total_recaudo": t_data["total_recaudo"],
            "total_monedas": t_data["total_monedas"],
            "total_billetes": t_data["total_billetes"],
            "promedio": promedio,
            "parqueaderos": sorted(list(t_data["parqueaderos"])),
            "registros": t_data["registros"]
        })

    # Ordenar por recaudo descendente
    lista_trabajadores.sort(key=lambda x: x["total_recaudo"], reverse=True)

    # Lista parqueaderos ordenada
    lista_parqueaderos = list(parqueaderos_map.values())
    lista_parqueaderos.sort(key=lambda x: x["total_recaudo"], reverse=True)

    # Top métricas
    top_turnos = None
    if lista_trabajadores:
        top_turnos = max(lista_trabajadores, key=lambda x: x["turnos"])

    top_recaudo = lista_trabajadores[0] if lista_trabajadores else None

    pct_monedas = round((tot_monedas * 100 / tot_general), 1) if tot_general > 0 else 0
    pct_billetes = round((tot_billetes * 100 / tot_general), 1) if tot_general > 0 else 0

    # ── Balance Financiero y Cruce con Nómina (Supabase) ──
    try:
        from nomina_supabase import obtener_resumen_nomina
        resumen_nom = obtener_resumen_nomina(mes=mes, anio=anio, quincena=quincena)
        por_parq_nom = resumen_nom.get("por_parqueadero", {})
    except Exception:
        resumen_nom = {
            "gastos_admin": {"q1": 0, "q2": 0, "total": 0},
            "gastos_remesas": {"q1": 0, "q2": 0, "total": 0},
            "total_general": {"q1": 0, "q2": 0, "total": 0, "total_personas": 0},
            "quincenas_encontradas": []
        }
        por_parq_nom = {}

    balance_financiero = []
    tot_nomina_parq = 0

    todos_parqs = sorted(list(set(parqueaderos_map.keys()) | set(por_parq_nom.keys())))
    for p_nom in todos_parqs:
        rec_data = parqueaderos_map.get(p_nom, {"turnos": 0, "total_recaudo": 0, "total_monedas": 0, "total_billetes": 0})
        nom_data = por_parq_nom.get(p_nom, {"q1": 0, "q2": 0, "total": 0, "arl": 0, "personas": 0})

        recaudo = rec_data["total_recaudo"]
        nomina_q1 = nom_data["q1"]
        nomina_q2 = nom_data["q2"]
        nomina_total = nom_data["total"]
        tot_nomina_parq += nomina_total

        ganancia_neta = recaudo - nomina_total
        margen_pct = round((ganancia_neta / recaudo) * 100, 1) if recaudo > 0 else (0.0 if nomina_total == 0 else -100.0)

        if ganancia_neta > 0 and margen_pct >= 25:
            estado = "RENTABLE"
        elif ganancia_neta >= 0:
            estado = "EQUILIBRIO"
        else:
            estado = "DEFICIT"

        balance_financiero.append({
            "parqueadero": p_nom,
            "turnos": rec_data["turnos"],
            "recaudo": recaudo,
            "nomina_q1": nomina_q1,
            "nomina_q2": nomina_q2,
            "nomina_total": nomina_total,
            "ganancia_neta": ganancia_neta,
            "margen_pct": margen_pct,
            "personas_nomina": nom_data["personas"],
            "estado": estado
        })

    balance_financiero.sort(key=lambda x: x["ganancia_neta"], reverse=True)

    gastos_admin = resumen_nom["gastos_admin"]["total"]
    gastos_remesas = resumen_nom["gastos_remesas"]["total"]
    total_nomina_general = resumen_nom["total_general"]["total"]
    utilidad_neta_fundacion = tot_general - total_nomina_general
    margen_fundacion_pct = round((utilidad_neta_fundacion / tot_general) * 100, 1) if tot_general > 0 else 0

    # ── Estimado en Tiempo Real (Día a Día / En Curso) ──
    try:
        from nomina_supabase import calcular_estimado_tiempo_real
        estimado_tr = calcular_estimado_tiempo_real(filtrados, incluir_arl=incluir_arl)
    except Exception as e:
        estimado_tr = {
            "por_parqueadero": [],
            "totales": {
                "total_recaudo": tot_general,
                "total_sueldos": 0,
                "total_arl": 0,
                "total_costo": 0,
                "ganancia_neta_total": 0,
                "margen_total_pct": 0.0,
                "proy_15_total": 0,
                "proy_30_total": 0
            },
            "dias_con_datos": 0,
            "incluir_arl": incluir_arl,
            "error": str(e)
        }

    return {
        "totales": {
            "total_recaudo": tot_general,
            "total_monedas": tot_monedas,
            "total_billetes": tot_billetes,
            "total_turnos": len(filtrados),
            "pct_monedas": pct_monedas,
            "pct_billetes": pct_billetes,
            "trabajadores_activos": len(lista_trabajadores)
        },
        "top_turnos": top_turnos,
        "top_recaudo": top_recaudo,
        "trabajadores": lista_trabajadores,
        "parqueaderos": lista_parqueaderos,
        "total_registros": len(filtrados),
        "balance_financiero": balance_financiero,
        "estimado_tiempo_real": estimado_tr,
        "resumen_nomina": {
            "total_nomina_parqueaderos": tot_nomina_parq,
            "gastos_admin": gastos_admin,
            "gastos_remesas": gastos_remesas,
            "total_nomina_general": total_nomina_general,
            "utilidad_neta_fundacion": utilidad_neta_fundacion,
            "margen_fundacion_pct": margen_fundacion_pct,
            "quincenas_encontradas": resumen_nom["quincenas_encontradas"]
        }
    }


def exportar_reporte_balance_csv(ruta_archivo, balance_data, periodo_texto=""):
    """Exporta el reporte detallado por trabajador a formato CSV."""
    import csv
    with open(ruta_archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["REPORTE Y BALANCE DE RECAUDO CONTEOCC358"])
        writer.writerow([f"Período: {periodo_texto}"])
        writer.writerow([
            f"Total Recaudado: $ {balance_data['totales']['total_recaudo']:,}".replace(",", "."),
            f"Total Monedas: $ {balance_data['totales']['total_monedas']:,}".replace(",", "."),
            f"Total Billetes: $ {balance_data['totales']['total_billetes']:,}".replace(",", "."),
            f"Total Turnos: {balance_data['totales']['total_turnos']}"
        ])
        writer.writerow([])
        writer.writerow([
            "Posición", "Trabajador", "Turnos (# Veces)",
            "Total Recaudado ($)", "Total Monedas ($)", "Total Billetes ($)",
            "Promedio x Turno ($)", "Parqueaderos"
        ])
        for idx, t in enumerate(balance_data["trabajadores"], 1):
            writer.writerow([
                idx,
                t["trabajador"],
                t["turnos"],
                t["total_recaudo"],
                t["total_monedas"],
                t["total_billetes"],
                t["promedio"],
                ", ".join(t["parqueaderos"])
            ])

        # Sección 2: Balance Financiero por Parqueadero (Recaudo vs Nómina)
        if "balance_financiero" in balance_data and balance_data["balance_financiero"]:
            writer.writerow([])
            writer.writerow(["BALANCE FINANCIERO Y RENTABILIDAD POR PARQUEADERO (RECAUDO VS NÓMINA)"])
            writer.writerow([
                "Posición", "Parqueadero", "Turnos (#)", "Recaudo Máquina ($)",
                "Nómina Q1 ($)", "Nómina Q2 ($)", "Total Nómina ($)",
                "Ganancia Neta ($)", "Margen (%)", "Estado"
            ])
            for idx, p in enumerate(balance_data["balance_financiero"], 1):
                writer.writerow([
                    idx,
                    p["parqueadero"],
                    p["turnos"],
                    p["recaudo"],
                    p["nomina_q1"],
                    p["nomina_q2"],
                    p["nomina_total"],
                    p["ganancia_neta"],
                    f"{p['margen_pct']}%",
                    p["estado"]
                ])
            res_nom = balance_data.get("resumen_nomina", {})
            writer.writerow([])
            writer.writerow(["RESUMEN FINANCIERO GENERAL"])
            writer.writerow(["Total Recaudo Máquina ($)", balance_data["totales"]["total_recaudo"]])
            writer.writerow(["Total Nómina Parqueaderos ($)", res_nom.get("total_nomina_parqueaderos", 0)])
            writer.writerow(["Gastos Administración ($)", res_nom.get("gastos_admin", 0)])
            writer.writerow(["Gastos Remesas ($)", res_nom.get("gastos_remesas", 0)])
            writer.writerow(["Total Nómina General ($)", res_nom.get("total_nomina_general", 0)])
            writer.writerow(["GANANCIA NETA LIBRE FUNDACIÓN ($)", res_nom.get("utilidad_neta_fundacion", 0)])
            writer.writerow(["MARGEN LIBRE (%)", f"{res_nom.get('margen_fundacion_pct', 0)}%"])

    return len(balance_data["trabajadores"])


def sincronizar_desde_sheets(hoja_tipo="principal", mes_nombre="OCTUBRE 2026"):
    """
    Lee todas las filas registradas en una pestaña de Google Sheets y las
    agrega a la base de datos local si no existían, para tener estadísticas completas.
    """
    try:
        from sheets.google_sheets import conectar_sheet, normalizar
        ws = conectar_sheet(hoja_tipo, nombre_pestana=mes_nombre)
        todos = ws.get_all_values()
    except Exception as e:
        return 0, f"Error conectando a Sheets: {e}"

    PARQUEADEROS_SET = {
        "5 CON 6", "6 CON 6", "CARTON", "GUACANDA",
        "GALERIA", "ROZO", "2 CON 10", "MAYORISTA",
        "BOLIVAR", "GUABINAS"
    }

    MESES_MAP = {
        "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
        "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
        "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
    }
    mes_num_real = None
    for nom_m, num_m in MESES_MAP.items():
        if nom_m in str(mes_nombre).upper():
            mes_num_real = num_m
            break

    fecha_actual = ""
    parqueadero_actual = ""
    importados = 0

    init_db()
    with _conectar() as conn:
        for r in todos:
            if not r:
                continue
            txt_a = str(r[0]).strip() if len(r) > 0 else ""
            txt_norm = normalizar(txt_a)

            # Detectar fecha y normalizar con el mes real de la pestaña
            if '/' in txt_a and len(txt_a) > 0 and txt_a[0].isdigit():
                partes_f = txt_a.split('/')
                dia_f = partes_f[0].strip()
                anio_f = partes_f[2].strip() if len(partes_f) > 2 else '2026'
                mes_f = mes_num_real if mes_num_real else (partes_f[1].strip() if len(partes_f) > 1 else '9')
                fecha_actual = f"{dia_f}/{mes_f}/{anio_f}"
                parqueadero_actual = ""
                continue

            # Detectar parqueadero
            if txt_norm in PARQUEADEROS_SET:
                parqueadero_actual = txt_norm
                continue

            # Detectar fila de trabajador con conteo
            if fecha_actual and parqueadero_actual and txt_a and "TOTAL" not in txt_norm:
                # Comprobar si tiene conteo en columna S (índice 18) o total monedas/billetes
                total_turno_str = r[18].replace("$", "").replace(".", "").replace(",", "").strip() if len(r) > 18 else ""
                if total_turno_str.isdigit() and int(total_turno_str) > 0:
                    tt = int(total_turno_str)
                    tm_str = r[10].replace("$", "").replace(".", "").replace(",", "").strip() if len(r) > 10 else "0"
                    tb_str = r[17].replace("$", "").replace(".", "").replace(",", "").strip() if len(r) > 17 else "0"
                    tm = int(tm_str) if tm_str.isdigit() else 0
                    tb = int(tb_str) if tb_str.isdigit() else 0

                    trabajador = txt_norm

                    # Verificar si ya existe exactamente este turno en la base de datos
                    cur = conn.execute("""
                        SELECT id FROM conteos 
                        WHERE fecha_turno = ? AND parqueadero = ? AND trabajador = ? AND total_turno = ?
                    """, (fecha_actual, parqueadero_actual, trabajador, tt))
                    if not cur.fetchone():
                        # Monedas
                        monedas = {
                            "1000": int(r[2]) if len(r) > 2 and r[2].isdigit() else 0,
                            "200a": int(r[3]) if len(r) > 3 and r[3].isdigit() else 0,
                            "500":  int(r[4]) if len(r) > 4 and r[4].isdigit() else 0,
                            "100a": int(r[5]) if len(r) > 5 and r[5].isdigit() else 0,
                            "200b": int(r[6]) if len(r) > 6 and r[6].isdigit() else 0,
                            "50a":  int(r[7]) if len(r) > 7 and r[7].isdigit() else 0,
                            "100b": int(r[8]) if len(r) > 8 and r[8].isdigit() else 0,
                            "50b":  int(r[9]) if len(r) > 9 and r[9].isdigit() else 0,
                        }
                        billetes = {
                            "2000":   int(r[11]) if len(r) > 11 and r[11].isdigit() else 0,
                            "5000":   int(r[12]) if len(r) > 12 and r[12].isdigit() else 0,
                            "10000":  int(r[13]) if len(r) > 13 and r[13].isdigit() else 0,
                            "20000":  int(r[14]) if len(r) > 14 and r[14].isdigit() else 0,
                            "50000":  int(r[15]) if len(r) > 15 and r[15].isdigit() else 0,
                            "100000": int(r[16]) if len(r) > 16 and r[16].isdigit() else 0,
                        }

                        conn.execute("""
                            INSERT INTO conteos (
                                timestamp, fecha_turno, parqueadero, trabajador,
                                hoja_tipo, monedas_json, billetes_json,
                                total_monedas, total_billetes, total_turno
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            fecha_actual,
                            parqueadero_actual,
                            trabajador,
                            hoja_tipo,
                            json.dumps(monedas),
                            json.dumps(billetes),
                            tm, tb, tt
                        ))
                        importados += 1

    return importados, "OK"

