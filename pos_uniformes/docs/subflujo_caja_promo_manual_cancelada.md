# Subflujo Caja: Promo Manual Fallida o Cancelada

## Objetivo

Definir el comportamiento esperado cuando el usuario intenta aplicar una promo manual y la autorizacion se cancela o falla.

## Regla principal

1. Si el descuento seleccionado es cero, la promo manual debe limpiarse.
2. Si ya existia una promo autorizada y se vuelve a elegir el mismo porcentaje, la promo se conserva.
3. Si se elige un nuevo porcentaje, debe solicitarse autorizacion.
4. Si la autorizacion falla o se cancela:
   - el combo debe volver al porcentaje previamente autorizado
   - si no habia promo previa, el estado de promo debe quedar limpio
5. La promo solo cuenta como activa si el porcentaje seleccionado coincide con el porcentaje autorizado.

## Archivos involucrados

- `services/manual_promo_flow_service.py`
- `ui/main_window.py`
- `services/sale_discount_option_service.py`

## Casos esperados

### Caso A. El usuario pone descuento cero

- La promo se limpia.
- El resumen deja de mostrar promo manual.

### Caso B. Ya existia promo autorizada y se vuelve a elegir el mismo porcentaje

- No pide nueva autorizacion.
- La promo se conserva.

### Caso C. El usuario elige una promo nueva y cancela

- El combo vuelve al porcentaje anterior.
- Si habia promo previa, se conserva esa promo previa.
- Si no habia promo previa, no debe quedar promo activa.

### Caso D. El usuario elige una promo nueva y el codigo falla

- Debe comportarse igual que en cancelacion.
- No debe quedar promo nueva activa.

## Anomalias a vigilar

- la promo queda activa aunque el usuario cancelo
- el combo muestra un porcentaje pero el estado autorizado es otro
- al fallar autorizacion se pierde una promo previa valida
- una promo sigue afectando el total aunque el descuento seleccionado ya no coincide

## Checklist manual rapido

- aplicar promo valida y conservarla
- intentar cambiar a otra promo y cancelar
- intentar cambiar a otra promo y fallar codigo
- volver a cero y confirmar que la promo se limpia
