# Mapas de escuelas — San Felipe, Gto.

Mapas interactivos (Leaflet + OpenStreetMap, necesitan internet para los tiles).

- `mapa_escuelas_san_felipe.html` — las 47 escuelas registradas en el POS, coloreadas por nivel
  (colores del panel: Preescolar `#7c4dff`, Primaria `#2979ff`, Secundaria `#00bfa5`, Bachillerato `#ff6d00`).
  En gris: escuelas de la cabecera que no están en la base. `~` = ubicación probable.
- `mapa_preescolares_san_felipe.html` — solo preescolares (clientes vs. no clientes).
- Los `.png` son capturas de la vista del pueblo.

**Ver:** doble clic en el HTML (Brave), o servir la carpeta:

```bash
python3 -m http.server 8933 -d mapas_escuelas
```

**Fuente de ubicaciones:** fichas por CCT de escuelasmex.com (directorio SEP), ago 2026.
Sin ubicar: Jean Piaget (Pre), Vicente Guerrero (Pre+Pri, 3 candidatas), Palacio (Pri).
Los datos de escuelas/niveles salieron de `pos_uniformes/data/catalog_cache.json`.
