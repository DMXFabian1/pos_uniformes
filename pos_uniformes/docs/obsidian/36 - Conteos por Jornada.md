---
tags: [modulo, pos-uniformes, kiosko, inventario]
---

# 36 — Conteos por Jornada

> Que una empleada pueda contar sola, dejarlo a medias, y que Daniel revise por bloque antes de que toque el inventario.

Relacionado: [[07 - Servicios - Catálogo e Inventario]] · [[17 - App Satélite]] · [[28 - Libreta Digital]] · [[35 - Demanda No Atendida]] · [[37 - Revisar y Pedidos]]

---

## De dónde viene

El módulo de conteo ya existía (calendario por escuela, hoja térmica, captura, aprobación desde el Panel de Uniformes; 1,173 conteos hasta julio). Lo que **no** se podía era delegarlo: la captura enseñaba lo que el sistema creía, una casilla vacía se tomaba por buena, `contado_por` era siempre "admin (satélite)", y cada renglón vivía suelto (ni pausar, ni avance, ni revisar como bloque).

Plan de cuatro pasos acordado el 2026-09-10; los tres primeros ese día y el cuarto el 11. **Probado en la tienda el 2026-09-11**: 5 jornadas en producción.

## Paso 1 — El acomodo del menú

- Botón **Cámaras** oculto (patrón de Tarifarios/Catálogo). El visor sigue en **Ctrl+Shift+C**, con test que lo cuida.
- **Calendario** queda solo con el calendario del mes. No pide gafete: ahí no se hace nada, se mira.
- **Conteos** es la sección nueva, donde se trabaja.

## Paso 2 — Que se pueda soltar

- **Gafete al entrar** (mismo criterio que la Libreta). `contado_por` = "Nombre (VEND-N)". Salir de la página cierra la sesión.
- **Sin pistas**: fuera la columna "Tienda", el número gris en la casilla y la diferencia en vivo (rojo/verde). Solo dice cuántas van.
- **Vacío = no la conté**: no se registra, no se toca `ultimo_conteo_at`. Antes vacío tomaba el esperado y le ponía fecha fresca a un dato viejo — peor que no contar. Antes de registrar avisa cuántas quedan sin capturar.

## Paso 3 — La jornada

Tabla `conteo_jornada` (migración **`ab1c2d3e4f5a`**) + `jornada_id` en `conteo_inventario`. Servicio `services/conteo_jornada_service.py`:

| Función | Qué hace |
|---|---|
| `abrir_jornada` | escuela **o** prenda básica (los básicos siempre por prenda: 2,361 renglones no se cuentan en una tarde); anota cuántas tallas abarca. **2026-09-13:** si esa escuela ya tiene una abierta lanza `JornadaEnProceso` con ella |
| `jornadas_abiertas` / `jornadas_por_revisar` / `jornadas_recientes` | las tres listas de la página |
| `avance` | tallas hechas/total y prendas completas/total |
| `puede_seguirla` | **cualquiera con gafete** (2026-09-13; antes solo quien la abrió o `VEND-1`) |
| `terminar_jornada` | la cierra; **no toca inventario** |
| `resumen_para_revisar` | cada talla con sistema / contó / diferencia (el diálogo ya usa `revision_service.revisar`, ver [[37 - Revisar y Pedidos]]) |
| `aplicar_jornada` / `descartar_jornada` | solo el dueño; aplicar usa `confirmar_ajustes_lote`; descartar deja marca en `notas` |
| `guardar_tallas` | upsert por talla; devuelve `Guardado(guardadas, conflictos)` — lo que otra capturó con otro número no se pisa salvo `reemplazar_ajenas` |
| `jornada_abierta_de` / `abiertas_por_alcance` | qué escuela (o prenda) tiene jornada en proceso |
| `UltimoConteo.reciente()` | contada hace menos de `DIAS_RECIEN_CONTADA` (14) |
| `JornadaRef` / `ref()` | foto plana para la UI (un ORM fuera de sesión revienta al tocarlo) |

