# Instalacion en Windows

## Requisitos

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

## 6. Ejecutar la app

```powershell
.venv\Scripts\python -m pos_uniformes.main
```

## 7. Respaldo de base en Windows

El proyecto ya incluye un script portable:

```powershell
.venv\Scripts\python scripts\backup_database.py
```

Por defecto:

- genera un respaldo nuevo
- conserva 7 dias
- elimina respaldos mas viejos del mismo formato

Si `pg_dump` no esta en `PATH`, instala PostgreSQL con herramientas cliente o agrega su carpeta `bin`.

## 8. Sobre lector QR o pistola

La app funciona si el lector emula teclado HID.

Flujo:

- enfoca el campo `SKU` en `Caja`
- escanea el QR
- el lector escribe el SKU

Si tu lector usa modo serial o SDK propietario, necesitarias integracion adicional.

## 9. Validacion minima

- abrir login
- entrar con `admin`
- abrir `Inventario`
- registrar una entrada
- generar un QR
- vender por SKU en `Caja`
- revisar `Historial`
