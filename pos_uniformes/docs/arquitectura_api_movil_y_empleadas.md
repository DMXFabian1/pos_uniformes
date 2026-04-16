# Arquitectura: API, app movil y modulo de empleadas

## Contexto

Este documento unifica tres iniciativas que convergen en una misma evolucion arquitectonica del sistema:

- llevar la funcion actual del satelite (consulta de catalogo, precios y armado de presupuestos) a dispositivos moviles
- abrir el modulo de empleadas descrito en `docs/empleadas_y_comisiones.md`
- introducir una capa de API REST en la PC principal que sirva a todos los clientes

Hacerlas por separado duplicaria trabajo. La API que necesita el movil es la misma superficie donde debe vivir la identidad `empleada`.

Complementa y no reemplaza:

- `docs/satelite_consulta_y_cache_local.md`
- `docs/empleadas_y_comisiones.md`
- `docs/arquitectura_actual.md`

## Decisiones de producto vigentes

### Alcance del movil

La app movil es la herramienta de trabajo personal de la empleada. Va mas alla del satelite actual: no solo replica la consulta de catalogo y presupuestos, sino que le da a la vendedora acceso rapido a su propia actividad comercial en cualquier momento del dia.

Funciones incluidas:

- consulta rapida de precios (escaneo de codigo de barras o busqueda)
- consulta de catalogo completo
- armado de presupuestos vinculados a cliente
- escaneo de QR de cliente para identificarlo rapidamente
- vista de sus ventas del dia y del periodo atribuidas a ella
- acceso a sus tickets confirmados
- lista de sus borradores de presupuesto activos

No cobra, no descuenta inventario, no corta caja, no sustituye `Caja`.

### Entorno de red

- uso exclusivo dentro de la tienda
- red Wi-Fi local del local comercial
- sin exposicion a internet publico
- mas de 5 dispositivos moviles simultaneos esperados

### Identidad y atribucion

- `usuario` = operador tecnico del sistema (sigue como hoy)
- `empleada` = identidad comercial a quien se acredita venta, presupuesto o atencion
- el login movil se hace con `QR + PIN` de empleada, no con usuario del POS
- el presupuesto nacido en movil trae `seller_employee_id` desde el origen

## Topologia objetivo

```
[5+ moviles PWA]  ──http LAN──┐
[Satelite desktop actual]     ├──> [FastAPI en PC principal] ──> [PostgreSQL]
[Caja / POS principal]   ─────┘
```

- PostgreSQL sigue como fuente de verdad unica en la PC principal
- FastAPI como servicio en la PC principal, escuchando en IP fija de LAN
- la PC principal debe permanecer encendida para operar (limite ya conocido del satelite)

Consecuencia importante:

- los moviles no hablan directo a PostgreSQL
- solo la API habla con la base
- esto deja abierta la puerta a que el satelite desktop tambien migre a la API mas adelante

## Principios arquitectonicos

1. `usuario` y `empleada` no se mezclan. La API expone ambos conceptos separados y los clientes deben respetar la distincion.
2. La fuente de verdad es PostgreSQL en la PC principal. Ningun cliente puede asumir autoridad local.
3. La atribucion comercial viaja con el recurso desde su creacion. Un presupuesto creado en movil no debe requerir reasignacion posterior para tener empleada acreditada.
4. Degradacion explicita. Si el movil pierde red, debe mostrarlo visualmente y no permitir operaciones que parezcan exitosas sin serlo.
5. Nada sensible en modo degradado. No hay cobro, no hay cancelaciones, no hay movimiento de inventario desde movil.
6. La numeracion de recursos concurrentes vive en el servidor. Con 5+ dispositivos no se puede asignar folios desde cliente.
7. La autenticacion del movil no se hereda del POS. Es un flujo propio basado en empleada.

## Modelo de identidad

### Usuario

- acceso tecnico al sistema
- apertura y cierre de caja
- cancelaciones y autorizaciones
- auditoria de acciones sensibles

### Empleada

- ficha comercial: nombre, codigo interno, telefono, rol operativo, estado, QR unico, PIN corto, foto opcional
- identidad reutilizable entre POS, satelite, kiosko y movil
- sujeto de atribucion de venta, presupuesto y atencion

### Impacto en el esquema

