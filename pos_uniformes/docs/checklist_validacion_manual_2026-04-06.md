# Checklist de Validacion Manual

Fecha base: `2026-04-06`

Objetivo:
Registrar las validaciones manuales pendientes de esta ronda para no olvidarlas mientras seguimos implementando.

## Windows

- [ ] Generar un bundle de Windows y confirmar que existan `_internal/pos_uniformes/migrations` y `_internal/pos_uniformes/assets/qr_icons`.
- [ ] Probar `Generar QR` en Windows con assets presentes y confirmar que no se cierre la app.
- [ ] Probar `Generar QR` en Windows simulando falta de asset y confirmar que el PNG se genere sin cerrar la app.
- [ ] Revisar en Windows que el logo, nombre y version visible se muestren correctamente al arrancar.
- [ ] Revisar en Windows que el selector de usuarios del login tenga contraste correcto sin pasar el mouse.
- [ ] Revisar en Windows si el icono de ventana se ve consistente; recordar que antes del empaquetado final falta preparar un `.ico` dedicado.

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

## Comprobante de apartado

- [ ] Abrir un comprobante de apartado y confirmar que ya no muestre `Estado`.
- [ ] Confirmar que ya no muestre `Codigo cliente`, `Telefono`, `SKU`, `Copias configuradas` ni `Impresora preferida`.
- [ ] Confirmar que no se impriman notas internas como `Creado desde Caja` o `ambiente de pruebas`.
- [ ] Confirmar que total, abonado y saldo pendiente se entienden rapido.
- [ ] Revisar si el bloque de `Abonos` aporta valor al cliente tal como quedo o si conviene simplificarlo mas.

## Nota pendiente

- [ ] Antes del empaquetado final de Windows, preparar `assets/app_icon.ico` y conectarlo al `.spec`.

## Estado del checkpoint tecnico

- [x] `check_startup_health.py` en verde el `2026-04-06`.
- [x] suite completa `unittest discover` en verde el `2026-04-06` con `636` pruebas.
- [x] regresiones tecnicas de `catalog_snapshot_service` y `quote_satellite_window` corregidas antes de cerrar este checkpoint.
