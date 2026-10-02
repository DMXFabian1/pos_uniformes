---
tags: [pos-uniformes, telegram, resumen, alertas, servidor]
---

# Telegram: resumen diario, recordatorios y comandos (2026-09-08)

> [!info] `/descanso_X` mueve el descanso y `/vino_X` compensa faltas (2026-09-13)
> `/descanso_Fanny` en un día que no es el suyo deja su fijo de esa semana como trabajo (un solo descanso, sin falta). `/vino_Stayce` en su día de descanso cuenta como día trabajado de más y **tapa una falta del mismo ciclo** en la nómina. Ver [[30 - Calendario de Empleadas]].

> [!info] `/asistencia` y la tarea de las 11:00 (2026-09-12)
> Quién vino hoy. Nadie checa entrada: la presencia se **deduce** del primer movimiento en la Libreta o de una jornada de conteo abierta; el mensaje lo dice y separa "presente desde HH:MM" de "sin movimientos todavía" (no se cuelga la falta por no haber vendido). Descanso y falta salen del calendario. **Daniel tiene la última palabra:** al final de la lista va **un comando tocable por empleada** — `/falta_Fanny · /descanso_Fanny` (una sola palabra, sin acentos; si dos se llaman igual, inicial del apellido: `FannyO`). Un toque marca el día en el calendario (el mismo de León) con nota "Daniel desde Telegram"; **repetirlo quita la marca**; la marca se ve en el propio comando (✗ /falta_Fanny). Que *vino* ya se deduce; *falta* manda aunque haya venta. Con espacio también: `/falta Fanny`, `/vino Fanny`. Servicio: `services/asistencia_service.py`. (Se probaron botones inline y Daniel los descartó; la infraestructura `teclado / editar_mensaje / responder_toque` queda en `telegram_service` sin usarse.) Tarea **"POS Asistencia"** a las 11:00 (`resumen_diario_telegram.bat --asistencia`), INFRA_VERSION 4.

> [!success] Para qué
> Control del negocio desde el celular, dentro o fuera del país, sin abrir nada: el servidor de la tienda habla con Telegram. Bot propio (BotFather), sin librerías externas (`urllib`).

## Configuración (una vez, en `pos_uniformes.env` de la PC servidor)

```
POS_UNIFORMES_TELEGRAM_BOT_TOKEN=<token de @BotFather>
POS_UNIFORMES_TELEGRAM_CHAT_ID=<tu chat>
```

- Token creado el 2026-09-08 (guardado en el env local de la Mac, gitignored). **2026-09-09: configurado en la PC principal; el bot contesta.** Tropiezos resueltos: certificado del antivirus (truststore + reintento) y nombres de tarea con ":" (schtasks los rechaza). El bot ignora comandos de más de 10 min (mandados con él apagado) y pide reenviarlos.
- **Todo de un jalón en la principal:** `scripts\configurar_telegram.bat` (pide el token, espera tu "hola" al bot, guarda el chat id, manda un resumen de prueba e instala bot + tareas). Chat id de Daniel ya descubierto el 2026-09-08 (probado desde la Mac: el resumen llegó).
- `scripts\instalar_resumen_diario.bat [HH:MM] [auto]` crea las tareas de Windows: **POS Resumen 1645 / 1745** (sin ":" en el nombre: Windows no lo acepta) (el resumen sale **15 min antes de cerrar**: 17:45; jueves y domingo 16:45 — `--si-toca` decide según el horario de la tienda; con HH:MM queda a hora fija), **POS Pendientes** (13:30), **POS Telegram bot** (al iniciar sesión, queda escuchando). Con `auto` además **POS Corte 1630 / 1730** (corte automático por hora; hoy apagado por decisión de Daniel).

## Qué manda

**Resumen del día** (`/resumen` o la tarea de cierre, 15 min antes de cerrar): ventas (operaciones, piezas, efectivo/tarjeta, por empleada), cortes con **sobrante/faltante** y reactivo, retiros del cajón, pagos y faltas del día, afluencia y conversión de las cámaras, pendientes, y mañana (quién descansa, pagos próximos). Cada bloque es defensivo: si una tabla no existe aún, se omite.

