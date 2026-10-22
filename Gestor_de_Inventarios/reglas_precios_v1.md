# Prompt de Reglas de Precios

Usa este documento como especificacion operativa para una app que actualiza precios en `data/productos.db`.

> **Fuente de verdad (desde 2026-10-22):** los precios validos son los del PostgreSQL de la caja (PC de la tienda).
> `productos.db` y este documento se corrigen para igualar a la caja, nunca al reves.
> Toda subida nueva se aplica primero en la caja (con auditoria en `cambio_catalogo`) y despues se refleja aqui.
>
> Ultima actualizacion: 2026-10-22 — escaleras tomadas de la caja tras igualar 866 SKUs.

## Objetivo

Aplicar precios objetivo por categoria, nivel, familia y talla.

## Regla global obligatoria

Nunca bajar precios.

Formula obligatoria:

```text
precio_nuevo = MAX(precio_actual, precio_objetivo)
```

## Regla de lectura

- Si una linea dice `linea completa`, aplica a todas las tallas de esa familia.
- Si una familia o producto esta marcado como `excluido`, no se toca.
- Si un registro no coincide con ninguna regla, conservar el precio actual.
- Las lineas marcadas `precio especial en caja` son precios puestos a mano en el POS (ofertas o liquidaciones).
  Se respetan tal cual y no se heredan a otras escuelas ni tallas. Confirmar con Daniel antes de normalizarlos.

## Bandas de talla

- `Infantil`: `2, 4, 6, 8, 10`
- `Juvenil`: `12, 14, 16, 18`
- `Adulto`: `30, 32, 34, 36, 38, 40, 42, 44, CH, MD, GD, EXG`

## Orden sugerido de aplicacion

1. `Playeras`
2. `Sueter Basico`
3. `Sueter Oficial`
4. `Camisas`
5. `Chalecos`
6. `Faldas`
7. `Pantalon Basico`
8. `Chamarras`
9. `Pants 2pz y 3pz`

## 1. Playeras

### 1.1 Playera Deportiva

Aplicar por `tipo_pieza='Playera'`, `tipo_prenda='Deportivo'`, `nivel_educativo` y talla exacta.

| Nivel | Tallas | Precio objetivo |
|---|---|---:|
| Preescolar | `2, 4, 6, 8, 10` | 175 |
| Preescolar | `12, 14, 16` | 199 |
| Preescolar | `CH, MD, GD, EXG` | 219 |
| Primaria | `4, 6, 8, 10` | 199 |
| Primaria | `12, 14, 16` | 209 |
| Primaria | `CH` | 219 |
| Primaria | `MD` | 225 |
| Primaria | `GD, EXG` | 235 |
| Secundaria | `12, 14, 16` | 229 |
| Secundaria | `CH, MD, GD, EXG` | 239 |
| Bachillerato | `12, 14, 16` | 229 |
| Bachillerato | `CH, MD, GD, EXG` | 239 |

### 1.2 Playera Polo por escuela (Oficial)

Aplicar por `tipo_pieza='Playera'`, `tipo_prenda='Oficial'`, `nivel_educativo` y talla. Misma escalera que la deportiva de su nivel.

| Nivel | Tallas | Precio objetivo |
|---|---|---:|
| Primaria | `4, 6, 8, 10` | 199 |
| Primaria | `12, 14, 16` | 209 |
| Primaria | `CH` | 219 |
| Primaria | `MD` | 225 |
| Primaria | `GD, EXG` | 235 |
| Secundaria | `12, 14, 16` | 229 |
| Secundaria | `CH, MD, GD, EXG` | 239 |
| Bachillerato | `14, 16` | 229 |
| Bachillerato | `CH, MD, GD, EXG` | 239 |

Excepciones activas:

- `Conalep` y `SABES` en Bachillerato manejan `239` en linea completa (incluye 14 y 16).
- `CBTIS 148` Playera Deportiva Ad hoc: `150` linea completa — precio especial en caja.
- `Vicente Guerrero` Playera Blanca talla `4`: `89` — precio especial en caja (6 y 8 van a 175).
- `Jose Maria Morelos y Pavon` Polo talla `18`: `199` — precio especial en caja.
- `ESTV 663` Polo talla `32`: `219` — precio especial en caja.

## 2. Sueter Basico

Aplicar por `tipo_pieza='Suéter'` y `tipo_prenda='Básico'`.

Excluir:

- `Suéter Oferta Ad hoc Talla Uni`

