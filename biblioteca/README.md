# Mi Biblioteca

Tu biblioteca virtual: catálogo personal de libros con escáner de ISBN,
alojado como web app de Google Apps Script con los datos en una hoja de
cálculo de Google (igual que el Libro Mayor).

## Qué hace

- **Escanear el ISBN** con la cámara del teléfono. El servidor busca los
  datos del libro (título, autor, portada, año, páginas, categoría) en
  **Google Books** y, si no aparece, en **Open Library**. También puedes
  buscar por título o escribir el ISBN a mano.
- **Dos listas**: *Mi biblioteca* (los que tienes) y *Por comprar* (los que
  quieres). Si escaneas en la librería un libro que ya tienes, te avisa al
  instante — y cuando compras uno deseado, un toque en ✓ lo pasa a tu
  biblioteca.
- **Organización**: búsqueda por título/autor/ISBN, filtros por categoría,
  estado de lectura (pendiente / leyendo / leído), calificación con
  estrellas y notas libres (dónde está, quién te lo prestó…).
- **Estadísticas**: totales, leídos, páginas leídas, categorías y autores
  más frecuentes.

## Archivos

| Archivo | Qué es |
|---|---|
| `Code.gs` | Servidor: API, validación de ISBN, búsqueda de metadatos y hoja de cálculo |
| `Index.html` | Toda la interfaz (pantallas, escáner, estilos y lógica del cliente) |
| `appsscript.json` | Manifiesto del proyecto (opcional) |

## Cómo publicarla (5–10 minutos)

1. **Crea una hoja de cálculo nueva** en [sheets.google.com](https://sheets.google.com)
   (por ejemplo "Mi Biblioteca — datos").
2. En la hoja, abre **Extensiones → Apps Script**.
3. Pega el contenido de **`Code.gs`** en el archivo `Código.gs`.
4. **+ → HTML**, nómbralo exactamente `Index` y pega el contenido de
   **`Index.html`** completo.
5. *(Opcional)* Cambia el título en el bloque `CONFIG` de `Code.gs`.
6. **Implementar → Nueva implementación → Aplicación web**:
   - *Ejecutar como*: **Yo**
   - *Quién tiene acceso*: **Cualquier usuario**
   - Autoriza los permisos (pedirá acceso a hojas de cálculo y a servicios
     externos: son las búsquedas en Google Books / Open Library).
7. Copia la **URL `/exec`**: esa es la app. En el teléfono, ábrela y usa
   **Añadir a pantalla de inicio** para instalarla con su icono.

La pestaña `Libros` de la hoja se crea sola la primera vez.

## Sobre la cámara

Las web apps de Apps Script corren dentro de un marco aislado de Google y
en algunos teléfonos/navegadores ese marco **no permite la cámara en vivo**.
La app lo resuelve con tres caminos, en este orden:

1. **Cámara en vivo** con detección continua (si el navegador la permite).
2. **Tomar foto**: abre la cámara nativa del teléfono, tomas una foto del
   código de barras y la app lo lee de la imagen. Funciona prácticamente
   siempre.
3. **Escribir el ISBN** a mano (valida el dígito de control).

Si la cámara en vivo no abre, usa "Tomar foto" — el resultado es el mismo.

## Si luego cambias el código

**Implementar → Administrar implementaciones → ✏️ → Versión: Nueva →
Implementar** (guardar no basta; hay que crear una versión nueva para que
la misma URL sirva el código actualizado).
