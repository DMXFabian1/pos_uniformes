# Estrategia de Respaldos Automaticos y Recuperacion

## Objetivo

Definir una estrategia practica para proteger la base de datos del POS frente a:

- perdida de luz
- dano del equipo
- corrupcion operativa
- error humano

La idea no es depender solo del respaldo manual desde la app, sino combinar:

- proteccion del motor
- respaldos automaticos
- copias fuera de la maquina

## Aclaracion importante

Un respaldo `.dump` no evita por si solo la corrupcion por apagones.

Para reducir riesgo real hacen falta dos capas distintas:

### 1. Resistencia operativa

- PostgreSQL bien configurado
- escritura segura a disco
- recuperacion del motor al reiniciar
- idealmente UPS o no-break

### 2. Recuperacion

- respaldos automaticos
- retencion
- copia externa
- restauracion probada

## Estado actual

Hoy el sistema ya tiene:

- respaldo manual desde Configuracion
- soporte para `.sql` y `.dump`
- restauracion de `.dump`
- script reutilizable de respaldo:
  - `scripts/backup_database.py`
- runner listo para tarea programada:
  - `scripts/run_scheduled_backup.py`
- servicio base:
  - `services/backup_service.py`

No existe todavia un programador automatico dentro del POS.

## Decision recomendada

No conviene correr respaldos automaticos desde la UI principal.

La estrategia recomendada es:

- mantener respaldo manual dentro del POS
- programar respaldo automatico por tarea del sistema operativo
- copiar respaldos a una ubicacion externa

Asi el POS no queda responsable de:

- esperar horas
- dormir y despertar tareas
- bloquear UI
- manejar estados frágiles de segundo plano

## Modelo recomendado

### Capa A. Respaldo manual

Seguir igual:

- crear respaldo manual desde Configuracion
- revisar lista
- restaurar `.dump`

Sirve para:

- checkpoint antes de cambios sensibles
- respaldo inmediato antes de restaurar
- exportacion operativa controlada

### Capa B. Respaldo automatico local

Programar una tarea externa que ejecute:

- `scripts/backup_database.py`

Formato recomendado:

- `.dump`

Frecuencia recomendada:

- un respaldo nocturno diario
- un respaldo extra al mediodia si la operacion lo justifica

Retencion local recomendada:

- `7` a `14` dias diarios
- `4` a `8` semanas si se agrega respaldo semanal

### Capa C. Copia externa

Despues de generar el `.dump`, copiarlo a:

- OneDrive
- Google Drive
- Dropbox
- NAS
- disco externo

Regla importante:

- el respaldo no debe vivir solo en la misma maquina que corre PostgreSQL

## Politica recomendada

### Frecuencia minima sugerida

- diario a las `02:00`

### Frecuencia recomendada para operacion media

- diario a las `02:00`
- adicional a las `14:00`

### Formato

- usar `.dump` para restauracion real
- dejar `.sql` solo como apoyo tecnico, no como respaldo principal operativo

### Rotacion

- diarios locales: `14` dias
- semanales externos: `8` semanas

## Propuesta tecnica por sistema

### Windows

Usar:

- `Task Scheduler`

Tarea sugerida:

- ejecutar el Python de la `.venv`
- correr `scripts/run_scheduled_backup.py --format custom --retention-days 14`

Si se agrega copia externa:

- segunda tarea o script post-respaldo para copiar a carpeta sincronizada

### macOS

Usar:

- `launchd`

Y ejecutar el mismo script con la `.venv`.

## Estado visible dentro del POS

La vista de `Configuracion > Respaldo y restauracion` ya puede mostrar:

- ultimo respaldo automatico correcto
- antiguedad del ultimo automatico
- si el ultimo automatico ya esta viejo
- si la ultima ejecucion automatica fallo

Esto depende del archivo de estado que mantiene:

- `scripts/run_scheduled_backup.py`

## Recuperacion ante falla

### Escenario 1. Error operativo

- restaurar el ultimo `.dump` sano
- validar apertura
- revisar movimientos posteriores perdidos si aplica

### Escenario 2. Dano del equipo

- reinstalar PostgreSQL
- restaurar el respaldo externo mas reciente
- validar version del esquema

### Escenario 3. Apagon o corte brusco

- primero dejar que PostgreSQL recupere consistencia al reiniciar
- solo restaurar un respaldo si la base realmente quedo danada o inconsistente

No conviene restaurar por reflejo si el motor puede recuperarse solo.

## Recomendaciones de resiliencia

### Muy recomendadas

- no-break / UPS en el equipo del servidor o caja principal
- disco SSD sano
- PostgreSQL instalado de forma normal, no portable improvisada
- apagado correcto del sistema cuando sea posible

### Recomendadas

- carpeta externa sincronizada para respaldos
- prueba de restauracion periodica
- checklist simple para recuperacion

## Alcance recomendado para implementacion futura

### v1

- documentar politica oficial de respaldo
- estandarizar `.dump` como formato principal
- dejar script listo para tarea programada
- documentar frecuencia y retencion

### v2

- agregar script auxiliar para copia externa
- documentar instalacion en Windows y macOS

### v3

- considerar una pequena vista en Configuracion para mostrar:
  - ultimo respaldo automatico detectado
  - estado de antiguedad
  - advertencia si el ultimo respaldo es viejo

## Lo que no conviene hacer

- dejar el respaldo automatico viviendo dentro de `main_window.py`
- depender solo del respaldo manual
- guardar el unico respaldo en la misma maquina
- usar solo `.sql` si el flujo real de restauracion depende de `.dump`
- suponer que respaldo = proteccion contra apagones

## Propuesta de ruta

Esta mejora encaja mejor en `Fase 5` como iniciativa de estabilidad operativa.

Orden recomendado:

1. definir politica oficial
2. preparar tarea automatica Windows
3. preparar copia externa
4. documentar recuperacion
5. opcionalmente, mostrar estado del ultimo respaldo en Configuracion
