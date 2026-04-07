# Checklist de Validacion Manual

Fecha base: `2026-04-06`

Objetivo:
Registrar las validaciones manuales pendientes de esta ronda para no olvidarlas mientras seguimos implementando.

## Orden sugerido de ejecucion en Windows

Sigue este orden para validar sin mezclar causas ni perder tiempo entre pantallas.

### 1. Arranque base

- [x] Abrir la app y confirmar que el login carga sin errores.
- [x] Confirmar que se vean logo, nombre y version.
- [x] Confirmar que el selector de usuarios tenga contraste legible.
- [x] Iniciar sesion y verificar `Cargando aplicacion...`.
- [x] Confirmar que el cursor vuelve a normal al terminar de abrir la principal.

### 2. QR y etiquetas

- [x] Ir a `Inventario` y generar un QR individual.
- [x] Confirmar que la app no se cierre al generar el QR.
- [x] Confirmar que el preview se refresque despues de generar el QR.
- [x] Confirmar que el QR tenga imagen central cuando los assets existen.
- [x] Probar `Imprimir etiqueta` y confirmar que siga operativo en Windows.

### 3. Carga y salida segura

- [x] Probar una recarga general y confirmar cursor de espera.
- [ ] Probar `Generar todos los QR` y confirmar cursor de espera y regreso a normal.
- [x] Intentar cerrar la app en reposo y confirmar que pide confirmacion.
- [x] Intentar cerrar la app durante una operacion pesada y confirmar que no se cierra.

### 4. Caja

- [x] Revisar tabla de Caja y confirmar que ya no aparezca `SKU`.
- [x] Confirmar que `Cantidad` este al inicio.
- [x] Confirmar que la lectura visual de filas sea mas clara.
- [x] Probar una venta con stock insuficiente y confirmar que no bloquea.

### 5. Apartados y Presupuestos

- [x] Revisar carrito de Presupuestos y confirmar que ya no aparezca `SKU`.
- [x] Revisar detalle de Presupuestos y confirmar estructura consistente con Caja.
- [x] Revisar detalle de Apartados y confirmar estructura consistente con Caja.
- [x] Generar un comprobante de apartado y revisar limpieza del ticket.

### 6. Deportivo 2pz -> 3pz

- [x] Escanear `Pants 2pz` deportivo y confirmar pregunta de playera.
- [x] Confirmar que una playera valida de la misma escuela se agrega bien.
- [x] Confirmar que una playera de otra escuela se bloquea.
- [x] Confirmar que la lista muestre `Exacta`, `Sugerida` y `Atipica`.
- [x] Cobrar una venta de prueba y revisar ticket.

### 7. Caja y cierres

- [x] Revisar cierre de caja con apartados cancelados.
- [x] Confirmar que no inflen el esperado.
- [x] Revisar historial de cierres y confirmar que abra y cuadre.

### 8. Visual general

- [ ] Revisar `Catalogo`.
- [ ] Revisar `Inventario`.
- [ ] Revisar `Analitica`.
- [ ] Revisar `Configuracion`.
- [ ] Revisar dialogs operativos.

### 9. Empaquetado Windows

- [ ] Generar bundle de Windows.
- [ ] Confirmar `_internal/pos_uniformes/migrations`.
- [ ] Confirmar `_internal/pos_uniformes/assets/qr_icons`.
- [ ] Revisar icono de ventana.
- [x] `assets/app_icon.ico` ya quedo preparado para el empaquetado final.

## Windows

- [ ] Generar un bundle de Windows y confirmar que existan `_internal/pos_uniformes/migrations` y `_internal/pos_uniformes/assets/qr_icons`.
- [ ] Probar `Generar QR` en Windows con assets presentes y confirmar que no se cierre la app.
- [ ] Probar `Generar QR` en Windows simulando falta de asset y confirmar que el PNG se genere sin cerrar la app.
- [ ] Revisar en Windows que el logo, nombre y version visible se muestren correctamente al arrancar.
- [ ] Revisar en Windows que el selector de usuarios del login tenga contraste correcto sin pasar el mouse.
- [ ] Revisar en Windows si el icono de ventana y del `.exe` se ven consistentes con el `.ico` dedicado.

## Arranque y carga

- [ ] Iniciar sesion y confirmar que el login permanece visible mientras carga la app principal.
- [ ] Confirmar que durante la carga se vea el mensaje `Cargando aplicacion...`.
- [ ] Confirmar que el cursor vuelve a normal al terminar la carga inicial.
- [ ] Probar una recarga general y confirmar que aparece cursor de espera y luego vuelve a normal.
- [ ] Probar `Generar QR` individual y confirmar estado de carga visible y cursor normal al finalizar.
- [ ] Probar `Generar todos los QR` y confirmar estado de carga visible y cursor normal al finalizar.
- [ ] Intentar cerrar la app en reposo y confirmar que pide confirmacion.
- [ ] Intentar cerrar la app durante una operacion pesada y confirmar que no se cierra.

