# Instructivo de prueba en PC del negocio

Objetivo: abrir `POS Uniformes` en la PC del negocio usando una base separada de pruebas, sin tocar la base real.

## Qué archivo llevar

Copiar este archivo a la PC del negocio:

- `C:\dev\pos_uniformes\pos_uniformes\dist\POSUniformes-2026.03.18-windows.zip`

Ese `.zip` ya incluye:

- el ejecutable
- la carpeta `_internal`
- el driver Brother
- la base de prueba en `seed\initial.dump`

## Dónde colocarlo

Descomprimir el `.zip` completo en una carpeta local, por ejemplo:

- `C:\POSUniformes-Pruebas`

No mover ni borrar archivos internos del bundle.

## Paso 1: abrir PowerShell en la carpeta

Entrar a la carpeta donde quedó el `.exe`.

Ejemplo:

```powershell
cd C:\POSUniformes-Pruebas
```

## Paso 2: instalar PostgreSQL si hace falta

Si la PC del negocio no tiene PostgreSQL instalado, instalar primero PostgreSQL 17.

Intentar con:

```powershell
winget install -e --id PostgreSQL.PostgreSQL.17 --source winget --accept-source-agreements --accept-package-agreements
```

Durante la instalación:

- dejar el puerto `5432`
- usar el usuario `postgres`
- recordar la contraseña elegida
- dejar instaladas las `Command Line Tools`

## Paso 3: preparar la base de pruebas

Si PostgreSQL en esa PC usa usuario `postgres` y contraseña `postgres`, correr:

```powershell
.\setup_windows_local_bundle.ps1 -DbName pos_uniformes_pruebas -InstallBrotherDriver
```

Si PostgreSQL usa otra contraseña, correr:

```powershell
.\setup_windows_local_bundle.ps1 -DbName pos_uniformes_pruebas -DbUser postgres -DbPassword TU_PASSWORD -AdminUser postgres -AdminPassword TU_PASSWORD -InstallBrotherDriver
```

Qué hace este paso:

- crea la base `pos_uniformes_pruebas` si no existe
- restaura el respaldo de prueba incluido en el bundle
- deja `pos_uniformes.env` apuntando a `pos_uniformes_pruebas`
- lanza el instalador del driver Brother

## Paso 4: abrir el sistema

Cuando termine el setup, abrir:

```powershell
.\POSUniformes-2026.03.18.exe
```

## Resultado esperado

La app debe abrir con estas condiciones:

- usa la base `pos_uniformes_pruebas`
- no toca la base real `pos_uniformes`
- conserva el nombre de negocio de pruebas
- la impresión de etiquetas queda lista si el driver Brother termina de instalarse bien

## Qué no hacer

- no ejecutar el bundle apuntando a `pos_uniformes`
- no sobrescribir manualmente la base real
- no copiar solo el `.exe`
- no sacar el contenido de `_internal`, `drivers` o `seed`

## Verificación rápida

Si todo sale bien, al final debe existir:

- `pos_uniformes.env` junto al `.exe`

Y ese archivo debe apuntar a:

```ini
POS_UNIFORMES_DB_NAME=pos_uniformes_pruebas
```

## Si algo falla

Revisar primero:

1. PostgreSQL está instalado y corriendo.
2. La contraseña real de `postgres` es la correcta.
3. El bundle se descomprimió completo.
4. El script se ejecutó dentro de la carpeta del bundle.

## Comando corto recomendado

Si la PC del negocio ya tiene PostgreSQL con credenciales por defecto:

```powershell
cd C:\POSUniformes-Pruebas
.\setup_windows_local_bundle.ps1 -DbName pos_uniformes_pruebas -InstallBrotherDriver
.\POSUniformes-2026.03.18.exe
```