Tabla:

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8` | 289 |
| `10, 12, 14, 16` | 299 |
| `28, 30, 32, 34` | 309 |
| `36, 38, 40, 42` | 315 |
| `44, 46` | 325 |

## 3. Sueter Oficial

Aplicar por `tipo_pieza='Suéter'`, `tipo_prenda='Oficial'`, `nivel_educativo` y talla.

| Nivel | Tallas | Precio objetivo |
|---|---|---:|
| Preescolar | `4, 6, 8, 10` | 299 |
| Primaria | `4, 6, 8, 10` | 299 |
| Primaria | `12, 14, 16` | 315 |
| Primaria | `18, 30, 32, 34, 36, 38` | 325 |
| Primaria | `40, 42` | 335 |
| Secundaria | `12, 14, 16, 18` | 325 |
| Secundaria | `30, 32, 34, 36, 38` | 345 |
| Secundaria | `40, 42, 44` | 355 |
| Bachillerato | `14, 16` | 325 |
| Bachillerato | `32, 34, 36, 38` | 345 |
| Bachillerato | `40, 42, 44` | 355 |

Excepciones activas:

- `UVEG` en `Bachillerato` maneja `355` para `14, 16`; `365` para `32, 34, 36, 38`; `375` para `40, 42` (subida 2026-10-22 por costo Martell).
- `Margarita Paz Paredes` en `Preescolar` maneja `315` para `4, 6, 8, 10`.
- `CBTIS 148` (Botones M y Cuello V H) maneja `200` en linea completa — precio especial en caja.

## 4. Camisas

### 4.1 Camisa Basica

Aplicar por `tipo_pieza='Camisa'`, `tipo_prenda='Básico'` y familia detectada desde `nombre`.

Familias validas:

- `Camisa Manga Corta Blanca`
- `Camisa Prowear Manga Corta Blanca`
- `Camisa Manga Larga H Blanca`
- `Camisa Manga Larga M Blanca`

#### Camisa Manga Corta Blanca

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8` | 89 |
| `10, 12, 14, 16` | 99 |
| `28, 30` | 115 |
| `32, 34` | 135 |
| `36, 38` | 145 |
| `40, 42` | 165 |

#### Camisa Prowear Manga Corta Blanca

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8` | 125 |
| `10, 12` | 145 |
| `14, 16` | 155 |
| `28, 30, 32, 34, 36, 38` | 165 |
| `40, 42` | 185 |

#### Camisa Manga Larga H Blanca

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 199 |
| `10, 12, 14, 16, 18` | 219 |
| `32, 34` | 239 |
| `36, 38` | 249 |
| `40, 42, 44, CH` | 259 |
| `MD` | 269 |
| `GD` | 279 |
| `EXG` | 289 |

#### Camisa Manga Larga M Blanca

| Tallas | Precio objetivo |
|---|---:|
| `30, CH` | 269 |
| `MD, GD` | 289 |
| `EXG` | 309 |

### 4.2 Camisa Oficial

Aplicar por `tipo_pieza='Camisa'`, `tipo_prenda='Oficial'`, `nivel_educativo` y talla.

| Nivel | Tallas | Precio objetivo |
|---|---|---:|
| Preescolar | linea completa | 139 |
| Primaria | `4, 6, 8, 10` | 215 |
| Primaria | `12, 14, 16` | 225 |
| Primaria | `32, 34, 36, 38` | 245 |
| Secundaria | linea completa | 265 |
| Bachillerato | linea completa | 265 |

Nota:

- Si aparece `Camisa Manga Larga Blanca` en `265` sin `nivel_educativo`, conservar en `265`.
- Las `Camisas Oficiales` ligadas a una escuela especifica se consideran excepciones operativas y deben respetarse como linea escolar.
- Excepciones activas detectadas: `Francisco Villa`, `Bicentenario` y `Conalep`.
- `CBTIS 148` Camisa Manga Corta Blanca: `200` linea completa — precio especial en caja.

## 5. Chalecos

### 5.1 Chaleco Basico

Aplicar por `tipo_pieza='Chaleco'`, `tipo_prenda='Básico'`.

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8` | 229 |
| `10, 12, 14, 16` | 239 |
| `28, 30, 32, 34` | 259 |
| `36, 38, 40` | 269 |
| `42, 44, 46` | 289 |

### 5.2 Chaleco Oficial

Aplicar por `tipo_pieza='Chaleco'`, `tipo_prenda='Oficial'`, `nivel_educativo` y talla.

