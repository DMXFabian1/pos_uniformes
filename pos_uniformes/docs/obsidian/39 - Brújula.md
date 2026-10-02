---
tags: [brujula, pos-uniformes, arquitectura, decision]
fecha: 2026-09-22
estado: vigente
---

# 39 — Brújula

> **Una escuela, un número, cuatro ventanas.**

El sistema existe para responder tres preguntas, y ninguna más:

1. **Qué necesita cada escuela.**
2. **Cuánto tengo de verdad.**
3. **Qué me pidieron que no tenía.**

| Ventana | Para quién | Qué muestra |
|---------|-----------|-------------|
| **POS** | Daniel | la gestión: catálogo, precios, conteos, pedidos |
| **Kiosko** | el piso | venta rápida, presupuestos, consulta |
| **Libreta** | el dinero | lo que entró de verdad (ver [[28 - Libreta Digital]]) |
| **Mapa** | el estado | las escuelas pintadas por cómo están |

**Ninguna ventana calcula. Todas preguntan.** Si una pantalla sabe la regla de negocio, esa pantalla ya se desfasó — solo falta que te des cuenta.

---

## Reglas vigentes

> **Nada entra al sistema si no cuelga de una escuela o de una prenda.**

Si una idea no se puede colgar de ninguna de las dos, es otro proyecto y vive en otra carpeta. Esto no prohíbe tener otros proyectos — prohíbe que se disfracen de POS.

- **Una lógica, un servicio.** Si dos archivos saben la misma regla, uno de los dos está mal.
- **La UI no hace SQL.** Ni Python que genera HTML, ni JS en el navegador.
- **Antes de escribir una consulta nueva, revisar si el servicio ya existe.**

*(El congelamiento de módulos nuevos se levantó al cerrar la Fase 2.)*

---

## Estado al 2026-09-22

### Quién contesta qué

| Pregunta | Servicio dueño |
|---|---|
| qué es *tienda* (total − piso − bodega) | `inventario_totales_service` |
| qué es *bajo mínimo* (`stock_minimo`, o 2) | `inventario_totales_service` |
| qué no se suma por venir contado en otra pieza | `conjunto_service.filtro_sin_conjuntos` |
| qué prendas tiene una escuela | `escuela_piezas_service` → `catalog_school_link_service` |
| cómo se ordenan los nombres (acentos) | `utils.text_normalization` |
| **cómo va una escuela** (todo junto) | `escuela_estado_service.estado_de` / `estados_de_todas` |
| **el semáforo** | `conteo_mapa_service.semaforo` |

### El semáforo, en un solo lugar

`conteo_mapa_service.semaforo(en_rojo, faltan, nunca, tallas)`:

| | Significa | Cuándo |
|---|---|---|
| 🔴 **rojo** | **no sabemos qué hay** | se vendió sin contar (existencia en negativo) **o** nunca se contó ni una talla |
| 🟠 **ámbar** | le falta contarse | venció, o está contada a medias |
| 🟢 **verde** | al día | contada y vigente |

Los dos caminos al rojo quieren decir lo mismo: *ese número no lo verificó nadie*.

### Quién lo pinta

| Ventana | Qué usa | Commit |
|---|---|---|
| **Mapa** | anillo por escuela, ficha, caja de clientes compartidos | `1baa43bf`, `1818dd3d` |
| **Panel** — portada | el mapa embebido como primera pestaña | `039a6ec2` |
| **Panel** — Disponibilidad | chip de salud por escuela | `e24aa16e` |
| **Libreta** (celular) | pantalla 🏫 Escuelas, agrupada por estado | `4c5768a2` |
| **Kiosko** — Conteos | `lo_que_toca` con lo rojo primero, mismo semáforo | `39c2b3c4`, `3bd134e6` |

Ninguna decide el umbral: lo traducen a su paleta. **Hay tests guardianes** que truenan si alguna vuelve a decidirlo, o si vuelve SQL crudo al generador del Panel.

