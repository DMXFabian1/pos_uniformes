# Checador de precios — ESP32-S3 (WROOM N16R8) + cámara OV2640/OV3660

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
| Placa | ESP32-S3-WROOM-1 **N16R8** (16MB flash, 8MB PSRAM) + cámara **OV2640 u OV3660**, dual USB-C |
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
- 🔋 **Deep sleep activado** (`USAR_DEEP_SLEEP = true`): entre escaneos la placa
  duerme y despierta al pulsar el botón (GPIO1). Esto lleva la autonomía de
  ~horas a **días/semanas** con pilas AA recargables.

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

Hay dos modos, según `USAR_DEEP_SLEEP` en la sección **[B]** del `.ino`:

### Modo batería (`USAR_DEEP_SLEEP = true`) — por defecto
1. La placa está **dormida** (consumo mínimo, ~microamperios).
2. **Pulsas el botón** → despierta, conecta WiFi e inicia la cámara (~3-4 s).
3. Enciende el **LED** y busca el QR; al leerlo: **beep** y
   `GET /api/v1/precio/<sku>`.
4. Muestra **nombre, talla/color y precio** (o "No encontrado") por 5 s.
5. **Vuelve a dormir** hasta el siguiente botonazo.

### Modo USB (`USAR_DEEP_SLEEP = false`)
Igual, pero **siempre encendido**: responde al instante (sin los 3-4 s de
arranque), a costa de más consumo. Ideal si está conectado por USB.

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

## 7. Lista de compras

Precios aproximados en **MXN (México, 2026)**; varían por tienda.

### Electrónica (lo esencial)
| # | Componente | Cant. | Precio aprox. |
|---|---|---|---|
| 1 | Placa **ESP32-S3 N16R8 + OV3660** (KLYCKIT, dual USB-C) | 1 | $250 – $400 |
| 2 | **OLED SSD1306 0.96" 128x64 I2C** (4 pines) | 1 | $70 – $150 |
| 3 | **Buzzer activo** 5V | 1 | $10 – $30 |
| 4 | **Botón** push (momentáneo, tipo tact o de panel) | 1 | $5 – $30 |
| 5 | **LED blanco** 5mm + **resistencia 220Ω** | 1 | $5 – $15 |
| 6 | Cable **USB-C** (para programar) | 1 | $30 – $60 |

### Para alimentar con pilas AA recargables
| # | Componente | Cant. | Precio aprox. |
|---|---|---|---|
| 7 | Módulo **step-up boost MT3608** (ajustable a 5V) | 1 | $20 – $40 |
| 8 | **Portapilas 3×AA** (con interruptor, ideal) | 1 | $20 – $50 |
| 9 | **Pilas AA NiMH recargables** | **3** (pack de 4) | $80 – $180 |
| 10 | **Cargador** de pilas AA (si no tienes) | 1 | $150 – $300 |

### Armado (si no lo tienes)
| # | Componente | Precio aprox. |
|---|---|---|
| 11 | **Tiras de headers** macho (la placa viene SIN soldar) | $10 – $30 |
| 12 | **Cautín + soldadura** (para soldar headers/cables) | $150 – $400 |
| 13 | Cables dupont y/o protoboard | $40 – $100 |

> 💡 **Atajo:** si no quieres lidiar con boost + pilas, un **power bank USB**
> (~$150–300) reemplaza los puntos 7–10: solo conectas el USB-C.

**Estimado solo electrónica (1–6):** ~$370 – $685
**Con kit de pilas (7–10):** +$270 – $570
**Total típico armado:** **~$650 – $1,250 MXN**

## Notas / pendientes
- El sketch **no se ha probado en hardware**; hay que compilarlo y flashearlo.
  Si algo falla, lo más probable es `quirc` (memoria) o la dirección I2C de la
  OLED (`0x3C`/`0x3D`). Avísame y ajustamos.
- El endpoint es **público** (sin token): úsalo **solo en la red local**.
- Si la lectura de QR va lenta, se puede bajar a `FRAMESIZE_QQVGA` o subir el
  `xclk_freq_hz`.