**Pendientes** (13:30 o `/pendientes`): pagos de hoy/atrasados, posibles faltas, descansos, horarios sin configurar. Si no hay nada, no manda nada.

**Comandos** (solo responde al chat configurado; a cualquier otro lo ignora):

| Comando | Hace |
|---------|------|
| `/corte` | Hace el corte ahora (pagos del día incluidos), **manda el ticket del encargado a la impresora de la tienda** (cola `trabajo`) y responde con venta, pagos, retiros, lo que se saca y el reactivo |
| `/corte 5000` | El mismo corte, pero **se retiran $5,000**: el ticket cuadra con esa cifra (es la oficial) |
| `/corte sintarjeta` | El mismo corte, **sin la línea de los cobros con tarjeta** en el papel |
| `/corte 5000 sintarjeta` | Se pueden juntar |
| `/nocorte` | Deja pasar el corte que se propuso hoy (no se hace) |
| `/estado` | Qué hay en caja ahora, sin cortar |
| `/resumen` | El resumen del día |
| `/pendientes` | Lo que falta por registrar |
| `/ayuda` | La lista |

## Supervisor único (2026-09-10)

Las 4 tareas de cada 5 min (bot y PWA, arranque + vigía) abrían una consola un instante y arrancaban Python de cero; Daniel seguía viendo la ventana y pidió gastar menos. Ahora hay **un solo proceso oculto**: `scripts/supervisor.py` (`supervisor.bat`).

| Pieza | Qué hace |
|-------|----------|
| `supervisor.py` | Cada **60 s** revisa: ¿el bot late? ¿la PWA contesta `/health`? Si no, mata al pegado y lo levanta sin ventana; calma de 3 min entre intentos por servicio; mutex (`Global\POSUniformesSupervisor`); log en `logs/supervisor.log`. Sin token de Telegram, solo cuida la PWA |
| `--pedir-reinicio` | Deja `data/supervisor.reiniciar`; el supervisor la consume en su siguiente vuelta y reinicia bot + PWA. Lo usan `abrir_pos.bat` y `actualizar_pc_principal.bat` (ya no llaman a los vigías) |
| Tareas | **POS Supervisor** (al iniciar sesión) y **POS Supervisor check** (cada 30 min; si ya corre, sale). Ambas vía `correr_oculto.vbs`. `instalar_supervisor.bat` las crea y **borra** las viejas (POS Telegram bot/vigia, POS PWA servidor/vigia) |
| Quién lo instala | `instalar_supervisor.bat` directo, o `instalar_resumen_diario.bat` / `instalar_servidor_pwa.bat` / `quitar_parpadeo_tareas.bat` (todos delegan) |

Los vigías (`telegram_bot_vigia.py`, `servidor_pwa_vigia.py`) siguen existiendo: el supervisor usa sus funciones y sirven a mano. El bot hace una vuelta cada ~25 s (antes 15).

## El bot se cuida solo (2026-09-09)

"Funcionaba de a ratos": dependía de una ventana negra (la cerraban, o tras actualizar seguía el proceso viejo, o dos procesos peleaban por `getUpdates` → 409). Ahora:

| Pieza | Qué hace |
|-------|----------|
| `scripts/telegram_bot.py` | **Candado** (mutex de Windows `Global\POSUniformesTelegramBot`: si ya hay un bot, el nuevo sale) · **latido** en `data/telegram_bot.heartbeat` cada vuelta (≤15 s) · `data/telegram_bot.pid` · **log** en `logs/telegram_bot.log` (rotativo) · nunca muere: si truena, espera 15 s y sigue |
| `scripts/telegram_bot_vigia.py/.bat [--reiniciar]` | Si el latido tiene < 3 min no hace nada; si no, mata el pid guardado y **levanta el bot sin ventana** (`CREATE_NO_WINDOW`). `--reiniciar` fuerza matar+levantar. Sin token configurado, no hace nada |
| Tareas | **POS Telegram bot** (al iniciar sesión → vigía) · **POS Telegram vigia** (cada 5 min). Las crea `instalar_resumen_diario.bat` |
| Actualización | `abrir_pos.bat` y `actualizar_pc_principal.bat` llaman `telegram_bot_vigia.bat --reiniciar` al final: el bot toma el código nuevo solo |

