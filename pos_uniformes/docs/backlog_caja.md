# Backlog de Caja

## Solicitudes abiertas de operacion

### 2026-03-13

#### 1. Calculadora usable con teclado fisico

- Contexto:
  La calculadora o captura de cobro debe responder tambien a las teclas del teclado, no solo a botones en pantalla.
- Objetivo:
  Permitir captura rapida sin depender del mouse.
- Criterio esperado:
  - numeros del teclado escriben monto
  - `Backspace` corrige
  - `Enter` confirma cuando corresponda
  - `Esc` cancela si el flujo lo permite

#### 2. Quitar el nombre del cliente del total visible en Caja

- Contexto:
  En la pantalla de caja, el bloque del total no debe mostrar el nombre del cliente.
- Objetivo:
  Reducir ruido visual en el area de cobro.
- Criterio esperado:
  - el total y beneficio siguen visibles
  - el nombre del cliente no aparece dentro del bloque principal de total
  - la referencia del cliente puede vivir en otra zona si sigue siendo necesaria

#### 3. Redondeo de efectivo a favor para evitar centavos

- Contexto:
  No siempre hay monedas para centavos o denominaciones pequenas.
- Objetivo:
  Definir una politica de redondeo de efectivo operativa y consistente.
- Pendiente por definir:
  - si aplica solo a efectivo
  - si el redondeo siempre va a favor del negocio
  - si debe mostrarse como linea explicita en ticket y resumen
- Criterio esperado:
  - regla clara y documentada
  - visible para el operador antes de confirmar
  - consistente entre total, cambio y ticket
