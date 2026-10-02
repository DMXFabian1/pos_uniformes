---
tags: [pendiente, pos-uniformes, catalogo, conjuntos]
fecha: 2026-09-22
estado: el caso 3 resuelto; quedan 35 conjuntos que necesitan decisiones de Daniel
---

# 40 — Conjuntos con tallas que no se pueden armar

> **Eran 37 conjuntos. Quedan 35.**
> Ofrecen tallas que ninguna de sus piezas tiene: El catálogo las enseña, su stock calcula cero y no se pueden vender. Idéntico en la Mac y en la tienda.

## Cómo salió

De rebote, el 2026-09-22. Reconciliando el stock negativo en la tienda, el **Pants 3pz Álvaro Obregón El Carretón** talla 14 aguantó dos pasadas en −1: `stock_derivado` devuelve `None` cuando ninguna pieza de un grupo tiene esa talla, y `sincronizar_conjunto` se salta esos casos. Al arreglarlo (`5941316c`) y preguntar por todos los demás, aparecieron 36 más.

**Solo ese se notó porque se fue a negativo. Los otros 36 están callados** — en cero, que parece normal.

## Cómo verlos

```
Set-Location C:\Users\Pc\pos_uniformes; .\pos_uniformes\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from pos_uniformes.database.connection import get_session; from pos_uniformes.services import conjunto_service as cs; s=get_session(); [print('  ' + (p.nombre_base or p.nombre)[:46].ljust(47) + 'sin armar: ' + ', '.join(t)) for p in cs.conjuntos_activos(s) for t in [cs.tallas_sin_pieza(s, p.id)] if t]; s.close()"
```

## Son tres problemas distintos

### 1. Tallas del sistema equivocado (la mayoría)

**Chamarra Deportivo Narciso Mendoza** ofrece `CH, GD, MD` — pero sus dos piezas se venden por número (`4…18`). Lo mismo en Adolfo López Mateo, Palacio e Ignacio Ramírez López.

Al revés en bachillerato: las chamarras de **CBTIS 148, SABES, CECYTE, Conalep y UVEG** ofrecen `12` y `14`, y su Pants 2pz va por letra (`16, CH, MD, GD, EXG`).

> Probablemente son **tallas basura** que hay que quitarle al conjunto, no piezas que falte dar de alta. Pero eso lo decide Daniel: si de verdad vende esa chamarra en 12, entonces falta el pants en 12.

### 2. Una talla suelta que falta

Preescolares (Blanca Verónica, Frida Kahlo, Jean Piaget, Jorge Cantor, Patria): a la chamarra le falta la `10` y al 3pz la `2`. Francisco Villa e Himno Nacional: la `4`. Santa Rosa 238: la `12`.

Aquí sí huele a **pieza que falta dar de alta**, no a talla sobrante.

### 3. Receta mal armada — el caso feo

**Pants 3pz Álvaro Obregón El Carretón** no tiene *una* talla rota: tiene **nueve**, o sea todas. La razón:

| | |
|---|---|
| el conjunto ofrece | GD, 10, 12, 14, 16, 6, 8, CH, MD |
| Pants 2pz Álvaro Obregón El Carretón | 14, 16, 6, 8, 10, 12, GD, CH, MD |
| **Playera Deportiva** | **Uni** |

La receta le puso una **playera unitalla genérica**. Como ninguna talla del 3pz existe en una playera "Uni", **ninguna se puede armar**. No es una talla faltante: es que `armar_recetas` eligió mal la pieza. Debería apuntar a la playera deportiva **de esa escuela**, con tallas numéricas.

**Vale la pena revisar si `armar_recetas` hizo lo mismo en otros.**

## Lo resuelto el 2026-09-22 (`bf667d0a`)

**El caso 3 (receta mal armada) está cerrado**, y solo eran esos dos.

- **Candado en `proponer_receta`**: descarta una pieza que no comparte ninguna talla con el conjunto. Con él puesto, El Carretón propone sola su `Playera Blanca` propia y el preescolar dice `faltan=['Playera']` en vez de inventar.
- **`scripts/arreglar_alvaro_obregon.py`** (reporta; `--aplicar`), resuelto por nombre y no por id. Aplicado en la tienda:
  - El Carretón: receta rehecha. Verificado después — **todas sus tallas ya calculan**, y el número que tenían (2, 2, 2, 2, 5, 2) coincide exacto con lo derivado: era correcto, solo que el sistema no podía demostrarlo.
  - Preescolar: sin receta y **desactivado** (0 ventas, 0 existencia en la tienda). Esa escuela no vende playera, así que un 3pz ahí no es un 3pz.
  - Las dos chamarras duplicadas: fundidas, y apagada la pieza del uniforme que quedaba apuntando al fundido.

> [!note] La chamarra quedó en 20 y marcada para contar
> Al fundir, las existencias se suman: 10 + 10. Como pueden ser las mismas diez prendas contadas dos veces, sus 4 tallas quedaron como **nunca contadas** — salen en rojo y el kiosko las pide. Un número que se declara dudoso vale más que uno inventado que parece bueno.

---

## Qué hacer con las 35 que quedan

1. ~~Revisar el caso 3~~ — hecho, ver arriba.
2. Para los casos 1 y 2, ir escuela por escuela decidiendo **quitar la talla al conjunto** o **darla de alta en la pieza**. No se puede adivinar sin saber qué se vende de verdad.
3. Mientras tanto no rompe nada visible: esas tallas se ven en cero. Lo único que hacen es ensuciar el catálogo y, si alguna se va a negativo, aguantar las reconciliaciones.

---

> Encontrado: 2026-09-22 · Ver [[38 - Catálogo Fase 2 - Uniformes]] · [[39 - Brújula]] · [[19 - Deuda Técnica]]
