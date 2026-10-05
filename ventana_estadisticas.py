"""
ventana_estadisticas.py — Ventana de Estadísticas, Balances y Reportes Quincenales/Mensuales
===========================================================================================
Permite consultar:
- Cuántas veces apareció cada trabajador en la quincena o mes (turnos trabajados).
- Cuánto dinero recaudó cada trabajador en total.
- Promedio por turno, monedas vs billetes.
- Balances globales de recaudo y comparativa gráfica profesional.
- Exportación a CSV / Excel con un solo clic.
- Sincronización directa con Google Sheets para cargar historial histórico.
"""

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from datetime import datetime

from config.datos import PARQUEADEROS
from historial_db import (
    obtener_balance_estadisticas,
    exportar_reporte_balance_csv,
    sincronizar_desde_sheets
)


def fmt_cop(val):
    try:
        return f"$ {int(val):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"


class VentanaEstadisticas(ctk.CTkToplevel):
    """Ventana completa de métricas, estadísticas y balances de recaudo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("📈 Balances y Estadísticas de Recaudo — ConteoCC358")
        self.geometry("1120x720")
        self.minsize(980, 620)
        self.configure(fg_color="#0F172A")

        self.datos_actuales = None
        self._centrar()
        self._crear_ui()
        self.after(100, self._cargar_datos)

    def _centrar(self):
        self.update_idletasks()
        w, h = 1120, 720
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(20, (sw - w) // 2)
        y = max(20, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── 1. HEADER Y BARRA DE FILTROS SUPERIOR ──
        f_header = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10)
        f_header.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")

        # Título y acciones principales
        f_tit = ctk.CTkFrame(f_header, fg_color="transparent")
        f_tit.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(
            f_tit,
            text="📊 Control de Recaudo, Balances y Estadísticas",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left")

        self.btn_exportar = ctk.CTkButton(
            f_tit, text="📥 Exportar Excel/CSV",
            fg_color="#059669", hover_color="#047857",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30, width=150,
            command=self._exportar_balance
        )
        self.btn_exportar.pack(side="right", padx=(6, 0))

        self.btn_sync = ctk.CTkButton(
            f_tit, text="🔄 Sincronizar desde Sheets",
            fg_color="#4F46E5", hover_color="#4338CA",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30, width=175,
            command=self._sincronizar_sheets
        )
        self.btn_sync.pack(side="right", padx=6)

        # Fila de Filtros
        f_filtros = ctk.CTkFrame(f_header, fg_color="transparent")
        f_filtros.pack(fill="x", padx=14, pady=(4, 8))

        # Filtro Período (Quincena / Mes)
        ctk.CTkLabel(f_filtros, text="Período:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(side="left", padx=(0, 4))
        self.combo_quincena = ctk.CTkComboBox(
            f_filtros,
            values=["1ra Quincena (Días 1 al 15)", "2da Quincena (Días 16 al 31)", "Mes Completo", "Todo el Historial"],
            width=210, height=28,
            command=lambda v: self._cargar_datos()
        )
        # Por defecto seleccionar la quincena actual
        dia_hoy = datetime.now().day
        if dia_hoy <= 15:
            self.combo_quincena.set("1ra Quincena (Días 1 al 15)")
        else:
            self.combo_quincena.set("2da Quincena (Días 16 al 31)")
        self.combo_quincena.pack(side="left", padx=(0, 10))

        # Filtro Mes
        ctk.CTkLabel(f_filtros, text="Mes:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(side="left", padx=(0, 4))
        meses_opciones = ["OCTUBRE 2026", "SEPTIEMBRE 2026", "NOVIEMBRE 2026", "DICIEMBRE 2026", "Todos los Meses"]
        self.combo_mes = ctk.CTkComboBox(
            f_filtros, values=meses_opciones, width=150, height=28,
            command=lambda v: self._cargar_datos()
        )
        # Mes actual por defecto
        mes_num = datetime.now().month
        nombres_mes = {9: "SEPTIEMBRE 2026", 10: "OCTUBRE 2026", 11: "NOVIEMBRE 2026", 12: "DICIEMBRE 2026"}
        self.combo_mes.set(nombres_mes.get(mes_num, "OCTUBRE 2026"))
        self.combo_mes.pack(side="left", padx=(0, 10))

        # Filtro Parqueadero
        ctk.CTkLabel(f_filtros, text="Parqueadero:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(side="left", padx=(0, 4))
        self.combo_parqueadero = ctk.CTkComboBox(
            f_filtros, values=["TODOS"] + PARQUEADEROS, width=130, height=28,
            command=lambda v: self._cargar_datos()
        )
        self.combo_parqueadero.set("TODOS")
        self.combo_parqueadero.pack(side="left", padx=(0, 10))

        # Buscador en vivo de trabajador
        ctk.CTkLabel(f_filtros, text="Buscar:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94A3B8").pack(side="left", padx=(0, 4))
        self.entry_buscar = ctk.CTkEntry(
            f_filtros, placeholder_text="Nombre de persona...", width=160, height=28
        )
        self.entry_buscar.pack(side="left", padx=(0, 8))
        self.entry_buscar.bind("<KeyRelease>", lambda e: self._cargar_datos())

        # Botón limpiar filtros
        ctk.CTkButton(
            f_filtros, text="✕", width=28, height=28,
            fg_color="#334155", hover_color="#475569",
            command=self._limpiar_filtros
        ).pack(side="left")

        # ── 2. TARJETAS RESUMEN (KPIS) ──
        f_kpis = ctk.CTkFrame(self, fg_color="transparent")
        f_kpis.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")
        for c in range(5):
            f_kpis.grid_columnconfigure(c, weight=1)

        self.kpi_total = self._crear_kpi_card(f_kpis, 0, "💰 TOTAL RECAUDADO", "$ 0", "#10B981")
        self.kpi_monedas = self._crear_kpi_card(f_kpis, 1, "🪙 TOTAL MONEDAS", "$ 0 (0%)", "#38BDF8")
        self.kpi_billetes = self._crear_kpi_card(f_kpis, 2, "💵 TOTAL BILLETES", "$ 0 (0%)", "#F59E0B")
        self.kpi_turnos = self._crear_kpi_card(f_kpis, 3, "👥 TURNOS TOTALES", "0 turnos", "#A855F7")
        self.kpi_top = self._crear_kpi_card(f_kpis, 4, "🥇 MAYOR RECAUDO", "N/A", "#EC4899")

        # ── 3. CUERPO PRINCIPAL CON PESTAÑAS (TABVIEW) ──
        self.tabview = ctk.CTkTabview(self, fg_color="#1E293B", corner_radius=10)
        self.tabview.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="nsew")

        self.tab_trabajadores = self.tabview.add("👥 Ranking por Persona (Nómina y Turnos)")
        self.tab_graficas = self.tabview.add("📊 Gráficas y Comparativas")
        self.tab_parqueaderos = self.tabview.add("🏢 Rentabilidad y Balance por Parqueadero")

        self._crear_tab_trabajadores()
        self._crear_tab_graficas()
        self._crear_tab_parqueaderos()

    def _crear_kpi_card(self, parent, col, titulo, valor_inicial, color_acento):
        card = ctk.CTkFrame(parent, fg_color="#1E293B", corner_radius=8, border_width=1, border_color="#334155")
        card.grid(row=0, column=col, padx=4, sticky="ew")

        ctk.CTkLabel(
            card, text=titulo, font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94A3B8"
        ).pack(anchor="w", padx=10, pady=(6, 2))

        lbl_val = ctk.CTkLabel(
            card, text=valor_inicial, font=ctk.CTkFont(size=14, weight="bold"),
            text_color=color_acento
        )
        lbl_val.pack(anchor="w", padx=10, pady=(0, 6))
        return lbl_val

    def _crear_tab_trabajadores(self):
        tab = self.tab_trabajadores
        tab.grid_columnconfigure(0, weight=3)
        tab.grid_columnconfigure(1, weight=2)
        tab.grid_rowconfigure(0, weight=1)

        # Panel Izquierdo: Tabla de Trabajadores
        f_left = ctk.CTkFrame(tab, fg_color="#0F172A", corner_radius=8)
        f_left.grid(row=0, column=0, padx=(6, 4), pady=6, sticky="nsew")
        f_left.grid_columnconfigure(0, weight=1)
        f_left.grid_rowconfigure(1, weight=1)

        lbl_info = ctk.CTkLabel(
            f_left,
            text="📋 Personas encontradas en el período — Toca una fila para ver el desglose:",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8"
        )
        lbl_info.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="w")

        # Treeview de trabajadores
        f_tree = ctk.CTkFrame(f_left, fg_color="transparent")
        f_tree.grid(row=1, column=0, padx=6, pady=(0, 6), sticky="nsew")
        f_tree.grid_columnconfigure(0, weight=1)
        f_tree.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background="#0F172A",
                        foreground="#F8FAFC",
                        fieldbackground="#0F172A",
                        rowheight=26,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                        background="#1E293B",
                        foreground="#94A3B8",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", "#2563EB")],
                  foreground=[("selected", "#FFFFFF")])

        columnas = ("pos", "nombre", "turnos", "recaudo", "promedio", "monedas", "billetes")
        self.tree_t = ttk.Treeview(f_tree, columns=columnas, show="headings", selectmode="browse")

        self.tree_t.heading("pos", text="#")
        self.tree_t.heading("nombre", text="Trabajador / Persona")
        self.tree_t.heading("turnos", text="Turnos (#)")
        self.tree_t.heading("recaudo", text="Total Recaudado")
        self.tree_t.heading("promedio", text="Promedio x Turno")
        self.tree_t.heading("monedas", text="Monedas")
        self.tree_t.heading("billetes", text="Billetes")

        self.tree_t.column("pos", width=35, anchor="center")
        self.tree_t.column("nombre", width=180, anchor="w")
        self.tree_t.column("turnos", width=70, anchor="center")
        self.tree_t.column("recaudo", width=110, anchor="e")
        self.tree_t.column("promedio", width=105, anchor="e")
        self.tree_t.column("monedas", width=95, anchor="e")
        self.tree_t.column("billetes", width=95, anchor="e")

        sb = ttk.Scrollbar(f_tree, orient="vertical", command=self.tree_t.yview)
        self.tree_t.configure(yscrollcommand=sb.set)

        self.tree_t.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self.tree_t.bind("<<TreeviewSelect>>", self._on_seleccionar_trabajador)

        # Panel Derecho: Detalle de turnos de la persona seleccionada
        self.f_detalle = ctk.CTkFrame(tab, fg_color="#0F172A", corner_radius=8)
        self.f_detalle.grid(row=0, column=1, padx=(4, 6), pady=6, sticky="nsew")
        self.f_detalle.grid_columnconfigure(0, weight=1)
        self.f_detalle.grid_rowconfigure(1, weight=1)

        self.lbl_detalle_titulo = ctk.CTkLabel(
            self.f_detalle, text="🔍 Selecciona una persona para ver sus turnos",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#38BDF8"
        )
        self.lbl_detalle_titulo.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="w")

        # Treeview de turnos individuales
        f_sub_tree = ctk.CTkFrame(self.f_detalle, fg_color="transparent")
        f_sub_tree.grid(row=1, column=0, padx=6, pady=(0, 6), sticky="nsew")
        f_sub_tree.grid_columnconfigure(0, weight=1)
        f_sub_tree.grid_rowconfigure(0, weight=1)

        cols_sub = ("fecha", "parqueadero", "turno", "monedas", "billetes")
        self.tree_sub = ttk.Treeview(f_sub_tree, columns=cols_sub, show="headings", selectmode="none")
        self.tree_sub.heading("fecha", text="Fecha")
        self.tree_sub.heading("parqueadero", text="Parqueadero")
        self.tree_sub.heading("turno", text="Total Turno")
        self.tree_sub.heading("monedas", text="Monedas")
        self.tree_sub.heading("billetes", text="Billetes")

        self.tree_sub.column("fecha", width=75, anchor="center")
        self.tree_sub.column("parqueadero", width=95, anchor="w")
        self.tree_sub.column("turno", width=90, anchor="e")
        self.tree_sub.column("monedas", width=80, anchor="e")
        self.tree_sub.column("billetes", width=80, anchor="e")

        sb_sub = ttk.Scrollbar(f_sub_tree, orient="vertical", command=self.tree_sub.yview)
        self.tree_sub.configure(yscrollcommand=sb_sub.set)

        self.tree_sub.grid(row=0, column=0, sticky="nsew")
        sb_sub.grid(row=0, column=1, sticky="ns")

    def _crear_tab_graficas(self):
        tab = self.tab_graficas
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        self.scroll_graficas = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.scroll_graficas.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.scroll_graficas.grid_columnconfigure(0, weight=1)

    def _crear_tab_parqueaderos(self):
        tab = self.tab_parqueaderos
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        # 1. Barra superior: Selector de Modo, Toggle ARL y Sincronizar Supabase
        f_top = ctk.CTkFrame(tab, fg_color="#0F172A", corner_radius=8)
        f_top.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")

        self.modo_finanzas = ctk.StringVar(value="tiempo_real")
        self.seg_modo = ctk.CTkSegmentedButton(
            f_top,
            values=["⚡ Estimado en Tiempo Real (En Curso)", "💼 Nómina Oficial Liquidada"],
            variable=self.modo_finanzas,
            command=self._cambiar_modo_finanzas,
            font=ctk.CTkFont(size=11, weight="bold"),
            selected_color="#2563EB",
            selected_hover_color="#1D4ED8",
            height=30
        )
        self.seg_modo.pack(side="left", padx=10, pady=6)

        self.var_arl = ctk.BooleanVar(value=True)
        self.chk_arl = ctk.CTkCheckBox(
            f_top,
            text="Incluir ARL proporcional ($2.540/turno)",
            variable=self.var_arl,
            command=self._on_toggle_arl,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38BDF8",
            fg_color="#0284C7",
            hover_color="#0369A1"
        )
        self.chk_arl.pack(side="left", padx=12, pady=6)

        self.btn_sync_nomina = ctk.CTkButton(
            f_top,
            text="🔄 Sincronizar Supabase",
            fg_color="#0284C7", hover_color="#0369A1",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=28, width=175,
            command=self._sincronizar_nomina
        )
        self.btn_sync_nomina.pack(side="right", padx=10, pady=6)

        # Subtítulo informativo / estado de cálculo
        self.lbl_info_modo = ctk.CTkLabel(
            tab,
            text="⚡ Estimación en tiempo real día a día según turnos contados y tarifas de trabajadores en Supabase.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        )
        self.lbl_info_modo.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="w")

        # 2. Tarjetas Resumen Financiero del Período
        f_kpi_fin = ctk.CTkFrame(tab, fg_color="#0F172A", corner_radius=8)
        f_kpi_fin.grid(row=2, column=0, padx=8, pady=(0, 6), sticky="ew")
        for i in range(5):
            f_kpi_fin.grid_columnconfigure(i, weight=1)

        self.lbl_kpi_titulos = []
        def _sub_kpi(col, titulo, valor, color):
            f = ctk.CTkFrame(f_kpi_fin, fg_color="#1E293B", corner_radius=6, border_width=1, border_color="#334155")
            f.grid(row=0, column=col, padx=4, pady=6, sticky="ew")
            lbl_t = ctk.CTkLabel(f, text=titulo, font=ctk.CTkFont(size=9, weight="bold"), text_color="#94A3B8")
            lbl_t.pack(anchor="w", padx=8, pady=(4, 1))
            self.lbl_kpi_titulos.append(lbl_t)
            lbl = ctk.CTkLabel(f, text=valor, font=ctk.CTkFont(size=13, weight="bold"), text_color=color)
            lbl.pack(anchor="w", padx=8, pady=(0, 4))
            return lbl

        self.lbl_fin_kpi0 = _sub_kpi(0, "🪙 RECAUDO ACUMULADO", "$ 0", "#38BDF8")
        self.lbl_fin_kpi1 = _sub_kpi(1, "👥 SUELDOS ESTIMADOS", "$ 0", "#F59E0B")
        self.lbl_fin_kpi2 = _sub_kpi(2, "🛡️ ARL ESTIMADA", "$ 0", "#A855F7")
        self.lbl_fin_kpi3 = _sub_kpi(3, "🏆 GANANCIA EN VIVO", "$ 0", "#10B981")
        self.lbl_fin_kpi4 = _sub_kpi(4, "🔮 PROYECCIÓN CIERRE", "$ 0", "#38BDF8")

        # 3. Contenedor de Tablas Financieras
        self.f_tree_p = ctk.CTkFrame(tab, fg_color="#0F172A", corner_radius=8)
        self.f_tree_p.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.f_tree_p.grid_columnconfigure(0, weight=1)
        self.f_tree_p.grid_rowconfigure(0, weight=1)

        # ── TABLA A: TIEMPO REAL ──
        cols_tr = ("pos", "parqueadero", "turnos", "recaudo", "sueldos", "arl", "costo_tot", "ganancia", "margen", "proy_15", "proy_30", "estado")
        self.tree_tr = ttk.Treeview(self.f_tree_p, columns=cols_tr, show="headings", selectmode="none")
        self.tree_tr.heading("pos", text="#")
        self.tree_tr.heading("parqueadero", text="Parqueadero")
        self.tree_tr.heading("turnos", text="Turnos (#)")
        self.tree_tr.heading("recaudo", text="🪙 Recaudo")
        self.tree_tr.heading("sueldos", text="Sueldos Est.")
        self.tree_tr.heading("arl", text="ARL Est.")
        self.tree_tr.heading("costo_tot", text="Costo Total")
        self.tree_tr.heading("ganancia", text="Ganancia en Vivo")
        self.tree_tr.heading("margen", text="Margen %")
        self.tree_tr.heading("proy_15", text="🔮 Proy. 15d")
        self.tree_tr.heading("proy_30", text="🔮 Proy. 30d")
        self.tree_tr.heading("estado", text="Estado")

        self.tree_tr.column("pos", width=32, anchor="center")
        self.tree_tr.column("parqueadero", width=125, anchor="w")
        self.tree_tr.column("turnos", width=65, anchor="center")
        self.tree_tr.column("recaudo", width=95, anchor="e")
        self.tree_tr.column("sueldos", width=95, anchor="e")
        self.tree_tr.column("arl", width=75, anchor="e")
        self.tree_tr.column("costo_tot", width=95, anchor="e")
        self.tree_tr.column("ganancia", width=115, anchor="e")
        self.tree_tr.column("margen", width=68, anchor="center")
        self.tree_tr.column("proy_15", width=105, anchor="e")
        self.tree_tr.column("proy_30", width=105, anchor="e")
        self.tree_tr.column("estado", width=100, anchor="center")

        self.tree_tr.tag_configure("ganancia", foreground="#10B981")
        self.tree_tr.tag_configure("equilibrio", foreground="#F59E0B")
        self.tree_tr.tag_configure("pérdida", foreground="#EF4444")
        self.tree_tr.tag_configure("deficit", foreground="#EF4444")

        self.sb_tr = ttk.Scrollbar(self.f_tree_p, orient="vertical", command=self.tree_tr.yview)
        self.tree_tr.configure(yscrollcommand=self.sb_tr.set)

        # ── TABLA B: NÓMINA OFICIAL LIQUIDADA ──
        cols_p = ("pos", "parqueadero", "turnos", "recaudo", "nomina_q1", "nomina_q2", "nomina_tot", "ganancia", "margen", "estado")
        self.tree_parq = ttk.Treeview(self.f_tree_p, columns=cols_p, show="headings", selectmode="none")
        self.tree_parq.heading("pos", text="#")
        self.tree_parq.heading("parqueadero", text="Parqueadero")
        self.tree_parq.heading("turnos", text="Turnos (#)")
        self.tree_parq.heading("recaudo", text="🪙 Recaudo")
        self.tree_parq.heading("nomina_q1", text="Nómina Q1")
        self.tree_parq.heading("nomina_q2", text="Nómina Q2")
        self.tree_parq.heading("nomina_tot", text="👥 Total Nómina")
        self.tree_parq.heading("ganancia", text="🟢 Ganancia Neta")
        self.tree_parq.heading("margen", text="📊 Margen %")
        self.tree_parq.heading("estado", text="Estado")

        self.tree_parq.column("pos", width=35, anchor="center")
        self.tree_parq.column("parqueadero", width=140, anchor="w")
        self.tree_parq.column("turnos", width=80, anchor="center")
        self.tree_parq.column("recaudo", width=115, anchor="e")
        self.tree_parq.column("nomina_q1", width=105, anchor="e")
        self.tree_parq.column("nomina_q2", width=105, anchor="e")
        self.tree_parq.column("nomina_tot", width=115, anchor="e")
        self.tree_parq.column("ganancia", width=125, anchor="e")
        self.tree_parq.column("margen", width=80, anchor="center")
        self.tree_parq.column("estado", width=110, anchor="center")

        self.tree_parq.tag_configure("rentable", foreground="#10B981")
        self.tree_parq.tag_configure("equilibrio", foreground="#F59E0B")
        self.tree_parq.tag_configure("deficit", foreground="#EF4444")

        self.sb_oficial = ttk.Scrollbar(self.f_tree_p, orient="vertical", command=self.tree_parq.yview)
        self.tree_parq.configure(yscrollcommand=self.sb_oficial.set)

        # Mostrar por defecto Tabla Tiempo Real
        self.tree_tr.grid(row=0, column=0, sticky="nsew")
        self.sb_tr.grid(row=0, column=1, sticky="ns")

    # ── CARGA Y RENDERIZADO DE DATOS ──

    def _obtener_parametros_filtro(self):
        # 1. Quincena
        txt_q = self.combo_quincena.get()
        if "1ra" in txt_q:
            quincena = "1ra"
        elif "2da" in txt_q:
            quincena = "2da"
        else:
            quincena = "todos"

        # 2. Mes y Año
        txt_m = self.combo_mes.get()
        mes = None
        anio = 2026
        meses_dict = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
            "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
            "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
        }
        for nombre_m, num_m in meses_dict.items():
            if nombre_m in txt_m.upper():
                mes = num_m
                break

        # 3. Parqueadero y búsqueda
        parq = self.combo_parqueadero.get()
        busqueda = self.entry_buscar.get().strip()

        return mes, anio, quincena, parq, busqueda

    def _cargar_datos(self):
        mes, anio, quincena, parq, busqueda = self._obtener_parametros_filtro()
        incluir_arl = self.var_arl.get() if hasattr(self, "var_arl") else True
        data = obtener_balance_estadisticas(
            mes=mes, anio=anio, quincena=quincena,
            filtro_trabajador=busqueda, filtro_parqueadero=parq,
            incluir_arl=incluir_arl
        )
        self.datos_actuales = data
        self._actualizar_kpis(data["totales"], data["top_turnos"], data["top_recaudo"])
        self._renderizar_tabla_trabajadores(data["trabajadores"])
        self._renderizar_graficas(data)
        self._renderizar_tabla_parqueaderos(data)

    def _actualizar_kpis(self, totales, top_turnos, top_recaudo):
        self.kpi_total.configure(text=fmt_cop(totales["total_recaudo"]))
        self.kpi_monedas.configure(text=f"{fmt_cop(totales['total_monedas'])} ({totales['pct_monedas']}%)")
        self.kpi_billetes.configure(text=f"{fmt_cop(totales['total_billetes'])} ({totales['pct_billetes']}%)")
        self.kpi_turnos.configure(text=f"{totales['total_turnos']} turnos ({totales['trabajadores_activos']} pers.)")

        if top_recaudo:
            nom_corto = top_recaudo['trabajador'][:14]
            self.kpi_top.configure(text=f"{nom_corto} ({fmt_cop(top_recaudo['total_recaudo'])})")
        else:
            self.kpi_top.configure(text="Sin datos")

    def _renderizar_tabla_trabajadores(self, lista):
        for item in self.tree_t.get_children():
            self.tree_t.delete(item)

        for item in self.tree_sub.get_children():
            self.tree_sub.delete(item)
        self.lbl_detalle_titulo.configure(text="🔍 Selecciona una persona para ver sus turnos individuales")

        for idx, t in enumerate(lista, 1):
            self.tree_t.insert("", "end", iid=str(idx), values=(
                idx,
                t["trabajador"],
                f"{t['turnos']} veces",
                fmt_cop(t["total_recaudo"]),
                fmt_cop(t["promedio"]),
                fmt_cop(t["total_monedas"]),
                fmt_cop(t["total_billetes"])
            ))

    def _on_seleccionar_trabajador(self, event):
        sel = self.tree_t.selection()
        if not sel or not self.datos_actuales:
            return
        idx = int(sel[0]) - 1
        trabajadores = self.datos_actuales.get("trabajadores", [])
        if 0 <= idx < len(trabajadores):
            t = trabajadores[idx]
            self.lbl_detalle_titulo.configure(
                text=f"👤 {t['trabajador']} — {t['turnos']} turnos | Total: {fmt_cop(t['total_recaudo'])}"
            )
            for item in self.tree_sub.get_children():
                self.tree_sub.delete(item)

            for reg in t.get("registros", []):
                self.tree_sub.insert("", "end", values=(
                    reg.get("fecha_turno", ""),
                    reg.get("parqueadero", ""),
                    fmt_cop(reg.get("total_turno", 0)),
                    fmt_cop(reg.get("total_monedas", 0)),
                    fmt_cop(reg.get("total_billetes", 0)),
                ))

    def _renderizar_graficas(self, data):
        # Limpiar frame de gráficas
        for w in self.scroll_graficas.winfo_children():
            w.destroy()

        trabajadores = data.get("trabajadores", [])
        tot_general = data["totales"]["total_recaudo"]

        # Título
        ctk.CTkLabel(
            self.scroll_graficas,
            text="🏆 TOP 10 PERSONAS CON MAYOR RECAUDO EN EL PERÍODO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#F8FAFC"
        ).pack(anchor="w", padx=10, pady=(6, 12))

        if not trabajadores or tot_general == 0:
            ctk.CTkLabel(
                self.scroll_graficas, text="No hay registros suficientes en este período para generar gráficas.",
                text_color="#64748B", font=ctk.CTkFont(size=12)
            ).pack(pady=30)
            return

        top10 = trabajadores[:10]
        max_recaudo = top10[0]["total_recaudo"] if top10 else 1

        for idx, t in enumerate(top10, 1):
            pct_global = round((t["total_recaudo"] * 100 / tot_general), 1) if tot_general > 0 else 0
            ratio_barra = t["total_recaudo"] / max_recaudo

            f_fila = ctk.CTkFrame(self.scroll_graficas, fg_color="#1E293B", corner_radius=6)
            f_fila.pack(fill="x", padx=6, pady=3)

            # Nombre y turnos
            f_txt = ctk.CTkFrame(f_fila, fg_color="transparent")
            f_txt.pack(fill="x", padx=8, pady=(4, 2))

            ctk.CTkLabel(
                f_txt,
                text=f"#{idx}  {t['trabajador']} ({t['turnos']} turnos trabajados)",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#F1F5F9"
            ).pack(side="left")

            ctk.CTkLabel(
                f_txt,
                text=f"{fmt_cop(t['total_recaudo'])}  ({pct_global}% del total)",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#38BDF8"
            ).pack(side="right")

            # Barra visual de progreso
            color_barra = "#10B981" if idx == 1 else "#3B82F6" if idx <= 3 else "#6366F1"
            prog = ctk.CTkProgressBar(f_fila, height=10, corner_radius=4, progress_color=color_barra, fg_color="#334155")
            prog.pack(fill="x", padx=8, pady=(0, 6))
            prog.set(ratio_barra)

    def _cambiar_modo_finanzas(self, valor=None):
        modo = self.modo_finanzas.get()
        if "Tiempo Real" in modo:
            self.chk_arl.configure(state="normal")
            self.tree_parq.grid_remove()
            self.sb_oficial.grid_remove()
            self.tree_tr.grid(row=0, column=0, sticky="nsew")
            self.sb_tr.grid(row=0, column=1, sticky="ns")
        else:
            self.chk_arl.configure(state="disabled")
            self.tree_tr.grid_remove()
            self.sb_tr.grid_remove()
            self.tree_parq.grid(row=0, column=0, sticky="nsew")
            self.sb_oficial.grid(row=0, column=1, sticky="ns")
        if self.datos_actuales:
            self._renderizar_tabla_parqueaderos(self.datos_actuales)

    def _on_toggle_arl(self):
        self._cargar_datos()

    def _renderizar_tabla_parqueaderos(self, data):
        if not data:
            return

        modo = self.modo_finanzas.get()
        es_tr = "Tiempo Real" in modo

        if es_tr:
            # ── RENDERIZAR TIEMPO REAL ──
            tr_data = data.get("estimado_tiempo_real", {})
            parqs_tr = tr_data.get("por_parqueadero", [])
            tot_tr = tr_data.get("totales", {})
            dias_datos = tr_data.get("dias_con_datos", 0)

            for item in self.tree_tr.get_children():
                self.tree_tr.delete(item)

            for idx, p in enumerate(parqs_tr, 1):
                estado_raw = p.get("estado", "EQUILIBRIO")
                tag = estado_raw.lower()
                gn = p.get("ganancia_neta", 0)
                signo_gn = "+" if gn > 0 else ""
                p15 = p.get("proy_quincena_15d", 0)
                signo_15 = "+" if p15 > 0 else ""
                p30 = p.get("proy_mes_30d", 0)
                signo_30 = "+" if p30 > 0 else ""

                self.tree_tr.insert("", "end", values=(
                    idx,
                    p["parqueadero"],
                    f"{p['turnos']} turnos",
                    fmt_cop(p["recaudo"]),
                    fmt_cop(p["sueldos"]),
                    fmt_cop(p["arl"]),
                    fmt_cop(p["costo_total"]),
                    f"{signo_gn}{fmt_cop(gn)}",
                    f"{p['margen_pct']}%",
                    f"{signo_15}{fmt_cop(p15)}",
                    f"{signo_30}{fmt_cop(p30)}",
                    f"● {estado_raw}"
                ), tags=(tag,))

            # KPIs Tiempo Real
            gn_total = tot_tr.get("ganancia_neta_total", 0)
            color_gn = "#10B981" if gn_total >= 0 else "#EF4444"
            signo_tot = "+" if gn_total > 0 else ""
            m_pct_tot = tot_tr.get("margen_total_pct", 0)

            if len(self.lbl_kpi_titulos) >= 5:
                self.lbl_kpi_titulos[0].configure(text="🪙 RECAUDO ACUMULADO")
                self.lbl_kpi_titulos[1].configure(text="👥 SUELDOS ESTIMADOS")
                self.lbl_kpi_titulos[2].configure(text="🛡️ ARL ESTIMADA")
                self.lbl_kpi_titulos[3].configure(text="🏆 GANANCIA EN VIVO")
                self.lbl_kpi_titulos[4].configure(text="🔮 PROYECCIÓN 15D / 30D")

            self.lbl_fin_kpi0.configure(text=fmt_cop(tot_tr.get("total_recaudo", 0)), text_color="#38BDF8")
            self.lbl_fin_kpi1.configure(text=fmt_cop(tot_tr.get("total_sueldos", 0)), text_color="#F59E0B")
            self.lbl_fin_kpi2.configure(text=fmt_cop(tot_tr.get("total_arl", 0)), text_color="#A855F7")
            self.lbl_fin_kpi3.configure(text=f"{signo_tot}{fmt_cop(gn_total)} ({m_pct_tot}%)", text_color=color_gn)

            p15_tot = tot_tr.get("proy_15_total", 0)
            p30_tot = tot_tr.get("proy_30_total", 0)
            s15 = "+" if p15_tot > 0 else ""
            s30 = "+" if p30_tot > 0 else ""
            self.lbl_fin_kpi4.configure(text=f"Q: {s15}{fmt_cop(p15_tot)} | M: {s30}{fmt_cop(p30_tot)}", text_color=color_gn)

            arl_txt = "con ARL ($2.540/turno)" if tr_data.get("incluir_arl") else "sin ARL (solo sueldos)"
            self.lbl_info_modo.configure(
                text=f"⚡ Estimación en tiempo real día a día — {dias_datos} días con turnos contados en el período ({arl_txt})."
            )

        else:
            # ── RENDERIZAR NÓMINA OFICIAL (SUPABASE) ──
            balance_fin = data.get("balance_financiero", [])
            res_nom = data.get("resumen_nomina", {})
            tot_general = data.get("totales", {}).get("total_recaudo", 0)

            for item in self.tree_parq.get_children():
                self.tree_parq.delete(item)

            for idx, p in enumerate(balance_fin, 1):
                estado_tag = p.get("estado", "EQUILIBRIO").lower()
                gn = p.get("ganancia_neta", 0)
                signo = "+" if gn > 0 else ""
                ganancia_txt = f"{signo}{fmt_cop(gn)}"

                self.tree_parq.insert("", "end", values=(
                    idx,
                    p["parqueadero"],
                    f"{p['turnos']} turnos",
                    fmt_cop(p["recaudo"]),
                    fmt_cop(p["nomina_q1"]),
                    fmt_cop(p["nomina_q2"]),
                    fmt_cop(p["nomina_total"]),
                    ganancia_txt,
                    f"{p['margen_pct']}%",
                    f"● {p['estado']}"
                ), tags=(estado_tag,))

            # KPIs Nómina Oficial
            tot_nom_parq = res_nom.get("total_nomina_parqueaderos", 0)
            tot_adm = res_nom.get("gastos_admin", 0) + res_nom.get("gastos_remesas", 0)
            utilidad = res_nom.get("utilidad_neta_fundacion", 0)
            margen = res_nom.get("margen_fundacion_pct", 0)

            if len(self.lbl_kpi_titulos) >= 5:
                self.lbl_kpi_titulos[0].configure(text="🪙 RECAUDO MÁQUINA")
                self.lbl_kpi_titulos[1].configure(text="👥 NÓMINA PARQUEADEROS")
                self.lbl_kpi_titulos[2].configure(text="🏢 ADMIN / REMESAS")
                self.lbl_kpi_titulos[3].configure(text="🏆 GANANCIA NETA LIBRE")
                self.lbl_kpi_titulos[4].configure(text="📈 MARGEN LIBRE %")

            color_utilidad = "#10B981" if utilidad >= 0 else "#EF4444"
            signo_u = "+" if utilidad > 0 else ""

            self.lbl_fin_kpi0.configure(text=fmt_cop(tot_general), text_color="#38BDF8")
            self.lbl_fin_kpi1.configure(text=fmt_cop(tot_nom_parq), text_color="#F59E0B")
            self.lbl_fin_kpi2.configure(text=fmt_cop(tot_adm), text_color="#A855F7")
            self.lbl_fin_kpi3.configure(text=f"{signo_u}{fmt_cop(utilidad)}", text_color=color_utilidad)
            self.lbl_fin_kpi4.configure(text=f"{margen}%", text_color=color_utilidad)

            qs = res_nom.get("quincenas_encontradas", [])
            qs_str = ", ".join(qs) if qs else "Ninguna liquidación oficial encontrada para este período"
            self.lbl_info_modo.configure(
                text=f"💼 Cruce oficial contra liquidaciones cerradas en Supabase: {qs_str}"
            )

    def _limpiar_filtros(self):
        self.entry_buscar.delete(0, "end")
        self.combo_parqueadero.set("TODOS")
        self._cargar_datos()

    def _exportar_balance(self):
        if not self.datos_actuales or not self.datos_actuales["trabajadores"]:
            messagebox.showinfo("Exportar", "No hay datos para exportar en este período.", parent=self)
            return

        periodo_txt = f"{self.combo_quincena.get()} - {self.combo_mes.get()}"
        fecha_sug = datetime.now().strftime("%Y%m%d_%H%M")
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar Balance de Recaudo",
            defaultextension=".csv",
            initialfile=f"Balance_Recaudo_{fecha_sug}.csv",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            try:
                n = exportar_reporte_balance_csv(ruta, self.datos_actuales, periodo_txt)
                messagebox.showinfo(
                    "Éxito",
                    f"✅ Balance exportado exitosamente con {n} trabajadores.\nPuedes abrirlo directamente en Excel.",
                    parent=self
                )
            except Exception as e:
                messagebox.showerror("Error al Exportar", f"No se pudo guardar el archivo:\n{e}", parent=self)

    def _sincronizar_sheets(self):
        txt_mes = self.combo_mes.get()
        if "TODOS" in txt_mes.upper():
            txt_mes = "OCTUBRE 2026"

        self.btn_sync.configure(state="disabled", text="⏳ Sincronizando...")

        def _tarea():
            importados, msg = sincronizar_desde_sheets(hoja_tipo="principal", mes_nombre=txt_mes)
            def _fin():
                self.btn_sync.configure(state="normal", text="🔄 Sincronizar desde Sheets")
                if importados > 0:
                    messagebox.showinfo(
                        "Sincronización Completa",
                        f"✅ Se importaron {importados} turnos desde Google Sheets ({txt_mes}) a la base de datos local.",
                        parent=self
                    )
                else:
                    messagebox.showinfo(
                        "Sincronización Completa",
                        f"Todos los turnos de {txt_mes} ya estaban sincronizados en el historial.",
                        parent=self
                    )
                self._cargar_datos()
            self.after(0, _fin)

        threading.Thread(target=_tarea, daemon=True).start()

    def _sincronizar_nomina(self):
        """Descarga en segundo plano liquidaciones y tarifas de trabajadores desde Supabase."""
        self.btn_sync_nomina.configure(state="disabled", text="⏳ Conectando...")

        def _tarea():
            from nomina_supabase import sincronizar_liquidaciones_supabase, sincronizar_trabajadores_supabase
            total_liq, err_liq = sincronizar_liquidaciones_supabase()
            total_trab, err_trab = sincronizar_trabajadores_supabase()

            def _fin():
                self.btn_sync_nomina.configure(state="normal", text="🔄 Sincronizar Supabase")
                if err_liq and err_trab:
                    messagebox.showerror(
                        "Error al Sincronizar Supabase",
                        f"No se pudo conectar a Supabase:\n{err_liq}",
                        parent=self
                    )
                else:
                    messagebox.showinfo(
                        "Sincronización Exitosa",
                        f"✅ Datos sincronizados desde Supabase:\n\n"
                        f"• {total_trab} trabajadores y tarifas para tiempo real.\n"
                        f"• {total_liq} liquidaciones oficiales de nómina.",
                        parent=self
                    )
                    self._cargar_datos()

            self.after(0, _fin)

        threading.Thread(target=_tarea, daemon=True).start()


# ── DIÁLOGO DE SEGURIDAD PARA ACCESO A BALANCES ─────────────────────────────

class DialogoContrasenaBalances(ctk.CTkToplevel):
    """
    Modal de seguridad que solicita la contraseña de administrador
    para acceder a la información de balances, rentabilidad y nómina.
    """
    CLAVE_CORRECTA = "fundamiga2026EM"

    def __init__(self, parent, callback_exito=None):
        super().__init__(parent)
        self.callback_exito = callback_exito
        self.title("Acceso Protegido — Balances")
        self.geometry("420x260")
        self.resizable(False, False)
        self.configure(fg_color="#0F172A")

        self.transient(parent)
        self.grab_set()

        # Centrar en relación a la ventana principal
        try:
            x = parent.winfo_x() + (parent.winfo_width() - 420) // 2
            y = parent.winfo_y() + (parent.winfo_height() - 260) // 2
            self.geometry(f"420x260+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        # Icono y encabezado
        lbl_icono = ctk.CTkLabel(
            self, text="🔒",
            font=ctk.CTkFont(size=36)
        )
        lbl_icono.pack(pady=(16, 2))

        lbl_titulo = ctk.CTkLabel(
            self, text="Balances y Rentabilidad Financiera",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F8FAFC"
        )
        lbl_titulo.pack(pady=(0, 2))

        lbl_sub = ctk.CTkLabel(
            self, text="Ingresa la contraseña de administrador para ver las ganancias:",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        )
        lbl_sub.pack(pady=(0, 8))

        # Campo contraseña
        f_pass = ctk.CTkFrame(self, fg_color="transparent")
        f_pass.pack(pady=4)

        self.entry_pass = ctk.CTkEntry(
            f_pass,
            show="*",
            width=240,
            height=34,
            font=ctk.CTkFont(size=13),
            placeholder_text="Contraseña autorizada"
        )
        self.entry_pass.pack(side="left", padx=(0, 6))
        self.entry_pass.focus()

        self.btn_ver = ctk.CTkButton(
            f_pass, text="👁", width=36, height=34,
            fg_color="#334155", hover_color="#475569",
            command=self._toggle_ver
        )
        self.btn_ver.pack(side="left")

        # Label error
        self.lbl_error = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#EF4444"
        )
        self.lbl_error.pack(pady=(4, 6))

        # Botones de acción
        f_btns = ctk.CTkFrame(self, fg_color="transparent")
        f_btns.pack(pady=(2, 10))

        btn_cancelar = ctk.CTkButton(
            f_btns, text="Cancelar",
            fg_color="#334155", hover_color="#475569",
            width=110, height=32,
            command=self.destroy
        )
        btn_cancelar.pack(side="left", padx=6)

        btn_entrar = ctk.CTkButton(
            f_btns, text="Acceder ➜",
            fg_color="#2563EB", hover_color="#1D4ED8",
            width=130, height=32,
            font=ctk.CTkFont(weight="bold"),
            command=self._verificar
        )
        btn_entrar.pack(side="left", padx=6)

        # Atajos de teclado
        self.bind("<Return>", lambda e: self._verificar())
        self.bind("<Escape>", lambda e: self.destroy())

    def _toggle_ver(self):
        if self.entry_pass.cget("show") == "*":
            self.entry_pass.configure(show="")
            self.btn_ver.configure(text="🔒")
        else:
            self.entry_pass.configure(show="*")
            self.btn_ver.configure(text="👁")

    def _verificar(self):
        pwd = self.entry_pass.get()
        if pwd == self.CLAVE_CORRECTA:
            self.destroy()
            if self.callback_exito:
                self.callback_exito()
        else:
            self.lbl_error.configure(text="❌ Contraseña incorrecta. Acceso denegado.")
            self.entry_pass.delete(0, "end")
            self.entry_pass.focus()

