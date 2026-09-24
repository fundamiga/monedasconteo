import sys
import os

# En aplicaciones empaquetadas con console=False (noconsole), sys.stdout y sys.stderr son None
# y cualquier biblioteca (como pyserial o logging) que intente escribir falla en silencio.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import threading
import customtkinter as ctk
import serial.tools.list_ports
from datetime import datetime

from config.datos import TRABAJADORES, PARQUEADEROS
from selector_trabajador import SelectorTrabajador
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
        self.modo_rapido = True          # Modo ventana emergente automática
        self.modo_continuo = True        # Al guardar un turno, abre inmediatamente el siguiente en blanco
        self.ultimo_respaldo = None      # Memoria del último conteo guardado para recuperar si se necesita
        self._ventana_abierta = False     # Para no abrir dos ventanas a la vez
        self.ventana_rapida_instancia = None # Referencia a la ventana rápida activa
        self.ventana_tabla = None         # Ventana opcional de Modo Tabla

        self._crear_ui()
        self._actualizar_puertos()

        # Atajo global en toda la aplicación: Barra espaciadora y tecla F1
        self.bind_all("<F1>", lambda e: self._adelantar_nuevo_turno())
        self.bind_all("<space>", self._on_space_pressed)

    def _on_space_pressed(self, event):
        # Si ya hay una ventana rápida abierta, no hacer nada para permitir espacios en sus campos
        if self._ventana_abierta and self.ventana_rapida_instancia and self.ventana_rapida_instancia.winfo_exists():
            return

        # Si el usuario está escribiendo dentro de un campo de texto en la ventana principal, respetar el espacio
        try:
            focused = self.focus_get()
            if focused and focused.winfo_class() in ("Entry", "Text", "TEntry"):
                return
        except Exception:
            pass

        self._adelantar_nuevo_turno()

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
        top.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 5), sticky="ew")

        # ── FILA 1: CONEXIÓN SERIAL + ACCIONES PRINCIPALES ──
        fila1 = ctk.CTkFrame(top, fg_color="transparent")
        fila1.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(fila1, text="🪙 CC358 Recaudo",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#60A5FA").pack(side="left", padx=(4, 12))

        # Puerto COM
        self.combo_puertos = ctk.CTkComboBox(fila1, values=["Buscando..."], width=170)
        self.combo_puertos.pack(side="left", padx=4)
        ctk.CTkButton(fila1, text="🔄", width=32,
                      command=self._actualizar_puertos).pack(side="left", padx=2)

        ctk.CTkLabel(fila1, text="Baud:").pack(side="left", padx=(8, 2))
        self.combo_baud = ctk.CTkComboBox(
            fila1, values=["9600", "4800", "19200", "38400", "115200"], width=75)
        self.combo_baud.set("9600")
        self.combo_baud.pack(side="left", padx=2)

        # Botón Conectar COM (BIEN VISIBLE A LA IZQUIERDA)
        self.btn_conectar = ctk.CTkButton(
            fila1, text="⚡ Conectar COM", width=130, height=34,
            fg_color="#2FA572", hover_color="#1E7B54",
            font=ctk.CTkFont(weight="bold"),
            command=self._toggle_conexion)
        self.btn_conectar.pack(side="left", padx=10)

        self.lbl_status = ctk.CTkLabel(
            fila1, text="🔴 Desconectado",
            text_color="#FF6B6B",
            font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_status.pack(side="left", padx=6)

        # A la derecha de fila 1: GUARDAR y LIMPIAR
        ctk.CTkButton(
            fila1, text="🔄 Limpiar",
            fg_color="#4B5563", hover_color="#374151",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=85, height=34,
            command=self._limpiar_todo).pack(side="right", padx=4)

        self.btn_guardar_top = ctk.CTkButton(
            fila1, text="💾 GUARDAR",
            fg_color="#107C41", hover_color="#0B5C30",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, height=34,
            command=self._guardar_en_sheets)
        self.btn_guardar_top.pack(side="right", padx=4)

        # ── FILA 2: MODOS Y HERRAMIENTAS ──
        fila2 = ctk.CTkFrame(top, fg_color="transparent")
        fila2.pack(fill="x", padx=10, pady=(2, 8))

        # Botón ADELANTAR TURNO
        self.btn_adelantar = ctk.CTkButton(
            fila2, text="➕ Nuevo Turno [Espacio]", width=175, height=30,
            fg_color="#059669", hover_color="#047857",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._adelantar_nuevo_turno)
        self.btn_adelantar.pack(side="left", padx=(4, 6))

        # Botón MODO RÁPIDO ON/OFF
        self.btn_modo_rapido = ctk.CTkButton(
            fila2, text="⚡ Modo Rapido ON", width=135, height=30,
            fg_color="#D97706", hover_color="#B45309",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_modo_rapido)
        self.btn_modo_rapido.pack(side="left", padx=4)

        # Botón MODO TABLA
        self.btn_modo_tabla = ctk.CTkButton(
            fila2, text="📊 Modo Tabla", width=110, height=30,
            fg_color="#2563EB", hover_color="#1D4ED8",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._abrir_modo_tabla)
        self.btn_modo_tabla.pack(side="left", padx=4)

        # Botón CÁMARA
        self.btn_modo_camara = ctk.CTkButton(
            fila2, text="📷 Cámara OCR", width=110, height=30,
            fg_color="#0D9488", hover_color="#0F766E",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._abrir_modo_camara)
        self.btn_modo_camara.pack(side="left", padx=4)

        # Checkbox Modo Continuo (Auto-reabrir en 0 tras guardar)
        self.chk_continuo = ctk.CTkCheckBox(
            fila2, text="Auto-reabrir en 0", font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_modo_continuo)
        if self.modo_continuo:
            self.chk_continuo.select()
        self.chk_continuo.pack(side="left", padx=(6, 4))

        # Botón DISCRETO RECUPERAR ANTERIOR en PC
        self.btn_recuperar_pc = ctk.CTkButton(
            fila2, text="↩️ Recuperar", width=95, height=30,
            fg_color="#78350F", hover_color="#92400E", text_color="#FDE68A",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._recuperar_anterior_pc)
        self.btn_recuperar_pc.pack(side="left", padx=4)

        # Destino Hoja
        ctk.CTkLabel(fila2, text="Destino:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 4))
        self.combo_hoja = ctk.CTkComboBox(
            fila2, values=["📁 Pruebas", "⚠️ PRINCIPAL"], width=130, height=30,
            command=self._on_cambio_hoja)
        self.combo_hoja.set("⚠️ PRINCIPAL")
        self.combo_hoja.pack(side="left", padx=2)

        # Botón Simulación
        self.btn_sim = ctk.CTkButton(
            fila2, text="▶ Simulación", width=105, height=30,
            fg_color="#6B7280", hover_color="#4B5563",
            command=self._toggle_simulacion)
        self.btn_sim.pack(side="right", padx=4)

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
        self.combo_trabajador = SelectorTrabajador(
            seleccion, width=280)
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

    def _toggle_modo_continuo(self):
        self.modo_continuo = bool(self.chk_continuo.get())
        if self.modo_continuo:
            self._log("⚡ Modo Continuo ACTIVO: Al guardar se abrirá automáticamente el siguiente turno en 0.")
        else:
            self._log("Modo Continuo desactivado: La ventana se cerrará tras guardar.")

    def _recuperar_anterior_pc(self):
        """Recupera los datos del último turno guardado o limpiado."""
        if not self.ultimo_respaldo:
            self._log("⚠️ No hay datos previos en memoria para recuperar.")
            return

        resp = self.ultimo_respaldo
        self._log(f"↩️ Recuperando datos anteriores de {resp.get('trabajador', 'N/A')} ({resp.get('parqueadero', '')})...")

        # 1. Si la ventana rápida está abierta, inyectar allí directamente
        if self._ventana_abierta and self.ventana_rapida_instancia and self.ventana_rapida_instancia.winfo_exists():
            self.ventana_rapida_instancia._recuperar_anterior()
            self.ventana_rapida_instancia.lift()
            self.ventana_rapida_instancia.focus()
            return

        # 2. Si no está abierta, abrir la ventana rápida y cargarle los datos
        self._abrir_ventana_rapida(monedas=resp.get("monedas", {}))
        if self.ventana_rapida_instancia and self.ventana_rapida_instancia.winfo_exists():
            self.after(80, self.ventana_rapida_instancia._recuperar_anterior)

        # 3. Restaurar también en los campos de la ventana principal
        if resp.get("monedas"):
            self._mostrar_monedas(resp["monedas"])
        if resp.get("billetes"):
            for k, v in resp["billetes"].items():
                if k in self.campos_billetes:
                    self.campos_billetes[k].delete(0, "end")
                    if v > 0:
                        self.campos_billetes[k].insert(0, str(v))
        if resp.get("trabajador"):
            self.combo_trabajador.set(resp["trabajador"])
        if resp.get("parqueadero"):
            self.combo_parqueadero.set(resp["parqueadero"])
        self._actualizar_totales()

    def _adelantar_nuevo_turno(self):
        """Abre la ventana de conteo por anticipado para escribir datos mientras la máquina cuenta."""
        if self._ventana_abierta and self.ventana_rapida_instancia and self.ventana_rapida_instancia.winfo_exists():
            self.ventana_rapida_instancia.lift()
            self.ventana_rapida_instancia.focus()
            return

        self._log("⚡ Adelantando nuevo turno: ingresa trabajador y billetes mientras la máquina cuenta...")
        self._abrir_ventana_rapida(monedas={})

    # ─────────────────────────────────────────
    # CALLBACK DATOS CC358
    # ─────────────────────────────────────────

    def _on_datos_recibidos(self, monedas):
        """Llamado cuando la CC358 (o simulación) envía un conteo."""
        self.monedas_actuales = monedas

        # Sincronizar con la ventana de Modo Tabla si está abierta
        if self.ventana_tabla and self.ventana_tabla.winfo_exists():
            self.after(0, self.ventana_tabla.recibir_conteo_monedas, monedas)

        # Si la ventana rápida ya está abierta esperándolo, inyectarle los datos
        if self._ventana_abierta and self.ventana_rapida_instancia and self.ventana_rapida_instancia.winfo_exists():
            self._log("📥 Inyectando conteo recibido en la ventana activa...")
            self.after(0, self.ventana_rapida_instancia.recibir_conteo, monedas)
            return

        # Si no estaba abierta y Modo Rápido está activo, abrirla normalmente
        if self.modo_rapido and not self._ventana_abierta:
            self.after(0, self._abrir_ventana_rapida, monedas)
        else:
            self.after(0, self._mostrar_monedas, monedas)


    def _abrir_ventana_rapida(self, monedas):
        """Abre la ventana emergente de conteo rápido."""
        self._ventana_abierta = True
        self._log("Abriendo ventana rápida de conteo...")

        def al_cerrar():
            self._ventana_abierta = False
            self.ventana_rapida_instancia = None
            self._log("Turno guardado. Esperando siguiente conteo...")
            if self.modo_continuo:
                # Reabrir automáticamente en 0 el siguiente turno
                self.after(250, lambda: self._abrir_ventana_rapida(monedas={}))

        v = VentanaConteo(self, monedas, callback_cerrar=al_cerrar)
        self.ventana_rapida_instancia = v
        v.protocol("WM_DELETE_WINDOW", lambda: (
            setattr(self, '_ventana_abierta', False),
            setattr(self, 'ventana_rapida_instancia', None),
            v.destroy()
        ))

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
        # Guardar respaldo antes de limpiar por si el usuario lo borro por error
        monedas_prev = self._leer_monedas()
        billetes_prev = self._leer_billetes()
        if any(monedas_prev.values()) or any(billetes_prev.values()):
            self.ultimo_respaldo = {
                "monedas": monedas_prev,
                "billetes": billetes_prev,
                "trabajador": self.combo_trabajador.get(),
                "parqueadero": self.combo_parqueadero.get()
            }

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

    def _obtener_hoja_tipo(self):
        return "principal" if "PRINCIPAL" in self.combo_hoja.get().upper() else "pruebas"

    def _on_cambio_hoja(self, valor):
        hoja = self._obtener_hoja_tipo()
        if hoja == "principal":
            self._log("⚠️ ATENCIÓN: Modo Hoja PRINCIPAL (Producción) activado.")
        else:
            self._log("📁 Modo Hoja de Pruebas activado.")

    def _guardar_en_sheets(self):
        trabajador  = self.combo_trabajador.get()
        parqueadero = self.combo_parqueadero.get()
        dia_sel     = self._obtener_dia_seleccionado()
        fecha       = obtener_fecha_hoy(dia_sel)
        hoja_tipo   = self._obtener_hoja_tipo()
        monedas     = self._leer_monedas()
        billetes    = self._leer_billetes()

        self.btn_guardar_top.configure(state="disabled", text="⏳ Guardando...")
        self.lbl_resultado.configure(text=f"Guardando en {hoja_tipo.upper()}...", text_color="#9CA3AF")

        threading.Thread(
            target=self._tarea_guardar,
            args=(trabajador, parqueadero, fecha, monedas, billetes, hoja_tipo),
            daemon=True
        ).start()

    def _tarea_guardar(self, trabajador, parqueadero, fecha, monedas, billetes, hoja_tipo="pruebas"):
        try:
            self._log(f"Buscando fila en {hoja_tipo.upper()}: {fecha} | {parqueadero} | {trabajador}...")
            ws = conectar_sheet(hoja_tipo)
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
            self.ultimo_respaldo = {
                "monedas": {**monedas},
                "billetes": {**billetes},
                "trabajador": trabajador,
                "parqueadero": parqueadero
            }
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
