/* ===========================================================================
 *  VER LA CÁMARA — transmisión de video al navegador (ESP32-S3)
 * ===========================================================================
 *
 *  Sirve para VER en vivo lo que capta la cámara, desde tu celular o compu,
 *  abriendo la IP de la placa en un navegador. Útil para ajustar enfoque,
 *  luz y distancia antes de leer QR con el checador.
 *
 *  Cómo usar:
 *    1. Edita tu WiFi abajo.
 *    2. Sube este sketch (misma config: ESP32S3 Dev Module, OPI PSRAM, 16MB,
 *       USB CDC Disabled; sube por el puerto wchusbserial).
 *    3. Abre el Monitor Serie (115200): te dirá la IP, ej. http://192.168.0.9
 *    4. Abre ESA dirección en el navegador de tu cel/compu (misma red WiFi).
 *       Verás el video en vivo de la cámara.
 *
 *  NO necesita librerías extra (todo viene con el paquete esp32).
 *  Para volver a leer QR, vuelve a subir el sketch del checador.
 * ===========================================================================
 */

#include <WiFi.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_timer.h"
#include "img_converters.h"   // convertir el cuadro a JPEG por software

// ── CONFIG — EDITA ESTO ─────────────────────────────────────────────────────
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";

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

httpd_handle_t servidor = NULL;

// ── Cámara en modo JPEG (para transmitir) ───────────────────────────────────
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
  config.xclk_freq_hz = 10000000;
  config.frame_size   = FRAMESIZE_QVGA;       // 320x240 (sensor GC2145, sin JPEG HW)
  config.pixel_format = PIXFORMAT_GRAYSCALE;  // grises: lo que SÍ soporta el sensor
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.fb_count     = 2;
  config.grab_mode    = CAMERA_GRAB_LATEST;
  config.jpeg_quality = 12;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Fallo al iniciar la camara: 0x%x\n", err);
    return false;
  }
  return true;
}

// ── Transmisión MJPEG ───────────────────────────────────────────────────────
#define PARTE_LIMITE "frameboundary"
static const char* STREAM_TIPO = "multipart/x-mixed-replace;boundary=" PARTE_LIMITE;
static const char* STREAM_SEP  = "\r\n--" PARTE_LIMITE "\r\n";
static const char* STREAM_CAB  = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static esp_err_t stream_handler(httpd_req_t* req) {
  esp_err_t res = httpd_resp_set_type(req, STREAM_TIPO);
  if (res != ESP_OK) return res;

  char cab[64];
  while (true) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) { res = ESP_FAIL; break; }

    // El sensor no da JPEG; convertimos el cuadro (grises) a JPEG por software.
    uint8_t* jpg = NULL;
    size_t jpg_len = 0;
    bool ok = frame2jpg(fb, 80, &jpg, &jpg_len);
    esp_camera_fb_return(fb);
    if (!ok) { res = ESP_FAIL; break; }

    res = httpd_resp_send_chunk(req, STREAM_SEP, strlen(STREAM_SEP));
    if (res == ESP_OK) {
      size_t n = snprintf(cab, sizeof(cab), STREAM_CAB, jpg_len);
      res = httpd_resp_send_chunk(req, cab, n);
    }
    if (res == ESP_OK)
      res = httpd_resp_send_chunk(req, (const char*)jpg, jpg_len);

    free(jpg);
    if (res != ESP_OK) break;   // el navegador cerró la conexión
  }
  return res;
}

// Página HTML que muestra el video con una etiqueta <img> (más compatible
// con Safari/Brave que el stream "pelón").
static esp_err_t index_handler(httpd_req_t* req) {
  httpd_resp_set_type(req, "text/html");
  const char* html =
    "<!DOCTYPE html><html><head><meta name='viewport' "
    "content='width=device-width,initial-scale=1'><title>Camara ESP32</title></head>"
    "<body style='margin:0;background:#000;text-align:center'>"
    "<p style='color:#fff;font-family:sans-serif'>Camara ESP32-S3 (grises)</p>"
    "<img src='/stream' style='width:100%;max-width:480px'/>"
    "</body></html>";
  return httpd_resp_send(req, html, strlen(html));
}

void iniciarServidor() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.max_uri_handlers = 4;
  httpd_uri_t uri_index  = { .uri = "/",       .method = HTTP_GET, .handler = index_handler,  .user_ctx = NULL };
  httpd_uri_t uri_stream = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL };
  if (httpd_start(&servidor, &config) == ESP_OK) {
    httpd_register_uri_handler(servidor, &uri_index);
    httpd_register_uri_handler(servidor, &uri_stream);
  }
}

// ── WiFi ──────────────────────────────────────────────────────────────────
void conectarWiFi() {
  Serial.printf("Conectando a WiFi '%s'", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 20000) { delay(300); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("\nWiFi OK. Abre en tu navegador:  http://%s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("\n** No se pudo conectar al WiFi **");
}

void setup() {
  Serial.begin(115200);
  delay(600);
  Serial.println("\n\n=== VER CAMARA (stream al navegador) ===");
  if (!iniciarCamara()) { Serial.println("** ERROR de camara **"); while (true) delay(1000); }
  conectarWiFi();
  iniciarServidor();
  Serial.println("Servidor listo. Abre la direccion http://<IP> de arriba.");
}

void loop() {
  delay(1000);   // todo el trabajo lo hace el servidor web
}