| Nivel | Tallas | Precio objetivo |
|---|---|---:|
| Primaria | `2, 4, 6, 8` | 249 |
| Primaria | `10, 12, 14, 16` | 269 |
| Primaria | `32, 34` | 289 |
| Primaria | `36, 38, 40` | 299 |
| Primaria | `42` | 309 |
| Primaria | `CH, MD` | 299 |
| Primaria | `GD, EXG` | 309 |
| Secundaria | `12, 14, 16` | 269 |
| Secundaria | `30, 32, 34` | 289 |
| Secundaria | `36, 38, 40` | 299 |
| Secundaria | `42, 44` | 309 |
| Bachillerato | `14, 16` | 269 |
| Bachillerato | `32, 34` | 289 |
| Bachillerato | `36, 38, 40` | 299 |
| Bachillerato | `42, 44` | 309 |

Nota:

- `Huizache` (sin `nivel_educativo`) sigue la escalera de `Chaleco Oficial Primaria`: `6, 8` → 249; `10, 12, 14, 16` → 269; `34` → 289; `36` → 299. Ya no es excepcion.
- Las tallas `CH, MD, GD, EXG` de Primaria existen solo en `Colegio Motolinea`.
- Escuelas en Primaria con esta escalera: `Albino García Ramos`, `Colegio Motolinea`, `Francisco Villa`, `Himno Nacional`, `Ignacio Allende`, `Ignacio Zaragoza`, `Justo Sierra`, `Miguel Campuzano`, `Miguel Hidalgo`.
- Secundaria: `Práxedis Guerrero`, `Telesecundaria 512`. Bachillerato: `SABES`.

## 6. Faldas

### 6.1 Falda Basica

Aplicar por `tipo_pieza='Falda'`, `tipo_prenda='Básico'` y familia detectada desde `nombre`.

#### Linea Gales

Aplica a:

- `Falda Gales azul`
- `Falda Gales rojo`
- `Falda Gales verde`

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 195 |
| `10, 12` | 205 |
| `14, 16` | 215 |
| `28, 30, 32, 34` | 225 |
| `36, 38, 40, 42` | 235 |
| `44` | 245 |

#### Linea Escolar

Aplica a:

- `Falda Escolar Azul Marino`
- `Falda Cuatro tablas ...` (Azul Rey, Blanca, Café, Verde)
- `Falda Vino`

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8, 10, 12, 14` | 195 |
| `16, 18, 20, 28, 30` | 205 |
| `32, 34` | 215 |
| `36, 38` | 225 |
| `40, 42` | 235 |

#### Falda Escoces

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 215 |
| `10, 12, 14, 16` | 235 |
| `28, 30, 32, 34` | 245 |
| `36, 38` | 255 |
| `40, 42` | 265 |

#### Falda Gris

Aplica a:

- `Falda Gris claro`
- `Falda Gris obscuro`

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8, 10, 12, 14, 16` | 265 |
| `28, 30, 32, 34` | 275 |
| `36, 38` | 285 |
| `40, 42` | 295 |

### 6.2 Falda Oficial

Aplicar por `tipo_pieza='Falda'`, `tipo_prenda='Oficial'` y familia/nivel.

| Familia o nivel | Tallas | Precio objetivo |
|---|---|---:|
| `Preescolar Falda Azul` | linea completa | 239 |
| `Bachillerato SABES` | `10, 12, 14, 16, 28, 30, 32, 34` | 285 |
| `Bachillerato SABES` | `36, 38, 40, 42` | 295 |
| `Bachillerato Conalep` | `14, 16, 28, 30, 32, 34` | 285 |
| `Bachillerato Conalep` | `36, 38, 40, 42` | 295 |
| `Pata de gallo (Colegio Motolinea)` | `4, 6, 8` | 209 |
| `Pata de gallo (Colegio Motolinea)` | `10, 12` | 219 |
| `Pata de gallo (Colegio Motolinea)` | `14, 16` | 229 |
| `Pata de gallo (Colegio Motolinea)` | `28, 30, 32, 34` | 249 |
| `Pata de gallo (Colegio Motolinea)` | `36, 38` | 259 |
| `Sin nivel Pgallo cafe` | `12` | 219 |
| `Sin nivel Pgallo cafe` | `14, 16` | 229 |
| `Sin nivel Pgallo cafe` | `28, 30, 32, 34` | 249 |
| `Sin nivel Pgallo cafe` | `36, 38, 40, 42` | 259 |

Excepcion activa:

