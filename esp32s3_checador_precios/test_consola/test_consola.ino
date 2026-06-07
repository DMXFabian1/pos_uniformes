/* ===========================================================================
 *  CHECADOR DE PRECIOS — PRUEBA POR CONSOLA (sin pantalla OLED)
 *  ESP32-S3 + cámara OV2640/OV3660
 * ===========================================================================
 *
 *  Para probar el checador ANTES de que llegue la pantalla OLED.
 *  Muestra TODO en el Monitor Serie. Solo necesitas la placa + WiFi
 *  (la cámara ya viene integrada). NO requiere OLED, botón ni buzzer.
 *
 *  Funcionamiento: escaneo CONTINUO. Apunta un QR (con el SKU) a la cámara
 *  y verás en consola el código leído y la respuesta de tu API.
 *
 *  ---------------------------------------------------------------------------
 *  LIBRERÍAS: ArduinoJson (v7+).  quirc ya viene incluido (carpeta src/).
 *
 *  CONFIG ARDUINO IDE (igual que el firmware real):
 *    - Driver CH343 instalado · Placa "ESP32S3 Dev Module"
 *    - PSRAM "OPI PSRAM" · Flash "16MB" · USB CDC On Boot "Disabled"
 *    - Sube por el puerto  /dev/cu.wchusbserial...
 *    - Abre el Monitor Serie a 115200 baud.
 * ===========================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#include "src/quirc.h"

// ── CONFIG — EDITA ESTO ─────────────────────────────────────────────────────
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";
const char* API_BASE      = "http://192.168.0.10:8000";   // IP del POS + puerto

// ── Pines de cámara (confirmados para esta placa) ───────────────────────────
#define PWDN_GPIO_NUM   -1
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM   15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5
#define Y9_GPIO_NUM     16
#define Y8_GPIO_NUM     17
#define Y7_GPIO_NUM     18
#define Y6_GPIO_NUM     12
#define Y5_GPIO_NUM     10
#define Y4_GPIO_NUM      8
#define Y3_GPIO_NUM      9
#define Y2_GPIO_NUM     11
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM   13

#define QR_ANCHO  320
#define QR_ALTO   240
struct quirc* qr = nullptr;

// Anti-repetición: no procesar el mismo SKU una y otra vez por segundo.
String ultimoSku = "";
unsigned long ultimoMs = 0;

// ── Cámara ──────────────────────────────────────────────────────────────────
bool iniciarCamara() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;   // 10MHz: evita overflow del buffer (EV-EOF-OVF)
  config.frame_size   = FRAMESIZE_QVGA;
  config.pixel_format = PIXFORMAT_GRAYSCALE;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.fb_count     = 2;                // doble buffer: la cámara no se satura mientras quirc procesa
  config.grab_mode    = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Fallo al iniciar la camara: 0x%x\n", err);
    return false;
  }
  return true;
}

// ── WiFi ──────────────────────────────────────────────────────────────────
void conectarWiFi() {
  Serial.printf("Conectando a WiFi '%s'", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) {
    delay(300); Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("\nWiFi OK. IP: %s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("\n** No se pudo conectar al WiFi (revisa SSID/clave) **");
}

// ── Lectura de QR ───────────────────────────────────────────────────────────
bool leerQR(String& salida) {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) return false;
  bool leido = false;
  int w, h;
  uint8_t* imagen = quirc_begin(qr, &w, &h);
  if ((int)fb->len >= w * h) {
    memcpy(imagen, fb->buf, w * h);
    quirc_end(qr);
    int n = quirc_count(qr);
    for (int i = 0; i < n && !leido; i++) {
      struct quirc_code code;
      struct quirc_data data;
      quirc_extract(qr, i, &code);
      if (quirc_decode(&code, &data) == 0) {
        salida = String((const char*)data.payload);
        salida.trim();
        leido = salida.length() > 0;
      }
    }
  }
  esp_camera_fb_return(fb);
  return leido;
}

// ── Consulta a la API e impresión en consola ────────────────────────────────
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
  Serial.println("\n\n=== CHECADOR DE PRECIOS — prueba por consola ===");

  conectarWiFi();

  if (!iniciarCamara()) {
    Serial.println("** ERROR de camara: revisa la placa **");
    while (true) delay(1000);
  }
  qr = quirc_new();
  if (!qr || quirc_resize(qr, QR_ANCHO, QR_ALTO) < 0) {
    Serial.println("** ERROR de memoria (quirc) **");
    while (true) delay(1000);
  }
  Serial.println("Listo. Apunta un codigo QR (con el SKU) a la camara...\n");
}

void loop() {
  String sku;
  if (leerQR(sku)) {
    // Evita repetir el mismo SKU si sigue frente a la cámara.
    if (sku != ultimoSku || millis() - ultimoMs > 3000) {
      ultimoSku = sku;
      ultimoMs = millis();
      Serial.println("QR leido: " + sku);
      consultar(sku);
      Serial.println();
    }
  }
  delay(50);
}
