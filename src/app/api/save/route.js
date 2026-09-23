import { NextResponse } from "next/server";
import { guardarFilaSheet, obtenerEstructuraDia, normalizar } from "@/lib/googleSheets";

export async function POST(req) {
  try {
    const body = await req.json();
    let { fila, trabajador, parqueadero, dia, monedas = {}, billetes = {} } = body;

    // Si no se proporcionó el número de fila exacto, buscarlo en la estructura del día seleccionado
    if (!fila) {
      const resEstructura = await obtenerEstructuraDia(dia);
      const estructura = resEstructura.datos || [];
      const pNorm = normalizar(parqueadero);
      const tNorm = normalizar(trabajador);

      let filaEncontrada = null;
      let filaVacia = null;

      for (const p of estructura) {
        if (normalizar(p.parqueadero) === pNorm) {
          for (const f of p.filas) {
            if (f.vacia && filaVacia === null) {
              filaVacia = f.fila;
            }
            if (!f.vacia && normalizar(f.trabajador).includes(tNorm)) {
              filaEncontrada = f.fila;
              break;
            }
          }
          break;
        }
      }

      fila = filaEncontrada || filaVacia;

      if (!fila) {
        return NextResponse.json(
          { error: `No se encontró espacio disponible para ${trabajador} en ${parqueadero} (${resEstructura.fecha || "Día " + dia}).` },
          { status: 400 }
        );
      }
    }

    await guardarFilaSheet({ fila, trabajador, monedas, billetes });

    return NextResponse.json({
      success: true,
      fila,
      mensaje: `Guardado exitosamente en fila ${fila}`
    });
  } catch (error) {
    console.error("Error en /api/save:", error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