**Captura con jornada** (`ConteoSubirDialog(jornada=…)`): sin elegir escuela, lo ya capturado aparece puesto y bloqueado **con su número** (no el del sistema), "Guardar y seguir después" deja la jornada abierta, "Terminar conteo" la cierra. No duplica renglones al retomar.

**Página Conteos** (misma estética que la Libreta, 2026-09-10 tarde): gate réplica, saludo "Hola, Stayce 👋" / "Conteos de la tienda", tarjetas POR CONTAR · A MEDIAS · MÍAS · POR REVISAR (dueño), barra de acciones con los tres pasos, jornadas en tarjetas dentro de paneles blancos, y abajo el **tablero de escuelas** (antes HISTORIAL de 8 jornadas; desde el 14/09 todas las escuelas, ver más abajo). Las consultas van detrás de la sonda de red: sin servidor no se congela.

Archivos: `ui/dialogs/conteo_jornada_dialogs.py` (empezar / revisar) · `ui/helpers/conteos_jornadas_helper.py` (tarjetas e historial) · estilo `libretaPanel` en `ui/styles/satellite_styles.py`.

## Paso 4 — La hoja de papel (hecho 2026-09-11, probado en la tienda)

Al tocar **"1 · Imprimir la hoja"** en Conteos: eliges escuela (o prenda básica) y luego **a dónde va** — lo decide quien imprime, cada vez:

| Destino | Qué sale |
|---|---|
| **Hoja carta** (HP) | El formato de Daniel — tabla por prenda con **Talla · Exist. · Pedido** — acomodado de a **tres tarjetas por fila**, con la paleta del kiosko (banda café, encabezados crema, zebra en las tallas, borde tostado). Cada prenda va **N/total, el mismo número que la pantalla de captura** (las dos leen `conteo_jornada_service.alcance`). Práxedis: 10 prendas, 94 tallas, 2 páginas |
| **Tira de tickets** | La de siempre: una tira de 80 mm por prenda, misma salida (`open_conteo_print_dialog`, encolada al servidor desde un kiosko), con corte entre tiras |

Archivos: `services/conteo_hoja_carta_service.py` (HTML puro + paginación propia) · `ui/helpers/conteo_hoja_carta_print_helper.py` (QPrinter con diálogo, HP preseleccionada si existe; también a PDF) · `ConteoDestinoDialog` en `ui/dialogs/conteo_jornada_dialogs.py`.

> [!warning] Lo que solo se ve imprimiendo con Qt (no en el navegador)
> `QTextDocument` **ignora el CSS de tablas**: bordes, alturas y fondos van como atributos HTML (`border`, `cellspacing`, `bgcolor`, `height`). Y **parte tablas entre páginas**: la paginación es propia (`paginar`), con alturas estimadas; una fila de tarjetas nunca se corta y la primera página carga con el encabezado. Por eso las previsualizaciones se hacen con el render de Qt (`render_qt.py` en el scratchpad), no con Brave.

> [!info] La HP está fallando (2026-09-11)
> Daniel la dejó descansar; por eso el selector. Hay un diagnóstico listo por si un día quiere saber qué le pasa: `scripts\diagnostico_impresora_carta.bat` (lista impresoras como las ve Qt y como las ve Windows, y manda una hoja de prueba a cada HP) → `scripts\enviar_reporte.bat`. Ojo: desde la Mac en la red de la tienda ese script **sí imprime** en la HP (salió una hoja de prueba el 11/09).

**Última vez que se contó (2026-09-13):** al elegir escuela, tanto en el kiosko como en el celular, se ve cuándo se contó por última vez y quién ("hace 3 días (Stayce)", o "nunca"). Manda la última jornada terminada; sin jornada, la fecha más reciente de sus tallas. Si fue hace menos de 7 días avisa antes de abrir. `ultimos_conteos` en `conteo_jornada_service`.

**Contar desde el celular (2026-09-13):** la misma hoja en la PWA, sin papel; ver [[31 - PWA Libreta Móvil]]. Sigue existiendo la hoja carta y la tira para quien las prefiera.

## La jornada es de la escuela, no de la persona (2026-09-13)