`telegram_bot.bat` ahora solo llama al vigía con `--reiniciar` (ya no deja ventana). Si algo raro pasa: leer `logs\telegram_bot.log`. Tests: `test_telegram_vigia`.

## Alertas al instante (2026-09-09)

Además del resumen y los comandos, el bot **avisa solo**:

| Alerta | Cuándo | De dónde sale |
|--------|--------|---------------|
| 🧾 Corte hecho | Cualquier corte (dueño, León, `/corte`, tarea): quién, hora, venta efectivo, pagos (por empleada), lo que se saca, reactivo. Si el dueño contó y hubo diferencia, la dice; ≥ $50 lleva ⚠️ | `corte_caja_service.cerrar_corte` → cola |
| 💸 Retiro del cajón | Al apuntarlo: monto, motivo, quién, hora | `retiros_service.registrar_retiro` → cola |
| ⏰ Cierre sin corte | 10 min después de cerrar, si hubo movimientos y no hay corte con fecha de hoy; una vez al día | Vigilante del bot |
| 🚨 Fuera de horario | Movimiento de la Libreta antes de las **09:00 (supuesto)** o después del cierre (18:00 / 17:00 jue-dom) | Vigilante del bot |

**Cómo viaja:** la tabla `alerta_telegram` (migración `w6e7f8a9b0c1`) es una cola. Cualquier máquina (kiosko, PWA, tarea) deja ahí el texto y **el bot de la PC servidor lo manda en su siguiente vuelta** (≤ 15 s). Así los kioskos no necesitan el token. Si no hay red, se reintenta hasta 5 veces. Si la base aún no tiene la tabla, el corte/retiro se guarda igual y la alerta se pierde sin romper nada.

`services/alertas_service.py`: `encolar`, `enviar_pendientes`, `texto_alerta_corte/retiro`, `Vigilante.revisar` (puro: recuerda el último movimiento revisado y si ya avisó hoy; en la primera vuelta no reclama lo viejo), `procesar`. La hora de apertura vive en `horario_tienda_service.APERTURA`. Tests: `test_alertas`.

## El corte pregunta antes de imprimir (2026-09-09)

A la hora del corte (30 min antes de cerrar) el sistema **ya no cierra la caja solo**: manda a Telegram lo que hay y espera a que Daniel conteste `/corte`. Si no contesta, se lo recuerda **una** vez (20 min después); si sigue sin contestar, la caja se queda sin corte y entra la alerta de "cierre sin corte".

| Pieza | Qué hace |
|-------|----------|
| `services/corte_propuesta_service.py` | Estado del día en `data/corte_propuesto.json` (fecha, momento, si ya se recordó). `anotar_propuesta`, `anotar_recordatorio`, `cancelar` (lo hace `/nocorte`), `toca_recordar` |
| `scripts/corte_automatico.py` | Sin argumentos: propone y avisa. `--recordar`: recuerda una vez. `--simular`, `--forzar` siguen |
| Tareas | **POS Corte 1630 / 1730** (propone) y **POS Corte recordatorio 1650 / 1750**, todas ocultas. Solo con `instalar_resumen_diario.bat HH:MM auto` |

## Avisos a las pantallas (`/aviso`) — 2026-10-01

Daniel: *"me gustaría enviar mensajes desde Telegram y se vean como aviso, de
hecho creo que esa ventana de avisos le falta mucho por mejorar"*.

`/aviso Junta a las 6` sale **a pantalla completa** en los satélites, encima de
lo que estén haciendo. Reutiliza la cartelera que ya existía (tabla `anuncio`,
overlay, LISTEN/NOTIFY); lo nuevo es lo que cambia al mandarlo **de lejos**:

