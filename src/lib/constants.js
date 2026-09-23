// Configuración de Hojas de Google Sheets
export const SHEETS_CONFIG = {
  pruebas: {
    nombre: "Pruebas (Copia)",
    id: "1LDcd54KEzxy02zQHyPMUHPUNoKIlAZZL7p_T7cFQ4oA",
    gid: "1508532602",
    sheet_name: "SEPTIEMBRE 2026"
  },
  principal: {
    nombre: "INGRESOS DIARIOS (Principal)",
    id: "1oRStHtTlQyTZoE0JHZ3waKjmX8j7Bt4646ufflnprNY",
    gid: "61264833",
    sheet_name: "SEPTIEMBRE 2026"
  }
};

export const SHEETS = SHEETS_CONFIG;
export const ID_SHEET = SHEETS_CONFIG.pruebas.id;
export const GID_SHEET = SHEETS_CONFIG.pruebas.gid;

export const PARQUEADEROS = [
  "5 CON 6",
  "6 CON 6",
  "CARTON",
  "GUACANDA",
  "GALERIA",
  "ROZO",
  "2 CON 10",
  "MAYORISTA",
  "BOLIVAR",
  "GUABINAS"
];

export const TRABAJADORES = [
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
  "YULIETH CERON"
];

export const DENOM_MONEDAS = [
  { key: "1000", label: "$1.000", valor: 1000 },
  { key: "200a", label: "$200 (A)", valor: 200 },
  { key: "500", label: "$500", valor: 500 },
  { key: "100a", label: "$100 (A)", valor: 100 },
  { key: "200b", label: "$200 (B)", valor: 200 },
  { key: "50a", label: "$50 (A)", valor: 50 },
  { key: "100b", label: "$100 (B)", valor: 100 },
  { key: "50b", label: "$50 (B)", valor: 50 }
];

export const DENOM_BILLETES = [
  { key: "2000", label: "$2.000", valor: 2000 },
  { key: "5000", label: "$5.000", valor: 5000 },
  { key: "10000", label: "$10.000", valor: 10000 },
  { key: "20000", label: "$20.000", valor: 20000 },
  { key: "50000", label: "$50.000", valor: 50000 },
  { key: "100000", label: "$100.000", valor: 100000 }
];
