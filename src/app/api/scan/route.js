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
        { error: "Falta la variable de entorno GEMINI_API_KEY en Vercel." },
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

    const prompt = `Eres un lector especializado de pantallas LCD azules de máquinas contadoras de monedas SAT CC358.

La pantalla tiene EXACTAMENTE 3 COLUMNAS y 8 FILAS fijas:
- COLUMNA IZQUIERDA: tipo de denominación
- COLUMNA DEL MEDIO (CENTRO): CANTIDAD de monedas contadas  ← EL NÚMERO QUE DEBES LEER
- COLUMNA DERECHA: subtotal en pesos (el número más grande, que NO debes usar)

IMPORTANTE: Tú debes leer SOLO la columna del MEDIO (la cantidad de monedas), NUNCA la columna derecha (el subtotal).

Las 8 filas en orden exacto de arriba hacia abajo son:
Fila 1: "1 K"  → moneda $1.000  → lee la CANTIDAD del centro
Fila 2: "200"  → moneda $200 vieja (tipo A) → lee la CANTIDAD del centro
Fila 3: "500"  → moneda $500    → lee la CANTIDAD del centro
Fila 4: "100"  → moneda $100 vieja (tipo A) → lee la CANTIDAD del centro
Fila 5: "200"  → moneda $200 nueva (tipo B) → lee la CANTIDAD del centro
Fila 6: " 50"  → moneda $50 vieja (tipo A)  → lee la CANTIDAD del centro
Fila 7: "100"  → moneda $100 nueva (tipo B) → lee la CANTIDAD del centro
Fila 8: " 50"  → moneda $50 nueva (tipo B)  → lee la CANTIDAD del centro

EJEMPLOS de cómo leer cada fila:
- Fila que dice: "1 K    1    1000"  → la CANTIDAD es 1   (NO 1000)
- Fila que dice: "200    7    1400"  → la CANTIDAD es 7   (NO 1400)
- Fila que dice: " 50   69   3450"  → la CANTIDAD es 69  (NO 3450)
- Fila que dice: "100   11   1100"  → la CANTIDAD es 11  (NO 1100)
- Fila que dice: "500    0       0"  → la CANTIDAD es 0

Responde ÚNICAMENTE con un JSON válido, sin texto adicional, sin bloques de código markdown:
{
  "1000": <cantidad fila 1>,
  "200a": <cantidad fila 2>,
  "500": <cantidad fila 3>,
  "100a": <cantidad fila 4>,
  "200b": <cantidad fila 5>,
  "50a": <cantidad fila 6>,
  "100b": <cantidad fila 7>,
  "50b": <cantidad fila 8>
}`;

    // gemini-2.5-pro: el modelo más potente y preciso de Google para visión
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=${geminiKey}`;

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

    const geminiRes = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!geminiRes.ok) {
      const errData = await geminiRes.text();
      console.error("Error Gemini API:", errData);
      return NextResponse.json(
        { error: `Error Gemini (${geminiRes.status}): ${errData}` },
        { status: 500 }
      );
    }

    const data = await geminiRes.json();
    const candidateText = data?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";

    console.log("Gemini 2.5 Pro response:", candidateText);

    const cleanedText = candidateText
      .replace(/```json/gi, "")
      .replace(/```/g, "")
      .trim();

    let resultado;
    try {
      resultado = JSON.parse(cleanedText);
    } catch (parseErr) {
      console.error("Error parseando respuesta:", cleanedText);
      return NextResponse.json(
        { error: `Gemini respondió algo inesperado: ${cleanedText}` },
        { status: 500 }
      );
    }

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
