"""
main.py — Punto de entrada.
Copia este archivo y `led_controller.py` + `config.py` a tu ESP32/ESP8266
usando Thonny, ampy, o rshell y ejecuta con: mpremote run main.py
"""

import config
from led_controller import WS2812B

# ── Inicialización ───────────────────────────────────────────────────────────
led = WS2812B(
    pin=config.LED_PIN,
    count=config.LED_COUNT,
    brightness=config.BRIGHTNESS,
)

# ── Modo de operación ────────────────────────────────────────────────────────
# Pon MODE en:
#   "demo"       → recorre todos los efectos automáticamente
#   "single"     → ejecuta solo el efecto indicado en SINGLE_EFFECT
#   "interactive"→ controla por consola serial (requiere conexión USB)

MODE = "demo"
SINGLE_EFFECT = "aurora"   # solo usado si MODE == "single"

# ── Efectos disponibles (nombre → función) ───────────────────────────────────
EFFECTS = {
    "solid_rojo":     lambda: led.solid(255, 0, 0, 3000),
    "solid_azul":     lambda: led.solid(0, 100, 255, 3000),
    "solid_verde":    lambda: led.solid(0, 255, 80, 3000),
    "solid_blanco":   lambda: led.solid(255, 255, 255, 3000),
    "breathe_azul":   lambda: led.breathe(0, 100, 255, 8, 3),
    "breathe_rojo":   lambda: led.breathe(255, 0, 0, 8, 3),
    "heartbeat":      lambda: led.heartbeat(255, 0, 60, 12, 5),
    "color_shift":    lambda: led.color_shift(50, 300),
    "rainbow":        lambda: led.rainbow(18, 3),
    "glitter_rainbow":lambda: led.glitter_rainbow(18, 2),
    "rainbow_chase":  lambda: led.rainbow_chase(55, 5),
    "running_lights": lambda: led.running_lights(255, 50, 200, 35, 3),
    "theater_chase":  lambda: led.theater_chase(255, 0, 200, 80, 10),
    "scanner":        lambda: led.scanner(255, 0, 0, 4, 35, 4),
    "bounce":         lambda: led.bounce(160, 0, 255, 22, 5),
    "meteor_azul":    lambda: led.meteor_rain(30, 120, 255, 10, 65, 22, 2),
    "meteor_rojo":    lambda: led.meteor_rain(255, 50, 0, 10, 65, 22, 2),
    "comet":          lambda: led.comet(0, 255, 80, 14, 18, 3),
    "fire":           lambda: led.fire(55, 120, 15, 200),
    "plasma":         lambda: led.plasma(22, 150),
    "aurora":         lambda: led.aurora(32, 200),
    "lava_lamp":      lambda: led.lava_lamp(35, 200),
    "matrix":         lambda: led.matrix_rain(50, 150),
    "twinkle":        lambda: led.twinkle(255, 255, 255, 10, 80, 30),
    "sparkle":        lambda: led.sparkle_fade(255, 200, 50, 18, 150),
    "lightning":      lambda: led.lightning(10, 25),
    "strobe":         lambda: led.strobe(255, 255, 255, 15, 40),
    "hyperspace":     lambda: led.hyperspace(5, 120),
}


def interactive_mode():
    """Control por consola serial: escribe el nombre del efecto y Enter."""
    print("\n=== WS2812B Control Interactivo ===")
    print("Efectos disponibles:")
    for name in sorted(EFFECTS.keys()):
        print("  -", name)
    print("Escribe 'demo' para el ciclo completo o 'off' para apagar.\n")
    while True:
        try:
            cmd = input("Efecto > ").strip().lower()
        except EOFError:
            break
        if cmd == "off":
            led.clear()
            print("LEDs apagados.")
        elif cmd == "demo":
            led.demo()
        elif cmd in EFFECTS:
            print("Ejecutando:", cmd)
            EFFECTS[cmd]()
            led.clear()
        else:
            print("Efecto desconocido. Escribe el nombre exacto de la lista.")


# ── Main ─────────────────────────────────────────────────────────────────────
print("WS2812B Controller iniciado. PIN={} LEDs={} BRILLO={}".format(
    config.LED_PIN, config.LED_COUNT, config.BRIGHTNESS))

if MODE == "demo":
    while True:
        led.demo()

elif MODE == "single":
    if SINGLE_EFFECT in EFFECTS:
        while True:
            EFFECTS[SINGLE_EFFECT]()
    else:
        print("Efecto '{}' no encontrado.".format(SINGLE_EFFECT))

elif MODE == "interactive":
    interactive_mode()
