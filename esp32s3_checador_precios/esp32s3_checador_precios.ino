/* ===========================================================================
 *  CHECADOR DE PRECIOS  —  ESP32-S3 (WROOM-1 N16R8) + cámara OV2640 u OV3660
 *  (placa "dual USB-C", tipo KLYCKIT / Freenove ESP32-S3-CAM clon)
 * ===========================================================================
 *
 *  NOTA cámara: funciona igual con OV2640 (2MP) u OV3660 (3MP). El driver
 *  esp_camera detecta el sensor automáticamente; no hay que cambiar nada.
 *
 *  Igual que la versión del ESP32-CAM AI-Thinker, pero adaptado al ESP32-S3:
 *    - Inicializa la cámara con los pines PROPIOS de esta placa (no AI-Thinker).
 *    - Decodifica el QR con la librería 'quirc' directamente (control total).
 *    - OLED y buzzer en pines LIBRES (en el S3 los 12/14/15 los usa la cámara).
 *    - Se programa por USB-C: NO necesita adaptador FTDI.
 *
 *  Flujo: pulsas el BOTÓN -> enciende LED -> lee QR -> beep -> GET
 *         /api/v1/precio/<sku> -> muestra nombre+precio en la OLED -> 5 s ->
 *         vuelve a la pantalla de espera.
 *
 * ---------------------------------------------------------------------------
 *  ⚠️ IMPORTANTE — ANTES DE NADA:
 *
 *  1) PINOUT DE CÁMARA: los #define de la sección [A] YA están confirmados
 *     contra el diagrama de pines de esta placa (coinciden todos). Los pines
 *     de OLED/buzzer [C] también se eligieron libres según ese diagrama.
 *
 *  2) Este sketch NO se pudo probar en hardware al escribirlo. Hay que
 *     compilarlo y flashearlo en la placa real y ajustar si hace falta.
 *
 * ---------------------------------------------------------------------------
 *  LIBRERÍAS A INSTALAR EN EL ARDUINO IDE (Gestor de Librerías):
 *    - "ArduinoJson"            por Benoit Blanchon   (v7+)
 *    - "Adafruit SSD1306"       por Adafruit
 *    - "Adafruit GFX Library"   por Adafruit
 *
 *  El decodificador de QR 'quirc' YA viene incluido en este sketch (carpeta
 *  src/), no necesitas instalar ninguna librería de QR. (quirc: Daniel Beer,
 *  licencia ISC. Verificado: compila con esp32 core 3.3.8.)
 *
 *  'esp_camera', WiFi, HTTPClient y Wire vienen con el paquete de placas esp32.
 *
 * ---------------------------------------------------------------------------
 *  CONFIGURACIÓN DEL ARDUINO IDE:
 *    - DRIVER:             instala primero el driver CH343 en la PC (esta placa
 *                          usa el chip CH343 USB-a-serial; sin él no se reconoce).
 *    - Placa:              "ESP32S3 Dev Module"
 *    - PSRAM:              "OPI PSRAM"            (¡obligatorio!)
 *    - Flash Size:         "16MB (128Mb)"
 *    - USB CDC On Boot:    "Disabled"  (la placa carga por el chip CH343; con
 *                          Disabled el Serial sale por ese puerto USB-to-serial)
 *    - Partition Scheme:   "16M Flash (3MB APP/9.9MB FATFS)" o "Huge APP"
 *    - Para subir: usa el puerto USB-C rotulado "USB to serial" (CH343).
 *      Si no entra en modo descarga: mantén BOOT, pulsa y suelta RST, suelta BOOT.
 *
 * ---------------------------------------------------------------------------
 *  CONEXIONES (pines LIBRES confirmados con el diagrama de la placa):
 *    OLED SSD1306 (I2C):   SDA -> GPIO 47 ,  SCL -> GPIO 21 ,  VCC 3V3 , GND
 *    Buzzer (activo):      (+) -> GPIO 14 ,  (-) -> GND
 *    Botón "escanear":     GPIO 1  <-> GND  (usa pull-up interno)
 *    LED iluminación:      GPIO 41 -> LED -> R 220Ω -> GND
 *
 *  (47 y 21 están juntos en el header y no tienen función especial; 14, 1 y 41
 *   son libres. Se EVITARON: GPIO2 = "LED ON", GPIO42 = JTAG/MTMS, GPIO48 = LED
 *   RGB WS2812, los pines de cámara, y 19/20 = USB nativo.)
 *
 *  ALIMENTACIÓN: USB-C / power bank, o pilas AA NiMH con módulo step-up a 5V
 *  hacia el pin 5V (usa UNA sola fuente a la vez).
 * ===========================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "esp_camera.h"
#include "src/quirc.h"      // quirc viene incluido en este sketch (carpeta src/)
#include "esp_sleep.h"      // sueño profundo (deep sleep)
#include "driver/rtc_io.h"  // pull-up del botón durante el sueño

// ===========================================================================
// [A] PINOUT DE LA CÁMARA  —  ✅ CONFIRMADO con el diagrama de TU placa
//     (coincide pin por pin con el pinout ESP32-S3-WROOM CAM enviado)
// ===========================================================================
#define PWDN_GPIO_NUM   -1
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM   15
#define SIOD_GPIO_NUM    4   // SDA del bus de la cámara (SCCB) — NO es el de la OLED
#define SIOC_GPIO_NUM    5   // SCL del bus de la cámara (SCCB)
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

// ===========================================================================
// [B] CONFIGURACIÓN — EDITA ESTOS VALORES
// ===========================================================================
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";

// IP del servidor del POS en tu red local + puerto.
const char* API_BASE = "http://192.168.0.10:8000";
// El firmware arma:  API_BASE + "/api/v1/precio/" + <sku>

// MODO DE ENERGÍA:
//   true  -> SUEÑO PROFUNDO (batería): duerme y despierta al pulsar el botón;
//            escanea una vez y vuelve a dormir. Máxima duración de pilas.
//            (Cada escaneo tarda ~3-4 s extra porque reconecta WiFi y cámara.)
//   false -> SIEMPRE ENCENDIDO (USB): responde al instante, gasta más.
const bool USAR_DEEP_SLEEP = true;

// ===========================================================================
// [C] PINES OLED / BUZZER / BOTÓN / LED  (pines libres confirmados)
// ===========================================================================
#define PIN_SDA     47    // I2C SDA de la OLED (GPIO47, libre)
#define PIN_SCL     21    // I2C SCL de la OLED (GPIO21, libre)
#define PIN_BUZZER  14    // Buzzer activo      (GPIO14, libre)
#define PIN_BOTON    1    // Botón "escanear"   (GPIO1 -> a GND; pull-up interno)
#define PIN_LED     41    // LED de iluminación (GPIO41 -> LED + resistencia ~220Ω -> GND)

// Cuánto tiempo busca un QR tras pulsar el botón (ms) antes de rendirse.
const unsigned long VENTANA_ESCANEO_MS = 6000;

#define OLED_ANCHO  128
#define OLED_ALTO   64
#define OLED_DIR    0x3C  // dirección I2C típica (o 0x3D)

Adafruit_SSD1306 oled(OLED_ANCHO, OLED_ALTO, &Wire, -1);

// Resolución de captura para leer el QR. QVGA (320x240) en escala de grises:
// suficiente para QR y ligero para quirc.
#define QR_ANCHO  320
#define QR_ALTO   240

struct quirc* qr = nullptr;

const unsigned long TIEMPO_RESULTADO_MS = 5000;

// ===========================================================================
//  PANTALLA OLED  (idénticas a la versión AI-Thinker)
// ===========================================================================
void imprimirAjustado(const String& texto, int caracteresPorLinea) {
  String palabra = "";
  int columnaActual = 0;
  for (unsigned int i = 0; i <= texto.length(); i++) {
    char c = (i < texto.length()) ? texto[i] : ' ';
    if (c == ' ') {
      if (columnaActual + (int)palabra.length() > caracteresPorLinea) {
        oled.println();
        columnaActual = 0;
      }
      oled.print(palabra);
      oled.print(' ');
      columnaActual += palabra.length() + 1;
      palabra = "";
    } else {
      palabra += c;
    }
  }
}

void mostrarMensaje(const String& linea1, const String& linea2 = "") {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 8);
  oled.println(linea1);
  if (linea2.length() > 0) { oled.println(); oled.println(linea2); }
  oled.display();
}

void mostrarEspera() {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 4);
  oled.println("Checador de precios");
  oled.drawLine(0, 16, 127, 16, SSD1306_WHITE);
  oled.setTextSize(2);
  oled.setCursor(0, 24); oled.println("Pulsa el");
  oled.setCursor(0, 44); oled.println("boton");
  oled.display();
}

void mostrarProducto(const String& nombre, const String& talla,
                     const String& color, float precio) {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  imprimirAjustado(nombre, 21);
  oled.setCursor(0, 30);
  String detalle = "";
  if (talla.length() > 0) detalle += "T:" + talla + " ";
  if (color.length() > 0) detalle += color;
  oled.println(detalle);
  oled.setTextSize(2);
  oled.setCursor(0, 44);
  oled.print("$"); oled.println(precio, 2);
  oled.display();
}

void mostrarNoEncontrado(const String& sku) {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(2);
  oled.setCursor(0, 6);
  oled.println("No"); oled.println("encontrado");
  oled.setTextSize(1);
  oled.setCursor(0, 50);
  oled.print("SKU: "); oled.println(sku);
  oled.display();
}

// ===========================================================================
//  BUZZER
// ===========================================================================
// Buzzer ACTIVO. Si el tuyo es PASIVO usa:  tone(PIN_BUZZER, 2000, 150);
void pitar() {
  digitalWrite(PIN_BUZZER, HIGH);
  delay(120);
  digitalWrite(PIN_BUZZER, LOW);
}

// ===========================================================================
//  WIFI
// ===========================================================================
void conectarWiFi() {
  mostrarMensaje("Conectando a WiFi...", String(WIFI_SSID));
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(300); Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi OK. IP: %s\n", WiFi.localIP().toString().c_str());
    mostrarMensaje("WiFi conectado", WiFi.localIP().toString());
    delay(1200);
  } else {
    Serial.println("\nSin WiFi.");
    mostrarMensaje("Sin WiFi", "Revisa SSID/clave");
    delay(2000);
  }
}

// ===========================================================================
//  CÁMARA  (esp_camera con los pines de la sección [A])
// ===========================================================================
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
  config.frame_size   = FRAMESIZE_QVGA;       // 320x240
  config.pixel_format = PIXFORMAT_GRAYSCALE;  // ideal para quirc
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

// ===========================================================================
//  CONSULTA A LA API
// ===========================================================================
String urlEncode(const String& s) {
  String salida = ""; char buf[4];
  for (unsigned int i = 0; i < s.length(); i++) {
    char c = s[i];
    if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') salida += c;
    else { sprintf(buf, "%%%02X", (unsigned char)c); salida += buf; }
  }
  return salida;
}

void consultarYMostrar(const String& sku) {
  if (WiFi.status() != WL_CONNECTED) { conectarWiFi(); return; }

  String url = String(API_BASE) + "/api/v1/precio/" + urlEncode(sku);
  Serial.println("GET " + url);

  HTTPClient http;
  http.setConnectTimeout(4000);
  http.setTimeout(4000);
  http.begin(url);
  int codigoHTTP = http.GET();

  if (codigoHTTP == 200) {
    String cuerpo = http.getString();
    Serial.println(cuerpo);
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, cuerpo);
    if (err) {
      mostrarMensaje("Error de datos");
    } else if (doc["encontrado"] | false) {
      String nombre = String((const char*)(doc["nombre"] | ""));
      String talla  = String((const char*)(doc["talla"]  | ""));
      String color  = String((const char*)(doc["color"]  | ""));
      float precio  = doc["precio"] | 0.0;
      mostrarProducto(nombre, talla, color, precio);
    } else {
      mostrarNoEncontrado(sku);
    }
  } else {
    Serial.printf("HTTP %d\n", codigoHTTP);
    mostrarMensaje("Error de servidor", "HTTP " + String(codigoHTTP));
  }
  http.end();
}

// ===========================================================================
//  LECTURA DE QR con quirc
// ===========================================================================
// Captura un cuadro de la cámara, lo pasa por quirc y, si hay un QR válido,
// devuelve su contenido en 'salida'. Devuelve true si leyó algo.
bool leerQR(String& salida) {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) return false;

  bool leido = false;
  int w, h;
  uint8_t* imagen = quirc_begin(qr, &w, &h);   // buffer interno de quirc (w*h)

  // Copiamos el cuadro en escala de grises (1 byte por pixel) a quirc.
  if ((int)fb->len >= w * h) {
    memcpy(imagen, fb->buf, w * h);
    quirc_end(qr);

    int n = quirc_count(qr);
    for (int i = 0; i < n && !leido; i++) {
      struct quirc_code code;
      struct quirc_data data;
      quirc_extract(qr, i, &code);
      if (quirc_decode(&code, &data) == 0) {   // 0 = sin error
        salida = String((const char*)data.payload);
        salida.trim();
        leido = salida.length() > 0;
      }
    }
  }

  esp_camera_fb_return(fb);
  return leido;
}

// ===========================================================================
//  ARRANQUE DE SUBSISTEMAS (WiFi + cámara + quirc)
// ===========================================================================
// Conecta WiFi e inicializa cámara y quirc. Es lo "caro" en energía y tiempo;
// en modo batería solo se ejecuta cuando el botón despierta la placa.
bool sistemaListo = false;
void prepararSistema() {
  if (sistemaListo) return;

  conectarWiFi();

  if (!iniciarCamara()) {
    mostrarMensaje("Error de camara", "Revisa pines [A]");
    while (true) delay(1000);   // sin cámara no hay nada que hacer
  }

  qr = quirc_new();
  if (!qr || quirc_resize(qr, QR_ANCHO, QR_ALTO) < 0) {
    mostrarMensaje("Error de memoria", "quirc");
    while (true) delay(1000);
  }

  sistemaListo = true;
  Serial.println("Lector de QR (quirc) listo.");
}

// ===========================================================================
//  SUEÑO PROFUNDO  (se despierta pulsando el botón)
// ===========================================================================
void irADormir() {
  mostrarMensaje("En reposo.", "Pulsa el boton");
  delay(1000);
  oled.clearDisplay(); oled.display();   // apaga los pixeles (ahorra)
  digitalWrite(PIN_LED, LOW);

  // El botón (GPIO1, que es RTC) despierta la placa cuando se pone en LOW.
  // Mantenemos su pull-up activo durante el sueño para que en reposo lea HIGH.
  rtc_gpio_pullup_en((gpio_num_t)PIN_BOTON);
  rtc_gpio_pulldown_dis((gpio_num_t)PIN_BOTON);
  esp_sleep_enable_ext1_wakeup(1ULL << PIN_BOTON, ESP_EXT1_WAKEUP_ANY_LOW);

  Serial.println("Durmiendo. Pulsa el boton para despertar.");
  Serial.flush();
  esp_deep_sleep_start();   // NO regresa: al despertar se reinicia setup()
}

// ===========================================================================
//  SETUP
// ===========================================================================
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Botón con resistencia pull-up interna: en reposo lee HIGH, pulsado LOW.
  pinMode(PIN_BOTON, INPUT_PULLUP);

  // LED de iluminación, apagado al inicio.
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  // OLED (bus I2C en pines propios, distinto al de la cámara).
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_DIR)) {
    Serial.println("No se encontro la OLED. Revisa cableado/direccion.");
  }
  oled.clearDisplay(); oled.display();

  if (USAR_DEEP_SLEEP) {
    // Modo batería: cada arranque viene de un botonazo (o del encendido).
    esp_sleep_wakeup_cause_t causa = esp_sleep_get_wakeup_cause();
    if (causa == ESP_SLEEP_WAKEUP_EXT1) {
      // Despertó por el botón -> prepara todo y escanea una vez.
      prepararSistema();
      escanearUnaVez();
    } else {
      // Primer encendido normal -> saluda y duerme esperando el botón.
      mostrarMensaje("Listo.", "Pulsa el boton");
      delay(1500);
    }
    irADormir();   // NO regresa
  } else {
    // Modo siempre encendido (alimentado por USB).
    prepararSistema();
    mostrarEspera();
  }
}

// ===========================================================================
//  ESCANEO BAJO DEMANDA (al pulsar el botón)
// ===========================================================================
// Enciende el LED, busca un QR durante VENTANA_ESCANEO_MS y, si lo encuentra,
// consulta el precio y lo muestra. Si no, avisa. Apaga el LED al terminar.
void escanearUnaVez() {
  mostrarMensaje("Escaneando...", "Acerca el codigo QR");
  digitalWrite(PIN_LED, HIGH);          // enciende la luz para la cámara

  String sku;
  bool leido = false;
  unsigned long inicio = millis();
  while (millis() - inicio < VENTANA_ESCANEO_MS) {
    if (leerQR(sku)) { leido = true; break; }
    delay(50);
  }

  digitalWrite(PIN_LED, LOW);           // apaga la luz

  if (leido) {
    Serial.println("QR leido: " + sku);
    pitar();
    consultarYMostrar(sku);
  } else {
    Serial.println("No se detecto QR en la ventana.");
    mostrarMensaje("No se detecto", "ningun codigo QR");
  }

  delay(TIEMPO_RESULTADO_MS);           // deja ver el resultado 5 s
  // No volvemos a "espera" aquí: lo decide quien llama (dormir o mostrarEspera).
}

// ===========================================================================
//  LOOP
// ===========================================================================
void loop() {
  // En modo SUEÑO PROFUNDO nunca se llega aquí (setup() duerme la placa).
  if (USAR_DEEP_SLEEP) return;

  // --- Modo SIEMPRE ENCENDIDO (alimentado por USB) ---
  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
    mostrarEspera();
  }

  // Espera a que se pulse el botón (lectura LOW por el pull-up).
  if (digitalRead(PIN_BOTON) == LOW) {
    delay(30);                          // antirrebote simple
    if (digitalRead(PIN_BOTON) == LOW) {
      escanearUnaVez();
      mostrarEspera();
      // Espera a que se suelte el botón para no re-disparar.
      while (digitalRead(PIN_BOTON) == LOW) delay(10);
    }
  }

  delay(20);
}
