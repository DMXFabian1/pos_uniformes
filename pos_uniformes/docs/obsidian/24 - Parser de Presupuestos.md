---
tags: [feature, pos-uniformes, parser, presupuestos]
---

# Parser de Presupuestos — Lenguaje Natural

> Genera presupuestos a partir de texto libre, sin LLM, 100% offline.

## Ubicación

`scripts/presupuesto_parser.py` — CLI interactivo standalone.

## Cómo funciona

```
>>> oficial completo niña margarita paz talla 8
```

1. **Detecta tipo**: "oficial" / "deportivo" / "completo" (ambos)
2. **Detecta género**: "niña" → Mujer, "niño" → Hombre
3. **Fuzzy match escuela**: aliases + SequenceMatcher
4. **Extrae tallas**: regex "talla(s) X, Y, Z"
5. **Query DB**: CTE productos directos + ligados, filtrado por género/tipo/talla
6. **Post-filtro**: escuelas con olan excluyen manga corta para niñas
7. **Formato ticket**: estilo MAXIMODA listo para imprimir

## Reglas de negocio

| Solicitud | Resultado |
|-----------|-----------|
| "deportivo completo" | Solo Pants 3pz |
| "oficial completo niña" | Piezas oficiales con genero IN (Mujer, Unisex) |
| "oficial completo niño" | Piezas oficiales con genero IN (Hombre, Unisex) |
| "completo" (sin tipo) | Pants 3pz + todo el oficial |
| Escuela con olan + niña | Olan sí, manga corta no |
| Escuela con olan + niño | Manga corta sí, olan no (filtro género) |
| Escuela sin olan | Manga corta para ambos (Unisex) |
| Piezas específicas | "suéter y pantalón" → solo esas piezas |

## Campos DB que usa

| Campo | Tabla | Propósito |
|-------|-------|-----------|
| `genero` | `producto` | Filtrar Hombre/Mujer/Unisex |
| `tipo_uniforme` | `tipo_pieza` | Filtrar oficial/deportivo |
| `catalog_school_product_link` | — | Productos básicos ligados a escuelas |

## Pendientes

### Prioridad alta

- [ ] **Ligar manga corta a primarias restantes** — 24 primarias sin link (Emiliano Zapata, Albino García, Benito Juárez, Club Rotario, etc.)
- [ ] **Ligar suéteres faltantes** — muchas escuelas no tienen suéter ligado, no aparece en presupuesto completo
- [ ] **Aplicar cambios DB en Windows** — `tipo_pieza.tipo_uniforme`, `producto.genero`, links nuevos
- [ ] **Integrar a app satélite** — campo de texto en la UI de presupuestos que use el parser
- [ ] **Imprimir directo** — conectar salida del parser con `_build_cart_ticket_text()` o `open_printable_text_dialog()`

### Prioridad media

- [ ] **Múltiples tallas en un presupuesto** — "2 niñas talla 8 y 10" → subtotales por talla + total
- [ ] **Múltiples géneros** — "1 niño talla 10 y 1 niña talla 8" → presupuesto combinado
- [ ] **Chaleco, corbatín, moño** — verificar que escuelas que los usan los tengan ligados
- [ ] **Validar cobertura** — avisar si la escuela no tiene todas las piezas esperadas
- [ ] **Sugerir piezas faltantes** — "Frida Kahlo no tiene falda registrada, ¿la incluyo?"

### Prioridad baja

- [ ] **WhatsApp** — enviar presupuesto como imagen/PDF por WhatsApp
- [ ] **Historial** — guardar presupuestos generados para referencia
- [ ] **Descuentos/promos** — aplicar promo 3pz si aplica
- [ ] **Modo conversacional** — "y si le agrego el chaleco?" sin repetir todo

## Ejemplo de salida

```
              MAXIMODA
        Presupuesto Estimado
——————————————————————————————————————————
       ESTE NO ES UN COMPROBANTE
          FISCAL NI DE COMPRA
       Precios solo de referencia
——————————————————————————————————————————
Escuela:             Margarita Paz Paredes
Uniforme:                         Completo
Género:                               Niña
Talla(s):                                8
——————————————————————————————————————————
PIEZAS
——————————————————————————————————————————

  Pants 3pz Margarita Paz Paredes
    Pants 3pz | 8                     $515

  Camisa Cuello olan Azul
    Camisa | 8                        $139

  Falda Escoces Margarita Paz Paredes
    Falda | 8                         $239

  Suéter Botones Margarita Paz Paredes
    Suéter | 8                        $315
——————————————————————————————————————————
PRESUPUESTO ESTIMADO:               $1,208
——————————————————————————————————————————
```

## Dependencias

- `psycopg2` (ya en el proyecto)
- `difflib.SequenceMatcher` (stdlib)
- Sin LLM, sin internet, sin costo

---

> Creado: 2026-05-25 | Commit: `722b8e1`
