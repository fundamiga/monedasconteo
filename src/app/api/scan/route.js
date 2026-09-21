import { NextResponse } from "next/server";

export async function POST(req) {
  try {
    const body = await req.json();
    const { image, apiKey } = body;

    if (!image) {
      return NextResponse.json({ error: "No se envió ninguna imagen." }, { status: 400 });
    }

    const geminiKey = apiKey || process.env.GEMINI_API_KEY;

    if (!geminiKey) {
      return NextResponse.json(
        {
          error:
            "Falta la clave API de Gemini. Puedes configurarla en las variables de entorno de Vercel (GEMINI_API_KEY) o ingresarla en los ajustes de la app."
        },
        { status: 400 }
      );
    }

    // Limpiar base64 (quitar cabecera data:image/jpeg;base64, si existe)
    let base64Data = image;
    let mimeType = "image/jpeg";
    if (image.includes(",")) {
      const parts = image.split(",");
      base64Data = parts[1];
      const match = parts[0].match(/:(.*?);/);
      if (match) mimeType = match[1];
    }

    const prompt = `Analiza detalladamente esta foto de la pantalla LCD azul de la máquina contadora de monedas SAT CC358.
La pantalla tiene 8 filas fijas en el siguiente orden exacto de arriba a abajo:
Fila 1: 1 K: ($1.000)
Fila 2: 200: ($200 vieja / tipo 1)
Fila 3: 500: ($500)
Fila 4: 100: ($100 vieja / tipo 1)
Fila 5: 200: ($200 nueva / tipo 2)
Fila 6:  50: ($50 vieja / tipo 1)
Fila 7: 100: ($100 nueva / tipo 2)
Fila 8:  50: ($50 nueva / tipo 2)

Cada fila muestra: [Denominación] [Cantidad de monedas] [Subtotal].
Por favor, extrae la CANTIDAD (el número en la columna central) de cada una de las 8 filas. Si alguna fila tiene 0 o está vacía, pon 0.

Responde ÚNICAMENTE un objeto JSON válido con esta estructura exacta, sin texto adicional ni bloques de código markdown:
{
  "1000": 0,
  "200a": 0,
  "500": 0,
  "100a": 0,
  "200b": 0,
  "50a": 0,
  "100b": 0,
  "50b": 0
}`;

    // Llamar a la API de Gemini (probamos gemini-1.5-flash o gemini-2.5-flash)
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiKey}`;

    const payload = {
      contents: [
        {
          parts: [
            { text: prompt },
            {
              inline_data: {
                mime_type: mimeType,
                data: base64Data
              }
            }
          ]
        }
      ],
      generationConfig: {
        temperature: 0.1,
        response_mime_type: "application/json"
      }
    };

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.text();
      console.error("Error Gemini API:", errData);
      return NextResponse.json(
        { error: `Error de Gemini API (${res.status}): ${errData}` },
        { status: 500 }
      );
    }

    const data = await res.json();
    const candidateText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";

    // Limpiar markdown si vino con ```json
    const cleanedText = candidateText.replace(/```json/g, "").replace(/```/g, "").trim();
    const resultado = JSON.parse(cleanedText);

    return NextResponse.json({
      success: true,
      monedas: resultado,
      raw: candidateText
    });
  } catch (error) {
    console.error("Error en /api/scan:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
