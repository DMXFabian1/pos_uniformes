/*
 * ============================================================
 *  ELEVADOR DE 3 PISOS - Arduino Nano + L298N
 * ============================================================
 *
 *  Hardware (según diagrama Fritzing):
 *   - Motor DC 3-6V en OUT1/OUT2 del L298N, alimentado con 12V.
 *   - 3 botones de llamada (piso 1, 2, 3) a GND  -> INPUT_PULLUP.
 *   - 3 micro-switches de fin de carrera, uno por piso, a GND -> INPUT_PULLUP.
 *   - Display 7 segmentos de CÁTODO COMÚN con resistencias (220-330 Ω).
 *
 *  Funcionamiento:
 *   - Al encender hace "homing": si no está en ningún piso baja hasta
 *     encontrar un switch.
 *   - Se pueden pedir varios pisos; atiende primero los que están en la
 *     dirección en la que ya viaja (como un elevador real, algoritmo SCAN).
 *   - Arranque suave por PWM para no dar el tirón.
 *   - Mientras viaja el display parpadea mostrando el último piso conocido.
 *   - Si tarda más de TIMEOUT_VIAJE_MS en llegar al siguiente piso, se detiene
 *     por seguridad y muestra "E". Se reinicia con cualquier botón.
 *
 *  IMPORTANTE: el motor es de 3-6V y el L298N recibe 12V. VELOCIDAD_PWM
 *  limita el voltaje efectivo (12V * 110/255 ≈ 5.2V). No lo subas a 255
 *  o puedes quemar el motor.
 * ============================================================
 */

// ---------------------- PINES (ajusta a tu cableado) ----------------------
// L298N
const uint8_t PIN_ENA = 10;   // PWM (velocidad). Debe ser pin PWM: 3,5,6,9,10,11
const uint8_t PIN_IN1 = 11;   // dirección
const uint8_t PIN_IN2 = 12;   // dirección

// Botones de llamada (al presionar conectan a GND)
const uint8_t PIN_BTN[3] = { 9, 8, 7 };     // piso 1, piso 2, piso 3

// Micro-switches de fin de carrera por piso (al activarse conectan a GND)
const uint8_t PIN_SW[3]  = { 6, 5, 4 };     // piso 1, piso 2, piso 3

// Display 7 segmentos cátodo común: a, b, c, d, e, f, g
const uint8_t PIN_SEG[7] = { 3, 2, A0, A1, A2, A3, A4 };

// ---------------------- PARÁMETROS ----------------------
const uint8_t  VELOCIDAD_PWM      = 110;    // 0-255. ~5V efectivos con fuente de 12V
const uint8_t  PWM_HOMING         = 90;     // más lento al buscar piso al encender
const uint16_t RAMPA_MS           = 400;    // duración del arranque suave
const uint16_t ESPERA_EN_PISO_MS  = 2000;   // "puertas abiertas" antes de seguir
const uint32_t TIMEOUT_VIAJE_MS   = 15000;  // máximo entre pisos antes de error
const uint16_t DEBOUNCE_MS        = 40;
const uint16_t PARPADEO_MS        = 250;

// Si al subir el elevador BAJA, cambia esto a true (invierte el motor)
const bool INVERTIR_MOTOR = false;

// ---------------------- DISPLAY ----------------------
// Segmentos: bit0=a, bit1=b, bit2=c, bit3=d, bit4=e, bit5=f, bit6=g
const uint8_t DIGITOS[] = {
  0b0111111, // 0
  0b0000110, // 1
  0b1011011, // 2
  0b1001111, // 3
  0b1100110, // 4
  0b1101101, // 5
  0b1111101, // 6
  0b0000111, // 7
  0b1111111, // 8
  0b1101111, // 9
};
const uint8_t SEG_E     = 0b1111001; // "E" error
const uint8_t SEG_GUION = 0b1000000; // "-" buscando piso
const uint8_t SEG_OFF   = 0;

void mostrar(uint8_t mascara) {
  for (uint8_t i = 0; i < 7; i++) {
    digitalWrite(PIN_SEG[i], (mascara >> i) & 1 ? HIGH : LOW);
  }
}

