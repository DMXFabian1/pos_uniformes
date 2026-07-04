"""
main.py — Punto de entrada con control via PWA.

Copia estos archivos a la raíz del ESP32:
  main.py  config.py  led_controller.py  wifi_server.py  index.html

El ESP32 inicia WiFi, levanta el servidor HTTP y muestra la URL por serial.
Abre esa URL en tu celular para controlar los LEDs.
"""

import config
import _thread
import time
import wifi_server
from led_controller import WS2812B

# ── Inicialización ───────────────────────────────────────────────────────────

ip = wifi_server.setup_wifi(
    config.WIFI_MODE,
    config.WIFI_SSID,   config.WIFI_PASSWORD,
    config.ROUTER_SSID, config.ROUTER_PASSWORD,
)

led = WS2812B(pin=config.LED_PIN, count=config.LED_COUNT, brightness=config.BRIGHTNESS)

# Enlace entre el servidor y el objeto LED (para interrumpir efectos)
wifi_server.led_ref = led

# ── Servidor HTTP en hilo de fondo ───────────────────────────────────────────

_srv = wifi_server.start_server(config.SERVER_PORT)

def _server_loop():
    while True:
        try:
            conn, _ = _srv.accept()
            wifi_server.handle(conn)
        except OSError:
            pass  # timeout corto, normal

_thread.start_new_thread(_server_loop, ())

# ── Mapa efecto → función del controlador ────────────────────────────────────

def _run_effect():
    st  = wifi_server.state
    nm  = st["effect"]
    r, g, b = st["r"], st["g"], st["b"]
    sp  = st["speed"]
    led.brightness = st["brightness"]
    led.stop_flag  = False

    if st["off"]:
        led.clear()
        time.sleep_ms(200)
        return

    try:
        if   nm == "solid":          led.solid(r, g, b, 1000)
        elif nm == "breathe":        led.breathe(r, g, b, max(5, sp // 3), 1)
        elif nm == "heartbeat":      led.heartbeat(r, g, b, max(8, sp // 2), 1)
        elif nm == "color_shift":    led.color_shift(sp, 200)
        elif nm == "rainbow":        led.rainbow(max(5, sp), 1)
        elif nm == "glitter_rainbow":led.glitter_rainbow(max(5, sp), 1)
        elif nm == "rainbow_chase":  led.rainbow_chase(max(30, sp * 2), 1)
        elif nm == "running_lights": led.running_lights(r, g, b, sp, 1)
        elif nm == "theater_chase":  led.theater_chase(r, g, b, max(50, sp * 2), 4)
        elif nm == "scanner":        led.scanner(r, g, b, 4, sp, 1)
        elif nm == "bounce":         led.bounce(r, g, b, sp, 1)
        elif nm == "meteor":         led.meteor_rain(r, g, b, 10, 65, sp, 1)
        elif nm == "comet":          led.comet(r, g, b, 14, sp, 1)
        elif nm == "fire":           led.fire(55, 120, max(8, sp // 2), 100)
        elif nm == "plasma":         led.plasma(sp, 100)
        elif nm == "aurora":         led.aurora(sp, 100)
        elif nm == "lava_lamp":      led.lava_lamp(sp, 100)
        elif nm == "matrix_rain":    led.matrix_rain(max(30, sp * 2), 100)
        elif nm == "twinkle":        led.twinkle(r, g, b, 10, max(50, sp * 2), 15)
        elif nm == "sparkle":        led.sparkle_fade(r, g, b, sp, 100)
        elif nm == "lightning":      led.lightning(5, sp)
        elif nm == "strobe":         led.strobe(r, g, b, 8, sp)
        elif nm == "hyperspace":     led.hyperspace(max(3, sp // 5), 100)
        else:                        led.rainbow(sp, 1)
    except Exception as e:
        print("Error en efecto '{}':".format(nm), e)

# ── Loop principal ───────────────────────────────────────────────────────────

print("Listo. URL: http://{}".format(ip))

while True:
    wifi_server.state["changed"] = False
    _run_effect()
