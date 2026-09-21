"""
Modo Cámara con Visión Artificial (OCR)
Permite apuntar la cámara web a la pantalla de la contadora CC358,
leer los números automáticamente y enviarlos al sistema de recaudo.
"""

import re
import asyncio
import threading
import cv2
import numpy as np
from PIL import Image, ImageTk
import customtkinter as ctk

import winsdk.windows.media.ocr as ocr
import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.storage.streams as streams


async def _ocr_en_memoria(frame):
    """Ejecuta el motor OCR nativo de Windows 11 sobre una imagen en memoria."""
    try:
        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            return ""

        ok, buf = cv2.imencode(".png", frame)
        if not ok:
            return ""

        writer = streams.DataWriter()
        writer.write_bytes(buf.tobytes())
        stream = streams.InMemoryRandomAccessStream()
        await stream.write_async(writer.detach_buffer())
        stream.seek(0)

        decoder = await imaging.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        res = await engine.recognize_async(bitmap)
        return res.text
    except Exception as e:
        return f"Error OCR: {e}"


def extraer_monedas_de_texto(texto):
    """
    Intenta extraer denominaciones y cantidades del texto reconocido por OCR.
    Retorna un diccionario compatible con el sistema:
    {'1000': X, '500': X, '200a': X, '100a': X, '50a': X, ...}
    """
    monedas = {
        "1000": 0, "500": 0, "200a": 0, "200b": 0,
        "100a": 0, "100b": 0, "50a": 0, "50b": 0
    }

    if not texto:
        return monedas

    texto_limpio = texto.replace("$", " ").replace(".", "").replace(",", "")

    # Patrones comunes en pantallas de contadoras:
    # "1000 : 5", "1000-5", "1000 5", "500 : 12", etc.
    for linea in texto_limpio.split("\n"):
        linea = linea.strip()
        # Buscar pares (denominacion, cantidad)
        matches = re.findall(r"(1000|500|200|100|50)\s*[:\-\s]\s*(\d+)", linea, re.IGNORECASE)
        for denom, cant in matches:
            d = denom.lower()
            if d == "1000":
                monedas["1000"] = int(cant)
            elif d == "500":
                monedas["500"] = int(cant)
            elif d == "200":
                if monedas["200a"] == 0:
                    monedas["200a"] = int(cant)
                else:
                    monedas["200b"] = int(cant)
            elif d == "100":
                if monedas["100a"] == 0:
                    monedas["100a"] = int(cant)
                else:
                    monedas["100b"] = int(cant)
            elif d == "50":
                if monedas["50a"] == 0:
                    monedas["50a"] = int(cant)
                else:
                    monedas["50b"] = int(cant)

    return monedas


