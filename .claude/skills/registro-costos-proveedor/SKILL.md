---
name: registro-costos-proveedor
description: Registrar una nota de remisión o compra de proveedor (Martell, Tejidos Romanos, etc.) en pos_uniformes/docs/costos_proveedores.md con su tabla de costos y el margen contra el precio de venta actual de la caja. Usar cuando Daniel comparta una foto o lista de una remisión o diga "registra esta compra".
---

# Registrar costos de proveedor

Archivo: `pos_uniformes/docs/costos_proveedores.md`. Leer primero su encabezado (convenciones `B`, `V` y la fórmula de margen) y una sección existente para copiar el formato. Si en esta rama el archivo no tiene las remisiones más recientes que menciona Daniel, avisar: puede que estén en otra rama.

## Pasos

1. Ubicar la sección `## <Proveedor>`, o crearla, y agregar `### Remisión <dd-mmm-aaaa>`.
2. Tabla `| Cant | Prenda | Tallas | Costo | Importe |` con una fila de total en negritas.
3. **Cuadrar la suma:** si el total escrito en la nota no coincide con la suma de los renglones, dejar una nota `>` con la diferencia.
4. Tabla `### Margen contra precio de venta actual` con `| Prenda | Tallas | Costo | Venta | Margen |`:
   - Venta = precio actual en la caja (solo lectura) o en `Gestor_de_Inventarios/data/productos.db` si no hay acceso a la caja. Decir cuál se usó.
   - Margen = (venta − costo) / venta, en porcentaje sin decimales.
   - Marcar los márgenes bajos (menos de 40 %) como candidatos a subir precio, **sin aplicar nada**. Si Daniel decide subir, usar la skill `cambio-precios-catalogo`.
5. Si la prenda es nueva (no existe en el catálogo), decirlo y no inventar el precio de venta.
6. Commit: `docs: compra <Proveedor>, <prenda principal> (<dd-mmm-aaaa>)`.
