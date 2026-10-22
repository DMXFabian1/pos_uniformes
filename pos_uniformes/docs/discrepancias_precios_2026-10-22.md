# Discrepancias de precios SQLite ↔ Caja (22-oct-2026)

Comparación de `Gestor_de_Inventarios/data/productos.db` (4,032 SKUs con precio) contra `variante.precio_venta`
en el PostgreSQL de la tienda (192.168.0.10), hecha desde la Mac en LAN. Detalle completo por SKU en
`discrepancias_precios_2026-10-22.csv` (columnas: caso, sku, producto, talla, sqlite, caja, diferencia, último cambio en caja, stock).

| Situación | SKUs |
|---|---:|
| Iguales | 3,139 |
| SQLite más alto (`SQLITE_MAYOR`) — `sincronizar_precios_postgres.py` los **subiría** en la caja | 287 |
| Caja más alta (`CAJA_MAYOR`) — SQLite está atrasado; el script los omite | 579 |
| En SQLite pero sin SKU en la caja (`SIN_MATCH`) | 27 |

> [!warning] No correr `sincronizar_precios_postgres.py` hasta revisar la sección SQLite más alto.
> Al cierre de la sesión 2026-04-23 había 0 discrepancias. Desde entonces se cambiaron precios directamente en el POS
> (84 SKUs en julio, 430 en septiembre, 47 en octubre) sin pasar a SQLite, y SQLite trae subidas que la caja no tiene.

## Qué hacer con cada grupo

1. **CAJA_MAYOR (579):** la caja es lo que se cobra hoy. Lo razonable es traer esos precios a SQLite (SQLite nunca baja,
   así que es compatible con la regla) y actualizar `reglas_precios_v1.md` donde la escalera cambió. Candidatos a nueva regla:
   pantalones de vestir (+10 a +14), chalecos oficiales por escuela (ahora 249–309), polos por escuela (229–239), faldas (+4 a +20).
2. **SQLITE_MAYOR (287):** revisar producto por producto antes de sincronizar. Varios precios de la caja parecen ofertas puestas
   a mano (CBTIS 148 en 200, Pants 2pz Deportivo CBTIS en 300, Short Deportivo en 89) y otros son escaleras de SQLite que nunca
   llegaron a la caja (Falda Cuatro Tablas, Falda Vino, Pants 2pz lisos, Bata). Lo que se confirme se aplica con el script en la PC.
3. **SIN_MATCH (27):** SKUs que existen en el Gestor y no en el POS. Decidir si se dan de alta en la caja o se retiran del Gestor.

### SQLite más alto — el sync los subiría en la caja

287 SKUs en 61 productos.