- conservar `usuario_id` en `venta`, `presupuesto` y recursos existentes como operador real
- agregar `seller_employee_id` (FK a `empleada`, nullable al principio) en los mismos recursos
- no eliminar ni renombrar columnas actuales para no romper el POS existente

## Autenticacion movil

### Alta de empleadas

La creacion y gestion de empleadas (nombre, codigo `VEND-N`, PIN) se realiza exclusivamente desde el POS principal, por un usuario con rol `ADMIN`. La app movil nunca da de alta empleadas ni reinicia PINs.

Esto ya existe en codigo:

- modelo `Empleada` en `database/models.py`
- `services/employee_identity_service.py` cubre alta, edicion, generacion de codigo `VEND-N`, hash de PIN y resolucion por QR escaneado
- PIN numerico de 4 a 8 digitos, hasheado con el mismo `AuthService` del POS
- solo ADMIN puede crear o modificar empleadas

### Flujo de login en movil

1. la PWA consulta la lista de empleadas activas al servidor y la muestra como listbox con nombres visibles ordenados alfabeticamente
2. la empleada toca su nombre
3. ingresa su PIN en un teclado numerico grande
4. el servidor valida nombre + PIN y emite un token de sesion ligado a `employee_id` y al dispositivo
5. el token tiene vigencia corta y se renueva mientras haya actividad
6. al cerrar turno o cambiar de empleada, la sesion se cierra

El listbox es el metodo principal por UX en dispositivos tactiles y por consistencia con el selector de usuarios ya existente en el login del POS. El QR escaneado queda como metodo alternativo opcional a futuro, no como requisito de la v1.

### Consideraciones

- el token no es permanente por dispositivo, es por sesion de empleada
- un dispositivo puede rotar entre empleadas durante el dia
- acciones sensibles pueden requerir reconfirmacion con PIN aunque haya sesion activa
- el PIN nunca viaja en claro ni se almacena reversible
- registro de intentos fallidos de login por empleada y por dispositivo
- si la empleada esta inactiva en la ficha del POS, no aparece en el listbox y el servidor rechaza el login aunque el PIN coincida

## Superficie de API (primera version)

Catalogo:

- catalogo de productos
- precios vigentes
- busqueda por codigo, descripcion o categoria
- ficha de producto
- consulta rapida de precio por codigo de barras escaneado

Presupuestos:

- crear presupuesto con `seller_employee_id` derivado de la sesion
- agregar y quitar partidas
- editar cantidades
- listar borradores activos de la empleada en sesion
- marcar presupuesto como listo para pasar a caja

Ventas y tickets de la empleada:

- ventas del dia atribuidas a la empleada en sesion (`seller_employee_id`)
- ventas del periodo con filtro de fecha
- detalle de ticket individual
- conteo de ventas, total generado y piezas del dia

Empleadas:

- listado publico de empleadas activas para el listbox de login
- login con empleada seleccionada + PIN
- cierre de sesion
- consulta de ficha propia
- no expone alta, edicion ni reinicio de PIN (eso vive solo en el POS)

Clientes:

- consulta de cliente por QR escaneado con la camara del movil
- no expone alta ni edicion de cliente
- la creacion de cliente nuevo solo ocurre desde POS o kiosko, nunca desde movil

Fuera de alcance de la v1:

- cobro
- cancelaciones
- movimientos de inventario
- comisiones calculadas (se pueden ver ventas brutas, no liquidaciones)
- analitica comparativa entre empleadas

## Concurrencia con 5+ dispositivos

Ajustes obligatorios:

- numeracion de presupuestos por secuencia en PostgreSQL, no client-side
- pool de conexiones de SQLAlchemy dimensionado para moviles + satelite desktop + caja
- pruebas de carga minimas antes de liberar: varias sesiones simultaneas creando y editando presupuestos

### Propiedad del borrador de presupuesto

Regla vigente: un borrador de presupuesto creado desde movil queda ligado a la empleada que lo creo. Solo esa empleada puede editarlo desde movil.

Consecuencias:

- no hay edicion concurrente posible entre dos empleadas sobre el mismo borrador movil
- no se necesita control optimista complejo para estos recursos
- si otra empleada quiere retomar un borrador, debe pasar por POS o esperar a que el presupuesto se confirme
- desde POS, un ADMIN si puede revisar o reasignar si hace falta, pero eso no ocurre desde movil
- si la empleada cierra sesion, el borrador persiste en el servidor y puede retomarlo en cualquier dispositivo al volver a iniciar sesion

## Cliente movil

Opcion recomendada: `PWA` responsiva instalable.

Motivos:

- una sola base de codigo para iOS, Android y navegador de escritorio
- sin distribucion por tiendas de aplicaciones
- cache via service worker encaja con la futura Fase 2 del satelite
- menor costo de mantenimiento que doble nativo

Se descarta en esta etapa:

- React Native / Flutter por doble mantenimiento y distribucion mas compleja
- app nativa iOS/Android dedicada

### Pantallas y navegacion

La app tiene dos modos de uso que conviven:

Modo atencion a cliente (flujo principal):

1. pantalla de inicio post-login: escaner de QR de cliente
2. escanear QR → catalogo con cliente vinculado
3. sin QR u omitir → catalogo sin cliente
4. agregar al presupuesto → presupuesto activo
5. presupuesto listo → regresa al escaner para el siguiente cliente

Modo herramienta personal (acceso desde navegacion inferior):

- `Escaner` — consulta rapida de precio por codigo de barras o inicio de atencion por QR cliente
- `Catalogo` — busqueda libre de productos y precios
- `Presupuestos` — borradores activos de la empleada
- `Mis ventas` — ventas del dia y del periodo atribuidas, con conteo y total
- `Mis tickets` — historial de tickets confirmados

UX obligatoria:

- listbox de empleadas activas + teclado numerico grande para PIN en login
- navegacion inferior fija con acceso a las cinco secciones
- boton `Agregar al presupuesto` con protagonismo visual en catalogo y detalle de producto
- el escaner sirve para dos cosas: QR de cliente e inicio de atencion, y codigo de barras de producto para consulta rapida de precio
- scroll por arrastre en tablas y listados, pensado para uso tactil
- banner claro cuando no hay conexion con la PC principal
- indicador visible de empleada en sesion en todo momento
- boton discreto de cambiar empleada para rotar turno sin cerrar la app

## Seguridad en LAN

- FastAPI accesible solo en la red Wi-Fi del local
- certificado local (mkcert o self-signed) para HTTPS interno, o HTTP plano si el router esta aislado
- Wi-Fi del local con contrasena robusta y red separada para dispositivos personales
- tokens de sesion con expiracion corta
- PIN de empleada nunca viaja en claro ni se almacena reversible
- registro de intentos fallidos de login

## Deployment en la PC principal

Objetivo: que la API viva como un servicio estable en la PC principal, con la misma disciplina operativa que hoy tienen los respaldos.

- `FastAPI` ejecutado con `uvicorn` en un solo worker al inicio; ampliar solo si se observa carga real
- servicio Windows gestionado con `NSSM` para autoinicio, restart automatico en caso de crash y logs redirigidos
- alternativa valida: `Task Scheduler` con trigger `At startup`, pero se prefiere NSSM por manejo de fallos
- logs con rotacion diaria en `logs/api/`, siguiendo el patron usado en respaldos
- endpoint `/health` que reporta estado de base de datos, version de API y timestamp
- el endpoint `/health` lo consume tambien el satelite desktop y la PWA para detectar caidas
- la IP de la PC principal en la LAN debe ser fija (reservada en el router por MAC)
- documentar el arranque como extension de `WINDOWS_SETUP.md`

## Gestion de dispositivos moviles

Objetivo: mantener fricción baja para 5+ dispositivos sin perder control administrativo.

Flujo:

- la primera vez que un movil inicia sesion con empleada valida, el servidor registra automaticamente un `device_id` con nombre generico editable
- el POS expone una seccion `Configuracion > Dispositivos` con la lista de dispositivos registrados, ultima actividad y boton `Revocar`
- revocar un dispositivo invalida sus tokens actuales y obliga a nuevo login al volver a conectarse
- el admin puede renombrar dispositivos para ubicarlos en piso (`iPhone Ana`, `Tablet mostrador`)
- no se requiere pairing code ni aprobacion previa: el control real es que sin QR o seleccion + PIN de empleada no hay login

