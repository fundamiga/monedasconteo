# Plan de Integración - Contadora de Monedas SAT CC358

Este proyecto conecta la máquina contadora de monedas **SAT CC358** con un PC a través de un puerto serial RS-232 y genera reportes automáticos en **Excel**.

---

## 🔌 Requisitos de Hardware

1. **Contadora de Monedas SAT CC358** (con puerto RS-232 DB9).
2. **Adaptador USB a RS-232 DB9 Hembra** (Recomendado con chip FTDI).

---

## 🛠️ Requisitos de Software

- **Python 3.12+** (Ya verificado en el sistema).
- Librerías necesarias:
  - `pyserial` (Para comunicación con el puerto COM) - *Ya instalada*.
  - `openpyxl` (Para manipulación de hojas de cálculo Excel) - *Ya instalada*.
  - `customtkinter` (Para la interfaz visual moderna de escritorio) - *Ya instalada*.

---

## 🧭 Fases del Proyecto

### Fase 1: Sniffing y Descubrimiento del Protocolo (Actual)
Cuando llegue el cable:
1. Conectar el adaptador a la PC y a la contadora.
2. Ejecutar el monitor serial:
   ```bash
   python monitor_serial.py
   ```
3. Seleccionar el puerto COM detectado (ej. COM3, COM4).
4. Realizar un conteo de prueba en la máquina o presionar el botón `PRINT` / `REPORT`.
5. El monitor mostrará en tiempo real:
   - Los bytes en **HEXADECIMAL** (para ver caracteres especiales o de control).
   - Los bytes en **TEXTO** legible.
   - Guardará todo automáticamente en `captura_cc358.log`.

---

### Fase 2: Construcción del Parser (`cc358_parser.py`)
Con la trama real capturada en la Fase 1:
- Se identifican los delimitadores (ej. STX `0x02`, ETX `0x03`, retornos de carro `\r\n`).
- Se mapea cada denominación ($50, $100, $200, $500, $1.000) con su cantidad de monedas y valor total.

---

### Fase 3: Exportación a Excel (`export_excel.py`)
- Creación y actualización automática del archivo `.xlsx` con:
  - Fecha y hora exacta del conteo.
  - Desglose por moneda.
  - Cantidades y total recaudado.

---

### Fase 4: Interfaz Gráfica (GUI con CustomTkinter)
- Visualización en vivo de los datos en pantalla.
- Botones de "Conectar", "Exportar a Excel", y "Historial de conteos".
