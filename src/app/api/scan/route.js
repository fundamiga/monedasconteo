import { NextResponse } from "next/server";

export async function POST(req) {
  try {
    const body = await req.json();
    const { image } = body;

    if (!image) {
      return NextResponse.json({ error: "No se envió ninguna imagen." }, { status: 400 });
    }

    const geminiKey = process.env.GEMINI_API_KEY;

    if (!geminiKey) {
      return NextResponse.json(
        { error: "Falta configurar la variable GEMINI_API_KEY en Vercel." },
        { status: 500 }
      );
    }

    // Limpiar base64
    let base64Data = image;
    let mimeType = "image/jpeg";
    if (image.includes(",")) {
      const parts = image.split(",");
      base64Data = parts[1];
      const match = parts[0].match(/:(.*?);/);
      if (match) mimeType = match[1];
    }

    const prompt = `Observa detalladamente la pantalla LCD azul de esta contadora de monedas SAT CC358.
Muestra una tabla con 8 renglones fijos y 3 columnas:
- Columna 1: denominación de la moneda
- Columna 2 (CENTRAL): CANTIDAD de monedas contadas (este es el dato exacto que necesito)
- Columna 3: subtotal en pesos

Los 8 renglones en orden de arriba hacia abajo corresponden a:
1. 1K ($1000)
2. 200 (primera fila de $200) -> 200a
3. 500 ($500)
4. 100 (primera fila de $100) -> 100a
5. 200 (segunda fila de $200) -> 200b
6. 50 (primera fila de $50) -> 50a
7. 100 (segunda fila de $100) -> 100b
8. 50 (segunda fila de $50) -> 50b

Ejemplo de cómo leer la pantalla:
1 K:      1      1000   -> cantidad = 1
200:      0         0   -> cantidad = 0
500:      2      1000   -> cantidad = 2
100:     11      1100   -> cantidad = 11
200:      7      1400   -> cantidad = 7
50:      69      3450   -> cantidad = 69
100:     25      2500   -> cantidad = 25
50:       1        50   -> cantidad = 1

Extrae con precisión milimétrica las 8 cantidades (columna central). Si una fila tiene 0 o está vacía pon 0.
Responde ÚNICAMENTE un JSON válido con este formato:
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
        temperature: 0.0
      }
    };

    // Lista de modelos disponibles en orden de prioridad
    const modelos = [
      "gemini-3.5-flash",
      "gemini-3.6-flash",
      "gemini-3.5-flash-lite",
      "gemini-3-flash-preview"
    ];

    let geminiRes = null;
    let ultimoError = null;
    let modeloExitoso = null;

    for (const model of modelos) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${geminiKey}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          geminiRes = await res.json();
          modeloExitoso = model;
          break;
        } else {
          const errText = await res.text();
          ultimoError = `[${model}] Error ${res.status}: ${errText}`;
          console.warn(ultimoError);
        }
      } catch (callErr) {
        ultimoError = `[${model}] Exception: ${callErr.message}`;
        console.warn(ultimoError);
      }
    }

    if (!geminiRes) {
      console.error("Ningún modelo de Gemini respondió con éxito:", ultimoError);
      return NextResponse.json(
        { error: `Fallo al procesar con IA: ${ultimoError}` },
        { status: 502 }
      );
    }

    const candidateText = geminiRes?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";
    console.log(`Respuesta exitosa de ${modeloExitoso}:`, candidateText);

    // Limpiar markdown tipo ```json ... ```
    const cleanedText = candidateText
      .replace(/```json/gi, "")
      .replace(/```/g, "")
      .trim();

    // Extraer solo el bloque { ... }
    const matchJson = cleanedText.match(/\{[\s\S]*\}/);
    if (!matchJson) {
      return NextResponse.json(
        { error: `Respuesta de IA no contiene JSON válido: ${candidateText}` },
        { status: 500 }
      );
    }

    const resultado = JSON.parse(matchJson[0]);

    // Asegurar que todos los valores sean numéricos
    const monedasLimpias = {
      "1000": parseInt(resultado["1000"], 10) || 0,
      "200a": parseInt(resultado["200a"], 10) || 0,
      "500": parseInt(resultado["500"], 10) || 0,
      "100a": parseInt(resultado["100a"], 10) || 0,
      "200b": parseInt(resultado["200b"], 10) || 0,
      "50a": parseInt(resultado["50a"], 10) || 0,
      "100b": parseInt(resultado["100b"], 10) || 0,
      "50b": parseInt(resultado["50b"], 10) || 0
    };

    return NextResponse.json({
      success: true,
      monedas: monedasLimpias,
      model: modeloExitoso,
      raw: candidateText
    });
  } catch (error) {
    console.error("Error en /api/scan:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
