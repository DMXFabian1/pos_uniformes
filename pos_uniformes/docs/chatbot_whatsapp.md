# Chatbot de presupuestos por WhatsApp

Bot que cotiza uniformes por WhatsApp con un flujo **guiado por menús/botones**,
usando la **WhatsApp Cloud API oficial de Meta**. Reutiliza el catálogo y la
lógica de presupuestos del POS: los precios **siempre** salen de la base de
datos (tabla `variante`), nunca se inventan.

## Cómo funciona

El bot acompaña al cliente paso a paso:

1. **Escuela** — lista de escuelas con productos activos (o escribe para filtrar).
2. **Prenda** — familias de producto de esa escuela, con su precio "desde".
3. **Talla / color** — variantes con su precio unitario.
4. **Cantidad** — número de piezas.
5. **Agregar otra / Finalizar** — botones.
6. **Nombre** (opcional).
7. Se crea un **`Presupuesto` en estado `BORRADOR`**, con el teléfono de
   WhatsApp del cliente y `observacion = "Generado por chatbot de WhatsApp"`,
   atribuido a un usuario de servicio (primer CAJERO activo; si no, ADMIN).

Una empleada revisa el borrador en el POS y lo emite/atiende normalmente.
El cliente recibe su **folio** (`PRE-YYYYMMDD-HHMMSS-XXXX`) para mencionarlo en tienda.

## Componentes (código)

| Archivo | Rol |
|---|---|
| `api/routers/whatsapp.py` | Webhook: `GET` verificación + `POST` recepción (procesa en background, responde 200 de inmediato). |
| `api/services/whatsapp_client.py` | Cliente de la Cloud API: envía texto, botones y listas; verifica firma `X-Hub-Signature-256`. |
| `api/services/whatsapp_flow_service.py` | Máquina de estados de la conversación + consultas a BD + creación del presupuesto. |

Los endpoints quedan bajo `/api/v1/whatsapp/webhook`.

## Configuración (variables de entorno)

En `pos_uniformes.env` (ver `pos_uniformes.env.example`):

```
WHATSAPP_TOKEN=            # Token permanente del System User (Meta Business)
WHATSAPP_PHONE_NUMBER_ID=  # Phone Number ID (no el número en sí)
WHATSAPP_VERIFY_TOKEN=     # Cadena secreta que tú eliges (handshake del webhook)
WHATSAPP_APP_SECRET=       # Opcional: App Secret, para validar la firma de cada mensaje
WHATSAPP_API_VERSION=v21.0 # Opcional
```

## Puesta en marcha

### 1. Cuenta de Meta

1. Crea una app de tipo *Business* en <https://developers.facebook.com/> y agrega el producto **WhatsApp**.
2. Obtén el **Phone Number ID** y un **token de acceso permanente** (System User en Meta Business).
3. Define un **Verify token** (cualquier cadena secreta) y cópialo en `WHATSAPP_VERIFY_TOKEN`.
4. Copia el **App Secret** en `WHATSAPP_APP_SECRET` (recomendado para validar firmas).

### 2. Exponer el webhook (LAN → internet)

La API del POS es de **red local**. WhatsApp necesita un webhook público HTTPS.
Opciones:

- **Cloudflare Tunnel / ngrok** apuntando al puerto 8000 (rápido para empezar).
- Un **VPS** con el servicio expuesto y conexión por VPN a la red del negocio.

Registra en Meta como *Callback URL*:

```
https://TU-DOMINIO-PUBLICO/api/v1/whatsapp/webhook
```

y el *Verify token* que pusiste arriba. Suscríbete al campo **`messages`**.

### 3. Reiniciar la API

```
python api_server.py
```

Manda "hola" al número de WhatsApp Business y el bot iniciará el flujo.

## Notas y límites

- **Estado de conversación en memoria.** Para este prototipo el estado vive en
  el proceso (`_SESSIONS` en `whatsapp_flow_service.py`); funciona porque la API
  corre con **un solo worker** de uvicorn. Para escalar a varios workers, mover
  ese estado a **Redis** o a una tabla de la base de datos.
- **Listas de WhatsApp:** máximo 10 filas. Si una escuela/prenda tiene más
  opciones, el bot muestra las primeras y permite **escribir para filtrar**.
- **Ventana de 24 h.** Fuera de la ventana de servicio al cliente, Meta solo
  permite mensajes con *plantillas* aprobadas. El flujo aquí asume que el
  cliente escribe primero (abre la ventana).
- **No usar librerías no oficiales** (whatsapp-web.js / Baileys): violan los
  términos de Meta y arriesgan el baneo del número del negocio.

## Próximos pasos sugeridos

- Adjuntar un **PDF** del presupuesto al cerrar (reusar el generador del POS).
- Vincular el teléfono con un **`Cliente`** existente (campo `Cliente.telefono`).
- Capa de **lenguaje natural** (Claude API) para entender texto libre, validando
  siempre precios y totales contra esta misma lógica.
- Notificar a una empleada cuando entra un borrador nuevo por WhatsApp.
