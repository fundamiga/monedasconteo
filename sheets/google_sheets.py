"""
Módulo de integración con Google Sheets
Usa cuenta de servicio (service account) - no requiere login del usuario
"""

import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

from config.datos import (
    ID_SHEET,
    COL_MONEDA_1000, COL_MONEDA_200A, COL_MONEDA_500,
    COL_MONEDA_100A, COL_MONEDA_200B, COL_MONEDA_50A,
    COL_MONEDA_100B, COL_MONEDA_50B, COL_TOTAL_MONEDAS,
    COL_BILLETE_2000, COL_BILLETE_5000, COL_BILLETE_10000,
    COL_BILLETE_20000, COL_BILLETE_50000, COL_BILLETE_100000,
    COL_TOTAL_BILLETES, COL_TOTAL_TURNO
)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

import os
import sys

def obtener_ruta_base():
    """Resuelve la ruta correcta tanto en modo script como dentro de un .exe de PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CREDS_FILE = os.path.join(obtener_ruta_base(), "config", "credentials.json")

_CACHE_WS = {}

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

def obtener_nombre_pestana_mes(fecha_str=None):
    """Devuelve el nombre esperado de la pestaña según la fecha (ej: 'OCTUBRE 2026')."""
    if fecha_str:
        partes = str(fecha_str).strip().split('/')
        if len(partes) >= 3:
            try:
                mes = int(partes[1])
                anio = int(partes[2])
                if mes in MESES_ES:
                    return f"{MESES_ES[mes]} {anio}"
            except Exception:
                pass
    hoy = datetime.now()
    return f"{MESES_ES.get(hoy.month, 'OCTUBRE')} {hoy.year}"


def conectar_sheet(tipo_hoja="pruebas", forzar=False, fecha_str=None, nombre_pestana=None):
    """
    Conecta con Google Sheets usando cuenta de servicio (pruebas o principal).
    Selecciona automáticamente la pestaña del mes según la fecha (ej: 'OCTUBRE 2026', 'SEPTIEMBRE 2026').
    Cachea la sesión para respuesta ultra rápida.
    """
    from config.datos import SHEETS_CONFIG
    clave = "principal" if tipo_hoja.lower() == "principal" else "pruebas"

    if not nombre_pestana and fecha_str:
        nombre_pestana = obtener_nombre_pestana_mes(fecha_str)

    cache_key = f"{clave}_{nombre_pestana}" if nombre_pestana else clave
    if not forzar and cache_key in _CACHE_WS:
        return _CACHE_WS[cache_key]

    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    cfg = SHEETS_CONFIG[clave]
    sheet = client.open_by_key(cfg["id"])

    worksheet = None
    # 1. Intentar abrir por nombre de pestaña dinámico según el mes (ej: 'OCTUBRE 2026')
    if nombre_pestana:
        try:
            worksheet = sheet.worksheet(nombre_pestana)
        except Exception:
            worksheet = None

    # 2. Si no, intentar por el GID configurado
    if worksheet is None:
        try:
            worksheet = sheet.get_worksheet_by_id(int(cfg["gid"]))
        except Exception:
            worksheet = None

    # 3. Si no, intentar por el sheet_name configurado
    if worksheet is None:
        try:
            worksheet = sheet.worksheet(cfg["sheet_name"])
        except Exception:
            worksheet = sheet.sheet1

    _CACHE_WS[cache_key] = worksheet
    return worksheet


def obtener_fecha_hoy(dia=None):
    """
    Retorna la fecha en formato D/M/YYYY correspondiente al turno.
    Por defecto retorna la fecha del DÍA ANTERIOR (ayer), ya que el recaudo
    siempre corresponde al turno recogido el día anterior.
    Si se pasa un número de día:
    - Si coincide con ayer -> día y mes de ayer (ej: 30 de septiembre).
    - Si coincide con hoy -> día y mes de hoy (ej: 1 de octubre).
    - Si día > hoy.day -> corresponde al mes anterior (ej: día 30 cuando hoy es 1 de octubre).
    - Si día <= hoy.day -> corresponde a este mes (ej: día 1 cuando hoy es 1 o 2 de octubre).
    """
    ahora = datetime.now()
    from datetime import timedelta
    ayer = ahora - timedelta(days=1)

    if dia is None:
        return f"{ayer.day}/{ayer.month}/{ayer.year}"

    dia_num = int(dia)
    if dia_num == ayer.day:
        return f"{dia_num}/{ayer.month}/{ayer.year}"
    elif dia_num == ahora.day:
        return f"{dia_num}/{ahora.month}/{ahora.year}"
    elif dia_num > ahora.day:
        mes_ant = ahora.month - 1 if ahora.month > 1 else 12
        anio_ant = ahora.year if ahora.month > 1 else ahora.year - 1
        return f"{dia_num}/{mes_ant}/{anio_ant}"
    else:
        return f"{dia_num}/{ahora.month}/{ahora.year}"


MESES_ABREV = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Ago',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
}

def generar_opciones_fechas_combo():
    """
    Genera lista amigable de opciones para el selector de fecha del turno.
    Incluye siempre los últimos 5 a 7 días hábiles recientes (con días del mes anterior si aplica)
    y los días del mes actual.
    """
    ahora = datetime.now()
    from datetime import timedelta
    import calendar

    ayer = ahora - timedelta(days=1)
    opciones = []
    fechas_vistas = set()

    # 1. Ayer (por defecto)
    txt_ayer = f"{ayer.day}/{ayer.month}/{ayer.year} — Ayer ({ayer.day} {MESES_ABREV[ayer.month]})"
    opciones.append(txt_ayer)
    fechas_vistas.add((ayer.day, ayer.month, ayer.year))

    # 2. Hoy
    txt_hoy = f"{ahora.day}/{ahora.month}/{ahora.year} — Hoy ({ahora.day} {MESES_ABREV[ahora.month]})"
    opciones.append(txt_hoy)
    fechas_vistas.add((ahora.day, ahora.month, ahora.year))

    # 3. Días hábiles anteriores recientes (últimos 7 días para cubrir rezagados del mes anterior o semana previa)
    for i in range(2, 8):
        d_pasado = ahora - timedelta(days=i)
        clave = (d_pasado.day, d_pasado.month, d_pasado.year)
        if clave not in fechas_vistas:
            etiqueta = "Mes Anterior" if d_pasado.month != ahora.month else "Día hábil"
            txt = f"{d_pasado.day}/{d_pasado.month}/{d_pasado.year} — {d_pasado.day} {MESES_ABREV[d_pasado.month]} ({etiqueta})"
            opciones.append(txt)
            fechas_vistas.add(clave)

    # 4. Resto de días del mes actual (1 al último día)
    _, max_dias = calendar.monthrange(ahora.year, ahora.month)
    for d in range(1, max_dias + 1):
        clave = (d, ahora.month, ahora.year)
        if clave not in fechas_vistas:
            txt = f"{d}/{ahora.month}/{ahora.year} — Día {d} {MESES_ABREV[ahora.month]}"
            opciones.append(txt)
            fechas_vistas.add(clave)

    return opciones


def extraer_fecha_de_opcion(texto):
    """
    Extrae la fecha en formato D/M/YYYY del texto seleccionado en el combo.
    Ejemplo: '30/9/2026 — 30 Sep (Mes Anterior)' -> '30/9/2026'
    """
    if not texto:
        return obtener_fecha_hoy()
    txt = str(texto).strip()
    if " — " in txt:
        return txt.split(" — ")[0].strip()
    if '/' in txt:
        partes = [p.strip() for p in txt.split('/') if p.strip()]
        if len(partes) >= 3:
            return f"{partes[0]}/{partes[1]}/{partes[2]}"
    import re
    m = re.search(r'\d+', txt)
    if m:
        return obtener_fecha_hoy(int(m.group(0)))
    return obtener_fecha_hoy()


def normalizar(texto):
    """Normaliza texto para comparación."""
    if not texto:
        return ""
    return str(texto).upper().strip()


def _fila_tiene_conteo(r):
    """
    Retorna True si la fila ya tiene un conteo registrado (dinero > 0 o casillas con cantidades).
    Evita sobreescribir turnos previos del mismo trabajador.
    """
    if not r:
        return False
    # 1. Total turno (columna S, índice 18 base 0)
    if len(r) > 18:
        val_tot = re.sub(r'[^\d]', '', str(r[18]))
        if val_tot and int(val_tot) > 0:
            return True

    # 2. Casillas de monedas (C-J, índices 2-9) o billetes (L-Q, índices 11-16)
    indices = [2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16]
    for col_idx in indices:
        if len(r) > col_idx:
            val = str(r[col_idx]).strip()
            if val and val != "0":
                val_num = re.sub(r'[^\d]', '', val)
                if val_num and int(val_num) > 0:
                    return True
    return False


def buscar_fila_trabajador(worksheet, fecha_str, parqueadero, trabajador):
    """
    Busca la fila del trabajador dado una fecha y parqueadero.
    - Si el trabajador tiene una fila con su nombre que AÚN NO tiene conteo: retorna esa fila.
    - Si el trabajador ya tiene un conteo previo (o no está en la lista): busca la primera
      fila vacía disponible dentro del parqueadero para NO sobreescribir el conteo anterior.
    Retorna el número de fila (base 1) o None si no hay espacio.
    """
    try:
        todos = worksheet.get_all_values()
    except Exception:
        columna_a = worksheet.col_values(1)
        todos = [[f] for f in columna_a]

    parqueadero_norm = normalizar(parqueadero)
    trabajador_norm = normalizar(trabajador)

    # Parsear fecha buscada
    partes = fecha_str.strip().split('/')
    dia_buscado = partes[0].strip()

    PARQUEADEROS_NORM = [normalizar(p) for p in [
        "5 CON 6","6 CON 6","CARTON","GUACANDA",
        "GALERIA","ROZO","2 CON 10","MAYORISTA",
        "BOLIVAR","GUABINAS"
    ]]

    en_fecha = False
    en_parqueadero = False
    primera_vacia = None
    fila_inicio_parqueadero = None
    fila_total = None

    for i, r in enumerate(todos):
        texto_a = str(r[0]).strip() if r and len(r) > 0 else ""
        celda_a = normalizar(texto_a)

        # Detectar fila de fecha
        if '/' in texto_a and len(texto_a) > 0 and texto_a[0].isdigit():
            partes_c = texto_a.split('/')
            try:
                dia_c = int(partes_c[0].strip())
                dia_b = int(dia_buscado.strip())
                coincide_dia = (dia_c == dia_b)
            except Exception:
                coincide_dia = (partes_c[0].strip() == dia_buscado)

            if coincide_dia and (partes_c[2].strip() if len(partes_c) > 2 else False):
                en_fecha = True
                en_parqueadero = False
                primera_vacia = None
                fila_inicio_parqueadero = None
                fila_total = None
                continue
            elif en_fecha:
                # Nueva fecha → salir
                break
        elif not en_fecha and texto_a == dia_buscado and (i == 0 or not (todos[i-1] and str(todos[i-1][0]).strip())):
            en_fecha = True
            en_parqueadero = False
            primera_vacia = None
            fila_inicio_parqueadero = None
            fila_total = None
            continue

        if not en_fecha:
            continue

        # Detectar parqueadero
        if celda_a in PARQUEADEROS_NORM:
            if celda_a == parqueadero_norm:
                en_parqueadero = True
                primera_vacia = None
                fila_inicio_parqueadero = i + 2  # Primera fila de trabajadores en este parqueadero
                fila_total = None
            else:
                # Llegamos a otro parqueadero, salir si estábamos en el correcto
                if en_parqueadero:
                    break
                en_parqueadero = False
            continue

        if en_parqueadero:
            # TOTAL TURNO marca el fin de la sección
            if "TOTAL" in celda_a:
                fila_total = i + 1
                break

            tiene_conteo = _fila_tiene_conteo(r)

            if tiene_conteo:
                # Esta fila YA tiene un turno guardado. Nunca sobreescribirla,
                # aunque tenga el nombre del trabajador.
                continue

            # La fila NO tiene conteo:
            # 1. Si coincide el nombre del trabajador (ej. fila pre-escrita sin llenar):
            if celda_a and (trabajador_norm in celda_a or celda_a in trabajador_norm):
                return i + 1

            # 2. Si la fila está totalmente vacía de nombre:
            if not celda_a and primera_vacia is None:
                primera_vacia = i + 1

    # Si encontramos una fila vacía disponible, usarla
    if primera_vacia is not None:
        return primera_vacia

    # Si NO encontramos fila vacía pero estábamos en el parqueadero y tenemos la fila de TOTAL TURNO:
    # Crear e insertar una fila nueva automáticamente sin dañar fórmulas ni totales del Excel
    if en_parqueadero and fila_total is not None and fila_inicio_parqueadero is not None:
        nueva_fila = fila_total

        # Fórmulas idénticas a las filas existentes:
        # Columna K: Total monedas
        f_k = f'=C{nueva_fila}*$C$3+D{nueva_fila}*$D$3+E{nueva_fila}*$E$3+F{nueva_fila}*$F$3+G{nueva_fila}*$G$3+H{nueva_fila}*$H$3+I{nueva_fila}*$I$3+J{nueva_fila}*$J$3'
        # Columna R: Total billetes
        f_r = f'=L{nueva_fila}*$L$3+M{nueva_fila}*$M$3+N{nueva_fila}*$N$3+O{nueva_fila}*$O$3+P{nueva_fila}*$P$3+Q{nueva_fila}*$Q$3'
        # Columna S: Total turno (K + R)
        f_s = f'=K{nueva_fila}+R{nueva_fila}'

        vals = [''] * 19
        vals[0] = trabajador
        vals[10] = f_k
        vals[17] = f_r
        vals[18] = f_s

        worksheet.insert_row(vals, index=nueva_fila, value_input_option='USER_ENTERED', inherit_from_before=True)

        # La fila de TOTAL TURNO se desplazó una posición hacia abajo
        fila_total_nueva = nueva_fila + 1
        tot_updates = [
            {'range': f'K{fila_total_nueva}', 'values': [[f'=SUM(K{fila_inicio_parqueadero}:K{nueva_fila})']]},
            {'range': f'R{fila_total_nueva}', 'values': [[f'=SUM(R{fila_inicio_parqueadero}:R{nueva_fila})']]},
            {'range': f'S{fila_total_nueva}', 'values': [[f'=SUM(S{fila_inicio_parqueadero}:S{nueva_fila})']]},
        ]
        worksheet.batch_update(tot_updates)

        return nueva_fila

    return None


def escribir_nombre_trabajador(worksheet, fila, nombre):
    """Escribe el nombre del trabajador en la columna A de la fila indicada."""
    worksheet.update_cell(fila, 1, nombre)



def guardar_conteo(worksheet, fila, monedas, billetes):
    """Escribe los datos de monedas y billetes en la fila indicada."""

    def cell(col):
        return gspread.utils.rowcol_to_a1(fila, col)

    updates = [
        {'range': cell(COL_MONEDA_1000),   'values': [[monedas.get('1000', '')]]},
        {'range': cell(COL_MONEDA_200A),   'values': [[monedas.get('200a', '')]]},
        {'range': cell(COL_MONEDA_500),    'values': [[monedas.get('500', '')]]},
        {'range': cell(COL_MONEDA_100A),   'values': [[monedas.get('100a', '')]]},
        {'range': cell(COL_MONEDA_200B),   'values': [[monedas.get('200b', '')]]},
        {'range': cell(COL_MONEDA_50A),    'values': [[monedas.get('50a', '')]]},
        {'range': cell(COL_MONEDA_100B),   'values': [[monedas.get('100b', '')]]},
        {'range': cell(COL_MONEDA_50B),    'values': [[monedas.get('50b', '')]]},
        {'range': cell(COL_BILLETE_2000),  'values': [[billetes.get('2000', '')]]},
        {'range': cell(COL_BILLETE_5000),  'values': [[billetes.get('5000', '')]]},
        {'range': cell(COL_BILLETE_10000), 'values': [[billetes.get('10000', '')]]},
        {'range': cell(COL_BILLETE_20000), 'values': [[billetes.get('20000', '')]]},
        {'range': cell(COL_BILLETE_50000), 'values': [[billetes.get('50000', '')]]},
        {'range': cell(COL_BILLETE_100000),'values': [[billetes.get('100000', '')]]},
    ]

    worksheet.batch_update(updates)
    return True


def calcular_totales(monedas, billetes):
    """Calcula totales de monedas, billetes y turno."""
    def n(v):
        try:
            return int(v) if v != '' else 0
        except:
            return 0

    tm = (
        n(monedas.get('1000')) * 1000 +
        n(monedas.get('200a')) * 200  +
        n(monedas.get('500'))  * 500  +
        n(monedas.get('100a')) * 100  +
        n(monedas.get('200b')) * 200  +
        n(monedas.get('50a'))  * 50   +
        n(monedas.get('100b')) * 100  +
        n(monedas.get('50b'))  * 50
    )

    tb = (
        n(billetes.get('2000'))   * 2000   +
        n(billetes.get('5000'))   * 5000   +
        n(billetes.get('10000'))  * 10000  +
        n(billetes.get('20000'))  * 20000  +
        n(billetes.get('50000'))  * 50000  +
        n(billetes.get('100000')) * 100000
    )

    return tm, tb, tm + tb


def obtener_estructura_hoy(ws=None, dia=None):
    """
    Lee las filas de hoy agrupadas por parqueadero.
    Retorna una lista de diccionarios con parqueaderos y sus filas exactas.
    """
    if ws is None:
        ws = conectar_sheet()

    valores = ws.get_all_values()
    inicio = None
    if dia is None:
        from datetime import timedelta
        dia_buscado = (datetime.now() - timedelta(days=1)).day
    else:
        dia_buscado = int(dia)

    for i, r in enumerate(valores):
        txt_a = r[0].strip() if r and len(r) > 0 else ""
        if '/' in txt_a and txt_a[0].isdigit():
            partes_c = txt_a.split('/')
            try:
                if int(partes_c[0].strip()) == dia_buscado:
                    inicio = i
                    break
            except Exception:
                pass

    if inicio is None:
        return []

    parques = [
        "5 CON 6", "6 CON 6", "CARTON", "GUACANDA", "GALERIA",
        "ROZO", "2 CON 10", "MAYORISTA", "BOLIVAR", "GUABINAS"
    ]
    parques_norm = [normalizar(p) for p in parques]

    datos = []
    actual_parque = None

    for i in range(inicio, min(inicio + 95, len(valores))):
        r = valores[i]
        celda = normalizar(r[0]) if r else ""

        if celda in parques_norm:
            actual_parque = {"parqueadero": r[0].strip(), "filas": []}
            datos.append(actual_parque)
            continue

        if actual_parque:
            if "TOTAL" in celda:
                actual_parque["total"] = r[18].strip() if len(r) > 18 else ""
                actual_parque = None
                continue

            datos[-1]["filas"].append({
                "fila": i + 1,
                "trabajador": r[0].strip(),
                "total_monedas": r[10].strip() if len(r) > 10 else "",
                "total_billetes": r[17].strip() if len(r) > 17 else "",
                "total_turno": r[18].strip() if len(r) > 18 else "",
                "vacia": not bool(r[0].strip()),
                "monedas": {
                    "1000": r[2].strip() if len(r) > 2 else "",
                    "200a": r[3].strip() if len(r) > 3 else "",
                    "500":  r[4].strip() if len(r) > 4 else "",
                    "100a": r[5].strip() if len(r) > 5 else "",
                    "200b": r[6].strip() if len(r) > 6 else "",
                    "50a":  r[7].strip() if len(r) > 7 else "",
                    "100b": r[8].strip() if len(r) > 8 else "",
                    "50b":  r[9].strip() if len(r) > 9 else "",
                }
            })

    return datos


def guardar_fila_directa(worksheet, fila, trabajador, monedas, billetes):
    """
    Escribe directamente en una fila específica del Sheet.
    Escribe el nombre si es necesario y los valores de monedas y billetes.
    """
    if trabajador:
        escribir_nombre_trabajador(worksheet, fila, trabajador)

    guardar_conteo(worksheet, fila, monedas, billetes)
    return True