## Caja, Apartados y Presupuestos

- [ ] En Caja, confirmar que la tabla ya no muestre `SKU`.
- [ ] En Caja, confirmar que `Cantidad` quede al inicio y que la lectura de renglones sea mas clara.
- [ ] En Presupuestos, confirmar que el carrito ya no muestre `SKU` y que `Cantidad` quede al inicio.
- [ ] Revisar en Presupuestos que al escanear/agregar productos la tabla respire mejor y no se vea recortada; idealmente debe sentirse tan amplia y legible como Caja.
- [ ] En detalle de Presupuestos, confirmar la misma estructura visual que en Caja.
- [ ] En detalle de Apartados, confirmar la misma estructura visual que en Caja.
- [ ] En Caja, probar una venta con stock insuficiente y confirmar que ya no bloquea la operacion.

## Coherencia visual

- [ ] Revisar `Catalogo` y confirmar que ya no se sienta naranja de forma permanente; los colores fuertes solo deben marcar alertas reales.
- [ ] Revisar `Inventario` y confirmar que stock bajo, QR pendiente y apartados usen badges claros sin teñir toda la tabla.
- [ ] Revisar `Analitica` y confirmar que KPIs, cards y tablas sigan la misma paleta neutra con acentos semanticos.
- [ ] Revisar `Configuracion` y dialogs operativos para confirmar que cards, banners y tablas empatan con la nueva paleta.
- [ ] Revisar dialogo de impresion de etiquetas y confirmar que ya no se sienta visualmente fuera de la misma familia de la app.

## Deportivo 2pz -> 3pz

- [ ] En Caja, escanear un `Pants 2pz` deportivo y confirmar que pregunta si tambien lleva playera.
- [ ] Responder `Si`, capturar una playera valida de la misma escuela y confirmar que agrega ambas lineas.
- [ ] Probar una playera de escuela distinta y confirmar que la bloquea.
- [ ] Dejar vacio el SKU de playera y confirmar que se abre la lista de seleccion.
- [ ] Confirmar que la lista de playeras muestre marcas `Exacta`, `Sugerida` o `Atipica`.
- [ ] Confirmar que el mensaje en Caja aclare que es una `Prueba deportivo 3pz`.
- [ ] Cobrar una venta con esa composicion y confirmar que el ticket del cliente no muestre la nota interna de maqueta.
- [ ] Mas adelante, revisar en historial o trazabilidad que la venta y el movimiento si conserven la nota interna de maqueta.
- [ ] Tomar una decision sobre los SKUs legacy catalogados como `3pz`: definir si se conservan solo como compatibilidad temporal, si se migran a `2pz + playera` guiado, o si se ocultan del flujo operativo una vez validada la nueva regla.

## Comprobante de apartado

- [ ] Abrir un comprobante de apartado y confirmar que ya no muestre `Estado`.
- [ ] Confirmar que ya no muestre `Codigo cliente`, `Telefono`, `SKU`, `Copias configuradas` ni `Impresora preferida`.
- [ ] Confirmar que no se impriman notas internas como `Creado desde Caja` o `ambiente de pruebas`.
- [ ] Confirmar que total, abonado y saldo pendiente se entienden rapido.
- [ ] Revisar si el bloque de `Abonos` aporta valor al cliente tal como quedo o si conviene simplificarlo mas.

## Nota pendiente

- [ ] Confirmar en una build real de Windows que `assets/app_icon.ico` se aplique correctamente al `.exe` y al acceso directo.

## Estado del checkpoint tecnico

- [x] `check_startup_health.py` en verde el `2026-04-06`.
- [x] suite completa `unittest discover` en verde el `2026-04-06` con `636` pruebas.
- [x] regresiones tecnicas de `catalog_snapshot_service` y `quote_satellite_window` corregidas antes de cerrar este checkpoint.
- [x] validacion manual fuerte en Windows del flujo principal completada hasta `2026-04-07` para arranque, QR individual, etiquetas, carga/salida segura, Caja, Presupuestos, Apartados y regla deportivo `2pz -> 3pz`.

## Pendiente despues de este checkpoint

- [ ] Generar bundle final de Windows con la version `2026.04.07`.
- [ ] Confirmar dentro del bundle `_internal/pos_uniformes/migrations`.
- [ ] Confirmar dentro del bundle `_internal/pos_uniformes/assets/qr_icons`.
- [ ] Revisar el `.exe` empaquetado con el nuevo `.ico`.
- [ ] Tomar decision operativa sobre los SKUs legacy `3pz`.