void mostrarPiso(int8_t piso) { // piso 0..2 -> dígito 1..3
  if (piso < 0) mostrar(SEG_GUION);
  else          mostrar(DIGITOS[piso + 1]);
}

// ---------------------- MOTOR ----------------------
enum Direccion : int8_t { ABAJO = -1, QUIETO = 0, ARRIBA = 1 };

void motorParar() {
  analogWrite(PIN_ENA, 0);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
}

void motorMover(int8_t dir, uint8_t pwm) {   // dir: ARRIBA o ABAJO
  bool subir = (dir == ARRIBA) != INVERTIR_MOTOR;
  digitalWrite(PIN_IN1, subir ? HIGH : LOW);
  digitalWrite(PIN_IN2, subir ? LOW  : HIGH);
  analogWrite(PIN_ENA, pwm);
}

// ---------------------- ENTRADAS ----------------------
bool switchActivo(uint8_t piso) { return digitalRead(PIN_SW[piso]) == LOW; }

// Devuelve el piso cuyo switch está activo, o -1
int8_t pisoDetectado() {
  for (uint8_t i = 0; i < 3; i++) if (switchActivo(i)) return i;
  return -1;
}

// Debounce de botones con detección de flanco (solo al presionar)
bool    btnEstado[3]     = { false, false, false };
uint32_t btnUltimoCambio[3] = { 0, 0, 0 };

bool botonPresionado(uint8_t i) {
  bool lectura = digitalRead(PIN_BTN[i]) == LOW;
  if (lectura != btnEstado[i] && millis() - btnUltimoCambio[i] > DEBOUNCE_MS) {
    btnEstado[i] = lectura;
    btnUltimoCambio[i] = millis();
    return lectura; // true solo en el flanco de presionar
  }
  return false;
}

// ---------------------- ESTADO DEL ELEVADOR ----------------------
enum Estado : uint8_t { HOMING, PARADO, VIAJANDO, ESPERANDO, ERROR_ };

Estado    estado        = HOMING;
int8_t    pisoActual    = -1;       // último piso confirmado por switch
int8_t    pisoDestino   = -1;
Direccion direccion     = QUIETO;   // dirección preferente (para SCAN)
bool      pendiente[3]  = { false, false, false };
uint32_t  tInicio       = 0;        // marca de tiempo del estado actual (timeout)
uint32_t  tArranque     = 0;        // inicio del viaje (rampa de arranque)

bool hayPendientes() {
  return pendiente[0] || pendiente[1] || pendiente[2];
}

// Elige el siguiente destino: primero en la dirección actual, si no hay, da la vuelta
int8_t siguienteDestino() {
  if (direccion != ABAJO) {               // preferir subir
    for (int8_t p = pisoActual + 1; p < 3; p++) if (pendiente[p]) return p;
    for (int8_t p = pisoActual - 1; p >= 0; p--) if (pendiente[p]) return p;
  } else {                                // preferir bajar
    for (int8_t p = pisoActual - 1; p >= 0; p--) if (pendiente[p]) return p;
    for (int8_t p = pisoActual + 1; p < 3; p++) if (pendiente[p]) return p;
  }
  return -1;
}

void cambiarEstado(uint8_t nuevo) {
  estado  = (Estado)nuevo;
  tInicio = millis();
}

void iniciarViaje(int8_t destino) {
  pisoDestino = destino;
  direccion   = (destino > pisoActual) ? ARRIBA : ABAJO;
  cambiarEstado(VIAJANDO);
  tArranque = tInicio;
  Serial.print(F("Viajando del piso ")); Serial.print(pisoActual + 1);
  Serial.print(F(" al piso "));          Serial.println(destino + 1);
}

// Rampa de arranque suave: de 0 a VELOCIDAD_PWM en RAMPA_MS
uint8_t pwmRampa(uint32_t transcurrido) {
  if (transcurrido >= RAMPA_MS) return VELOCIDAD_PWM;
  return (uint8_t)((uint32_t)VELOCIDAD_PWM * transcurrido / RAMPA_MS);
}

