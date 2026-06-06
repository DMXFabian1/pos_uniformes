# Demo en Wokwi (vista previa de la interfaz)

Simulación del checador para **ver cómo se comporta antes de soldar**: pantallas
de la OLED, beep del buzzer y el LED, usando el botón como "escáner".

## ⚠️ Qué simula y qué no
| | |
|---|---|
| ✅ OLED, botón, buzzer, LED | Funcionan igual que en el aparato real |
| ✅ Parseo del JSON | Mismo formato que `/api/v1/precio/{sku}` |
| ❌ Cámara / lectura de QR | Wokwi no tiene cámara virtual → se **simula** el escaneo |
| ❌ WiFi / API local | No se puede llegar a tu red → la respuesta se **simula en código** |
| ❌ Deep sleep | Desactivado en la demo para que sea interactiva |

> El firmware **real** (cámara, quirc, WiFi, deep sleep) está en la carpeta de
> arriba: `../esp32s3_checador_precios.ino`.

## Cómo correrlo (2 minutos)

1. Entra a **https://wokwi.com** → **New Project** → elige **ESP32-S3**
   (o cualquier ESP32; luego pegamos el diagrama correcto).
2. En la pestaña del código (`sketch.ino`), borra todo y **pega el contenido de
   `checador_demo_wokwi.ino`**.
3. Abre la pestaña **`diagram.json`** y **pega el contenido de `diagram.json`**
   de esta carpeta.
4. Si pide librerías, agrega las de `libraries.txt`
   (*Library Manager* dentro de Wokwi): **Adafruit SSD1306**, **Adafruit GFX**,
   **ArduinoJson**. (Normalmente las detecta solo.)
5. Pulsa **▶ Play**.

## Qué vas a ver
- Arranca mostrando **"Pulsa el botón"**.
- Cada clic en el **botón verde**:
  1. Enciende el **LED** y muestra "Escaneando...".
  2. Suena el **buzzer**.
  3. Muestra un producto de prueba (nombre + talla/color + **precio**).
- La demo recorre 4 SKUs: 3 existen y **1 no** (`NOEXISTE`), para que veas
  también la pantalla **"No encontrado"**.

## Notas
- Si la OLED no enciende en la simulación, cambia `OLED_DIR` a `0x3D`.
- Si alguna conexión marca error de pin, arrástrala en el editor visual al pin
  correcto (los GND pueden llamarse `GND.1`, `GND.2`, etc. según el modelo).
- Cuando armes el hardware real, usa el sketch de la carpeta de arriba; el
  cableado es el mismo que el de `diagram.json`.