| Hueco al mandar de lejos | Qué se hizo |
|---|---|
| Nadie vuelve a pasar a apagarlo | `anuncio.expira_en`. Por omisión 12 h; `/aviso 3h …`, `30m`, `2d`. Un «hoy cerramos temprano» no amanece puesto |
| Nadie contesta | `anuncio.pide_acuse` + tabla `anuncio_visto`. En la pantalla hay **«✅ Enterada»**; al tocarlo le llega a Daniel *«✅ Evelyn vio el aviso en Entrada»* |

### Las reglas del aviso con acuse

- **Un toque al aire no lo quita.** Si se fuera de un roce, el acuse no querría
  decir nada. Solo sus dos botones lo cierran.
- **«Luego»** existe para no dejar la caja bloqueada con un cliente enfrente:
  esconde el aviso y vuelve a salir hasta que alguien lo acuse.
- **No se cierra solo.** Los anuncios normales se van a los 20 s; uno con acuse
  espera.
- **No rota.** La cartelera no pasa de largo un aviso sin acusar.
- **Una vez acusado en esa pantalla** deja de pedirlo ahí (sigue pidiéndolo en
  las demás): no estorba dos veces por el mismo gesto.
- **Idempotente por pantalla:** dos toques = un renglón y un solo mensaje a
  Daniel.
- Si no hay empleada con sesión, el acuse se guarda sin nombre: vale más un
  «alguien en Entrada lo vio» que nada.

### La ventana de avisos, lo que le faltaba

- La letra era fija (64/40 px): un mensaje de tres renglones se salía de la
  pantalla. Ahora **baja de tamaño según el largo**.
- No decía **de cuándo era** el aviso. Ahora trae `AVISO · hace 5 min`.
- El pie decía *"Toca la pantalla para volver"* también cuando era un aviso.
- En el menú admin del satélite: casilla **«Pedir que confirmen»**, selector de
  plazo, y la lista de activos dice **quién lo vio** y cuándo se quita.

### Control desde el chat (lo segundo que pidió el mismo día)

*"me gustaría controlarlos de telegram"*. Cuatro cosas que antes solo se podían
desde el menú admin del satélite:

| Gesto | Qué hace |
|---|---|
| **Mandarle una foto al bot** | Sale a pantalla completa. Sin comando: es el gesto más corto que hay. El pie de foto es el aviso, y ahí también valen el plazo y la `@pantalla`. Antes el bot ignoraba las fotos por completo |
| `/aviso @caja2 Ven un momento` | Solo en esa pantalla. El `@` ignora espacios y acentos (`@caja2` = «Caja 2»); si dos empiezan igual **no adivina**, y si no existe lo pone en todas avisando |
| `/cartel Promoción de mochilas` | El que **no** interrumpe: rota en la cartelera cuando nadie está tocando, sin «Enterada» y con prioridad 0 (el aviso urgente va en 10) |
| `/avisos` → tocar uno | Su propia pantalla con **🗑 Quitarlo**, **⏱ +3 h / +12 h** y **🔄 Que lo vean otra vez** |

Detalles que importan:

- **`+3 h` cuenta desde ahora**, no desde el vencimiento viejo: si ya venció,
  «+3 h» tiene que dar tres horas de hoy.
- **«Otra vez» crea un id NUEVO** y apaga el viejo. Tiene que ser así: cada
  kiosko recuerda los ids que ya acusó para no estorbar dos veces con lo mismo,
  así que revivir el original no haría que nadie lo volviera a ver. Los acuses
  de la vuelta anterior quedan guardados.
- **Si la foto no se puede bajar o leer, no se crea nada.** Más vale no poner
  nada que poner un cuadro negro en la tienda.
- Un correo en el texto (`juan@correo.com`) no se confunde con una pantalla: el
  `@` solo se lee al principio.

