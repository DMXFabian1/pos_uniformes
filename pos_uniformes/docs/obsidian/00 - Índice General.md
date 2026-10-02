---
tags: [indice, pos-uniformes]
---

# POS Uniformes — Dashboard

> Sistema punto de venta en Python para tienda de uniformes escolares.
> Stack: PyQt6 · PostgreSQL · SQLAlchemy ORM · Alembic

---

## La brújula

> [!tip] **Una escuela, un número, cuatro ventanas** → [[39 - Brújula]]
> El sistema responde tres preguntas: **qué necesita cada escuela**, **cuánto tengo de verdad**, **qué me pidieron que no tenía**.
> POS = la gestión · Kiosko = el piso · Libreta = el dinero · Mapa = el estado.
> **Ninguna ventana calcula: todas preguntan al mismo cerebro.**
> Regla de admisión: *nada entra al sistema si no cuelga de una escuela o de una prenda.*
> **Las cinco fases quedaron cerradas el 2026-09-22.** El generador del Panel pasó de 8 consultas SQL a ninguna, nació `escuela_estado_service`, el mapa es la portada del Panel y las cuatro ventanas pintan el mismo semáforo (`conteo_mapa_service.semaforo`: rojo = *no sabemos qué hay*). Pendiente de tienda: correr `revisar_stock_negativo.bat` en la principal y contar lo rojo.

---

## Estado actual

> [!success] La venta ya descuenta stock (2026-09-14) · Revisar dice qué pedir y qué surtir, la jornada es de la escuela, bodega desde el celular, nómina por días (2026-09-13)
> **Sesión 2026-09-20 (noche 3) — rediseño del catálogo, fase 1 (aplicada en producción):** Daniel: "rediseñar cómo están los uniformes sin afectar los SKU". (1) **Nombres limpios**: `Producto.nombre` ya no carga "| Tipo de prenda | Tipo de pieza" (`CatalogService._build_product_display_name` no lo pega; `Producto.nombre_completo` lo arma con "·" cuando hace falta); `scripts/limpiar_nombres_productos.py` limpió **398** (manda el `nombre_base` curado; cada palabra con mayúscula inicial —Olan, Cielo, Roja— menos conectores y siglas; recupera del sufijo el tipo de prenda que faltaba; la prenda dice el nombre de su plantel ya separado; el UNIQUE marca+nombre cuenta inactivos, que reciben " (2)"). (2) **Escuelas partidas** con `scripts/separar_escuela_por_nivel.py`: **#52 Álvaro Obregón (El Carretón)** = Primaria (6 prendas; #43 queda Preescolar) y **#53 Vicente Guerrero Preescolar** (5 prendas; #37 queda Primaria; la jornada 25 de Nayeli se partió en 25/78). (3) **Duplicados fundidos** con `scripts/fundir_productos.py` (tallas con sus SKUs al destino; la talla repetida queda inactiva bajo el origen y su existencia pasa con un movimiento): Camisa Cuello Olan Blanca #426→#394 (eran las dos mitades: tallas 2–10 y 12–GD), Pants 2pz y 3pz Deportivo Álvaro Obregón #193→#482 y #187→#522. Todo sin tocar un SKU. Pendiente: Meilisearch se re-indexa solo al abrir el kiosko/POS (o Ctrl+Shift+A → Sincronizar). Fases 2 (Uniforme como entidad) y 3 (conjuntos) sin empezar. Ver [[07 - Servicios - Catálogo e Inventario]].

> **Sesión 2026-09-20 (noche 2):** el mapa del kiosko **a tono con el programa**: tarjetas `libretaCard` redondeadas, títulos `libretaSeccion`, barra pintada, fichas de talla y botones del kiosko (`ui/helpers/conteo_mapa_widgets.py`, widgets nativos); y el diálogo con colores fijos (el modo oscuro de la Mac lo pintaba negro).

