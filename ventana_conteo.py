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


def obtener_monitores():
    """Retorna lista de monitores conectados en Windows con sus coordenadas."""
    monitors = []
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            r = lprcMonitor.contents
            monitors.append({
                'left': r.left, 'top': r.top,
                'right': r.right, 'bottom': r.bottom,
                'width': r.right - r.left, 'height': r.bottom - r.top
            })
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    except Exception:
        pass
    if not monitors:
        monitors = [{'left': 0, 'top': 0, 'right': 1920, 'bottom': 1080, 'width': 1920, 'height': 1080}]
    return monitors


class VentanaConteo(ctk.CTkToplevel):
    """
    Ventana emergente que aparece cuando la CC358 termina un conteo.
    Muestra monedas, permite ingresar billetes, trabajador y parqueadero.
    Se cierra sola al guardar. Soporta selección de monitor en pantallas múltiples.
    """

    def __init__(self, parent, monedas=None, callback_cerrar=None, auto_guardar_print=None):
        super().__init__(parent)
        self.monedas = monedas or {}
        self.callback_cerrar = callback_cerrar
        self.auto_guardar_print = auto_guardar_print if auto_guardar_print is not None else getattr(parent, 'auto_guardar_print', False)
        self.labels_cant_monedas = {}
        self.labels_subtotal_monedas = {}
        self.filas_monedas = {}
        self.monitores = obtener_monitores()
        self.ancho = 680

        # Determinar monitor objetivo
        ajustes = getattr(parent, 'ajustes', {})
        idx_guardado = ajustes.get('monitor_popup', None)
        if idx_guardado is not None and 0 <= idx_guardado < len(self.monitores):
            self.monitor_actual = idx_guardado
        elif len(self.monitores) > 1:
            try:
                parent_x = parent.winfo_rootx()
                self.monitor_actual = 0
                for idx, m in enumerate(self.monitores):
                    if m['left'] <= parent_x < m['right']:
                        self.monitor_actual = idx
                        break
            except Exception:
                self.monitor_actual = 0
        else:
            self.monitor_actual = 0

        self.title("Nuevo Conteo CC358")
        self.resizable(True, True)
        self.attributes("-topmost", True)  # Siempre encima
        self.minsize(640, 500)

        # Construir UI primero para medir el tamaño real
        self._crear_ui()

        # Ajustar posición en el monitor seleccionado
        self.update_idletasks()
        alto_real = self.winfo_reqheight()
        mon = self.monitores[self.monitor_actual]
        x = mon['left'] + max(10, (mon['width'] - self.ancho) // 2)
        y = mon['top'] + 20
        self.geometry(f"{self.ancho}x{alto_real}+{x}+{y}")

        # Enfocar primer campo de billetes o trabajador
        self.after(200, self._enfocar_primer_campo)

    def _cambiar_monitor(self):
        if len(self.monitores) < 2:
            return
        self.monitor_actual = (self.monitor_actual + 1) % len(self.monitores)
        mon = self.monitores[self.monitor_actual]
        alto_real = self.winfo_height() or 560
        x = mon['left'] + max(10, (mon['width'] - self.ancho) // 2)
        y = mon['top'] + 20
        self.geometry(f"{self.ancho}x{alto_real}+{x}+{y}")
        if hasattr(self, "btn_monitor"):
            self.btn_monitor.configure(text=f"🖥️ Pantalla {self.monitor_actual + 1}")
        if hasattr(self.master, "ajustes"):
            self.master.ajustes["monitor_popup"] = self.monitor_actual
            try:
                from app_gui import guardar_ajustes
                guardar_ajustes(self.master.ajustes)
            except Exception:
                pass

    def _abrir_historial(self):
        try:
            from ventana_historial import VentanaHistorial
            v = VentanaHistorial(self)
            v.lift()
            v.focus()
        except Exception as e:
            print(f"Error abriendo ventana de historial: {e}")

    def _enfocar_primer_campo(self):
        try:
            if "2000" in self.campos_billetes:
                self.campos_billetes["2000"].focus()
        except Exception:
            pass

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        tiene_monedas = any(v > 0 for v in self.monedas.values())

        # ── Título y botón de cambio de monitor ──
        f_top = ctk.CTkFrame(self, fg_color="transparent")
        f_top.grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 4), sticky="ew")

        self.lbl_titulo = ctk.CTkLabel(
            f_top, 
            text="✅ ¡Monedas Recibidas de la Máquina!" if tiene_monedas else "⚡ Adelantar Conteo (Escribe datos mientras cuenta)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#34D399" if tiene_monedas else "#FBBF24")
        self.lbl_titulo.pack(side="left", padx=4)

        if len(self.monitores) > 1:
            self.btn_monitor = ctk.CTkButton(
                f_top,
                text=f"🖥️ Pantalla {self.monitor_actual + 1}",
                fg_color="#1E3A8A", hover_color="#1D4ED8",
                font=ctk.CTkFont(size=11, weight="bold"),
                width=110, height=26,
                command=self._cambiar_monitor
            )
            self.btn_monitor.pack(side="right", padx=4)

        # Botón discreto HISTORIAL en la ventana rápida
        self.btn_historial_rapido = ctk.CTkButton(
            f_top,
            text="📜 Historial",
            fg_color="#4C1D95", hover_color="#5B21B6", text_color="#DDD6FE",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=90, height=26,
            command=self._abrir_historial
        )
        self.btn_historial_rapido.pack(side="right", padx=4)

        # ── Panel MONEDAS (izquierda) ──
        self.frame_mon = ctk.CTkFrame(
            self, 
            fg_color="#1F2937", 
            corner_radius=10,
            border_width=2,
            border_color="#10B981" if tiene_monedas else "#374151"
        )
        self.frame_mon.grid(row=1, column=0, padx=(10, 5), pady=3, sticky="nsew")

        f_header_mon = ctk.CTkFrame(self.frame_mon, fg_color="transparent")
        f_header_mon.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(f_header_mon, text="MONEDAS (automático)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#34D399" if tiene_monedas else "#60A5FA").pack(side="left")

        # Botón DISCRETO RECUPERAR ANTERIOR — esquina superior del panel de monedas
        self.btn_recuperar = ctk.CTkButton(
            f_header_mon, text="↩️ Recuperar",
            fg_color="#78350F", hover_color="#92400E", text_color="#FDE68A",
            font=ctk.CTkFont(size=10),
            width=90, height=22,
            command=self._recuperar_anterior)
        self.btn_recuperar.pack(side="left", padx=8)

        self.lbl_espera_print = ctk.CTkLabel(
            f_header_mon, 
            text="🟢 ¡CONTEO RECIBIDO!" if tiene_monedas else "🟡 Esperando PRINT...",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#34D399" if tiene_monedas else "#FBBF24")
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

            fila = ctk.CTkFrame(
                self.frame_mon, 
                fg_color="#064E3B" if cant > 0 else "transparent",
                corner_radius=6
            )
            fila.pack(fill="x", padx=8, pady=1)
            self.filas_monedas[key] = fila

            ctk.CTkLabel(fila, text=label, width=70,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(4, 0))
            lbl_c = ctk.CTkLabel(
                fila, text=f"{cant}",
                width=35, 
                text_color="#34D399" if cant > 0 else "#6B7280",
                font=ctk.CTkFont(size=13, weight="bold") if cant > 0 else ctk.CTkFont(size=12)
            )
            lbl_c.pack(side="left")
            self.labels_cant_monedas[key] = lbl_c

            ctk.CTkLabel(
                fila, text="uds",
                text_color="#9CA3AF" if cant > 0 else "#6B7280", 
                font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=(2, 6))
            lbl_sub = ctk.CTkLabel(
                fila, text=fmt_cop(subtotal),
                text_color="#A7F3D0" if cant > 0 else "#6B7280", 
                font=ctk.CTkFont(size=11, weight="bold" if cant > 0 else "normal")
            )
            lbl_sub.pack(side="right", padx=(0, 4))
            self.labels_subtotal_monedas[key] = lbl_sub

        # Total monedas
        sep = ctk.CTkFrame(self.frame_mon, height=1, fg_color="#374151")
        sep.pack(fill="x", padx=10, pady=3)
        f_tm = ctk.CTkFrame(self.frame_mon, fg_color="transparent")
        f_tm.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkLabel(f_tm, text="Total monedas:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.lbl_tm_valor = ctk.CTkLabel(
            f_tm, text=fmt_cop(tm),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#34D399" if tiene_monedas else "#60A5FA"
        )
        self.lbl_tm_valor.pack(side="right")

        self._tm = tm

        # ── Panel BILLETES (derecha) ──
        frame_bil = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        frame_bil.grid(row=1, column=1, padx=(5, 10), pady=3, sticky="nsew")

        ctk.CTkLabel(frame_bil, text="BILLETES (manual)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#FBBF24").pack(anchor="w", padx=10, pady=(6, 2))

        self.campos_billetes = {}
        self._entradas_billetes = []
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
            self._entradas_billetes.append(entry)

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

        from sheets.google_sheets import (
            generar_opciones_fechas_combo, extraer_fecha_de_opcion,
            obtener_nombre_pestana_mes, obtener_opcion_defecto_combo
        )
        dias_opciones = generar_opciones_fechas_combo()
        opcion_defecto = obtener_opcion_defecto_combo(dias_opciones)

        self.combo_dia = ctk.CTkComboBox(
            f_dia, values=dias_opciones, width=240, height=28,
            command=self._on_cambio_dia)
        self.combo_dia.set(opcion_defecto)
        self.combo_dia.pack(side="left")

        fecha_ini = extraer_fecha_de_opcion(opcion_defecto)
        pestana_ini = obtener_nombre_pestana_mes(fecha_ini)
        self.lbl_fecha_txt = ctk.CTkLabel(
            f_dia, text=f"📁 {pestana_ini}",
            text_color="#10B981", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_fecha_txt.pack(side="left", padx=8)

        # ── Navegación con flechas (Arriba / Abajo) entre billetes y trabajador ──
        for idx, ent in enumerate(self._entradas_billetes):
            def _crear_nav(i):
                def _bajar(event=None):
                    if i < len(self._entradas_billetes) - 1:
                        nxt = self._entradas_billetes[i + 1]
                        nxt.focus_set()
                        nxt.after(10, lambda: nxt.select_range(0, "end"))
                        return "break"
                    else:
                        if hasattr(self, "combo_trabajador") and hasattr(self.combo_trabajador, "entry"):
                            self.combo_trabajador.entry.focus_set()
                            self.combo_trabajador.entry.after(10, lambda: self.combo_trabajador.entry.select_range(0, "end"))
                            return "break"
                    return None

                def _subir(event=None):
                    if i > 0:
                        prv = self._entradas_billetes[i - 1]
                        prv.focus_set()
                        prv.after(10, lambda: prv.select_range(0, "end"))
                        return "break"
                    return None

                return _bajar, _subir

            bajar_fn, subir_fn = _crear_nav(idx)
            ent.bind("<Down>", bajar_fn)
            ent.bind("<Up>", subir_fn)
            ent.bind("<FocusIn>", lambda e, w=ent: w.after(10, lambda: w.select_range(0, "end")))

        # Desde el campo del trabajador, flecha arriba regresa al último billete ($100.000)
        def _subir_desde_trabajador(event=None):
            if not (self.combo_trabajador._popup and self.combo_trabajador._popup.winfo_exists()):
                if self._entradas_billetes:
                    ultimo = self._entradas_billetes[-1]
                    ultimo.focus_set()
                    ultimo.after(10, lambda: ultimo.select_range(0, "end"))
                    return "break"
            return None

        self.combo_trabajador.entry.bind("<Up>", _subir_desde_trabajador)

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
                      width=90, height=36, command=self.destroy).pack(side="left", padx=4)

        self.lbl_estado = ctk.CTkLabel(frame_btns, text="",
                                        text_color="#9CA3AF")
        self.lbl_estado.pack(side="left", padx=6)

        self.btn_guardar = ctk.CTkButton(
            frame_btns,
            text="💾 GUARDAR Y CERRAR",
            fg_color="#107C41", hover_color="#0B5C30",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=190, height=38,
            command=self._guardar)
        self.btn_guardar.pack(side="right", padx=6)

        # Atajo Enter para guardar rápidamente
        self.bind("<Return>", lambda e: self._guardar())

    def _recuperar_anterior(self):
        """Restaura los datos del turno anterior guardados en la app principal."""
        if hasattr(self.master, "ultimo_respaldo") and self.master.ultimo_respaldo:
            resp = self.master.ultimo_respaldo
            if resp.get("monedas"):
                self.recibir_conteo(resp["monedas"])
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
            self._actualizar_total()
            self.lbl_estado.configure(text="↩️ Datos anteriores recuperados", text_color="#FBBF24")
        else:
            self.lbl_estado.configure(text="⚠️ No hay datos previos en memoria", text_color="#9CA3AF")

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
                self.labels_cant_monedas[key].configure(
                    text=str(cant),
                    text_color="#34D399" if cant > 0 else "#6B7280",
                    font=ctk.CTkFont(size=13, weight="bold") if cant > 0 else ctk.CTkFont(size=12)
                )
            if key in self.labels_subtotal_monedas:
                self.labels_subtotal_monedas[key].configure(
                    text=fmt_cop(subtotal),
                    text_color="#A7F3D0" if cant > 0 else "#6B7280",
                    font=ctk.CTkFont(size=11, weight="bold" if cant > 0 else "normal")
                )
            if key in self.filas_monedas:
                self.filas_monedas[key].configure(
                    fg_color="#064E3B" if cant > 0 else "transparent"
                )

        self._tm = tm
        self.lbl_tm_valor.configure(text=fmt_cop(tm), text_color="#34D399", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_espera_print.configure(text="🟢 ¡CONTEO RECIBIDO!", text_color="#34D399")
        self.lbl_titulo.configure(text="✅ ¡Monedas Recibidas de la Máquina!", text_color="#34D399")
        self._actualizar_total()

        # Destello verde para despertar visual inmediato
        self._animar_destello_verde()

        # Si el modo de auto-guardar con PRINT está activado, guardar directamente sin pedir clics
        if getattr(self, "auto_guardar_print", False):
            self.lbl_estado.configure(text="⚡ Guardando automáticamente por botón PRINT...", text_color="#34D399")
            self.after(350, self._guardar)
        else:
            # Si falta el trabajador, enfocar el campo de trabajador; sino el botón guardar
            if not self.combo_trabajador.get().strip():
                self.combo_trabajador.entry.focus()
            else:
                self.btn_guardar.focus()

    def _animar_destello_verde(self):
        """Efecto visual de destello verde en el marco de monedas."""
        try:
            self.frame_mon.configure(border_color="#34D399", border_width=3, fg_color="#064E3B")
            def _normalizar():
                try:
                    self.frame_mon.configure(border_color="#10B981", border_width=2, fg_color="#1F2937")
                except Exception:
                    pass
            self.after(380, _normalizar)
        except Exception:
            pass

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
        from sheets.google_sheets import extraer_fecha_de_opcion, obtener_nombre_pestana_mes
        fecha_res = extraer_fecha_de_opcion(valor)
        pestana = obtener_nombre_pestana_mes(fecha_res)
        self.lbl_fecha_txt.configure(text=f"📁 {pestana}")

    def _obtener_fecha_final(self):
        from sheets.google_sheets import extraer_fecha_de_opcion
        return extraer_fecha_de_opcion(self.combo_dia.get())

    def _guardar(self):
        trabajador  = self.combo_trabajador.get().strip()

        # Validación obligatoria de trabajador
        if not trabajador or trabajador == "?" or trabajador.startswith("--"):
            self.btn_guardar.configure(state="normal", text="💾 GUARDAR TURNO [Enter]")
            self.lbl_estado.configure(
                text="⚠️ ¡FALTA TRABAJADOR! Escribe o selecciona el nombre.",
                text_color="#F87171"
            )
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass
            try:
                self.combo_trabajador.entry.focus()
                self.combo_trabajador.entry.configure(border_color="#EF4444")
                def _restaurar_borde():
                    try:
                        self.combo_trabajador.entry.configure(border_color="#374151")
                    except Exception:
                        pass
                self.after(2500, _restaurar_borde)
            except Exception:
                pass
            return

        parqueadero = self.combo_parqueadero.get()
        fecha       = self._obtener_fecha_final()
        hoja_tipo   = "principal" if "PRINCIPAL" in self.combo_hoja.get().upper() else "pruebas"
        billetes    = self._leer_billetes()

        self.btn_guardar.configure(state="disabled", text="⏳ Guardando...")
        self.lbl_estado.configure(text=f"Guardando en {hoja_tipo.upper()}...", text_color="#9CA3AF")

        threading.Thread(
            target=self._tarea_guardar,
            args=(trabajador, parqueadero, fecha, billetes, hoja_tipo),
            daemon=True
        ).start()

    def _tarea_guardar(self, trabajador, parqueadero, fecha, billetes, hoja_tipo="pruebas"):
        try:
            ws = conectar_sheet(hoja_tipo, fecha_str=fecha)
            fila = buscar_fila_trabajador(ws, fecha, parqueadero, trabajador)

            if fila is None:
                self.after(0, self._error, "Sin espacio disponible en esa seccion.")
                return

            fila_datos = ws.row_values(fila)
            if not fila_datos or not fila_datos[0].strip():
                escribir_nombre_trabajador(ws, fila, trabajador)

            guardar_conteo(ws, fila, self.monedas, billetes)

            # Respaldo permanente local inmediato
            try:
                from historial_db import guardar_historial
                guardar_historial(fecha, parqueadero, trabajador, self.monedas, billetes, hoja_tipo)
            except Exception as ex_db:
                print(f"Error guardando en historial: {ex_db}")

            datos_guardados = {
                "monedas": {**self.monedas},
                "billetes": {**billetes},
                "trabajador": trabajador,
                "parqueadero": parqueadero
            }
            if hasattr(self.master, "ultimo_respaldo"):
                self.master.ultimo_respaldo = datos_guardados
            self.after(0, self._exito)

        except Exception as e:
            self.after(0, self._error, str(e))

    def _exito(self):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        self.lbl_estado.configure(text="✅ ¡Guardado con éxito!", text_color="#10B981")
        def _cerrar_y_notificar():
            self.destroy()
            if self.callback_cerrar:
                self.callback_cerrar()
        # Cerrar la ventana tras 500ms y notificar para abrir el siguiente turno si está en modo continuo
        self.after(500, _cerrar_y_notificar)

    def _error(self, msg):
        self.lbl_estado.configure(text=f"Error: {msg}", text_color="#EF4444")
        self.btn_guardar.configure(state="normal", text="Reintentar")
