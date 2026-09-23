"""
Widget Selector de Trabajador con Búsqueda Predictiva, Colores y Letras
Permite escribir letras/nombres con filtrado en vivo o elegir letras rápidas.
Compatible con la API de CTkComboBox (.get(), .set(), .configure()).
"""

import unicodedata
import tkinter as tk
import customtkinter as ctk
from config.datos import TRABAJADORES

# Paleta de colores atractivos para los avatares según la letra inicial
COLORES_LETRAS = [
    "#2563EB",  # Azul
    "#059669",  # Esmeralda
    "#D97706",  # Ámbar
    "#7C3AED",  # Violeta
    "#E11D48",  # Rosa rojizo
    "#0891B2",  # Cian
    "#4F46E5",  # Índigo
    "#0D9488",  # Verde azulado
    "#EA580C",  # Naranja
    "#DB2777",  # Magenta
    "#16A34A",  # Verde
    "#475569",  # Pizarra
]


def get_color_letra(letra):
    """Retorna un color distintivo según la letra inicial."""
    if not letra:
        return COLORES_LETRAS[0]
    return COLORES_LETRAS[ord(letra.upper()[0]) % len(COLORES_LETRAS)]


def normalizar_texto(s):
    """Remueve acentos y convierte a mayúsculas para búsquedas insensibles."""
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(s))
        if unicodedata.category(c) != "Mn"
    ).upper().strip()


