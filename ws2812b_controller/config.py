# ── LED ─────────────────────────────────────────────────────────────────────
LED_PIN    = 4     # GPIO conectado al DIN de la tira
LED_COUNT  = 60    # Número de LEDs
BRIGHTNESS = 0.6   # Brillo global (0.0 – 1.0)

# ── WiFi ─────────────────────────────────────────────────────────────────────
# "AP"  → el ESP32 crea su propio punto de acceso (sin router)
# "STA" → el ESP32 se conecta a tu red WiFi existente
WIFI_MODE     = "AP"
WIFI_SSID     = "LEDControl"
WIFI_PASSWORD = "led12345"

# Solo para WIFI_MODE = "STA"
ROUTER_SSID     = "TuWiFi"
ROUTER_PASSWORD = "TuPassword"

# ── Servidor ─────────────────────────────────────────────────────────────────
SERVER_PORT = 80
