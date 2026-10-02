"""
actualizador.py — Auto-actualizador desde GitHub Releases
==========================================================
Al arrancar la app, este módulo consulta la API de GitHub para ver si
hay una versión más nueva que la instalada. Si la hay, descarga el nuevo
.exe en segundo plano, reemplaza el actual y lo relanza.

Uso en app_gui.py:
    from actualizador import verificar_actualizacion
    # Llamar después de que la ventana esté lista:
    self.after(2000, lambda: verificar_actualizacion(self))
"""

import os
import sys
import json
import threading
import subprocess
import urllib.request
import urllib.error
from packaging.version import Version


# ── Configuración ────────────────────────────────────────────────────────────
GITHUB_OWNER  = "fundamiga"
GITHUB_REPO   = "monedasconteo"
VERSION_ACTUAL = "1.1.1"          # <-- Actualiza esto en cada release que hagas
NOMBRE_EXE    = "ConteoCC358.exe" # <-- Nombre exacto del .exe en el release
# ─────────────────────────────────────────────────────────────────────────────

API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def _es_exe_empaquetado():
    """Detecta si estamos corriendo como .exe (PyInstaller) o como script Python."""
    return getattr(sys, "frozen", False)


def _obtener_ultima_version():
    """
    Consulta la API de GitHub y devuelve (tag, url_descarga) del último release.
    Retorna (None, None) si falla o no hay asset .exe.
    """
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "ConteoCC358-Updater/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        tag = data.get("tag_name", "").lstrip("v")
        assets = data.get("assets", [])

        url_exe = None
        for asset in assets:
            if asset.get("name", "").lower() == NOMBRE_EXE.lower():
                url_exe = asset.get("browser_download_url")
                break

        return tag, url_exe

    except Exception:
        return None, None


def _descargar_y_reemplazar(url_descarga, ventana, lbl_estado):
    """Descarga el nuevo .exe, reemplaza el actual y relanza."""
    try:
        exe_actual = sys.executable if _es_exe_empaquetado() else None
        if not exe_actual:
            return  # Solo actualiza si corre como .exe

        carpeta    = os.path.dirname(exe_actual)
        exe_nuevo  = os.path.join(carpeta, NOMBRE_EXE + ".nuevo")
        exe_backup = os.path.join(carpeta, NOMBRE_EXE + ".bak")

        # ── Descargar ──
        def _progreso(n_bloques, tam_bloque, tam_total):
            if tam_total > 0 and lbl_estado:
                pct = min(int(n_bloques * tam_bloque * 100 / tam_total), 99)
                try:
                    ventana.after(0, lambda: lbl_estado.configure(
                        text=f"⬇️ Descargando actualización... {pct}%"))
                except Exception:
                    pass

        urllib.request.urlretrieve(url_descarga, exe_nuevo, _progreso)

        # ── Reemplazar con script .bat que espera a que este proceso cierre ──
        bat = os.path.join(carpeta, "_actualizar.bat")
        with open(bat, "w") as f:
            f.write(f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{exe_nuevo}" "{exe_actual}"
del "{exe_backup}" 2>nul
start "" "{exe_actual}"
del "%~f0"
""")

        try:
            ventana.after(0, lambda: lbl_estado.configure(
                text="✅ Actualización lista — reiniciando..."))
        except Exception:
            pass

        ventana.after(1200, lambda: _relanzar(bat))

    except Exception as e:
        try:
            ventana.after(0, lambda: lbl_estado.configure(
                text=f"⚠️ Error al actualizar: {e}"))
        except Exception:
            pass


def _relanzar(bat_path):
    """Lanza el .bat de reemplazo y cierra la app actual."""
    try:
        subprocess.Popen(["cmd", "/c", bat_path],
                         creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass
    os._exit(0)


def verificar_actualizacion(ventana, lbl_estado=None):
    """
    Punto de entrada principal. Llamar desde la app después de que la UI esté lista.

    Parámetros:
        ventana    — La ventana principal CTk (para usar .after y mostrar diálogos).
        lbl_estado — (Opcional) CTkLabel donde mostrar el progreso. Si es None
                     se busca self.lbl_estado en la ventana.
    """
    if lbl_estado is None:
        lbl_estado = getattr(ventana, "lbl_estado", None)

    def _tarea():
        tag_nueva, url = _obtener_ultima_version()

        if not tag_nueva or not url:
            return  # Sin internet o sin releases → silencioso

        try:
            hay_nueva = Version(tag_nueva) > Version(VERSION_ACTUAL)
        except Exception:
            hay_nueva = tag_nueva != VERSION_ACTUAL

        if not hay_nueva:
            return  # Ya tiene la última versión → silencioso

        # Hay versión nueva — avisar en la UI y preguntar
        def _mostrar_aviso():
            try:
                import customtkinter as ctk

                dialogo = ctk.CTkToplevel(ventana)
                dialogo.title("🔄 Actualización disponible")
                dialogo.geometry("380x160")
                dialogo.resizable(False, False)
                dialogo.attributes("-topmost", True)
                dialogo.grab_set()

                ctk.CTkLabel(
                    dialogo,
                    text=f"Nueva versión disponible: v{tag_nueva}",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color="#34D399"
                ).pack(pady=(18, 4))

                ctk.CTkLabel(
                    dialogo,
                    text=f"Versión actual: v{VERSION_ACTUAL}\nSe descargará e instalará automáticamente.",
                    font=ctk.CTkFont(size=12),
                    text_color="#9CA3AF"
                ).pack(pady=(0, 12))

                frame_btns = ctk.CTkFrame(dialogo, fg_color="transparent")
                frame_btns.pack()

                def _actualizar():
                    dialogo.destroy()
                    if lbl_estado:
                        lbl_estado.configure(text="⬇️ Iniciando descarga...")
                    threading.Thread(
                        target=_descargar_y_reemplazar,
                        args=(url, ventana, lbl_estado),
                        daemon=True
                    ).start()

                ctk.CTkButton(
                    frame_btns, text="⬇️ Actualizar ahora",
                    fg_color="#107C41", hover_color="#0B5C30",
                    width=160, height=34,
                    command=_actualizar
                ).pack(side="left", padx=8)

                ctk.CTkButton(
                    frame_btns, text="Ahora no",
                    fg_color="#374151", hover_color="#4B5563",
                    width=100, height=34,
                    command=dialogo.destroy
                ).pack(side="left", padx=8)

            except Exception:
                pass

        ventana.after(0, _mostrar_aviso)

    threading.Thread(target=_tarea, daemon=True).start()