Lo que pidieron las empleadas después de una semana usándolo: **imprimían la hoja con la sesión de otra** y luego no podían capturar con la suya; **dos podían abrir la misma escuela** y pisarse; y querían que **una ya contada no apareciera** en el menú. Cuatro cambios, mismo servicio, se ven igual en kiosko y celular:

1. **Una sola jornada abierta por escuela** (o prenda de básicos). Elegir una que ya está en proceso no abre otra: el kiosko dice *"Práxedis la empezó Fanny a las 10:20 y sigue a medias"* con **Seguirla / Imprimir otra hoja / Cancelar** (`_conteos_ofrecer_seguir`). El selector la marca `EN PROCESO (Fanny)` en naranja; en el celular la ficha dice "En proceso · Fanny" y al tocarla sigue esa jornada (`POST /movil/conteos` devuelve la existente con `en_proceso`).
2. **Sin candado de dueña.** Cualquiera con gafete captura y termina; cada talla guarda quién (`contado_por`). Descartar sigue siendo solo de Daniel. `JornadaAjena` ya no se lanza.
3. **Las contadas hace menos de 14 días no salen** al empezar ni al imprimir; casilla **"Ver todas"** (kiosko) o enlace "Ver todas (N contadas hace poco)" (celular). Una en proceso se ve siempre.
4. **Si dos capturan la misma talla con otro número, no se pisan**: la segunda ve *"Ana puso 5 (hoy 10:32), tú 7 — ¿Reemplazar con lo tuyo?"*. No → queda lo de Ana y su número aparece bloqueado; Sí → gana lo suyo a su nombre. Mismo número = nada que preguntar. La hoja trae `quien` por talla (nombre junto a la talla en el celular, tooltip en el kiosko). De paso, el kiosko ya guarda por `guardar_tallas`: antes `registrar_conteos_lote` podía **duplicar** una talla si dos tenían la pantalla abierta.

**Tablero de escuelas (2026-09-14):** el HISTORIAL (8 jornadas recientes) se volvió **ESCUELAS Y BÁSICOS · cuándo se contó cada una**: todas las escuelas y prendas básicas con último conteo (hace N días / nunca), fecha, quién, tallas y estado (Aplicada / Por revisar / Descartada / Conteo viejo / Nunca / En proceso · quién). Orden: en proceso, luego de la más reciente a la más vieja, nunca al final. `tablero_conteos` / `FilaTablero` (con `jornada_id` de la última terminada: **doble clic abre el comparativo**, ver [[37 - Revisar y Pedidos]]). Lo capturado de todas las jornadas se trae en una consulta (`capturado_por_jornada`, 2026-09-15: de 85 a 60 consultas, 1.5 → 1.1 s por wifi desde la Mac; y el 17/09 el alcance de todas las escuelas en 2 consultas con `alcances_en_lote` / `conteo_service.obtener_variantes_para_conteo_varias`: abrir Conteos pasó de ~85 a ~10 consultas). En producción: 59 filas — 20 contadas la semana del 10–13, 10 con conteo viejo (junio–julio), 29 nunca.

**Aplicar deja negativos (2026-09-15):** `confirmar_ajustes_lote` ya no omite la talla cuyo ajuste dejaría el total en negativo (era un guardia del CheckConstraint que se quitó en `cd3e4f5a6b7c`): se aplica igual y el negativo es la señal de recontar. Antes quedaba inflada justo la talla que se acabó entre el conteo y el aplicar. El aviso del diálogo ahora dice "N sin diferencia" en vez de "se omitieron (dejarían negativo)".

