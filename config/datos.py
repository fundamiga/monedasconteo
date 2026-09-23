"""
Datos fijos del sistema: Trabajadores y Parqueaderos
Extraídos del Google Sheet de recaudo
"""

PARQUEADEROS = [
    "5 CON 6",
    "6 CON 6",
    "CARTON",
    "GUACANDA",
    "GALERIA",
    "ROZO",
    "2 CON 10",
    "MAYORISTA",
    "BOLIVAR",
    "GUABINAS",
]

TRABAJADORES = sorted([
    "ADRIAN  OROZCO",
    "ALBA MARY  MARMOLEJO",
    "ALEXANDER RIVAS",
    "ANA  GOMEZ",
    "ANGELA MARIA RAMIREZ",
    "AYDE  GOMEZ",
    "CAMILO",
    "CARLOS ALBERTO  ORDOÑEZ",
    "CARLOS ANDRES QUICENO",
    "CARLOS GALARZA",
    "CESAR  CASTRO",
    "CRISTIAN CAMILO  AGUDELO",
    "CRISTIAN YAIR  TELLEZ",
    "DARIO DIAZ",
    "DEYSY MORA",
    "DIANA CAROLINA ARIAS",
    "DIANA RIASCOS",
    "DONELA GARZON",
    "EIDER PABON",
    "EMILSEN MAYORGA",
    "ESTEBAN ARIAS",
    "FABIAN  CARMONA",
    "FRANCISCO LOPEZ",
    "FREDDY OSPINA",
    "GILDARDO MOSCOSO",
    "GLORIA CATALINA PALACIOS",
    "GLORIA TERESA URBANO",
    "GUILLERMO DOMINGUEZ",
    "GUSTAVO  SANDOVAL",
    "HAROLD  CASTRO",
    "HIROSHI TAKATA",
    "ISABELA  BERMUDEZ",
    "ISABELLA GOMEZ",
    "JHON JAIRO CASTAÑEDA",
    "JOHAN GRANADA",
    "JOHAN OCHOA",
    "JOLMAN TAMAYO",
    "JOSE DAVINSON RIASCOS",
    "JOSE JAVIER TANGARIFE",
    "JOSE LAME",
    "JOSE LEONEL OSPINA",
    "JOSE TELMO OSPINA",
    "JUAN ALQUIBER ARCILA",
    "JUAN CARLOS BECERRA",
    "JULIAN ARBOLEDA",
    "LUIS CARLOS SUAREZ",
    "MARCOS AURELIO ALVAREZ",
    "MARIA ISABEL TIBAVIZCO",
    "MARILAND JOHANA AGUDELO",
    "MARILIN VALDEZ",
    "MONICA LOANGO",
    "ONNEY CUARTAS",
    "PARMENIDES NOREÑA",
    "VLAIMIR OSMA",
    "YESENIA LOANGO",
    "YESSICA ORTIZ",
    "YOLANDA ISAZA",
    "YULIETH CERON",
])

# Columnas del Google Sheet (índice base 1 para gspread)
COL_MONEDA_1000   = 3   # C
COL_MONEDA_200A   = 4   # D  ($200 tipo 1)
COL_MONEDA_500    = 5   # E
COL_MONEDA_100A   = 6   # F  ($100 tipo 1)
COL_MONEDA_200B   = 7   # G  ($200 tipo 2)
COL_MONEDA_50A    = 8   # H  ($50 tipo 1)
COL_MONEDA_100B   = 9   # I  ($100 tipo 2)
COL_MONEDA_50B    = 10  # J  ($50 tipo 2)
COL_TOTAL_MONEDAS = 11  # K

# Columnas de BILLETES:
COL_BILLETE_2000   = 12  # L
COL_BILLETE_5000   = 13  # M
COL_BILLETE_10000  = 14  # N
COL_BILLETE_20000  = 15  # O
COL_BILLETE_50000  = 16  # P
COL_BILLETE_100000 = 17  # Q
COL_TOTAL_BILLETES = 18  # R
COL_TOTAL_TURNO    = 19  # S

# Configuración de Hojas de Google Sheets
SHEETS_CONFIG = {
    "pruebas": {
        "nombre": "Pruebas (Copia)",
        "id": "1LDcd54KEzxy02zQHyPMUHPUNoKIlAZZL7p_T7cFQ4oA",
        "gid": "1508532602",
        "sheet_name": "SEPTIEMBRE 2026"
    },
    "principal": {
        "nombre": "INGRESOS DIARIOS (Principal)",
        "id": "1oRStHtTlQyTZoE0JHZ3waKjmX8j7Bt4646ufflnprNY",
        "gid": "61264833",
        "sheet_name": "SEPTIEMBRE 2026"
    }
}

# Compatibilidad hacia atrás
ID_SHEET = SHEETS_CONFIG["pruebas"]["id"]
GID_SHEET = SHEETS_CONFIG["pruebas"]["gid"]
