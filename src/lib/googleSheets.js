import { google } from "googleapis";
import { ID_SHEET, PARQUEADEROS } from "./constants";

/**
 * Obtiene el cliente autenticado de Google Sheets
 */
export function getGoogleAuth() {
  let credentials;

  if (process.env.GOOGLE_SERVICE_ACCOUNT_KEY) {
    try {
      credentials = JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY);
    } catch (e) {
      console.error("Error parseando GOOGLE_SERVICE_ACCOUNT_KEY:", e);
    }
  }

  if (!credentials) {
    try {
      const fs = require("fs");
      const path = require("path");
      const credsPath = path.join(process.cwd(), "config", "credentials.json");
      if (fs.existsSync(credsPath)) {
        credentials = JSON.parse(fs.readFileSync(credsPath, "utf8"));
      }
    } catch (e) {
      console.error("Error leyendo credentials.json local:", e);
    }
  }

  if (!credentials) {
    throw new Error(
      "No se encontraron credenciales de Google Service Account. Configura GOOGLE_SERVICE_ACCOUNT_KEY."
    );
  }

  const auth = new google.auth.GoogleAuth({
    credentials,
    scopes: [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive"
    ]
  });

  return auth;
}

export async function getSheetsClient() {
  const auth = getGoogleAuth();
  const sheets = google.sheets({ version: "v4", auth });
  return sheets;
}

export function normalizar(str) {
  if (!str) return "";
  return str.toString().toUpperCase().trim();
}

/**
 * Retorna las filas de una fecha específica (o del día anterior por defecto) organizadas por parqueadero
 * @param {number|string} diaParam - Número del día del mes (1 al 31)
 */
export async function obtenerEstructuraDia(diaParam = null) {
  const sheets = await getSheetsClient();
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: ID_SHEET,
    range: "SEPTIEMBRE 2026!A1:S2500"
  });

  const valores = res.data.values || [];

  // Si no se especifica día, tomar por defecto el DÍA ANTERIOR
  let diaTarget = parseInt(diaParam, 10);
  if (isNaN(diaTarget) || diaTarget < 1 || diaTarget > 31) {
    const ahora = new Date();
    // Restar 1 día para ir por default al día anterior
    const ayer = new Date(ahora.getTime() - 24 * 60 * 60 * 1000);
    diaTarget = ayer.getDate();
  }

  // Buscar la fila de encabezado de fecha exacta para ese día (ej: "22/2/2026" o "02/02/2026")
  let inicio = -1;
  let fechaEncontrada = "";

  for (let i = 0; i < valores.length; i++) {
    const celda = (valores[i][0] || "").toString().trim();
    if (celda.includes("/")) {
      const partes = celda.split("/");
      const diaCelda = parseInt(partes[0], 10);
      if (diaCelda === diaTarget) {
        inicio = i;
        fechaEncontrada = celda;
        break;
      }
    }
  }

  if (inicio === -1) {
    // Si no encuentra la fecha exacta, tomar fila 1378 como fallback
    inicio = 1377;
    fechaEncontrada = `Día ${diaTarget}`;
  }

  const parquesNorm = PARQUEADEROS.map(normalizar);
  const datos = [];
  let actualParque = null;

  for (let i = inicio; i < Math.min(inicio + 95, valores.length); i++) {
    const row = valores[i] || [];
    const celdaA = normalizar(row[0]);

    // Si encontramos otra celda con fecha posterior a la de inicio, paramos la sección del día
    if (i > inicio && (row[0] || "").toString().trim().includes("/") && !parquesNorm.includes(celdaA)) {
      break;
    }

    if (parquesNorm.includes(celdaA)) {
      actualParque = { parqueadero: row[0].trim(), filas: [] };
      datos.push(actualParque);
      continue;
    }

    if (actualParque) {
      if (celdaA.includes("TOTAL")) {
        actualParque.total = row[18] || "";
        actualParque = null;
        continue;
      }

      const nombre = (row[0] || "").toString().trim();
      datos[datos.length - 1].filas.push({
        fila: i + 1,
        trabajador: nombre,
        total_monedas: row[10] || "",
        total_billetes: row[17] || "",
        total_turno: row[18] || "",
        vacia: !nombre
      });
    }
  }

  return {
    dia: diaTarget,
    fecha: fechaEncontrada,
    datos
  };
}

// Compatibilidad
export async function obtenerEstructuraHoy() {
  const result = await obtenerEstructuraDia();
  return result.datos;
}

/**
 * Guarda los conteos en la fila correspondiente de Google Sheets
 */
export async function guardarFilaSheet({ fila, trabajador, monedas = {}, billetes = {} }) {
  const sheets = await getSheetsClient();
  const sheetName = "SEPTIEMBRE 2026";

  const num = (v) => {
    const val = parseInt(v, 10);
    return isNaN(val) ? "" : val;
  };

  const updates = [
    // Columnas de Monedas (C a J): 1000, 200a, 500, 100a, 200b, 50a, 100b, 50b
    {
      range: `${sheetName}!C${fila}:J${fila}`,
      values: [[
        num(monedas["1000"]),
        num(monedas["200a"]),
        num(monedas["500"]),
        num(monedas["100a"]),
        num(monedas["200b"]),
        num(monedas["50a"]),
        num(monedas["100b"]),
        num(monedas["50b"])
      ]]
    },
    // Columnas de Billetes (L a Q): 2000, 5000, 10000, 20000, 50000, 100000
    {
      range: `${sheetName}!L${fila}:Q${fila}`,
      values: [[
        num(billetes["2000"]),
        num(billetes["5000"]),
        num(billetes["10000"]),
        num(billetes["20000"]),
        num(billetes["50000"]),
        num(billetes["100000"])
      ]]
    }
  ];

  // Si se envió nombre de trabajador, actualizar columna A
  if (trabajador) {
    updates.unshift({
      range: `${sheetName}!A${fila}`,
      values: [[trabajador]]
    });
  }

  await sheets.spreadsheets.values.batchUpdate({
    spreadsheetId: ID_SHEET,
    requestBody: {
      valueInputOption: "USER_ENTERED",
      data: updates
    }
  });

  return { success: true, fila };
}