Riesgo controlado:

- si un movil se pierde o se roba, no tiene credenciales almacenadas: cada sesion requiere PIN
- el admin puede revocar preventivamente desde POS en cualquier momento

## Contrato de errores y versionado

- prefijo `/api/v1/` desde el primer endpoint; evita refactor costoso despues
- cuerpo de error uniforme: `{ "error": { "code": "string", "message": "string", "detail": {} } }`
- `code` es un identificador estable para el cliente, `message` es texto humano en espanol, `detail` es opcional para datos estructurados
- codigos HTTP usados de forma consistente:
  - `200/201` exito
  - `400` validacion
  - `401` sin token o token invalido
  - `403` empleada autenticada pero sin permiso para el recurso
  - `404` recurso no existe
  - `409` conflicto, por ejemplo intentar editar un borrador de otra empleada
  - `5xx` error del servidor
- montos como string decimal, nunca float, alineado con el manejo del POS
- fechas en ISO-8601 con zona horaria explicita
- autenticacion por `Authorization: Bearer <token>` en header

## Impacto en reportes existentes

Principio: no romper reportes actuales, solo extender.

- `usuario_id` sigue siendo operador tecnico en todos los reportes vigentes; ninguna columna existente se modifica
- `seller_employee_id` aparece como columna adicional en vistas de ventas y presupuestos cuando tenga sentido comercial
- reportes de desempeno por empleada nacen aparte, filtrando por `seller_employee_id`; no se sobreescriben reportes existentes
- en presupuestos creados desde movil, el `usuario_id` puede ser un usuario de servicio de la API (o `NULL` si el esquema lo permite), mientras que `seller_employee_id` lleva la empleada real
- documentar explicitamente que operador tecnico y vendedora acreditada no siempre coinciden, para evitar lectura incorrecta de reportes

## Transicion del satelite desktop y del kiosko

Regla: la API nace sirviendo al movil. Los demas clientes migran cuando este estable, no antes.

- `Satelite desktop actual`: no migra en la v1. Sigue conectandose directo a PostgreSQL como hoy. Migra a la API solo cuando la PWA este validada en piso, como parte de la Etapa 6 o posterior.
- `Kiosko`: cuando se abra su desarrollo, nace directamente como cliente de la API y reutiliza el modelo `Empleada` existente. No se duplica logica ni modelos.
- `POS principal`: no migra. Sigue siendo cliente directo de PostgreSQL y dueno de las operaciones sensibles (caja, inventario, cancelaciones, alta de empleadas).

Orden natural resultante:

1. hoy: POS y satelite desktop hablan directo a PostgreSQL
2. Etapas 2 a 5: se agrega PWA como cliente de API; el resto sigue igual
3. Etapa 6+: satelite desktop migra a API
4. al abrir kiosko: nace consumiendo API desde el inicio
5. POS principal se mantiene como cliente directo de PostgreSQL indefinidamente por diseno

## Fases recomendadas

### Etapa 0. Contrato del modelo

- cerrar decisiones de `usuario` vs `empleada` en esquema
- definir donde vive `seller_employee_id`
- documentar QR y PIN
- revisar `database/connection.py` y plan de migracion Alembic

### Etapa 1. Empleadas en backend

Parcialmente hecho. El POS ya contiene:

- modelo `Empleada` en `database/models.py`
- `services/employee_identity_service.py` con alta, edicion, generacion de codigo `VEND-N`, hash de PIN y resolucion por QR
- solo ADMIN puede gestionar empleadas

Queda pendiente en esta etapa:

- agregar `seller_employee_id` nullable en `venta`, `presupuesto` y afines
- migracion Alembic correspondiente
- revisar `database/connection.py` para dimensionar el pool de conexiones ante clientes adicionales
- sin UI nueva todavia

### Etapa 2. API de lectura y auth de empleada

- FastAPI como servicio en la PC principal, bajo `NSSM`, con `/health` funcional
- endpoints de catalogo y precios
- endpoint de lista publica de empleadas activas para el listbox de login
- endpoint de login con empleada seleccionada + PIN
- token de sesion por empleada y dispositivo, con expiracion corta
- registro automatico de `device_id` al primer login
- endpoint de consulta de cliente por QR escaneado

