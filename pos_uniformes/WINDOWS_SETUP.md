# Instalacion y paquete para Windows

## Opcion recomendada para probar en Windows

Si quieres llevar la app como paquete y no instalar Python ni dependencias de la app en la PC destino:

1. Genera la build en una PC Windows de desarrollo con:

```powershell
scripts\build_windows_bundle.ps1
```

2. Eso produce:

- `dist\POSUniformes-<VERSION>\`
- `dist\POSUniformes-<VERSION>-windows.zip`

3. En la PC destino:

- descomprime `POSUniformes-<VERSION>-windows.zip`
- copia `pos_uniformes.env.example` como `pos_uniformes.env`
- ajusta host, puerto, base, usuario y password
- ejecuta `POSUniformes-<VERSION>.exe`

Importante:

- esta build ya incluye Python y librerias de la app
- no incluye PostgreSQL
- la PC destino solo necesita acceso a la base PostgreSQL correspondiente

## Opcion recomendada para una PC solo de empaquetado

Si tienes otra PC Windows y quieres usarla solo para sacar el zip listo:

```powershell
py scripts\windows_build_runner.py --branch codex/etiquetas-windows --with-precheck
```

Ese wrapper:

- hace `git fetch + checkout + pull` de la rama indicada
- asegura `.venv`
- instala dependencias de runtime y build
- ejecuta `scripts\build_windows_bundle.ps1`
- te deja listo `dist\POSUniformes-<VERSION>-windows.zip`

Opciones utiles:

```powershell
py scripts\windows_build_runner.py --branch codex/etiquetas-windows --skip-git
py scripts\windows_build_runner.py --branch codex/etiquetas-windows --create-seed-backup
py scripts\windows_build_runner.py --branch codex/etiquetas-windows --brother-driver-installer-path .\ruta\BrotherDriverInstaller.exe
```

Si solo quieres revisar los pasos sin ejecutarlos:

```powershell
py scripts\windows_build_runner.py --branch codex/etiquetas-windows --dry-run
```

## Opcion recomendada para correr la app local con pasos visibles

Si quieres abrir la app en Windows y ver claramente en que paso va:

```powershell
py scripts\windows_run_dev.py
```

Ese script:

- revisa si existe `pos_uniformes.env`
- si falta, lo copia desde `pos_uniformes.env.example`
- corre `alembic upgrade head`
- corre `check_startup_health.py`
- abre la app
- imprime tiempos por paso para que sepas si sigue avanzando

Opciones utiles:

```powershell
py scripts\windows_run_dev.py --dry-run
py scripts\windows_run_dev.py --skip-precheck
py scripts\windows_run_dev.py --skip-migrations
```

## Opcion recomendada para instalar y configurar PostgreSQL local

Si la PC Windows es nueva y todavia no tiene PostgreSQL listo para POS Uniformes:

```powershell
py scripts\windows_setup_postgres.py --install-postgres
```

Ese script:

- puede lanzar la instalacion de PostgreSQL via `winget`
- te pide el password del usuario PostgreSQL si hace falta
- crea o actualiza `pos_uniformes.env`
- crea la base `pos_uniformes` si no existe
- corre migraciones
- corre precheck

Opciones utiles:

```powershell
py scripts\windows_setup_postgres.py --dry-run
py scripts\windows_setup_postgres.py --db-name pos_uniformes_pruebas
py scripts\windows_setup_postgres.py --skip-precheck
py scripts\windows_setup_postgres.py --skip-migrations
```

Nota:

- para la parte de instalacion, lo mas seguro es correr PowerShell como administrador
- el instalador de PostgreSQL puede abrir ventanas propias durante el paso interactivo

## App satelite de Presupuestos

La app satelite de Presupuestos se distribuye por separado del POS principal. Usa la misma base PostgreSQL y los mismos servicios compartidos, pero abre una ventana dedicada solo para:

- escaneo rapido de SKU como pantalla principal
- consulta inmediata de precio y detalles de la presentacion
- catalogo simplificado para cotizar por escuela y extras generales
- consultar presupuestos
- guardar borradores
- emitir presupuestos
- reencontrarlos por folio o telefono
- compartir por WhatsApp
- imprimir despues

Build en Windows:

```powershell
scripts\build_presupuestos_satelite_windows.ps1
```

Si tambien quieres correr el precheck de base en la PC de build:

```powershell
scripts\build_presupuestos_satelite_windows.ps1 -WithPrecheck
```

Eso produce:

- `dist\PresupuestosSatelite-<VERSION>\`
- `dist\PresupuestosSatelite-<VERSION>-windows.zip`

En la PC satelite:

1. descomprime `PresupuestosSatelite-<VERSION>-windows.zip`
2. copia `pos_uniformes.env.example` como `pos_uniformes.env`
3. apunta ese `.env` a la misma base PostgreSQL del sistema principal
4. ejecuta `PresupuestosSatelite-<VERSION>.exe`

Importante:

- no necesitas instalar el POS principal en esa PC
- la app satelite no abre caja ni sesion de efectivo
- ambas PCs deben ver la misma base para compartir presupuestos y clientes

## Opcion recomendada para dejar app + base local listas

Si quieres que el bundle de Windows llegue con una base semilla lista para restaurar:

1. En la PC Windows de build genera la build con respaldo semilla:

```powershell
scripts\build_windows_bundle.ps1 -CreateSeedBackup
```

O si ya tienes un `.dump` especifico:

```powershell
scripts\build_windows_bundle.ps1 -SeedBackupPath .\ruta\mi_base_inicial.dump
```

2. Eso deja dentro del bundle:

- `setup_windows_local_bundle.ps1`
- `setup_windows_local_bundle.bat`
- `seed\initial.dump` si se incluyo semilla

3. En la PC destino, despues de instalar PostgreSQL local, ejecuta:

```powershell
.\setup_windows_local_bundle.ps1 `
  -DbHost localhost `
  -DbPort 5432 `
  -DbName pos_uniformes `
  -DbUser postgres `
  -DbPassword postgres
```

