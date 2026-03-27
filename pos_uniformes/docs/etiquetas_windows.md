# Etiquetas Windows

## Checkpoint actual

- La generacion de etiquetas sigue siendo portable desde `utils/label_generator.py`.
- En Windows, la impresion de etiquetas ahora intenta usar el flujo directo que ya funcionaba en el sistema de referencia:
  - `win32print`
  - `win32ui`
  - `PIL.ImageWin`
- Si la impresora preferida no esta disponible, se usa la predeterminada de Windows o la primera disponible.
- Fuera de Windows se conserva el fallback con `QPrinter`.

## Referencia usada

- Carpeta: `C:\Users\Daniel\Desktop\pos_uniformes\Solo Referencia`
- Archivo clave revisado: `Gestor_de_Inventarios\src\modules\scanner\scan_and_print.py`

## Pendiente de validacion fisica

- Probar con la impresora real de etiquetas instalada en Windows.
- Confirmar tamano fisico, driver y comportamiento del spooler con la Brother objetivo.

## Estado de esta PC

- Impresora detectada actualmente por Windows: `Microsoft Print to PDF`
- `pywin32` instalado en la `.venv`
