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

CREDS_FILE = "config/credentials.json"


def conectar_sheet(tipo_hoja="pruebas"):
    """Conecta con Google Sheets usando cuenta de servicio (pruebas o principal)."""
    from config.datos import SHEETS_CONFIG
    clave = "principal" if tipo_hoja.lower() == "principal" else "pruebas"
    cfg = SHEETS_CONFIG[clave]

    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(cfg["id"])
    # Abrir la pestaña específica por GID
    try:
        worksheet = sheet.get_worksheet_by_id(int(cfg["gid"]))
    except Exception:
        try:
            worksheet = sheet.worksheet(cfg["sheet_name"])
        except Exception:
            worksheet = sheet.sheet1
    return worksheet


def obtener_fecha_hoy(dia=None):
    """
    Retorna la fecha en el formato que usa el Sheet (DD/2/YYYY).
    Por defecto retorna el DÍA ANTERIOR (ayer), ya que el recaudo siempre
    corresponde al turno recogido el día anterior.
    """
    hoy = datetime.now()
    if dia is None:
        from datetime import timedelta
        ayer = hoy - timedelta(days=1)
        dia_num = ayer.day
    else:
        dia_num = int(dia)
    return f"{dia_num}/2/{hoy.year}"


def normalizar(texto):
    """Normaliza texto para comparación."""
    if not texto:
        return ""
    return str(texto).upper().strip()


def buscar_fila_trabajador(worksheet, fecha_str, parqueadero, trabajador):
    """
    Busca la fila del trabajador dado una fecha y parqueadero.
    - Si el trabajador ya tiene una fila con su nombre: retorna esa fila.
    - Si no, retorna la primera fila vacía disponible dentro del parqueadero.
    Retorna el número de fila (base 1) o None si no hay espacio.
    """
    todos = worksheet.get_all_values()
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

    for i, fila in enumerate(todos):
        celda_a = normalizar(fila[0]) if fila else ""
        texto_a = fila[0].strip() if fila else ""

        # Detectar fila de fecha
        if '/' in texto_a and texto_a[0].isdigit():
            partes_c = texto_a.split('/')
            if partes_c[0].strip() == dia_buscado and partes_c[2].strip() if len(partes_c) > 2 else False:
                en_fecha = True
                en_parqueadero = False
                primera_vacia = None
                continue
            elif en_fecha:
                # Nueva fecha → salir
                break

        if not en_fecha:
            continue

        # Detectar parqueadero
        if celda_a in PARQUEADEROS_NORM:
            if celda_a == parqueadero_norm:
                en_parqueadero = True
                primera_vacia = None
            else:
                # Llegamos a otro parqueadero, salir si estábamos en el correcto
                if en_parqueadero:
                    break
                en_parqueadero = False
            continue

        if en_parqueadero:
            # TOTAL TURNO marca el fin de la sección
            if "TOTAL" in celda_a:
                break

            # Fila vacía disponible
            if not celda_a and primera_vacia is None:
                primera_vacia = i + 1  # guardar por si no encontramos al trabajador

            # Fila con el trabajador
            if celda_a and (
                trabajador_norm in celda_a or
                celda_a in trabajador_norm
            ):
                return i + 1  # fila exacta del trabajador

    # Si no encontramos al trabajador, usamos la primera fila vacía
    return primera_vacia


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


def obtener_estructura_hoy(ws=None):
    """
    Lee las filas de hoy agrupadas por parqueadero.
    Retorna una lista de diccionarios con parqueaderos y sus filas exactas.
    """
    if ws is None:
        ws = conectar_sheet()

    valores = ws.get_all_values()
    inicio = None
    dia_str = str(datetime.now().day)

    for i, r in enumerate(valores):
        if r and r[0].strip().startswith(dia_str) and '/' in r[0]:
            inicio = i
            break

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
