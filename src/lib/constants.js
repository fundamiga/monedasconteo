export const ID_SHEET = "1LDcd54KEzxy02zQHyPMUHPUNoKIlAZZL7p_T7cFQ4oA";
export const GID_SHEET = "1508532602"; // SEPTIEMBRE 2026

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
  "EIDER PABON",
  "FABIAN  CARMONA",
  "FREDDY OSPINA",
  "GILDARDO MOSCOSO",
  "GUSTAVO  SANDOVAL",
  "HAROLD  CASTRO",
  "HEIDY CAROLINA BAUTISTA",
  "ISABELA  BERMUDEZ",
  "JENIFER SERNA",
  "JHON JAIRO CASTAÑEDA",
  "JHONIER  GONZALEZ",
  "JOSE LUIS  ROSERO",
  "JOSUE ORLANDO PALOMINO",
  "JUAN ALQUIBER ARCILA",
  "JUAN CARLOS BECERRA",
  "LUIS CARLOS SUARES",
  "LUIS FERNDO DIAS",
  "MARILIN VALDEZ",
  "MIGUEL BENITEZ",
  "PARMENIADES NOREÑA",
  "STIVEL",
  "VALERIA",
  "VICTOR MARIN",
  "YURANI MOSCOSO"
];

// Mapeo de columnas en Google Sheet
export const COLS = {
  MONEDA_1000: 3,   // C
  MONEDA_200A: 4,   // D
  MONEDA_500: 5,    // E
  MONEDA_100A: 6,   // F
  MONEDA_200B: 7,   // G
  MONEDA_50A: 8,    // H
  MONEDA_100B: 9,   // I
  MONEDA_50B: 10,   // J
  TOTAL_MONEDAS: 11,// K
  BILLETE_2000: 12, // L
  BILLETE_5000: 13, // M
  BILLETE_10000: 14,// N
  BILLETE_20000: 15,// O
  BILLETE_50000: 16,// P
  BILLETE_100000: 17,// Q
  TOTAL_BILLETES: 18,// R
  TOTAL_TURNO: 19   // S
};

export const DENOM_MONEDAS = [
  { key: "1000", label: "$1.000", valor: 1000, row: 1 },
  { key: "200a", label: "$200 (A)", valor: 200, row: 2 },
  { key: "500", label: "$500", valor: 500, row: 3 },
  { key: "100a", label: "$100 (A)", valor: 100, row: 4 },
  { key: "200b", label: "$200 (B)", valor: 200, row: 5 },
  { key: "50a", label: "$50 (A)", valor: 50, row: 6 },
  { key: "100b", label: "$100 (B)", valor: 100, row: 7 },
  { key: "50b", label: "$50 (B)", valor: 50, row: 8 },
];

export const DENOM_BILLETES = [
  { key: "2000", label: "$2.000", valor: 2000 },
  { key: "5000", label: "$5.000", valor: 5000 },
  { key: "10000", label: "$10.000", valor: 10000 },
  { key: "20000", label: "$20.000", valor: 20000 },
  { key: "50000", label: "$50.000", valor: 50000 },
  { key: "100000", label: "$100.000", valor: 100000 },
];
