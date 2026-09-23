"""
Ventana Rápida de Conteo - Aparece automáticamente cuando la CC358 termina de contar.
La operadora llena nombre, parqueadero y billetes, guarda, y la ventana se cierra sola.
"""

import threading
import customtkinter as ctk
from datetime import datetime

from config.datos import TRABAJADORES, PARQUEADEROS
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

    def __init__(self, parent, monedas, callback_cerrar=None):
        super().__init__(parent)
        self.monedas = monedas
        self.callback_cerrar = callback_cerrar

        self.title("Nuevo Conteo CC358")
        self.geometry("640x560")
        self.resizable(False, False)
        self.attributes("-topmost", True)  # Siempre encima

        # Centrar en pantalla
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 320
        y = (self.winfo_screenheight() // 2) - 280
        self.geometry(f"640x560+{x}+{y}")

        self._crear_ui()

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Título ──
        ctk.CTkLabel(self, text="Nuevo Conteo Recibido",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color="#60A5FA").grid(
            row=0, column=0, columnspan=2, pady=(18, 8))

        # ── Panel MONEDAS (izquierda) ──
        frame_mon = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        frame_mon.grid(row=1, column=0, padx=(15, 7), pady=4, sticky="nsew")

        ctk.CTkLabel(frame_mon, text="MONEDAS (automático)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#60A5FA").pack(anchor="w", padx=12, pady=(10, 4))

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
            fila.pack(fill="x", padx=12, pady=1)
            ctk.CTkLabel(fila, text=label, width=75,
                         font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(fila, text=f"{cant}",
                         width=40, text_color="#10B981",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(fila, text=f"uds",
                         text_color="#6B7280").pack(side="left", padx=(2, 10))
            ctk.CTkLabel(fila, text=fmt_cop(subtotal),
                         text_color="#9CA3AF").pack(side="right")

        # Total monedas
        sep = ctk.CTkFrame(frame_mon, height=1, fg_color="#374151")
        sep.pack(fill="x", padx=12, pady=6)
        f_tm = ctk.CTkFrame(frame_mon, fg_color="transparent")
        f_tm.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(f_tm, text="Total monedas:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(f_tm, text=fmt_cop(tm),
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#60A5FA").pack(side="right")

        self._tm = tm

        # ── Panel BILLETES (derecha) ──
        frame_bil = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        frame_bil.grid(row=1, column=1, padx=(7, 15), pady=4, sticky="nsew")

        ctk.CTkLabel(frame_bil, text="BILLETES (manual)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#FBBF24").pack(anchor="w", padx=12, pady=(10, 4))

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
            fila.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(fila, text=label, width=80,
                         font=ctk.CTkFont(weight="bold")).pack(side="left")
            entry = ctk.CTkEntry(fila, width=65, placeholder_text="0")
            entry.pack(side="left", padx=6)
            ctk.CTkLabel(fila, text="uds", text_color="#9CA3AF").pack(side="left")
            entry.bind("<KeyRelease>", lambda e: self._actualizar_total())
            self.campos_billetes[key] = entry

        # Total billetes
        sep2 = ctk.CTkFrame(frame_bil, height=1, fg_color="#374151")
        sep2.pack(fill="x", padx=12, pady=6)
        f_tb = ctk.CTkFrame(frame_bil, fg_color="transparent")
        f_tb.pack(fill="x", padx=12)
        ctk.CTkLabel(f_tb, text="Total billetes:",
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_tb = ctk.CTkLabel(f_tb, text="$ 0",
                                    font=ctk.CTkFont(size=14, weight="bold"),
                                    text_color="#FBBF24")
        self.lbl_tb.pack(side="right")

        # ── Datos del turno ──
        frame_datos = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        frame_datos.grid(row=2, column=0, columnspan=2,
                         padx=15, pady=8, sticky="ew")
        frame_datos.grid_columnconfigure(1, weight=1)
        frame_datos.grid_columnconfigure(3, weight=1)

        # Trabajador
        ctk.CTkLabel(frame_datos, text="Trabajador:").grid(
            row=0, column=0, padx=(12, 6), pady=8, sticky="w")
        self.combo_trabajador = ctk.CTkComboBox(
            frame_datos, values=TRABAJADORES, width=220)
        self.combo_trabajador.set(TRABAJADORES[0])
        self.combo_trabajador.grid(row=0, column=1, padx=6, pady=8, sticky="ew")

        # Parqueadero
        ctk.CTkLabel(frame_datos, text="Parqueadero:").grid(
            row=0, column=2, padx=(12, 6), pady=8, sticky="w")
        self.combo_parqueadero = ctk.CTkComboBox(
            frame_datos, values=PARQUEADEROS, width=130)
        self.combo_parqueadero.set(PARQUEADEROS[0])
        self.combo_parqueadero.grid(row=0, column=3, padx=(6, 12), pady=8, sticky="ew")

        # Fecha del Recaudo
        ctk.CTkLabel(frame_datos, text="Fecha Recaudo:").grid(
            row=1, column=0, padx=(12, 6), pady=(0, 8), sticky="w")

        f_dia = ctk.CTkFrame(frame_datos, fg_color="transparent")
        f_dia.grid(row=1, column=1, columnspan=3, padx=6, pady=(0, 8), sticky="w")

        from datetime import datetime, timedelta
        ayer_dia = (datetime.now() - timedelta(days=1)).day
        dias_opciones = [f"Dia {d} (Ayer)" if d == ayer_dia else f"Dia {d} (Hoy)" if d == datetime.now().day else f"Dia {d}" for d in range(1, 32)]

        self.combo_dia = ctk.CTkComboBox(
            f_dia, values=dias_opciones, width=150,
            command=self._on_cambio_dia)
        self.combo_dia.set(f"Dia {ayer_dia} (Ayer)")
        self.combo_dia.pack(side="left")

        self.lbl_fecha_txt = ctk.CTkLabel(
            f_dia, text=obtener_fecha_hoy(ayer_dia),
            text_color="#10B981", font=ctk.CTkFont(weight="bold"))
        self.lbl_fecha_txt.pack(side="left", padx=10)

        # ── Total turno ──
        frame_total = ctk.CTkFrame(self, fg_color="#064E3B", corner_radius=10)
        frame_total.grid(row=3, column=0, columnspan=2,
                         padx=15, pady=4, sticky="ew")
        ctk.CTkLabel(frame_total, text="TOTAL TURNO:",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=20, pady=10)
        self.lbl_total = ctk.CTkLabel(frame_total, text=fmt_cop(tm),
                                       font=ctk.CTkFont(size=20, weight="bold"),
                                       text_color="#10B981")
        self.lbl_total.pack(side="right", padx=20, pady=10)

        # ── Botones ──
        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.grid(row=4, column=0, columnspan=2,
                        padx=15, pady=(8, 15), sticky="ew")

        ctk.CTkButton(frame_btns, text="Cancelar",
                      fg_color="#374151", hover_color="#4B5563",
                      width=100, command=self.destroy).pack(side="left", padx=6)

        self.lbl_estado = ctk.CTkLabel(frame_btns, text="",
                                        text_color="#9CA3AF")
        self.lbl_estado.pack(side="left", padx=10)

        self.btn_guardar = ctk.CTkButton(
            frame_btns,
            text="💾 GUARDAR Y CERRAR",
            fg_color="#107C41", hover_color="#0B5C30",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=200, height=40,
            command=self._guardar)
        self.btn_guardar.pack(side="right", padx=6)

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
        billetes    = self._leer_billetes()

        self.btn_guardar.configure(state="disabled", text="Guardando...")
        self.lbl_estado.configure(text="Conectando...", text_color="#9CA3AF")

        threading.Thread(
            target=self._tarea_guardar,
            args=(trabajador, parqueadero, fecha, billetes),
            daemon=True
        ).start()

    def _tarea_guardar(self, trabajador, parqueadero, fecha, billetes):
        try:
            ws = conectar_sheet()
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