Si el usuario que crea la base es distinto, puedes pasar tambien:

```powershell
.\setup_windows_local_bundle.ps1 `
  -DbHost localhost `
  -DbPort 5432 `
  -DbName pos_uniformes `
  -DbUser pos_app `
  -DbPassword app_password `
  -AdminUser postgres `
  -AdminPassword admin_password
```

Ese script:

- crea la base si no existe
- restaura `seed\initial.dump` si viene incluido
- genera `pos_uniformes.env` junto al ejecutable
- deja la app lista para abrirse localmente

Si el bundle no trae semilla y aun asi quieres solo dejar la conexion preparada:

```powershell
.\setup_windows_local_bundle.ps1 -AllowEmptySchema
```

## Requisitos para generar la build

- Windows 10 u 11
- Python 3.12
- PostgreSQL 16 o superior
- VS Code

## 1. Instalar Python

- Descarga Python 3.12 desde [python.org](https://www.python.org/downloads/windows/)
- Durante la instalacion activa `Add python.exe to PATH`

## 2. Instalar PostgreSQL

- Instala PostgreSQL para Windows
- Recuerda:
  - host
  - puerto
  - base de datos
  - usuario
  - password

Si aun no existe la base:

```powershell
createdb -U postgres pos_uniformes
```

## 2.1. Requisito extra si vas a imprimir etiquetas en Windows

- Para impresion real de etiquetas con Brother QL-800, instala el driver oficial de Brother antes de probar la app.
- Enlace validado:
  - https://support.brother.com/g/b/downloadhowto.aspx?c=mx&lang=es&prod=lpql800eus&os=10069&dlid=dlfp101277_000&flang=201&type3=347
- Sin ese driver, Windows puede dejar visible solo impresoras virtuales o no exponer correctamente la impresora de etiquetas.
- Si quieres que el bundle de Windows tambien lleve el instalador del driver, genera la build con:

```powershell
scripts\build_windows_bundle.ps1 -BrotherDriverInstallerPath .\ruta\BrotherDriverInstaller.exe
```

- Luego, en la PC destino, puedes correr:

```powershell
.\setup_windows_local_bundle.ps1 -InstallBrotherDriver
```

- Nota: lo mas seguro es incluir el instalador oficial descargado manualmente por ti. El proyecto no descarga drivers de terceros automaticamente.
- Si ya copiaste el instalador a `packaging\windows\drivers\`, las futuras builds tambien lo incluiran aunque no vuelvas a pasar `-BrotherDriverInstallerPath`.

## 3. Crear entorno virtual

Desde la carpeta del proyecto:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Configurar variables

En PowerShell:

```powershell
$env:POS_UNIFORMES_DB_HOST="localhost"
$env:POS_UNIFORMES_DB_PORT="5432"
$env:POS_UNIFORMES_DB_NAME="pos_uniformes"
$env:POS_UNIFORMES_DB_USER="postgres"
$env:POS_UNIFORMES_DB_PASSWORD="postgres"
```

Si prefieres dejarlo fijo, puedes crear un script `.ps1` local para exportarlas antes de abrir la app.

## 5. Aplicar migraciones

```powershell
.venv\Scripts\python -m alembic upgrade head
```

## 6. Ejecutar la app en modo desarrollo

```powershell
.venv\Scripts\python -m pos_uniformes.main
```

## 7. Generar paquete portable

```powershell
scripts\build_windows_bundle.ps1
```

Si tambien quieres validar la conexion y esquema en esa misma PC de build:

```powershell
scripts\build_windows_bundle.ps1 -WithPrecheck
```

Si ademas quieres incluir una base semilla dentro del bundle:

```powershell
scripts\build_windows_bundle.ps1 -CreateSeedBackup
```

O usando un `.dump` ya existente:

```powershell
scripts\build_windows_bundle.ps1 -SeedBackupPath .\ruta\mi_base_inicial.dump
```

Si tambien quieres incluir el instalador oficial del driver Brother para etiquetas:

```powershell
scripts\build_windows_bundle.ps1 -BrotherDriverInstallerPath .\ruta\BrotherDriverInstaller.exe
```

Tambien puedes dejarlo guardado una vez en:

```text
packaging\windows\drivers\
```

y las siguientes builds lo incluiran automaticamente.

Resultado:

- carpeta: `dist\POSUniformes-<VERSION>\`
- zip portable: `dist\POSUniformes-<VERSION>-windows.zip`

La build incluye:

- ejecutable `POSUniformes-<VERSION>.exe`
- dependencias de Python
- assets y migraciones necesarias
- archivo `pos_uniformes.env.example`
- archivo `VERSION`
- `setup_windows_local_bundle.ps1`
- `setup_windows_local_bundle.bat`
- `seed\initial.dump` cuando se genero o copio una semilla

La version sale del archivo `VERSION` en la raiz del proyecto.

## Versiones y builds de prueba

Para no confundirnos:

- `VERSION` define la version visible del producto dentro de la app.
- `VERSION` tambien define el nombre base del ejecutable y del bundle:
  - `POSUniformes-<VERSION>.exe`
  - `POSUniformes-<VERSION>-windows.zip`
- La rama y el commit no cambian la version del producto por si solos.

Si usas GitHub Actions para builds de prueba en Windows:

- el artifact subido agrega `rama + commit corto` al nombre para distinguir pruebas entre si
- ejemplo:
  - producto: `2026.03.18`
  - rama: `codex/etiquetas-windows`
  - commit: `fa050e0`
  - artifact: `POSUniformes-2026.03.18-codex-etiquetas-windows-fa050e0-windows.zip`

Regla recomendada:

- mientras estemos probando internamente, podemos repetir `VERSION` y distinguirnos por `rama + commit`
- cuando decidamos una build candidata real para entregar, entonces si actualizamos `VERSION`

## 8. Configuracion del paquete

En la carpeta final de la build:

1. copia `pos_uniformes.env.example`
2. renombralo a `pos_uniformes.env`
3. ajusta sus valores

Ejemplo:

```ini
POS_UNIFORMES_DB_HOST=localhost
POS_UNIFORMES_DB_PORT=5432
POS_UNIFORMES_DB_NAME=pos_uniformes
POS_UNIFORMES_DB_USER=postgres
POS_UNIFORMES_DB_PASSWORD=postgres
```

La app leera ese archivo automaticamente al arrancar.

Si usas `setup_windows_local_bundle.ps1`, este archivo se genera automaticamente.

## 9. Respaldo de base en Windows

El proyecto ya incluye un script portable:

```powershell
.venv\Scripts\python scripts\backup_database.py
```

Por defecto:

- genera un respaldo nuevo
- conserva 7 dias
- elimina respaldos mas viejos del mismo formato

Si `pg_dump` no esta en `PATH`, instala PostgreSQL con herramientas cliente o agrega su carpeta `bin`.

## 9.1. Respaldo automatico con Programador de tareas (Task Scheduler)

Para que la base se respalde sola cada dia sin que nadie tenga que acordarse:

### Que hace el runner automatico

El script `scripts/run_scheduled_backup.py`:

- genera un `.dump` con `pg_dump`
- aplica rotacion automatica (elimina respaldos mas viejos de N dias)
- actualiza un archivo de estado que el POS puede leer en `Configuracion > Respaldo`
- opcionalmente copia el respaldo a una ubicacion externa (OneDrive, disco externo, etc.)

### Crear la tarea en Task Scheduler

Abre PowerShell como administrador y ejecuta:

```powershell
$python   = "C:\ruta\al\proyecto\pos_uniformes\.venv\Scripts\python.exe"
$script   = "C:\ruta\al\proyecto\pos_uniformes\scripts\run_scheduled_backup.py"
$args     = "--format custom --retention-days 14"

