---
name: actualizar-vault
description: Mantener al día el vault de Obsidian del POS (~/Documents/Obsidian Vault) después de un cambio de código, de precios o de una sesión de trabajo — qué nota tocar, cómo anotar, revisar enlaces con obsidian-notes y no filtrar secretos al repo público. Usar al cerrar una tarea, cuando Daniel diga "documenta esto", "actualiza Obsidian" o "revisa el vault".
---

# Actualizar el vault de Obsidian

Vault: `/Users/danielfabian/Documents/Obsidian Vault/`. Si la sesión no tiene acceso, pedir acceso a esa carpeta. El vault es la documentación viva; `pos_uniformes/docs/obsidian/` del repo es una copia vieja que no se toca.

## Qué nota tocar

| Cambio | Nota |
|---|---|
| Cualquier sesión de trabajo | `POS Uniformes/21 - Sesión de Trabajo.md`: estado actual y pendientes |
| Servicio o flujo (ventas, apartados, caja, Libreta, nómina, Telegram, satélite, conteos, buzón…) | La nota numerada del dominio; buscarla en `POS Uniformes/00 - Índice General.md` |
| Tablas o migraciones nuevas | `POS Uniformes/02 - Base de Datos.md`, más las migraciones pendientes de aplicar en la tienda |
| Precios o escuelas | `Gestor de Precios/02 - Historial de Sesiones de Precios.md` y, si cambia una regla, `01 - Reglas de Precios.md` |
| IPs, rutas, PINs, comandos | `POS Uniformes/22 - Referencia Rápida.md` (solo en el vault, nunca en el repo) |
| Deuda o pendiente nuevo | `POS Uniformes/19 - Deuda Técnica.md` |
| Tema nuevo sin nota | Nota nueva `NN - Título.md` (siguiente número libre), enlazada desde `00 - Índice General` |

## Cómo escribir

- Editar la sección vigente: **reemplazar** lo que quedó viejo en vez de solo agregar abajo. Las notas largas (`21 - Historial de Sesiones` supera las 1800 líneas) no deben crecer más. Si `21 - Sesión de Trabajo` se llena, mover lo cerrado a `21 - Historial de Sesiones`.
- Fechar las afirmaciones que envejecen ("(2026-11-10)") y citar el commit corto cuando lo haya.
- Enlazar con wikilinks usando el nombre completo de la nota, por ejemplo `[[22 - Referencia Rápida#Rutas en producción]]`; los nombres son únicos. Cerrar las notas nuevas con una línea `Related:`.
- Si el código contradice una nota, corregir la nota y decirlo.
- **Nunca** copiar contenido del vault al repo: el repo en GitHub es público y el vault tiene contraseñas y PINs.

## Revisar

Al terminar, cargar la skill `obsidian-notes` y correr su revisión sobre el vault. Reportar el antes y el después. Errores esperados: 0. El aviso de "carpetas sin índice" es falso para las carpetas que tienen `00 - Índice …`.

Mostrar a Daniel un resumen de qué notas se cambiaron y en qué. Para borrar o archivar notas, preguntar antes.
