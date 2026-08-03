# Mapas de escuelas — San Felipe, Gto.

## Mapa principal: `mapa_escuelas_san_felipe.html`

Mapa interactivo (Leaflet + clustering, necesita internet para los tiles) con
**todas las escuelas del mercado**: la cabecera completa (todos los niveles,
incluye CONAFE y particulares) + las comunidades donde hay clientes + los
SABES/telebachilleratos rurales del municipio (~125 escuelas).

- **Color = nivel** (colores del panel): Preescolar `#7c4dff`, Primaria `#2979ff`,
  Secundaria `#00bfa5`, Bachillerato `#ff6d00`, gris = otros (CECATI/CAM).
- **Relleno = cliente** del POS; **anillo hueco** = sin registrar (oportunidad).
- Controles: búsqueda por nombre/comunidad/CCT, chips por nivel, selector
  Todas / Solo clientes / Oportunidades, switch de SABES+telebach rurales,
  Ver pueblo / Ver municipio / Imprimir.
- Lista lateral agrupada por localidad (colapsable) y resumen de cobertura.
- `~` = ubicación probable (nombre repetido en varias comunidades).

### Regenerar

```bash
python3 mapas_escuelas/generar_datos_escuelas.py
```

Descarga el directorio SEP (escuelasmex.com, fichas por CCT) a
`cache_fichas/` (gitignoreado) y genera el HTML desde `plantilla_mapa.html`
con los datos inyectados. Con caché es casi instantáneo; para buscar escuelas
nuevas en el directorio, borrar `cache_fichas/listado_*.html` y volver a correr.

Los clientes se marcan cruzando `pos_uniformes/data/catalog_cache.json` con el
dict `CLIENTES_CCT` del script (desambiguaciones investigadas ago-2026).
Pendientes de ubicar: Jean Piaget (Pre), Vicente Guerrero (Pre+Pri, 3
candidatas), Palacio (Pri) — al saber cuáles son, agregarlas a `CLIENTES_CCT`.

### PNG para compartir

```bash
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" --headless --disable-gpu --hide-scrollbars --window-size=1400,900 --virtual-time-budget=15000 --screenshot=mapas_escuelas/mapa_escuelas_san_felipe.png http://localhost:8933/mapa_escuelas_san_felipe.html
```

(O el botón **Imprimir** dentro del mapa para PDF por el diálogo del navegador.)

## Mapa secundario: `mapa_preescolares_san_felipe.html`

Versión anterior solo-preescolares (clientes vs no clientes). Se conserva como
referencia; el principal la reemplaza.

**Servir local:** entrada `mapas-escuelas` de `.claude/launch.json` (puerto 8933), o:

```bash
python3 -m http.server 8933 -d mapas_escuelas
```
