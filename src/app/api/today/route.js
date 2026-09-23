import { NextResponse } from "next/server";
import { obtenerEstructuraDia } from "@/lib/googleSheets";

export const dynamic = "force-dynamic";

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const diaParam = searchParams.get("dia");

    const resultado = await obtenerEstructuraDia(diaParam);
    return NextResponse.json({
      success: true,
      dia: resultado.dia,
      fecha: resultado.fecha,
      datos: resultado.datos
    });
  } catch (error) {
    console.error("Error en /api/today:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