class VentanaCamaraOCR(ctk.CTkToplevel):
    """
    Ventana que abre la cámara web, muestra vista en vivo,
    y permite capturar y leer la pantalla con visión artificial.
    """

    def __init__(self, parent, callback_datos, callback_log=None):
        super().__init__(parent)
        self.callback_datos = callback_datos
        self.callback_log = callback_log or (lambda msg: None)

        self.title("📷 Modo Cámara — Reconocimiento Óptico (OCR)")
        self.geometry("820x650")
        self.minsize(700, 550)
        self.attributes("-topmost", True)

        self.cap = None
        self.corriendo = False
        self.ultimo_frame = None

        self._crear_ui()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self._iniciar_camara()

    def _crear_ui(self):
        self.grid_columnconfigure(0, weight=6)
        self.grid_columnconfigure(1, weight=4)
        self.grid_rowconfigure(1, weight=1)

        # ── Barra superior ──
        top = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=8)
        top.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 6), sticky="ew")

        ctk.CTkLabel(
            top,
            text="📷 Apunta la cámara a la pantalla de la máquina CC358",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#60A5FA"
        ).pack(side="left", padx=15, pady=8)

        self.lbl_cam_status = ctk.CTkLabel(
            top,
            text="Iniciando cámara...",
            font=ctk.CTkFont(size=12),
            text_color="#FBBF24"
        )
        self.lbl_cam_status.pack(side="right", padx=15)

        # ── Panel Izquierdo: Vista previa de video ──
        f_video = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        f_video.grid(row=1, column=0, padx=(12, 6), pady=(0, 10), sticky="nsew")
        f_video.pack_propagate(False)

        self.lbl_video = ctk.CTkLabel(f_video, text="Cargando video...")
        self.lbl_video.pack(fill="both", expand=True, padx=6, pady=6)

        # Botón grande de captura
        self.btn_capturar = ctk.CTkButton(
            f_video,
            text="📸  ESCANEAR PANTALLA AHORA",
            fg_color="#107C41", hover_color="#059669",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=44,
            command=self._capturar_y_leer
        )
        self.btn_capturar.pack(fill="x", padx=15, pady=(0, 10))

        # ── Panel Derecho: Resultados detectados ──
        right = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        right.grid(row=1, column=1, padx=(6, 12), pady=(0, 10), sticky="nsew")

        ctk.CTkLabel(
            right, text="🔢 Valores Detectados",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FBBF24"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            right,
            text="Verifica o ajusta los números si es necesario:",
            font=ctk.CTkFont(size=11), text_color="#9CA3AF"
        ).pack(anchor="w", padx=12, pady=(0, 8))

        # Campos de monedas editables
        f_campos = ctk.CTkFrame(right, fg_color="#111827", corner_radius=8)
        f_campos.pack(fill="x", padx=12, pady=4)

        self.campos_monedas = {}
        for denom, clave in [
            ("$1.000", "1000"), ("$500", "500"),
            ("$200 (A)", "200a"), ("$200 (B)", "200b"),
            ("$100 (A)", "100a"), ("$100 (B)", "100b"),
            ("$50 (A)", "50a"), ("$50 (B)", "50b")
        ]:
            row = ctk.CTkFrame(f_campos, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=denom, width=70, font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
            e = ctk.CTkEntry(row, width=60, height=26, placeholder_text="0")
            e.pack(side="left", padx=6)
            ctk.CTkLabel(row, text="uds", text_color="#6B7280", font=ctk.CTkFont(size=11)).pack(side="left")
            self.campos_monedas[clave] = e

        # Cuadro con el texto en crudo que leyó el OCR
        ctk.CTkLabel(right, text="Texto crudo leído por OCR:", font=ctk.CTkFont(size=11), text_color="#9CA3AF").pack(anchor="w", padx=12, pady=(8, 2))
        self.txt_ocr_raw = ctk.CTkTextbox(right, height=75, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_ocr_raw.pack(fill="x", padx=12, pady=(0, 8))

        # Botón confirmar
        self.btn_confirmar = ctk.CTkButton(
            right,
            text="✅  USAR ESTE CONTEO",
            fg_color="#2563EB", hover_color="#1D4ED8",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            command=self._confirmar_y_enviar
        )
        self.btn_confirmar.pack(fill="x", padx=12, pady=8)

        self.lbl_estado = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=11))
        self.lbl_estado.pack(pady=2)

    # ─────────────────────────────────────────
    # BUCLE DE VIDEO
    # ─────────────────────────────────────────

    def _iniciar_camara(self):
        self.corriendo = True
        threading.Thread(target=self._bucle_camara, daemon=True).start()

    def _bucle_camara(self):
        # Usar DirectShow en Windows 11 para compatibilidad óptima
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.after(0, lambda: self.lbl_cam_status.configure(
                text="❌ No se pudo conectar a la cámara", text_color="#EF4444"
            ))
            return

        self.after(0, lambda: self.lbl_cam_status.configure(
            text="🟢 Cámara activa", text_color="#10B981"
        ))

        while self.corriendo and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue

            self.ultimo_frame = frame.copy()

            # Dibujar caja de guía en el centro de la imagen
            h, w, _ = frame.shape
            x1, y1 = int(w * 0.15), int(h * 0.2)
            x2, y2 = int(w * 0.85), int(h * 0.8)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame, "Centra la pantalla aqui", (x1 + 10, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
            )

            # Redimensionar para la UI
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(frame_rgb)
            img_tk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(480, 360))

            try:
                self.lbl_video.configure(image=img_tk, text="")
                self.lbl_video.image = img_tk
            except:
                break

            cv2.waitKey(30)

        if self.cap:
            self.cap.release()

    def _capturar_y_leer(self):
        """Toma el frame actual y lo procesa con OCR de Windows."""
        if self.ultimo_frame is None:
            return

        self.btn_capturar.configure(state="disabled", text="⏳ Leyendo pantalla...")
        self.lbl_estado.configure(text="Procesando visión artificial...", text_color="#FBBF24")

        # Tomar la región central de la guía
        h, w, _ = self.ultimo_frame.shape
        x1, y1 = int(w * 0.12), int(h * 0.15)
        x2, y2 = int(w * 0.88), int(h * 0.85)
        recorte = self.ultimo_frame[y1:y2, x1:x2]

        threading.Thread(target=self._hilo_ocr, args=(recorte,), daemon=True).start()

    def _hilo_ocr(self, img):
        try:
            texto = asyncio.run(_ocr_en_memoria(img))
            monedas = extraer_monedas_de_texto(texto)
            self.after(0, self._mostrar_resultados, texto, monedas)
        except Exception as e:
            self.after(0, lambda: self.lbl_estado.configure(text=f"Error: {e}", text_color="#EF4444"))
            self.after(0, lambda: self.btn_capturar.configure(state="normal", text="📸  ESCANEAR PANTALLA AHORA"))

    def _mostrar_resultados(self, texto, monedas):
        self.btn_capturar.configure(state="normal", text="📸  ESCANEAR DE NUEVO")

        # Mostrar texto en crudo
        self.txt_ocr_raw.delete("1.0", "end")
        self.txt_ocr_raw.insert("1.0", texto if texto.strip() else "(No se detectó texto claro)")

        # Llenar campos de monedas
        for clave, entry in self.campos_monedas.items():
            entry.delete(0, "end")
            val = monedas.get(clave, 0)
            if val:
                entry.insert(0, str(val))

        self.lbl_estado.configure(text="✅ Escaneo completado. Revisa los valores.", text_color="#10B981")
        self.callback_log(f"OCR detectó: {texto.replace(chr(10), ' ')}")

    def _confirmar_y_enviar(self):
        """Lee los campos editados por la usuaria y los manda a la app principal."""
        monedas = {}
        for clave, entry in self.campos_monedas.items():
            val = entry.get().strip()
            monedas[clave] = int(val) if val.isdigit() else 0

        self.callback_datos(monedas)
        self.callback_log("Monedas de la cámara enviadas al sistema.")
        self.lbl_estado.configure(text="✅ ¡Enviado al sistema!", text_color="#10B981")
        self.after(800, self._al_cerrar)

    def _al_cerrar(self):
        self.corriendo = False
        if self.cap:
            self.cap.release()
        self.destroy()
