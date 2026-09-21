"""
Monitor y Sniffer Serial para SAT CC358
---------------------------------------
Este script detecta los puertos COM disponibles, se conecta a la contadora
y muestra todo lo que reciba tanto en texto como en formato HEXADECIMAL (HEX).
Además, guarda todo en un archivo de registro 'captura_cc358.log' para no perder nada.
"""

import sys
import time
from datetime import datetime
import serial
import serial.tools.list_ports

def listar_puertos():
    puertos = list(serial.tools.list_ports.comports())
    return puertos

def seleccionar_puerto():
    while True:
        puertos = listar_puertos()
        if not puertos:
            print("\n⚠️  No se detectaron puertos COM conectados.")
            print("👉 Conecta el adaptador USB-RS232 a tu PC.")
            entrada = input("Presiona [ENTER] para reintentar o 'q' para salir: ").strip().lower()
            if entrada == 'q':
                sys.exit(0)
            continue

        print("\n========================================")
        print("  PUERTOS COM DETECTADOS:")
        print("========================================")
        for idx, p in enumerate(puertos, start=1):
            print(f" [{idx}] {p.device} - {p.description}")
        print("========================================")

        if len(puertos) == 1:
            eleccion = input(f"Se detectó únicamente '{puertos[0].device}'. ¿Usar este puerto? (S/n): ").strip().lower()
            if eleccion in ('', 's', 'si', 'y'):
                return puertos[0].device

        entrada = input("Selecciona el número de puerto (o 'r' para refrescar): ").strip().lower()
        if entrada == 'r':
            continue
        try:
            num = int(entrada)
            if 1 <= num <= len(puertos):
                return puertos[num - 1].device
            else:
                print("❌ Opción inválida.")
        except ValueError:
            print("❌ Entrada inválida.")

def seleccionar_baudrate():
    bauds_comunes = [9600, 4800, 19200, 38400, 57600, 115200, 2400, 1200]
    print("\n----------------------------------------")
    print("Velocidades comunes (Baud Rate):")
    for idx, b in enumerate(bauds_comunes, start=1):
        defecto = " (Por defecto recomendado)" if b == 9600 else ""
        print(f" [{idx}] {b}{defecto}")
    print("----------------------------------------")
    entrada = input("Elige una velocidad [1 por defecto: 9600] o escribe un número: ").strip()
    if not entrada:
        return 9600
    try:
        num = int(entrada)
        if 1 <= num <= len(bauds_comunes):
            return bauds_comunes[num - 1]
        elif num > 100:
            return num
    except ValueError:
        pass
    return 9600

def iniciar_monitor(puerto, baudrate):
    log_filename = "captura_cc358.log"
    print("\n========================================================")
    print(f" Conectando a {puerto} a {baudrate} baudios (8-N-1)...")
    print("========================================================")

    try:
        ser = serial.Serial(
            port=puerto,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0
        )
    except serial.SerialException as e:
        print(f"❌ Error al abrir el puerto {puerto}: {e}")
        return

    print(f"🟢 CONECTADO EXITOSAMENTE A {puerto}")
    print(f"📁 Guardando toda la captura en: {log_filename}")
    print("--------------------------------------------------------")
    print("👉 Enciende la CC358 o presiona 'PRINT' / 'REPORT' en la máquina.")
    print("👉 Presiona Ctrl + C en esta ventana para detener.")
    print("========================================================\n")

    with open(log_filename, "a", encoding="utf-8", errors="replace") as log_file:
        inicio_str = f"\n--- INICIO DE SESION: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {puerto} @ {baudrate} ---\n"
        log_file.write(inicio_str)
        log_file.flush()

        try:
            buffer = bytearray()
            ultimo_tiempo = time.time()

            while True:
                # Leer bytes disponibles
                en_espera = ser.in_waiting
                if en_espera > 0:
                    datos = ser.read(en_espera)
                    buffer.extend(datos)
                    ultimo_tiempo = time.time()
                else:
                    # Si recibimos datos y hubo una pausa de al menos 0.2 segundos, mostramos el bloque
                    if len(buffer) > 0 and (time.time() - ultimo_tiempo > 0.2):
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        hex_str = " ".join(f"{b:02X}" for b in buffer)
                        texto_str = buffer.decode("latin1", errors="replace").replace("\r", "\\r").replace("\n", "\\n\n")

                        salida = (
                            f"\n📥 [{timestamp}] {len(buffer)} bytes recibidos:\n"
                            f"   [HEX]  : {hex_str}\n"
                            f"   [TEXTO]: {texto_str}\n"
                        )
                        print(salida, end="")
                        log_file.write(salida)
                        log_file.flush()
                        buffer.clear()

                    time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n\n⏹️  Monitor detenido por el usuario.")
        finally:
            ser.close()
            print("🔒 Puerto serial cerrado.")

if __name__ == "__main__":
    print("=" * 55)
    print("    SNIFFER & MONITOR SERIAL - SAT CC358")
    print("=" * 55)
    puerto_elegido = seleccionar_puerto()
    baud_elegido = seleccionar_baudrate()
    iniciar_monitor(puerto_elegido, baud_elegido)