> **Sesión 2026-09-20 (noche) — limpieza en producción:** por el bug de la captura por prenda, lo contado de varias prendas quedó en la jornada de una sola (#60, #63, #66, #71, #76) y las de las otras "a medias" en 0. `scripts/reubicar_conteos_por_prenda.py` (dry-run; `--aplicar`) mueve cada renglón a la jornada de su prenda (la de esa persona, o una nueva a su nombre) y deja la destino como la origen (terminada/aplicada). **Aplicado: 138 tallas, 11 movimientos**; todas quedaron completas (Suéter V Verde y Camisas olan aplicadas; Playeras, Faldas Gales y Pantalones Vestir por revisar). Además `Mandil Infantil Estampado` (id 584, alta del 13) se renombró a **Bata Infantil Estampado**; las 8 Bata Infantil de siempre no se tocaron.

> **Sesión 2026-09-20 (tarde) — Mapa de conteos:** Daniel: "una guía visual para ver qué está contado y qué no… como el panel de uniformes, pero que no sea megalítico". `services/conteo_mapa_service.py`: tres capas — `resumen` (escuelas con su nivel + tipos de básicos, cada uno con tallas al día / viejas / nunca, % y "hace N d"), `escuela`/`basicos` (sus prendas con las mismas cifras) y dentro de cada prenda sus tallas con días. "Al día" = dentro de la vigencia de esa escuela. **Celular:** 🗺 Mapa de conteos en el inicio del dueño (`/movil/conteos/mapa`, `/mapa/escuela/{id}`, `/mapa/basicos/{tipo}`; cache v24). **Kiosko:** Daniel: "me refería a la sección Conteos" → el mapa **sustituye a la tabla** dentro de la sección (la tabla queda en *Ver tabla*, por el doble clic al comparativo), pintado **nativo** con texto enriquecido de Qt (`ui/helpers/conteo_mapa_rich_text.py`: mosaicos, barras y fichas como tablas con `bgcolor`, enlaces `e19`/`bPantalón`/`p0`/`mapa` para cambiar de capa) — el kiosko no trae WebEngine y son ~200 MB por máquina. `ConteoMapaWidget` (buscador, estado, ↻; datos en hilo, no más de una vez por minuto; `scroll_propio=False` en la sección) y `ConteoMapaDialog` (botón 🗺 Mapa). Los mosaicos dicen *En proceso · Fanny · hoja impresa 10:32* y quién contó la última vez (`_jornadas_por_clave`). Con datos reales: 3,711 tallas, 55 % al día, 1,557 nunca. Ver [[36 - Conteos por Jornada]].

> **Sesión 2026-09-20:** bug en el kiosko — al capturar una jornada de **una sola prenda** de básicos, `ConteoSubirDialog._cargar_piezas` cargaba por tipo y traía todos los pantalones; ahora, con jornada, usa `alcance(escuela, tipo, prenda)` como la hoja impresa y el celular. **Básicos que no aparecían** (pants liso rojo/verde, suéteres rojo/vino): eran generales sin liga a escuela; Daniel: "me gustaría que aparezcan, menos lo que es ropa normal" → básico = **todo general de uniforme**, tenga o no existencia, ligado o no; fuera solo la ropa normal por categoría o tipo de prenda (`CATEGORIAS_ROPA_NORMAL`: casual, temporada, interior, calzado…). En producción: 56 → **196 prendas (1,874 tallas)**. Una sola definición (`_filtro_basicos`) para lista, estado y calendario (`b8bd9122`). Ver [[36 - Conteos por Jornada]].

> **Sesión 2026-09-19:** **Corte con desglose** — cada pago y cada retiro del periodo con fecha y casilla; se desmarca el que **no salió del cajón** (Daniel: "el pago a Evelyn lo hice ayer") y queda anotado `en_cajon=False` (migración `0b1c2d3e4f5a`, sexta): deja de restarse y el ticket solo lista lo que sí salió; `pagos_registrados_del_periodo`/`retiros_del_periodo` filtran por default. **Asistencia en el celular** — "¿Qué pasó con Naye?" ahora enseña las marcas de las últimas dos semanas con **Quitar** (Daniel: "le puse que faltó Naye y no tengo manera de corregirlo"), suma *Sí vino (en su descanso)*, y el dueño tiene el mismo flujo desde su inicio (`GET /movil/encargado/marcas/{code}`, cache v23). Ver [[33 - Caja, Nómina y Corte Automático]], [[30 - Calendario de Empleadas]].

> **Sesión 2026-09-18 (noche) — navegación de la PWA y llegadas:** **barra superior** fija (‹ Atrás · título · ↻ Actualizar · ⋯ Menú) con **pila de pantallas** real: cada función que pinta una pantalla se envuelve y hace `pushState`, así el **botón físico / gesto de atrás** regresa dentro de la app; las acciones (guardar, cobrar, marcar) no se apilan y al terminar la pila vuelve a la raíz (atrás no regresa a "confirmar"); jalar hacia abajo actualiza *la pantalla actual* (menos dentro de la hoja de captura). Menú: quién · tienda/consulta · versión, *Actualizar*, *Traer la última versión* (borra caché + SW + recarga), *Cerrar sesión*. **Llegó mercancía** con casilla "🏷 Imprimir una etiqueta por pieza" (cola `trabajo`, como Buscar; solo en tienda) y **📜 Lo que ha llegado** para el dueño (último mes por día + nota + quién; también se ve en el POS → Historial inventarios como ENTRADA_COMPRA "Llegó: …"). "Sin color" no se enseña junto a la talla. Cache v22. Ver [[31 - PWA Libreta Móvil]].

> **Sesión 2026-09-18 (tarde 2) — hojas repetidas:** las chicas imprimían conteos que otra ya estaba haciendo porque **imprimir no dejaba huella** (la jornada solo nacía al capturar). Ahora **imprimir la hoja abre la jornada a nombre de quien imprime** (`registrar_impresion`; si ya había una, se pega a ella y cuenta la hoja), hace falta gafete para imprimir, el selector dice "EN PROCESO (Fanny) · hoja impresa 10:32", y si insisten sale un aviso fuerte con "No imprimir" por defecto. El banner "Imprimir orden de conteo" (sin gafete) ahora lleva a Conteos. Celular: la ficha en proceso dice también la hoja. Migración `f06b7c8d9e0f` (quinta). **Bodega móvil:** *Llegó mercancía* sigue las reglas de la hoja — sin Pants 3pz ni Chamarra (se arman con 2pz + playera / quitando la chamarra, no llegan como pieza), orden por tipo de pieza y tallas de chica a grande, nombre corto + tipo en la lista. Cache v19. Ver [[36 - Conteos por Jornada]].

> **Sesión 2026-09-18 (tarde) — Contar en el celular:** pestañas **Escuelas | Básicos**, **buscador** (sin acentos, busca también en las escondidas) y **grupos** *En proceso · Tocan · Nunca contadas · Contadas* con su cuenta; **⚠ solo en las que de verdad vencieron** (ya contadas y pasada la vigencia; las nunca contadas van en su grupo sin alerta). **Bug arreglado:** la hoja de captura salía vacía desde el 17 — el selector de prendas de básicos repetía el id `cont-prendas` y las tallas se pintaban en el div oculto; ahora `cont-prenda-sel` y un test de ids únicos en la PWA (`test_pwa_index_html`). Cache v17. Pruebas: servidor de la Mac expuesto en la LAN (`http://192.168.0.4:8765/app`) contra la copia local, PIN temporal 1234 solo ahí; capturas con Playwright + Brave a 390×844 (`scratchpad/pwa_shot.py`). Ver [[36 - Conteos por Jornada]], [[31 - PWA Libreta Móvil]].

> **Sesión 2026-09-18:** **Siempre el nombre, nunca `VEND-1`** — `services/nombres_empleadas_service.py`: `nombres_por_codigo(session)` (caché 5 min, incluye inactivas, copia local `data/empleadas_nombres.json` para el kiosko sin red) y `mostrar(texto)` que cambia cada código por el nombre ("Ana López (VEND-3)" → "Ana López"; `corto=True` → primer nombre). Aplicado en tickets de corte ("Por:"), historial de cortes y pagos, Libreta del kiosko (encabezados, detalle, ranking, dueño), movimientos de inventario y bodega, conteos (tablero, quién capturó, conflictos), celular (cortes, ranking, conteos) y el resumen de Telegram. Lo guardado no cambia (los permisos siguen por código). **Red:** la principal perdió la `.10` por un celular que la tomó por DHCP (quedó en `169.254…` con IP fija corrupta); se recuperó con `netsh` y Daniel apartó la `.10` en el ARRIS. Ver [[29 - Updates y Mensajería]], [[22 - Referencia Rápida]].

> **Sesión 2026-09-17 — afinar:** medido el arranque del kiosko con perfilador (1.0 s en la Mac): lo más caro era el flujo guiado normalizando cada producto general por cada escuela con ligas (0.38 s → 0.05 s, y se repetía en **cada** cambio de escuela/nivel). El banner de conteo vencido consultaba Postgres **en el hilo de la UI** cada 10 min (congelaba por Wi-Fi) → hilo aparte. Tarifarios: la lista de escuelas hacía ~100 consultas (1–2 por escuela) → 2. Índice nuevo en `movimiento_inventario.referencia` (cada venta preguntaba "¿ya desconté libreta:N?" recorriendo la tabla; migración `ef5a6b7c8d9e`). **Escaneo en venta rápida cache-primero** (hecho: cero viajes a Postgres por pieza). Tablero de Conteos: el alcance de todas las escuelas en 2 consultas (de ~60 a ~10 al abrir). **Celular: básicos por prenda** (al tocar el tipo: "todas" o una sola, cada una con su último conteo y quién la cuenta; cache v15). **POS:** la normalización del buscador con caché (arranque 1.9 → 1.2 s). Afluencia se queda como está (no es prioridad). **Ojo:** la `.10` respondía desde otro aparato (Postgres/SMB cerrados) — revisar el rango DHCP. Ver [[19 - Deuda Técnica]].

> **Sesión 2026-09-15:** **Iconos originales** de vuelta (la M para el POS, el átomo para el kiosko; estaban en Descargas) en 7 tamaños, commit `9384ff8c`. **Pasos de una sola vez al actualizar** (`postactualizacion.bat --pasos-unicos`, solo desde `actualizar_pc_principal.bat`): Meilisearch a S4U, `descontar_ventas_pasadas --aplicar` e instalar afluencia (abre sola la ventana de dibujar líneas); anotados en `data\pasos_unicos.txt`, los que fallan se reintentan. Ya no queda nada que correr a mano en la principal. **Revisión de bugs:** nómina — el sábado trabajado por un descanso movido no es día de más (una falta extra sí se descuenta); aplicar un conteo ya no se salta la talla que dejaría negativo; `descontar_ventas_pasadas` corre en cada actualización; el tablero de Conteos trae lo capturado en una consulta (1.5 → 1.1 s). Ver [[29 - Updates y Mensajería]], [[30 - Calendario de Empleadas]], [[36 - Conteos por Jornada]].

> **Sesión 2026-09-14 (mañana):** el corte del dueño ofrece los **pagos que tocan hoy** y los descuenta; Stayce con descanso fijo sábado y su sábado 12 como "vino" (pago completo). **La venta del kiosko descuenta stock** desde hoy (puede quedar negativo = qué recontar; migración `cd3e4f5a6b7c`); `scripts\descontar_ventas_pasadas.bat --aplicar` una vez para las ventas del 2 al 13 de septiembre. **Reimprimir ticket** también desde el detalle de la operación (todas). En Conteos, el tablero muestra **todas** las escuelas con su último conteo (no solo 8 jornadas). **Revisar rediseñado**: tarjetas que filtran, tabla de 5 columnas por prenda y "por qué" al tocar una talla. **Comparativo** con el conteo anterior (había / hay / vendidas / sin explicar) con doble clic en el tablero, aunque la jornada ya esté aplicada. **Catálogo (en producción):** Práxedis Guerrero se partió en **Práxedis G Guerrero** (Primaria, id 19) y **Práxedis Guerrero Secundaria** (id 49), y la jornada de Stayce del 13 se partió con ellas (24 y 26); nacieron **Miguel Hidalgo (Rancho Nuevo)** (id 50: mismas piezas en gris, sin chaleco, stock 0) e **Ignacio Allende (Jaral)** (id 51: sin suéteres, stock 0). 51 escuelas ahora. Anotación pendiente: **214 de 322 prendas de escuela están "Sin color"** (se trabaja después). **Tarjeta:** en Libreta, celular y tickets ahora manda lo que **llega** (neto) y lo cobrado va en chico. **Básicos por prenda:** el selector dice cuándo se contó cada tipo y cada prenda, y se puede contar una sola (migración `de4f5a6b7c8d`). **Ventanas negras:** `POS Corte 1630/1730` con el .bat directo → `INFRA_VERSION 6` las recrea ocultas; el bot y la PWA ahora con `pythonw.exe` (Windows Terminal los mostraba como pestaña); `MeilisearchPOS` a `S4U`. **Iconos** de 7 tamaños para kiosko y POS (al día siguiente se cambiaron por los originales). Ver [[07 - Servicios - Catálogo e Inventario]], [[33 - Caja, Nómina y Corte Automático]], [[28 - Libreta Digital]].
>
> **Rama activa:** `chore/reorganizacion-repo` · **HEAD:** `ce1eca1d` (2026-09-14, pusheada) · **VERSION `2026.11.11`** (la build publica versión+commit; ya no hay que bumpear)
> **Sesión 2026-09-13 (domingo, larga):** **Contar desde el celular** (la hojita en la PWA, sin Pedido) y **cuándo se contó por última vez** al elegir escuela. **Afluencia:** verificada desde la Mac contra las 4 cámaras (funcionaba; el servidor no la corría) → log, tarea oculta, `INFRA_VERSION 5`, diagnóstico; Daniel movió la línea de ENTRADA2.2 y ahora **la dibuja con el ratón** (`dibujar_lineas.bat`, el contador la toma en caliente). **Revisar v2** en tres pasos: por talla cuántas hay, cuántas se vendieron, ritmo, cuánto pedir (4 semanas), Daniel decide y **se guarda** (`bc2d3e4f5a6b`), hoja de pedido (copiar / imprimir / Telegram), **historia de la talla** e **historia de la escuela** (qué prenda y talla se vende más, % del total, "N de M prendas hacen el 80 %") — ver [[37 - Revisar y Pedidos]]. **Conteos, lo que pidieron las empleadas:** una sola jornada por escuela con "Seguirla / Imprimir otra hoja", sin candado de dueña, las contadas hace menos de 14 días fuera del menú ("Ver todas"), si dos capturan la misma talla se pregunta antes de pisar, y **Eliminar / Reasignar** en las jornadas a medias — ver [[36 - Conteos por Jornada]]. **Básicos:** piso = a la mano, bodega = lo que está en cajas (el módulo Bodega del POS, 31 cajas paradas desde julio); Revisar pide contra el total y dice **surtir** de las cajas antes que pedir; en el celular del dueño, **📦 Bodega**: *Llegó mercancía* (entra al piso; parte a caja si se decide, prellenado con lo pedido), *Pasar al piso* y *Corregir caja* (recuento). **Nómina:** darle descanso en otro día mueve el fijo de esa semana, y **solo se descuenta si laboró menos días de los que le tocan** (faltó martes, vino sábado = completo). Producto "Mandil Infantil Estampado" $75 creado en producción. Pendiente de decisión: filtro de internet con NextDNS en el módem (el Deco en modo AP no puede).
>
> **Sesión 2026-09-12:** la **ventana negra** era la tarea "POS Snapshot Casa" (sin `correr_oculto.vbs`, sobrevivió a la limpieza) → `INFRA_VERSION 4` la recrea oculta. **`/asistencia`** en el bot y tarea diaria a las 11:00: presencia deducida del primer movimiento, y al final **un comando tocable por empleada** (`/falta_Fanny · /descanso_Fanny`, repetir lo quita) para que Daniel tenga la última palabra. Se probaron botones inline y los descartó. Ver [[34 - Telegram y Resumen Diario]].
>
> **Sesión 2026-09-11 (en la tienda):** **paso 4** — la hoja de conteo en **carta** con el formato de Daniel (Talla · Exist. · Pedido, tres tarjetas por fila, paleta del kiosko, numerada igual que la pantalla) y un **selector carta / tira** porque la HP empezó a fallar. PC principal actualizada, producción en `ab1c2d3e4f5a`, **5 jornadas ya registradas**. Ver [[36 - Conteos por Jornada]].
>
> **Sesión 2026-09-10 (noche):** **Conteos por jornada** en el kiosko — sección nueva (se fue el botón Cámaras, sigue en Ctrl+Shift+C), gafete al entrar, la captura ya no enseña lo que el sistema cree, vacío = no contada, jornadas que se pausan y retoman, avance por prendas, y Daniel **aplica o descarta por bloque** desde el kiosko. Estética igual a la Libreta. Queda el **paso 4** (hoja carta en la HP) para hacerlo en el local. Ver [[36 - Conteos por Jornada]]. Además: la suite completa en **paralelo, 80 s → 28 s** ([[18 - Cobertura de Tests]]).
>
> **Sesión 2026-09-10 (tarde):** la pestaña **Analítica** dejó de leer tablas muertas y ahora muestra **lo que de verdad se vende** desde la Libreta (producto, prenda, escuela, talla, hora, empleada) más **"Lo que se perdió"**: la demanda que nadie registraba. Se junta sola desde el kiosko, **sin que las empleadas llenen nada** — ver [[35 - Demanda No Atendida]]. Hallazgo grande: **el stock lleva congelado desde el 16 de julio** porque vender en el kiosko no lo descuenta ([[07 - Servicios - Catálogo e Inventario]]). El POS adelgazó de **once pestañas a siete** y se fue el aviso diario de "Caja pendiente de corte" ([[03 - Mapa de Módulos UI]], [[08 - Servicios - Caja]]).
>
> **Sesión 2026-09-10:** **un solo supervisor oculto** para bot y PWA (se fue la ventana negra) y **la infraestructura se aplica sola al actualizar** (`postactualizacion.py`, `INFRA_VERSION`). **Un solo ticket** (el simple) por defecto en todos lados y el corte pregunta por la **venta**; **cifras oficiales** (con ajustes) sin anunciarlo y las reales solo con Ctrl+Shift+R; corregir cortes (ajustar la venta, quitar el ajuste, borrar) y deshacer pagos; la interfaz ya no nombra a la familia; Meilisearch con SKU corto y ranking por ventas. Ver [[29 - Updates y Mensajería]], [[33 - Caja, Nómina y Corte Automático]], [[28 - Libreta Digital]], [[13 - Servicios - Utilidades]].
>
> **Sesión 2026-09-09:** PC principal actualizada y bot de Telegram funcionando (TLS del antivirus + nombres de tarea). Nuevo: **historial de cortes con reimpresión** (Libreta → 🧾 Cortes), **alertas por Telegram** (cola `alerta_telegram`, migración `w6e7f8a9b0c1`), venta rápida con **Sin ticket**, **← Regresar** y **chips de prendas** en "Producto sin código", **Calendario del kiosko** con detalle del día y pago por gafete (Naye sin descansos falsos). Diagnóstico de impresión lenta (Windows Update). Auditoría de Meilisearch pendiente de decisión. Ver [[33 - Caja, Nómina y Corte Automático]], [[34 - Telegram y Resumen Diario]], [[30 - Calendario de Empleadas]], [[17 - App Satélite]].
>
> **Sesión 2026-09-08 (maratón):** impresora HP y DVR Dahua conectados al Deco; **visor de cámaras** en el kiosko (empleadas = entradas, admin PIN = todas) y **Ver momento** en la Libreta; **contador de afluencia** con YOLO (proceso aparte) y sección Afluencia/conversión; **caja con reactivo** ($11,160), **corte por periodo**, **nómina** 1,300 + 2/comisión − 216.67/falta, **corte de un botón para León** con pagos automáticos y ticket simple, **retiros con motivo**, **empleadas por días** (Naye), **Equipo** (baja/reactivar/horario), **Pendientes de hoy**, **historial de pagos**, **resumen diario y bot de Telegram** (`/corte` desde el celular), horario de tienda (corte 30 min antes de cerrar). Además: suite de tests saneada (`pytest --fast` 4 s; completa 1,811 en ~70 s) y updater que ya no pide bump de VERSION. Ver [[32 - Cámaras y Afluencia]], [[33 - Caja, Nómina y Corte Automático]], [[34 - Telegram y Resumen Diario]]
> **Sesión anterior (2026-09-05/06):** pulido táctil, Libreta v4 (solo dinero real), reimprimir/cambiar pago/reasignar, venta sin código, anticipo de apartado. Ver [[28 - Libreta Digital]], [[17 - App Satélite]]
> **Migraciones:** producción al día en `ab1c2d3e4f5a` (2026-09-11). Nada pendiente.
> **Migraciones nuevas (4, pendientes en producción):** `s2a3…` afluencia_hora · `t3b4…` caja_parametros + empleada_pago + periodo en libreta_corte · `u4c5…` empleadas por días · `v5d6…` caja_retiro — se aplican solas con `actualizar_pc_principal.bat`
> **Suite de tests:** Verde ✓ **2,319** (2026-09-14) · `--fast` 734 en ~4 s · completa `-n 6 --dist load` en ~28 s

> [!important] Dirección del proyecto (2026-09-04)
> **Kiosko primero:** la venta rápida es la herramienta de piso de las empleadas; el POS principal queda como gestión de Daniel. Las mejoras se concentran en el satélite. **Resuelto el 2026-09-14:** la venta del kiosko descuenta stock. Falta correr `descontar_ventas_pasadas.bat --aplicar` una vez y contar lo que se mueve para prender `EXISTENCIA_CONFIABLE`. Ver [[07 - Servicios - Catálogo e Inventario]].

> [!warning] Pendiente
> 1. **Actualizar la PC principal** con `scripts\actualizar_pc_principal.bat` (trae TODO lo de hoy + 4 migraciones + build) y reabrir el satélite en cada kiosko (se actualiza solo). Guía paso a paso en [[21 - Sesión de Trabajo]].
> 2. En la principal: `scripts\instalar_resumen_diario.bat` (bot + resumen 15 min antes de cerrar + pendientes 13:30) tras poner token y chat id en `pos_uniformes.env` (falta el chat id: escribirle "hola" al bot). Opcional: `afluencia\instalar_afluencia.bat` (contador de personas).
> 3. En cada kiosko: Ctrl+Shift+A → 📹 Cámaras → IP `192.168.0.11`, `dany`, contraseña, Detectar canales, marcar las 4 ENTRADA, Guardar (una vez por máquina; ya hecho en el primero).
> 4. **Equipo** (Libreta del dueño): dar de baja a Lupita; poner descanso fijo y último pago a las 6 restantes; Naye = por días sáb/dom. Sin eso no hay nómina ni faltas sugeridas.
> 5. Confirmar el descuento por falta ($216.67 supuesto) en ⚙ Caja y nómina.
> 6. Probar el video en el exe de Windows y validar las líneas de afluencia con gente entrando.
> 7. Lo de antes que sigue: estrenar la PWA (PINes, Tailscale), merge a `main`, kioskos restantes, limpiar worktrees viejos de la Mac.

## Versiones en producción

| App | Bundle instalado | Código listo |
|-----|-----------------|--------------|
| POS Principal | pull ~`2026.09.11` en PC tienda (2026-09-04); **pendiente pull de 2026-09-08** | `chore/reorganizacion-repo` `3c69b5b` = `2026.11.11+3c69b5b` (pusheada) |
| App Satélite | `2026.11.11` en el primer kiosko (2026-09-08, con Cámaras); resto pendiente | ídem |
| PWA Móvil | aún no desplegada (servidores .bat listos) | `pwa/` + `api/routers/movil.py` |

---

## Métricas del proyecto

| Métrica | Valor |
|---------|-------|
| Archivos Python | ~395 (sin tests; 637 con tests) |
| Tablas en BD | 60 |
| Servicios | 157 |
| Cobertura de tests | ~90% |
| Vistas UI | 12 · Dialogos 23 · Helpers UI 112 |
| Líneas en MainWindow | ~12,500 |
| Dependencias circulares | 0 ✓ |

---

## Documentación

### Arquitectura y código
- [[01 - Arquitectura General]] — capas, arranque, reglas del proyecto
- [[02 - Base de Datos]] — 43 tablas, modelos ORM, relaciones
- [[03 - Mapa de Módulos UI]] — MainWindow, vistas, diálogos, helpers

### Servicios por dominio
- [[04 - Servicios - Ventas]]
- [[05 - Servicios - Apartados]]
- [[06 - Servicios - Presupuestos]]
- [[07 - Servicios - Catálogo e Inventario]]
- [[08 - Servicios - Caja]]
- [[09 - Servicios - Clientes y Lealtad]]
- [[10 - Servicios - Empleadas]]
- [[11 - Servicios - Configuración y Marketing]]
- [[12 - Servicios - Analítica e Historia]]
- [[13 - Servicios - Utilidades]]

### Flujos operativos
- [[14 - Flujo de Venta]]
- [[15 - Flujo de Apartado]]
- [[16 - Flujo de Presupuesto]]
- [[17 - App Satélite]] — arquitectura, límites, roadmap
- [[28 - Libreta Digital]] — registro de ventas/comisiones por empleada, cortes, privacidad por gafete, **movimientos privados** y cifras oficiales vs reales (2026-09-10)
- [[30 - Calendario de Empleadas]] — descansos/faltas/pagos, autoservicio con reglas, encargado ENC-1 (2026-09-04); detalle del día + pago por gafete en el kiosko (2026-09-09)
- [[31 - PWA Libreta Móvil]] — app de celular tienda/casa: ciclo y movimientos de la empleada, menú del encargado, dinero real y **tu corte** del dueño, buscador con escáner, etiquetas (2026-09-10)
- [[32 - Cámaras y Afluencia]] — DVR Dahua en el kiosko, Ver momento, contador de personas y conversión (2026-09-08)
- [[33 - Caja, Nómina y Corte Automático]] — reactivo, corte por periodo, sueldo+comisiones−faltas, corte de un botón para León, retiros, Equipo, Pendientes (2026-09-08)
- [[34 - Telegram y Resumen Diario]] — resumen de la noche, pendientes, `/corte` desde el celular, alertas al instante, y **`/asistencia`** con comandos tocables por empleada (2026-09-12)
- [[35 - Demanda No Atendida]] — lo que pidieron y no se pudo vender; se junta sola desde el kiosko sin formularios, y se lee en Analítica (2026-09-10)
- [[36 - Conteos por Jornada]] — contar sin formularios trampa: gafete, sin pistas, vacío = no contada, pausar y retomar, y el dueño aplica por bloque (2026-09-10)
- [[37 - Revisar y Pedidos]] — revisar un conteo = decidir qué pedir o surtir: ritmo por talla, a la mano / en cajas, sugerencia a 4 semanas, la decisión se guarda y la siguiente revisión aprende; hoja de pedido, historia de talla y de escuela, bodega desde el celular (2026-09-13)
- [[38 - Catálogo Fase 2 - Uniformes]] — el uniforme de cada escuela como entidad (piezas que señalan productos propios o generales: grupo, orden, obligatoria, color) y los conjuntos 3pz/chamarra con receta (la venta mueve sus piezas, stock calculado); scripts armar_uniformes / armar_recetas y pantalla POS Más → Uniformes por escuela; hecho en código, pendiente en producción (2026-09-21)
- [[39 - Brújula]] — **el norte del proyecto**: una escuela, un número, cuatro ventanas; la regla de admisión, quién es dueño de cada definición, el semáforo compartido y las cinco fases, cerradas (2026-09-22)
- [[40 - Conjuntos con tallas que no se pueden armar]] — 37 conjuntos ofrecen tallas que ninguna de sus piezas tiene; tres causas distintas (tallas del sistema equivocado, tallas que faltan, y una receta que apunta a una playera unitalla). Encontrado de rebote reconciliando stock; **necesita decisiones** (2026-09-22)
- [[41 - Chuleta - atajos y comandos]] — **todo lo que se puede teclear o hacer doble clic en un solo lugar**: atajos del POS y del kiosko, los .bat del escritorio, los scripts que de verdad se usan, los comandos de Telegram (2026-09-25)
- [[42 - Antes de irme — lo que no dependa de mí]] — respaldo automático, corte sin él, la hoja para la tienda

### Estado del proyecto
- [[18 - Cobertura de Tests]]
- [[19 - Deuda Técnica]]
- [[20 - Pendientes y Fase 5]]

### Herramientas
- [[23 - Cómo leer este vault]]
- [[24 - Parser de Presupuestos]] — generador offline de presupuestos por texto libre
- [[25 - Panel de Uniformes]] — dashboard HTML embebido en la app (7 tabs: piezas, tarifarios, catalogo, faltantes, variantes, conteo)
- [[27 - Generador Tarifarios Escuelas]] — sistema de generadores desde la DB (Gestor): principal, índices con PDF, vertical con fotos, Reto Tarifario (juego)

### Auditoría
- [[26 - Auditoría Completa del Sistema]] — análisis profundo, bugs priorizados, deuda técnica (2026-05-25)

### Trabajo diario
- [[21 - Sesión de Trabajo]] — sesión activa
- [[21 - Historial de Sesiones]] — log de sesiones cerradas
- [[22 - Referencia Rápida]] — IPs, PINs, comandos, rutas
- [[29 - Updates y Mensajería]] — kioskos auto-actualizables por red + reportes de consola por git (2026-09)

---

## Sistemas conectados

- [[../PWA Móvil/00 - Índice PWA|PWA Móvil (React, vieja)]] — DESCARTADA 2026-09-04; la sustituye [[31 - PWA Libreta Móvil]]
- [[../Gestor de Precios/00 - Índice Gestor|Gestor de Precios]] — catálogo SQLite, escaleras de precios, guías rápidas para empleadas
- [[../Mapa Tienda/00 - Índice Mapa|Mapa Tienda]] — editor de plano 2D de la tienda (modo Arquitecto listo, modo Juego pendiente)
- [[../Libro Mayor/00 - Índice Libro Mayor|Libro Mayor]] — app Apps Script Daniel↔Coraima, Sheets como DB, append-only
- [[../Cien Mexicanos/Cien Mexicanos Dijeron|Cien Mexicanos]] — juego de concurso control+tablero en un HTML

---

> [!danger] Regla de oro
> `ui/main_window.py` es el coordinador central.
> **Nunca meterle lógica nueva densa.**
> Toda mejora nace en `services/` o `ui/dialogs/` y se conecta desde la ventana.

---

> [!abstract] Iniciativas activas
> **Cámaras + afluencia** — visor RTSP en kiosko, Ver momento, YOLO en la PC servidor (2026-09-08). Ver [[32 - Cámaras y Afluencia]].
> **Caja con reactivo y nómina automática** — corte por periodo, pagos calculados, León de un botón, Telegram (2026-09-08). Ver [[33 - Caja, Nómina y Corte Automático]].
>
> **Conteos por jornada** (2026-09-10). El conteo se puede delegar a las empleadas sin que ensucien el inventario; Daniel revisa y aplica por bloque desde el kiosko. Ver [[36 - Conteos por Jornada]].

> **Revisar = decidir qué pedir** (2026-09-13). La información del conteo se convierte en acción: cuánto pedir por talla, con memoria de lo que se pidió antes y qué pasó. Predecir todavía no: 12 días de Libreta. Ver [[37 - Revisar y Pedidos]].
>
> **Analítica sobre lo real y demanda no atendida** (2026-09-10). La Analítica lee la Libreta, no las tablas muertas, y junto a lo que se vendió muestra lo que se perdió. La captura es invisible para las empleadas. Ver [[35 - Demanda No Atendida]] · [[12 - Servicios - Analítica e Historia]].
> **Despachador de impresión POS/kiosko → satélite** — cola en tabla `trabajo`, rol Servidor/Estación (2026-07-11→18). Ver [[17 - App Satélite]].
> **Calendario de conteos periódicos** — recordatorio + auto-orden por escuela y básicos (2026-07-12→17). Ver [[17 - App Satélite]].
> **Anuncios/Cartelera en satélites** — broadcast texto/imágenes dirigible (2026-07-18). Ver [[17 - App Satélite]].
> **Reorganización del repo** — limpieza git + `_archivo/` en `chore/reorganizacion-repo` (2026-08-02). Ver [[21 - Sesión de Trabajo]].
> **Venta Rápida en satélite** — gate QR empleada, tickets venta/apartado/copia, impresión multi-ticket con TicketPrintQueue + excepthook global (2026-06-10 → 07-03). Ver [[17 - App Satélite]].
> **Tarifarios Escuelas desde la DB** — 4 generadores HTML/PDF: principal + índices + vertical + Reto Tarifario juego (2026-07). Ver [[27 - Generador Tarifarios Escuelas]].
> **Stock por ubicación** — `stock_bodega` + `stock_piso` en Variante, stock_tienda derivado (2026-05-28). Columnas visibles en Inventario.
> **Panel Uniformes embebido** — QWebEngineView + QWebChannel, modulo conteo inventario con bridge JS↔Python (2026-05-26). Ver [[25 - Panel de Uniformes]].
> **Modulo: Bodega (mini-WMS)** — gestion fisica de cajas, racks y distribucion de inventario. Implementado 2026-05-17/18, mejorado 2026-05-21.
> **Meilisearch** — busqueda typo-tolerant en 6 areas del POS. Integrado 2026-05-19/20. Ver [[13 - Servicios - Utilidades]].