- `Margarita Paz Paredes` Falda Azul Preescolar tallas `4, 6, 8`: `89` en caja — precio especial en caja (la regla de linea es 239).

## 7. Pantalon Basico

Aplicar por `tipo_pieza='Pantalón'`, `tipo_prenda='Básico'` y familia detectada desde `nombre`.

### 7.1 Vestir

Aplica a `Pantalón Vestir ...` en Azul Marino, Azul Rey, Blanco, Café, Caqui, Gris, Negro, Verde, Verde olivo y Vino.

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 235 |
| `10, 12` | 245 |
| `14, 16` | 255 |
| `18, 20` | 265 |
| `28, 30` | 275 |
| `32, 34` | 285 |
| `36, 38` | 295 |
| `40, 42, 44` | 315 |

#### Vestir Gris claro / Gris obscuro

Misma escalera mas 14.

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8` | 249 |
| `10, 12` | 259 |
| `14, 16` | 269 |
| `18, 20` | 279 |
| `28, 30` | 289 |
| `32, 34` | 299 |
| `36, 38` | 309 |
| `40, 42, 44` | 329 |

#### Gales (azul, rojo, verde)

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 5, 6, 8` | 235 |
| `10, 12, 14, 16` | 245 |
| `18, 20, 28, 30` | 265 |
| `32, 34` | 285 |
| `36, 38` | 295 |
| `40, 42, 44` | 315 |

### 7.2 Escoces / Gabardina

#### Escoces

| Tallas | Precio objetivo |
|---|---:|
| `2, 3, 4, 6, 8` | 199 |
| `10, 12, 14, 16` | 239 |
| `28, 30, 32` | 269 |