| Producto | SKUs | SQLite | Caja | Último cambio en caja |
|---|---:|---|---|---|
| Bata Manga Larga Blanca | 14 | 439 | 365 | 2026-10-17 |
| Falda Vino | 12 | 199–235 | 195–225 | 2026-09-22 |
| Falda Cuatro Tablas Azul Rey | 9 | 205–235 | 195–225 | 2026-07-22 |
| Falda Cuatro Tablas Blanca | 9 | 205–235 | 195–225 | 2026-07-22 |
| Falda Cuatro Tablas Café | 9 | 205–235 | 195–225 | 2026-07-22 |
| Falda Cuatro Tablas Verde | 9 | 205–235 | 195–225 | 2026-07-22 |
| Suéter Botones M Rojo CBTIS 148 | 9 | 325–355 | 200 | 2026-09-21 |
| Suéter Cuello V H Rojo CBTIS 148 | 9 | 325–355 | 200 | 2026-09-13 |
| Camisa Manga Corta Blanca CBTIS 148 | 8 | 265 | 200 | 2026-10-16 |
| Pants 2pz Deportivo Adolfo López Mateo | 8 | 575–595 | 485–495 | 2026-09-14 |
| Pants 2pz Deportivo Álvaro Obregón | 8 | 445 | 415 | 2026-09-22 |
| Pants 2pz Liso Azul Marino | 8 | 250–265 | 175–190 | 2026-10-21 |
| Pants 2pz Liso Azul Rey | 8 | 250–265 | 175–190 | 2026-10-06 |
| Pants 2pz Liso Rojo | 8 | 250–265 | 175–190 | 2026-10-18 |
| Pants 2pz Liso Verde | 8 | 250–265 | 175–190 | 2026-10-19 |
| Pants 2pz Liso Vino | 8 | 250–265 | 175–190 | 2026-10-17 |
| Short Deportivo | 7 | 175–445 | 89 | 2026-04-24 |
| Playera Deportiva CBTIS 148 | 6 | 229–239 | 150 | 2026-10-12 |
| Pants 2pz Deportivo CBTIS 148 | 5 | 615 | 300 | 2026-09-21 |
| Pants 2pz Margarita Paz Paredes | 5 | 445 | 415 | 2026-09-14 |
| Pants 3pz Margarita Paz Paredes | 5 | 545 | 515 | 2026-09-22 |
| Pants 2pz Deportivo Blanca Verónica Soto Martínez Príncipes | 4 | 445 | 415 | 2026-10-07 |
| Pants 2pz Deportivo Frida Kahlo | 4 | 445 | 415 | 2026-10-11 |
| Pants 2pz Deportivo Jean Piaget | 4 | 445 | 415 | 2026-09-22 |
| Pants 2pz Deportivo Jorge Cantor | 4 | 445 | 415 | 2026-09-19 |
| Pants 2pz Deportivo Patria | 4 | 445 | 415 | 2026-09-19 |
| Pants 2pz Deportivo Sor Juana Inés de la Cruz | 4 | 515 | 415 | 2026-09-19 |
| Pants 2pz Vidal Alcocer | 4 | 445 | 415 | 2026-09-19 |
| Pants 3pz Deportivo Blanca Verónica Soto Martínez Príncipes | 4 | 545 | 515 | 2026-10-07 |
| Pants 3pz Deportivo Frida Kahlo | 4 | 545 | 515 | 2026-10-11 |
| Pants 3pz Deportivo Jean Piaget | 4 | 545 | 515 | 2026-10-19 |
| Pants 3pz Deportivo Jorge Cantor | 4 | 545 | 515 | 2026-09-22 |
| Pants 3pz Deportivo Patria | 4 | 545 | 515 | 2026-10-01 |
| Pants 3pz Deportivo Álvaro Obregón | 4 | 545 | 515 | 2026-09-20 |
| Playera Deportiva Blanca Verónica Soto Martínez Príncipes | 4 | 195 | 175 | 2026-09-27 |
| Playera Deportiva Frida Kahlo | 4 | 195 | 175 | 2026-10-11 |
| Playera Deportiva Jorge Cantor | 4 | 195 | 175 | 2026-09-19 |
| Playera Deportiva Patria | 4 | 195 | 175 | 2026-10-01 |
| Playera Deportiva Sor Juana Inés de la Cruz | 4 | 195 | 175 | 2026-09-19 |
| Chaleco Azul Albino García Ramos | 3 | 290–300 | 289–299 | 2026-09-14 |
| Chaleco Azul Marino Francisco Villa | 3 | 290–300 | 289–299 | 2026-09-19 |
| Chaleco Azul Marino Miguel Hidalgo | 3 | 290–300 | 289–299 | 2026-09-11 |
| Chaleco Rojo Ignacio Allende | 3 | 290–300 | 289–299 | 2026-09-19 |
| Chaleco Azul Marino SABES | 2 | 285 | 269 | 2026-09-13 |
| Chaleco Beige Himno Nacional | 2 | 290–300 | 289–299 | 2026-09-13 |
| Chaleco Rojo Justo Sierra | 2 | 290–300 | 289–299 | 2026-09-13 |
| Chamarra Punto Azul Marino | 2 | 405–415 | 395 | 2026-09-22 |
| Chamarra Punto Azul Rey | 2 | 405–415 | 395 | 2026-07-22 |
| Chamarra Punto Bicolor | 2 | 405–415 | 395 | 2026-07-22 |
| Chamarra Punto Doble Raya | 2 | 405–415 | 395 | 2026-07-22 |
| Chamarra Punto Gris | 2 | 405–415 | 395 | 2026-07-22 |
| Chamarra Punto Raya Roja | 2 | 405–415 | 395 | 2026-07-22 |
| Chamarra Punto Rojo | 2 | 405–415 | 395 | 2026-09-22 |
| Chamarra Punto Verde | 2 | 405–415 | 395 | 2026-07-22 |
| Chamarra Punto Vino | 2 | 405–415 | 395 | 2026-07-22 |
| Suéter Botones M Azul Marino Club Rotario | 2 | 345 | 325 | 2026-09-13 |
| Chaleco Azul Marino Miguel Campuzano | 1 | 290 | 289 | 2026-09-11 |
| Chaleco Blanco Ignacio Zaragoza | 1 | 290 | 289 | 2026-09-19 |
| Falda Gales Rojo | 1 | 245 | 235 | 2026-07-22 |
| Pants 2pz Liso Doble Raya | 1 | 265 | 250 | 2026-07-22 |
| Suéter Cuello V H Azul Marino Club Rotario | 1 | 345 | 325 | 2026-09-13 |


