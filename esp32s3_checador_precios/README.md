# Checador de precios — ESP32-S3 (WROOM N16R8) + OV3660

Versión para la placa **ESP32-S3 dual USB-C con cámara OV3660** (tipo KLYCKIT /
Freenove ESP32-S3-CAM). Hace lo mismo que la versión AI-Thinker, pero adaptada
al ESP32-S3. El QR contiene el **SKU** del producto (`variante.sku`).

> Si tienes el ESP32-CAM AI-Thinker (OV2640), usa la otra carpeta:
> `../esp32_checador_precios/`.

## Diferencias clave vs. AI-Thinker
- **Se programa por USB-C**: **no necesita adaptador FTDI**.
- **Pines de cámara propios** (ya confirmados con el diagrama de la placa).
- **Lectura de QR con `quirc`** directo (más fiable en S3).
- **OLED y buzzer en pines libres**: en el S3 los GPIO 12/14/15 los usa la cámara.

## 1. Hardware

| Componente | Detalle |
|---|---|
| Placa | ESP32-S3-WROOM-1 **N16R8** (16MB flash, 8MB PSRAM) + cámara **OV3660**, dual USB-C |
| Pantalla | OLED **SSD1306 128x64 I2C** |
| Buzzer | Activo |
| Cable | **USB-C** (al puerto rotulado **COM**) |

> La placa viene con **pines sin soldar**: necesitas soldar las tiras de
> headers (o soldar cables directo) para conectar la OLED y el buzzer.

### Conexiones (confirmadas con el diagrama de pines)

| Señal | Pin ESP32-S3 | Notas |
|---|---|---|
| OLED **SDA** | GPIO **47** | |
| OLED **SCL** | GPIO **21** | |
| OLED VCC / GND | 3V3 / GND | |
| Buzzer (+) / (–) | GPIO **14** / GND | buzzer activo |
| **Botón** | GPIO **1** ↔ GND | sin resistencia externa (pull-up interno) |
| **LED** iluminación | GPIO **41** → LED → **R 220Ω** → GND | LED blanco recomendado |

Pines evitados a propósito: `GPIO2` (LED ON), `GPIO42` (JTAG/MTMS),
`GPIO48` (LED RGB WS2812), los de la cámara y `GPIO19/20` (USB nativo).

### Alimentación

- **Más fácil:** cable **USB-C** (al puerto **COM**) o un **power bank USB**.
- **Con pilas AA recargables (NiMH):** NO las conectes directo. Usa
  `3–4 pilas AA → módulo step-up (boost) a 5V → pin 5V de la placa`.
  El boost mantiene 5 V estables aunque las pilas se descarguen.
- ⚠️ Alimenta por **una sola fuente a la vez** (USB **o** pilas, no ambas).
- 🔋 El **botón** ahorra batería (la cámara solo captura al escanear). Para
  máxima duración se puede añadir *deep sleep* y despertar con el botón
  (GPIO1 es apto para wake) — pídelo y lo agrego.

## 2. Software (Arduino IDE)

### Librerías (Gestor de Librerías)
- **ArduinoJson** — Benoit Blanchon (v7+)
- **Adafruit SSD1306** + **Adafruit GFX Library**
- **ESP32QRCodeReader** — Álvaro Viebrantz
  - No usamos su API de alto nivel, pero **incluye `quirc.h`** (el
    decodificador de QR que sí usamos). Es la forma más fácil de tener `quirc`
    disponible en el IDE.

`esp_camera`, `WiFi`, `HTTPClient` y `Wire` vienen con el paquete **esp32**.

### Configuración de la placa
- **Placa:** `ESP32S3 Dev Module`
- **PSRAM:** `OPI PSRAM`  *(obligatorio)*
- **Flash Size:** `16MB (128Mb)`
- **USB CDC On Boot:** `Enabled`  *(para ver el Monitor Serie por USB-C)*
- **Partition Scheme:** `16M Flash (3MB APP/9.9MB FATFS)` o `Huge APP`

## 3. Configura el sketch

En `esp32s3_checador_precios.ino`, sección **[B]**:

```cpp
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";
const char* API_BASE      = "http://192.168.0.10:8000";  // IP del POS + puerto
```

## 4. Subir el firmware

1. Conecta el cable **USB-C** al puerto **COM**.
2. Selecciona el puerto en *Herramientas → Puerto*.
3. Sube el sketch. Si no entra en modo descarga: mantén **BOOT**, pulsa y
   suelta **RST**, luego suelta **BOOT** y vuelve a subir.

## 5. Cómo funciona

1. Conecta WiFi y muestra **"Pulsa el botón"**.
2. Al **pulsar el botón**: enciende el **LED** y la cámara busca un QR durante
   unos segundos (`VENTANA_ESCANEO_MS`).
3. Si lo lee: **beep**, apaga el LED y hace `GET /api/v1/precio/<sku>`.
4. Muestra **nombre, talla/color y precio**; si no existe, **"No encontrado"**;
   si no detectó QR, **"No se detectó ningún código"**.
5. A los **5 segundos** vuelve a la pantalla de espera.

## 6. Endpoint que consume

```
GET /api/v1/precio/{sku}
```
```json
{ "encontrado": true, "sku": "JUMP-6", "nombre": "Jumper Primaria X",
  "talla": "6", "color": "Azul", "precio": 350.00 }
```

Prueba desde una PC en la red:
```
curl http://192.168.0.10:8000/api/v1/precio/JUMP-6
```

## Notas / pendientes
- El sketch **no se ha probado en hardware**; hay que compilarlo y flashearlo.
  Si algo falla, lo más probable es `quirc` (memoria) o la dirección I2C de la
  OLED (`0x3C`/`0x3D`). Avísame y ajustamos.
- El endpoint es **público** (sin token): úsalo **solo en la red local**.
- Si la lectura de QR va lenta, se puede bajar a `FRAMESIZE_QQVGA` o subir el
  `xclk_freq_hz`.