// ---------------------- SETUP ----------------------
void setup() {
  Serial.begin(9600);

  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  motorParar();

  for (uint8_t i = 0; i < 3; i++) {
    pinMode(PIN_BTN[i], INPUT_PULLUP);
    pinMode(PIN_SW[i],  INPUT_PULLUP);
  }
  for (uint8_t i = 0; i < 7; i++) pinMode(PIN_SEG[i], OUTPUT);

  // Pequeña animación de prueba del display (0-9)
  for (uint8_t d = 0; d <= 9; d++) { mostrar(DIGITOS[d]); delay(80); }
  mostrar(SEG_OFF);

  pisoActual = pisoDetectado();
  if (pisoActual >= 0) {
    Serial.print(F("Listo en piso ")); Serial.println(pisoActual + 1);
    cambiarEstado(PARADO);
  } else {
    Serial.println(F("Sin piso detectado, bajando (homing)..."));
    direccion = ABAJO;
    cambiarEstado(HOMING);
  }
}

// ---------------------- LOOP ----------------------
void loop() {
  uint32_t ahora = millis();

  // ---- 1. Leer botones (en cualquier estado) ----
  for (uint8_t i = 0; i < 3; i++) {
    if (botonPresionado(i)) {
      if (estado == ERROR_) {               // cualquier botón resetea el error
        Serial.println(F("Error reiniciado, haciendo homing"));
        direccion = ABAJO;
        cambiarEstado(HOMING);
        break;
      }
      if (i == pisoActual && (estado == PARADO || estado == ESPERANDO)) {
        continue;                           // ya estamos aquí, ignorar
      }
      pendiente[i] = true;
      Serial.print(F("Llamada al piso ")); Serial.println(i + 1);
    }
  }

  // ---- 2. Máquina de estados ----
  switch (estado) {

    case HOMING: {
      motorMover(ABAJO, PWM_HOMING);
      int8_t p = pisoDetectado();
      if (p >= 0) {
        motorParar();
        pisoActual = p;
        Serial.print(F("Homing OK, piso ")); Serial.println(p + 1);
        cambiarEstado(PARADO);
      } else if (ahora - tInicio > TIMEOUT_VIAJE_MS) {
        motorParar();
        Serial.println(F("ERROR: homing sin encontrar piso"));
        cambiarEstado(ERROR_);
      }
      break;
    }

    case PARADO: {
      motorParar();
      if (hayPendientes()) {
        int8_t dest = siguienteDestino();
        if (dest >= 0) iniciarViaje(dest);
      }
      break;
    }

    case VIAJANDO: {
      motorMover(direccion, pwmRampa(ahora - tArranque));

      // Actualizar piso actual al pasar por switches intermedios
      int8_t p = pisoDetectado();
      if (p >= 0 && p != pisoActual) {
        pisoActual = p;
        tInicio = ahora;                    // reinicia el timeout entre pisos
        Serial.print(F("Pasando piso ")); Serial.println(p + 1);
      }

      if (p == pisoDestino) {               // llegamos
        motorParar();
        pendiente[pisoDestino] = false;
        Serial.print(F("Llegó al piso ")); Serial.println(pisoDestino + 1);
        cambiarEstado(ESPERANDO);
      } else if (ahora - tInicio > TIMEOUT_VIAJE_MS) {
        motorParar();
        Serial.println(F("ERROR: tiempo de viaje excedido"));
        cambiarEstado(ERROR_);
      }
      break;
    }

    case ESPERANDO: {                       // "puertas abiertas"
      motorParar();
      if (ahora - tInicio >= ESPERA_EN_PISO_MS) {
        cambiarEstado(PARADO);
      }
      break;
    }

    case ERROR_: {
      motorParar();
      pendiente[0] = pendiente[1] = pendiente[2] = false;
      break;
    }
  }

  // ---- 3. Display ----
  switch (estado) {
    case VIAJANDO:
    case HOMING:
      // parpadea el último piso conocido (o "-" si no se conoce)
      if ((ahora / PARPADEO_MS) % 2 == 0) mostrarPiso(pisoActual);
      else                                mostrar(SEG_OFF);
      break;
    case ERROR_:
      if ((ahora / PARPADEO_MS) % 2 == 0) mostrar(SEG_E);
      else                                mostrar(SEG_OFF);
      break;
    default:
      mostrarPiso(pisoActual);
      break;
  }
}