#### Gabardina Negro

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8, 10, 12, 14, 16` | 219 |

### 7.3 Vestir Pata de gallo

| Tallas | Precio objetivo |
|---|---:|
| `4, 6, 8` | 235 |
| `10, 12, 14, 16` | 245 |
| `20, 28, 30` | 265 |
| `32, 34` | 285 |
| `36, 38` | 295 |
| `40, 42` | 315 |

## 7B. Pantalon Oficial

Aplicar por `tipo_pieza='Pantalón'` y `tipo_prenda='Oficial'`.

Familia detectada:

- `Pantalón Escoces`

Tabla:

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 239 |

Notas:

- esta linea ya viene completamente plana y ordenada
- no requiere escalera adicional por ahora
- si aparecen mas tallas oficiales en el futuro, revisar aparte antes de heredar reglas de `Pantalón Básico`
- aplicar siempre `MAX(precio_actual, precio_objetivo)`

## 7C. Jumper Basico

Aplicar por `tipo_pieza='Jumper'` y `tipo_prenda='Básico'`.

Tabla:

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 249 |
| `10, 12, 14, 16` | 269 |
| `28, 30` | 289 |
| `32, 34` | 309 |
| `36, 38` | 319 |
| `40, 42` | 329 |

Notas:

- esta linea ya viene completamente ordenada
- la tabla se conserva como regla formal para detectar rezagos futuros
- no requiere ajuste adicional por ahora
- aplicar siempre `MAX(precio_actual, precio_objetivo)`

## 8. Chamarras

Aplicar por `tipo_pieza='Chamarra'`.

### 8.1 Chamarra Basica

Aplicar por `tipo_prenda='Básico'` y familia detectada desde `nombre`.

#### Chamarra Liso

Aplica a:

- `Chamarra Liso ...`

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 175 |
| `10, 12` | 195 |
| `14, 16` | 215 |
| `28, CH, MD, GD, EXG` | 235 |

#### Chamarra Punto

Aplica a:

- `Chamarra Punto ...`

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 275 |
| `10, 12, 14, 16` | 295 |
| `28, CH` | 385 |
| `MD, GD, EXG` | 395 |

Notas:

- `Chamarra Basica` ya viene ordenada y esta tabla sirve como regla formal para detectar rezagos futuros.
- No heredar reglas de `Chamarra Basica` a `Chamarra Deportiva`.

### 8.2 Chamarra Deportiva

Aplicar por `tipo_prenda='Deportivo'`, `nivel_educativo` y `escudo='Con Escudo'`.

Regla de negocio:

- La `Chamarra Deportiva` se considera `Con Escudo` como regla general de operacion.
- No mostrar ni heredar `Sin Escudo` como opcion general.
- Si aparece una chamarra deportiva sin escudo en el futuro, no actualizar automaticamente; revisar aparte.
- Si un plantel ya esta arriba del objetivo, se respeta con `MAX(precio_actual, precio_objetivo)`.

Tabla base:

| Nivel | Precio objetivo |
|---|---:|
| Preescolar | 315 |
| Primaria | 335 |
| Secundaria | 385 |
| Bachillerato | 385 |

Notas operativas:

- Hoy en la base la `Chamarra Deportiva` existe casi por completo como `Con Escudo`.
- Para consulta rapida y para la app, manejar esta linea solo como `Con Escudo`.
- No hay excepciones activas en esta linea al cierre actual.

### 8.3 Alta de escuelas faltantes para Chamarras Deportivas

No crear precios por escuela como regla principal.

Usar esta jerarquia:

1. Si existe regla especifica por escuela, usarla.
2. Si no existe, heredar desde `nivel_educativo` con `Con Escudo`.
3. Si no existe coincidencia, conservar el precio actual y no inventar precio.

Paquetes sugeridos de tallas al dar de alta una escuela nueva:

- `Preescolar`: `4, 6, 8`
- `Primaria`: `4, 6, 8, 10, 12, 14, 16, CH, MD, GD`
- `Secundaria`: `12, 14, 16, CH, MD, GD, EXG`
- `Bachillerato`: `12, 14, 16, CH, MD, GD, EXG`

Escuelas que hoy no tienen `Chamarra Deportiva` y pueden heredarse desde plantilla:

- `Preescolar`: `Sor Juana Inés de la Cruz`, `Vidal Acolcer`
- `Primaria`: `Adolfo Lopez Mateo`, `Alvaro Obregon`, `Colegio Motolinea`, `Huizache`, `Ignacio Zaragoza`, `Narciso Mendoza`, `Palacio`, `Vicente Guerrero`
- `Secundaria`: `ESTV 663`, `Santa Rosa 238`, `Telesecundaria 600`

## 9. Pants 2pz y 3pz Deportivo

Aplicar por `tipo_pieza IN ('Pants 2pz','Pants 3pz')`, `tipo_prenda='Deportivo'`, `nivel_educativo` y talla exacta.

### Preescolar

| Tallas | 2 piezas | 3 piezas |
|---|---:|---:|
| `2, 4, 6, 8, 10` | 415 | 515 |

### Primaria

| Tallas | 2 piezas | 3 piezas |
|---|---:|---:|
| `4, 6, 8, 10, 12` | 485 | 585 |
| `14, 16, 18` | 495 | 595 |
| `CH, MD` | 585 | 685 |
| `GD` | 595 | 695 |

### Secundaria

| Tallas | 2 piezas | 3 piezas |
|---|---:|---:|
| `10, 12` | 595 | 695 |
| `14, 16` | 605 | 705 |
| `CH, MD, GD, EXG` | 615 | 715 |

### Bachillerato

| Tallas | 2 piezas | 3 piezas |
|---|---:|---:|
| `16` | 615 | 715 |
| `CH, MD, GD, EXG` | 615 | 715 |

Excepciones activas:

- `UVEG` Bachillerato: 2pz `690`, 3pz `790` en linea completa.
- `CBTIS 148` Bachillerato 2pz: `300` linea completa — precio especial en caja.
- `Vicente Guerrero` Preescolar 2pz tallas `4, 6, 8`: `89` — precio especial en caja.

## 9B. Pants 2pz Basico (Liso)

Aplicar por `tipo_pieza='Pants 2pz'`, `tipo_prenda='Básico'` y familia desde `nombre`.

#### Liso (Azul Marino, Azul Rey, Rojo, Verde, Vino)

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8, 10, 12` | 175 |
| `14, 16` | 190 |
| `28, CH` | 315 |
| `MD` | 325 |
| `GD` | 335 |
| `EXG` | 345 |

#### Liso Doble raya

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 250 |
| `10, 12, 14, 16` | 265 |
| `28, CH` | 315 |
| `MD` | 325 |
| `GD` | 335 |
| `EXG` | 345 |

Nota:

- Los 175/190 infantiles y juveniles del Liso vienen asi de la caja (antes 250/265 en SQLite). Quedan apenas arriba del
  `Pants Suelto Liso` (165/180). Revisar si es intencional.

## 10. Pants Suelto Basico

Aplicar por `tipo_pieza='Pants Suelto'`, `tipo_prenda='Básico'` y `atributo`.

### Liso

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 165 |
| `10, 12, 14, 16` | 180 |
| `28, CH` | 205 |
| `MD` | 215 |
| `GD` | 225 |
| `EXG` | 235 |

