import { NextResponse } from "next/server";
import { obtenerEstructuraDia } from "@/lib/googleSheets";

export const dynamic = "force-dynamic";

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const diaParam = searchParams.get("dia");
    const hojaParam = searchParams.get("hoja") || "pruebas";

    const resultado = await obtenerEstructuraDia(diaParam, hojaParam);
    return NextResponse.json({
      success: true,
      dia: resultado.dia,
      fecha: resultado.fecha,
      hoja: resultado.hoja,
      nombreHoja: resultado.nombreHoja,
      datos: resultado.datos
    });
  } catch (error) {
    console.error("Error en /api/today:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