**Básicos por prenda (2026-09-14):** Daniel: *"quiero saber cuándo fue la última vez que lo contamos, y a veces no quiero contar todos los pantalones, solo un tipo o solo un color de suéter"*. Columna `conteo_jornada.prenda` (migración `de4f5a6b7c8d`): `""` = todo el tipo, o el nombre completo del producto. `alcance(escuela_id, tipo_pieza, prenda)`, `abrir_jornada(prenda=…)`, hoja carta, tira (`build_conteo_sheets_basicos(prenda=)`), Revisar e Historia aceptan prenda; `clave_alcance` da `("basicos", tipo)` o `("basicos", tipo, prenda)`; `ultimos_conteos` tiene clave por prenda (jornada de esa prenda, o fallback a `ultimo_conteo_at` de sus tallas) y una prenda contada también actualiza el tipo. Chocan: una prenda abierta con "todo el tipo" y con la misma prenda; dos prendas distintas del mismo tipo se cuentan a la vez. **Selector del kiosko:** el combo de tipo dice "Pantalón · hoy (Stayce)" y un tercer combo "Todas las de Pantalón · hoy (Stayce)" / "Pantalón Gris Escolar · hoy (Stayce)" / "Pantalón Azul · nunca". **Mapa de conteos (2026-09-20):** `conteo_mapa_service` — `estado_talla(v)` = `al_dia` (contada y dentro de vigencia) / `vieja` (contada, `requiere_conteo`) / `nunca`; `_cifras()` da tallas, al_dia, viejas, nunca, `pct_al_dia`, `ultimo_dias` (el conteo más reciente que la tocó) y `estado` del conjunto; `resumen()` (2 consultas para todas las escuelas vía `obtener_variantes_para_conteo_varias` + básicos), `escuela(id)`, `basicos(tipo)`, `todo()` y `html()` (página autónoma con el JSON embebido, `</` escapado). Celular: `mapaConteos` / `mapaPintarDetalle` (dueño). Kiosko: `ui/dialogs/conteo_mapa_dialog.py` — `ConteoMapaWidget` **dentro de la sección Conteos** en lugar de la tabla (`Ver tabla` la trae de vuelta; `_conteos_alternar_tabla`), pintado con **widgets del kiosko** (`ui/helpers/conteo_mapa_widgets.py`: `Semaforo` barra pintada a mano, `Mosaico` = `libretaCard` con borde izquierdo del color del estado y fondo naranja si está en proceso, `CapaMapa` (total + rejilla por nivel + básicos), `Prenda` (tarjeta que despliega sus fichas de talla) y `CapaDetalle` (‹ Mapa como `secondaryButton`); `conteo_mapa_rich_text.py` queda como alternativa sin usar). Con el modo oscuro del sistema el scroll del diálogo salía negro: colores explícitos, datos en hilo `conteo-mapa` (`recargar(forzar=)`, no más de una vez por minuto; `_refresh_conteos_vista` lo llama), sin WebEngine. El botón 🗺 Mapa abre el mismo widget grande. `resumen()` trae `en_proceso` (quién · hoja) y `quien` por escuela/tipo. `html()` (página autónoma) sigue disponible. Tests: `test_conteo_mapa_service` (cifras, detalle, HTML, widget: una a la vez y no antes de un minuto, navegación por capas, sección con Ver tabla, mosaicos con quién).

**Qué es un básico (2026-09-20):** **todo** producto general (sin escuela) activo que sea de uniforme, tenga o no existencia y esté o no ligado a una escuela. Fuera solo la **ropa normal**: categoría o tipo de prenda en `conteo_service.CATEGORIAS_ROPA_NORMAL` (ropa casual, casual, calzado, accesorios —plural, no "Accesorio"—, temporada, ropa interior, interior, pijamas, descanso, deportivo casual, formal). `_filtro_basicos()` es la única definición y la usan la lista (`obtener_variantes_basicos_para_conteo`), el estado y el calendario. Antes solo los ligados por catálogo: se quedaban fuera Pants 2pz Liso Rojo/Verde, Suéteres Rojo/Vino, boinas, moños… En producción: 56 → 196 prendas (1,874 tallas). Test: `test_basicos_son_todos_los_generales_de_uniforme_menos_la_ropa_normal`.

**Limpieza (2026-09-20):** `scripts/reubicar_conteos_por_prenda.py` — `planear()` detecta en cada jornada de básicos con `prenda` los renglones de otro producto; `aplicar()` los pasa a la jornada de su prenda (misma persona, mismo tipo; si no existe la crea con la `iniciada_at` de la origen) y copia `terminada_at`/`revisada_at`. No toca lo contado ni lo aplicado. Corrido en producción el 20/09 (138 tallas). Test: `test_reubicar_conteos_por_prenda`.

