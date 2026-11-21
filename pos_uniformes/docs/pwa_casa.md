# La Libreta en casa (solo consulta) y la llave de sesiones

Actualizado: 2026-11-20.

La Libreta móvil (`pwa/index.html`, servida por la API en `/app`) corre en la
PC de la tienda. Desde 2026-11-20 también puede correr en casa, 24/7, leyendo
la copia viva de la base (Postgres `pos-viva` del servidor de casa, que se
recarga desde la tienda cada 15 min). **La casa solo consulta**: cortes, pagos,
etiquetas, bodega, conteos y presupuestos siguen en la Libreta de la tienda, y
la tienda nunca depende de la casa.

## Variables

| Variable | Dónde | Qué hace |
|---|---|---|
| `POS_PWA_MODO` | entorno o `pos_uniformes.env` | `casa` o `tienda`. Manda sobre lo que se deducía antes. Sin ella, todo igual que siempre: un snapshot SQLite (`POS_UNIFORMES_DB_URL=sqlite:///…`) es la casa y lo demás la tienda. |
| `POS_API_SECRET_KEY` | entorno o `pos_uniformes.env` | Llave con que se firman las sesiones (JWT). Opcional: sin ella se usa la del archivo (abajo). |
| `POS_API_TOKEN_EXPIRE_HOURS` | entorno o `pos_uniformes.env` | Cuántas horas dura una sesión. Default 8. |
| `POS_PWA_PEDIR_COPIA_URL` | entorno (solo casa) | A dónde pedir una copia nueva de la tienda (el disparador del servidor de casa, p. ej. `http://192.168.68.115:8926/copia`). |
| `POS_PWA_PEDIR_COPIA_TOKEN_FILE` | entorno (solo casa) | Archivo con el token para ese disparador (se lee en cada petición; no viaja: firma cada petición con HMAC). Sin estas dos, `/movil/actualizar` contesta `sin_configurar`. |

`POS_PWA_MODO=casa` va **solo** en el entorno del servidor de la casa (su
contenedor), nunca en el `pos_uniformes.env` de la tienda: ese archivo también
lo leen el POS y el kiosko, y en modo casa la conexión a la base se abre en
solo lectura.

## Qué cambia en modo casa

- **Nada escribe.** Un middleware (`api/main.py`) contesta `409` con el mismo
  cuerpo que ya usaban las acciones de tienda
  (`{"detail": {"error": {"code": "solo_en_tienda", …}}}`) a todo lo que no sea
  `GET`/`HEAD`/`OPTIONS`. Las únicas excepciones son entrar y salir
  (`POST /api/v1/auth/login` y `/logout`) y pedir una copia nueva
  (`POST /api/v1/movil/actualizar`, abajo), que no tocan la base.
- **La base, en solo lectura.** La conexión se abre con
  `-c default_transaction_read_only=on` (además del `statement_timeout`): si algo
  se escapara, lo rechaza el propio Postgres. Conviene además conectarse con un
  usuario de solo lectura.
- **No reindexa Meilisearch al arrancar.**
- **Archivos:** solo lo inevitable en `data/` (la llave de sesiones y la copia
  local de nombres `empleadas_nombres.json`). En Docker, `data/` debe ser un
  volumen con permiso de escritura, y hace falta `TZ=America/Mexico_City`
  (el código usa `date.today()`).
- **Frescura.** `/api/v1/movil/inicio` agrega `"datos_de": "AAAA-MM-DDTHH:MM"`,
  la hora de la tienda de la copia que se está leyendo. Sale del `COMMENT` que
  deja la carga de `pos-viva` en la base
  («copia … (de la tienda a las AAAA-MM-DD HH:MM), cargada …»); `null` si no se
  puede leer. La Libreta lo enseña arriba, discreto: «Datos de la tienda de las
  14:15» (o «de ayer 18:45»). En modo tienda la llave no viene y no se ve nada.