`bajar_archivo` / `foto_mas_grande` viven en `telegram_service.py` (getFile +
descarga, con el mismo manejo del certificado del antivirus que el resto, y un
tope de 10 MB).

### Piezas

| Pieza | Archivo |
|---|---|
| Texto y botones del bot | `services/telegram_avisos_service.py` (`mandar`, `mandar_foto`, `resumen`, `detalle`, `texto_y_botones`, `atender`, `buscar_pantalla`, `aviso_de_acuse`) · prefijo `av:` |
| Más vida a uno puesto | `anuncio_service.alargar`, `anuncio_service.reponer` |
| Fotos | `telegram_service.bajar_archivo` / `foto_mas_grande` · `telegram_bot_service.atender_foto` (lo llama el bucle de `escuchar`) |
| Acuse y vigencia | `services/anuncio_service.py` (`vigente`, `vence_en`, `marcar_visto`, `ya_visto_en`, `quien_vio`) |
| Pantalla | `ui/anuncio_overlay.py` (botones, letra que se ajusta) · `ui/helpers/anuncio_cartelera.py` (`al_acusar`) |
| Enganche | `ui/quote_satellite_window.py` → `_registrar_acuse_de_aviso` (off-thread: DB + Telegram) |
| Migración | `c2d3e4f5a6b7_avisos_con_acuse_y_vencimiento` |
| Tests | `test_telegram_avisos` (97) · `test_anuncio_cartelera` (52) · `test_bot_conexion` (13) |

**Pendiente en producción:** correr `alembic upgrade head` en la PC principal.

Relacionado: [[17 - App Satélite]] · [[41 - Chuleta - atajos y comandos]]

## El día que todo se probó en la tienda (2026-10-02)

Daniel mandó fotos de la pantalla. Lo que se vio no estaba en ningún test.

### Lo que salió mal, y por qué ningún test lo atrapó

| Lo que se vio | La causa |
|---|---|
| El aviso **transparente**: se veía el kiosko detrás y el título no aparecía | El fondo colgaba del `background-color` de la hoja de estilo, y Qt solo lo pinta en un QWidget pelado bajo condiciones que **cambian entre plataformas**: en la Mac sí, en el Windows de la tienda no |
| La foto como una **estampilla** de 20 px | El escalado se medía contra el QLabel, y el label medía lo que su pixmap: huevo y gallina. El primer cuadro mandaba para siempre |
| **Bandas blancas** detrás de cada texto | Con una hoja de estilo en el padre, Qt dibuja también a los hijos con el estilo de hojas y **cada etiqueta se pinta su propio fondo** |

**El fondo ahora lo pinta `paintEvent` a mano**, que no depende de nada de eso.

> [!warning] La lección, que es de método
> Los primeros tests miraban los píxeles del overlay y **pasaban igual con el
> código roto**, porque este Qt sí respeta la hoja. Tres tests verdes
> custodiando un bug. El que sirve **le quita la hoja de estilo antes de
> mirar**. Y las otras dos las encontré **renderizando las cuatro pantallas y
> mirándolas** — no leyendo el código.

### El cierre a media venta

> *"Estaba imprimiendo un tiket y salió el anuncio, se bugeó y se cerró"*

El aviso aparecía **encima de un diálogo abierto** y le robaba el foco. Ahora la
cartelera pregunta si hay un modal abierto: si lo hay, el aviso **no sale**, se
guarda y se enseña al cerrarse (reintenta cada 4 s). La cartelera por
inactividad tampoco se mete. Si no se puede saber, se asume ocupada: **ante la
duda gana la venta**.

Y pintar un anuncio ya no puede llevarse el proceso — en este programa una
excepción dentro de un slot de Qt puede tumbar la app entera.

---

## Revisión a conciencia de anuncios (2026-10-02)

Daniel pidió revisar. Salieron **cinco**, todos del mismo tipo: código que
funcionaba en el orden en que lo probé y no en el orden en que ocurre.

1. **El acuse vivía solo en la RAM del kiosko.** Bastaba reiniciarlo —cosa que
   pasa en cada publicación— para que el recado le volviera a salir a quien ya
   lo leyó. `filas_para_cache` ahora deja fuera lo que esa pantalla acusó.