**Captura por prenda (2026-09-20):** la pantalla de captura amarrada a una jornada carga `alcance(escuela_id, tipo_pieza, prenda)` — antes cargaba `obtener_variantes_basicos_agrupadas(tipo)` y una jornada de "Pantalón Gris" traía todos los pantalones. Test: `test_una_jornada_de_una_sola_prenda_carga_solo_esa_prenda`.

**Imprimir deja huella (2026-09-18):** el flujo real es *imprimir → contar en papel → capturar después*, y la jornada solo nacía al capturar, así que la segunda empleada no veía nada y volvía a imprimir. Ahora `conteo_jornada_service.registrar_impresion(session, escuela_id, tipo_pieza, prenda, empleada_code, empleada_nombre) → (jornada, ya_habia)`: abre la jornada (o toma la abierta) y suma `hojas_impresas` / `impresa_at` (migración `f06b7c8d9e0f`); `JornadaRef.hoja_texto` = "hoja impresa 10:32" / "2 hojas impresas, la última 10:40". Kiosko: `_conteos_imprimir_hoja` exige gafete, si el selector trae una abierta pregunta con `_conteos_confirmar_otra_hoja` ("No imprimir" por defecto), y al salir la hoja (carta o tira) llama `_conteos_anotar_impresion`. El selector muestra `EN PROCESO (Fanny) · hoja impresa 10:32` y el rótulo dice "no la imprimas otra vez". El banner del kiosko ya no imprime: lleva a Conteos. El celular recibe `en_proceso.hoja`. Tests: `test_imprimir_la_hoja_abre_la_jornada…`, `ImprimirDejaHuellaTests`. **Pendiente de ver en la tienda:** una jornada abierta por impresión y nunca capturada queda "a medias" hasta que la capturen o la eliminen (Eliminar/Reasignar en las tarjetas).

**Celular, pantalla Contar (2026-09-18):** "Empezar un conteo" tiene pestañas **Escuelas | Básicos** (`contTab`), un buscador (`contNorm`, sin acentos; con texto muestra todas las coincidencias, incluidas las escondidas por recientes) y las escuelas en grupos (`contPintarEscuelas`): *En proceso* (ámbar) · *Tocan* (⚠, acento) · *Nunca contadas* · *Contadas* (aquí viven las escondidas y el "Ver todas"). En el API, `toca` solo es True si `escuelas_con_conteo_vencido` la trae **con `dias_para_vencer` no nulo** (ya contada y vencida); una nunca contada no lleva ⚠. Cache `maximoda-v22`. Test: `test_una_escuela_nunca_contada_no_lleva_alerta_y_una_vencida_si`. **Ojo con los ids:** la hoja pinta en `#cont-prendas` y el selector de básicos en `#cont-prenda-sel`; el 17 se repitió el id y la hoja quedó en blanco (`test_pwa_index_html` vigila que ningún id del HTML estático se repita).

**Celular (2026-09-17):** el API `GET /movil/conteos` trae en cada tipo sus `prendas` (`nombre`, `corto` —el completo si dos prendas comparten nombre corto—, `ultimo`, `en_proceso`), y al tocar un tipo con varias prendas se abre "Pantalón: ¿qué contamos?" con *Todas las de Pantalón* + una ficha por prenda; el POST lleva `prenda`. Cache `maximoda-v15`. El tablero sigue por tipo.

**Cuando una escuela se parte (2026-09-14):** al separar Práxedis en Primaria y Secundaria, la jornada de Stayce (94 tallas, contó las dos) se partió a mano en dos jornadas con los mismos datos (24 → Secundaria, 26 → Primaria) reasignando `conteo_inventario.jornada_id` por escuela del producto; nada se recontó ni se volvió a aplicar. `avance` cuenta solo tallas que siguen en el alcance, por eso ya no sale "94 de 38". Receta en [[07 - Servicios - Catálogo e Inventario]].

