import { NextResponse } from "next/server";

// Almacén en memoria global para compartir el último conteo entre peticiones
// Al estar en globalThis, persiste en memoria en la instancia del servidor
if (!globalThis._ultimoConteoCC358) {
  globalThis._ultimoConteoCC358 = null;
}

export async function POST(req) {
  try {
    const body = await req.json();
    const { monedas = {}, total = 0, timestamp = Date.now() } = body;

    const conteo = {
      monedas,
      total: Number(total) || 0,
      timestamp: Number(timestamp) || Date.now(),
      recibidoEn: new Date().toISOString()
    };

    globalThis._ultimoConteoCC358 = conteo;

    return NextResponse.json({
      success: true,
      mensaje: "Conteo sincronizado correctamente",
      conteo
    });
  } catch (error) {
    console.error("Error en POST /api/cc358-sync:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const since = searchParams.get("since");

    const conteo = globalThis._ultimoConteoCC358;

    if (!conteo) {
      return NextResponse.json({ disponible: false, conteo: null });
    }

    // Si el cliente pide solo conteos más nuevos que su última lectura
    if (since && conteo.timestamp <= Number(since)) {
      return NextResponse.json({ disponible: false, conteo: null });
    }

    return NextResponse.json({
      disponible: true,
      conteo
    });
  } catch (error) {
    console.error("Error en GET /api/cc358-sync:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