- **Lo más nuevo al abrir.** `POST /api/v1/movil/actualizar` (con sesión;
  en la tienda es `404`) le pide al servidor de casa una copia nueva de la
  tienda sin esperarla (`services/pedir_copia_service.py`, máx. 3 s) y contesta
  `{"estado": …, "datos_de": …}`. `estado`: `pidiendo` o `en_curso` (la está
  sacando), `reciente` (la última es de hace menos de 2 min), `espera` (se
  pidió una hace poco y no salió), `fuera_de_horario` (fuera del horario de
  la tienda), `tope` (ya se pidieron 4 en la última hora o 24 hoy),
  `tienda_apagada`, `sin_configurar`, `sin_respuesta` o `error`. El token del
  disparador no viaja: cada petición lleva una firma HMAC de un solo uso
  (cabecera `X-Firma`, con hora y nonce), porque va por HTTP plano en la LAN.
  La Libreta lo llama al abrir, al recargar, al volver a la app tras más de
  1 min y con el ↻ junto a la hora; con `pidiendo`/`en_curso` muestra
  «Trayendo lo más nuevo de la tienda…» y vuelve a llamar a
  `/movil/actualizar` cada 8 s (máx. 2½ min): para cuando llega la copia nueva,
  cuando contesta otra cosa (`espera` si falló, `tienda_apagada`…) o al plazo.
  Cada vez que `datos_de` es otra que la de pantalla repinta enseguida la hora
  de arriba y la pantalla abierta (cualquiera, no solo inicio), aunque siga
  esperando. Con `tienda_apagada` o `fuera_de_horario`: «La tienda está
  cerrada: datos de las HH:MM». Lo demás no cambia nada en pantalla. Si el
  teléfono se duerme a media espera, al despertar insiste hasta una respuesta
  buena (o 2 fallas) y, si se volvió a la app, pide otra vez.
- **Freno al adivinar PIN** (`api/services/limite_login.py`). La copia de casa
  se alcanza por Tailscale; por empleada, tras 5 PIN equivocados se contesta
  `429` (`demasiados_intentos`, con `Retry-After`) durante 1 min, y cada fallo
  más duplica la espera hasta 15 min. Un PIN bueno lo reinicia. Vive en memoria
  (reiniciar la API lo borra). En la tienda no hay freno: nada cambia.
- **Versión de la base en `/health`.** Con `POS_PWA_MODO=casa`, `/health` agrega
  `"version_base"`: `igual`, `casa_mas_vieja` (la base trae una migración que
  este código no conoce), `casa_mas_nueva` o `desconocida`
  (`services/version_base_service.py`). El servidor de casa avisa si no es
  `igual`. En la tienda `/health` queda como siempre.

## La llave de sesiones (`data/api_secret.key`)

Hasta 2026-11-20 la llave era un texto fijo en el código, y el repo es
público: cualquiera podía fabricar una sesión de VEND-1. Ahora
(`utils/llave_api.py`):

1. Si `POS_API_SECRET_KEY` está y no es la llave pública vieja, esa manda.
2. Si no, se usa la guardada en `data/api_secret.key` dentro de la carpeta de
   datos del POS (`satellite_data_dir()`): junto al código en la PC de la tienda
   y en Linux; `%APPDATA%\PresupuestosSatelite\data\` en el ejecutable de
   Windows. La tienda corre la API desde el código fuente, así que ahí es
   `<checkout>\pos_uniformes\data\api_secret.key`, junto a
   `pos_uniformes.env`.
3. Si no existe, se genera una al azar (`secrets.token_urlsafe(48)`) **una
   vez**, se guarda ahí y se reutiliza en cada arranque. Permisos: `600` en
   Linux y macOS; en Windows `chmod` no restringe, así que se le quita la
   herencia con `icacls` y quedan solo la cuenta que corre la API, SYSTEM y
   Administradores (si `icacls` falla, se avisa en el log y la llave sirve
   igual). Aun así, la carpeta del checkout de la tienda debe ser solo de la
   cuenta del POS: ahí vive también la contraseña de Postgres.
4. Si arrancan dos procesos a la vez sin archivo (el vigía relanzando, o
   uvicorn con `--workers`), el primero que la crea gana y el otro usa esa: no
   se pisan (antes el segundo podía reemplazarla y dejar inválidas las sesiones
   del primero).

La tienda queda segura sola al actualizarse; no hay que pegar nada. La llave
nunca se escribe en el log y el archivo está en `.gitignore`. Si la carpeta no
se puede escribir, la API sigue funcionando con una llave en memoria (y avisa
en el log): las sesiones se pierden en cada reinicio.

**Efecto al actualizar:** los tokens viejos (firmados con la llave pública)
dejan de servir. Cada quien vuelve a entrar con su PIN **una vez** y listo.

Cada servidor (tienda y casa) tiene su propia llave: una sesión de la casa no
sirve en la tienda ni al revés. Para invalidar todas las sesiones de un
servidor basta con borrar su `data/api_secret.key` y reiniciar la API.

## Arrancar la API sin lo de escritorio

`requirements-api.txt` trae solo lo que la API necesita en Linux (sin PyQt,
pywin32, brother_ql ni alembic):

```bash
pip install -r pos_uniformes/requirements-api.txt
POS_PWA_MODO=casa TZ=America/Mexico_City \
  uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8000
```

`api_server.py` no sirve para esto: arrancar con `uvicorn`.