### Las cifras de hoy (base de la Mac)

| | |
|---|---|
| escuelas con estado en el mapa | 45 — **6 en rojo**, 13 por contar, 26 al día |
| escuelas del POS | 52 — 7 rojo, 16 ámbar, 29 verde |
| renglones del kiosko | 40 — 19 rojo, 21 ámbar |
| tallas vivas | 5,052 |
| en negativo | **30** (la peor en −4; 51 piezas en rojo) |
| en cero o menos | 3,041 — **60% del catálogo** |
| de esas, nunca contadas | **2,077** |
| tests | 2,565 pasan (falla 1 preexistente de afluencia) |

---

## Lo que falta

1. **Correr `revisar_stock_negativo.bat` en la tienda.** Todo lo medido salió de la Mac: dimensiona el método, no el daño real. Hay `.bat` de un clic que deja el reporte en `reportes\` y ofrece mandarlo por git (`60476877`).
2. **Contar lo rojo.** Ya sale primero en el kiosko y en el celular.
3. **El guard de venta sigue apagado** — a propósito, ver abajo. Volver a evaluarlo cuando el catálogo esté contado.
4. **El HTML del Panel se sigue commiteando como foto.** La deuda que quedó fuera de la Fase 2; ver [[25 - Panel de Uniformes]].

### Decisión: el guard de venta se queda apagado

`services/sale_stock_policy.py` → `TEMPORARY_SALE_STOCK_GUARD_ENABLED = False`. Prenderlo bloquearía la venta del **60% del catálogo**, y 2,077 de esas tallas están en cero porque **nadie las contó**, no porque no haya.

Estorbar al mostrador para cuidar un número que nadie ha verificado es al revés — es el criterio de Daniel: *si un cambio solo le sirve a él y le estorba a quien atiende, no va al piso*.

> **Ojo con el mito:** la venta **sí** descuenta desde el 2026-09-14. Lo que el flag apaga es el **bloqueo** y el permiso de quedar en negativo. Y los **apartados ya bloquean hoy** (`InventarioService.validar_stock_disponible` no mira el flag).

En su lugar, el negativo se volvió señal: alimenta `lo_que_toca` y sale primero.

---

## Cómo se llegó aquí

Todo el 2026-09-22, en una sesión. Daniel: *"siento que tengo muchas ideas dispersas y estoy haciendo crecer el sistema sin guía… quiero que todo apunte a un solo camino."*

El problema no era la cantidad de módulos: **cada uno se trajo su propia copia de la verdad**, y el desfase que Daniel temía ya estaba en producción.

| Fase | Qué cambió | Commits |
|---|---|---|
| **0** | Escribir la brújula y poner [[25 - Panel de Uniformes]] al día (llevaba 4 meses sin tocar) | — |
| **1** | El negativo dejó de ser misterio: script de reconciliación y el rojo empuja los conteos | `9a56c32c`, `39c2b3c4`, `60476877` |
| **2** | El generador del Panel pasó de **8 consultas SQL a ninguna** | `8b031958`, `e3ef740a`, `8d1af476` |
| **3** | `escuela_estado_service`: todo de una escuela en una pregunta | `2fb0243c` |
| **4** | El mapa dejó de ser bonito y se volvió el tablero | `1baa43bf`, `039a6ec2`, `1818dd3d` |
| **+** | Las cuatro ventanas preguntando el mismo semáforo | `e24aa16e`, `4c5768a2`, `3bd134e6`, `4ffeb03d` |

### Los desfases que aparecieron

- **Los conjuntos, dos veces.** `conjunto_service.filtro_sin_conjuntos` en el POS y `NOT IN (SELECT conjunto_id FROM conjunto_componente)` a mano en el Panel, duplicado. Había hasta una constante `SQL_SIN_CONJUNTOS` que nadie usaba.
- **Las prendas de una escuela, con las ligas viejas.** El Panel decidía por `catalog_school_product_link`; el POS ya usaba el **uniforme armado** ([[38 - Catálogo Fase 2 - Uniformes]]). Coincidían solo porque las ligas se mantienen en espejo: **52 uniformes contra 143 ligas**. El día que se retiren, el Panel se habría quedado ciego sin que nadie lo notara.
- **El orden alfabético.** "Álvaro Obregón" iba al final en Python y primero en Postgres: la misma lista en dos órdenes según quién la pintara.
- **El semáforo del kiosko.** Ver abajo.

### Decisiones de diseño que vale recordar

- **Práxedis Guerrero:** el POS tiene dos (#19 Primaria, #49 Secundaria) y el mapa mandaba **tres CCT** a un nombre inexistente. El prefijo del CCT lo resuelve: `DES` y el CEBA `11DBA0022L` → Secundaria, `DPR` → Primaria.
- **Planteles compartidos:** SABES cubre 13 planteles con un registro, Motolinea 3. El anillo se pinta **solo cuando el estado es de esa escuela**; los demás lo llevan en la ficha, en la lista con punto hueco, y en la caja *"Clientes de varios planteles"*. Sin esa caja, SABES quedaba en rojo sin aparecer en el mapa — peor que el ruido que se venía a quitar.
- **El kiosko no lleva tablero de gestión.** La empleada no decide qué pedir ni cuándo contar. Decirle cuánto se vendió en 30 días es ruido en su pantalla.

---

## Lo que se aprendió

> [!caution] Un diff vacío no prueba nada si no se verificó que el programa **corrió**
> Al mover el último SQL del generador se perdió `_get_connection`, que además de conectar **elegía base** (la Mac si responde, si no la de la tienda) y ponía el paquete en el `sys.path`. El guion tronó con `ModuleNotFoundError`… y el diff dio *"cero diferencias"*, porque la corrida había fallado y el HTML seguía siendo el viejo.

> [!warning] Al unificar una regla, revisar también quién la **pinta**
> El kiosko tenía su propio semáforo (rojo = nunca contada, ámbar = empezada, gris = el resto) mientras las otras tres usaban otro. Un renglón con 5 tallas en rojo —el más urgente— salía **gris** en el kiosko y **rojo** en el mapa. Apareció **dentro** del trabajo de la brújula: en la Fase 1 se arregló el texto y el orden de esa pantalla, no el color, y así siguió dos fases más.

> [!note] Un cambio de criterio, un archivo
> Cuando Daniel pidió que *"nunca contada"* volviera a rojo, las cuatro ventanas se movieron juntas sin tocarlas: el kiosko pasó de 13 a 19 renglones rojos y las escuelas de 4 a 7. Solo hubo que corregir a mano las **leyendas**, que decían *"rojo = se vendió sin contar"* y ya era la mitad de la verdad.

> [!note] Límite heredado del reparto
> Los niveles de una escuela salen de sus **propias** prendas, así que una que solo llevara generales no tendría de dónde colgarlas. En la tienda no pasa. Si algún día pasa, hay que darle nivel a la escuela en vez de deducirlo.

---

## Lo que esta brújula NO dice

- No dice que los módulos existentes estén mal. Cada uno nació de un dolor real.
- No dice que haya que reescribir el POS. Los servicios son el activo; el problema era quién **no** los usaba.
- No prohíbe experimentar. Prohíbe que el experimento se vuelva una segunda fuente de verdad sin que nadie lo decida.

---

> Creado y cerrado: 2026-09-22 · Índice: [[00 - Índice General]]
> Ver: [[25 - Panel de Uniformes]] · [[36 - Conteos por Jornada]] · [[37 - Revisar y Pedidos]] · [[38 - Catálogo Fase 2 - Uniformes]] · [[19 - Deuda Técnica]]
