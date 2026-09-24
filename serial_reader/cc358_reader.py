"""
Lector serial para SAT CC358
Formato oficial descubierto con cable FTDI USB-RS232
"""

import threading
import time
import random
import re
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
                timeout=0.2
            )
            # Señales DTR/RTS requeridas para comunicación fluida
            self.ser.dtr = True
            self.ser.rts = True
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            self.activo = True
            self.callback_log(f"🟢 Conectado a {puerto} @ {baudrate} baudios (SAT CC358 lista).")
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
            try:
                self.ser.close()
            except Exception:
                pass
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
                    print(f"[SERIAL BYTES] +{len(datos)} bytes recibidos (total buffer: {len(buffer)})")
                else:
                    # Si pasaron más de 300ms sin nuevos bytes y hay datos acumulados
                    if len(buffer) > 0 and (time.time() - ultimo > 0.3):
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        texto = buffer.decode("latin1", errors="replace")

                        print(f"[SERIAL TRAMA COMPLETA] {len(buffer)} bytes:\n{texto}")
                        self.callback_log(
                            f"\n📥 [{timestamp}] Trama recibida de SAT CC358 ({len(buffer)} bytes):\n"
                            + texto.strip()
                        )

                        # Parsear los datos de la CC358
                        monedas = self._parsear(buffer)
                        if monedas:
                            print(f"[PARSER EXITOSO] Monedas: {monedas}")
                            self.callback_datos(monedas)
                        else:
                            print("[PARSER AVISO] No se pudo extraer monedas de la trama.")

                        buffer.clear()
                    time.sleep(0.03)
            except Exception as e:
                print(f"[SERIAL ERROR]: {e}")
                self.callback_log(f"⚠️ Error en lectura: {e}")
                break

    def _loop_simulacion(self):
        """Modo simulación: genera datos de prueba."""
        self.callback_log("⏳ Simulación: esperando 5 segundos...")
        time.sleep(5)

        while self.activo:
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
            self.callback_log(f"\n🟡 [SIMULACIÓN] Conteo generado.")
            self.callback_datos(monedas_sim)
            time.sleep(30)

    def _parsear(self, buffer):
        """
        Parser exacto para la trama de la SAT CC358.
        Estructura de la trama recibida:
          Item:     Quantity     Amount
          1000:     2         2000
           200:     4          800
           500:    13         6500
           100:     7          700
           200:    28         5600
            50:     2          100
           100:    25         2500
            50:     3          150
        Total: 18350
        """
        try:
            texto = buffer.decode("latin1", errors="replace")
            lineas = texto.splitlines()

            monedas = {
                '1000': 0, '200a': 0, '500': 0, '100a': 0,
                '200b': 0, '50a': 0, '100b': 0, '50b': 0
            }

            # El orden fijo de las 8 líneas que envía la CC358:
            # 1. 1000
            # 2. 200 (primera = tipo A)
            # 3. 500
            # 4. 100 (primera = tipo A)
            # 5. 200 (segunda = tipo B)
            # 6. 50  (primera = tipo A)
            # 7. 100 (segunda = tipo B)
            # 8. 50  (segunda = tipo B)
            orden_keys = ['1000', '200a', '500', '100a', '200b', '50a', '100b', '50b']
            idx = 0

            for linea in lineas:
                linea_limpia = linea.strip()
                if not linea_limpia or ':' not in linea_limpia:
                    continue

                if "TOTAL" in linea_limpia.upper() or "ITEM" in linea_limpia.upper():
                    continue

                # Extraer números de la línea: [denominacion, cantidad, subtotal]
                nums = re.findall(r'\d+', linea_limpia)
                if len(nums) >= 2 and idx < len(orden_keys):
                    # nums[0] es la denominación, nums[1] es la CANTIDAD
                    cantidad = int(nums[1])
                    monedas[orden_keys[idx]] = cantidad
                    idx += 1

            if idx >= 8:
                self.callback_log(
                    f"✅ ¡Conteo procesado con éxito por cable!\n"
                    f"   $1.000: {monedas['1000']} | $500: {monedas['500']} | $200(A): {monedas['200a']} | $200(B): {monedas['200b']}\n"
                    f"   $100(A): {monedas['100a']} | $100(B): {monedas['100b']} | $50(A): {monedas['50a']} | $50(B): {monedas['50b']}"
                )
                return monedas

            # Si se leyeron líneas pero menos de 8
            if any(monedas.values()):
                return monedas

            return None
        except Exception as e:
            self.callback_log(f"⚠️ Error al parsear trama: {e}")
            return None
