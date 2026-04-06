# Sincronizacion simple Mac / Windows

Programa minimo para marcar un checkpoint desde Windows o Mac y subirlo a GitHub.

## Que hace

- muestra dos botones
- `Commit en Windows`
- `Commit en Mac`
- muestra la rama actual para confirmar donde va el push
- abajo muestra la ultima fecha registrada para cada lado
- al hacer clic:
  - actualiza `docs/sync_checkpoint_status.json`
  - filtra basura generada como `__pycache__`, `.pyc`, `generated`, `dist`, `build` y respaldos
  - hace `git add` solo de cambios utiles
  - hace `git commit`
  - hace `git push`

## Como abrirlo en Windows

```powershell
cd C:\dev\pos_uniformes\pos_uniformes
.venv\Scripts\python.exe scripts\sync_checkpoint_gui.py
```

O mas simple:

```powershell
cd C:\dev\pos_uniformes\pos_uniformes
.venv\Scripts\python.exe main_sync.py
```

## Como abrirlo en Mac

```bash
cd /ruta/a/pos_uniformes
python3 scripts/sync_checkpoint_gui.py
```

O mas simple:

```bash
cd /ruta/a/pos_uniformes
python3 main_sync.py
```

## Archivo compartido de estado

- `docs/sync_checkpoint_status.json`

Ese archivo viaja por GitHub, asi que ambos equipos ven la misma fecha al hacer `pull`.

## Nota importante

Este programa no usa `git add -A` a ciegas. La ventana tambien deja visible la rama actual para reducir errores al sincronizar, y sigue dejando fuera archivos generados tipicos.
