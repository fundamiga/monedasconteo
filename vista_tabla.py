"""
Vista Modo Tabla Excel - Interfaz visual idéntica a Google Sheets.
Permite ver las filas de hoy de cada parqueadero y tocar la fila deseada
para llenarla de inmediato con las monedas contadas y billetes.
"""

import threading
import customtkinter as ctk

from config.datos import TRABAJADORES
from sheets.google_sheets import (
    conectar_sheet, obtener_estructura_hoy, guardar_fila_directa,
    calcular_totales
)


def fmt_cop(valor):
    if not valor:
        return "$ 0"
    if isinstance(valor, str):
        v_limpio = valor.replace("$", "").replace(".", "").replace(",", "").strip()
        try:
            val = float(v_limpio)
            return f"$ {val:,.0f}".replace(",", ".")
        except:
            return valor
    try:
        return f"$ {valor:,.0f}".replace(",", ".")
    except:
        return str(valor)


class VistaTablaExcel(ctk.CTkFrame):
    """
    Componente visual que muestra la tabla de parqueaderos del día actual.
    La operadora simplemente toca la fila donde quiere registrar el conteo.
    """

    def __init__(self, parent, callback_log=None):
        super().__init__(parent, fg_color="transparent")
        self.callback_log = callback_log or (lambda msg: None)

        self.monedas_actuales = {}
        self.datos_parqueaderos = []
        self.ws = None

        self._crear_ui()
        self.recargar_datos()

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── PANEL SUPERIOR: Conteo pendiente y Billetes rápidos ──
        self.top_card = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        self.top_card.grid(row=0, column=0, padx=10, pady=(6, 8), sticky="ew")

        # Fila 1 del panel: Estado del conteo
        f_estado = ctk.CTkFrame(self.top_card, fg_color="transparent")
        f_estado.pack(fill="x", padx=12, pady=(10, 4))

        self.lbl_estado_conteo = ctk.CTkLabel(
            f_estado,
            text="⚪ Esperando conteo de monedas de la máquina...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#9CA3AF"
        )
        self.lbl_estado_conteo.pack(side="left")

        self.btn_recargar = ctk.CTkButton(
            f_estado,
            text="🔄 Recargar Tabla",
            width=130, height=28,
            fg_color="#374151", hover_color="#4B5563",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.recargar_datos
        )
        self.btn_recargar.pack(side="right")

        # Fila 2: Resumen de monedas contadas
        self.lbl_resumen_monedas = ctk.CTkLabel(
            self.top_card,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#60A5FA"
        )
        self.lbl_resumen_monedas.pack(anchor="w", padx=12, pady=(0, 4))

        # Fila 3: Entrada rápida de billetes
        f_billetes = ctk.CTkFrame(self.top_card, fg_color="#111827", corner_radius=8)
        f_billetes.pack(fill="x", padx=12, pady=(2, 10))

        ctk.CTkLabel(
            f_billetes, text="💵 Billetes (si hay):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FBBF24"
        ).pack(side="left", padx=(10, 6), pady=6)

        self.campos_billetes = {}
        for denom, clave in [
            ("$2k", "2000"), ("$5k", "5000"), ("$10k", "10000"),
            ("$20k", "20000"), ("$50k", "50000"), ("$100k", "100000")
        ]:
            ctk.CTkLabel(f_billetes, text=denom, text_color="#9CA3AF", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 2))
            e = ctk.CTkEntry(f_billetes, width=46, height=26, placeholder_text="0")
            e.pack(side="left", padx=(0, 6))
            e.bind("<KeyRelease>", lambda evt: self._recalcular_totales_billetes())
            self.campos_billetes[clave] = e

        self.lbl_total_vista = ctk.CTkLabel(
            f_billetes,
            text="Total turno: $ 0",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10B981"
        )
        self.lbl_total_vista.pack(side="right", padx=12)

        # ── TABLA CON SCROLL (Igual a Excel) ──
        self.scroll_tabla = ctk.CTkScrollableFrame(
            self,
            corner_radius=10,
            fg_color="#111827"
        )
        self.scroll_tabla.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.scroll_tabla.grid_columnconfigure(1, weight=1)

        self.lbl_cargando = ctk.CTkLabel(
            self.scroll_tabla,
            text="⏳ Conectando con Google Sheets y cargando filas de hoy...",
            font=ctk.CTkFont(size=14),
            text_color="#9CA3AF"
        )
        self.lbl_cargando.pack(pady=40)

    # ─────────────────────────────────────────
    # CARGA Y RENDERIZADO DE LA TABLA
    # ─────────────────────────────────────────

    def recargar_datos(self):
        """Descarga la estructura de filas de hoy desde el Sheet en segundo plano."""
        self.btn_recargar.configure(state="disabled", text="⏳ Cargando...")
        threading.Thread(target=self._hilo_cargar, daemon=True).start()

    def _hilo_cargar(self):
        try:
            if not self.ws:
                self.ws = conectar_sheet()
            datos = obtener_estructura_hoy(self.ws)
            self.after(0, self._renderizar_tabla, datos)
        except Exception as e:
            self.callback_log(f"Error al cargar tabla: {e}")
            self.after(0, self._error_carga, str(e))

    def _error_carga(self, error):
        self.btn_recargar.configure(state="normal", text="🔄 Recargar Tabla")
        for w in self.scroll_tabla.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.scroll_tabla,
            text=f"❌ No se pudo cargar el Sheet: {error}",
            text_color="#EF4444"
        ).pack(pady=30)

    def _renderizar_tabla(self, datos):
        self.btn_recargar.configure(state="normal", text="🔄 Recargar Tabla")
        self.datos_parqueaderos = datos

        # Limpiar tabla previa
        for w in self.scroll_tabla.winfo_children():
            w.destroy()

        if not datos:
            ctk.CTkLabel(
                self.scroll_tabla,
                text="⚠️ No se encontraron filas para el día de hoy en el Sheet.",
                text_color="#FBBF24"
            ).pack(pady=30)
            return

        # ── Encabezado tipo hoja de cálculo ──
        f_header = ctk.CTkFrame(self.scroll_tabla, fg_color="#1F2937", corner_radius=6, height=32)
        f_header.pack(fill="x", padx=4, pady=(2, 6))

        ctk.CTkLabel(f_header, text="Fila", width=45, font=ctk.CTkFont(size=11, weight="bold"), text_color="#9CA3AF").pack(side="left", padx=4)
        ctk.CTkLabel(f_header, text="Trabajador", width=220, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9CA3AF").pack(side="left", padx=4)
        ctk.CTkLabel(f_header, text="Monedas", width=90, font=ctk.CTkFont(size=11, weight="bold"), text_color="#60A5FA").pack(side="left", padx=4)
        ctk.CTkLabel(f_header, text="Billetes", width=90, font=ctk.CTkFont(size=11, weight="bold"), text_color="#FBBF24").pack(side="left", padx=4)
        ctk.CTkLabel(f_header, text="Total Turno", width=100, font=ctk.CTkFont(size=11, weight="bold"), text_color="#10B981").pack(side="left", padx=4)
        ctk.CTkLabel(f_header, text="Acción rápida", width=160, font=ctk.CTkFont(size=11, weight="bold"), text_color="#E5E7EB").pack(side="right", padx=10)

        # ── Secciones por parqueadero ──
        for p in datos:
            nombre_p = p["parqueadero"]
            filas = p["filas"]
            total_p = p.get("total", "")

            # Barra del Parqueadero
            f_parque = ctk.CTkFrame(self.scroll_tabla, fg_color="#1E3A5F", corner_radius=6, height=28)
            f_parque.pack(fill="x", padx=4, pady=(8, 2))

            ctk.CTkLabel(
                f_parque,
                text=f"📍 {nombre_p}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#93C5FD"
            ).pack(side="left", padx=10, pady=4)

            if total_p:
                ctk.CTkLabel(
                    f_parque,
                    text=f"Total: {fmt_cop(total_p)}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#6EE7B7"
                ).pack(side="right", padx=10)

            # Filas del parqueadero
            for f in filas:
                self._crear_fila_visual(nombre_p, f)

    def _crear_fila_visual(self, parqueadero, f):
        num_fila = f["fila"]
        trabajador = f["trabajador"]
        total_m = f["total_monedas"]
        total_b = f["total_billetes"]
        total_t = f["total_turno"]
        vacia = f["vacia"]

        color_bg = "#1A202C" if vacia else "#14291F"
        fila_frame = ctk.CTkFrame(self.scroll_tabla, fg_color=color_bg, corner_radius=4, height=32)
        fila_frame.pack(fill="x", padx=4, pady=1)

        # Número de fila
        ctk.CTkLabel(
            fila_frame, text=str(num_fila), width=45,
            text_color="#6B7280", font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=4)

        # Nombre del trabajador
        txt_nombre = trabajador if trabajador else "(Fila vacía disponible)"
        color_nombre = "#E5E7EB" if trabajador else "#9CA3AF"
        lbl_nom = ctk.CTkLabel(
            fila_frame, text=txt_nombre, width=220, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold" if trabajador else "normal"),
            text_color=color_nombre
        )
        lbl_nom.pack(side="left", padx=4)

        # Totales
        ctk.CTkLabel(
            fila_frame, text=fmt_cop(total_m) if total_m else "-",
            width=90, text_color="#93C5FD", font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=4)

        ctk.CTkLabel(
            fila_frame, text=fmt_cop(total_b) if total_b else "-",
            width=90, text_color="#FDE68A", font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=4)

        ctk.CTkLabel(
            fila_frame, text=fmt_cop(total_t) if total_t else "-",
            width=100, text_color="#34D399", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=4)

        # Botón de tocar fila
        hay_conteo = bool(self.monedas_actuales)
        btn_txt = "📥 TOCAR PARA LLENAR" if vacia else "🔄 Reemplazar"
        btn_color = "#10B981" if (hay_conteo and vacia) else ("#2563EB" if vacia else "#4B5563")

        btn_accion = ctk.CTkButton(
            fila_frame,
            text=btn_txt,
            width=160, height=26,
            fg_color=btn_color,
            hover_color="#059669",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda p=parqueadero, nf=num_fila, t=trabajador, fr=fila_frame: self._tocar_fila(p, nf, t, fr)
        )
        btn_accion.pack(side="right", padx=8, pady=3)

    # ─────────────────────────────────────────
    # ACCIÓN AL TOCAR LA FILA
    # ─────────────────────────────────────────

    def _tocar_fila(self, parqueadero, num_fila, trabajador_actual, frame_fila):
        """La operadora tocó esta fila para llenarla."""
        if not self.monedas_actuales:
            # Si aún no contó monedas, preguntamos si desea registrar solo billetes
            self._abrir_dialogo_confirmacion(parqueadero, num_fila, trabajador_actual, frame_fila, monedas_vacias=True)
            return

        self._abrir_dialogo_confirmacion(parqueadero, num_fila, trabajador_actual, frame_fila, monedas_vacias=False)

    def _abrir_dialogo_confirmacion(self, parqueadero, num_fila, trabajador_actual, frame_fila, monedas_vacias=False):
        """Diálogo rápido que pide confirmar o elegir el trabajador antes de escribir."""
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar Fila")
        dialogo.geometry("420x280")
        dialogo.resizable(False, False)
        dialogo.attributes("-topmost", True)

        # Centrar
        dialogo.update_idletasks()
        x = (dialogo.winfo_screenwidth() // 2) - 210
        y = (dialogo.winfo_screenheight() // 2) - 140
        dialogo.geometry(f"420x280+{x}+{y}")

        ctk.CTkLabel(
            dialogo,
            text=f"📍 {parqueadero} — Fila {num_fila}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#60A5FA"
        ).pack(pady=(15, 6))

        # Selector de trabajador
        ctk.CTkLabel(dialogo, text="Selecciona el trabajador:").pack(anchor="w", padx=30, pady=(6, 2))
        combo_t = ctk.CTkComboBox(dialogo, values=TRABAJADORES, width=320)
        combo_t.set(trabajador_actual if trabajador_actual else TRABAJADORES[0])
        combo_t.pack(padx=30, pady=(0, 10))

        # Resumen del monto
        billetes = self._leer_billetes()
        monedas = self.monedas_actuales if not monedas_vacias else {}
        tm, tb, tt = calcular_totales(monedas, billetes)

        f_resumen = ctk.CTkFrame(dialogo, fg_color="#1F2937", corner_radius=8)
        f_resumen.pack(fill="x", padx=30, pady=4)
        ctk.CTkLabel(f_resumen, text=f"Monedas: {fmt_cop(tm)} | Billetes: {fmt_cop(tb)}", font=ctk.CTkFont(size=11), text_color="#9CA3AF").pack(pady=3)
        ctk.CTkLabel(f_resumen, text=f"TOTAL: {fmt_cop(tt)}", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10B981").pack(pady=(0, 4))

        lbl_guardando = ctk.CTkLabel(dialogo, text="", font=ctk.CTkFont(size=11), text_color="#9CA3AF")
        lbl_guardando.pack(pady=2)

        # Botones
        f_btns = ctk.CTkFrame(dialogo, fg_color="transparent")
        f_btns.pack(fill="x", padx=30, pady=(6, 12))

        ctk.CTkButton(f_btns, text="Cancelar", fg_color="#374151", width=90, command=dialogo.destroy).pack(side="left")

        def ejecutar_guardado():
            t_elegido = combo_t.get()
            btn_ok.configure(state="disabled", text="Guardando...")
            lbl_guardando.configure(text="Escribiendo en Google Sheets...", text_color="#9CA3AF")

            def tarea():
                try:
                    guardar_fila_directa(self.ws, num_fila, t_elegido, monedas, billetes)
                    self.after(0, lambda: self._guardado_exitoso(dialogo, frame_fila, t_elegido, tm, tb, tt))
                except Exception as ex:
                    self.after(0, lambda: lbl_guardando.configure(text=f"Error: {ex}", text_color="#EF4444"))
                    self.after(0, lambda: btn_ok.configure(state="normal", text="Reintentar"))

            threading.Thread(target=tarea, daemon=True).start()

        btn_ok = ctk.CTkButton(
            f_btns, text="💾 ¡Guardar en Excel!",
            fg_color="#107C41", hover_color="#059669",
            font=ctk.CTkFont(weight="bold"), width=180,
            command=ejecutar_guardado
        )
        btn_ok.pack(side="right")

    def _guardado_exitoso(self, dialogo, frame_fila, trabajador, tm, tb, tt):
        dialogo.destroy()

        # Resaltar la fila en verde brillante en la tabla
        frame_fila.configure(fg_color="#064E3B")

        # Limpiar monedas pendientes y billetes
        self.monedas_actuales = {}
        for e in self.campos_billetes.values():
            e.delete(0, "end")

        self.lbl_estado_conteo.configure(
            text=f"✅ Guardado para {trabajador} ({fmt_cop(tt)}) — Esperando nuevo conteo...",
            text_color="#10B981"
        )
        self.lbl_resumen_monedas.configure(text="")
        self.lbl_total_vista.configure(text="Total turno: $ 0")

        self.callback_log(f"Fila {trabajador} guardada exitosamente.")

        # Recargar para refrescar totales
        self.after(1500, self.recargar_datos)

    # ─────────────────────────────────────────
    # MANEJO DE DATOS SERIALES
    # ─────────────────────────────────────────

    def recibir_conteo_monedas(self, monedas):
        """Llamado cuando la CC358 emite un nuevo conteo."""
        self.monedas_actuales = monedas

        # Calcular monto total de monedas
        tm, _, _ = calcular_totales(monedas, {})

        detalles = []
        for denom, clave in [("$1000", "1000"), ("$500", "500"), ("$200A", "200a"), ("$200B", "200b"), ("$100A", "100a"), ("$100B", "100b"), ("$50A", "50a"), ("$50B", "50b")]:
            cant = monedas.get(clave, 0)
            if cant:
                detalles.append(f"{denom}: {cant}")

        txt_detalles = " | ".join(detalles)

        self.lbl_estado_conteo.configure(
            text=f"🟢 ¡MONEDAS LISTAS! Total: {fmt_cop(tm)} — Toca la fila abajo 👇",
            text_color="#10B981"
        )
        self.lbl_resumen_monedas.configure(text=f"Desglose: {txt_detalles}")
        self._recalcular_totales_billetes()

    def _leer_billetes(self):
        result = {}
        for key, entry in self.campos_billetes.items():
            v = entry.get().strip()
            result[key] = int(v) if v.isdigit() else 0
        return result

    def _recalcular_totales_billetes(self):
        billetes = self._leer_billetes()
        tm, tb, tt = calcular_totales(self.monedas_actuales, billetes)
        self.lbl_total_vista.configure(text=f"Total turno: {fmt_cop(tt)}")


class VentanaTablaExcel(ctk.CTkToplevel):
    """Ventana independiente para el Modo Tabla Excel (Tocar Fila)."""

    def __init__(self, parent, callback_log=None):
        super().__init__(parent)
        self.title("📊 Modo Tabla Excel — Tocar Fila")
        self.geometry("1000x720")
        self.minsize(850, 550)

        self.vista = VistaTablaExcel(self, callback_log=callback_log)
        self.vista.pack(fill="both", expand=True, padx=5, pady=5)

    def recibir_conteo_monedas(self, monedas):
        if hasattr(self, 'vista'):
            self.vista.recibir_conteo_monedas(monedas)

