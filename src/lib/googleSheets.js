import { google } from "googleapis";
import fs from "fs";
import path from "path";
import { ID_SHEET, GID_SHEET, PARQUEADEROS } from "./constants";

export function getGoogleAuth() {
  let credentials = null;

  // 1. Intentar variable de entorno en Vercel
  if (process.env.GOOGLE_SERVICE_ACCOUNT_KEY) {
    try {
      credentials = JSON.parse(process.env.GOOGLE_SERVICE_ACCOUNT_KEY);
    } catch (e) {
      console.error("Error al parsear GOOGLE_SERVICE_ACCOUNT_KEY:", e);
    }
  }

  // 2. Si no hay variable, buscar archivo local config/credentials.json
  if (!credentials) {
    const localPath = path.join(process.cwd(), "config", "credentials.json");
    if (fs.existsSync(localPath)) {
      credentials = JSON.parse(fs.readFileSync(localPath, "utf-8"));
    }
  }

  if (!credentials) {
    throw new Error(
      "No se encontraron credenciales de Google Sheets. Configura GOOGLE_SERVICE_ACCOUNT_KEY en Vercel o config/credentials.json localmente."
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
 * Retorna las filas del día actual organizadas por parqueadero
 */
export async function obtenerEstructuraHoy() {
  const sheets = await getSheetsClient();
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: ID_SHEET,
    range: "SEPTIEMBRE 2026!A1:S2500"
  });

  const valores = res.data.values || [];
  const diaHoy = new Date().getDate().toString();

  let inicio = -1;
  for (let i = 0; i < valores.length; i++) {
    const celda = (valores[i][0] || "").toString().trim();
    if (celda.startsWith(diaHoy) && celda.includes("/")) {
      inicio = i;
      break;
    }
  }

  if (inicio === -1) {
    // Si no encuentra el día de hoy, tomar la fila 1378 (18/2/2026) como referencia
    inicio = 1377;
  }

  const parquesNorm = PARQUEADEROS.map(normalizar);
  const datos = [];
  let actualParque = null;

  for (let i = inicio; i < Math.min(inicio + 95, valores.length); i++) {
    const row = valores[i] || [];
    const celdaA = normalizar(row[0]);

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

  return datos;
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
