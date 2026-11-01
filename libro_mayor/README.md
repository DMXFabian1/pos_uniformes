# Libro Mayor — interfaz adaptada a la versión en producción

Registro compartido de préstamos y pagos entre Daniel y Coraima, como web
app de Google Apps Script con los datos en una hoja de cálculo.

**Este repositorio contiene solo `Index.html`**: la interfaz, adaptada
sobre el código real de la app desplegada (tipos "envió/recibió dinero",
asistente por pasos, corrección y cancelación). El servidor (`Código.gs`)
vive únicamente en el proyecto de Apps Script en producción y **no debe
reemplazarse**: la interfaz usa su API tal cual
(`api_getEstado`, `api_registrarMovimiento`, `api_aprobarMovimiento`,
`api_rechazarMovimiento`, `api_corregirMovimiento`, `api_cancelarMovimiento`).

> Una reconstrucción antigua con otros nombres de tipos vivió aquí antes
> (`Code.gs` de "prestó dinero / recibió un pago"). Se eliminó porque era
> incompatible con los datos reales; está en el historial de git si se
> necesitara como referencia.

## Mejoras de esta interfaz sobre la desplegada

1. **Saldo a prueba de todo**: el saldo y el saldo acumulado por fila se
   recalculan en el cliente solo con confirmados (el `saldoDespues` del
   servidor venía con la convención invertida). Bajo el saldo de Inicio
   aparece "+$X por aprobar" cuando hay pendientes.
2. **Una sola convención de signo**, siempre desde el usuario activo:
   "A tu favor" / "Le debes a X" en Inicio, y en el historial cada fila
   dice "A tu favor $X" (verde) o "Debes $X" (rojo) en lugar de signos.
3. **Captura rápida**: teclado físico en el asistente (dígitos, punto y
   Backspace en el monto; Enter avanza y registra al final), botón
   "Registrar y agregar otro" que conserva tipo/método/fecha y reabre
   directo en el monto, y el pendiente aparece al instante en la lista
   mientras el servidor responde (si falla, se quita y muestra el error real).
4. **Editar pendientes propios**: botón "Editar" en el detalle (junto a
   "Cancelar"); por dentro cancela el anterior y registra el sustituto,
   usando solo la API existente del servidor.
5. **Badge con el total de pendientes** (rojo si te tocan a ti, gris si
   esperan a la otra persona) y **chips con los últimos 6 conceptos**
   usados por el usuario activo.

Sin cambios en el flujo de aprobación ni en el diseño visual.

## Cómo publicar la actualización

1. Abrir el proyecto de Apps Script de la app (desde la hoja de cálculo:
   Extensiones → Apps Script).
2. Abrir el archivo HTML de la interfaz (`Index`) y reemplazar TODO su
   contenido por el de este `Index.html`. **No tocar `Código.gs`.**
3. **Implementar → Administrar implementaciones → ✏️ → Versión: Nueva →
   Implementar** (guardar no basta: sin versión nueva, la URL sigue
   sirviendo la interfaz anterior).

## Pendiente conocido

La **moneda original** (guardar "COP 212,511" junto al monto en MXN)
requiere columnas nuevas y cambios en `Código.gs`; queda fuera de esta
adaptación de solo-interfaz.