2. **Una pantalla retirada dejaba el aviso colgado para siempre**, esperando un
   acuse que no iba a llegar. Solo cuentan las vistas en los últimos 7 días;
   *apagada desde ayer sí cuenta* (mañana la prenden y tiene que verlo).
3. **`cerrar_si_ya_lo_vieron` devuelve `(False, 0)`** tanto al cerrar como al no
   poder averiguarlo, y el mensaje deducía «ya lo vieron» de que `faltan` fuera
   cero: le habría dicho que se quitó algo que seguía puesto.
4. **`area_para_imagen` preguntaba `isVisible()`** del pie de foto, pero la
   cartelera **pinta y después muestra**: siempre False, el pie nunca se
   descontaba.
5. **`/avisos` decía «toca uno» y mandaba el texto pelón** — los comandos
   siempre se contestaban sin botones. Ahora `/avisos`, `/prestamos` y `/menu`
   llevan los suyos.

**Cómo se encontraron:** corriendo el ciclo completo (mandar → acusar → cerrar →
reponer → cachear) e imprimiendo qué pasaba en cada paso.

### El acuse ya no se pierde si se cae la PC

`services/acuse_local_queue_service.py`: si la base no contesta al tocar
«Enterada», el acuse se encola en disco y el watchdog lo sube al volver, con
**la hora del toque** («lo tocaron hace 2 h; la PC estaba apagada»).

La cartelera **arranca leyendo esa cola**, que es lo que de verdad cierra el
agujero: aunque el kiosko se reinicie con la base caída, lo acusado no vuelve.
El drenado va **antes** de guardar el cache — si fuera después, el aviso ya
acusado volvería a bajar y a aparecer en la misma vuelta.

### Una vez visto, el aviso terminó

> *"Una vez que ponen enterada, debería de ya no salir de nuevo, solo que me
> avise que ya se enteraron y ya"*

Acusar solo dejaba de **pedir** acuse y el recado seguía rotando como anuncio
común. Ahora se va de esa pantalla, y cuando lo acusaron todas las que le
tocaban, el aviso **se apaga solo**. Un aviso es un recado, no un cartel: para
quedarse puesto está `/cartel`.

---

## El bot cuenta su propio silencio (2026-10-02)

Ese día la PC se quedó sin internet y el bot llevaba horas muerto: sin resumen,
sin alertas, sin `/corte`. Daniel se enteró **por accidente**, al intentar
actualizar. Con él fuera una semana, se habría visto igual que una tienda
tranquila.

El bot no puede avisar mientras está incomunicado —esa es la falla— pero sí
anotar el hueco y contarlo al volver:

```
📡 Volví a tener línea.
Estuve 2 h 16 min sin poder hablar, de las 09:14 a las 11:30.
En ese rato no te llegó nada: ni resumen, ni alertas, ni los avisos
de préstamos o gastos.
```

| Decisión | Por qué |
|---|---|
| Solo cuenta si una consulta a Telegram **falla** | El bot vivo sin alcanzar la red; eso es lo que pasó |
| **La noche no cuenta** | Si la PC se apaga al cerrar ninguna consulta falla. «Estuve 15 h callado» cada mañana sería ruido, y el ruido se ignora |
| Menos de 5 min no se reporta | La red parpadea |
| El estado va **en disco** | El supervisor reinicia el bot; si se cayó a las 9 y arrancó a las 11, el hueco sigue siendo de dos horas |

`services/bot_conexion_service.py` · `test_bot_conexion` (13).

Es el tercer caso del mismo patrón, después del respaldo que nadie disparaba y
del «ya estás al día»: **el silencio pasando por normalidad.**

---

## Préstamos: se deciden desde el aviso (2026-10-02)

> *"Me gustaría al momento que me llegue el mensaje del bot decidir aprobarlo o
> no, no que solo me informe"* — y *"no es muy claro el mensaje"*.