$action   = New-ScheduledTaskAction -Execute $python -Argument "$script $args" `
              -WorkingDirectory "C:\ruta\al\proyecto\pos_uniformes"

$trigger  = New-ScheduledTaskTrigger -Daily -At "02:00"

$settings = New-ScheduledTaskSettingsSet `
              -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
              -StartWhenAvailable

Register-ScheduledTask `
  -TaskName   "POSUniformes - Respaldo automatico" `
  -Action     $action `
  -Trigger    $trigger `
  -Settings   $settings `
  -RunLevel   Highest `
  -Force
```

Ajusta `C:\ruta\al\proyecto\pos_uniformes` a la ruta real del proyecto en esa PC.

### Agregar un respaldo extra al mediodia (opcional)

Si la operacion lo justifica, registra una segunda tarea con un trigger adicional:

```powershell
$trigger2 = New-ScheduledTaskTrigger -Daily -At "14:00"

$action2  = New-ScheduledTaskAction -Execute $python -Argument "$script $args" `
              -WorkingDirectory "C:\ruta\al\proyecto\pos_uniformes"

Register-ScheduledTask `
  -TaskName   "POSUniformes - Respaldo automatico mediodia" `
  -Action     $action2 `
  -Trigger    $trigger2 `
  -Settings   $settings `
  -RunLevel   Highest `
  -Force
```

