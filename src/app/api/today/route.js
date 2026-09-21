import { NextResponse } from "next/server";
import { obtenerEstructuraHoy } from "@/lib/googleSheets";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const estructura = await obtenerEstructuraHoy();
    return NextResponse.json({ success: true, datos: estructura });
  } catch (error) {
    console.error("Error en /api/today:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
