/* ===========================================================================
 *  CHECADOR DE PRECIOS  —  ESP32-CAM (AI-Thinker, cámara OV2640)
 * ===========================================================================
 *
 *  Qué hace:
 *    1. Se conecta a tu red WiFi.
 *    2. Lee códigos QR de forma continua con la cámara.
 *    3. Al detectar un QR, hace un GET a la API del POS:
 *           GET http://<IP_SERVIDOR>:8000/api/v1/precio/<sku>
 *    4. Parsea el JSON de respuesta con ArduinoJson.
 *    5. Muestra NOMBRE y PRECIO en una pantalla OLED SSD1306 128x64.
 *    6. Suena un buzzer al leer el QR.
 *    7. Si el producto no existe, muestra "No encontrado".
 *    8. Tras 5 segundos vuelve a la pantalla de espera.
 *
 *  El QR debe contener el SKU del producto (campo variante.sku de la BD).
 *
 * ---------------------------------------------------------------------------
 *  LIBRERÍAS A INSTALAR EN EL ARDUINO IDE (Gestor de Librerías):
 *    - "ArduinoJson"            por Benoit Blanchon   (v7 o superior)
 *    - "Adafruit SSD1306"       por Adafruit
 *    - "Adafruit GFX Library"   por Adafruit
 *    - "ESP32QRCodeReader"      por Álvaro Viebrantz
 *          (si no aparece en el gestor, instálala desde:
 *           https://github.com/alvarowolfx/ESP32QRCodeReader  ->  Sketch >
 *           Incluir librería > Añadir biblioteca .ZIP)
 *
 *  Las librerías WiFi, HTTPClient, Wire y esp_camera vienen incluidas con el
 *  paquete de placas "esp32" de Espressif (Gestor de Tarjetas).
 *
 * ---------------------------------------------------------------------------
 *  CONFIGURACIÓN DEL ARDUINO IDE:
 *    - Placa:           "AI Thinker ESP32-CAM"
 *    - PSRAM:           Enabled   (¡obligatorio! el lector de QR la necesita)
 *    - Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)" recomendado
 *    - Para subir: usa un adaptador FTDI/USB-TTL a 5V, conecta GPIO0 a GND
 *      antes de subir y pulsa RESET. Quita GPIO0-GND al terminar.
 *
 * ---------------------------------------------------------------------------
 *  CONEXIONES (módulo AI-Thinker):
 *    OLED SSD1306 (I2C):   SDA -> GPIO 15 ,  SCL -> GPIO 14 ,  VCC 3V3 , GND
 *    Buzzer:               (+) -> GPIO 12 ,  (-) -> GND
 *
 *  NOTA sobre los pines: en el ESP32-CAM los GPIO 12, 14 y 15 son los pines de
 *  la tarjeta microSD. Quedan libres SOLO si NO usas tarjeta microSD (este
 *  proyecto no la usa). Además, el GPIO 12 es un "strapping pin": debe estar en
 *  BAJO al encender. Un buzzer ACTIVO (que en reposo queda en LOW) es seguro.
 * ===========================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "ESP32QRCodeReader.h"

// ---------------------------------------------------------------------------
// 1) CONFIGURACIÓN — EDITA ESTOS VALORES
// ---------------------------------------------------------------------------

// Datos de tu red WiFi
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";

// Dirección de la API del POS en tu red local (IP del servidor + puerto).
// Ejemplo: si el POS corre en la PC 192.168.0.10, deja:
const char* API_BASE = "http://192.168.0.10:8000";
// El firmware armará la URL:  API_BASE + "/api/v1/precio/" + <sku>

// ---------------------------------------------------------------------------
// 2) PINES Y PANTALLA
// ---------------------------------------------------------------------------

#define PIN_SDA      15      // I2C SDA de la OLED
#define PIN_SCL      14      // I2C SCL de la OLED
#define PIN_BUZZER   12      // Buzzer

#define OLED_ANCHO   128
#define OLED_ALTO    64
#define OLED_DIR     0x3C    // Dirección I2C típica de la SSD1306 (o 0x3D)

// La OLED comparte el bus Wire (lo inicializamos con pines personalizados).
Adafruit_SSD1306 oled(OLED_ANCHO, OLED_ALTO, &Wire, -1);

// Lector de QR sobre la cámara del módulo AI-Thinker.
ESP32QRCodeReader lector(CAMERA_MODEL_AI_THINKER);

// Tiempo que se muestra el resultado antes de volver a "espera" (ms).
const unsigned long TIEMPO_RESULTADO_MS = 5000;

// ===========================================================================
//  FUNCIONES DE LA PANTALLA OLED
// ===========================================================================

// Imprime texto largo con salto de línea por palabras (word-wrap) a partir de
// la posición actual del cursor. Con la fuente por defecto (tamaño 1) caben
// ~21 caracteres por línea.
void imprimirAjustado(const String& texto, int caracteresPorLinea) {
  String palabra = "";
  int columnaActual = 0;
  for (unsigned int i = 0; i <= texto.length(); i++) {
    char c = (i < texto.length()) ? texto[i] : ' ';
    if (c == ' ') {
      // ¿Cabe la palabra en la línea actual?
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

// Mensaje simple centrado verticalmente (para avisos del sistema).
void mostrarMensaje(const String& linea1, const String& linea2 = "") {
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oled.setCursor(0, 8);
  oled.println(linea1);
  if (linea2.length() > 0) {
    oled.println();
    oled.println(linea2);
  }
  oled.display();
}

// Pantalla de espera: invita a escanear.
void mostrarEspera() {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 4);
  oled.println("Checador de precios");
  oled.drawLine(0, 16, 127, 16, SSD1306_WHITE);
  oled.setTextSize(2);
  oled.setCursor(0, 26);
  oled.println("Escanea");
  oled.setCursor(0, 46);
  oled.println("un QR");
  oled.display();
}

// Muestra el producto encontrado: nombre (ajustado), talla/color y precio grande.
void mostrarProducto(const String& nombre, const String& talla,
                     const String& color, float precio) {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);

  // Nombre del producto (puede ocupar 1-3 líneas).
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  imprimirAjustado(nombre, 21);

  // Talla / color en una línea.
  oled.setCursor(0, 30);
  String detalle = "";
  if (talla.length() > 0) detalle += "T:" + talla + " ";
  if (color.length() > 0) detalle += color;
  oled.println(detalle);

  // Precio en grande, abajo.
  oled.setTextSize(2);
  oled.setCursor(0, 44);
  oled.print("$");
  oled.println(precio, 2);   // 2 decimales

  oled.display();
}

// Pantalla de "No encontrado".
void mostrarNoEncontrado(const String& sku) {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(2);
  oled.setCursor(0, 6);
  oled.println("No");
  oled.println("encontrado");
  oled.setTextSize(1);
  oled.setCursor(0, 50);
  oled.print("SKU: ");
  oled.println(sku);
  oled.display();
}

// ===========================================================================
//  BUZZER
// ===========================================================================

// Pitido corto. Pensado para un buzzer ACTIVO (trae su propio oscilador).
// Si tu buzzer es PASIVO, sustituye por:  tone(PIN_BUZZER, 2000, 150);
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

  // Esperamos hasta 20 segundos a que conecte.
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(300);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi conectado. IP: ");
    Serial.println(WiFi.localIP());
    mostrarMensaje("WiFi conectado", WiFi.localIP().toString());
    delay(1200);
  } else {
    Serial.println("\nNo se pudo conectar al WiFi.");
    mostrarMensaje("Sin WiFi", "Revisa SSID/clave");
    delay(2000);
  }
}

// ===========================================================================
//  CONSULTA A LA API
// ===========================================================================

// Codifica caracteres no seguros para URL (espacios, /, etc.).
String urlEncode(const String& s) {
  String salida = "";
  char buf[4];
  for (unsigned int i = 0; i < s.length(); i++) {
    char c = s[i];
    if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
      salida += c;
    } else {
      sprintf(buf, "%%%02X", (unsigned char)c);
      salida += buf;
    }
  }
  return salida;
}

// Consulta el SKU en la API y muestra el resultado en la OLED.
void consultarYMostrar(const String& sku) {
  if (WiFi.status() != WL_CONNECTED) {
    mostrarMensaje("Sin conexion WiFi");
    conectarWiFi();
    return;
  }

  String url = String(API_BASE) + "/api/v1/precio/" + urlEncode(sku);
  Serial.print("GET ");
  Serial.println(url);

  HTTPClient http;
  http.setConnectTimeout(4000);   // 4 s para conectar
  http.setTimeout(4000);          // 4 s para respuesta
  http.begin(url);

  int codigoHTTP = http.GET();

  if (codigoHTTP == 200) {
    String cuerpo = http.getString();
    Serial.println(cuerpo);

    // Parseo del JSON. JsonDocument es de ArduinoJson v7.
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, cuerpo);

    if (err) {
      Serial.print("Error JSON: ");
      Serial.println(err.c_str());
      mostrarMensaje("Error de datos");
    } else {
      bool encontrado = doc["encontrado"] | false;
      if (encontrado) {
        String nombre = String((const char*)(doc["nombre"] | ""));
        String talla  = String((const char*)(doc["talla"]  | ""));
        String color  = String((const char*)(doc["color"]  | ""));
        float precio  = doc["precio"] | 0.0;
        mostrarProducto(nombre, talla, color, precio);
      } else {
        mostrarNoEncontrado(sku);
      }
    }
  } else {
    // Error de red o del servidor.
    Serial.print("HTTP ");
    Serial.println(codigoHTTP);
    mostrarMensaje("Error de servidor", "HTTP " + String(codigoHTTP));
  }

  http.end();
}

// ===========================================================================
//  SETUP
// ===========================================================================

void setup() {
  Serial.begin(115200);
  delay(300);

  // Buzzer: salida y en reposo (LOW). Importante por ser GPIO12 strapping pin.
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Inicializa el bus I2C con los pines indicados y arranca la OLED.
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_DIR)) {
    Serial.println("No se encontro la OLED SSD1306. Revisa el cableado/direccion.");
    // Seguimos de todos modos; el sistema funciona aunque la OLED falle.
  }
  oled.clearDisplay();
  oled.display();

  // Conexión WiFi.
  conectarWiFi();

  // Arranca la cámara y el decodificador de QR (corre en el núcleo 1).
  lector.setup();
  lector.beginOnCore(1);
  Serial.println("Lector de QR listo.");

  mostrarEspera();
}

// ===========================================================================
//  LOOP
// ===========================================================================

void loop() {
  // Reconecta el WiFi si se cayó.
  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
    mostrarEspera();
  }

  // Estructura donde el lector deja el QR decodificado.
  struct QRCodeData datosQR;

  // receiveQrCode espera hasta 100 ms por un nuevo código.
  if (lector.receiveQrCode(&datosQR, 100)) {
    if (datosQR.valid) {
      // El contenido del QR es el SKU.
      String sku = String((const char*)datosQR.payload);
      sku.trim();
      Serial.print("QR leido: ");
      Serial.println(sku);

      if (sku.length() > 0) {
        pitar();                 // beep al leer
        consultarYMostrar(sku);  // consulta API y muestra
        delay(TIEMPO_RESULTADO_MS);  // mantiene el resultado 5 s
        mostrarEspera();             // vuelve a la pantalla de espera
      }
    }
  }
}
