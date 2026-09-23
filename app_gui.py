"""
Interfaz Gráfica Principal - Sistema de Recaudo CC358
Monedas automáticas desde CC358 + Billetes manuales → Google Sheets
"""

import threading
import customtkinter as ctk
import serial.tools.list_ports
from datetime import datetime

from config.datos import TRABAJADORES, PARQUEADEROS
from serial_reader.cc358_reader import CC358Reader
from sheets.google_sheets import (
    conectar_sheet, buscar_fila_trabajador,
    guardar_conteo, calcular_totales, obtener_fecha_hoy
)
from ventana_conteo import VentanaConteo
from vista_tabla import VentanaTablaExcel
from modo_camara import VentanaCamaraOCR

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def fmt_cop(valor):
    return f"$ {valor:,.0f}".replace(",", ".")


class AppCC358(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Recaudo CC358 → Google Sheets")
        self.geometry("1100x750")
        self.minsize(950, 650)

        # Estado
        self.reader = None
        self.worksheet = None
        self.monedas_actuales = {}
        self.modo_rapido = False          # Modo ventana emergente automática
        self._ventana_abierta = False     # Para no abrir dos ventanas a la vez
        self.ventana_tabla = None         # Ventana opcional de Modo Tabla

        self._crear_ui()
        self._actualizar_puertos()

    # ─────────────────────────────────────────
    # CONSTRUCCIÓN DE LA UI
    # ─────────────────────────────────────────

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=5)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(1, weight=1)

        self._crear_barra_conexion()
        self._crear_panel_registro()
        self._crear_panel_consola()

    def _crear_barra_conexion(self):
        top = ctk.CTkFrame(self, corner_radius=10)
        top.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 8), sticky="ew")

        ctk.CTkLabel(top, text="🪙 Recaudo CC358",
                     font=ctk.CTkFont(size=19, weight="bold")).pack(side="left", padx=15, pady=10)

        # Puerto COM
        self.combo_puertos = ctk.CTkComboBox(top, values=["Buscando..."], width=200)
        self.combo_puertos.pack(side="left", padx=6, pady=10)
        ctk.CTkButton(top, text="🔄", width=34,
                      command=self._actualizar_puertos).pack(side="left", padx=2)

        ctk.CTkLabel(top, text="Baud:").pack(side="left", padx=(10, 3))
        self.combo_baud = ctk.CTkComboBox(
            top, values=["9600", "4800", "19200", "38400", "115200"], width=80)
        self.combo_baud.set("9600")
        self.combo_baud.pack(side="left", padx=3, pady=10)

        # Botón Simulación
        self.btn_sim = ctk.CTkButton(
            top, text="▶ Simulación", width=110,
            fg_color="#6B7280", hover_color="#4B5563",
            command=self._toggle_simulacion)
        self.btn_sim.pack(side="left", padx=6, pady=10)

        # Botón MODO RÁPIDO (Popup automático)
        self.btn_modo_rapido = ctk.CTkButton(
            top, text="⚡ Modo Rapido", width=115,
            fg_color="#B45309", hover_color="#92400E",
            font=ctk.CTkFont(weight="bold"),
            command=self._toggle_modo_rapido)
        self.btn_modo_rapido.pack(side="left", padx=4, pady=10)

        # Botón MODO TABLA EXCEL (Ventana interactiva de filas)
        self.btn_modo_tabla = ctk.CTkButton(
            top, text="📊 Modo Tabla", width=115,
            fg_color="#2563EB", hover_color="#1D4ED8",
            font=ctk.CTkFont(weight="bold"),
            command=self._abrir_modo_tabla)
        self.btn_modo_tabla.pack(side="left", padx=4, pady=10)

        # Botón MODO CÁMARA OCR
        self.btn_modo_camara = ctk.CTkButton(
            top, text="📷 Modo Cámara", width=120,
            fg_color="#0D9488", hover_color="#0F766E",
            font=ctk.CTkFont(weight="bold"),
            command=self._abrir_modo_camara)
        self.btn_modo_camara.pack(side="left", padx=4, pady=10)

        # Botón Conectar
        self.btn_conectar = ctk.CTkButton(
            top, text="Conectar COM", width=120,
            fg_color="#2FA572", hover_color="#1E7B54",
            font=ctk.CTkFont(weight="bold"),
            command=self._toggle_conexion)
        self.btn_conectar.pack(side="right", padx=8, pady=10)

        self.lbl_status = ctk.CTkLabel(
            top, text="🔴 Desconectado",
            text_color="#FF6B6B",
            font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_status.pack(side="right", padx=8)

        # Botón GUARDAR siempre visible en la barra superior
        self.btn_guardar_top = ctk.CTkButton(
            top, text="💾 GUARDAR",
            fg_color="#107C41", hover_color="#0B5C30",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=130, height=36,
            command=self._guardar_en_sheets)
        self.btn_guardar_top.pack(side="right", padx=6, pady=10)

        # Botón LIMPIAR / DESDE CERO
        ctk.CTkButton(
            top, text="🔄 Limpiar",
            fg_color="#7C3AED", hover_color="#5B21B6",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=95, height=36,
            command=self._limpiar_todo).pack(side="right", padx=4, pady=10)

    def _abrir_modo_camara(self):
        """Abre la ventana de captura con cámara web y OCR."""
        self._log("Abriendo Modo Cámara con Visión Artificial...")
        VentanaCamaraOCR(self, callback_datos=self._on_datos_recibidos, callback_log=self._log)

    def _abrir_modo_tabla(self):
        """Abre la ventana interactiva del Modo Tabla Excel."""
        if self.ventana_tabla is None or not self.ventana_tabla.winfo_exists():
            self.ventana_tabla = VentanaTablaExcel(self, callback_log=self._log)
            if self.monedas_actuales:
                self.ventana_tabla.recibir_conteo_monedas(self.monedas_actuales)
            self._log("Modo Tabla abierto en ventana independiente.")
        else:
            self.ventana_tabla.lift()
            self.ventana_tabla.focus()

    def _crear_panel_registro(self):
        left = ctk.CTkFrame(self, corner_radius=10)
        left.grid(row=1, column=0, padx=(15, 7), pady=(0, 15), sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="📋 Registro de Turno",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=15, pady=(15, 8))

        # ── Trabajador y Parqueadero ──
        seleccion = ctk.CTkFrame(left, fg_color="transparent")
        seleccion.pack(fill="x", padx=15, pady=4)
        seleccion.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(seleccion, text="Trabajador:").grid(row=0, column=0, sticky="w", pady=3)
        self.combo_trabajador = ctk.CTkComboBox(
            seleccion, values=TRABAJADORES, width=280)
        self.combo_trabajador.set(TRABAJADORES[0])
        self.combo_trabajador.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)

        ctk.CTkLabel(seleccion, text="Parqueadero:").grid(row=1, column=0, sticky="w", pady=3)
        self.combo_parqueadero = ctk.CTkComboBox(
            seleccion, values=PARQUEADEROS, width=280)
        self.combo_parqueadero.set(PARQUEADEROS[0])
        self.combo_parqueadero.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=3)

        ctk.CTkLabel(seleccion, text="Fecha Recaudo:").grid(row=2, column=0, sticky="w", pady=3)
        fecha_frame = ctk.CTkFrame(seleccion, fg_color="transparent")
        fecha_frame.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=3)

        from datetime import datetime, timedelta
        ayer_dia = (datetime.now() - timedelta(days=1)).day
        dias_opciones = [f"Dia {d} (Ayer)" if d == ayer_dia else f"Dia {d} (Hoy)" if d == datetime.now().day else f"Dia {d}" for d in range(1, 32)]
        
        self.combo_dia = ctk.CTkComboBox(
            fecha_frame, values=dias_opciones, width=160,
            command=self._on_cambio_dia)
        self.combo_dia.set(f"Dia {ayer_dia} (Ayer)")
        self.combo_dia.pack(side="left")

        self.lbl_fecha = ctk.CTkLabel(
            fecha_frame, text=obtener_fecha_hoy(ayer_dia),
            text_color="#10B981", font=ctk.CTkFont(weight="bold"))
        self.lbl_fecha.pack(side="left", padx=10)

        # ── MONEDAS (automáticas desde CC358) ──
        ctk.CTkLabel(left, text="🪙 MONEDAS  (desde CC358 — automático)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#60A5FA").pack(anchor="w", padx=15, pady=(12, 4))

        monedas_frame = ctk.CTkFrame(left, fg_color="#1F2937", corner_radius=8)
        monedas_frame.pack(fill="x", padx=15, pady=2)

        self.campos_monedas = {}
        monedas_def = [
            ("$1.000",  "1000"),
            ("$500",    "500"),
            ("$200 (A)","200a"),
            ("$200 (B)","200b"),
            ("$100 (A)","100a"),
            ("$100 (B)","100b"),
            ("$50 (A)", "50a"),
            ("$50 (B)", "50b"),
        ]
        for i, (label, key) in enumerate(monedas_def):
            fila = ctk.CTkFrame(monedas_frame, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(fila, text=label, width=80,
                         font=ctk.CTkFont(weight="bold")).pack(side="left")
            entry = ctk.CTkEntry(fila, width=80, placeholder_text="0",
                                 state="disabled")
            entry.pack(side="left", padx=6)
            ctk.CTkLabel(fila, text="unidades", text_color="#9CA3AF").pack(side="left")
            self.campos_monedas[key] = entry

        # ── BILLETES (manuales) ──
        ctk.CTkLabel(left, text="💵 BILLETES  (digitar manualmente)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#FBBF24").pack(anchor="w", padx=15, pady=(12, 4))

        billetes_frame = ctk.CTkFrame(left, fg_color="#1F2937", corner_radius=8)
        billetes_frame.pack(fill="x", padx=15, pady=2)

        self.campos_billetes = {}
        billetes_def = [
            ("$2.000",    "2000"),
            ("$5.000",    "5000"),
            ("$10.000",   "10000"),
            ("$20.000",   "20000"),
            ("$50.000",   "50000"),
            ("$100.000",  "100000"),
        ]
        for label, key in billetes_def:
            fila = ctk.CTkFrame(billetes_frame, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(fila, text=label, width=80,
                         font=ctk.CTkFont(weight="bold")).pack(side="left")
            entry = ctk.CTkEntry(fila, width=80, placeholder_text="0")
            entry.pack(side="left", padx=6)
            ctk.CTkLabel(fila, text="unidades", text_color="#9CA3AF").pack(side="left")
            entry.bind("<KeyRelease>", lambda e: self._actualizar_totales())
            self.campos_billetes[key] = entry

        # ── TOTALES ──
        totales = ctk.CTkFrame(left, fg_color="#111827", corner_radius=8)
        totales.pack(fill="x", padx=15, pady=10)

        def fila_total(parent, label, attr, color):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(f, text=label, text_color="#9CA3AF").pack(side="left")
            lbl = ctk.CTkLabel(f, text="$ 0", font=ctk.CTkFont(
                size=14, weight="bold"), text_color=color)
            lbl.pack(side="right")
            return lbl

        self.lbl_total_monedas  = fila_total(totales, "Total monedas:", "tm", "#60A5FA")
        self.lbl_total_billetes = fila_total(totales, "Total billetes:", "tb", "#FBBF24")
        self.lbl_total_turno    = fila_total(totales, "TOTAL TURNO:", "tt", "#10B981")

        # ── Botón Guardar ──
        self.btn_guardar = ctk.CTkButton(
            left, text="💾  Guardar en Google Sheets",
            fg_color="#107C41", hover_color="#0B5C30",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            command=self._guardar_en_sheets)
        self.btn_guardar.pack(fill="x", padx=15, pady=(4, 15))

        self.lbl_resultado = ctk.CTkLabel(left, text="", text_color="#9CA3AF")
        self.lbl_resultado.pack(pady=(0, 8))

    def _crear_panel_consola(self):
        right = ctk.CTkFrame(self, corner_radius=10)
        right.grid(row=1, column=1, padx=(7, 15), pady=(0, 15), sticky="nsew")


        top_r = ctk.CTkFrame(right, fg_color="transparent")
        top_r.pack(fill="x", padx=15, pady=(15, 6))

        ctk.CTkLabel(top_r, text="📡 Monitor Serial en Vivo",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")

        ctk.CTkButton(top_r, text="Limpiar", width=65, height=26,
                      fg_color="#374151", hover_color="#4B5563",
                      command=lambda: self.txt_consola.delete("1.0", "end")).pack(side="right")

        self.txt_consola = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Consolas", size=12), wrap="none")
        self.txt_consola.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self._log("Sistema listo.\n"
                  "Conecta el adaptador USB-RS232 y haz clic en 'Conectar COM'.\n"
                  "O usa '▶ Simulación' para probar sin cable.\n"
                  + "─" * 55)

        self.lbl_bytes = ctk.CTkLabel(right, text="Esperando datos...",
                                      font=ctk.CTkFont(size=11), text_color="#6B7280")
        self.lbl_bytes.pack(anchor="w", padx=15, pady=(0, 8))

    # ─────────────────────────────────────────
    # LÓGICA DE CONEXIÓN
    # ─────────────────────────────────────────

    def _actualizar_puertos(self):
        puertos = list(serial.tools.list_ports.comports())
        if puertos:
            vals = [f"{p.device} ({p.description})" for p in puertos]
            self.combo_puertos.configure(values=vals)
            self.combo_puertos.set(vals[0])
        else:
            self.combo_puertos.configure(values=["Sin puertos COM"])
            self.combo_puertos.set("Sin puertos COM")

    def _toggle_conexion(self):
        if self.reader and self.reader.activo:
            self.reader.desconectar()
            self.reader = None
            self.btn_conectar.configure(
                text="Conectar COM", fg_color="#2FA572", hover_color="#1E7B54")
            self.lbl_status.configure(text="🔴 Desconectado", text_color="#FF6B6B")
        else:
            puerto = self.combo_puertos.get().split()[0]
            baud = int(self.combo_baud.get())
            self.reader = CC358Reader(self._on_datos_recibidos, self._log_thread)
            ok = self.reader.conectar(puerto, baud, simulacion=False)
            if ok:
                self.btn_conectar.configure(
                    text="Desconectar", fg_color="#DC2626", hover_color="#991B1B")
                self.lbl_status.configure(
                    text=f"🟢 {puerto}", text_color="#10B981")

    def _toggle_simulacion(self):
        if self.reader and self.reader.activo:
            self.reader.desconectar()
            self.reader = None
            self.btn_sim.configure(text="▶ Simulación", fg_color="#6B7280")
            self.lbl_status.configure(text="🔴 Desconectado", text_color="#FF6B6B")
        else:
            self.reader = CC358Reader(self._on_datos_recibidos, self._log_thread)
            self.reader.conectar(None, simulacion=True)
            self.btn_sim.configure(text="⏹ Detener Sim.", fg_color="#D97706")
            self.lbl_status.configure(text="🟡 Simulación activa", text_color="#FBBF24")

    def _toggle_modo_rapido(self):
        self.modo_rapido = not self.modo_rapido
        if self.modo_rapido:
            self.btn_modo_rapido.configure(
                text="⚡ Modo Rapido ON", fg_color="#D97706", hover_color="#B45309")
            self._log("Modo Rapido activado: la ventana emergera automaticamente al recibir un conteo.")
        else:
            self.btn_modo_rapido.configure(
                text="⚡ Modo Rapido", fg_color="#B45309", hover_color="#92400E")
            self._log("Modo Rapido desactivado.")

    # ─────────────────────────────────────────
    # CALLBACK DATOS CC358
    # ─────────────────────────────────────────

    def _on_datos_recibidos(self, monedas):
        """Llamado cuando la CC358 (o simulación) envía un conteo."""
        self.monedas_actuales = monedas

        # Sincronizar con la ventana de Modo Tabla si está abierta
        if self.ventana_tabla and self.ventana_tabla.winfo_exists():
            self.after(0, self.ventana_tabla.recibir_conteo_monedas, monedas)

        if self.modo_rapido and not self._ventana_abierta:
            self.after(0, self._abrir_ventana_rapida, monedas)
        else:
            self.after(0, self._mostrar_monedas, monedas)


    def _abrir_ventana_rapida(self, monedas):
        """Abre la ventana emergente de conteo rápido."""
        self._ventana_abierta = True
        self._log("Abriendo ventana rapida de conteo...")

        def al_cerrar():
            self._ventana_abierta = False
            self._log("Guardado. Esperando siguiente conteo...")

        v = VentanaConteo(self, monedas, callback_cerrar=al_cerrar)
        v.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, '_ventana_abierta', False), v.destroy()))

    def _mostrar_monedas(self, monedas):
        """Actualiza los campos de monedas en la UI (hilo principal)."""
        for key, entry in self.campos_monedas.items():
            entry.configure(state="normal")
            entry.delete(0, "end")
            val = monedas.get(key, 0)
            if val:
                entry.insert(0, str(val))
            entry.configure(state="disabled")
        self._actualizar_totales()
        self._log("Datos de conteo actualizados automaticamente.")

    # ─────────────────────────────────────────
    # TOTALES
    # ─────────────────────────────────────────

    def _actualizar_totales(self):
        monedas = self._leer_monedas()
        billetes = self._leer_billetes()
        tm, tb, tt = calcular_totales(monedas, billetes)
        self.lbl_total_monedas.configure(text=fmt_cop(tm))
        self.lbl_total_billetes.configure(text=fmt_cop(tb))
        self.lbl_total_turno.configure(text=fmt_cop(tt))

    def _leer_monedas(self):
        result = {}
        for key, entry in self.campos_monedas.items():
            v = entry.get().strip()
            result[key] = int(v) if v.isdigit() else 0
        return result

    def _leer_billetes(self):
        result = {}
        for key, entry in self.campos_billetes.items():
            v = entry.get().strip()
            result[key] = int(v) if v.isdigit() else 0
        return result

    # ─────────────────────────────────────────
    # LIMPIAR TODO
    # ─────────────────────────────────────────

    def _limpiar_todo(self):
        """Resetea todos los campos de monedas y billetes a cero."""
        # Limpiar monedas
        for entry in self.campos_monedas.values():
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.configure(state="disabled")

        # Limpiar billetes
        for entry in self.campos_billetes.values():
            entry.delete(0, "end")

        # Resetear totales
        self.lbl_total_monedas.configure(text="$ 0")
        self.lbl_total_billetes.configure(text="$ 0")
        self.lbl_total_turno.configure(text="$ 0")

        # Limpiar mensaje de resultado
        self.lbl_resultado.configure(text="", text_color="#9CA3AF")

        if self.ventana_tabla and self.ventana_tabla.winfo_exists():
            self.ventana_tabla.vista.monedas_actuales = {}
            self.ventana_tabla.vista.lbl_estado_conteo.configure(
                text="⚪ Esperando conteo de monedas de la máquina...",
                text_color="#9CA3AF"
            )
            self.ventana_tabla.vista.lbl_resumen_monedas.configure(text="")
            for e in self.ventana_tabla.vista.campos_billetes.values():
                e.delete(0, "end")
            self.ventana_tabla.vista.lbl_total_vista.configure(text="Total turno: $ 0")

        self._log("Campos limpiados. Listo para nuevo conteo.")


    # ─────────────────────────────────────────
    # GUARDAR EN GOOGLE SHEETS
    # ─────────────────────────────────────────

    def _on_cambio_dia(self, valor):
        import re
        m = re.search(r'\d+', valor)
        if m:
            dia_num = int(m.group(0))
            self.lbl_fecha.configure(text=obtener_fecha_hoy(dia_num))

    def _obtener_dia_seleccionado(self):
        import re
        txt = self.combo_dia.get()
        m = re.search(r'\d+', txt)
        return int(m.group(0)) if m else None

    def _guardar_en_sheets(self):
        trabajador  = self.combo_trabajador.get()
        parqueadero = self.combo_parqueadero.get()
        dia_sel     = self._obtener_dia_seleccionado()
        fecha       = obtener_fecha_hoy(dia_sel)
        monedas     = self._leer_monedas()
        billetes    = self._leer_billetes()

        self.btn_guardar_top.configure(state="disabled", text="⏳ Guardando...")
        self.lbl_resultado.configure(text="Conectando con Google Sheets...", text_color="#9CA3AF")

        threading.Thread(
            target=self._tarea_guardar,
            args=(trabajador, parqueadero, fecha, monedas, billetes),
            daemon=True
        ).start()

    def _tarea_guardar(self, trabajador, parqueadero, fecha, monedas, billetes):
        try:
            self._log(f"Buscando fila: {fecha} | {parqueadero} | {trabajador}...")
            ws = conectar_sheet()
            fila = buscar_fila_trabajador(ws, fecha, parqueadero, trabajador)

            if fila is None:
                self.after(0, self._resultado_error,
                           f"No se encontro espacio disponible para '{trabajador}'\n"
                           f"en {parqueadero} para {fecha}.\n"
                           f"El parqueadero puede estar lleno.")
                return

            # Si la fila esta vacia, escribir el nombre del trabajador
            fila_datos = ws.row_values(fila)
            if not fila_datos or not fila_datos[0].strip():
                from sheets.google_sheets import escribir_nombre_trabajador
                escribir_nombre_trabajador(ws, fila, trabajador)
                self._log(f"Nombre '{trabajador}' escrito en fila {fila}.")

            guardar_conteo(ws, fila, monedas, billetes)
            tm, tb, tt = calcular_totales(monedas, billetes)

            self.after(0, self._resultado_ok,
                       f"Guardado exitosamente en fila {fila}.\n"
                       f"Total turno: {fmt_cop(tt)}")
            self._log(f"Datos guardados en Google Sheets | Fila {fila}")

        except FileNotFoundError as e:
            self.after(0, self._resultado_error, f"{e}")
        except Exception as e:
            self.after(0, self._resultado_error, f"Error: {e}")


    def _resultado_ok(self, msg):
        self.lbl_resultado.configure(text=msg, text_color="#10B981")
        self.btn_guardar_top.configure(state="normal", text="💾 GUARDAR EN SHEETS")

    def _resultado_error(self, msg):
        self.lbl_resultado.configure(text=msg, text_color="#EF4444")
        self.btn_guardar_top.configure(state="normal", text="💾 GUARDAR EN SHEETS")

    # ─────────────────────────────────────────
    # CONSOLA
    # ─────────────────────────────────────────

    def _log(self, texto):
        self.txt_consola.insert("end", f"\n{texto}")
        self.txt_consola.see("end")

    def _log_thread(self, texto):
        """Log seguro desde hilos secundarios."""
        self.after(0, self._log, texto)


if __name__ == "__main__":
    app = AppCC358()
    app.mainloop()