### Etapa 3. API de presupuestos y ventas de empleada

- crear, editar, listar presupuestos
- numeracion server-side via secuencia PostgreSQL
- atribucion automatica de `seller_employee_id` desde la sesion
- borrador ligado a empleada creadora: solo ella puede editarlo desde movil
- endpoint de ventas del dia atribuidas a la empleada en sesion
- endpoint de ventas por periodo con filtro de fecha
- endpoint de detalle de ticket individual

### Etapa 4. PWA movil

- login con listbox de empleadas + PIN
- navegacion inferior con cinco secciones: Escaner, Catalogo, Presupuestos, Mis ventas, Mis tickets
- escaner dual: QR de cliente para inicio de atencion, codigo de barras para consulta rapida de precio
- flujo completo de catalogo → agregar → presupuesto → listo para caja
- vista de ventas del dia y del periodo con conteo y total
- historial de tickets confirmados
- banner de conexion
- pruebas reales en piso con varias empleadas

### Etapa 5. Hardening multi-dispositivo

- ajuste del pool de conexiones
- pruebas de carga con varias sesiones simultaneas
- gestion de dispositivos desde POS (`Configuracion > Dispositivos`) con renombrado y revocacion

### Etapa 6. Atribucion en POS desktop y kiosko

- permitir seleccionar empleada acreditada en satelite actual y en caja
- trazabilidad uniforme entre canales
- revision de reportes existentes para no mezclar operadora y vendedora

### Etapa 7. Analitica y comisiones

- solo cuando la atribucion este solida en los tres canales
- seguir el orden descrito en `docs/empleadas_y_comisiones.md`

## Riesgos especificos

- usar el usuario del POS como login movil. Rompe el modelo desde el inicio.
- tratar el token movil como permanente por dispositivo en lugar de por sesion de empleada.
- permitir que un movil caiga a un modo offline que parezca escribir cuando en realidad no escribe.
- abrir comisiones antes de que la atribucion este estable en todos los canales.
- dimensionar la API con mentalidad de 1-2 clientes y descubrir el problema en piso con 6 vendedoras.
- asumir que el Wi-Fi del local aguanta. Un router domestico debil degrada la experiencia mas que cualquier decision de software.
- mezclar esta arquitectura con cambios en `Caja` o `Inventario` en el mismo ciclo.

## Que NO hace esta arquitectura

- no habilita cobro desde movil
- no reemplaza el satelite desktop en el corto plazo
- no expone la API a internet
- no resuelve operacion offline completa
- no introduce replicas de base de datos
- no toca `Caja` ni `Inventario` como parte del alcance

## Relacion con iniciativas ya documentadas

- la `Fase 2` del satelite (cache local de lectura) sigue siendo valida y aplica tanto al satelite desktop como al movil via service worker
- la `Fase 6` del modulo de empleadas se adelanta parcialmente: el movil nace ya con identidad de empleada, aunque la analitica completa se deje para despues
- el orden de trabajo de `docs/empleadas_y_comisiones.md` se respeta: ficha, atribucion, analitica, comisiones

## Estado

- `2026-04-15`: documento creado para unificar API, movil y empleadas
- `2026-04-15`: cerradas 8 decisiones de arquitectura (alta de empleadas desde POS, borrador ligado a empleada, escaneo de cliente solo consulta, deployment Windows con NSSM, gestion de dispositivos, versionado `/api/v1/` y contrato de errores, reportes por extension, transicion satelite y kiosko)
- `2026-04-15`: ajuste de login movil a listbox de empleadas activas + PIN, con QR como alternativa opcional futura
- `2026-04-15`: redefinicion del alcance: la app es la herramienta de trabajo personal de la empleada; incluye mis ventas, mis tickets, escaner dual y navegacion por secciones
- `2026-04-15`: escaner definido como pantalla de inicio post-login con doble funcion: QR de cliente para inicio de atencion y codigo de barras para consulta rapida de precio
- `2026-04-15`: descubrimiento: parte de la Etapa 1 ya existe en codigo (`Empleada` y `employee_identity_service.py`); falta `seller_employee_id` en ventas y presupuestos
- implementacion pendiente
- prerrequisito: cerrar etapa actual de estabilizacion operativa del satelite conectado antes de abrir este frente
