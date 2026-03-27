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
