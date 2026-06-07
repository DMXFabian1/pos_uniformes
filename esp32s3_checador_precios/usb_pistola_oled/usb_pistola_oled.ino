/* ===========================================================================
 *  CHECADOR DE PRECIOS — PISTOLA USB + PANTALLA OLED INTEGRADA
 *  ESP32-S3 (host USB) + lector de código de barras/QR USB + OLED SSD1306
 * ===========================================================================
 *
 *  La pistola USB se conecta al ESP32-S3 (que actúa como HOST USB) y "teclea"
 *  el código escaneado. El ESP32 lo recibe, consulta tu API por WiFi y muestra
 *  el NOMBRE y PRECIO en la pantalla OLED integrada. Aparato autónomo.
 *
 *  ---------------------------------------------------------------------------
 *  CONEXIONES:
 *    PISTOLA USB -> puerto USB-C "OTG" del ESP32, con un adaptador OTG
 *                   (USB-A hembra -> USB-C macho).
 *    OLED SSD1306 (I2C):  SDA -> GPIO 47 , SCL -> GPIO 21 , VCC 3V3 , GND
 *    ALIMENTACIÓN: por el pin 5V (desde el módulo 18650 a 5V) o por el puerto
 *                  UART. El puerto OTG debe entregar 5V a la pistola.
 *
 *  ⚠️ ALIMENTACIÓN DE LA PISTOLA: el ESP32 debe darle 5V por el puerto OTG.
 *     Si la pistola NO enciende al conectarla, alimenta la placa por el pin 5V
 *     (módulo 18650) — en estas placas el 5V suele llegar también al puerto OTG.
 *     Si aún no enciende, usa un adaptador OTG con entrada de 5V externa.
 *
 *  ---------------------------------------------------------------------------
 *  LIBRERÍAS (Gestor de Librerías):
 *    - EspUsbHost          (TANAKA Masayuki)  -> USB host para leer la pistola
 *    - ArduinoJson         (Benoit Blanchon, v7+)
 *    - Adafruit SSD1306 + Adafruit GFX Library
 *
 *  CONFIG ARDUINO IDE:
 *    - Placa: ESP32S3 Dev Module · PSRAM: OPI PSRAM · Flash: 16MB
 *    - USB CDC On Boot: Disabled   (el USB nativo se usa como HOST, no CDC)
 *    - USB Mode: "USB-OTG (TinyUSB)"  (modo host por el puerto OTG)
 *    - Programa/depura por el puerto UART (wchusbserial), NO por el OTG.
 * ===========================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "EspUsbHost.h"

// ── CONFIG — EDITA ESTO ─────────────────────────────────────────────────────
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";
const char* API_BASE      = "http://192.168.0.10:8000";   // IP del POS + puerto

// ── OLED ────────────────────────────────────────────────────────────────────
#define PIN_SDA     47
#define PIN_SCL     21
#define OLED_ANCHO  128
#define OLED_ALTO   64
#define OLED_DIR    0x3C
Adafruit_SSD1306 oled(OLED_ANCHO, OLED_ALTO, &Wire, -1);
const unsigned long TIEMPO_RESULTADO_MS = 5000;

// ── Buffer del código que va tecleando la pistola ───────────────────────────
String lectura = "";
volatile bool hayCodigo = false;
String codigoListo = "";

// ── Pantalla OLED (helpers) ─────────────────────────────────────────────────
void imprimirAjustado(const String& texto, int cpl) {
  String palabra = ""; int col = 0;
  for (unsigned int i = 0; i <= texto.length(); i++) {
    char c = (i < texto.length()) ? texto[i] : ' ';
    if (c == ' ') {
      if (col + (int)palabra.length() > cpl) { oled.println(); col = 0; }
      oled.print(palabra); oled.print(' '); col += palabra.length() + 1; palabra = "";
    } else palabra += c;
  }
}
void mostrarMensaje(const String& l1, const String& l2 = "") {
  oled.clearDisplay(); oled.setTextSize(1); oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 8); oled.println(l1);
  if (l2.length()) { oled.println(); oled.println(l2); }
  oled.display();
}
void mostrarEspera() {
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1); oled.setCursor(0, 4); oled.println("Checador de precios");
  oled.drawLine(0, 16, 127, 16, SSD1306_WHITE);
  oled.setTextSize(2); oled.setCursor(0, 30); oled.println("Escanea");
  oled.display();
}
void mostrarProducto(const String& nombre, const String& talla, const String& color, float precio) {
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1); oled.setCursor(0, 0); imprimirAjustado(nombre, 21);
  oled.setCursor(0, 30);
  String d = ""; if (talla.length()) d += "T:" + talla + " "; if (color.length()) d += color;
  oled.println(d);
  oled.setTextSize(2); oled.setCursor(0, 44); oled.print("$"); oled.println(precio, 2);
  oled.display();
}
void mostrarNoEncontrado(const String& sku) {
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(2); oled.setCursor(0, 6); oled.println("No"); oled.println("encontrado");
  oled.setTextSize(1); oled.setCursor(0, 50); oled.print("Cod: "); oled.println(sku);
  oled.display();
}

// ── Lector USB (la pistola se comporta como teclado) ────────────────────────
EspUsbHost usb;

// ── WiFi ──────────────────────────────────────────────────────────────────
void conectarWiFi() {
  mostrarMensaje("Conectando WiFi...", String(WIFI_SSID));
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) { delay(300); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi OK. IP: %s\n", WiFi.localIP().toString().c_str());
    mostrarMensaje("WiFi conectado", WiFi.localIP().toString()); delay(1000);
  } else {
    mostrarMensaje("Sin WiFi", "Revisa SSID/clave"); delay(1500);
  }
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
  Serial.println("GET " + url);
  HTTPClient http;
  http.setConnectTimeout(4000); http.setTimeout(4000);
  http.begin(url);
  int code = http.GET();
  if (code == 200) {
    String cuerpo = http.getString();
    Serial.println(cuerpo);
    JsonDocument doc;
    if (deserializeJson(doc, cuerpo)) mostrarMensaje("Error de datos");
    else if (doc["encontrado"] | false)
      mostrarProducto(String((const char*)(doc["nombre"] | "")),
                      String((const char*)(doc["talla"]  | "")),
                      String((const char*)(doc["color"]  | "")),
                      doc["precio"] | 0.0);
    else mostrarNoEncontrado(sku);
  } else {
    mostrarMensaje("Error de servidor", "HTTP " + String(code));
  }
  http.end();
}

// ── Setup / Loop ────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("\n=== Checador: pistola USB + OLED ===");

  Wire.begin(PIN_SDA, PIN_SCL);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_DIR))
    Serial.println("OLED no encontrada (prueba 0x3D).");
  oled.clearDisplay(); oled.display();

  conectarWiFi();

  // Lector USB: distribución de teclado US y callback de tecla.
  usb.setKeyboardLayout(ESP_USB_HOST_KEYBOARD_LAYOUT_EN_US);
  usb.onKeyboard([](const EspUsbHostKeyboardEvent &event) {
    if (!event.pressed) return;                 // solo al presionar
    if (event.ascii == '\r' || event.ascii == '\n') {   // Enter = fin del código
      if (lectura.length() > 0) { codigoListo = lectura; hayCodigo = true; lectura = ""; }
    } else if (event.ascii >= 0x20 && event.ascii < 0x7F) {
      lectura += (char)event.ascii;
    }
  });
  if (!usb.begin()) {
    Serial.printf("usb.begin() fallo: %s\n", usb.lastErrorName());
    mostrarMensaje("Error USB host", "Revisa conexion");
  }

  mostrarEspera();
  Serial.println("Listo. Escanea con la pistola USB...");
}

void loop() {
  if (hayCodigo) {
    hayCodigo = false;
    String sku = codigoListo; sku.trim();
    if (sku.length() > 0) {
      Serial.println("Codigo: " + sku);
      consultar(sku);
      delay(TIEMPO_RESULTADO_MS);
      mostrarEspera();
    }
  }
  delay(1);   // deja respirar al host USB
}