**Eliminar y Reasignar (2026-09-13, noche):** en las tarjetas de jornadas a medias. *Eliminar* (dueño o quien la abrió) borra la jornada con lo capturado — nunca tocó el inventario; si alguna talla ya se aplicó, se niega. *Reasignar* (solo dueño) la pasa a otra empleada activa; lo capturado conserva quién lo contó. Nació de dos Emiliano Zapata abiertas antes de la regla de una sola. `eliminar_jornada` / `reasignar_jornada` / `puede_eliminarla`.

**Después (no urgente):** código de barras en la hoja para saltar al renglón al escanear.

## Tests

`test_conteos_seccion.py` (12) · `test_conteo_subir_dialog.py` (13) · `test_conteo_jornada_service.py` (27) · `test_conteo_jornada_ui.py` (29) · `test_conteo_hoja_carta.py` (19) · `test_api_conteos_movil.py` (en proceso, conflictos, `reciente`). Los de la página usan **dobles** (`SimpleNamespace` + métodos desligados), no la ventana real: construirla levanta hilos y roba foco a otras pruebas.

## Rediseño y rendimiento de la sección Conteos (2026-09-22)

Daniel: *"siento que hicimos un montón de cambios en conteos… el diseño abruma"*. La pantalla mezclaba el trabajo de la empleada con el panorama del dueño, y cargaba todo de golpe en el hilo de la UI.

**Ahora la pantalla sabe quién entró** (`_conteos_aplicar_rol`, `_conteos_ordenar_secciones`):

| | Empleada | Dueño (VEND-1) |
|---|---|---|
| Arriba | **TE TOCA CONTAR** con su botón "Imprimir hoja" por renglón (imprime ESA hoja, sin preguntar qué) | Tarjetas: **POR REVISAR** destacada y primera, POR CONTAR, A MEDIAS |
| Luego | jornadas a medias, y la lista de por revisar al final | **POR REVISAR** (de a 8, con "ver las otras N"), luego lo que toca |
| Mapa | cerrado, detrás de "Ver cómo va la tienda" | abierto, con "Ver tabla" y el Calendario |

Fuera: el "Actualizar" y el "Mapa" duplicados, el "2 · Cuenta en el piso y anota" que no hacía nada, la tarjeta MÍAS y la caja de "no hay conteos a medias". Ya no hay scroll horizontal (el renglón largo del mosaico del mapa fijaba 1,070 px de ancho mínimo).

**Qué se ve** (`conteo_jornada_service.lo_que_toca`): lo vencido según la vigencia de su escuela y lo que nunca se ha contado; lo que alguien ya está contando no entra. Orden: vencido de lo más viejo a lo más nuevo, y al final lo que nunca.

**Rendimiento** (contra la base de la tienda, como lo vive un kiosko):

| | Antes | Ahora |
|---|---|---|
| Vista del dueño | 3.2 s · 67 consultas (y ~5 s con lo nuevo) | **2.0 s · 30 consultas**, en un hilo |
| Vista de la empleada | — | 0.9 s · 24 consultas, en un hilo |
| La pantalla responde | cuando terminaba de cargar | **31 ms** |

- `avances_en_lote`: 3 consultas para todas las jornadas en vez de 3 por cada una (el avance de las 35 por revisar eran 99 idas a la base).
- `alcances_en_lote(..., cache=...)` y `tablero_conteos(..., cache=...)`: las tallas de cada escuela se traen una sola vez por refresco.
- `lo_que_toca(..., filas=...)`: reusa el tablero en vez de recalcularlo.
- La lectura completa vive en un hilo; mientras llega, el encabezado dice "actualizando…" y lo que ya estaba pintado se queda. Si cambió la persona mientras cargaba, lo que llega tarde se ignora.

Commits `caac66da` (rediseño) y `2d670a3d` (rendimiento). Pendiente: la misma mano en **Contar** del celular.

## Lo que falta contar se mide talla por talla (2026-09-22)

Daniel: *"faltan varias prendas, por ejemplo las calcetas, pero ya no aparece la opción para imprimir y contar; solo se contó una y faltan los demás colores"*.

