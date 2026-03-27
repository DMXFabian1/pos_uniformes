# Etiquetas Windows

## Checkpoint actual

- La generacion de etiquetas sigue siendo portable desde `utils/label_generator.py`.
- En Windows, la impresion de etiquetas ahora intenta usar el flujo directo que ya funcionaba en el sistema de referencia:
  - `win32print`
  - `win32ui`
  - `PIL.ImageWin`
- No se usa `Microsoft Print to PDF` como salida automatica para etiquetas.
- Si no hay una impresora fisica real disponible, la app muestra error claro en vez de mandar a PDF.
- Fuera de Windows se conserva el fallback con `QPrinter`.

## Referencia usada

- Carpeta: `C:\Users\Daniel\Desktop\pos_uniformes\Solo Referencia`
- Archivo clave revisado: `Gestor_de_Inventarios\src\modules\scanner\scan_and_print.py`

## Pendiente de validacion fisica

- Probar con la impresora real de etiquetas instalada en Windows.
- Confirmar tamano fisico, driver y comportamiento del spooler con la Brother objetivo.

## Estado de esta PC

- Impresora detectada actualmente por Windows: `Microsoft Print to PDF`
- Con el comportamiento actual, eso no cuenta como impresora valida de etiquetas.
- `pywin32` instalado en la `.venv`
