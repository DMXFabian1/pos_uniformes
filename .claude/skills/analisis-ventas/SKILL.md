---
name: analisis-ventas
description: Analizar las ventas reales de la tienda (Libreta de la caja) y sacar datos útiles para decidir — cuánto se vendió contra el periodo anterior, qué escuelas y prendas mueven la tienda, curva de tallas para pedir, qué se va a acabar, inventario parado, margen, días y horas fuertes, empleadas y lo que pidieron y no había. Solo lectura. Usar cuando Daniel pregunte "¿cómo vamos?", "¿qué se vendió este mes?", "¿qué pido para UVEG?", "¿qué escuela vende más?", "¿qué tengo parado?", "revisa mis ventas".
---

# Análisis de ventas

Un script de **solo lectura** (`scripts/analizar_ventas.py`) hace las cuentas. Usa los mismos servicios que la pestaña Analítica del POS, así que las cifras cuadran con ella. El trabajo de la skill es **interpretar**: no pegarle a Daniel las tablas completas, sino decirle qué significan y qué hacer.

## Dónde están los datos

- Las ventas reales están en la **Libreta** (`libreta_venta`), que tiene datos desde el **2-sep-2026**. Las tablas `venta` y `venta_detalle` quedaron casi vacías: no usarlas.
- Leer **de la caja**, porque la base local está atrasada en migraciones y el script lo avisa. Leer está permitido; el script se conecta en modo solo lectura.
  ```bash
  "$PY" .claude/skills/analisis-ventas/scripts/analizar_ventas.py --dias 30 --env-file "<env de la caja, ver CLAUDE.md>"
  ```

## Cómo pedirlo

| Pregunta de Daniel | Comando (más `--env-file …`) |
|---|---|
| "¿Cómo vamos?" | `--dias 30 --secciones resumen,escuelas,prendas,horarios` |
| "¿Cómo fue octubre?" | `--desde 2026-10-01 --hasta 2026-10-31` |
| "¿Qué pido?" | `--dias 30 --secciones reabasto,faltantes,tallas` |
| "¿Qué pido para UVEG?" | `--escuela UVEG --dias 60 --secciones tallas,reabasto,productos` |
| "¿Qué tengo parado?" | `--secciones muerto --sin-movimiento 60` |
| "¿Cuánto gano?" | `--secciones margen` (revisar la cobertura de costos) |
| "¿Quién vende más?" | `--secciones empleadas` |

Secciones: `resumen`, `escuelas`, `prendas`, `productos`, `tallas`, `reabasto`, `margen`, `muerto`, `horarios`, `empleadas`, `faltantes`. Con `--top N` se recortan las listas. Pedir solo las secciones necesarias gasta menos tokens.

## Cómo leerlo (trampas conocidas)

- **Temporada:** septiembre es regreso a clases. Comparar octubre o noviembre contra septiembre siempre "baja". Decirlo antes de alarmar. Cuando haya un año de datos (a partir de sep-2027), el script agrega solo la columna "Año pasado", que es la comparación justa.
- **Existencia NEGATIVA** = se vendió sin registrar la entrada de mercancía. No quiere decir "agotado": no se sabe cuánto hay. La recomendación es un conteo o capturar las entradas, no "pedir 15".
- **"(general / sin escuela)"** son prendas sin escuela (pants liso, pijamas, calcetas, playera polo). Suelen ser más de la mitad de la venta.
- **"(sin dato)"** en prendas son piezas vendidas sin SKU del catálogo (SIN-CODIGO). Si son muchas, hay productos por dar de alta (skill `alta-productos`).
- **Margen:** usa el `costo_referencia` actual y casi no hay costos capturados. Si la cobertura es menor al 30 %, no sacar conclusiones de la tienda entera.
- **Inventario parado:** mientras la Libreta tenga menos historia que la ventana pedida, salen como "parados" productos que solo son de temporada. Su valor a precio de venta no es dinero disponible.
- **Cobrado oficial** lleva los ajustes del dueño en sus cortes. Con `--escuela` el cobrado no se muestra, porque es de toda la tienda; se muestran el importe y las piezas de esa escuela.

## Qué entregar

1. **3 a 5 hallazgos** con su número y la acción que sugieren. Por ejemplo: "UVEG: se pidieron 5 Pants 3pz CH que no había y la existencia está en −15 → contar y pedir CH/MD".
2. Las tablas solo si Daniel las pide, o un extracto corto.
3. Si un hallazgo vale la pena guardarlo (tendencia, decisión de compra), anotarlo con `actualizar-vault`.

Si Daniel quiere un análisis que el script no hace, primero ver si lo tienen los servicios `analitica_libreta_service` (por producto, sku, escuela, pieza, talla, empleada, día, hora o forma de pago), `analitica_tablero_service`, `comparativa_service` o `demanda_service`, y agregarlo como sección nueva **reusándolos**. No repetir las definiciones en SQL propio.
