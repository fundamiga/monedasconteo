"""
Lector serial para SAT CC358
Incluye modo SIMULACIÓN para pruebas sin cable físico
"""

import threading
import time
import random
from datetime import datetime


class CC358Reader:
    """
    Lector de datos de la contadora CC358.
    Puede operar en modo REAL (puerto COM) o SIMULACIÓN.
    """

    def __init__(self, callback_datos, callback_log):
        """
        callback_datos: función que recibe un dict con las monedas
        callback_log: función que recibe mensajes de texto para la consola
        """
        self.callback_datos = callback_datos
        self.callback_log = callback_log
        self.ser = None
        self.hilo = None
        self.activo = False
        self.modo_simulacion = False

    def conectar(self, puerto, baudrate=9600, simulacion=False):
        """Conecta al puerto serial o activa el modo simulación."""
        self.modo_simulacion = simulacion

        if simulacion:
            self.activo = True
            self.callback_log("🟡 MODO SIMULACIÓN activado. No se usa puerto físico.")
            self.hilo = threading.Thread(target=self._loop_simulacion, daemon=True)
            self.hilo.start()
            return True

        try:
            import serial
            self.ser = serial.Serial(
                port=puerto,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5
            )
            self.activo = True
            self.callback_log(f"🟢 Conectado a {puerto} @ {baudrate} baudios.")
            self.hilo = threading.Thread(target=self._loop_serial, daemon=True)
            self.hilo.start()
            return True
        except Exception as e:
            self.callback_log(f"❌ Error al conectar: {e}")
            return False

    def desconectar(self):
        """Desconecta el puerto serial."""
        self.activo = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.callback_log("🔒 Desconectado.")

    def _loop_serial(self):
        """Loop de lectura del puerto serial real."""
        buffer = bytearray()
        ultimo = time.time()

        while self.activo and self.ser and self.ser.is_open:
            try:
                en_espera = self.ser.in_waiting
                if en_espera > 0:
                    datos = self.ser.read(en_espera)
                    buffer.extend(datos)
                    ultimo = time.time()
                else:
                    if len(buffer) > 0 and (time.time() - ultimo > 0.3):
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        hex_str = " ".join(f"{b:02X}" for b in buffer)
                        texto = buffer.decode("latin1", errors="replace")

                        self.callback_log(
                            f"\n📥 [{timestamp}] {len(buffer)} bytes:\n"
                            f"   HEX  : {hex_str}\n"
                            f"   TEXTO: {texto}\n"
                        )

                        # Intentar parsear los datos
                        monedas = self._parsear(buffer)
                        if monedas:
                            self.callback_datos(monedas)

                        buffer.clear()
                    time.sleep(0.05)
            except Exception as e:
                self.callback_log(f"⚠️ Error en lectura: {e}")
                break

    def _loop_simulacion(self):
        """
        Modo simulación: espera 5 segundos y genera datos de prueba.
        Simula lo que haría la CC358 al terminar un conteo.
        """
        self.callback_log("⏳ Simulación: esperando 5 segundos para generar un conteo...")
        time.sleep(5)

        while self.activo:
            # Genera cantidades aleatorias de monedas (simulando un conteo real)
            monedas_sim = {
                '1000': random.randint(0, 10),
                '500':  random.randint(0, 20),
                '200a': random.randint(0, 30),
                '200b': random.randint(0, 20),
                '100a': random.randint(0, 40),
                '100b': random.randint(0, 30),
                '50a':  random.randint(0, 50),
                '50b':  random.randint(0, 40),
            }

            self.callback_log(
                f"\n🟡 [SIMULACIÓN] Conteo generado:\n"
                f"   $1.000  → {monedas_sim['1000']}\n"
                f"   $500    → {monedas_sim['500']}\n"
                f"   $200(A) → {monedas_sim['200a']}\n"
                f"   $200(B) → {monedas_sim['200b']}\n"
                f"   $100(A) → {monedas_sim['100a']}\n"
                f"   $100(B) → {monedas_sim['100b']}\n"
                f"   $50(A)  → {monedas_sim['50a']}\n"
                f"   $50(B)  → {monedas_sim['50b']}\n"
            )
            self.callback_datos(monedas_sim)

            # Esperar 30 segundos antes del próximo conteo simulado
            time.sleep(30)

    def _parsear(self, buffer):
        """
        Parser de datos de la CC358.
        ⚠️ Este parser es provisional - se completará cuando tengamos
           la primera trama real de la máquina con el cable FTDI.

        Por ahora intenta leer un formato simple de texto CSV:
        Ej: "1000:5,500:10,200:20,100:15,50:8"
        """
        try:
            texto = buffer.decode("latin1", errors="replace").strip()
            monedas = {}

            # Intentar formato CSV simple
            if ':' in texto:
                partes = texto.split(',')
                for parte in partes:
                    if ':' in parte:
                        denom, cantidad = parte.split(':')
                        monedas[denom.strip()] = int(cantidad.strip())
                if monedas:
                    return monedas

            # Si no reconocemos el formato, logueamos para analizarlo
            self.callback_log(
                f"⚠️ Formato desconocido de CC358. "
                f"Captura guardada en 'captura_cc358.log' para análisis."
            )
            with open("captura_cc358.log", "a") as f:
                f.write(f"\n{datetime.now()}: {buffer.hex()}\n")

            return None
        except Exception:
            return None
