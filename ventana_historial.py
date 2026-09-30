"""
ventana_historial.py — Ventana visual de Historial y Respaldo Permanente
========================================================================
Permite ver todos los conteos guardados históricamente, buscar por nombre
de trabajador o fecha, ver el desglose exacto de monedas/billetes y
reenviar al Google Sheets con un solo clic si algo se borró accidentalmente.
"""

import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

from historial_db import consultar_historial, exportar_csv
from config.datos import PARQUEADEROS
from sheets.google_sheets import (
    conectar_sheet, buscar_fila_trabajador,
    escribir_nombre_trabajador, guardar_conteo
)


def fmt_cop(valor):
    try:
        v = int(valor or 0)
        return f"$ {v:,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"


class VentanaHistorial(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📜 Historial de Conteos y Respaldo Permanente")
        self.geometry("980x620")
        self.minsize(850, 500)
        self.attributes("-topmost", True)

        self._crear_ui()
        self._cargar_datos()

    def _crear_ui(self):
        # ── Barra Superior: Filtros y Búsqueda ──
        frame_filtros = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=8)
        frame_filtros.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(frame_filtros, text="🔍 Buscar Trabajador:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.entry_busqueda = ctk.CTkEntry(frame_filtros, placeholder_text="Escribe el nombre...", width=200, height=30)
        self.entry_busqueda.pack(side="left", padx=4, pady=8)
        self.entry_busqueda.bind("<KeyRelease>", lambda e: self._cargar_datos())

        ctk.CTkLabel(frame_filtros, text="Parqueadero:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.combo_parqueadero = ctk.CTkComboBox(
            frame_filtros, values=["TODOS"] + PARQUEADEROS, width=130, height=30,
            command=lambda v: self._cargar_datos()
        )
        self.combo_parqueadero.set("TODOS")
        self.combo_parqueadero.pack(side="left", padx=4, pady=8)

        ctk.CTkLabel(frame_filtros, text="Fecha:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.entry_fecha = ctk.CTkEntry(frame_filtros, placeholder_text="ej: 30/2 o 2026-09", width=120, height=30)
        self.entry_fecha.pack(side="left", padx=4, pady=8)
        self.entry_fecha.bind("<KeyRelease>", lambda e: self._cargar_datos())

        ctk.CTkButton(
            frame_filtros, text="🔄 Actualizar", width=90, height=30,
            fg_color="#374151", hover_color="#4B5563",
            command=self._cargar_datos
        ).pack(side="left", padx=8, pady=8)

        ctk.CTkButton(
            frame_filtros, text="📥 Exportar CSV", width=110, height=30,
            fg_color="#059669", hover_color="#047857",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._exportar_csv
        ).pack(side="right", padx=10, pady=8)

        # ── Área Central: Tabla de Conteos + Panel Detalle ──
        frame_central = ctk.CTkFrame(self, fg_color="transparent")
        frame_central.pack(fill="both", expand=True, padx=12, pady=4)

        # Tabla estilo ttk.Treeview moderna
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background="#111827",
                        foreground="#F9FAFB",
                        rowheight=26,
                        fieldbackground="#111827",
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                        background="#1F2937",
                        foreground="#34D399",
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#065F46")])

        cols = ("id", "hora", "fecha_turno", "parqueadero", "trabajador", "tot_mon", "tot_bil", "tot_turno")
        self.tree = ttk.Treeview(frame_central, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("id", text="#")
        self.tree.heading("hora", text="Hora Guardado")
        self.tree.heading("fecha_turno", text="Fecha Turno")
        self.tree.heading("parqueadero", text="Parqueadero")
        self.tree.heading("trabajador", text="Trabajador")
        self.tree.heading("tot_mon", text="Monedas")
        self.tree.heading("tot_bil", text="Billetes")
        self.tree.heading("tot_turno", text="TOTAL TURNO")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("hora", width=130, anchor="center")
        self.tree.column("fecha_turno", width=90, anchor="center")
        self.tree.column("parqueadero", width=110, anchor="w")
        self.tree.column("trabajador", width=190, anchor="w")
        self.tree.column("tot_mon", width=100, anchor="e")
        self.tree.column("tot_bil", width=100, anchor="e")
        self.tree.column("tot_turno", width=115, anchor="e")

        scrollbar = ttk.Scrollbar(frame_central, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_registro)

        # ── Panel Lateral Derecho: Detalle y Reenvío ──
        self.frame_detalle = ctk.CTkFrame(frame_central, width=280, fg_color="#1F2937", corner_radius=8)
        self.frame_detalle.pack(side="right", fill="y", padx=(8, 0))
        self.frame_detalle.pack_propagate(False)

        ctk.CTkLabel(self.frame_detalle, text="Detalle del Registro", font=ctk.CTkFont(size=13, weight="bold"), text_color="#34D399").pack(pady=(10, 4))
        
        self.lbl_detalle_nombre = ctk.CTkLabel(self.frame_detalle, text="Selecciona un registro", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_detalle_nombre.pack(padx=8, pady=2)

        self.lbl_detalle_lugar = ctk.CTkLabel(self.frame_detalle, text="", font=ctk.CTkFont(size=11), text_color="#9CA3AF")
        self.lbl_detalle_lugar.pack(padx=8, pady=2)

        # Caja de texto con desglose
        self.txt_desglose = ctk.CTkTextbox(self.frame_detalle, height=260, font=ctk.CTkFont(size=11), fg_color="#111827")
        self.txt_desglose.pack(fill="x", padx=10, pady=8)

        # Botón REENVIAR A GOOGLE SHEETS
        self.btn_reenviar = ctk.CTkButton(
            self.frame_detalle,
            text="🔁 Reenviar a Google Sheets",
            fg_color="#0D9488", hover_color="#0F766E",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            command=self._reenviar_a_sheets,
            state="disabled"
        )
        self.btn_reenviar.pack(fill="x", padx=10, pady=(4, 6))

        self.lbl_estado_reenvio = ctk.CTkLabel(self.frame_detalle, text="", font=ctk.CTkFont(size=11), text_color="#9CA3AF")
        self.lbl_estado_reenvio.pack(padx=10, pady=2)

        # ── Barra Inferior: Resumen Totales ──
        frame_inferior = ctk.CTkFrame(self, fg_color="#111827", corner_radius=8)
        frame_inferior.pack(fill="x", padx=12, pady=(4, 10))

        self.lbl_conteo_registros = ctk.CTkLabel(frame_inferior, text="0 registros", font=ctk.CTkFont(size=12), text_color="#9CA3AF")
        self.lbl_conteo_registros.pack(side="left", padx=14, pady=6)

        self.lbl_suma_total = ctk.CTkLabel(frame_inferior, text="Suma Total: $ 0", font=ctk.CTkFont(size=13, weight="bold"), text_color="#10B981")
        self.lbl_suma_total.pack(side="right", padx=14, pady=6)

        self._registros_cargados = {}
        self._registro_seleccionado = None

    def _cargar_datos(self):
        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)

        trabajador = self.entry_busqueda.get().strip()
        parqueadero = self.combo_parqueadero.get()
        fecha = self.entry_fecha.get().strip()

        registros = consultar_historial(
            filtro_trabajador=trabajador,
            filtro_parqueadero=parqueadero,
            filtro_fecha=fecha,
            limite=200
        )

        self._registros_cargados = {r["id"]: r for r in registros}
        suma_tot = 0

        for r in registros:
            suma_tot += int(r.get("total_turno", 0) or 0)
            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"],
                r["timestamp"],
                r["fecha_turno"],
                r["parqueadero"],
                r["trabajador"],
                fmt_cop(r["total_monedas"]),
                fmt_cop(r["total_billetes"]),
                fmt_cop(r["total_turno"]),
            ))

        self.lbl_conteo_registros.configure(text=f"Total: {len(registros)} conteos en historial")
        self.lbl_suma_total.configure(text=f"Suma Total: {fmt_cop(suma_tot)}")

    def _on_select_registro(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        reg_id = int(sel[0])
        r = self._registros_cargados.get(reg_id)
        if not r:
            return

        self._registro_seleccionado = r
        self.lbl_detalle_nombre.configure(text=r["trabajador"])
        self.lbl_detalle_lugar.configure(text=f"{r['parqueadero']} | Turno: {r['fecha_turno']}")

        monedas = json.loads(r["monedas_json"] or "{}")
        billetes = json.loads(r["billetes_json"] or "{}")

        txt = "── MONEDAS ──\n"
        nombres_m = [
            ("1000", "$1.000"), ("500", "$500"), ("200a", "$200(A)"),
            ("200b", "$200(B)"), ("100a", "$100(A)"), ("100b", "$100(B)"),
            ("50a", "$50(A)"), ("50b", "$50(B)")
        ]
        for k, nom in nombres_m:
            c = monedas.get(k, 0)
            if c:
                txt += f"  {nom:<9}: {c} uds\n"
        txt += f"  Subtotal: {fmt_cop(r['total_monedas'])}\n\n"

        txt += "── BILLETES ──\n"
        nombres_b = [
            ("2000", "$2.000"), ("5000", "$5.000"), ("10000", "$10.000"),
            ("20000", "$20.000"), ("50000", "$50.000"), ("100000", "$100.000")
        ]
        for k, nom in nombres_b:
            c = billetes.get(k, 0)
            if c:
                txt += f"  {nom:<9}: {c} uds\n"
        txt += f"  Subtotal: {fmt_cop(r['total_billetes'])}\n\n"
        txt += f"═══════════════════\n"
        txt += f"TOTAL: {fmt_cop(r['total_turno'])}\n"
        txt += f"Hoja: {r['hoja_tipo'].upper()}"

        self.txt_desglose.delete("1.0", "end")
        self.txt_desglose.insert("1.0", txt)

        self.btn_reenviar.configure(state="normal", text="🔁 Reenviar a Google Sheets")
        self.lbl_estado_reenvio.configure(text="")

    def _reenviar_a_sheets(self):
        """Toma el registro seleccionado y lo vuelve a guardar en Google Sheets."""
        if not self._registro_seleccionado:
            return
        r = self._registro_seleccionado
        trabajador = r["trabajador"]
        parqueadero = r["parqueadero"]
        fecha = r["fecha_turno"]
        hoja_tipo = r.get("hoja_tipo", "principal")
        monedas = json.loads(r["monedas_json"] or "{}")
        billetes = json.loads(r["billetes_json"] or "{}")

        self.btn_reenviar.configure(state="disabled", text="⏳ Reenviando...")
        self.lbl_estado_reenvio.configure(text="Conectando con Google Sheets...", text_color="#9CA3AF")

        def _tarea():
            try:
                ws = conectar_sheet(hoja_tipo)
                fila = buscar_fila_trabajador(ws, fecha, parqueadero, trabajador)
                if fila is None:
                    self.after(0, lambda: self.lbl_estado_reenvio.configure(
                        text="❌ Sin espacio disponible", text_color="#EF4444"))
                    self.after(0, lambda: self.btn_reenviar.configure(state="normal", text="🔁 Reenviar a Google Sheets"))
                    return

                fila_datos = ws.row_values(fila)
                if not fila_datos or not fila_datos[0].strip():
                    escribir_nombre_trabajador(ws, fila, trabajador)

                guardar_conteo(ws, fila, monedas, billetes)

                self.after(0, lambda: self.lbl_estado_reenvio.configure(
                    text=f"✅ ¡Restaurado en fila {fila}!", text_color="#10B981"))
                self.after(0, lambda: self.btn_reenviar.configure(state="normal", text="🔁 Reenviado con éxito"))
            except Exception as e:
                self.after(0, lambda: self.lbl_estado_reenvio.configure(
                    text=f"❌ Error: {e}", text_color="#EF4444"))
                self.after(0, lambda: self.btn_reenviar.configure(state="normal", text="Reintentar"))

        threading.Thread(target=_tarea, daemon=True).start()

    def _exportar_csv(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar Respaldo CSV",
            defaultextension=".csv",
            filetypes=[("Archivos CSV", "*.csv")],
            initialfile="respaldo_conteos.csv"
        )
        if ruta:
            try:
                total = exportar_csv(ruta)
                messagebox.showinfo("Exportación Exitosa", f"Se exportaron {total} registros correctamente en:\n{ruta}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar el archivo:\n{e}")
