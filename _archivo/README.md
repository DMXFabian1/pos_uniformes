# _archivo

Cosas que salieron de la raíz del repo en la reorganización de agosto 2026.
Nada de aquí se usa en producción; se conserva por si acaso.

| Qué | Por qué está aquí |
|---|---|
| `actualizar_precios_windows.py`, `reglas_precios_v1.md` | Duplicados idénticos de los que viven en `Gestor_de_Inventarios/` (esos son los buenos) |
| `revisar_precios_postgres.py`, `sincronizar_precios_postgres.py` | Scripts de precios huérfanos; nadie los importa. Si se reusan, correr desde `Gestor_de_Inventarios/` porque referencian `reglas_precios_v1.md` |
| `guia_rapida_*_compacta.md` (5) | Duplicados parciales; las 12 guías completas están en `Gestor_de_Inventarios/` |
| `deploy_bodega.ps1` | Script de deploy viejo, sin referencias |
| `pos_uniformes_2026.03.18_source*.zip` | Snapshots de marzo 2026 (ya no se versionan, solo quedan en disco) |
| `checador_precios/` | Esqueleto vacío de un proyecto que no arrancó (jun 2026) |
| `tarifarios/` | Generador viejo Escolta/Maximoda; lo reemplazan los generadores de `Gestor_de_Inventarios/` |
