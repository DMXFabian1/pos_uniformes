# Checador de precios — ESP32-CAM

Lector de códigos QR con ESP32-CAM que consulta el precio de tus productos en
el POS y lo muestra en una pantalla OLED. El QR contiene el **SKU** del producto
(`variante.sku` de la base de datos).

```
[QR del producto] --cámara--> ESP32-CAM --WiFi/HTTP GET--> API del POS --> PostgreSQL
                                   |
                                   +--> OLED (nombre + precio)  +  buzzer (beep)
```

## 1. Hardware

| Componente | Detalle |
|---|---|
| Placa | ESP32-CAM **AI-Thinker** con cámara OV2640 (**con PSRAM**) |
| Pantalla | OLED **SSD1306 128x64 I2C** |
| Buzzer | Activo (recomendado) |
| Programador | Adaptador FTDI / USB-TTL a **5V** |

### Conexiones

| Señal | Pin ESP32-CAM |
|---|---|
| OLED **SDA** | GPIO **15** |
| OLED **SCL** | GPIO **14** |
| OLED VCC | 3V3 |
| OLED GND | GND |
| Buzzer (+) | GPIO **12** |
| Buzzer (–) | GND |

> ⚠️ Los GPIO 12, 14 y 15 son los pines de la microSD del ESP32-CAM. Quedan
> libres porque este proyecto **no usa tarjeta microSD**. El GPIO 12 es un
> *strapping pin*: úsalo con un buzzer **activo** (en reposo queda en LOW). Si
> el buzzer queda en HIGH durante el arranque, la placa puede no encender.

## 2. Software (Arduino IDE)

### Paquete de placas
En *Preferencias → URLs adicionales de Gestor de Tarjetas* agrega:
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```
Luego en *Gestor de Tarjetas* instala **esp32** (Espressif).

### Librerías (Gestor de Librerías)
- **ArduinoJson** — Benoit Blanchon (v7+)
- **Adafruit SSD1306** — Adafruit
- **Adafruit GFX Library** — Adafruit
- **ESP32QRCodeReader** — Álvaro Viebrantz
  - Si no aparece en el gestor, descárgala de
    <https://github.com/alvarowolfx/ESP32QRCodeReader> e instálala con
    *Sketch → Incluir librería → Añadir biblioteca .ZIP*.

`WiFi`, `HTTPClient`, `Wire` y `esp_camera` ya vienen con el paquete esp32.

### Configuración de la placa
- **Placa:** `AI Thinker ESP32-CAM`
- **PSRAM:** `Enabled` (obligatorio)
- **Partition Scheme:** `Huge APP (3MB No OTA/1MB SPIFFS)`

## 3. Configura el sketch

En `esp32_checador_precios.ino` edita:

```cpp
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";
const char* API_BASE      = "http://192.168.0.10:8000";  // IP del POS + puerto
```

`API_BASE` debe apuntar a la PC donde corre la API del POS, en la misma red WiFi.

## 4. Subir el firmware

1. Conecta el FTDI: `5V→5V`, `GND→GND`, `U0R→TX`, `U0T→RX`.
2. Puentea **GPIO0 → GND** (modo descarga) y pulsa **RESET**.
3. Sube el sketch desde el Arduino IDE.
4. Quita el puente GPIO0–GND y pulsa **RESET** para arrancar.

## 5. Cómo funciona

1. Arranca, se conecta al WiFi y muestra **"Escanea un QR"**.
2. Al detectar un QR: **suena el buzzer** y consulta
   `GET /api/v1/precio/<sku>` en la API.
3. Muestra **nombre, talla/color y precio**; si no existe, **"No encontrado"**.
4. A los **5 segundos** vuelve a la pantalla de espera.

## 6. Endpoint que consume

Servido por la API del POS (FastAPI), público en la LAN:

```
GET /api/v1/precio/{sku}
```

Respuesta (HTTP 200 siempre):

```json
{ "encontrado": true, "sku": "JUMP-6", "nombre": "Jumper Primaria X",
  "talla": "6", "color": "Azul", "precio": 350.00 }
```

Para probarlo desde una PC en la red:
```
curl http://192.168.0.10:8000/api/v1/precio/JUMP-6
```

## Notas

- El endpoint es **público** (sin token) para simplificar el firmware:
  exponlo **solo en la red local**, no a internet.
- La cámara y la OLED conviven sin problema porque la OLED usa los pines de la
  microSD (libres) y no los de la cámara.
- Si la OLED no enciende, prueba la dirección I2C `0x3D` en `OLED_DIR`.
