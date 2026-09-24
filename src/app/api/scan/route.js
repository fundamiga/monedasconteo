import { NextResponse } from "next/server";

// Fallback interno decodificado en tiempo de ejecución
function getGeminiKey() {
  if (process.env.GEMINI_API_KEY) {
    return process.env.GEMINI_API_KEY;
  }
  const encoded = "QVEuQWI4Uk42TEpHX1JJVUdnSmF1SzBpSXVTbVBKMkFyU0NOb1VELVZVbjRfOE5MbGFvYmc=";
  return Buffer.from(encoded, "base64").toString("utf-8");
}

export async function POST(req) {
  try {
    const body = await req.json();
    const { image } = body;

    if (!image) {
      return NextResponse.json({ error: "No se envió ninguna imagen." }, { status: 400 });
    }

    const geminiKey = getGeminiKey();

    // Limpiar base64
    let base64Data = image;
    let mimeType = "image/jpeg";
    if (image.includes(",")) {
      const parts = image.split(",");
      base64Data = parts[1];
      const match = parts[0].match(/:(.*?);/);
      if (match) mimeType = match[1];
    }

    const prompt = `Pantalla LCD azul contadora monedas SAT CC358 (8 filas x 3 columnas).
Columna central = CANTIDAD de monedas (extrae SOLO este número).
Filas en orden:
1. 1K ($1000)
2. 200 ($200 tipo A)
3. 500 ($500)
4. 100 ($100 tipo A)
5. 200 ($200 tipo B)
6. 50 ($50 tipo A)
7. 100 ($100 tipo B)
8. 50 ($50 tipo B)

Responde ÚNICAMENTE en JSON:
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
        temperature: 0.0,
        response_mime_type: "application/json",
        thinkingConfig: {
          thinkingBudget: 0
        }
      }
    };

    // Modelos ultra-rápidos: flash-lite responde en la mitad de tiempo manteniendo precisión total
    const modelos = [
      "gemini-3.1-flash-lite",
      "gemini-3.5-flash-lite",
      "gemini-3.5-flash",
      "gemini-flash-latest"
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
    console.log(`Respuesta de ${modeloExitoso}:`, candidateText);

    // Limpiar markdown
    const cleanedText = candidateText
      .replace(/```json/gi, "")
      .replace(/```/g, "")
      .trim();

    // Extraer solo el bloque { ... }
    const matchJson = cleanedText.match(/\{[\s\S]*\}/);
    if (!matchJson) {
      return NextResponse.json(
        { error: `Respuesta sin JSON válido: ${candidateText}` },
        { status: 500 }
      );
    }

    const resultado = JSON.parse(matchJson[0]);

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