**El problema:** `lo_que_toca` miraba la **última jornada**. Un conteo cerrado sin terminar (la Calceta: un color de siete) contaba como "ya contado" y desaparecía de la lista. Un primer arreglo por prendas de la última jornada tenía trampa: al contar el resto se abre una jornada nueva cuyo alcance sigue siendo todo el tipo, así que se vería "a medias" para siempre.

**La solución:** el mismo criterio del mapa — **talla por talla**. `lo_que_toca(session, mapa=None)` lee `conteo_mapa_service.resumen()` y devuelve `PorContar` (tallas, al_dia, viejas, nunca, ultimo, quien_en_proceso) con `faltan`, `empezado` y `motivo`. Ya no importa en cuántas tandas se contó: aparece mientras queden tallas sin contar o vencidas, y desaparece cuando de verdad está completo.

- **Orden:** primero lo **empezado**, de lo que menos falta al que más (cerrar lo que está a medio camino); luego lo **vencido**, de lo más viejo; al final lo que **nunca** se contó.
- **La hoja sale solo con lo que falta** cuando ya se empezó: `grupos_para_hoja(..., solo_lo_que_falta=True)` quita las tallas contadas y vigentes (si no quedara nada, imprime la hoja completa).
- El renglón dice *"faltan 36 de 42 tallas · se contó hace 3 días"*.

En la tienda al aplicarlo: 32 pendientes, 26 de ellos **empezados** — Básicos · Falda 232 de 266 tallas, Pants 2pz 228 de 254, Pantalón 219 de 314, Suéter 189 de 223… Todo eso estaba invisible.

> [!warning] Dos bombas de Qt desactivadas el mismo día
> - Los avisos de los diálogos (`uniforme_escuela_dialog`, `school_product_link_dialog`) usaban `QTimer.singleShot(4000, self._limpiar_status)`: si la ventana se cerraba antes, el timer disparaba sobre un objeto ya borrado. Ahora el timer es **hijo del diálogo** y muere con él.
> - `test_inventory_label_dialog` esperaba el debounce con `QTest.qWait(400)`; bombear el bucle de eventos ahí tumbaba el proceso al azar en la suite en paralelo (`-n 6 --dist load`). **Ya pasaba antes**: al commit anterior le bastaron 4 tests de relleno para caerse 1 de 3 veces. Ahora el test dispara el timer del debounce a mano. Tres corridas limpias en ~38 s.

## Ventana de Historial: auditar sin entrar a Revisar (2026-09-22)

Daniel: *"¿cómo puedo compararlo con conteos anteriores?, ¿cómo saco pedidos?, debería existir una ventana para auditar esto, ver cómo evoluciona… ahora solo aparece cuando voy a revisar un conteo"*.

Todo eso **ya existía** (`ConteoComparativoDialog`, `ConteoRevisionDialog`, `PedidoHojaDialog`, `EscuelaHistoriaDialog`) pero solo se alcanzaba desde dentro de Revisar o con doble clic en una tabla escondida. Ahora tiene puerta propia: **Conteos → 📊 Historial** (solo el dueño).

- Izquierda: cada escuela y tipo de básicos con su último conteo, con buscador.
- Derecha: **todos** sus conteos — cuándo, quién, tallas, **faltaron**, **sobraron**, **pedido** y estado. Ahí se lee la evolución: si una escuela siempre sale con faltantes, salta.
- Del conteo elegido: **⇄ Comparar con el anterior** (de cualquiera, aplicado o no), **Revisar / decidir el pedido** (dice "Ver el pedido que decidiste" si ya se revisó) y **🧾 Hoja de pedido** (solo si ese conteo dejó pedido).
- Arriba: **📈 Cómo evoluciona** (ventas por semana y qué talla se pide más).

Código: `ui/dialogs/conteo_historial_dialog.py` + `conteo_jornada_service.historial_de_alcance` (una consulta agrega tallas, faltantes, sobrantes y pedido de todos los conteos del alcance). **No trae lógica nueva**: arma la ventana con los servicios que ya existían — cumple la regla de [[39 - Brújula]] ("una lógica, un servicio"). Commit `9f962f6e`.
