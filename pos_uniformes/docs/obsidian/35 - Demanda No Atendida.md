---
tags: [modulo, pos-uniformes, analitica, kiosko]
---

# 35 — Demanda No Atendida

> Lo que la gente pidió y no se pudo vender. El dato que ninguna tabla tenía.

Relacionado: [[28 - Libreta Digital]] · [[12 - Servicios - Analítica e Historia]] · [[07 - Servicios - Catálogo e Inventario]] · [[17 - App Satélite]]

---

## El problema

La Libreta cuenta lo que **sí** había. Ninguna tabla cuenta lo que **faltó**, y eso es justo lo que sirve para decidir qué pedir. También es lo que le falta al algoritmo que Daniel quiere alimentar: entrenado solo con ventas, aprende a comprar más de lo que ya compra, nunca aprende del hueco.

## La regla de diseño (criterio de Daniel, 2026-09-10)

> [!important] La empleada no llena formularios
> Un formulario, por chico que sea, es un impuesto que ella paga y el dueño cobra. Se llena bien dos semanas y luego se llena mal, y quedan datos peores que no tener nada.
>
> La señal tiene que ser **subproducto de un gesto que ella ya hace**, y ese gesto debe **devolverle algo útil a ella**. Si el cambio solo le sirve a Daniel y a ella le estorba, no va al piso todavía.

## Las tres señales

| Tipo | Cuándo se anota | ¿Depende del inventario? |
|------|-----------------|--------------------------|
| `busqueda_vacia` | Buscó algo y el catálogo no devolvió nada | **No** — es catálogo puro, confiable desde el día uno |
| `talla_agotada` | Eligió una talla que el sistema marca en cero | **Sí** |
| `carrito_vacio` | Piezas escaneadas y canceladas sin cobrar | No |

`busqueda_vacia` no siempre es falta de producto: muchas veces es un **sinónimo que le falta al buscador**. Cruzar con [[13 - Servicios - Utilidades]] (Meilisearch).

## Cómo funciona

`services/demanda_service.py`

- **Anotar es tonto a propósito.** Va a un JSON local (`demanda_pendiente.json`), funciona sin red y **nunca lanza excepción**. Una señal perdida no vale una venta.
- **La inteligencia está en el drenado.** `colapsar()` tira las cadenas de tecleo: cami → camis → camisa deja solo `"camisa"` (misma empleada, ventana de 90 s, mínimo 3 letras). Así la UI puede ser tonta y el dato sale limpio.
- **Repetición > señal suelta.** `Falta.urgente` = 3 veces o más. Una sola es ruido.
- El drenado va pegado al de la Libreta (satélite y venta rápida).

Tabla `demanda_no_atendida` — migración **`z9b0c1d2e3f4`**. Ver [[02 - Base de Datos]].

## Dónde se ve

**Daniel:** pestaña **Analítica** → bloque "Lo que se perdió", debajo de las ventas reales. Dos listas: **Qué pedir** (producto · talla) y **No lo encuentran** (texto buscado). Con veces, piezas y última vez; lo urgente en rojo. `ui/helpers/analytics_demanda_helper.py`.

**Las empleadas:** nada, por ahora. Ver abajo.

## El interruptor

> [!warning] `EXISTENCIA_CONFIABLE = False` en `services/demanda_service.py`
> Apagado porque el stock **no es confiable** (ver [[07 - Servicios - Catálogo e Inventario]]). Con él apagado:
> - Las tallas del Presupuesto guiado se ven **todas iguales**, como siempre.
> - La columna **"Hay"** no aparece en el buscador de Ctrl+S.
> - La captura sigue corriendo, invisible: cuando se prenda ya habrá historia.
>
> **Prenderlo solo cuando:** la venta descuente stock **y** esté contado lo que se mueve.

Cuando se prenda, así se ve: la talla agotada sale **punteada y gris**, sigue siendo tocable (un presupuesto no valida stock), y al tocarla se pinta **verde con "anotado ✓"** — acuse para que ella tenga qué decirle al cliente. En Ctrl+S, columna "Hay" con `≈N` o `agotado`.

## Lo que se dejó fuera a propósito

Preguntar **"¿se llevó otra cosa o se fue?"**. Eso sí necesita a una persona y solo se decide cuando haya meses de toques acumulados que digan si el hueco vale la pena.

## Tests

`tests/test_demanda_service.py` (19) · `tests/test_demanda_no_estorba.py` (7, el presupuesto no se estorba ni con el disco lleno) · `tests/test_analytics_demanda_panel.py` (5).
