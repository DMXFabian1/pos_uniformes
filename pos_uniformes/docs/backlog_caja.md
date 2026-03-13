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

#### 3. Redondeo de cobro para evitar centavos

- Contexto:
  Se busca una regla coherente para no batallar con centavos en ninguna modalidad de cobro.
- Objetivo:
  Definir una politica de redondeo operativa, consistente y mayormente a favor del negocio sin sentirse abusiva.
- Decision propuesta:
  - aplicar al total final en efectivo, transferencia y mixto
  - tramos:
    - `.00` a `.19` -> `.00`
    - `.20` a `.69` -> `.50`
    - `.70` a `.99` -> siguiente `.00`
  - mantener consistencia entre caja, cobro, ticket y corte
- Criterio esperado:
  - regla clara y documentada
  - visible para el operador antes de confirmar
  - consistente entre total, cambio y ticket
- Documento base:
  `docs/politica_redondeo_efectivo.md`

#### 4. Cliente en caja solo por escaneo de QR

- Contexto:
  En Caja no se quiere seleccion manual del cliente. La venta debe quedarse como mostrador salvo que el cliente se agregue escaneando su QR o codigo de cliente.
- Objetivo:
  Reducir errores operativos y forzar un flujo de identificacion mas consistente para beneficios de cliente.
- Criterio esperado:
  - el selector manual de cliente deja de ser editable o desaparece de Caja
  - el cliente solo se enlaza cuando se escanea su QR o codigo
  - si no se escanea cliente, la venta permanece como mostrador
  - el flujo de reemplazo de cliente escaneado con carrito sigue pidiendo confirmacion cuando corresponda
  - descuento, lealtad y resumen visual siguen sincronizados con el cliente escaneado
