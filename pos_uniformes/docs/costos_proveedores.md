# Costos de proveedores

Registro de lo que pagamos por prenda, tomado de las notas de remisión.
Sirve para calcular el margen contra el precio de venta y decidir dónde subir precio o armar ofertas.

Convenciones de las notas:

- `B` = Botones (abierto, "Botones M")
- `V` = Cuello V ("Cuello V H")
- Margen = (venta − costo) / venta

## Martell

### Remisión 19-oct-2026

| Cant | Prenda | Tallas | Costo | Importe |
|---:|---|---|---:|---:|
| 24 | Suéter básico Azul Rey B | 6, 8, 10 | 153 | 3,672 |
| 24 | Suéter Ignacio Allende B | 12, 14, 16 | 161 | 3,864 |
| 24 | Suéter Ignacio Allende V | 6, 8, 10 | 145 | 3,480 |
| 24 | Suéter Ignacio Allende V | 12, 14, 16 | 153 | 3,672 |
| 10 | Suéter básico Verde B | 6 | 153 | 1,530 |
| 10 | Suéter básico Verde B | 4 | 153 | 1,530 |
| 9 | Suéter Bicentenario V | 14, 16 | 157 | 1,413 |
| 11 | Suéter Bicentenario B | 14, 16 | 165 | 1,815 |
| 1 | Chaleco (escuela por confirmar) | 40 | 167 | 167 |
| 35 | Suéter UVEG B | 16 | 174 | 6,090 |
| 25 | Suéter UVEG B | 34 | 184 | 4,600 |
| 6 | Suéter UVEG B | 36 | 184 | 1,104 |
| 10 | Suéter UVEG B | 38 | 184 | 1,840 |
| 10 | Suéter UVEG B | 40 | 197 | 1,970 |
| 7 | Suéter UVEG B | 42 | 197 | 1,379 |
| **230** | | | | **38,126** |

> La nota escrita suma **38,182**; la suma de renglones da **38,126** (56 de diferencia). Revisar con el proveedor.

### Margen contra precio de venta actual

| Prenda | Tallas | Costo | Venta | Margen |
|---|---|---:|---:|---:|
| Básico Azul Rey B | 6, 8 / 10 | 153 | 289 / 299 | 47% / 49% |
| Básico Verde B | 4, 6 | 153 | 289 | 47% |
| Ignacio Allende V | 6, 8 / 10 | 145 | 290 / 295 | 50% / 51% |
| Ignacio Allende V | 12, 14, 16 | 153 | 315 | 51% |
| Ignacio Allende B | 12, 14, 16 | 161 | 315 | 49% |
| Bicentenario V | 14, 16 | 157 | 325 | 52% |
| Bicentenario B | 14, 16 | 165 | 325 | 49% |
| UVEG B | 16 | 174 | 355 | 51% |
| UVEG B | 34, 36, 38 | 184 | 365 | 50% |
| UVEG B | 40, 42 | 197 | 375 | 47% |
| Chaleco | 40 | 167 | 269–300 | 38–44% |

Precios de venta tomados de `Gestor_de_Inventarios/data/productos.db`.

### Cambios de precio derivados

- **22-oct-2026 · UVEG:** 14, 16 → 355 (antes 345) · 32–38 → 365 (antes 345) · 40, 42 → 375 (antes 355).
  El costo sube por talla (174 → 184 → 197) y la venta estaba casi plana.

## Alineación de precios SQLite ↔ caja (22-oct-2026)

Decisión: **los precios válidos son los de la caja (PostgreSQL de la tienda).** `productos.db` y los documentos se corrigen para igualarla, no al revés.

Al comparar las dos bases había 866 SKUs distintos (SQLite se había quedado atrás desde abril y además traía subidas que nunca llegaron a la caja). Detalle en `discrepancias_precios_2026-10-22.md` y su CSV.

| Qué se hizo | Dónde |
|---|---|
| 866 SKUs de `productos.db` igualados a la caja (579 suben, 287 bajan); 4,005 SKUs comunes idénticos | `Gestor_de_Inventarios/data/productos.db` |
| Reglas reescritas con las escaleras reales (tres copias iguales) | `reglas_precios_v1.md` |
| 11 guías rápidas alineadas, iguales en ambas carpetas | `guia_rapida_*_compacta.md` |
| Generadores de tarifarios y tarifarios docx/html regenerados | `generar_tarifarios*.py`, `generar_tarifario_escuelas.py` |
| Script de revisión con reglas nuevas; omite precios especiales en caja; 0 inconsistencias | `revisar_precios_postgres.py` |

Cambios de escalera más relevantes: suéter oficial (299 / 315 / 325 / 335 en primaria; 355 en tallas 40–44), chalecos oficiales 249–309, pantalones de vestir con escalón cada dos tallas (gris claro/obscuro +14), faldas básicas divididas en Gales y Escolar, pants 2pz deportivo preescolar 415/515, chamarra punto adulto plana en 395, boina 85, bata manga larga 365.

**Precios especiales en caja (confirmar si son intencionales):** CBTIS 148 en 200 (suéter y camisa), 150 (playera) y 300 (pants 2pz); Vicente Guerrero y Margarita Paz Paredes en 89; pants 2pz liso infantil 175/190; bata manga larga 365 por debajo de la manga corta 395.

Quedan 27 SKUs en `productos.db` sin SKU en la caja (casi todos chamarras deportivas talla 4 y 6 a 335): decidir si se dan de alta en el POS o se retiran del Gestor.
