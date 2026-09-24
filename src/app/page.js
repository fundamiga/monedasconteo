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
  Video,
  Upload,
  RefreshCw,
  Save,
  CheckCircle2,
  AlertCircle,
  Table,
  Coins,
  ChevronRight,
  Calendar,
  Search,
  Check,
  X,
  ChevronDown,
  User,
  Settings,
  AlertTriangle,
  RotateCcw
} from "lucide-react";

export default function Home() {
  const [tab, setTab] = useState("scan"); // "scan" | "table"
  const [modoCamara, setModoCamara] = useState("live"); // "live" | "photo"
  // Estados de video en vivo
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [streamActive, setStreamActive] = useState(false);
  const [streamError, setStreamError] = useState("");

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
  // Datos del turno (inicia vacío para exigir selección)
  const [trabajador, setTrabajador] = useState("");
  // Opción de auto-limpiar campos tras guardar (Por defecto: ON)
  const [autoLimpiarAlGuardar, setAutoLimpiarAlGuardar] = useState(true);
  const [mostrarAjustes, setMostrarAjustes] = useState(false);
  // Modal de confirmación cuando no hay billetes o recaudo
  const [alertaGuardar, setAlertaGuardar] = useState(null);
  const [parqueadero, setParqueadero] = useState(PARQUEADEROS[0]);
  const [saving, setSaving] = useState(false);
  const [mensaje, setMensaje] = useState(null);

  // Selección de Hoja de Cálculo: 'principal' por defecto
  const [hojaSeleccionada, setHojaSeleccionada] = useState("principal");

  // Memoria de respaldo del último registro guardado o limpiado
  const [ultimoRespaldo, setUltimoRespaldo] = useState(null);

  const restaurarUltimoRespaldo = () => {
    if (!ultimoRespaldo) return;
    setMonedas(ultimoRespaldo.monedas || {});
    setBilletes(ultimoRespaldo.billetes || {});
    if (ultimoRespaldo.trabajador) setTrabajador(ultimoRespaldo.trabajador);
    if (ultimoRespaldo.parqueadero) setParqueadero(ultimoRespaldo.parqueadero);
    setMensaje({
      tipo: "success",
      texto: "↩️ ¡Datos del turno anterior recuperados en pantalla!"
    });
  };

  // Control de Fecha / Día del recaudo (Por defecto: día anterior)
  const [diaSeleccionado, setDiaSeleccionado] = useState(() => {
    const ayer = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return ayer.getDate();
  });
  const [fechaSheet, setFechaSheet] = useState("");

  // Modo Tabla
  const [tablaHoy, setTablaHoy] = useState([]);
  const [loadingTabla, setLoadingTabla] = useState(false);

  // Búsqueda y selector interactivo de trabajador
  const [busquedaTrabajador, setBusquedaTrabajador] = useState("");
  const [dropdownTrabajadorAbierto, setDropdownTrabajadorAbierto] = useState(false);
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);

  const getColorForLetter = (letter) => {
    const colors = [
      "bg-blue-600 text-blue-100",
      "bg-emerald-600 text-emerald-100",
      "bg-amber-600 text-amber-100",
      "bg-purple-600 text-purple-100",
      "bg-rose-600 text-rose-100",
      "bg-cyan-600 text-cyan-100",
      "bg-indigo-600 text-indigo-100",
      "bg-teal-600 text-teal-100",
      "bg-orange-600 text-orange-100",
      "bg-pink-600 text-pink-100",
      "bg-sky-600 text-sky-100",
      "bg-violet-600 text-violet-100"
    ];
    if (!letter) return colors[0];
    const code = letter.toUpperCase().charCodeAt(0);
    return colors[code % colors.length];
  };

  const normalizarTexto = (txt) => {
    return (txt || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  };

  const letrasDisponibles = Array.from(
    new Set(TRABAJADORES.map((t) => t[0]?.toUpperCase()).filter(Boolean))
  ).sort();

  const trabajadoresFiltrados = TRABAJADORES.filter((t) => {
    if (!busquedaTrabajador.trim()) return true;
    const q = normalizarTexto(busquedaTrabajador);
    return normalizarTexto(t).includes(q);
  }).sort((a, b) => {
    if (!busquedaTrabajador.trim()) return 0;
    const q = normalizarTexto(busquedaTrabajador);
    const aStarts = normalizarTexto(a).startsWith(q);
    const bStarts = normalizarTexto(b).startsWith(q);
    if (aStarts && !bStarts) return -1;
    if (!aStarts && bStarts) return 1;
    return a.localeCompare(b);
  });

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownTrabajadorAbierto(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, []);

  useEffect(() => {
    if (dropdownTrabajadorAbierto && searchInputRef.current) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 60);
    }
  }, [dropdownTrabajadorAbierto]);

  const fileInputRef = useRef(null);

  useEffect(() => {
    cargarTabla(diaSeleccionado, hojaSeleccionada);
  }, [diaSeleccionado, hojaSeleccionada]);

  // Manejo de la cámara en vivo
  useEffect(() => {
    if (tab === "scan" && modoCamara === "live") {
      iniciarCamaraEnVivo();
    } else {
      detenerCamaraEnVivo();
    }
    return () => detenerCamaraEnVivo();
  }, [tab, modoCamara]);

  const iniciarCamaraEnVivo = async () => {
    detenerCamaraEnVivo();
    setStreamError("");
    try {
      const constraints = {
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setStreamActive(true);
      }
    } catch (err) {
      console.warn("Error al acceder a cámara en vivo:", err);
      setStreamError("No se pudo iniciar la cámara en vivo. Puedes usar el modo 'Subir Foto'.");
      setStreamActive(false);
    }
  };

  const detenerCamaraEnVivo = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setStreamActive(false);
  };

  const capturarFrameEnVivo = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    const maxW = 720;
    const scale = Math.min(1, maxW / vw);
    canvas.width = Math.round(vw * scale);
    canvas.height = Math.round(vh * scale);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const base64Image = canvas.toDataURL("image/jpeg", 0.82);
    setImagePreview(base64Image);
    procesarEscaneo(base64Image);
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
  const comprimirImagen = (dataUrl, maxWidth = 960, quality = 0.82) => {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const scale = Math.min(1, maxWidth / img.width);
        const w = Math.round(img.width * scale);
        const h = Math.round(img.height * scale);
        const c = document.createElement("canvas");
        c.width = w;
        c.height = h;
        const ctx = c.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        resolve(c.toDataURL("image/jpeg", quality));
      };
      img.src = dataUrl;
    });
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (evt) => {
      const original = evt.target.result;
      // Comprimir antes de enviar para escaneo ultra-rápido
      const base64Image = await comprimirImagen(original, 960, 0.82);
      setImagePreview(base64Image);
      await procesarEscaneo(base64Image);
    };
    reader.readAsDataURL(file);
  };

  const parsearLineasCC358Fallback = (text) => {
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    const resultado = {
      1000: 0, "200a": 0, 500: 0, "100a": 0,
      "200b": 0, "50a": 0, "100b": 0, "50b": 0
    };
    const orden = ["1000", "200a", "500", "100a", "200b", "50a", "100b", "50b"];
    let idx = 0;

    for (const l of lines) {
      const lineaNormalizada = l.replace(/1\s*K/gi, "1000").replace(/O/gi, "0").replace(/o/gi, "0");
      const nums = lineaNormalizada.match(/\d+/g);
      if (!nums || nums.length === 0) continue;

      if (nums.length >= 2 && idx < orden.length) {
        resultado[orden[idx]] = parseInt(nums[1], 10) || 0;
        idx++;
      } else if (nums.length === 1 && idx < orden.length) {
        resultado[orden[idx]] = parseInt(nums[0], 10) || 0;
        idx++;
      }
    }
    return resultado;
  };

  const procesarEscaneo = async (base64Image) => {
    setScanning(true);
    setScanStatus("Escaneando pantalla con Visión Artificial...");
    setMensaje(null);

    // 1. Intentar con Gemini Vision API (Alta precisión)
    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: base64Image })
      });

      const data = await res.json();

      if (res.ok && data.monedas) {
        setMonedas((prev) => ({ ...prev, ...data.monedas }));
        setMensaje({
          tipo: "success",
          texto: `🎯 ¡Pantalla leída con IA (${data.model || "Gemini"})! Revisa los valores.`
        });
        setScanning(false);
        setScanStatus("");
        return;
      } else if (data.error) {
        console.warn("Error devuelto por Gemini:", data.error);
      }
    } catch (apiErr) {
      console.warn("Fallo API Gemini Vision:", apiErr);
    }

    // 2. Fallback con Tesseract.js en el navegador si no hay clave de Gemini
    try {
      setScanStatus("Procesando con lector local...");
      const Tesseract = (await import("tesseract.js")).default;
      const res = await Tesseract.recognize(base64Image, "eng", {
        logger: (m) => {
          if (m.status === "recognizing text") {
            setScanStatus(`Leyendo números: ${Math.round(m.progress * 100)}%`);
          }
        }
      });

      const texto = res.data.text || "";
      const monedasDetectadas = parsearLineasCC358Fallback(texto);

      setMonedas((prev) => ({ ...prev, ...monedasDetectadas }));
      setMensaje({
        tipo: "success",
        texto: "⚠️ IA no disponible. Los valores mostrados son una estimación — verifica y ajusta manualmente."
      });
    } catch (err) {
      console.error(err);
      setMensaje({
        tipo: "error",
        texto: `No se pudo leer la imagen automáticamente. Puedes digitar las cantidades a mano.`
      });
    } finally {
      setScanning(false);
      setScanStatus("");
    }
  };

  // ── GUARDAR EN GOOGLE SHEETS ──
  const handleGuardar = async (filaSeleccionada = null, forzar = false) => {
    // 1. Validar que haya un trabajador seleccionado
    if (!trabajador || !trabajador.trim()) {
      setMensaje({
        tipo: "error",
        texto: "⚠️ Debes seleccionar a un trabajador antes de guardar el turno."
      });
      setDropdownTrabajadorAbierto(true);
      return;
    }

    // 2. Alertas preventivas si falta recaudo o billetes (a menos que se fuerce)
    if (!forzar) {
      if (totalTurno === 0) {
        setAlertaGuardar({
          titulo: "⚠️ Recaudo en $0",
          mensaje: `El recaudo para "${trabajador}" está en $0 (sin monedas y sin billetes). ¿Deseas registrar este turno en ceros?`,
          botonConfirmar: "Sí, guardar en ceros",
          accion: () => ejecutarGuardado(filaSeleccionada)
        });
        return;
      }

      if (totalBilletes === 0) {
        setAlertaGuardar({
          titulo: "⚠️ ¿Guardar sin billetes?",
          mensaje: `Registraste ${fmtCOP(totalMonedas)} en monedas pero NO digitaste ningún billete ($0). ¿Seguro que deseas guardar sin billetes?`,
          botonConfirmar: "Sí, guardar sin billetes",
          accion: () => ejecutarGuardado(filaSeleccionada)
        });
        return;
      }

      if (totalMonedas === 0) {
        setAlertaGuardar({
          titulo: "⚠️ ¿Guardar sin monedas?",
          mensaje: `Registraste ${fmtCOP(totalBilletes)} en billetes pero NO hay monedas escaneadas ($0). ¿Seguro que deseas guardar sin monedas?`,
          botonConfirmar: "Sí, guardar sin monedas",
          accion: () => ejecutarGuardado(filaSeleccionada)
        });
        return;
      }
    }

    await ejecutarGuardado(filaSeleccionada);
  };

  const ejecutarGuardado = async (filaSeleccionada) => {
    setSaving(true);
    setMensaje(null);

    const trabajadorGuardado = trabajador;
    const totalGuardado = totalTurno;

    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fila: filaSeleccionada,
          trabajador: trabajadorGuardado,
          parqueadero,
          dia: diaSeleccionado,
          hoja: hojaSeleccionada,
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
        texto: `🎉 ¡Guardado en fila ${data.fila} para ${trabajadorGuardado}! Total: ${fmtCOP(totalGuardado)}${
          autoLimpiarAlGuardar ? " — Formulario limpiado para el siguiente turno." : ""
        }`
      });

      cargarTabla();

      // Guardar respaldo de seguridad por si necesita recuperar lo recién guardado
      setUltimoRespaldo({
        monedas: { ...monedas },
        billetes: { ...billetes },
        trabajador: trabajadorGuardado,
        parqueadero
      });

      // AUTO-LIMPIAR CAMPOS SI ESTÁ ACTIVADO (POR DEFECTO TRUE)
      if (autoLimpiarAlGuardar) {
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
        setTrabajador(""); // Se quita la persona para no confundir al siguiente turno
      }
    } catch (err) {
      console.error(err);
      setMensaje({ tipo: "error", texto: `Error al guardar: ${err.message}` });
    } finally {
      setSaving(false);
    }
  };

  const cargarTabla = async (dia = diaSeleccionado, hoja = hojaSeleccionada) => {
    setLoadingTabla(true);
    try {
      const res = await fetch(`/api/today?dia=${dia}&hoja=${hoja}`);
      const data = await res.json();
      if (data.datos) {
        setTablaHoy(data.datos);
        if (data.fecha) setFechaSheet(data.fecha);
      }
    } catch (err) {
      console.error("Error al cargar tabla:", err);
    } finally {
      setLoadingTabla(false);
    }
  };

  const limpiarTodo = (limpiarPersona = true) => {
    // Si habia datos cargados, respaldar por si se borro por equivocacion
    const tieneMonedas = Object.values(monedas || {}).some(v => Number(v) > 0);
    const tieneBilletes = Object.values(billetes || {}).some(v => Number(v) > 0);
    if (tieneMonedas || tieneBilletes || (trabajador && trabajador.trim())) {
      setUltimoRespaldo({
        monedas: { ...monedas },
        billetes: { ...billetes },
        trabajador: trabajador || "",
        parqueadero: parqueadero || ""
      });
    }

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
    if (limpiarPersona) {
      setTrabajador("");
    }
    setMensaje(null);
  };

  return (
    <main className="max-w-md mx-auto min-h-screen pb-20 flex flex-col justify-between">
      {/* ── CABECERA SUPERIOR ── */}
      <header className="sticky top-0 z-30 bg-slate-900/95 backdrop-blur-md border-b border-slate-800 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-emerald-500/20 p-2 rounded-xl text-emerald-400">
              <Coins className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-tight text-white">Recaudo CC358</h1>
              <p className="text-[11px] text-slate-400">Google Sheets Móvil</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {/* BOTÓN DISCRETO RECUPERAR ANTERIOR (Solo aparece si hay algo en memoria) */}
            {ultimoRespaldo && (
              <button
                type="button"
                onClick={restaurarUltimoRespaldo}
                className="text-xs bg-amber-950/70 border border-amber-600/60 hover:bg-amber-900 active:scale-95 text-amber-200 px-2 py-1.5 rounded-lg font-medium transition flex items-center gap-1 shadow-sm"
                title="Recuperar los datos del turno anterior"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span className="text-[11px]">Recuperar</span>
              </button>
            )}

            <button
              onClick={() => limpiarTodo(true)}
              className="text-xs bg-slate-800 hover:bg-slate-700 active:scale-95 text-slate-300 px-2.5 py-1.5 rounded-lg font-medium transition"
              title="Limpiar formulario"
            >
              Limpiar
            </button>

            {/* BOTÓN DE AJUSTES OCULTO (No ocupa espacio en pantalla) */}
            <button
              type="button"
              onClick={() => setMostrarAjustes(!mostrarAjustes)}
              className={`p-1.5 rounded-lg border transition ${
                mostrarAjustes
                  ? "bg-blue-600 border-blue-500 text-white shadow-sm"
                  : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
              }`}
              title="Ajustes de limpieza automática"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* PANEL DESPLEGABLE OCULTO (Solo aparece al presionar el engranaje ⚙️) */}
        {mostrarAjustes && (
          <div className="mt-3 pt-3 border-t border-slate-800/80 animate-in fade-in duration-150">
            <div className="bg-slate-950/90 border border-slate-800 rounded-xl p-3 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <span className="text-xs font-bold text-slate-200 block">
                    Auto-limpiar al guardar
                  </span>
                  <span className="text-[10px] text-slate-400 block leading-tight mt-0.5">
                    Borra monedas, billetes y trabajador al guardar para no confundir con el siguiente turno.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setAutoLimpiarAlGuardar(!autoLimpiarAlGuardar)}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    autoLimpiarAlGuardar ? "bg-emerald-600" : "bg-slate-700"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                      autoLimpiarAlGuardar ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              <div className="text-[10px] text-emerald-400 font-medium pt-1.5 border-t border-slate-800/60 flex items-center justify-between">
                <span>Estado: {autoLimpiarAlGuardar ? "ACTIVADO (Por defecto)" : "DESACTIVADO (Mantiene datos)"}</span>
                <button
                  type="button"
                  onClick={() => setMostrarAjustes(false)}
                  className="text-slate-400 hover:text-slate-200 underline"
                >
                  Ocultar
                </button>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* ── SELECTOR DE MODOS PRINCIPALES (TABS) ── */}
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
            {/* ── SELECTOR DE DESTINO: PRUEBAS vs PRINCIPAL ── */}
      <div className="px-4 pt-2">
        <div className={`p-2.5 rounded-xl border flex items-center justify-between transition-colors ${
          hojaSeleccionada === "principal"
            ? "bg-amber-950/40 border-amber-600/70 text-amber-200"
            : "bg-slate-900/90 border-slate-800 text-slate-300"
        }`}>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${
              hojaSeleccionada === "principal" ? "bg-amber-400 animate-pulse" : "bg-emerald-400"
            }`} />
            <div>
              <span className="text-[11px] font-bold block">
                {hojaSeleccionada === "principal" ? "⚠️ HOJA PRINCIPAL (PRODUCCIÓN)" : "📁 Hoja de Pruebas"}
              </span>
              <span className="text-[10px] text-slate-400">
                {hojaSeleccionada === "principal" ? "Ingresos Diarios Corregido" : "Copia segura para pruebas"}
              </span>
            </div>
          </div>

          <div className="flex bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[11px]">
            <button
              onClick={() => setHojaSeleccionada("pruebas")}
              className={`px-2.5 py-1 rounded-md font-bold transition ${
                hojaSeleccionada === "pruebas"
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Pruebas
            </button>
            <button
              onClick={() => setHojaSeleccionada("principal")}
              className={`px-2.5 py-1 rounded-md font-bold transition ${
                hojaSeleccionada === "principal"
                  ? "bg-amber-600 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Principal
            </button>
          </div>
        </div>
      </div>

      {/* ── SELECTOR DE DÍA DE RECAUDO ── */}
      <div className="px-4 pt-2">
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-blue-500/20 p-1.5 rounded-lg text-blue-400">
              <Calendar className="w-4 h-4" />
            </div>
            <div>
              <span className="text-[11px] font-bold text-slate-300 block">
                Fecha del Recaudo:
              </span>
              <span className="text-[10px] text-slate-500">
                {diaSeleccionado === new Date(Date.now() - 24 * 60 * 60 * 1000).getDate()
                  ? "Día anterior (por defecto)"
                  : diaSeleccionado === new Date().getDate()
                  ? "Día de hoy"
                  : `Día ${diaSeleccionado}`}
                {fechaSheet ? ` • ${fechaSheet}` : ""}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <label className="text-[11px] text-slate-400 font-medium">Día:</label>
            <select
              value={diaSeleccionado}
              onChange={(e) => setDiaSeleccionado(parseInt(e.target.value, 10))}
              className="bg-slate-950 border border-slate-700 text-blue-400 font-bold text-xs py-1 px-2.5 rounded-lg focus:outline-none focus:border-blue-500 cursor-pointer"
            >
              {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => {
                const esAyer = d === new Date(Date.now() - 24 * 60 * 60 * 1000).getDate();
                const esHoy = d === new Date().getDate();
                return (
                  <option key={d} value={d}>
                    Día {d} {esAyer ? "(Ayer)" : esHoy ? "(Hoy)" : ""}
                  </option>
                );
              })}
            </select>
          </div>
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
            {/* SUB-SELECTOR: CÁMARA EN VIVO vs SUBIR FOTO */}
            <div className="flex bg-slate-950/60 p-1 rounded-xl border border-slate-800 text-xs font-medium">
              <button
                onClick={() => setModoCamara("live")}
                className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
                  modoCamara === "live"
                    ? "bg-slate-800 text-blue-400 font-bold shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Video className="w-3.5 h-3.5" />
                Cámara en Vivo
              </button>
              <button
                onClick={() => setModoCamara("photo")}
                className={`flex-1 py-1.5 rounded-lg flex items-center justify-center gap-1.5 transition ${
                  modoCamara === "photo"
                    ? "bg-slate-800 text-blue-400 font-bold shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
                Tomar / Subir Foto
              </button>
            </div>

            {/* 1. MODO CÁMARA EN VIVO */}
            {modoCamara === "live" && (
              <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
                {/* Visor horizontal - proporción parecida a pantalla LCD CC358 */}
                <div className="relative w-full bg-black" style={{ aspectRatio: "21/8" }}>
                  <video
                    ref={videoRef}
                    playsInline
                    muted
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                  {/* Viñeta lateral y vertical para enfocar el centro */}
                  <div className="absolute inset-0 pointer-events-none" style={{ background: "linear-gradient(to right, rgba(0,0,0,0.5) 0%, transparent 15%, transparent 85%, rgba(0,0,0,0.5) 100%)" }} />
                  <div className="absolute inset-0 pointer-events-none" style={{ background: "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, transparent 20%, transparent 80%, rgba(0,0,0,0.5) 100%)" }} />
                  {/* Marco guía con esquinas */}
                  <div className="absolute inset-0 pointer-events-none flex items-center justify-center" style={{ padding: "12% 8%" }}>
                    <div className="relative w-full h-full">
                      <div className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 border-blue-400" />
                      <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 border-blue-400" />
                      <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 border-blue-400" />
                      <div className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 border-blue-400" />
                      <div className="absolute inset-x-0 bottom-1 flex justify-center">
                        <span className="text-[10px] text-blue-300/70 font-medium">Pantalla CC358</span>
                      </div>
                    </div>
                  </div>
                  {scanning && (
                    <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center gap-2 z-10">
                      <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
                      <p className="text-xs font-bold text-blue-200">{scanStatus}</p>
                    </div>
                  )}
                </div>
                <canvas ref={canvasRef} className="hidden" />
                <div className="p-3">
                  {streamError ? (
                    <p className="text-xs text-rose-400 text-center">{streamError}</p>
                  ) : (
                    <button
                      onClick={capturarFrameEnVivo}
                      disabled={scanning || !streamActive}
                      className="w-full py-3 bg-blue-600 hover:bg-blue-500 active:scale-[0.99] text-white font-bold rounded-xl shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2 transition disabled:opacity-50 text-sm"
                    >
                      <Camera className="w-4 h-4" />
                      ESCANEAR PANTALLA CC358
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* 2. MODO SUBIR O TOMAR FOTO NATIVA */}
            {modoCamara === "photo" && (
              <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {imagePreview ? (
                  <>
                    <div className="relative w-full bg-black" style={{ aspectRatio: "16/6" }}>
                      <img
                        src={imagePreview}
                        alt="Pantalla CC358"
                        className="absolute inset-0 w-full h-full object-contain"
                      />
                      {scanning && (
                        <div className="absolute inset-0 bg-black/75 flex flex-col items-center justify-center gap-2 z-10">
                          <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
                          <p className="text-xs font-bold text-blue-200">{scanStatus}</p>
                        </div>
                      )}
                    </div>
                    <div className="p-3">
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold rounded-xl flex items-center justify-center gap-2 transition"
                      >
                        <Camera className="w-4 h-4" />
                        Tomar otra foto
                      </button>
                    </div>
                  </>
                ) : (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full py-8 flex flex-col items-center justify-center gap-3 transition group hover:bg-slate-900"
                  >
                    <div className="w-14 h-14 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-600/30 group-hover:scale-105 transition">
                      <Camera className="w-7 h-7" />
                    </div>
                    <div className="text-center">
                      <span className="text-sm font-bold text-blue-200 block">Tomar o subir foto</span>
                      <span className="text-[11px] text-slate-400">Apunta a la pantalla azul CC358</span>
                    </div>
                  </button>
                )}
              </div>
            )}



            {/* 3. TABLA DE MONEDAS DETECTADAS (8 FILAS EXACTAS) */}
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

            {/* 4. ENTRADA MANUAL DE BILLETES */}
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

            {/* 5. ASIGNACIÓN DE TRABAJADOR Y PARQUEADERO */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
              {/* SELECTOR DE TRABAJADOR CON BÚSQUEDA PREDICTIVA, LETRAS Y COLORES */}
              <div className="relative" ref={dropdownRef}>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-blue-400" />
                    <span>Trabajador Responsable:</span>
                  </label>
                  <span className="text-[10px] text-slate-400 font-medium bg-slate-800/80 px-2 py-0.5 rounded-full">
                    {TRABAJADORES.length} disponibles
                  </span>
                </div>

                {/* Botón principal del selector (muestra el trabajador actual con color e inicial) */}
                <button
                  type="button"
                  onClick={() => {
                    setDropdownTrabajadorAbierto(!dropdownTrabajadorAbierto);
                    setBusquedaTrabajador("");
                  }}
                  className={`w-full flex items-center justify-between p-3 rounded-xl border transition text-left ${
                    dropdownTrabajadorAbierto
                      ? "bg-slate-950 border-blue-500 ring-2 ring-blue-500/20 shadow-lg shadow-blue-500/10"
                      : "bg-slate-950/90 border-slate-700/80 hover:border-slate-600 active:scale-[0.99]"
                  }`}
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm shadow-md shrink-0 ${
                        trabajador
                          ? getColorForLetter(trabajador[0])
                          : "bg-slate-800 border border-slate-700 text-slate-400"
                      }`}
                    >
                      {trabajador ? trabajador[0] : "?"}
                    </div>
                    <div className="truncate">
                      <span className={`text-xs block truncate ${trabajador ? "font-bold text-white" : "font-semibold text-amber-400"}`}>
                        {trabajador || "⚠️ Selecciona un trabajador..."}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {trabajador ? "Toca para cambiar o buscar por letra" : "Toca aquí para buscar y asignar"}
                      </span>
                    </div>
                  </div>
                  <ChevronDown
                    className={`w-4 h-4 text-slate-400 shrink-0 ml-2 transition-transform duration-200 ${
                      dropdownTrabajadorAbierto ? "rotate-180 text-blue-400" : ""
                    }`}
                  />
                </button>

                {/* DROPDOWN FLOTANTE INTERACTIVO */}
                {dropdownTrabajadorAbierto && (
                  <div className="absolute z-50 left-0 right-0 mt-2 bg-slate-900 border border-slate-700/90 rounded-2xl shadow-2xl overflow-hidden backdrop-blur-xl">
                    {/* Barra de búsqueda por texto */}
                    <div className="p-3 border-b border-slate-800 bg-slate-950/80 space-y-2">
                      <div className="relative flex items-center">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
                        <input
                          ref={searchInputRef}
                          type="text"
                          value={busquedaTrabajador}
                          onChange={(e) => setBusquedaTrabajador(e.target.value)}
                          placeholder="Escribe una letra o nombre (ej: DI, CAR, C)..."
                          className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-9 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                        />
                        {busquedaTrabajador && (
                          <button
                            type="button"
                            onClick={() => {
                              setBusquedaTrabajador("");
                              searchInputRef.current?.focus();
                            }}
                            className="absolute right-2.5 p-1 rounded-full text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Barra de selección rápida por letra inicial con scroll horizontal */}
                      <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px]">
                        <button
                          type="button"
                          onClick={() => setBusquedaTrabajador("")}
                          className={`px-2 py-1 rounded-md font-bold text-[10px] shrink-0 transition ${
                            !busquedaTrabajador
                              ? "bg-blue-600 text-white"
                              : "bg-slate-800 text-slate-400 hover:text-white"
                          }`}
                        >
                          TODOS
                        </button>
                        {letrasDisponibles.map((letra) => {
                          const activa =
                            busquedaTrabajador.toUpperCase() === letra;
                          return (
                            <button
                              key={letra}
                              type="button"
                              onClick={() => setBusquedaTrabajador(letra)}
                              className={`w-6 h-6 rounded-md font-bold text-[11px] shrink-0 flex items-center justify-center transition ${
                                activa
                                  ? "bg-blue-500 text-white shadow-sm ring-1 ring-white/30"
                                  : "bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white"
                              }`}
                            >
                              {letra}
                            </button>
                          );
                        })}
                      </div>

                      {/* Contador de resultados */}
                      <div className="flex items-center justify-between text-[10px] text-slate-400 px-0.5">
                        <span>
                          {trabajadoresFiltrados.length === 1
                            ? "1 trabajador encontrado"
                            : `${trabajadoresFiltrados.length} trabajadores encontrados`}
                        </span>
                        {busquedaTrabajador && (
                          <span className="text-blue-400 font-medium">
                            Filtro: "{busquedaTrabajador}"
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Lista con scroll de resultados */}
                    <div className="max-h-64 overflow-y-auto divide-y divide-slate-800/60 p-1.5 space-y-0.5">
                      {trabajadoresFiltrados.length === 0 ? (
                        <div className="py-8 px-4 text-center">
                          <p className="text-xs text-slate-400 font-medium">
                            No se encontró nadie con "{busquedaTrabajador}"
                          </p>
                          <button
                            type="button"
                            onClick={() => setBusquedaTrabajador("")}
                            className="mt-2 text-xs text-blue-400 hover:underline font-semibold"
                          >
                            Mostrar todos ({TRABAJADORES.length})
                          </button>
                        </div>
                      ) : (
                        trabajadoresFiltrados.map((t) => {
                          const isSelected = t === trabajador;
                          const initial = t[0] || "?";
                          const badgeColor = getColorForLetter(initial);

                          return (
                            <button
                              key={t}
                              type="button"
                              onClick={() => {
                                setTrabajador(t);
                                setDropdownTrabajadorAbierto(false);
                                setBusquedaTrabajador("");
                              }}
                              className={`w-full flex items-center justify-between p-2.5 rounded-xl transition text-left ${
                                isSelected
                                  ? "bg-blue-600/20 border border-blue-500/40 text-blue-200"
                                  : "hover:bg-slate-800/70 text-slate-200"
                              }`}
                            >
                              <div className="flex items-center gap-2.5 overflow-hidden">
                                <span
                                  className={`w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${badgeColor}`}
                                >
                                  {initial}
                                </span>
                                <span
                                  className={`text-xs font-semibold truncate ${
                                    isSelected
                                      ? "text-blue-300 font-bold"
                                      : "text-slate-200"
                                  }`}
                                >
                                  {t}
                                </span>
                              </div>
                              {isSelected && (
                                <Check className="w-4 h-4 text-blue-400 shrink-0 ml-2" />
                              )}
                            </button>
                          );
                        })
                      )}
                    </div>

                    {/* Botón cerrar al fondo */}
                    <div className="p-2 bg-slate-950/90 border-t border-slate-800/80 text-center">
                      <button
                        type="button"
                        onClick={() => setDropdownTrabajadorAbierto(false)}
                        className="text-xs text-slate-400 hover:text-slate-200 font-medium py-1 px-4 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition"
                      >
                        Cerrar lista
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 block mb-1">
                  Parqueadero:
                </label>
                <select
                  value={parqueadero}
                  onChange={(e) => setParqueadero(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl py-2.5 px-3 text-xs font-medium text-slate-200 focus:outline-none focus:border-blue-500"
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
                className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white font-bold rounded-xl shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-2 transition disabled:opacity-50 text-sm"
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

          {/* MODAL DE ALERTA CUANDO FALTA RECAUDO O BILLETES */}
      {alertaGuardar && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-5 max-w-sm w-full shadow-2xl space-y-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">
                  {alertaGuardar.titulo}
                </h3>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                  {alertaGuardar.mensaje}
                </p>
              </div>
            </div>

            <div className="bg-slate-950/70 rounded-xl p-3 border border-slate-800 space-y-1.5 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Trabajador:</span>
                <span className="font-bold text-slate-200">{trabajador || "No asignado"}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Monedas:</span>
                <span className="font-semibold text-emerald-400">{fmtCOP(totalMonedas)}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Billetes:</span>
                <span className="font-semibold text-amber-400">{fmtCOP(totalBilletes)}</span>
              </div>
              <div className="flex justify-between pt-1.5 border-t border-slate-800 text-white font-bold">
                <span>Total Turno:</span>
                <span className="text-emerald-400">{fmtCOP(totalTurno)}</span>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={() => setAlertaGuardar(null)}
                className="flex-1 py-2.5 px-3 bg-slate-800 hover:bg-slate-700 active:scale-95 text-slate-200 text-xs font-semibold rounded-xl transition"
              >
                Volver y corregir
              </button>
              <button
                type="button"
                onClick={() => {
                  const accion = alertaGuardar.accion;
                  setAlertaGuardar(null);
                  if (accion) accion();
                }}
                className="flex-1 py-2.5 px-3 bg-amber-600 hover:bg-amber-500 active:scale-95 text-white text-xs font-bold rounded-xl transition shadow-lg shadow-amber-600/30"
              >
                {alertaGuardar.botonConfirmar || "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