### Caja más alta — SQLite atrasado

579 SKUs en 143 productos.

| Producto | SKUs | SQLite | Caja | Último cambio en caja |
|---|---:|---|---|---|
| Pantalón Vestir Gris Obscuro | 18 | 235–315 | 249–329 | 2026-10-11 |
| Pantalón Vestir Gris Claro | 17 | 235–315 | 249–329 | 2026-10-06 |
| Falda Escolar Pata de Gallo Colegio Motolinea | 13 | 205–255 | 209–259 | 2026-09-22 |
| Chaleco Azul Marino Colegio Motolinea | 11 | 240–270 | 249–309 | 2026-09-22 |
| Chaleco Verde Práxedis Guerrero Secundaria | 11 | 245–275 | 269–309 | 2026-09-14 |
| Falda Escolar Pgallo Cafe | 11 | 205–255 | 219–259 | 2026-07-22 |
| Chaleco Azul Albino García Ramos | 10 | 240–290 | 249–309 | 2026-09-19 |
| Chaleco Azul Marino Miguel Hidalgo | 10 | 240–290 | 249–309 | 2026-09-13 |
| Falda SABES | 10 | 270–285 | 285–295 | 2026-09-19 |
| Chaleco Azul Marino Telesecundaria 512 | 9 | 245–275 | 269–309 | 2026-09-14 |
| Chaleco Rojo Ignacio Allende | 9 | 240–290 | 249–299 | 2026-09-19 |
| Chaleco Azul Marino Francisco Villa | 8 | 240–290 | 249–299 | 2026-09-19 |
| Chaleco Beige Himno Nacional | 8 | 240–290 | 249–299 | 2026-10-11 |
| Chaleco Blanco Ignacio Zaragoza | 8 | 240–260 | 249–269 | 2026-10-14 |
| Chaleco Negro Huizache | 8 | 240–270 | 249–299 | 2026-09-22 |
| Chaleco Rojo Justo Sierra | 8 | 240–290 | 249–299 | 2026-09-13 |
| Falda Escoces | 8 | 205–215 | 215–235 | 2026-10-20 |
| Chaleco Azul Marino Miguel Campuzano | 7 | 240–270 | 249–289 | 2026-09-13 |
| Chaleco Azul Marino SABES | 7 | 285–295 | 289–309 | 2026-09-13 |
| Pantalón Escoces | 7 | 235–265 | 239–269 | 2026-09-22 |
| Playera Polo Blanca ESTV 663 | 7 | 219 | 229–239 | 2026-09-19 |
| Pantalón Vestir Caqui | 6 | 245–295 | 255–315 | 2026-10-16 |
| Pants Suelto Azul Marino Conalep | 6 | 285 | 289 | 2026-10-06 |
| Pants Suelto Azul Marino SABES | 6 | 285 | 289 | 2026-10-03 |
| Pants Suelto Rojo CBTIS 148 | 6 | 285 | 289 | 2026-09-13 |
| Playera Polo Blanca SABES | 6 | 219 | 239 | 2026-10-17 |
| Playera Polo CECYTE | 6 | 219 | 229–239 | 2026-09-22 |
| Playera Polo Conalep | 6 | 229–235 | 239 | 2026-10-18 |
| Pantalón Vestir Azul Marino | 5 | 245–295 | 255–315 | 2026-10-20 |
| Pantalón Vestir Azul Rey | 5 | 245–295 | 255–315 | 2026-07-22 |
| Pantalón Vestir Blanco | 5 | 245–295 | 255–315 | 2026-09-22 |
| Pantalón Vestir Café | 5 | 245–295 | 255–315 | 2026-07-22 |
| Pantalón Vestir Gris | 5 | 245–295 | 255–315 | 2026-07-22 |
| Pantalón Vestir Negro | 5 | 245–295 | 255–315 | 2026-09-22 |
| Pantalón Vestir Pata de Gallo | 5 | 245–255 | 265–315 | 2026-07-22 |
| Pantalón Vestir Verde | 5 | 245–295 | 255–315 | 2026-09-22 |
| Pantalón Vestir Verde Olivo | 5 | 245–295 | 255–315 | 2026-07-22 |
| Pantalón Vestir Vino | 5 | 245–295 | 255–315 | 2026-07-22 |
| Pants 2pz Deportivo UVEG | 5 | 650 | 690 | 2026-10-21 |
| Pants 3pz Deportivo UVEG | 5 | 750 | 790 | 2026-10-21 |
| Pants Suelto Azul Marino UVEG | 5 | 285 | 289 | 2026-09-14 |
| Suéter Botones M Azul Marino Álvaro Obregón El Carretón | 5 | 290–300 | 299–325 | 2026-07-22 |
| Suéter Cuello V H Azul Marino Álvaro Obregón El Carretón | 5 | 290–300 | 299–325 | 2026-07-22 |
| Pants Suelto Frida Kahlo | 4 | 235 | 239 | 2026-10-07 |
| Pants Suelto Margarita Paz Paredes | 4 | 235 | 239 | 2026-09-14 |
| Pants Suelto Patria | 4 | 235 | 239 | 2026-10-01 |
| Pants Suelto Álvaro Obregón | 4 | 235 | 239 | 2026-09-22 |
| Playera Polo Gris Albino García Ramos | 4 | 199–215 | 209–219 | 2026-09-19 |
| Playera Polo Gris Ignacio Allende | 4 | 199–215 | 209–219 | 2026-09-19 |
| Suéter Azul Marino Colegio Motolinea | 4 | 290–295 | 299 | 2026-09-22 |
| Suéter Botones M Azul Albino García Ramos | 4 | 290–295 | 299 | 2026-09-19 |
| Suéter Botones M Azul Marino Club Rotario | 4 | 290–295 | 299 | 2026-09-14 |
| Suéter Botones M Azul Marino Francisco Villa | 4 | 290–295 | 299 | 2026-10-14 |
| Suéter Botones M Azul Marino Miguel Campuzano | 4 | 290–295 | 299 | 2026-09-13 |
| Suéter Botones M Azul Marino Miguel Hidalgo | 4 | 290–295 | 299 | 2026-09-13 |
| Suéter Botones M Blanca Verónica Soto Martínez Príncipes | 4 | 290 | 299 | 2026-09-19 |
| Suéter Botones M Frida Kahlo | 4 | 290 | 299 | 2026-10-06 |
| Suéter Botones M Jorge Cantor | 4 | 290 | 299 | 2026-09-28 |
| Suéter Botones M Patria | 4 | 290 | 299 | 2026-09-18 |
| Suéter Botones M Rojo Benito Juárez | 4 | 290–295 | 299 | 2026-09-23 |
| Suéter Botones M Rojo Ignacio Allende | 4 | 290–295 | 299 | 2026-10-13 |
| Suéter Botones M Rojo José María Morelos y Pavón | 4 | 290–295 | 299 | 2026-09-19 |
| Suéter Botones M Sor Juana Inés de la Cruz | 4 | 290 | 299 | 2026-09-20 |
| Suéter Botones M Vino Práxedis G Guerrero | 4 | 290–295 | 299 | 2026-09-14 |
| Suéter Botones M Vino Vicente Guerrero | 4 | 290–295 | 299 | 2026-09-14 |
| Suéter Cuello V H Azul Albino García Ramos | 4 | 290–295 | 299 | 2026-09-19 |
| Suéter Cuello V H Azul Marino Club Rotario | 4 | 290–295 | 299 | 2026-09-14 |
| Suéter Cuello V H Azul Marino Francisco Villa | 4 | 290–295 | 299 | 2026-09-19 |
| Suéter Cuello V H Azul Marino Miguel Campuzano | 4 | 290–295 | 299 | 2026-10-14 |
| Suéter Cuello V H Azul Marino Miguel Hidalgo | 4 | 290–295 | 299 | 2026-09-13 |
| Suéter Cuello V H Blanca Verónica Soto Martínez Príncipes | 4 | 290 | 299 | 2026-10-12 |
| Suéter Cuello V H Frida Kahlo | 4 | 290 | 299 | 2026-09-13 |
| Suéter Cuello V H Jorge Cantor | 4 | 290 | 299 | 2026-09-19 |
| Suéter Cuello V H Patria | 4 | 290 | 299 | 2026-09-18 |
| Suéter Cuello V H Rojo Benito Juárez | 4 | 290–295 | 299 | 2026-09-22 |
| Suéter Cuello V H Rojo Ignacio Allende | 4 | 290–295 | 299 | 2026-09-19 |
| Suéter Cuello V H Rojo José María Morelos y Pavón | 4 | 290–295 | 299 | 2026-09-19 |
| Suéter Cuello V H Sor Juana Inés de la Cruz | 4 | 290 | 299 | 2026-09-19 |
| Suéter Cuello V H Vino Práxedis G Guerrero | 4 | 290–295 | 299 | 2026-09-14 |
| Suéter Cuello V H Vino Vicente Guerrero | 4 | 290–295 | 299 | 2026-09-14 |
| Chaleco Claudia U Azul Marino | 3 | 269 | 289 | 2026-09-21 |
| Chaleco Claudia U Blanco | 3 | 269 | 289 | 2026-09-21 |
| Chaleco Claudia U Negro | 3 | 269 | 289 | 2026-09-21 |
| Chaleco Claudia U Rojo | 3 | 269 | 289 | 2026-09-21 |
| Chaleco Claudia U Verde | 3 | 269 | 289 | 2026-09-22 |
| Chaleco Claudia U Vino | 3 | 269 | 289 | 2026-09-21 |
| Pants 2pz Álvaro Obregón El Carretón | 3 | 485–585 | 495–595 | 2026-07-22 |
| Playera Polo José María Morelos y Pavón | 3 | 199 | 209 | 2026-09-19 |
| Suéter Botones Azul Marino Ignacio Ramírez López | 3 | 290–295 | 299 | 2026-09-13 |
| Suéter Botones M Azul Adolfo López Mateo | 3 | 290–295 | 299 | 2026-09-14 |
| Suéter Botones M Rojo Justo Sierra | 3 | 295 | 299 | 2026-09-13 |
| Suéter Cuello V Azul Marino Ignacio Ramírez López | 3 | 290–295 | 299 | 2026-09-13 |
| Suéter Cuello V H Azul Adolfo López Mateo | 3 | 290–295 | 299 | 2026-09-14 |
| Suéter Cuello V H Rojo Justo Sierra | 3 | 295 | 299 | 2026-10-05 |
| Suéter Cuello V H Verde Práxedis Guerrero Secundaria | 3 | 345 | 355 | 2026-09-14 |
| Pantalón Gales Azul | 2 | 295 | 315 | 2026-09-22 |
| Pantalón Gales Rojo | 2 | 295 | 315 | 2026-07-22 |
| Pantalón Gales Verde | 2 | 295 | 315 | 2026-09-24 |
| Playera Blanca Álvaro Obregón El Carretón | 2 | 219 | 225–235 | 2026-07-22 |
| Playera Deportiva Club Rotario | 2 | 219 | 225–235 | 2026-09-13 |
| Playera Deportiva Emiliano Zapata | 2 | 219 | 225–235 | 2026-09-13 |
| Playera Deportiva Francisco Villa | 2 | 219 | 225–235 | 2026-09-14 |
| Suéter Botones M Azul Marino Telesecundaria 512 | 2 | 345 | 355 | 2026-09-14 |
| Suéter Botones M Telesecundaria 600 | 2 | 290–345 | 325–355 | 2026-09-18 |
| Suéter Botones M Verde Bicentenario | 2 | 345 | 355 | 2026-09-13 |
| Suéter Botones M Verde Práxedis Guerrero Secundaria | 2 | 345 | 355 | 2026-09-14 |
| Suéter Cuello V Azul Marino SABES | 2 | 335 | 345 | 2026-09-19 |
| Suéter Cuello V H Azul Marino Telesecundaria 512 | 2 | 345 | 355 | 2026-09-14 |
| Suéter Cuello V H Telesecundaria 600 | 2 | 290–345 | 325–355 | 2026-09-18 |
| Suéter Cuello V H Verde Bicentenario | 2 | 345 | 355 | 2026-09-14 |
| Suéter Cuello V H Verde Conalep | 2 | 335 | 345 | 2026-09-13 |
| Boina Escolta Azul Cielo | 1 | 80 | 85 | 2026-09-21 |
| Boina Escolta Azul Marino | 1 | 80 | 85 | 2026-10-04 |
| Boina Escolta Azul Rey | 1 | 80 | 85 | 2026-09-21 |
| Boina Escolta Beige | 1 | 80 | 85 | 2026-09-22 |
| Boina Escolta Blanca | 1 | 80 | 85 | 2026-10-11 |
| Boina Escolta Blanco | 1 | 80 | 85 | 2026-09-21 |
| Boina Escolta Café | 1 | 80 | 85 | 2026-09-21 |
| Boina Escolta Camuflaje | 1 | 80 | 85 | 2026-09-22 |
| Boina Escolta Gris | 1 | 80 | 85 | 2026-09-21 |
| Boina Escolta Negro | 1 | 80 | 85 | 2026-09-22 |
| Boina Escolta Rojo | 1 | 80 | 85 | 2026-10-20 |
| Boina Escolta Rosa | 1 | 80 | 85 | 2026-09-22 |
| Boina Escolta Verde | 1 | 80 | 85 | 2026-09-22 |
| Boina Escolta Verde Limon | 1 | 80 | 85 | 2026-09-22 |
| Boina Escolta Vino | 1 | 80 | 85 | 2026-09-22 |
| Falda Escolar Azul Marino | 1 | 195 | 205 | 2026-09-22 |
| Suéter Botones M Negro Huizache | 1 | 295 | 299 | 2026-09-18 |
| Suéter Botones M Verde Conalep | 1 | 335 | 345 | 2026-09-13 |
| Suéter Claudia Botones M Azul Marino | 1 | 309 | 315 | 2026-10-09 |
| Suéter Claudia Botones M Azul Rey | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Botones M Blanco | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Botones M Negro | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Botones M Rojo | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Botones M Verde | 1 | 309 | 315 | 2026-10-21 |
| Suéter Claudia Botones M Vino | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Cuello V H Azul Marino | 1 | 309 | 315 | 2026-09-19 |
| Suéter Claudia Cuello V H Blanco | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Cuello V H Negro | 1 | 309 | 315 | 2026-04-24 |
| Suéter Claudia Cuello V H Rojo | 1 | 309 | 315 | 2026-09-22 |
| Suéter Claudia Cuello V H Verde | 1 | 309 | 315 | 2026-09-19 |
| Suéter Claudia Cuello V H Vino | 1 | 309 | 315 | 2026-09-22 |
| Suéter Cuello V H Negro Huizache | 1 | 295 | 299 | 2026-09-18 |


### Sin SKU en la caja

| SKU | Producto (SQLite) | Precio SQLite |
|---|---|---:|
| SKU002814 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002799 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002802 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002803 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002805 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002806 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002808 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002811 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002812 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002825 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002816 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002819 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002820 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002822 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002823 | Chamarra Deportiva Talla 8 T8 | 335 |
| SKU002777 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002778 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002780 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002782 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002785 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002786 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002788 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002789 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002791 | Chamarra Deportiva Talla 4 T4 | 335 |
| SKU002794 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002795 | Chamarra Deportiva Talla 6 T6 | 335 |
| SKU002797 | Chamarra Deportiva Talla 6 T6 | 335 |
