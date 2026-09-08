# Afluencia: personas que entran, por hora

Cuenta con las cámaras del DVR cuántas personas entran a la tienda cada hora
(y cuántas pasan por fuera) y lo guarda en la tabla `afluencia_hora`. El kiosko
lo cruza con las ventas de la Libreta para mostrar la conversión por hora.

Corre como un proceso aparte en la PC servidor. **No usa el venv del POS**:
YOLO y OpenCV son pesados y no deben entrar al ejecutable del kiosko.

## Instalación (PC servidor, Windows): un solo paso

```bat
C:\Users\Pc\pos_uniformes\pos_uniformes\afluencia\instalar_afluencia.bat
```

Crea el entorno, copia la configuración, prueba el DVR, registra la tarea
"POS Afluencia" (arranca al iniciar sesión) y deja el contador corriendo.
A mano, equivale a:

```bat
cd C:\Users\Pc\pos_uniformes\pos_uniformes\afluencia
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy afluencia.json.example afluencia.json
```

La primera corrida descarga `yolov8n.pt` (6 MB). Lee el DVR de
`..\data\dvr_settings.json` (el mismo que configura el kiosko en
Administración → Cámaras) y Postgres de `..\pos_uniformes.env`.

## Calibrar las líneas de la puerta

```bat
.venv\Scripts\python contador_afluencia.py --calibrar
```

Deja en `calibracion\` un cuadro por cámara con cuadrícula 0.1 y la línea en
rojo. La línea va sobre el piso, cruzando la puerta; `lado_dentro` dice de qué
lado queda la tienda. Ajusta `afluencia.json` hasta que la línea quede bien.

## Probar sin tocar la base

```bat
.venv\Scripts\python contador_afluencia.py --sin-db --duracion 300 --debug-frames eventos
```

Imprime cada `entra` / `sale` y guarda un cuadro por evento en `eventos\`.

## Correr siempre

`contador_afluencia.bat` lo arranca en la PC servidor; agrégalo al Programador
de tareas de Windows al iniciar sesión. Guarda en Postgres cada minuto; si la
base no responde, acumula y reintenta.

Antes de correr en producción aplica la migración del POS:

```bat
cd ..
.venv\Scripts\alembic upgrade head
```