### Copiar respaldo a ubicacion externa (recomendado)

Si ya tienes OneDrive, Google Drive, un NAS o un disco externo montado, agrega `--external-dir`:

```powershell
$args = "--format custom --retention-days 14 --external-dir `"C:\Users\usuario\OneDrive\RespaldosPOS`""
```

O define la variable de entorno en el sistema para no repetirla en cada tarea:

```
POS_UNIFORMES_BACKUP_EXTERNAL_DIR=C:\Users\usuario\OneDrive\RespaldosPOS
```

Regla importante: el respaldo no debe vivir solo en la misma maquina que corre PostgreSQL.

### Verificar que la tarea funciona

1. Abre `Programador de tareas` en Windows
2. Busca `POSUniformes - Respaldo automatico`
3. Haz clic derecho y elige `Ejecutar`
4. Revisa que aparezca un `.dump` nuevo en `backups\database\`
5. Abre el POS, ve a `Configuracion > Respaldo` y confirma que muestra el ultimo respaldo automatico

### Eliminar la tarea si hace falta

```powershell
Unregister-ScheduledTask -TaskName "POSUniformes - Respaldo automatico" -Confirm:$false
```

## 10. Sobre lector QR o pistola

La app funciona si el lector emula teclado HID.

Flujo:

- enfoca el campo `SKU` en `Caja`
- escanea el QR
- el lector escribe el SKU

Si tu lector usa modo serial o SDK propietario, necesitarias integracion adicional.

## 11. Validacion minima

- abrir login
- entrar con `admin`
- abrir `Inventario`
- registrar una entrada
- generar un QR
- si vas a imprimir etiquetas, confirmar que la Brother QL-800 aparece en Windows con su driver oficial instalado
- vender por SKU en `Caja`
- revisar `Historial`