El aviso traía monto y motivo y mandaba a `/prestamos`: para contestar había que
acordarse de un comando y volver a buscar de quién era. Ahora:

```
💵 Evelyn Ortiz pide $800.00 prestados
Para: la inscripción de mi hijo

Lleva ganado: $1,412.00
Puede pedir hasta: $988.40
Le quedarían: $612.00 de su próximo pago

[ ✅ Prestarle a Evelyn ] [ ✖️ Ahora no ] [ 💵 Ver todos ]
```

El nombre va **dentro del botón**: con dos avisos en el chat, un «Aprobar» pelón
no dice de cuál. Aprobar sigue sin estar a un toque desde el **tablero** —ahí no
hay contexto—; en el aviso sí lo hay.

Escribiendo el test salió **código muerto propio**: `pedir` no la deja pedir si
ya tiene algo por cobrar, así que la línea «Ya debe» no se podía ver nunca.

### Y el motivo, de un toque

> *"Me dicen que no quieren escribir para qué, ¿podemos poner chips?"*

Seis en dos renglones: **Escuela · Doctor · Renta · Despensa · Un pago · Otra
cosa**. El motivo **se sigue pidiendo** —Daniel lo necesita para decidir— pero
ya no cuesta un teclado en pantalla con un cliente esperando. Son amplios a
propósito: nadie tiene que contar su vida para pedir prestado de su propio
sueldo (hay un test que los limita a doce letras).

«Otra cosa» **no llena el renglón: lo abre**. Si lo llenara, a Daniel le
llegaría «Para: Otra cosa» y tendría que preguntar igual.

## `/pulso` y la comparación (2026-10-02)

Daniel: *"perfeccionemos el bot, ¿tú qué crees que le haga falta?"*. La
respuesta no eran más comandos: al bot le faltaba **juicio**. Daba cifras y
ninguna manera de juzgarlas.

### `/pulso` — ¿está todo en pie?

Para contestar esa pregunta había que mandar `/hoy`, `/cortes`, `/asistencia`,
acordarse del respaldo y adivinar si los kioskos estaban prendidos: cinco
comandos y una corazonada. Ahora es una pantalla:

```
🫀 La tienda ahora — 02/10 12:24

⚠️ Abierta · nadie ha movido nada todavía
· Vendido: $0.00
   ↓ 100% abajo de un viernes normal a esta hora ($3,958)
⚠️ Último corte: hace 12 días

⚠️ Pantallas: 0 de 3 · apagada: Entrada, Caja 2
✅ Respaldo: hoy

✅ Nada esperando tu respuesta
```

Junta lo que se construyó en la semana: respaldo, pantallas, préstamos, avisos.

| Regla | Por qué |
|---|---|
| Cada renglón se gana su marca (✅ / ⚠️ / ·) | Se lee de un vistazo sin entender ninguna cifra |
| Lo que no se pudo averiguar **se dice** | Un `/pulso` que calla lo que no sabe enseña a confiar de más |
| Cada bloque es independiente **con rollback** | En Postgres una consulta fallida deja la transacción abortada y **todo lo que sigue falla también**. Sin el rollback, un bloque malo se llevaba la vista entera |

Lo del rollback salió corriéndolo contra la base real, no leyendo.

### Comparar: `$4,200` ¿es bueno?

`services/comparativa_service.py`. Dos decisiones que hacen que valga:

1. **Contra el mismo día de la semana** (4 semanas atrás). Una tienda de
   uniformes no vende igual lunes que sábado; comparar contra "ayer" habla del
   calendario, no del negocio.
2. **Hasta la misma hora.** A las 11 llevas dos horas de venta; compararlas
   contra un día completo diría que vas hundido **siempre**, y un bot que solo
   da malas noticias se ignora.

Los días sin venta (cerrado, festivo) se saltan: promediar un cero convierte un
día bueno en uno malo. Debajo del 8% se dice «como un viernes normal» — fingir
precisión en el ±3% es inventar una señal donde solo hay ruido.

