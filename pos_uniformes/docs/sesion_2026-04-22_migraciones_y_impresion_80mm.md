# Sesión 2026-04-22 — Migraciones pendientes + impresión ticket 80mm

Rama: `claude/review-pos-uniforme-hr1JL`
Commits relevantes: `1ce745e`, `b7208cd`, `375ce7b`, `8113ce3`, `8cfe9bd`, `1a2be9c`, `8f6ec1b`, `52178ae`

---

## 1. Problema: base de datos desactualizada al hacer pull en Windows

Al hacer `git pull` en Windows, el programa abrió con el error:

```
La base de datos esta desactualizada para esta version del programa.
Version actual: f0a1b2c3d4e5
Version esperada: a1b2c3d4e5f6, a3c7e9f1b204
```

### Causa

Dos migraciones nuevas agregadas en la sesión anterior partían del mismo padre (`f0a1b2c3d4e5`), creando dos heads en Alembic:

- `a1b2c3d4e5f6` — agrega `ultimo_conteo_at` y `stock_minimo` a la tabla `variante`
- `a3c7e9f1b204` — agrega `seller_employee_id` a `venta`, `presupuesto` y `apartado`

### Fix aplicado

**`migrations/versions/a3c7e9f1b204_add_seller_employee_id.py`**

`add_column` con `index=True` ya crea el índice automáticamente. El `create_index` explícito después fallaba con `DuplicateTable`. Se agregó `if_not_exists=True` a los tres `op.create_index`:

```python
op.create_index("ix_venta_seller_employee_id", "venta", ["seller_employee_id"], if_not_exists=True)
op.create_index("ix_presupuesto_seller_employee_id", "presupuesto", ["seller_employee_id"], if_not_exists=True)
op.create_index("ix_apartado_seller_employee_id", "apartado", ["seller_employee_id"], if_not_exists=True)
```

### Comando correcto para aplicar migraciones con múltiples heads

```powershell
python -m alembic upgrade heads   # plural, no head
```

---

## 2. Problema: ticket de presupuesto imprime mal en EC-PM-80320 (80mm)

La impresora EC Line EC-PM-80320 es de 80mm. El ticket salía con el texto ocupando solo una franja angosta del papel.

### Causa raíz

El código original estaba configurado para papel de **58mm**. Al imprimir en 80mm pasaban dos cosas:

1. `QTextDocument.setTextWidth()` usa coordenadas de pantalla (96 DPI), no las de la impresora (203 DPI). Esto causaba un desfase de unidades que hacía que el texto se imprimiera muy angosto.
2. `QPrintDialog` sobrescribía cualquier `setPageSize` configurado antes de abrirlo, restaurando el tamaño de página del driver.
3. `printer.pageLayout().paintRect(mm)` devolvía ~29mm en lugar de ~76mm porque el driver de la EC-PM-80320 reporta un tamaño de página incorrecto a Qt.

### Iteraciones de fix

| Intento | Qué se probó | Resultado |
|---------|-------------|-----------|
| 1 | `TICKET_PAPER_WIDTH_MM = 80`, separadores 48 chars | Mejoró pero wrapping incorrecto |
| 2 | `paintRect()` dinámico post-dialog | Driver reportaba ~29mm → seguía estrecho |
| 3 | Sin `QPrintDialog`, `setPageSize(80×600)` + `setFullPage(True)` antes de imprimir | Márgenes amplios (dialog había sobrescrito page size) |
| 4 | `setPageSize` + `setFullPage(True)` **después** de confirmar el dialog | Mejoró, pero márgenes amplios a ambos lados |
| 5 | `QPainter.drawText()` con `painter.viewport()` | ✅ Funciona correctamente |

### Fix final

**`ui/dialogs/printable_text_dialog.py`** — sustituir `QTextDocument.print(printer)` por `QPainter.drawText()`:

```python
printer = QPrinter(QPrinter.PrinterMode.HighResolution)
printer.setPrinterName(preferred_printer)
printer.setCopyCount(copies)
printer.setPageSize(QPageSize(QSizeF(TICKET_PAPER_WIDTH_MM, 600.0), QPageSize.Unit.Millimeter))
printer.setFullPage(True)

painter = QPainter(printer)
font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
font.setPointSize(TICKET_FONT_POINT_SIZE)
painter.setFont(font)

rect = painter.viewport()   # rect real del driver en sus coordenadas nativas
painter.drawText(
    rect,
    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
    content,
)
painter.end()
```

**Por qué funciona**: `painter.viewport()` devuelve el rectángulo imprimible en las coordenadas nativas del driver de la impresora. Al dibujar en ese rect directamente, el word-wrap ocurre al ancho físico real del papel, sin pasar por ninguna conversión de unidades de pantalla.

**`ui/helpers/ticket_print_layout_helper.py`** — ancho actualizado a 80mm:

```python
TICKET_PAPER_WIDTH_MM = 80.0
TICKET_TEXT_WIDTH_MM = 76.0   # 80 - 2*2mm márgenes
```

**`services/quote_text_service.py`** — separadores ajustados a 42 chars (conservador para ~44 chars que caben en 76mm a 8pt):

```python
QUOTE_TERMS_WRAP_WIDTH = 42
"=" * 42   # antes 40 (58mm) → 48 (primer intento 80mm) → 42 (final)
"-" * 42
```

### Comportamiento final

- Click en "Imprimir" → imprime directo, sin diálogo Win32 intermedio
- Impresora usada: la configurada en `impresora_preferida` de ajustes del negocio
- Texto ocupa el ancho completo del papel de 80mm
- Separadores y términos se ajustan correctamente

---

## 3. Archivos modificados en esta sesión

| Archivo | Cambio |
|---------|--------|
| `migrations/versions/a3c7e9f1b204_add_seller_employee_id.py` | `if_not_exists=True` en los 3 `create_index` |
| `ui/helpers/ticket_print_layout_helper.py` | `TICKET_PAPER_WIDTH_MM` 58→80, docstring, param `text_width_mm` en `build_ticket_document` |
| `ui/dialogs/printable_text_dialog.py` | `QPainter.drawText` en lugar de `QTextDocument.print`, sin `QPrintDialog`, `setFullPage(True)` |
| `services/quote_text_service.py` | Separadores 40→42, `QUOTE_TERMS_WRAP_WIDTH` 38→42 |

---

## 4. Pendientes / notas para continuar

- Los cambios están en `claude/review-pos-uniforme-hr1JL`, aún **no mergeados a `main`**. Hacer merge antes de la próxima release.
- La migración de merge de los dos heads (`a1b2c3d4e5f6` y `a3c7e9f1b204`) quedó pendiente de crear para que `alembic upgrade head` (singular) vuelva a funcionar sin errores.
- El ajuste de impresión (80mm, `QPainter`) afecta **todos** los tickets que usen `open_printable_text_dialog`, incluyendo ventas. Verificar que el ticket de venta también salga bien en la EC-PM-80320.
