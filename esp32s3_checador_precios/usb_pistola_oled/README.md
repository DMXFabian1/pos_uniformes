# Checador con pistola USB + pantalla OLED integrada

Aparato autónomo: conectas una **pistola lectora USB** al ESP32-S3 (que actúa
como **host USB**), escaneas, y el **precio aparece en la OLED** integrada.
Reusa tu API `/api/v1/precio/{sku}` por WiFi.

## Hardware
| Pieza | Detalle |
|---|---|
| ESP32-S3 (el que ya tienes) | actúa como host USB |
| **Pistola/lector USB** (2D, que lea QR) | en modo **teclado (HID)** |
| **Adaptador OTG** USB-A hembra → USB-C macho | para enchufar la pistola al puerto **OTG** |
| **OLED SSD1306 128x64 I2C** | SDA→GPIO47, SCL→GPIO21, VCC 3V3, GND |
| Alimentación 5V | módulo 18650 a 5V (al pin 5V) o por el puerto UART |

> ⚠️ **Power**: la pistola se alimenta con los 5V que el ESP32 entrega por el
> puerto OTG. Si NO enciende al conectarla, alimenta la placa por el **pin 5V**
> (módulo 18650). Si aún no, usa un adaptador OTG **con entrada de 5V externa**.

## Librerías (Arduino IDE)
- **EspUsbHost** — ⚠️ **instálala desde GitHub**, NO del Gestor (la del gestor es
  vieja y no sirve):
  - <https://github.com/tanakamasayuki/EspUsbHost> → **Code → Download ZIP**
  - Arduino IDE: **Sketch → Incluir biblioteca → Añadir biblioteca .ZIP**
- **ArduinoJson** (v7+)
- **Adafruit SSD1306** + **Adafruit GFX Library**

## Configuración Arduino IDE
- Placa: **ESP32S3 Dev Module** · PSRAM: **OPI PSRAM** · Flash: **16MB**
- **USB CDC On Boot: `Disabled`**  (el USB nativo se usa como HOST, no CDC)
- Si no detecta la pistola, prueba **USB Mode: "USB-OTG (TinyUSB)"**
- **Programa/depura por el puerto UART (wchusbserial)**, NO por el OTG
  (el OTG queda ocupado por la pistola).

## Uso
1. Edita tu WiFi + IP del POS en el `.ino`.
2. Sube por el puerto UART (wchusbserial).
3. Conecta la pistola al puerto OTG (con el adaptador).
4. Escanea → el precio aparece en la OLED.

## La pistola debe estar en modo "teclado" (HID)
La mayoría de las pistolas USB salen así de fábrica (teclean el código + Enter).
Si la tuya tiene modo "Virtual COM", cámbiala a **HID / teclado** (con su QR de
config del manual). Este firmware lee teclas HID y arma el código hasta el Enter.

## Nota
Compila verificado con esp32 core 3.3.8. El funcionamiento del host USB y la
alimentación de la pistola dependen del hardware; pruébalo y si la pistola no
enciende o no se detecta, revisa la sección de Power y el USB Mode.