### Punto

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 249 |
| `10, 12, 14, 16` | 269 |
| `28, CH` | 309 |
| `MD, GD` | 319 |
| `EXG` | 339 |

## 10B. Pants Suelto por escuela (Deportivo)

Aplicar por `tipo_pieza='Pants Suelto'`, `tipo_prenda='Deportivo'` y `nivel_educativo`.

| Nivel | Tallas | Precio objetivo |
|---|---|---:|
| Preescolar | linea completa | 239 |
| Bachillerato | linea completa | 289 |

Escuelas: Preescolar `Frida Kahlo`, `Margarita Paz Paredes`, `Patria`, `Álvaro Obregón`; Bachillerato `CBTIS 148`, `Conalep`, `SABES`, `UVEG`.

## 11. Malla Escolar

Aplicar por `tipo_pieza='Malla'`, `atributo='Escolar'`.

| Tallas | Precio objetivo |
|---|---:|
| `0-0, 0-2, 3-5, 6-8` | 109 |
| `9-12` | 129 |
| `13-18, CH-MD, GD-EXG, Dama` | 139 |

## 12. Accesorios

Aplicar por `tipo_pieza` y `escuela_id IS NULL`.

| Pieza | Atributo | Precio objetivo |
|---|---|---:|
| `Calceta` | `Escolar` | 49 |
| `Guante` | `Escolta` | 49 |
| `Corbata` | — | 70 |
| `Corbatín` | — | 70 |
| `Moño` | — | 70 |
| `Boina` | `Escolta` | 85 |

### Playera Polo Blanca

Aplicar por `tipo_pieza='Playera'`, `atributo='Polo'`, `escuela_id IS NULL`.

| Tallas | Precio objetivo |
|---|---:|
| `2, 4, 6, 8` | 135 |
| `10, 12` | 145 |
| `14, 16, 18` | 155 |
| `28, 30, 32, 34, 36, 38` | 170 |
| `40, 42` | 180 |
| `CH, MD` | 185 |
| `GD, EXG` | 195 |

## 13. Bata

Aplicar por `tipo_pieza='Bata'`.

| Tipo | Tallas | Precio objetivo |
|---|---|---:|
| Infantil | Uni | 65 |
| Manga Corta | `12 – 46` | 395 |
| Manga Larga | `12 – 46` | 365 |

Notas:

- La Bata Infantil es talla única; no aplicar escalera adicional.
- No heredar precios de Bata a otras prendas.
- La Manga Larga esta en 365 en la caja (SQLite traia 439). Si debe quedar arriba de la Manga Corta, subirla primero en la caja.

## Excepciones y conservaciones explicitas

- `Suéter Oferta Ad hoc Talla Uni` se conserva en `199`.
- Si una app no puede detectar con certeza la familia desde `nombre`, no debe actualizar ese registro.
- Todo registro sin coincidencia exacta con las reglas debe conservar su precio actual.

## Precios especiales en caja (resumen)

Precios puestos a mano en el POS que no siguen la escalera de su familia. Se respetan y no se heredan.

| Escuela / prenda | Tallas | Precio en caja | Regla de linea |
|---|---|---:|---:|
| `CBTIS 148` Suéter B y V | linea completa | 200 | 325–355 |
| `CBTIS 148` Camisa Manga Corta | linea completa | 200 | 265 |
| `CBTIS 148` Playera Deportiva Ad hoc | linea completa | 150 | 229–239 |
| `CBTIS 148` Pants 2pz Deportivo | linea completa | 300 | 615 |
| `Vicente Guerrero` Pants 2pz | `4, 6, 8` | 89 | 415 |
| `Vicente Guerrero` Playera Blanca | `4` | 89 | 175 |
| `Margarita Paz Paredes` Falda Azul | `4, 6, 8` | 89 | 239 |
| `Jose Maria Morelos y Pavon` Polo | `18` | 199 | 209 |
| `ESTV 663` Polo | `32` | 219 | 239 |

## Instruccion final para la app

Aplica todas las tablas anteriores usando coincidencia por:

1. `tipo_pieza`
2. `tipo_prenda`
3. `nivel_educativo` cuando exista
4. `escudo` cuando la regla lo requiera
5. familia inferida desde `nombre` cuando la regla lo requiera
6. talla o banda de talla

Y siempre cerrar con:

```text
precio_nuevo = MAX(precio_actual, precio_objetivo)
```
