# WS2812B LED Controller — ESP32 / ESP8266 (MicroPython)

## Archivos

| Archivo | Descripción |
|---|---|
| `config.py` | Pin GPIO, cantidad de LEDs y brillo global |
| `led_controller.py` | Clase `WS2812B` con todos los efectos |
| `main.py` | Punto de entrada; elige el modo de operación |

## Conexión del hardware

```
ESP32/ESP8266          WS2812B
─────────────          ───────
GND        ──────────► GND
5V / VIN   ──────────► 5V
GPIO 4     ──────────► DIN  (ajusta LED_PIN en config.py)
```

> Si la tira es corta (< 30 LEDs) puedes alimentarla desde el ESP.
> Para tiras largas usa una fuente externa de 5 V y comparte GND.

## Instalación

1. Flashea MicroPython en tu ESP32/ESP8266.
2. Copia los tres archivos con Thonny, `ampy` o `rshell`:
   ```bash
   ampy --port /dev/ttyUSB0 put config.py
   ampy --port /dev/ttyUSB0 put led_controller.py
   ampy --port /dev/ttyUSB0 put main.py
   ```
3. Edita `config.py` con tu pin y número de LEDs.
4. Reinicia el ESP o ejecuta `main.py`.

## Modos de operación (`main.py`)

| `MODE` | Comportamiento |
|---|---|
| `"demo"` | Cicla por todos los efectos automáticamente |
| `"single"` | Repite en bucle el efecto indicado en `SINGLE_EFFECT` |
| `"interactive"` | Control por consola serial (Thonny/minicom) |

## Efectos disponibles

| Efecto | Descripción |
|---|---|
| `solid` | Color fijo |
| `breathe` | Respiración suave |
| `heartbeat` | Pulso de corazón (lub-dub) |
| `color_shift` | Transición continua de color en toda la tira |
| `rainbow` | Arco iris desplazándose |
| `glitter_rainbow` | Arco iris con destellos blancos |
| `rainbow_chase` | Arco iris en perseguidor de 3 en 3 |
| `running_lights` | Ola sinusoidal suave |
| `theater_chase` | Perseguidor clásico |
| `scanner` | Ojo KITT/Cylon que rebota |
| `bounce` | Punto de luz que rebota |
| `meteor_rain` | Meteoro con cola que se desvanece |
| `comet` | Cometa que cruza la tira |
| `fire` | Simulación de fuego realista |
| `plasma` | Ondas de plasma con senos múltiples |
| `aurora` | Auroras boreales suaves |
| `lava_lamp` | Burbujas de color flotando |
| `matrix_rain` | Lluvia verde estilo Matrix |
| `twinkle` | Destellos aleatorios |
| `sparkle_fade` | Chispas que se apagan gradualmente |
| `lightning` | Relámpago |
| `strobe` | Estroboscopio |
| `hyperspace` | Estrellas acelerando hacia el hiperespacio |
