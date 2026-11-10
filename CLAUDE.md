# POS Uniformes

Sistema de punto de venta de una tienda de uniformes escolares. Todo en español (código, docs, commits).

## Ramas: dónde está el trabajo de verdad

- El tronco vivo es **`chore/reorganizacion-repo`**, y las ramas de trabajo salen de ahí (por ejemplo `feat/avisos-y-mapa`). **`main` se quedó en julio de 2026**: no partir de `main` ni confiar en sus docs.
- Cada rama tiene su propia carpeta de trabajo (`git worktree list`). No cambiar de rama en una carpeta que tiene trabajo sin commit.
- El repo en GitHub (`DMXFabian1/pos_uniformes`) es **público**: nunca commitear contraseñas, PINs, IPs con credenciales ni `pos_uniformes.env`.

## Qué hay en el repo

| Carpeta | Qué es |
|---|---|
| `pos_uniformes/` | POS principal: PyQt6 + SQLAlchemy 2 + PostgreSQL + Alembic. Incluye la API FastAPI (`api/`), el kiosko o satélite (`presupuestos_satelite_main.py`), la Libreta móvil estática servida en `/app` (`pwa/`), el conteo de afluencia por cámaras (`afluencia/`) y `reportes/`. |
| `pwa/` | App móvil React 18 + Vite + Tailwind (en pausa). |
| `Gestor_de_Inventarios/` | App vieja (customtkinter + SQLite `data/productos.db`). Viven aquí las reglas de precios, las guías y los generadores de tarifarios. |
| `mapa_tienda/`, `mapas_escuelas/` | Mapas HTML y JS de la tienda y de las escuelas. |
| `_archivo/` | Lo que salió de la raíz en agosto de 2026. No se usa (ver su README). |
| `cien_mexicanos/`, `libro_mayor/` | Otros proyectos. Ignorar salvo que se pida. |

## Comandos

Python 3.12. Cada carpeta de trabajo usa su `pos_uniformes/.venv`. Si no existe, se puede usar el de otra carpeta, por ejemplo `../pos_uniformes-avisos-mapa/pos_uniformes/.venv/bin/python3`, que ya trae pytest y xdist.

```bash
# Pruebas: SIEMPRE desde pos_uniformes/ (pytest.ini vive ahí; desde la raíz falla
# la colección de test_pruebas_no_tocan_datos_reales.py por `from tests.conftest`)
cd pos_uniformes
"$PY" -m pytest tests/test_lo_que_toque.py -q      # mientras se trabaja
"$PY" -m pytest tests --fast -q                    # lo puro: ~1250 pruebas en ~6 s
"$PY" -m pytest tests -n 6 --dist load -q          # todo (ver aviso abajo)
# Smoke de arranque
"$PY" scripts/check_startup_health.py
# API + PWA (desde la raíz)
./dev.sh
```

**Aviso (2026-11-10):** la suite completa con `-n 6` no termina en la Mac. Algunos procesos se caen con `Fatal Python error: Aborted` en `conftest.pytest_sessionfinish` → `quote_satellite_window._advertir_impresora_tickets_sin_elegir`. Hasta que se arregle, usar `--fast` más las pruebas del archivo tocado, y avisar a Daniel que la suite completa no corrió.

Para ahorrar tokens, mandar la salida a un archivo y mostrar solo el resumen y los nombres de las pruebas que fallan.
Migraciones: Alembic en `pos_uniformes/migrations/versions/`. Se corren con `python -m alembic upgrade head` desde `pos_uniformes/`.

## ⚠️ Base de datos de producción

- La caja (PostgreSQL de la PC de la tienda) es `server_db_host()` en `utils/config.py`. `main.py` **se conecta sola a producción** si la encuentra en la LAN y no hay `POS_UNIFORMES_DB_HOST` definido. Los generadores `*_db.py` de tarifarios también leen de ahí.
- **Nunca escribir en la caja ni correr migraciones contra ella sin confirmar antes con Daniel**, mostrando primero un dry-run o el resumen de cambios. Leer sí está permitido.
- En esta Mac, la configuración del proyecto apunta a la base **local** (que puede estar atrasada en migraciones). La conexión a la caja vive en `/Users/danielfabian/Documents/Playground 2/pos_uniformes/pos_uniformes.env`: pasarla con `--env-file` a los scripts de las skills, o con `set -a; . <ese env>; set +a` en la shell. No copiar sus valores a ningún archivo del repo.

## Reglas de arquitectura (de `pos_uniformes/docs/protocolo_cambios.md`)

- `ui/main_window.py` es el coordinador y el archivo más delicado. **No agregarle lógica nueva**: va en `services/` (servicio puro y probado) o en un dialog, vista o helper propio, y `main_window.py` solo conecta. No leerlo completo: buscar el método y leer solo ese rango.
- Una regla de negocio nueva lleva su prueba en `pos_uniformes/tests/test_<servicio>.py`.
- No mezclar refactor con comportamiento nuevo ni tocar dos dominios a la vez.

## Documentación: el vault de Obsidian manda

- La documentación viva está en el vault `~/Documents/Obsidian Vault/` (carpetas `POS Uniformes/`, `Gestor de Precios/`, `PWA Móvil/`, `Mapa Tienda/`). La entrada es `POS Uniformes/00 - Índice General.md`, y la nota de la sesión actual es `21 - Sesión de Trabajo.md`.
- `pos_uniformes/docs/obsidian/` es una copia vieja (4-oct-2026): **no editarla ni usarla como fuente**.
- Varios archivos de `pos_uniformes/docs/*.md` (arquitectura, diagrama de base de datos, mapa de módulos, planes y checklists de marzo a julio) están desactualizados. Ante una contradicción, ganan el código y el vault.
- Las notas del vault usan wikilinks `[[Nota]]` y tienen nombres únicos. Para revisarlo, usar la skill `obsidian-notes`.

## Precios: la fuente de verdad es la caja

- Los precios válidos son los del PostgreSQL de la caja. `productos.db` y los documentos se ajustan a ella, nunca al revés.
- Regla de oro: **nunca bajar precios** (`precio_nuevo = MAX(actual, objetivo)`), salvo que Daniel lo pida explícitamente.
- En la caja, los cambios se aplican con `CatalogService.aplicar_cambio_masivo_precio`, que deja bitácora en `cambio_catalogo`.
- Usar la skill `cambio-precios-catalogo`.

## Commits

Prefijo de dominio en español y fecha cuando aplica: `precios: …`, `escuelas: …`, `docs: …`, `feat(satélite): …`, `fix(backup): …`, `chore: …`.

## Build Windows

La versión visible sale de `pos_uniformes/VERSION`. El CI (`.github/workflows/windows-build.yml`) solo corre en pushes a `main` y `codex/etiquetas-windows`, así que el tronco vivo no tiene CI.
