# Libro Mayor

Registro compartido de préstamos y pagos entre dos personas, alojado como
web app de Google Apps Script con los datos en una hoja de cálculo de Google.

Cada movimiento que registra una persona queda **Pendiente** hasta que la otra
lo **aprueba** o **rechaza**. Solo lo confirmado cuenta para el saldo, que
indica quién le debe a quién. Los movimientos nunca se editan ni se borran:
un error se corrige con un movimiento de **Ajuste**.

## Archivos

| Archivo | Qué es |
|---|---|
| `Code.gs` | Servidor: API, validaciones y almacenamiento en la hoja de cálculo |
| `Index.html` | Toda la interfaz (pantallas, estilos y lógica del cliente) |
| `appsscript.json` | Manifiesto del proyecto (opcional, ver paso 6) |

## Cómo publicarla (5–10 minutos)

1. **Crea una hoja de cálculo nueva** en [sheets.google.com](https://sheets.google.com)
   (por ejemplo llámala "Libro Mayor — datos"). Ahí vivirán los movimientos.

2. En la hoja, abre **Extensiones → Apps Script**. Se abre el editor con un
   archivo `Código.gs` vacío.

3. **Pega el contenido de `Code.gs`** en ese archivo (borra lo que tenga).

4. Crea el archivo de la interfaz: en el editor, **+ → HTML**, nómbralo
   exactamente `Index`, y pega dentro el contenido de `Index.html` completo
   (reemplaza la plantilla que trae).

5. *(Opcional)* Si la app es para otras personas o quieres otro título,
   edita el bloque `CONFIG` al inicio de `Code.gs` — nombres, colores y
   título salen todos de ahí. No hay que tocar nada más.

6. *(Opcional)* En **Configuración del proyecto** (engrane) activa
   "Mostrar el archivo de manifiesto appsscript.json" y pega el contenido de
   `appsscript.json`. Esto deja fijados la zona horaria y el acceso.

7. **Publica**: botón **Implementar → Nueva implementación → Aplicación web**:
   - *Ejecutar como*: **Yo**
   - *Quién tiene acceso*: **Cualquier usuario** (así funciona sin iniciar
     sesión, igual que la original)
   - Autoriza los permisos cuando lo pida.

8. Copia la **URL** que termina en `/exec` — esa es la app. Ábrela en el
   teléfono y usa **Añadir a pantalla de inicio** para instalarla con icono
   propio, como la original.

La primera vez que alguien la abra, el servidor crea solo la pestaña
`Movimientos` con sus encabezados; no hay que preparar nada en la hoja.

## Si luego cambias el código

Para que los cambios lleguen a la URL publicada: **Implementar →
Administrar implementaciones → ✏️ → Versión: Nueva → Implementar**.
(Guardar el código no basta; hay que crear una versión nueva de la
implementación existente para conservar la misma URL.)
