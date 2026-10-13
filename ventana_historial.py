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
        self.title("📜 Historial de Conteos y Respaldo Permanente (Máquina 1 y Máquina 2)")
        self.geometry("1060x650")
        self.minsize(920, 520)
        self.attributes("-topmost", True)

        self._crear_ui()
        self._cargar_datos()

    def _crear_ui(self):
        # ── Barra Superior: Filtros y Máquinas ──
        frame_filtros = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=8)
        frame_filtros.pack(fill="x", padx=12, pady=(10, 6))

        # Fila 1: Selector de Máquinas + Sincronizar Drive + Exportar
        f_row1 = ctk.CTkFrame(frame_filtros, fg_color="transparent")
        f_row1.pack(fill="x", padx=10, pady=(8, 4))

        self.seg_maquina = ctk.CTkSegmentedButton(
            f_row1,
            values=["🌐 Todas las Máquinas", "🪙 Máquina 1 (CC358)", "✍️ Máquina 2 (Drive)"],
            command=lambda v: self._cargar_datos(),
            font=ctk.CTkFont(size=11, weight="bold"),
            selected_color="#0284C7",
            selected_hover_color="#0369A1",
            height=30
        )
        self.seg_maquina.set("🌐 Todas las Máquinas")
        self.seg_maquina.pack(side="left")

        self.btn_sync_m2 = ctk.CTkButton(
            f_row1, text="🔄 Sincronizar Máquina 2 (Drive)", width=195, height=30,
            fg_color="#0D9488", hover_color="#0F766E",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._sincronizar_m2
        )
        self.btn_sync_m2.pack(side="left", padx=12)

        ctk.CTkButton(
            f_row1, text="📥 Exportar CSV", width=110, height=30,
            fg_color="#059669", hover_color="#047857",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._exportar_csv
        ).pack(side="right")

        # Fila 2: Búsqueda Trabajador, Parqueadero, Fecha, Actualizar
        f_row2 = ctk.CTkFrame(frame_filtros, fg_color="transparent")
        f_row2.pack(fill="x", padx=10, pady=(4, 8))

        ctk.CTkLabel(f_row2, text="🔍 Buscar:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 4))
        self.entry_busqueda = ctk.CTkEntry(f_row2, placeholder_text="Escribe el nombre...", width=190, height=28)
        self.entry_busqueda.pack(side="left", padx=(0, 10))
        self.entry_busqueda.bind("<KeyRelease>", lambda e: self._cargar_datos())

        ctk.CTkLabel(f_row2, text="Parqueadero:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 4))
        self.combo_parqueadero = ctk.CTkComboBox(
            f_row2, values=["TODOS"] + PARQUEADEROS, width=130, height=28,
            command=lambda v: self._cargar_datos()
        )
        self.combo_parqueadero.set("TODOS")
        self.combo_parqueadero.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(f_row2, text="Fecha:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 4))
        self.entry_fecha = ctk.CTkEntry(f_row2, placeholder_text="ej: 30/2 o 2026-10", width=120, height=28)
        self.entry_fecha.pack(side="left", padx=(0, 10))
        self.entry_fecha.bind("<KeyRelease>", lambda e: self._cargar_datos())

        ctk.CTkButton(
            f_row2, text="🔄 Actualizar", width=85, height=28,
            fg_color="#374151", hover_color="#4B5563",
            command=self._cargar_datos
        ).pack(side="left")

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

        cols = ("id", "hora", "fecha_turno", "parqueadero", "trabajador", "tot_mon", "tot_bil", "tot_turno", "maquina")
        self.tree = ttk.Treeview(frame_central, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("id", text="#")
        self.tree.heading("hora", text="Hora Guardado")
        self.tree.heading("fecha_turno", text="Fecha Turno")
        self.tree.heading("parqueadero", text="Parqueadero")
        self.tree.heading("trabajador", text="Trabajador")
        self.tree.heading("tot_mon", text="Monedas")
        self.tree.heading("tot_bil", text="Billetes")
        self.tree.heading("tot_turno", text="TOTAL TURNO")
        self.tree.heading("maquina", text="Máquina / Origen")

        self.tree.column("id", width=38, anchor="center")
        self.tree.column("hora", width=120, anchor="center")
        self.tree.column("fecha_turno", width=85, anchor="center")
        self.tree.column("parqueadero", width=105, anchor="w")
        self.tree.column("trabajador", width=175, anchor="w")
        self.tree.column("tot_mon", width=90, anchor="e")
        self.tree.column("tot_bil", width=90, anchor="e")
        self.tree.column("tot_turno", width=105, anchor="e")
        self.tree.column("maquina", width=140, anchor="center")

        self.tree.tag_configure("maq1", foreground="#F9FAFB")
        self.tree.tag_configure("maq2", foreground="#FBBF24")  # Dorado/ámbar para Máquina 2

        scrollbar = ttk.Scrollbar(frame_central, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_registro)

        # ── Panel Lateral Derecho: Detalle y Reenvío ──
        self.frame_detalle = ctk.CTkFrame(frame_central, width=285, fg_color="#1F2937", corner_radius=8)
        self.frame_detalle.pack(side="right", fill="y", padx=(8, 0))
        self.frame_detalle.pack_propagate(False)

        ctk.CTkLabel(self.frame_detalle, text="Detalle del Registro", font=ctk.CTkFont(size=13, weight="bold"), text_color="#34D399").pack(pady=(10, 4))
        
        self.lbl_detalle_nombre = ctk.CTkLabel(self.frame_detalle, text="Selecciona un registro", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_detalle_nombre.pack(padx=8, pady=2)

        self.lbl_detalle_lugar = ctk.CTkLabel(self.frame_detalle, text="", font=ctk.CTkFont(size=11), text_color="#9CA3AF")
        self.lbl_detalle_lugar.pack(padx=8, pady=2)

        self.lbl_detalle_maquina = ctk.CTkLabel(self.frame_detalle, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38BDF8")
        self.lbl_detalle_maquina.pack(padx=8, pady=2)

        # Caja de texto con desglose
        self.txt_desglose = ctk.CTkTextbox(self.frame_detalle, height=240, font=ctk.CTkFont(size=11), fg_color="#111827")
        self.txt_desglose.pack(fill="x", padx=10, pady=6)

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
        maq_sel = self.seg_maquina.get()

        if "Máquina 1" in maq_sel:
            filtro_maq = "MAQUINA 1"
        elif "Máquina 2" in maq_sel:
            filtro_maq = "MAQUINA 2"
        else:
            filtro_maq = "TODAS"

        registros = consultar_historial(
            filtro_trabajador=trabajador,
            filtro_parqueadero=parqueadero,
            filtro_fecha=fecha,
            filtro_maquina=filtro_maq,
            limite=500
        )

        self._registros_cargados = {r["id"]: r for r in registros}
        suma_tot = 0
        suma_m1 = 0
        suma_m2 = 0
        count_m1 = 0
        count_m2 = 0

        for r in registros:
            tt = int(r.get("total_turno", 0) or 0)
            suma_tot += tt
            maq = str(r.get("maquina") or "MAQUINA 1").strip().upper()

            if maq == "MAQUINA 2":
                suma_m2 += tt
                count_m2 += 1
                maq_lbl = "✍️ Máquina 2 (Drive)"
                tag_row = "maq2"
            else:
                suma_m1 += tt
                count_m1 += 1
                maq_lbl = "🪙 Máquina 1 (CC358)"
                tag_row = "maq1"

            self.tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"],
                r["timestamp"],
                r["fecha_turno"],
                r["parqueadero"],
                r["trabajador"],
                fmt_cop(r["total_monedas"]),
                fmt_cop(r["total_billetes"]),
                fmt_cop(r["total_turno"]),
                maq_lbl
            ), tags=(tag_row,))

        if filtro_maq == "TODAS":
            self.lbl_conteo_registros.configure(text=f"Total: {len(registros)} conteos (🪙 M1: {count_m1} | ✍️ M2: {count_m2})")
            self.lbl_suma_total.configure(text=f"Total: {fmt_cop(suma_tot)} (M1: {fmt_cop(suma_m1)} | M2: {fmt_cop(suma_m2)})")
        else:
            self.lbl_conteo_registros.configure(text=f"Total: {len(registros)} conteos ({maq_sel})")
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

        maq_tipo = str(r.get("maquina") or "MAQUINA 1").strip().upper()
        if maq_tipo == "MAQUINA 2":
            self.lbl_detalle_maquina.configure(text="✍️ Registrado en Máquina 2 (Drive)", text_color="#FBBF24")
        else:
            self.lbl_detalle_maquina.configure(text="🪙 Contado en Máquina 1 (CC358)", text_color="#38BDF8")

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
                ws = conectar_sheet(hoja_tipo, fecha_str=fecha)
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

    def _sincronizar_m2(self):
        """Descarga e importa los conteos manuales ingresados en Google Drive como Máquina 2."""
        self.btn_sync_m2.configure(state="disabled", text="⏳ Sincronizando...")

        def _tarea():
            try:
                from historial_db import sincronizar_desde_sheets
                res = sincronizar_desde_sheets(hoja_tipo="principal")
                msg = (
                    f"Sincronización completada ({res.get('pestana', 'Mes actual')}):\n\n"
                    f"• {res.get('nuevos', 0)} nuevos turnos agregados a Máquina 2\n"
                    f"• {res.get('existentes', 0)} turnos ya existían en el historial\n"
                    f"• {res.get('total_leidos', 0)} conteos totales leídos en Google Drive"
                )
                self.after(0, lambda: messagebox.showinfo("Sincronización Máquina 2", msg))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error de Sincronización", f"No se pudo sincronizar desde Google Drive:\n{e}"))
            finally:
                self.after(0, lambda: self.btn_sync_m2.configure(state="normal", text="🔄 Sincronizar Máquina 2 (Drive)"))
                self.after(0, self._cargar_datos)

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
                maq_sel = self.seg_maquina.get()
                if "Máquina 1" in maq_sel:
                    filtro_maq = "MAQUINA 1"
                elif "Máquina 2" in maq_sel:
                    filtro_maq = "MAQUINA 2"
                else:
                    filtro_maq = "TODAS"

                total = exportar_csv(
                    ruta,
                    filtro_trabajador=self.entry_busqueda.get().strip(),
                    filtro_fecha=self.entry_fecha.get().strip(),
                    filtro_parqueadero=self.combo_parqueadero.get(),
                    filtro_maquina=filtro_maq
                )
                messagebox.showinfo("Exportación Exitosa", f"Se exportaron {total} registros correctamente en:\n{ruta}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar el archivo:\n{e}")
