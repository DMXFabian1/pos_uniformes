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

## Requisito real confirmado

- Para imprimir etiquetas en Windows con la Brother QL-800, hay que instalar el driver oficial de Brother.
- Descarga usada y validada en esta PC:
  - https://support.brother.com/g/b/downloadhowto.aspx?c=mx&lang=es&prod=lpql800eus&os=10069&dlid=dlfp101277_000&flang=201&type3=347
- Sin ese driver, Windows puede no exponer correctamente la impresora real y la app no podra imprimir etiquetas como se espera.

## Estado de esta PC

- Impresora de etiquetas validada: Brother QL-800 con driver oficial instalado.
- `pywin32` instalado en la `.venv`