class SelectorTrabajador(ctk.CTkFrame):
    """
    Componente moderno de selección de trabajador con:
    - Avatar circular/redondeado con la letra inicial y color dinámico
    - Campo de texto para escribir y filtrar al instante por letras o nombre
    - Ventana desplegable emergente con scroll y conteo de resultados
    - Barra de letras rápidas (A, B, C, D...)
    - Selección táctil / mouse y navegación con flechas de teclado y Enter
    """

    def __init__(self, master, lista_trabajadores=None, width=280, command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.lista = lista_trabajadores or TRABAJADORES
        self.callback_command = command
        self._popup = None
        self._items_filtrados = list(self.lista)

        # 1. Avatar con color y letra inicial
        self.lbl_badge = ctk.CTkLabel(
            self,
            text="A",
            width=32,
            height=32,
            corner_radius=8,
            fg_color=COLORES_LETRAS[0],
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.lbl_badge.pack(side="left", padx=(0, 6))

        # 2. Entry para escribir letras o nombre
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="Escribe letra o nombre (ej: C, DIA)...",
            width=max(width - 70, 160),
            height=32,
            font=ctk.CTkFont(size=12)
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # 3. Botón para abrir / alternar lista
        self.btn_desplegar = ctk.CTkButton(
            self,
            text="▼",
            width=30,
            height=32,
            fg_color="#374151",
            hover_color="#4B5563",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self._toggle_popup
        )
        self.btn_desplegar.pack(side="left")

        # Eventos del Entry
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<Down>", self._on_arrow_down)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Escape>", lambda e: self._cerrar_popup())

        # Establecer valor inicial por defecto
        if self.lista:
            self.set(self.lista[0])

    def get(self):
        """Retorna el trabajador seleccionado actualmente."""
        return self.entry.get().strip()

    def set(self, valor):
        """Establece el trabajador seleccionado y actualiza el avatar de color."""
        self.entry.delete(0, "end")
        self.entry.insert(0, valor)
        self._actualizar_badge(valor)
        if self.callback_command:
            try:
                self.callback_command(valor)
            except Exception:
                pass

    def _actualizar_badge(self, texto):
        t = texto.strip().upper() if texto else ""
        letra = t[0] if t else "?"
        color = get_color_letra(letra)
        self.lbl_badge.configure(text=letra, fg_color=color)

    def _filtrar(self, query):
        q = normalizar_texto(query)
        if not q:
            return list(self.lista)
        # Priorizar los que empiezan por la letra o texto escrito
        empiezan = [t for t in self.lista if normalizar_texto(t).startswith(q)]
        contienen = [
            t for t in self.lista
            if q in normalizar_texto(t) and not normalizar_texto(t).startswith(q)
        ]
        return empiezan + contienen

    def _on_focus_in(self, event):
        # Al enfocar el campo, seleccionar el texto para facilitar reemplazo
        self.entry.selection_range(0, "end")

    def _on_key_release(self, event):
        if event.keysym in ("Down", "Up", "Return", "Escape", "Tab"):
            return
        query = self.entry.get()
        self._actualizar_badge(query)
        self._items_filtrados = self._filtrar(query)
        self._abrir_popup()

    def _on_arrow_down(self, event):
        if self._popup and hasattr(self, "_listbox") and self._listbox:
            self._listbox.focus_set()
            if self._listbox.size() > 0:
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            return "break"
        else:
            self._items_filtrados = self._filtrar(self.entry.get())
            self._abrir_popup()
            return "break"

    def _on_enter(self, event):
        if self._popup and hasattr(self, "_listbox") and self._listbox:
            sel = self._listbox.curselection()
            if sel:
                idx = sel[0]
                if idx < len(self._items_filtrados):
                    self.set(self._items_filtrados[idx])
            elif self._items_filtrados:
                self.set(self._items_filtrados[0])
            self._cerrar_popup()
            return "break"
        elif self._items_filtrados:
            # Seleccionar la primera coincidencia directa
            self.set(self._items_filtrados[0])
            self._cerrar_popup()
            return "break"

    def _toggle_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._cerrar_popup()
        else:
            self._items_filtrados = self._filtrar(self.entry.get())
            self._abrir_popup()

    def _abrir_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._actualizar_lista()
            return

        self.update_idletasks()
        try:
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height() + 3
            w = max(self.winfo_width(), 320)
        except Exception:
            x = 200
            y = 200
            w = 320
        h = 250

        self._popup = tk.Toplevel(self)
        self._popup.wm_overrideredirect(True)
        self._popup.wm_geometry(f"{w}x{h}+{x}+{y}")
        self._popup.attributes("-topmost", True)
        self._popup.configure(bg="#1E293B")

        # Frame contenedor
        frame_box = tk.Frame(self._popup, bg="#0F172A", bd=1, relief="solid")
        frame_box.pack(fill="both", expand=True)

        # Barra de letras rápida en el popup
        f_letras = tk.Frame(frame_box, bg="#1E293B")
        f_letras.pack(fill="x", padx=4, pady=3)

        btn_todos = tk.Button(
            f_letras, text="TODOS", font=("Arial", 7, "bold"),
            bg="#2563EB", fg="white", bd=0, padx=4, pady=2,
            cursor="hand2", command=lambda: self._click_letra("")
        )
        btn_todos.pack(side="left", padx=1)

        letras = sorted(list(set(t[0].upper() for t in self.lista if t)))
        for l in letras[:14]:
            b = tk.Button(
                f_letras, text=l, font=("Arial", 7, "bold"),
                bg="#334155", fg="#E2E8F0", bd=0, padx=3, pady=2,
                cursor="hand2", command=lambda let=l: self._click_letra(let)
            )
            b.pack(side="left", padx=1)

        # Label contador
        self._lbl_count = tk.Label(
            frame_box, text="", font=("Arial", 8),
            bg="#0F172A", fg="#94A3B8", anchor="w"
        )
        self._lbl_count.pack(fill="x", padx=8, pady=(0, 2))

        # Listbox con scrollbar
        f_list = tk.Frame(frame_box, bg="#0F172A")
        f_list.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        scrollbar = tk.Scrollbar(f_list)
        scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            f_list,
            bg="#0F172A",
            fg="#F8FAFC",
            selectbackground="#2563EB",
            selectforeground="#FFFFFF",
            font=("Arial", 10),
            bd=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox.yview)

        self._listbox.bind("<ButtonRelease-1>", self._on_item_click)
        self._listbox.bind("<Return>", self._on_enter)
        self._listbox.bind("<Escape>", lambda e: self._cerrar_popup())

        # Cerrar al hacer clic fuera del popup
        self._popup.bind("<FocusOut>", self._on_focus_out)

        self._actualizar_lista()

    def _click_letra(self, letra):
        self.entry.delete(0, "end")
        if letra:
            self.entry.insert(0, letra)
        self._actualizar_badge(letra)
        self._items_filtrados = self._filtrar(letra)
        self._actualizar_lista()
        self.entry.focus_set()

    def _actualizar_lista(self):
        if not hasattr(self, "_listbox") or not self._listbox:
            return
        self._listbox.delete(0, "end")
        for item in self._items_filtrados:
            initial = item[0] if item else "?"
            self._listbox.insert("end", f"  [{initial}]  {item}")

        count = len(self._items_filtrados)
        if hasattr(self, "_lbl_count") and self._lbl_count:
            self._lbl_count.config(text=f"  {count} trabajadores encontrados:")

    def _on_item_click(self, event):
        sel = self._listbox.curselection()
        if sel:
            idx = sel[0]
            if idx < len(self._items_filtrados):
                self.set(self._items_filtrados[idx])
        self._cerrar_popup()

    def _on_focus_out(self, event):
        try:
            focused = self.winfo_toplevel().focus_get()
            if focused == self.entry or (self._popup and focused in self._popup.winfo_children()):
                return
        except Exception:
            pass
        self._cerrar_popup()

    def _cerrar_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