> [!warning] Un test atrapó un defecto de diseño
> «El mejor viernes del mes» se anunciaba por ganar un 3%. Eso es ruido, y
> anunciarlo así enseña a no creerle al bot — y entonces tampoco se le cree el
> día que sí pasa algo. Ahora la banda de «normal» se evalúa primero, y cuando
> sí destaca se dicen **las dos cosas**: que es el mejor y por cuánto.

`/hoy` también la trae. Tests: `test_comparativa` (11) · `test_pulso` (13).

## El bot iba lento: era el saludo TLS (2026-10-02)

Daniel: *"el bot funciona algo lento en telegram"*. Primero se midieron los
comandos contra una base real, y **ninguno era el problema**:

```
/ayuda 0 ms · /cortes 3 ms · /avisos 3 ms · /pagos 11 ms · /pulso 14 ms
/menu 24 ms · /hoy 38 ms · /estado 153 ms · /contar 173 ms
```

El costo estaba en la red. `_llamar` abría una **conexión nueva en cada
llamada**, o sea un saludo TLS completo cada vez. Medido desde la Mac:

| | por llamada |
|---|---|
| Conexión nueva cada vez | **571 ms** |
| Conexión reutilizada | **182 ms** |

Un 68% menos **en una red buena**. En la de la tienda —WiFi, con pérdida— un
saludo TLS son varias idas y vueltas más, así que la diferencia es mayor. Y el
bot hace una llamada por cada cosa que contesta.

Ahora usa un `PoolManager` de urllib3 **con nuestro mismo contexto TLS**, el que
confía en el certificado del antivirus. Eso era lo delicado: `requests` con su
propio paquete de certificados habría roto la tienda.

> [!tip] Red de seguridad
> Este es el único camino por el que habla el bot, y romperlo sería dejarlo mudo
> con Daniel de viaje. Si el camino rápido falla por cualquier motivo que no sea
> el certificado, la llamada se hace por urllib como siempre y nadie se entera.

### Dos bugs que atraparon los tests, uno de ellos viejo

1. **`urlopen` guarda la causa en `.reason`**, no en la cadena de excepciones.
   Sin mirar ahí, el error del certificado se perdía y no se reintentaba sin
   verificar — el bot mudo en la tienda. Lo atrapó un test que ya existía.
2. **No hay que seguir `__context__`.** Es «qué se estaba atendiendo cuando
   esto se lanzó», no «qué lo causó». Siguiéndolo, un error cualquiera lanzado
   dentro del `except` del certificado heredaba su causa y se daba por
   certificado también, y el reintento se quedaba dando vueltas.

`telegram_service._pedir` / `_obtener_pool` / `_es_de_certificado` ·
`ConexionReutilizadaTests` en `test_resumen_diario`.

## Infraestructura

| Pieza | Archivo |
|-------|---------|
| Envío | `services/telegram_service.py` (enviar_mensaje, obtener_chat_ids, partir_mensaje) |
| Resumen | `services/resumen_diario_service.py` (recolectar + formatear, texto_solo_pendientes) |
| Bot | `services/telegram_bot_service.py` (parsear, atender_texto, escuchar) · `scripts/telegram_bot.py/.bat` |
| Scripts | `scripts/resumen_diario_telegram.py/.bat` (`--imprimir`, `--chat-ids`, `--fecha`, `--pendientes`) · `scripts/corte_automatico.py/.bat` (`--simular`, `--forzar`) · `scripts/instalar_resumen_diario.bat` |
| Tests | `test_resumen_diario`, `test_telegram_bot`, `test_alertas`, `test_horario_tienda` |

Probado desde la Mac contra la base real (`--imprimir`): el resumen sale aunque falten las tablas nuevas. Para alertas nuevas: `alertas_service.encolar(session, texto)` desde cualquier lado, o sumar una revisión al `Vigilante`.

Relacionado: [[33 - Caja, Nómina y Corte Automático]] · [[32 - Cámaras y Afluencia]] · [[29 - Updates y Mensajería]]
