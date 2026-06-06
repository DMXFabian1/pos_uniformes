/* ===========================================================================
 *  DEMO para WOKWI — Checador de precios ESP32-S3 (vista previa de la interfaz)
 * ===========================================================================
 *
 *  Esta NO es la versión real: es una demo para el simulador Wokwi, donde la
 *  cámara/QR y la API local NO se pueden simular. Aquí:
 *
 *    - El BOTÓN hace de "escáner": cada pulsación simula leer un SKU de prueba.
 *    - En vez de llamar a la API por red, una función local devuelve el MISMO
 *      JSON que daría /api/v1/precio/{sku}, y se parsea con ArduinoJson igual
 *      que en el firmware real.
 *    - La OLED, el buzzer y el LED funcionan idénticos al aparato real, para
 *      previsualizar las pantallas, el beep y la luz antes de soldar.
 *
 *  El firmware REAL (con cámara, quirc, WiFi y deep sleep) está en
 *  ../esp32s3_checador_precios/esp32s3_checador_precios.ino
 *
 *  Cómo correrlo: ver README.md de esta carpeta.
 * ===========================================================================
 */

#include <Wire.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// Mismos pines que el aparato real.
#define PIN_SDA     47
#define PIN_SCL     21
#define PIN_BUZZER  14
#define PIN_BOTON    1
#define PIN_LED     41

#define OLED_ANCHO  128
#define OLED_ALTO   64
#define OLED_DIR    0x3C

Adafruit_SSD1306 oled(OLED_ANCHO, OLED_ALTO, &Wire, -1);
const unsigned long TIEMPO_RESULTADO_MS = 4000;

// ── "Catálogo" simulado (hace de cuenta que es tu base de datos) ────────────
struct ProductoDemo {
  const char* sku; const char* nombre; const char* talla; const char* color; float precio;
};
ProductoDemo CAT[] = {
  {"JUMP-6",  "Jumper Primaria Benito Juarez", "6",  "Azul Marino", 350.00},
  {"PLAY-M",  "Playera Polo Blanca",           "M",  "Blanco",      120.50},
  {"PANT-28", "Pantalon Escolar Gris",         "28", "Gris",        289.90},
};
const int N_CAT = sizeof(CAT) / sizeof(CAT[0]);

// SKUs que se "escanean" en orden al pulsar el botón (el último NO existe,
// para mostrar también la pantalla de "No encontrado").
const char* SKUS_DEMO[] = {"JUMP-6", "PLAY-M", "PANT-28", "NOEXISTE"};
const int N_SKUS = sizeof(SKUS_DEMO) / sizeof(SKUS_DEMO[0]);
int idxDemo = 0;

// Devuelve el MISMO JSON que /api/v1/precio/{sku}.
String respuestaSimulada(const String& sku) {
  JsonDocument d;
  for (int i = 0; i < N_CAT; i++) {
    if (sku.equalsIgnoreCase(CAT[i].sku)) {
      d["encontrado"] = true;
      d["sku"] = CAT[i].sku;
      d["nombre"] = CAT[i].nombre;
      d["talla"] = CAT[i].talla;
      d["color"] = CAT[i].color;
      d["precio"] = CAT[i].precio;
      String out; serializeJson(d, out); return out;
    }
  }
  d["encontrado"] = false;
  d["sku"] = sku;
  String out; serializeJson(d, out); return out;
}

// ── Pantalla OLED (idénticas al firmware real) ──────────────────────────────
void imprimirAjustado(const String& texto, int caracteresPorLinea) {
  String palabra = ""; int columnaActual = 0;
  for (unsigned int i = 0; i <= texto.length(); i++) {
    char c = (i < texto.length()) ? texto[i] : ' ';
    if (c == ' ') {
      if (columnaActual + (int)palabra.length() > caracteresPorLinea) { oled.println(); columnaActual = 0; }
      oled.print(palabra); oled.print(' '); columnaActual += palabra.length() + 1; palabra = "";
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
  oled.setTextSize(2);
  oled.setCursor(0, 24); oled.println("Pulsa el");
  oled.setCursor(0, 44); oled.println("boton");
  oled.display();
}

void mostrarProducto(const String& nombre, const String& talla, const String& color, float precio) {
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1); oled.setCursor(0, 0); imprimirAjustado(nombre, 21);
  oled.setCursor(0, 30);
  String detalle = "";
  if (talla.length()) detalle += "T:" + talla + " ";
  if (color.length()) detalle += color;
  oled.println(detalle);
  oled.setTextSize(2); oled.setCursor(0, 44); oled.print("$"); oled.println(precio, 2);
  oled.display();
}

void mostrarNoEncontrado(const String& sku) {
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(2); oled.setCursor(0, 6); oled.println("No"); oled.println("encontrado");
  oled.setTextSize(1); oled.setCursor(0, 50); oled.print("SKU: "); oled.println(sku);
  oled.display();
}

void pitar() { digitalWrite(PIN_BUZZER, HIGH); delay(120); digitalWrite(PIN_BUZZER, LOW); }

// ── Simula "escanear" y mostrar resultado ───────────────────────────────────
void simularEscaneo() {
  String sku = SKUS_DEMO[idxDemo];
  idxDemo = (idxDemo + 1) % N_SKUS;

  mostrarMensaje("Escaneando...", "(demo)");
  digitalWrite(PIN_LED, HIGH);
  delay(600);                       // simula el tiempo de captura

  pitar();
  String cuerpo = respuestaSimulada(sku);
  Serial.println("Simulado " + sku + " -> " + cuerpo);

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, cuerpo);
  if (err) {
    mostrarMensaje("Error de datos");
  } else if (doc["encontrado"] | false) {
    mostrarProducto(String((const char*)(doc["nombre"] | "")),
                    String((const char*)(doc["talla"]  | "")),
                    String((const char*)(doc["color"]  | "")),
                    doc["precio"] | 0.0);
  } else {
    mostrarNoEncontrado(sku);
  }

  digitalWrite(PIN_LED, LOW);
  delay(TIEMPO_RESULTADO_MS);
  mostrarEspera();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT); digitalWrite(PIN_BUZZER, LOW);
  pinMode(PIN_LED, OUTPUT);    digitalWrite(PIN_LED, LOW);
  pinMode(PIN_BOTON, INPUT_PULLUP);

  Wire.begin(PIN_SDA, PIN_SCL);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_DIR)) {
    Serial.println("No se encontro la OLED (prueba 0x3D).");
  }
  mostrarEspera();
}

void loop() {
  if (digitalRead(PIN_BOTON) == LOW) {       // botón pulsado (a GND)
    delay(30);
    if (digitalRead(PIN_BOTON) == LOW) {
      simularEscaneo();
      while (digitalRead(PIN_BOTON) == LOW) delay(10);  // espera a soltar
    }
  }
  delay(20);
}
