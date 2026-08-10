# Mi Biblioteca

Tu biblioteca virtual personal, estilo **Bookly pero gratis y tuya**:
catálogo con escáner de ISBN, rastreador de lectura con cronómetro, metas,
rachas y estadísticas. Alojada como web app de Google Apps Script con los
datos en una hoja de cálculo de Google, para uso de una sola persona.

## Qué hace

**Catálogo**
- **Escanear el ISBN** con la cámara. El servidor busca los datos del libro
  (título, autor, portada, año, páginas, categoría) en **Google Books** y,
  si no aparece, en **Open Library**. También puedes buscar por título o
  escribir el ISBN a mano.
- **Dos listas**: *Mi biblioteca* y *Por comprar*. Si escaneas en la
  librería un libro que ya tienes, te avisa al instante; cuando compras uno
  deseado, un toque en ✓ lo pasa a tu biblioteca.
- Búsqueda, filtros por categoría, calificación con estrellas y notas.
- **Rescate de portadas y páginas** para ediciones con ficha pobre (mangas
  en español, por ejemplo): busca en varias fuentes al agregar, y los libros
  ya guardados tienen un botón "Buscar portada y páginas" en su detalle.
- **Comparador de precios** en la lista de compras: consulta Buscalibre
  automáticamente (precio real, marcando la coincidencia exacta de ISBN) y
  abre con un toque la búsqueda en Amazon México, Google Shopping, Gandhi y
  MercadoLibre; el precio elegido se guarda en la lista con ✓.
- **Precio y librería** en la lista de compras (con total anotado), registro
  de **préstamos** ("se lo presté a X el día tal"), y **citas favoritas**
  por libro (tus frases subrayadas, con su página).

**Rastreador de lectura (lo de Bookly)**
- **Cronómetro de sesiones**: toca ▶ en el libro y lee. Se puede pausar, y
  sobrevive aunque cierres la app (aparece un chip flotante para volver).
- Al terminar te pregunta **en qué página vas**: de ahí salen el avance
  (barra y %), tu **velocidad** (pág/h) y el estimado de **cuánto te falta**
  para terminar cada libro.
- **Metas**: minutos de lectura al día y libros al año (se ajustan en ⚙️).
- **Racha** de días leyendo, minutos de hoy en el inicio, y estadísticas:
  gráfica de los últimos 7 días, tiempo total, páginas leídas reales,
  velocidad media, terminados este año contra tu meta, categorías, autores
  y un **resumen del año** (tu mejor mes, tu libro favorito…).
- **Historial de sesiones** por libro con opción de borrar una equivocada
  (p. ej. si el cronómetro quedó corriendo).
- **Memoria local**: la app guarda una copia de tu biblioteca en el
  teléfono; sin señal abre al instante con esa copia (ideal para el
  "¿ya tengo este libro?" dentro de una librería).

## Archivos

| Archivo | Qué es |
|---|---|
| `Code.gs` | Servidor: API, ISBN, metadatos, sesiones, metas y hojas de cálculo |
| `Index.html` | Toda la interfaz (pantallas, escáner, cronómetro, estilos y lógica) |
| `appsscript.json` | Manifiesto del proyecto (opcional) |

## Cómo publicarla (5–10 minutos)

1. **Crea una hoja de cálculo nueva** en [sheets.google.com](https://sheets.google.com)
   (por ejemplo "Mi Biblioteca — datos").
2. En la hoja, abre **Extensiones → Apps Script**.
3. Pega el contenido de **`Code.gs`** en el archivo `Código.gs`.
4. **+ → HTML**, nómbralo exactamente `Index` y pega el contenido de
   **`Index.html`** completo.
5. **Implementar → Nueva implementación → Aplicación web**:
   - *Ejecutar como*: **Yo**
   - *Quién tiene acceso*: **Solo yo** (la app es personal; queda protegida
     con tu cuenta de Google)
   - Autoriza los permisos (hojas de cálculo y servicios externos — esto
     último son las búsquedas en Google Books / Open Library).
6. Copia la **URL `/exec`**: esa es la app. En el teléfono (con tu sesión
   de Google iniciada), ábrela y usa **Añadir a pantalla de inicio**.

Las pestañas `Libros`, `Sesiones` y `Citas` de la hoja se crean solas la primera vez.

> Si con "Solo yo" la app no carga desde el icono de pantalla de inicio
> (pasa en algunos navegadores), cámbiala a "Cualquier usuario": la URL es
> imposible de adivinar y nadie más la conoce.

## Sobre la cámara

Las web apps de Apps Script corren dentro de un marco aislado de Google y
en algunos teléfonos ese marco no permite la cámara en vivo. La app tiene
tres caminos, en este orden:

1. **Cámara en vivo** con detección continua (si el navegador la permite).
2. **Tomar foto**: abre la cámara nativa, tomas una foto del código de
   barras y la app lo lee de la imagen. Funciona prácticamente siempre.
3. **Escribir el ISBN** a mano (valida el dígito de control).

## Si luego cambias el código

**Implementar → Administrar implementaciones → ✏️ → Versión: Nueva →
Implementar** (guardar no basta; hay que crear una versión nueva para que
la misma URL sirva el código actualizado).
