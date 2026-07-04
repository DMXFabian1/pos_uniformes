# WS2812B LED Controller — ESP32 / ESP8266 (MicroPython)

Control remoto via **PWA desde tu celular** por WiFi.

## Archivos

| Archivo | Descripción |
|---|---|
| `config.py` | Pin GPIO, LEDs, brillo y configuración WiFi |
| `led_controller.py` | Clase `WS2812B` con 23 efectos interruptibles |
| `wifi_server.py` | WiFi + servidor HTTP que sirve la PWA y la API |
| `index.html` | Interfaz web (PWA) que se abre en el celular |
| `main.py` | Punto de entrada; integra servidor y efectos |

---

## Conexión del hardware

```
ESP32 / ESP8266        WS2812B
───────────────        ───────
GND           ──────► GND
5V / VIN      ──────► 5V
GPIO 4        ──────► DIN   (configurable en config.py)
```

> Para tiras largas (> 30 LEDs) usa fuente externa de 5V y comparte GND.

---

## Instalación

### 1. Flashea MicroPython en el ESP32

Descarga el firmware desde [micropython.org](https://micropython.org/download/ESP32_GENERIC/) y flashéalo.

### 2. Copia los 5 archivos al ESP32

Con **Thonny** (más fácil):
- Abre cada archivo → Archivo → Guardar como → MicroPython device

Con **ampy** desde terminal:
```bash
pip install adafruit-ampy
ampy --port /dev/ttyUSB0 put config.py
ampy --port /dev/ttyUSB0 put led_controller.py
ampy --port /dev/ttyUSB0 put wifi_server.py
ampy --port /dev/ttyUSB0 put index.html
ampy --port /dev/ttyUSB0 put main.py
```

Con **rshell**:
```bash
pip install rshell
rshell -p /dev/ttyUSB0
cp config.py /pyboard/
cp led_controller.py /pyboard/
cp wifi_server.py /pyboard/
cp index.html /pyboard/
cp main.py /pyboard/
```

### 3. Configura `config.py`

```python
LED_PIN    = 4      # Tu pin GPIO
LED_COUNT  = 60     # Número de LEDs
BRIGHTNESS = 0.6    # Brillo (0.0–1.0)

WIFI_MODE  = "AP"           # o "STA" para conectar a tu router
WIFI_SSID  = "LEDControl"
WIFI_PASSWORD = "led12345"
```

### 4. Reinicia el ESP32

El serial mostrará algo como:
```
╔══════════════════════════════╗
║  LED Control listo           ║
║  WiFi : LEDControl           ║
║  URL  : http://192.168.4.1   ║
╚══════════════════════════════╝
```

---

## Uso

### Modo AP (predeterminado)
1. En tu celular ve a **WiFi** y conéctate a `LEDControl` (contraseña: `led12345`).
2. Abre el navegador y ve a **http://192.168.4.1**
3. Aparece la app de control.

### Modo STA
1. Cambia `WIFI_MODE = "STA"` y pon los datos de tu router en `config.py`.
2. El ESP32 se conecta a tu red y muestra la IP por serial.
3. Ambos (celular y ESP32) deben estar en la misma red WiFi.

### Instalar como app (opcional)
- **Android (Chrome):** menú ⋮ → "Añadir a pantalla de inicio"
- **iOS (Safari):** botón compartir → "Añadir a pantalla de inicio"

---

## Interfaz de la app

| Pestaña | Contenido |
|---|---|
| **Efectos** | 22 efectos organizados por categoría |
| **Color** | Selector nativo, sliders RGB y 9 paletas |
| **Config** | Brillo global, velocidad y botón apagar |

El punto de colores en el encabezado indica el estado:
- 🟢 Verde — conectado al ESP32
- 🔴 Rojo — sin conexión

---

## Efectos disponibles

| Categoría | Efectos |
|---|---|
| Animaciones | Rainbow, Glitter, Chase, Color Shift, Running, Teatro, Scanner, Bounce, Respirar, Latido, Cometa, Meteoro |
| Ambiente | Fuego, Plasma, Aurora, Lava Lamp, Matrix, Hiperespacio, Twinkle, Chispas |
| Dramáticos | Relámpago, Strobe |

---

## API HTTP

El ESP32 expone una API REST simple para integraciones externas:

```
GET  /api/status       → estado actual (JSON)
POST /api/cmd          → enviar comando (JSON)
```

Ejemplos:
```bash
# Cambiar efecto
curl -X POST http://192.168.4.1/api/cmd \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"effect","name":"fire"}'

# Color sólido
curl -X POST http://192.168.4.1/api/cmd \
  -d '{"cmd":"color","r":255,"g":0,"b":100}'

# Brillo al 80%
curl -X POST http://192.168.4.1/api/cmd \
  -d '{"cmd":"brightness","value":0.8}'

# Velocidad 50ms/frame
curl -X POST http://192.168.4.1/api/cmd \
  -d '{"cmd":"speed","value":50}'

# Apagar
curl -X POST http://192.168.4.1/api/cmd \
  -d '{"cmd":"off"}'
```
