"""
Ventana Rápida de Conteo - Aparece automáticamente cuando la CC358 termina de contar.
La operadora llena nombre, parqueadero y billetes, guarda, y la ventana se cierra sola.
"""

import threading
import customtkinter as ctk
from datetime import datetime

from config.datos import TRABAJADORES, PARQUEADEROS
from selector_trabajador import SelectorTrabajador
from sheets.google_sheets import (
    conectar_sheet, buscar_fila_trabajador, guardar_conteo,
    calcular_totales, obtener_fecha_hoy, escribir_nombre_trabajador
)


def fmt_cop(valor):
    return f"$ {valor:,.0f}".replace(",", ".")


class VentanaConteo(ctk.CTkToplevel):
    """
    Ventana emergente que aparece cuando la CC358 termina un conteo.
    Muestra monedas, permite ingresar billetes, trabajador y parqueadero.
    Se cierra sola al guardar.
    """

    def __init__(self, parent, monedas=None, callback_cerrar=None):
        super().__init__(parent)
        self.monedas = monedas or {}
        self.callback_cerrar = callback_cerrar
        self.labels_cant_monedas = {}
        self.labels_subtotal_monedas = {}

        self.title("Nuevo Conteo CC358")
        ancho = 680
        self.resizable(True, True)
        self.attributes("-topmost", True)  # Siempre encima
        self.minsize(640, 500)

        # Construir UI primero para medir el tamaño real
        self._crear_ui()

        # Ajustar posición: centrar X, Y=20 garantiza que siempre quede en pantalla
        self.update_idletasks()
        alto_real = self.winfo_reqheight()
        x = max(0, (self.winfo_screenwidth() // 2) - (ancho // 2))
        y = 20
        self.geometry(f"{ancho}x{alto_real}+{x}+{y}")

        # Enfocar primer campo de billetes o trabajador
        self.after(200, self._enfocar_primer_campo)

    def _enfocar_primer_campo(self):
        try:
            if "2000" in self.campos_billetes:
                self.campos_billetes["2000"].focus()
        except Exception:
            pass

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Título ──
        self.lbl_titulo = ctk.CTkLabel(
            self, 
            text="Nuevo Conteo Recibido" if any(self.monedas.values()) else "⚡ Adelantar Conteo (Escribe datos mientras cuenta)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#60A5FA" if any(self.monedas.values()) else "#FBBF24")
        self.lbl_titulo.grid(row=0, column=0, columnspan=2, pady=(8, 4))

        # ── Panel MONEDAS (izquierda) ──
        frame_mon = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        frame_mon.grid(row=1, column=0, padx=(10, 5), pady=3, sticky="nsew")

        f_header_mon = ctk.CTkFrame(frame_mon, fg_color="transparent")
        f_header_mon.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(f_header_mon, text="MONEDAS (automático)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#60A5FA").pack(side="left")
        
        self.lbl_espera_print = ctk.CTkLabel(
            f_header_mon, 
            text="" if any(self.monedas.values()) else "🟡 Esperando PRINT...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FBBF24")
        self.lbl_espera_print.pack(side="right")

        monedas_labels = [
            ("$1.000",  "1000"),
            ("$500",    "500"),
            ("$200 (A)","200a"),
            ("$200 (B)","200b"),
            ("$100 (A)","100a"),
            ("$100 (B)","100b"),
            ("$50 (A)", "50a"),
            ("$50 (B)", "50b"),
        ]

        tm = 0
        valores_monedas = {
            "1000": 1000, "500": 500,
            "200a": 200, "200b": 200,
            "100a": 100, "100b": 100,
            "50a": 50, "50b": 50
        }

        for label, key in monedas_labels:
            cant = self.monedas.get(key, 0)
            subtotal = cant * valores_monedas.get(key, 0)
            tm += subtotal

            fila = ctk.CTkFrame(frame_mon, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=0)
            ctk.CTkLabel(fila, text=label, width=70,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            lbl_c = ctk.CTkLabel(fila, text=f"{cant}",
                         width=35, text_color="#10B981",
                         font=ctk.CTkFont(size=12, weight="bold"))
            lbl_c.pack(side="left")
            self.labels_cant_monedas[key] = lbl_c

            ctk.CTkLabel(fila, text="uds",
                         text_color="#6B7280", font=ctk.CTkFont(size=11)).pack(side="left", padx=(2, 6))
            lbl_sub = ctk.CTkLabel(fila, text=fmt_cop(subtotal),
                         text_color="#9CA3AF", font=ctk.CTkFont(size=11))
            lbl_sub.pack(side="right")
            self.labels_subtotal_monedas[key] = lbl_sub

        # Total monedas
        sep = ctk.CTkFrame(frame_mon, height=1, fg_color="#374151")
        sep.pack(fill="x", padx=10, pady=3)
        f_tm = ctk.CTkFrame(frame_mon, fg_color="transparent")
        f_tm.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(f_tm, text="Total monedas:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.lbl_tm_valor = ctk.CTkLabel(f_tm, text=fmt_cop(tm),
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#60A5FA")
        self.lbl_tm_valor.pack(side="right")

        self._tm = tm

        # ── Panel BILLETES (derecha) ──
        frame_bil = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        frame_bil.grid(row=1, column=1, padx=(5, 10), pady=3, sticky="nsew")

        ctk.CTkLabel(frame_bil, text="BILLETES (manual)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#FBBF24").pack(anchor="w", padx=10, pady=(6, 2))

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
            fila = ctk.CTkFrame(frame_bil, fg_color="transparent")
            fila.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(fila, text=label, width=75,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            entry = ctk.CTkEntry(fila, width=55, placeholder_text="0", height=26)
            entry.pack(side="left", padx=4)
            ctk.CTkLabel(fila, text="uds", text_color="#9CA3AF",
                         font=ctk.CTkFont(size=11)).pack(side="left")
            entry.bind("<KeyRelease>", lambda e: self._actualizar_total())
            self.campos_billetes[key] = entry

        # Total billetes
        sep2 = ctk.CTkFrame(frame_bil, height=1, fg_color="#374151")
        sep2.pack(fill="x", padx=10, pady=3)
        f_tb = ctk.CTkFrame(frame_bil, fg_color="transparent")
        f_tb.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(f_tb, text="Total billetes:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.lbl_tb = ctk.CTkLabel(f_tb, text="$ 0",
                                    font=ctk.CTkFont(size=13, weight="bold"),
                                    text_color="#FBBF24")
        self.lbl_tb.pack(side="right")

        # ── Datos del turno ──
        frame_datos = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        frame_datos.grid(row=2, column=0, columnspan=2,
                         padx=10, pady=4, sticky="ew")
        frame_datos.grid_columnconfigure(1, weight=1)
        frame_datos.grid_columnconfigure(3, weight=1)

        # Trabajador
        ctk.CTkLabel(frame_datos, text="Trabajador:",
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(10, 4), pady=5, sticky="w")
        self.combo_trabajador = SelectorTrabajador(
            frame_datos, width=240)
        self.combo_trabajador.set(TRABAJADORES[0])
        self.combo_trabajador.grid(row=0, column=1, padx=4, pady=5, sticky="ew")

        # Parqueadero
        ctk.CTkLabel(frame_datos, text="Parqueadero:",
                     font=ctk.CTkFont(size=12)).grid(
            row=0, column=2, padx=(10, 4), pady=5, sticky="w")
        self.combo_parqueadero = ctk.CTkComboBox(
            frame_datos, values=PARQUEADEROS, width=130, height=28)
        self.combo_parqueadero.set(PARQUEADEROS[0])
        self.combo_parqueadero.grid(row=0, column=3, padx=(4, 10), pady=5, sticky="ew")

        # Hoja Destino y Fecha del Recaudo
        ctk.CTkLabel(frame_datos, text="Destino Hoja:",
                     font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=(10, 4), pady=(0, 5), sticky="w")
        self.combo_hoja = ctk.CTkComboBox(
            frame_datos, values=["📁 Pruebas", "⚠️ PRINCIPAL"], width=140, height=28)
        self.combo_hoja.set("⚠️ PRINCIPAL")
        self.combo_hoja.grid(row=1, column=1, padx=4, pady=(0, 5), sticky="w")

        ctk.CTkLabel(frame_datos, text="Fecha:",
                     font=ctk.CTkFont(size=12)).grid(
            row=1, column=2, padx=(10, 4), pady=(0, 5), sticky="w")

        f_dia = ctk.CTkFrame(frame_datos, fg_color="transparent")
        f_dia.grid(row=1, column=3, padx=(4, 10), pady=(0, 5), sticky="ew")

        from datetime import datetime, timedelta
        ayer_dia = (datetime.now() - timedelta(days=1)).day
        dias_opciones = [f"Dia {d} (Ayer)" if d == ayer_dia else f"Dia {d} (Hoy)" if d == datetime.now().day else f"Dia {d}" for d in range(1, 32)]

        self.combo_dia = ctk.CTkComboBox(
            f_dia, values=dias_opciones, width=140, height=28,
            command=self._on_cambio_dia)
        self.combo_dia.set(f"Dia {ayer_dia} (Ayer)")
        self.combo_dia.pack(side="left")

        self.lbl_fecha_txt = ctk.CTkLabel(
            f_dia, text=obtener_fecha_hoy(ayer_dia),
            text_color="#10B981", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_fecha_txt.pack(side="left", padx=8)

        # ── Total turno ──
        frame_total = ctk.CTkFrame(self, fg_color="#064E3B", corner_radius=10)
        frame_total.grid(row=3, column=0, columnspan=2,
                         padx=10, pady=3, sticky="ew")
        ctk.CTkLabel(frame_total, text="TOTAL TURNO:",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=16, pady=7)
        self.lbl_total = ctk.CTkLabel(frame_total, text=fmt_cop(tm),
                                       font=ctk.CTkFont(size=18, weight="bold"),
                                       text_color="#10B981")
        self.lbl_total.pack(side="right", padx=16, pady=7)

        # ── Botones ──
        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.grid(row=4, column=0, columnspan=2,
                        padx=10, pady=(5, 10), sticky="ew")

        ctk.CTkButton(frame_btns, text="Cancelar",
                      fg_color="#374151", hover_color="#4B5563",
                      width=100, height=36, command=self.destroy).pack(side="left", padx=6)

        self.lbl_estado = ctk.CTkLabel(frame_btns, text="",
                                        text_color="#9CA3AF")
        self.lbl_estado.pack(side="left", padx=10)

        self.btn_guardar = ctk.CTkButton(
            frame_btns,
            text="💾 GUARDAR Y CERRAR",
            fg_color="#107C41", hover_color="#0B5C30",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=200, height=38,
            command=self._guardar)
        self.btn_guardar.pack(side="right", padx=6)

        # Atajo Enter para guardar rápidamente
        self.bind("<Return>", lambda e: self._guardar())

    def recibir_conteo(self, nuevas_monedas):
        """Inyecta el conteo de la CC358 en vivo cuando la máquina manda PRINT."""
        self.monedas = nuevas_monedas
        valores_monedas = {
            "1000": 1000, "500": 500,
            "200a": 200, "200b": 200,
            "100a": 100, "100b": 100,
            "50a": 50, "50b": 50
        }
        tm = 0
        for key, cant in nuevas_monedas.items():
            subtotal = cant * valores_monedas.get(key, 0)
            tm += subtotal
            if key in self.labels_cant_monedas:
                self.labels_cant_monedas[key].configure(text=str(cant))
            if key in self.labels_subtotal_monedas:
                self.labels_subtotal_monedas[key].configure(text=fmt_cop(subtotal))

        self._tm = tm
        self.lbl_tm_valor.configure(text=fmt_cop(tm))
        self.lbl_espera_print.configure(text="✅ Conteo Recibido", text_color="#10B981")
        self.lbl_titulo.configure(text="Nuevo Conteo Recibido", text_color="#60A5FA")
        self._actualizar_total()
        # Enfocar botón guardar para confirmar con Enter
        self.btn_guardar.focus()

    def _leer_billetes(self):
        result = {}
        for key, entry in self.campos_billetes.items():
            v = entry.get().strip()
            result[key] = int(v) if v.isdigit() else 0
        return result

    def _actualizar_total(self):
        billetes = self._leer_billetes()
        _, tb, tt = calcular_totales(self.monedas, billetes)
        self.lbl_tb.configure(text=fmt_cop(tb))
        self.lbl_total.configure(text=fmt_cop(self._tm + tb))

    def _on_cambio_dia(self, valor):
        import re
        m = re.search(r'\d+', valor)
        if m:
            dia_num = int(m.group(0))
            self.lbl_fecha_txt.configure(text=obtener_fecha_hoy(dia_num))

    def _obtener_fecha_final(self):
        import re
        txt = self.combo_dia.get()
        m = re.search(r'\d+', txt)
        dia_num = int(m.group(0)) if m else None
        return obtener_fecha_hoy(dia_num)

    def _guardar(self):
        trabajador  = self.combo_trabajador.get()
        parqueadero = self.combo_parqueadero.get()
        fecha       = self._obtener_fecha_final()
        hoja_tipo   = "principal" if "PRINCIPAL" in self.combo_hoja.get().upper() else "pruebas"
        billetes    = self._leer_billetes()

        self.btn_guardar.configure(state="disabled", text="Guardando...")
        self.lbl_estado.configure(text=f"Guardando en {hoja_tipo.upper()}...", text_color="#9CA3AF")

        threading.Thread(
            target=self._tarea_guardar,
            args=(trabajador, parqueadero, fecha, billetes, hoja_tipo),
            daemon=True
        ).start()

    def _tarea_guardar(self, trabajador, parqueadero, fecha, billetes, hoja_tipo="pruebas"):
        try:
            ws = conectar_sheet(hoja_tipo)
            fila = buscar_fila_trabajador(ws, fecha, parqueadero, trabajador)

            if fila is None:
                self.after(0, self._error, "Sin espacio disponible en esa seccion.")
                return

            fila_datos = ws.row_values(fila)
            if not fila_datos or not fila_datos[0].strip():
                escribir_nombre_trabajador(ws, fila, trabajador)

            guardar_conteo(ws, fila, self.monedas, billetes)
            self.after(0, self._exito)

        except Exception as e:
            self.after(0, self._error, str(e))

    def _exito(self):
        self.lbl_estado.configure(text="Guardado correctamente", text_color="#10B981")
        if self.callback_cerrar:
            self.callback_cerrar()
        # Cerrar la ventana despues de 1.2 segundos
        self.after(1200, self.destroy)

    def _error(self, msg):
        self.lbl_estado.configure(text=f"Error: {msg}", text_color="#EF4444")
        self.btn_guardar.configure(state="normal", text="Reintentar")
