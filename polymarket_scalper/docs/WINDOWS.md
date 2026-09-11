# Guía: correr el bot en Windows

Para Windows 10 y 11. Todo esto deja el bot en **paper trading**: recolecta datos reales del
mercado y simula operaciones, pero no firma órdenes ni toca una wallet. No hay dinero en riesgo.

## 1. Instalar Python

Descarga Python 3.11 o superior de <https://www.python.org/downloads/>. Durante la instalación
**marca la casilla "Add python.exe to PATH"**, abajo del todo. Es el paso que más se olvida y sin
él nada funciona.

Para comprobar, abre PowerShell (botón Inicio, escribe `powershell`) y escribe:

```powershell
py --version
```

Debe responder `Python 3.11.x` o superior.

## 2. Descargar el proyecto

Si tienes Git instalado:

```powershell
cd $HOME\Documents
git clone --branch claude/scalping-explanation-i569dx https://github.com/DMXFabian1/pos_uniformes.git
cd pos_uniformes\polymarket_scalper
```

Si no tienes Git, entra al repositorio en el navegador, botón verde **Code**, **Download ZIP**,
descomprime en Documentos y entra a la carpeta `polymarket_scalper` desde PowerShell con `cd`.

## 3. Instalar el bot

```powershell
powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1
```

Tarda unos minutos: crea un entorno aislado en `.venv`, instala las dependencias y comprueba que
el comando responde. Puedes volver a ejecutarlo cuando actualices el código; no borra nada.

> `-ExecutionPolicy Bypass` es necesario porque Windows bloquea los scripts descargados por
> defecto. Afecta solo a esa ejecución, no cambia la configuración del sistema.

## 4. Arrancar el bot

**Todo de un solo clic:** doble clic en **`INICIAR-TODO.bat`**. Abre el bot en una ventana, el
panel en otra y el navegador en el panel. Es la forma recomendada.

Si prefieres controlarlos por separado:

- **`Iniciar-bot.bat`** solo el bot.
- **`Abrir-panel.bat`** solo el panel, con el navegador.

Clic derecho sobre cualquiera de ellos, "Enviar a", "Escritorio (crear acceso directo)", y lo
tienes a mano sin buscar la carpeta.

**Desde PowerShell**, si lo prefieres:

```powershell
.\deploy\iniciar-bot.ps1
```

Deja esa ventana abierta. En los primeros segundos verás:

```
discovery: 191 mercados (nba=158, tennis=33)
mercados activos=191 tokens=382 nuevos=382 retirados=0
sports feed conectado
```

y cada minuto una línea `estado:` con los contadores. Eso significa que está recolectando.

**Ctrl+C lo detiene guardando los datos pendientes.** No cierres la ventana con la X: perderías
hasta 30 segundos de datos sin escribir.

El log queda en `logs\bot.log` y rota solo a los 10 MB, así que nunca llena el disco.

## 5. Usarlo desde VS Code (recomendado si prefieres no usar la terminal)

Abre VS Code, menú **Archivo → Abrir carpeta**, y elige la carpeta `polymarket_scalper`. VS Code
detecta la configuración incluida y te ofrece instalar la extensión de Python: acéptala.

A partir de ahí todo se ejecuta desde el menú, sin escribir comandos:

**Ctrl+Shift+P**, escribe `Run Task`, Enter, y elige de la lista:

| Tarea | Qué hace |
|---|---|
| **Bot: iniciar (paper trading)** | arranca el bot. También con **Ctrl+Shift+B** |
| **Panel: abrir en el navegador** | levanta el panel en http://127.0.0.1:8787 |
| **Informes: ver todo** | datos, arrastre de cripto, resultados, wallets, modelos y disco |
| **Informe: arrastre entre ventanas de cripto** | solo el estudio de la racha |
| **Mercados: ver cuáles se siguen** | la lista de mercados activos |
| **Mantenimiento: correr las pruebas** | las 60 pruebas del proyecto |

Cada tarea abre su propia pestaña de terminal dentro de VS Code. Para detener el bot, haz clic en
esa pestaña y pulsa **Ctrl+C**: guarda los datos antes de cerrar.

Si además quieres poner puntos de interrupción y ver el código paso a paso, pulsa **F5** y elige
una de las configuraciones: bot, solo recolectar, panel, replay o estudio del arrastre.

> La primera vez, si VS Code pregunta por el intérprete de Python, elige el que está en
> `.venv\Scripts\python.exe` dentro del proyecto. La configuración ya lo apunta, así que
> normalmente no pregunta.

## 6. Ver el panel

Doble clic en **`Abrir-panel.bat`**, la tarea de VS Code, o desde **otra** ventana de PowerShell:

```powershell
.\deploy\iniciar-panel.ps1
```

Abre el navegador solo en <http://127.0.0.1:8787>. Se actualiza cada 10 segundos. Puedes abrirlo y
cerrarlo cuando quieras, es independiente del bot.

## 7. Evitar que la PC se duerma

El bot ya bloquea la suspensión mientras corre (`collector.prevent_sleep` en `config.yaml`). La
pantalla sí puede apagarse, que es lo normal. Aun así, conviene revisarlo en el sistema:

**Configuración → Sistema → Inicio/apagado y suspensión**, y en "Suspender" elige **Nunca** para
la opción "Cuando está conectado". Si es una laptop, además déjala conectada a la corriente.

Para comprobar qué impide dormir al equipo, en PowerShell como administrador:

```powershell
powercfg /requests
```

Con el bot corriendo debe aparecer una entrada bajo `SYSTEM`.

## 8. Que arranque solo al encender la PC

Abre PowerShell **como administrador** (clic derecho en el icono, "Ejecutar como administrador"),
ve a la carpeta del proyecto y ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\programar-inicio.ps1
```

Registra dos tareas de Windows, `ScalperPolymarket-Bot` y `ScalperPolymarket-Panel`, que arrancan
al iniciar sesión y se reinician solas si fallan. Comandos útiles:

```powershell
Start-ScheduledTask -TaskName ScalperPolymarket-Bot     # arrancar ahora sin reiniciar
Get-ScheduledTask -TaskName ScalperPolymarket-*         # ver estado
Stop-ScheduledTask  -TaskName ScalperPolymarket-Bot     # detener
powershell -ExecutionPolicy Bypass -File deploy\programar-inicio.ps1 -Quitar   # quitar las tareas
```

Con las tareas activas no necesitas dejar ventanas abiertas. El log sigue en `logs\bot.log`.

## 9. Actualizar e informes con doble clic

- **`ACTUALIZAR.bat`** descarga la última versión y actualiza las dependencias. Cierra antes la
  ventana del bot con Ctrl+C.
- **`VER-INFORMES.bat`** muestra de una vez: qué datos hay, el estudio del arrastre entre ventanas
  de cripto, los resultados por tipo de señal, los modelos aprendidos y el uso de disco.

## 10. Comandos del día a día

Desde la carpeta del proyecto, con el bot corriendo o detenido:

```powershell
$s = ".venv\Scripts\scalper.exe"

& $s overview      # todos los informes de una pasada
& $s status        # qué tablas hay y desde cuándo
& $s updown-study  # ¿el sesgo al abrir una ventana de cripto es información o sobrerreacción?
& $s report        # lo que predijo vs lo que obtuvo, por tipo de señal
& $s wallets       # ranking de wallets por historial
& $s games         # partidos en vivo enlazados a mercados
& $s model         # precio del mercado vs modelo, partido por partido
& $s retention     # cuánto ocupa en disco y cuánto crece por día
& $s train         # entrenar el modelo (el paper trading lo hace solo cada 6 h)
& $s models        # versiones del modelo y cuál está en uso
```

## 11. Disco

Con el enfoque en NBA y tenis, y la limpieza automática que corre una vez al día, el crecimiento
permanente ronda los 200 a 400 MB por día. Para revisarlo:

```powershell
& $s retention                # uso actual y estimación de crecimiento
& $s retention --dry-run      # qué borraría, sin tocar nada
& $s retention --apply        # hacerlo ahora
```

Si te quedas corto de espacio, baja `keep_days` en `config.yaml` y reinicia el bot.

## 12. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `py no se reconoce como comando` | Python sin PATH | reinstala marcando "Add python.exe to PATH" |
| `ERROR: To modify pip, please run...` | pip no puede reemplazarse a sí mismo en Windows | ya resuelto en el script; si lo ves, instala a mano con `.venv\Scripts\python.exe -m pip install -e ".[learn]"` |
| `WARNING: Ignoring invalid distribution ~olymarket-scalper` | carpeta residual de una instalación interrumpida | inofensivo; `ACTUALIZAR.bat` y el instalador la borran solos |
| `no se puede cargar el archivo ... está deshabilitada la ejecución de scripts` | política de PowerShell | usa `powershell -ExecutionPolicy Bypass -File ...` como indica la guía |
| Caracteres raros en vez de acentos | consola en codificación antigua | los scripts ya fijan `PYTHONUTF8=1`; si lanzas el comando a mano, escribe antes `$env:PYTHONUTF8=1` |
| `libros_validos` muy bajo de madrugada | pocos partidos a esa hora | normal, no es un error |
| `flow_lag` de varios minutos | el indexador de Polymarket va con retraso | normal, no afecta a los precios del libro |
| El bot se detuvo solo de noche | la PC se durmió | revisa el paso 6 |
| El panel no abre | el proceso del panel no está corriendo | ejecuta `.\deploy\iniciar-panel.ps1` |

## 13. Qué esperar

- **Primeras horas:** se llena `data\`, aparecen las primeras wallets perfiladas y los partidos de
  tenis en vivo. La NBA solo muestra futuros hasta que arranque la temporada, a fines de octubre.
- **Primera semana:** `scalper report` empieza a tener decenas de posiciones por tipo de señal. Ahí
  se ve cuál estrategia tiene ganancia real después de comisiones.
- **Semanas 2 y 3:** el modelo de aprendizaje junta ejemplos suficientes y `scalper models` dice si
  le gana a la heurística.

Solo después de eso tiene sentido hablar de operar con dinero real.
