---
name: registro-venta-libreta
description: Registrar en la Libreta de la caja ventas que no se capturaron en su momento (pedidos especiales, precios acordados, ventas fuera de la tienda, "que no quede fuera de registro"), con la empleada correcta para sus comisiones, con la fecha real sin descuadrar cortes ya cerrados, y descontando el stock. Usar cuando Daniel diga "registra la venta", "vendí 12 boinas a $70", "agrégale a Stayce sus comisiones de…", "esto se vendió el martes y no se anotó".
---

# Registrar ventas en la Libreta

Lo normal es que las empleadas capturen sus ventas en la Libreta. Esta skill es para las **excepciones**. Escribe en la caja, así que se ensaya primero y **solo se guarda con el OK de Daniel**.

Dos scripts en `scripts/`, desde la raíz del repo con `$PY` (ver `CLAUDE.md`) y `--env-file` del env de la caja:

| Script | Qué hace | Escribe |
|---|---|---|
| `buscar.py` | SKU, precio de lista y existencia (`--producto "boina vino"`, se repite), empleadas con su último pago (`--empleadas`), y los cortes de un día con la hora sugerida (`--dia AAAA-MM-DD`) | No |
| `registrar_venta.py plan.json` | Ensaya las ventas del plan en **una** transacción y dice en qué corte caen, cómo queda el cajón, las comisiones y el stock. Con `--aplicar` las guarda | Sí |

El formato del plan está en el docstring de `registrar_venta.py`. El precio es opcional, y si falta se usa el de lista. Usa `libreta_service.registrar_operacion` (como la Libreta: comisiones 1 por pieza y 2 en los de 3pz, stock con `libreta:N`) y deja `origen = "manual-claude"`.

## Pasos

1. **Traducir lo que dice Daniel a SKUs** con `buscar.py --producto`. Los nombres que usa no siempre son los del catálogo: "guinda" es **Vino** y "golpes" es **Golpe Escolta**. Si hay más de un candidato, preguntar. Si el producto no existe, darlo de alta con la skill `alta-productos`; `SIN-CODIGO` es el último recurso.
2. **Empleada:** la que cobra la comisión. Si una vendió y otra organizó, proponer un reparto justo: cada quien se queda con los renglones que atendió, y la comisión **no** se parte por pieza.
3. **Fecha (`cuando`):**
   - **Venta de hoy, con el dinero en el cajón:** sin `cuando`.
   - **Venta de un día pasado, o el dinero ya se retiró:** `buscar.py --dia` da la **hora sugerida**, entre la última operación del día y el cierre de su corte. Así cae en un corte ya cerrado y **el cajón abierto no se mueve**.
   - Si no hay corte cerrado ese día, la venta cae en el periodo abierto y **sube lo que debe haber en el cajón**. Decírselo a Daniel.
4. **Ensayo:** `registrar_venta.py plan.json`. Mostrar a Daniel la tabla: #, fecha, empleada, productos con precio (y el de lista si es distinto), total, efectivo o tarjeta, comisiones, en qué corte cae, cajón antes y después, y stock antes y después. **Esperar su OK.**
5. **Guardar:** el mismo comando con `--aplicar`, y verificar después con una consulta de solo lectura (`libreta_venta` por id y `movimiento_inventario` con `referencia = 'libreta:N'`).

## Avisos que no hay que pasar por alto

- `⚠ … estas comisiones NO entran en ningún pago`: la fecha cae **antes del último pago** de la empleada. Mover `cuando` después de ese pago (si Daniel quiere que las cobre) o avisarle.
- `⚠ NEGATIVA`: el stock queda bajo cero, porque se vendió sin capturar la entrada de mercancía. Recordarle a Daniel capturar la entrada. Con `"descontar_stock": false` la venta no toca el stock; usarlo solo si Daniel lo pide.
- **Los # de Libreta del ensayo se gastan:** el número real al guardar es otro, y es normal.
- **Abonos, apartados, cambios y devoluciones** no son de esta skill. Van en el POS.

## Después

Reportar el # guardado, el total, las comisiones por empleada, cómo quedó el cajón y los stocks negativos. Si fue algo fuera de lo común (una venta grande por pedido o un precio especial), ofrecer anotarlo con `actualizar-vault`.
