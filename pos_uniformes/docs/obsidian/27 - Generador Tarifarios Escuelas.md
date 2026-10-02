---
tags: [feature, pos-uniformes, tarifario, pdf, escuelas]
---

# Tarifarios de Escuelas — Sistema de Generadores

> Familia de scripts que generan los tarifarios desde la DB Postgres (con fallback a cache local).
> **Desde julio 2026 el sistema vigente vive en `Gestor_de_Inventarios/`** y genera HTML (+1 PDF); el script fpdf2 de mayo quedó como referencia histórica (al final).

---

## Capa común: `generar_tarifarios_db.py` (importado como `G`)

- **`G.cargar_filas()`** — lee variantes de Postgres `pos_uniformes` (credenciales de `../pos_uniformes/pos_uniformes.env`); si la DB no responde, cae al cache `tarifarios_cache_filas.json`. ⚠️ Cada corrida exitosa **reescribe el cache** — una corrida contra una DB en mal estado puede envenenar el fallback.
- Salidas en `Gestor_de_Inventarios/tarifarios_html/`.
- Ninguno acepta argumentos CLI: `python3 <script>.py` desde la carpeta del Gestor y sobrescribe su salida.

## Los 4 generadores (julio 2026)

| Script | Salida | Qué es |
|---|---|---|
| `generar_tarifario_escuelas_db.py` | `Tarifario_Escuelas_2026.html` | Documento principal, carta horizontal, una hoja por (nivel, escuela) + hoja de genéricos. Links de catálogo con cache propio `tarifarios_cache_links.json` |
| `generar_indices_tarifario.py` | `Indices_Tarifario_2026.html` + **PDF en `~/Downloads`** | Índice general + índices por nivel, con la numeración EXACTA del principal (reusa `E.secuencia_numerada`). Único que produce PDF de verdad (Brave headless, ruta Mac hardcodeada) |
| `generar_tarifario_escuelas_vertical.py` | `Tarifario_Escuelas_Vertical_2026.html` | Variante A4 retrato tipo catálogo con recuadro de foto por escuela (`fotos_escuelas/`, hoy vacía → placeholders). Autofit de escala uniforme para doble cara |
| `generar_juego_tarifario.py` | `Reto_Tarifario.html` | **Juego de capacitación offline**: banco automático (una pregunta por peldaño de cada escalera + excepciones), 3 modos (Rápido 10 / Completo 20 / Práctica), racha con bono, repaso de falladas, récords locales, sonidos, confeti, teclado 1-4 |

> [!warning] Orden de regeneración
> `generar_tarifario_escuelas_db.py` **primero**, `generar_indices_tarifario.py` **después** — los números de página de los índices se derivan de la misma secuencia. El principal omite las hojas de índice pero les reserva el número; se imprimen aparte y se intercalan sin mover páginas. (La versión vertical sí incluye sus índices.)

## Detalles finos

- `secuencia_numerada(filas)` numera todo el documento, índices incluidos.
- `limpiar(prod, esc)` quita el nombre de la escuela del nombre del producto (ignora acentos).
- Distractores del juego: `opciones_precio(correcto, pool)` — los 3 precios más cercanos de la misma escalera, ±10 progresivos si faltan.
- Juego: "Regenerar cuando cambien precios: preguntas y distractores se actualizan solos."
- PDFs de HTML sin Brave integrado: imprimir a PDF desde el navegador (ver nota de generación de PDFs en la Mac).

## Relación con otros módulos

- Misma DB que el POS (`pos_uniformes`); `school_tariff_service.py` genera los tarifarios de pantalla del POS, esto es para impresión/distribución.
- El [[25 - Panel de Uniformes]] muestra tarifarios interactivos en la app.
- El Reto Tarifario complementa las guías rápidas del [[../Gestor de Precios/00 - Índice Gestor|Gestor de Precios]].

---

## Histórico: script fpdf2 (mayo 2026, superseded)

`pos_uniformes/scripts/generar_tarifario_escuelas.py` (~1400 líneas, fpdf2 + psycopg) generaba un único PDF de 91 páginas: 79 de escuelas + 12 del tarifario general hardcodeado. Paginación manual (`auto_page_break=False`), headers "(cont.)", productos de catálogo vía `catalog_school_product_link`. Fue el primer sistema (2026-05-28) y sigue en el repo, pero el flujo vigente es el de arriba.
