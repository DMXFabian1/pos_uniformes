# POS Uniformes

Repositorio principal del POS en Python con soporte de trabajo diario desde macOS y validacion final en Windows.

## Objetivo de portabilidad

La forma recomendada de trabajar es:

- Mac para desarrollo diario
- Windows para validacion final y build del `.exe`
- mismo codigo fuente en ambas maquinas via `git`
- configuracion local fuera del repo usando `pos_uniformes.env`

El ejecutable de Windows se genera en Windows. El codigo fuente y el flujo de pruebas si pueden vivir sin problema en ambas PCs.

## Flujo recomendado Mac + Windows

1. Programa y prueba cambios en tu Mac.
2. Sube el codigo a un remoto privado con `git push`.
3. En Windows haz `git pull`.
4. Corre migraciones si hubo cambios de base:

```bash
python -m alembic upgrade head
```

5. Valida la app en Windows:

```bash
python -m pos_uniformes.main
```

6. Cuando todo este bien, genera la build final en Windows:

```powershell
scripts\build_windows_bundle.ps1
```

## Setup rapido de desarrollo

Desde la raiz del proyecto, en cualquiera de las dos maquinas:

```bash
python scripts/setup_dev_env.py
```

Ese script:

- crea `.venv` si no existe
- instala dependencias de runtime y build
- crea `pos_uniformes.env` local si aun no existe
- te deja los siguientes comandos para migrar y arrancar

Tambien puedes verlo sin ejecutar cambios:

```bash
python scripts/setup_dev_env.py --dry-run
```

## Configuracion local

El archivo local de cada maquina debe ser `pos_uniformes.env`.

- no se comparte entre maquinas
- no se sube al repo
- puede apuntar a bases distintas o a la misma base PostgreSQL

Usa como base:

- [pos_uniformes.env.example](./pos_uniformes.env.example)

## Git entre ambas PCs

Si todavia no tienes remoto, crea uno privado en GitHub, GitLab o Bitbucket y luego configuralo una sola vez:

```bash
git remote add origin <tu-remoto-privado>
git branch -M main
git push -u origin main
```

Despues el flujo diario queda asi:

En Mac:

```bash
git checkout -b tu-rama
git add .
git commit -m "mensaje"
git push -u origin tu-rama
```

En Windows:

```bash
git fetch
git pull
```

Si quieres un comando unico para recibir cambios sin pisar trabajo local por accidente:

```bash
python scripts/receive_updates.py
```

Para recibir una rama especifica, por ejemplo `codex/etiquetas-windows`:

```bash
python scripts/receive_updates.py --branch codex/etiquetas-windows
```

## Notas importantes

- `.venv` no se copia entre sistemas operativos; cada maquina crea la suya.
- `pos_uniformes.env` tampoco se comparte; cada maquina usa su propia configuracion.
- Si la app marca que la base esta desactualizada, corre `python -m alembic upgrade head`.
- Si quieres empaquetar para Windows, usa la guia detallada de [WINDOWS_SETUP.md](./WINDOWS_SETUP.md).
