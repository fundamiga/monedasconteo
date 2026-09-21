"use client";

import { useState, useEffect, useRef } from "react";
import {
  PARQUEADEROS,
  TRABAJADORES,
  DENOM_MONEDAS,
  DENOM_BILLETES
} from "@/lib/constants";
import {
  Camera,
  Upload,
  RefreshCw,
  Save,
  CheckCircle2,
  AlertCircle,
  Settings,
  Table,
  Coins,
  ChevronRight
} from "lucide-react";

export default function Home() {
  const [tab, setTab] = useState("scan"); // "scan" | "table"
  const [apiKey, setApiKey] = useState("");
  const [showSettings, setShowSettings] = useState(false);

  // Estados de captura y análisis
  const [imagePreview, setImagePreview] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState("");

  // Datos del conteo
  const [monedas, setMonedas] = useState({
    1000: 0,
    "200a": 0,
    500: 0,
    "100a": 0,
    "200b": 0,
    "50a": 0,
    "100b": 0,
    "50b": 0
  });

  const [billetes, setBilletes] = useState({
    2000: 0,
    5000: 0,
    10000: 0,
    20000: 0,
    50000: 0,
    100000: 0
  });

  // Datos del turno
  const [trabajador, setTrabajador] = useState(TRABAJADORES[0]);
  const [parqueadero, setParqueadero] = useState(PARQUEADEROS[0]);
  const [saving, setSaving] = useState(false);
  const [mensaje, setMensaje] = useState(null);

  // Modo Tabla
  const [tablaHoy, setTablaHoy] = useState([]);
  const [loadingTabla, setLoadingTabla] = useState(false);

  const fileInputRef = useRef(null);

  useEffect(() => {
    // Cargar API Key guardada en el navegador si existe
    const savedKey = localStorage.getItem("cc358_gemini_key");
    if (savedKey) setApiKey(savedKey);

    cargarTabla();
  }, []);

  const handleSaveApiKey = (key) => {
    setApiKey(key);
    localStorage.setItem("cc358_gemini_key", key);
    setShowSettings(false);
  };

  // Cálculos de totales
  const totalMonedas = DENOM_MONEDAS.reduce(
    (acc, m) => acc + (parseInt(monedas[m.key], 10) || 0) * m.valor,
    0
  );

  const totalBilletes = DENOM_BILLETES.reduce(
    (acc, b) => acc + (parseInt(billetes[b.key], 10) || 0) * b.valor,
    0
  );

  const totalTurno = totalMonedas + totalBilletes;

  const fmtCOP = (val) => `$ ${val.toLocaleString("es-CO")}`;

  // ── MANEJO DE FOTO Y ESCANEO ──
  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Crear vista previa
    const reader = new FileReader();
    reader.onload = async (evt) => {
      const base64Image = evt.target.result;
      setImagePreview(base64Image);
      await procesarEscaneo(base64Image);
    };
    reader.readAsDataURL(file);
  };

  const procesarEscaneo = async (base64Image) => {
    setScanning(true);
    setScanStatus("Analizando pantalla de la CC358 con IA...");
    setMensaje(null);

    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: base64Image, apiKey })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Error al procesar la imagen");
      }

      if (data.monedas) {
        setMonedas((prev) => ({ ...prev, ...data.monedas }));
        setMensaje({
          tipo: "success",
          texto: "✅ ¡Pantalla leída exitosamente! Revisa las cantidades abajo."
        });
      }
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: `Error en escaneo: ${err.message}` });
    } finally {
      setScanning(false);
      setScanStatus("");
    }
  };

  // ── GUARDAR EN GOOGLE SHEETS ──
  const handleGuardar = async (filaSeleccionada = null) => {
    setSaving(true);
    setMensaje(null);

    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fila: filaSeleccionada,
          trabajador,
          parqueadero,
          monedas,
          billetes
        })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Error al guardar en el Sheet");
      }

      setMensaje({
        tipo: "success",
        texto: `🎉 ¡Guardado exitosamente en fila ${data.fila}! Total: ${fmtCOP(totalTurno)}`
      });

      // Recargar tabla para reflejar el cambio
      cargarTabla();
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: `Error al guardar: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const cargarTabla = async () => {
    setLoadingTabla(true);
    try {
      const res = await fetch("/api/today");
      const data = await res.json();
      if (data.datos) {
        setTablaHoy(data.datos);
      }
    } catch (err) {
      console.error("Error al cargar tabla:", err);
    } finally {
      setLoadingTabla(false);
    }
  };

  const limpiarTodo = () => {
    setMonedas({
      1000: 0,
      "200a": 0,
      500: 0,
      "100a": 0,
      "200b": 0,
      "50a": 0,
      "100b": 0,
      "50b": 0
    });
    setBilletes({
      2000: 0,
      5000: 0,
      10000: 0,
      20000: 0,
      50000: 0,
      100000: 0
    });
    setImagePreview(null);
    setMensaje(null);
  };

  return (
    <main className="max-w-md mx-auto min-h-screen pb-20 flex flex-col justify-between">
      {/* ── CABECERA SUPERIOR ── */}
      <header className="sticky top-0 z-30 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="bg-emerald-500/20 p-2 rounded-xl text-emerald-400">
            <Coins className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-sm tracking-tight text-white">Recaudo CC358</h1>
            <p className="text-[11px] text-slate-400">Google Sheets Móvil</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={limpiarTodo}
            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1.5 rounded-lg font-medium transition"
          >
            Limpiar
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ── SELECTOR DE MODOS (TABS) ── */}
      <div className="px-4 pt-3">
        <div className="bg-slate-900 p-1 rounded-xl flex gap-1 border border-slate-800">
          <button
            onClick={() => setTab("scan")}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition ${
              tab === "scan"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Camera className="w-4 h-4" />
            Escanear Pantalla
          </button>
          <button
            onClick={() => setTab("table")}
            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition ${
              tab === "table"
                ? "bg-blue-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Table className="w-4 h-4" />
            Tocar Fila (Excel)
          </button>
        </div>
      </div>

      {/* ── NOTIFICACIONES FLOTANTES ── */}
      {mensaje && (
        <div className="px-4 pt-3">
          <div
            className={`p-3 rounded-xl border flex items-start gap-2.5 text-xs ${
              mensaje.tipo === "success"
                ? "bg-emerald-950/80 border-emerald-800/80 text-emerald-200"
                : "bg-rose-950/80 border-rose-800/80 text-rose-200"
            }`}
          >
            {mensaje.tipo === "success" ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            )}
            <p className="font-medium leading-relaxed">{mensaje.texto}</p>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────── */}
      {/* ── CONTENIDO PRINCIPAL SEGÚN TAB ── */}
      {/* ────────────────────────────────────────────────────────── */}
      <div className="p-4 space-y-4 flex-1">
        {tab === "scan" ? (
          <>
            {/* 1. BOTÓN DE CÁMARA / CAPTURA */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 text-center">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={handleFileChange}
                className="hidden"
              />

              {imagePreview ? (
                <div className="relative rounded-xl overflow-hidden border border-slate-700 max-h-48 mb-3 bg-black">
                  <img
                    src={imagePreview}
                    alt="Pantalla CC358"
                    className="w-full h-48 object-cover opacity-90"
                  />
                  {scanning && (
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex flex-col items-center justify-center text-white">
                      <RefreshCw className="w-7 h-7 text-blue-400 animate-spin mb-2" />
                      <p className="text-xs font-semibold text-blue-200">{scanStatus}</p>
                    </div>
                  )}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="absolute bottom-2 right-2 bg-slate-900/90 text-slate-200 text-xs px-2.5 py-1 rounded-lg border border-slate-700 flex items-center gap-1 font-medium"
                  >
                    <Camera className="w-3.5 h-3.5" />
                    Tomar otra
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full py-7 border-2 border-dashed border-blue-500/50 hover:border-blue-400 bg-blue-500/10 hover:bg-blue-500/15 rounded-xl flex flex-col items-center justify-center gap-2 transition group"
                >
                  <div className="w-12 h-12 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-600/30 group-hover:scale-105 transition">
                    <Camera className="w-6 h-6" />
                  </div>
                  <span className="text-sm font-semibold text-blue-200">
                    Tomar Foto a la Pantalla
                  </span>
                  <span className="text-[11px] text-slate-400">
                    La IA leerá las 8 denominaciones automáticamente
                  </span>
                </button>
              )}
            </div>

            {/* 2. TABLA DE MONEDAS DETECTADAS */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <span className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                  Monedas (CC358)
                </span>
                <span className="text-sm font-bold text-blue-300">
                  {fmtCOP(totalMonedas)}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-3">
                {DENOM_MONEDAS.map((m) => (
                  <div
                    key={m.key}
                    className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-2 flex items-center justify-between"
                  >
                    <div>
                      <span className="text-xs font-bold text-slate-200 block">
                        {m.label}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {fmtCOP((parseInt(monedas[m.key], 10) || 0) * m.valor)}
                      </span>
                    </div>
                    <input
                      type="number"
                      min="0"
                      value={monedas[m.key] || ""}
                      placeholder="0"
                      onChange={(e) =>
                        setMonedas({ ...monedas, [m.key]: parseInt(e.target.value, 10) || 0 })
                      }
                      className="w-14 bg-slate-900 border border-slate-700 rounded-lg py-1 px-2 text-right text-xs font-bold text-emerald-400 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* 3. ENTRADA MANUAL DE BILLETES */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                  Billetes (Manual)
                </span>
                <span className="text-sm font-bold text-amber-300">
                  {fmtCOP(totalBilletes)}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-3">
                {DENOM_BILLETES.map((b) => (
                  <div
                    key={b.key}
                    className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-2 flex flex-col gap-1"
                  >
                    <span className="text-[11px] font-bold text-slate-300">
                      {b.label}
                    </span>
                    <input
                      type="number"
                      min="0"
                      value={billetes[b.key] || ""}
                      placeholder="0"
                      onChange={(e) =>
                        setBilletes({
                          ...billetes,
                          [b.key]: parseInt(e.target.value, 10) || 0
                        })
                      }
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg py-1 px-2 text-right text-xs font-bold text-amber-400 focus:outline-none focus:border-amber-500"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* 4. ASIGNACIÓN DE TRABAJADOR Y PARQUEADERO */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1">
                  Trabajador:
                </label>
                <select
                  value={trabajador}
                  onChange={(e) => setTrabajador(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl py-2 px-3 text-xs font-medium text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  {TRABAJADORES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1">
                  Parqueadero:
                </label>
                <select
                  value={parqueadero}
                  onChange={(e) => setParqueadero(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl py-2 px-3 text-xs font-medium text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  {PARQUEADEROS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              {/* TOTAL DESTACADO */}
              <div className="bg-emerald-950/40 border border-emerald-800/60 rounded-xl p-3 flex items-center justify-between mt-2">
                <span className="text-xs font-bold text-emerald-300">TOTAL TURNO:</span>
                <span className="text-lg font-black text-emerald-400">
                  {fmtCOP(totalTurno)}
                </span>
              </div>

              {/* BOTÓN GUARDAR */}
              <button
                onClick={() => handleGuardar()}
                disabled={saving}
                className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white font-bold rounded-xl shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2 transition disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Guardando en Google Sheets...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    GUARDAR EN GOOGLE SHEETS
                  </>
                )}
              </button>
            </div>
          </>
        ) : (
          /* ── MODO TABLA (TOCAR FILA DESDE EL CELULAR) ── */
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-400">
                Toca una fila para asignarle el conteo actual
              </span>
              <button
                onClick={cargarTabla}
                disabled={loadingTabla}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-400 hover:text-white"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingTabla ? "animate-spin" : ""}`} />
              </button>
            </div>

            {totalTurno > 0 && (
              <div className="bg-blue-950/50 border border-blue-800/80 rounded-xl p-3 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-blue-300 block font-medium">
                    Conteo listo para asignar:
                  </span>
                  <span className="text-xs font-bold text-white">
                    {trabajador}
                  </span>
                </div>
                <span className="text-sm font-black text-blue-400">
                  {fmtCOP(totalTurno)}
                </span>
              </div>
            )}

            {tablaHoy.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                {loadingTabla ? "Cargando filas del Sheet..." : "No se encontraron filas."}
              </div>
            ) : (
              tablaHoy.map((p, idx) => (
                <div
                  key={idx}
                  className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden"
                >
                  <div className="bg-slate-800/80 px-3.5 py-2 flex items-center justify-between border-b border-slate-700/60">
                    <span className="font-bold text-xs text-blue-300">
                      📍 {p.parqueadero}
                    </span>
                    {p.total && (
                      <span className="text-[11px] font-semibold text-emerald-400">
                        {fmtCOP(p.total)}
                      </span>
                    )}
                  </div>

                  <div className="divide-y divide-slate-800/60">
                    {p.filas.map((f) => (
                      <div
                        key={f.fila}
                        className={`p-3 flex items-center justify-between transition ${
                          f.vacia ? "bg-slate-950/40" : "bg-slate-950/80"
                        }`}
                      >
                        <div>
                          <span className="text-xs font-semibold block text-slate-200">
                            {f.trabajador || (
                              <span className="text-slate-500 font-normal italic">
                                (Fila {f.fila} disponible)
                              </span>
                            )}
                          </span>
                          {f.total_turno && (
                            <span className="text-[10px] text-emerald-400 font-medium">
                              Total: {fmtCOP(f.total_turno)}
                            </span>
                          )}
                        </div>

                        <button
                          onClick={() => {
                            setParqueadero(p.parqueadero);
                            if (f.trabajador) setTrabajador(f.trabajador);
                            handleGuardar(f.fila);
                          }}
                          className={`text-xs font-bold px-3 py-1.5 rounded-lg flex items-center gap-1 transition ${
                            f.vacia
                              ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                              : "bg-slate-800 hover:bg-slate-700 text-slate-300"
                          }`}
                        >
                          {f.vacia ? "Asignar aquí" : "Sobrescribir"}
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* ── MODAL DE CONFIGURACIÓN ── */}
      {showSettings && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-5 space-y-4">
            <h2 className="font-bold text-sm text-white">Configuración de Gemini Vision</h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Para leer la pantalla con IA gratis, ingresa tu clave API de Google AI Studio:
            </p>

            <input
              type="password"
              placeholder="AIzaSy..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl py-2 px-3 text-xs font-mono text-white focus:outline-none focus:border-blue-500"
            />

            <div className="flex gap-2 justify-end pt-2">
              <button
                onClick={() => setShowSettings(false)}
                className="text-xs px-3 py-1.5 text-slate-400 hover:text-white"
              >
                Cerrar
              </button>
              <button
                onClick={() => handleSaveApiKey(apiKey)}
                className="text-xs px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 font-bold rounded-lg text-white"
              >
                Guardar Clave
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
