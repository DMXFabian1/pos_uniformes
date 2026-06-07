/* ===========================================================================
 *  CHECADOR DE PRECIOS — LECTOR GM65 (prueba por consola)
 *  ESP32-S3 + módulo escáner QR/código de barras GM65
 * ===========================================================================
 *
 *  Versión con LECTOR DEDICADO GM65 en vez de la cámara. El GM65 decodifica
 *  el QR/código de barras por hardware y manda el texto (el SKU) por UART.
 *  Mucho más confiable que la cámara: lee siempre, con su luz de apuntado.
 *
 *  Esta versión imprime todo en el Monitor Serie (sin OLED todavía).
 *
 *  ---------------------------------------------------------------------------
 *  CONEXIÓN del GM65 al ESP32-S3 (UART):
 *     GM65 VCC  -> 5V (o 3V3 según tu módulo)
 *     GM65 GND  -> GND
 *     GM65 TXD  -> GPIO 18  (RX del ESP32)
 *     GM65 RXD  -> GPIO 17  (TX del ESP32)
 *
 *  El GM65 trae un manual con códigos QR de configuración. Conviene escanear
 *  una vez el QR de "modo continuo / auto-sensing" para que lea solo al
 *  detectar algo enfrente (o usa su botón para disparar). Baud por defecto 9600.
 *
 *  ---------------------------------------------------------------------------
 *  LIBRERÍAS: ArduinoJson (v7+). Nada de cámara ni quirc.
 *  CONFIG IDE: ESP32S3 Dev Module · puerto wchusbserial · 115200 en el Monitor.
 *  (Aquí la PSRAM ya no es obligatoria, pero puedes dejar OPI PSRAM.)
 * ===========================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── CONFIG — EDITA ESTO ─────────────────────────────────────────────────────
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";
const char* API_BASE      = "http://192.168.0.10:8000";   // IP del POS + puerto

// ── UART del GM65 ───────────────────────────────────────────────────────────
#define GM65_RX_PIN  18    // ESP32 RX  <-- GM65 TXD
#define GM65_TX_PIN  17    // ESP32 TX  --> GM65 RXD
#define GM65_BAUD    9600  // baud por defecto del GM65
HardwareSerial GM65(1);    // usa el UART1 del ESP32

String lectura = "";
unsigned long ultimoByte = 0;

// ── WiFi ──────────────────────────────────────────────────────────────────
void conectarWiFi() {
  Serial.printf("Conectando a WiFi '%s'", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) { delay(300); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("\nWiFi OK. IP: %s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("\n** No se pudo conectar al WiFi **");
}

// ── Consulta a la API ───────────────────────────────────────────────────────
String urlEncode(const String& s) {
  String o = ""; char buf[4];
  for (unsigned int i = 0; i < s.length(); i++) {
    char c = s[i];
    if (isalnum(c) || c=='-'||c=='_'||c=='.'||c=='~') o += c;
    else { sprintf(buf, "%%%02X", (unsigned char)c); o += buf; }
  }
  return o;
}

void consultar(const String& sku) {
  if (WiFi.status() != WL_CONNECTED) { conectarWiFi(); return; }
  String url = String(API_BASE) + "/api/v1/precio/" + urlEncode(sku);
  Serial.println("  GET " + url);

  HTTPClient http;
  http.setConnectTimeout(4000);
  http.setTimeout(4000);
  http.begin(url);
  int code = http.GET();

  if (code == 200) {
    String cuerpo = http.getString();
    Serial.println("  Respuesta: " + cuerpo);
    JsonDocument doc;
    if (deserializeJson(doc, cuerpo)) {
      Serial.println("  [!] JSON invalido");
    } else if (doc["encontrado"] | false) {
      Serial.printf("  >> PRODUCTO: %s | Talla %s | %s | $%.2f\n",
        (const char*)(doc["nombre"] | ""),
        (const char*)(doc["talla"]  | ""),
        (const char*)(doc["color"]  | ""),
        (double)(doc["precio"] | 0.0));
    } else {
      Serial.println("  >> NO ENCONTRADO");
    }
  } else {
    Serial.printf("  [!] Error HTTP %d (¿esta corriendo la API y es la IP correcta?)\n", code);
  }
  http.end();
}

// ── Setup / Loop ────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(600);
  Serial.println("\n\n=== CHECADOR DE PRECIOS — lector GM65 (consola) ===");

  GM65.begin(GM65_BAUD, SERIAL_8N1, GM65_RX_PIN, GM65_TX_PIN);
  conectarWiFi();
  Serial.println("Listo. Escanea un QR/codigo con el GM65...");
}

void loop() {
  // Acumula los bytes que manda el GM65.
  while (GM65.available()) {
    char c = (char)GM65.read();
    if (c == '\r' || c == '\n') {
      // posible fin de código; lo procesamos abajo por la pausa
    } else {
      lectura += c;
    }
    ultimoByte = millis();
  }

  // Si ya no llegan bytes por 60 ms y hay algo, es un código completo.
  if (lectura.length() > 0 && millis() - ultimoByte > 60) {
    lectura.trim();
    if (lectura.length() > 0) {
      Serial.println("Codigo leido: " + lectura);
      consultar(lectura);
      Serial.println();
    }
    lectura = "";
  }
}
