# Backlog de Caja

## Solicitudes cerradas

### 2026-03-13

#### 1. Calculadora usable con teclado fisico ✅ cerrado 2026-04-18

- Verificado que `install_keypad_shortcuts` implementado desde `fc5f0bb` (2026-03-12) cubre todos los criterios:
  - digitos 0-9 escriben monto ✓
  - `Backspace` corrige ✓
  - `Enter` confirma ✓
  - `Esc` cancela ✓
- No se requirieron cambios adicionales.

#### 3. Redondeo de cobro para evitar centavos ✅ cerrado 2026-04-18

- `sale_rounding_service.py` implementa la regla `.00/.50/siguiente .00`
- Integrado en `sale_discount_service.py`, visible en panel de caja y ticket
- `ResumenCaja` ahora incluye `total_ajuste_redondeo` separado del descuento
- El detalle del corte en Configuracion muestra "Ajuste por redondeo" y "Descuentos aplicados"

---

## Solicitudes abiertas de operacion

### 2026-03-13

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

#### 4. Cliente en caja solo por escaneo de QR ✅ cerrado 2026-04-18

- Verificado que el flujo ya estaba implementado:
  - `sale_client_combo` es `setVisible(False)` + `setEnabled(False)` siempre
  - el cliente solo se enlaza via `_apply_scanned_client_to_sale` al escanear QR o codigo
  - sin escaneo la venta queda en "Mostrador / sin cliente" (index 0 del combo)
  - `confirm_replace` pide confirmacion si hay carrito con otro cliente
  - "Vaciar carrito" y fin de venta resetean cliente a Mostrador
  - descuento, lealtad y display label se sincronizan via `_handle_sale_client_changed`
