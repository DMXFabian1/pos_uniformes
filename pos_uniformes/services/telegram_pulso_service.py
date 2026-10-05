"""`/pulso` — ¿está todo en pie?

La pregunta que Daniel se hace desde lejos es una sola, y para contestarla tenía
que mandar `/hoy`, `/cortes`, `/asistencia`, acordarse de revisar el respaldo y
adivinar si los kioskos estaban prendidos. Cinco comandos y una corazonada.

Esto junta en una pantalla lo que se construyó esta semana. Reglas:

- **Cada renglón se gana su marca**: ✅ lo que está bien, ⚠️ lo que pide
  atención. Se puede leer de un vistazo sin entender ninguna cifra.
- **Lo que no se pudo averiguar se dice**, no se asume bien. Un `/pulso` que
  calla lo que no sabe es peor que no tenerlo: enseña a confiar de más.
- **Cada bloque es independiente**: si uno truena, los demás salen igual. El
  valor está en verlo completo, y un solo dato caído no puede llevarse la vista.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

BIEN = "✅"
OJO = "⚠️"
MUDO = "·"


def _bloque(session, lineas: list[str], hacer) -> None:
    """Corre un bloque; si truena, lo dice y sigue con los demás.

    El rollback no es adorno: en Postgres una consulta que falla deja la
    transacción abortada y **todo lo que venga después falla también**. Sin
    esto, un bloque malo se llevaba a los siguientes y el pulso salía medio
    vacío sin decir por qué (visto contra la base real, 02/10).
    """
    try:
        resultado = hacer()
    except Exception:  # noqa: BLE001
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        lineas.append(f"{OJO} (no se pudo leer este dato)")
        return
    if resultado:
        lineas.extend(resultado if isinstance(resultado, list) else [resultado])


def pulso(session, *, hoy: date | None = None, ahora: datetime | None = None) -> str:
    """El estado de la tienda en una pantalla."""
    ahora = ahora or datetime.now().astimezone()
    hoy = hoy or ahora.date()

    lineas: list[str] = [f"🫀 La tienda ahora — {ahora:%d/%m %H:%M}", ""]
    _bloque(session, lineas, lambda: _tienda(session, hoy, ahora))
    _bloque(session, lineas, lambda: _venta(session, hoy, ahora))
    _bloque(session, lineas, lambda: _corte(session, hoy))
    lineas.append("")
    _bloque(session, lineas, lambda: _pantallas(session))
    _bloque(session, lineas, lambda: _impresion(session, ahora))
    _bloque(session, lineas, lambda: _respaldo())
    lineas.append("")
    _bloque(session, lineas, lambda: _esperando(session))

    while lineas and not lineas[-1]:
        lineas.pop()
    return "\n".join(lineas)


# ── Bloques ──────────────────────────────────────────────────────────────────


def _tienda(session, hoy: date, ahora: datetime) -> list[str]:
    from pos_uniformes.services import asistencia_service as asis
    from pos_uniformes.services.horario_tienda_service import hora_apertura, hora_cierre

    apertura, cierre = hora_apertura(hoy), hora_cierre(hoy)
    abierta = apertura <= ahora.time() <= cierre
    estan = [a.nombre.split()[0] for a in asis.asistencia_del_dia(session, hoy)
             if a.estado == asis.PRESENTE]
    if not abierta:
        return [f"{MUDO} Cerrada (abre {apertura:%H:%M})"]
    if not estan:
        # En horario y sin nadie registrado: o no han llegado, o no han vendido.
        return [f"{OJO} Abierta · nadie ha movido nada todavía"]
    return [f"{BIEN} Abierta · {', '.join(estan)}"]


def _venta(session, hoy: date, ahora: datetime) -> list[str]:
    from pos_uniformes.services import comparativa_service as comp

    c = comp.comparar(session, hoy, ahora=ahora)
    lineas = [f"{MUDO} Vendido: ${c.hoy:,.2f}"]
    detalle = comp.texto(c)
    if detalle:
        lineas.append(f"   {detalle}")
    return lineas


def _corte(session, hoy: date) -> list[str]:
    from pos_uniformes.services.corte_caja_service import ultimo_corte

    corte = ultimo_corte(session)
    if corte is None:
        return [f"{OJO} Nunca se ha hecho un corte"]
    cuando = getattr(corte, "fecha", None) or getattr(corte, "created_at", None)
    dia = cuando.date() if hasattr(cuando, "date") else cuando
    if dia == hoy:
        return [f"{BIEN} Corte de hoy hecho (${Decimal(str(corte.monto_final)):,.2f})"]
    dias = (hoy - dia).days if dia else None
    if dias == 1:
        return [f"{MUDO} Último corte: ayer"]
    return [f"{OJO} Último corte: hace {dias} días"]


def _pantallas(session) -> list[str]:
    from pos_uniformes.services import satelite_registry_service as rsvc

    sats = rsvc.listar_con_estado(session)
    if not sats:
        return [f"{MUDO} Pantallas: ninguna registrada"]
    prendidas = [s for s in sats if s["online"]]
    apagadas = [s["nombre"] for s in sats if not s["online"]]
    if not apagadas:
        return [f"{BIEN} Pantallas: {len(prendidas)} prendidas"]
    marca = OJO if prendidas else OJO
    return [f"{marca} Pantallas: {len(prendidas)} de {len(sats)} · apagada: {', '.join(apagadas)}"]


def _impresion(session, ahora) -> list[str]:
    """¿Está saliendo el papel?

    Con una sola PC conectada a las impresoras, apagarla no da ningún error:
    los tickets y las etiquetas se quedan en la cola y el que vendió cree que
    su ticket salió. Este renglón es lo único que lo delata (2026-10-05).
    """
    from pos_uniformes.services import trabajos_service as tr

    atorados = tr.esperando_impresion(session, ahora=ahora)
    if not atorados:
        return [f"{BIEN} Impresión al día: nada esperando en la cola."]
    cuantos = {}
    for t in atorados:
        nombre = getattr(t.tipo, "value", str(t.tipo)).lower()
        cuantos[nombre] = cuantos.get(nombre, 0) + 1
    detalle = ", ".join(f"{n} {nombre}" for nombre, n in sorted(cuantos.items()))
    espera = ahora - (atorados[0].created_at.astimezone() if atorados[0].created_at else ahora)
    minutos = int(espera.total_seconds() // 60)
    cuanto = f"{minutos} min" if minutos < 120 else f"{minutos // 60} h"
    return [
        f"{OJO} Sin imprimir: {detalle} — el más viejo lleva {cuanto}.",
        "   Prende el Servidor de impresión (la PC con las impresoras) y sale solo.",
    ]


def _respaldo() -> list[str]:
    from pos_uniformes.services import respaldo_estado_service as est

    estado = est.leer_estado()
    # `texto_resumen` ya trae su propia marca; aquí manda la del renglón.
    linea = est.texto_resumen(estado).replace(" ✅", "").replace(" ⚠️", "")
    return [f"{BIEN if estado.al_dia else OJO} {linea}"]


def _esperando(session) -> list[str]:
    """Lo que pide una decisión suya. Si no hay nada, se dice — es buena noticia."""
    from pos_uniformes.services import anuncio_service as asvc
    from pos_uniformes.services import prestamos_service as pr

    pendientes = []
    prestamos = pr.pendientes(session)
    if prestamos:
        quienes = ", ".join(
            str(p.employee_name or p.employee_code).split()[0] for p in prestamos
        )
        pendientes.append(f"{OJO} Préstamos por responder: {quienes} → /prestamos")
    try:
        from pos_uniformes.services import descansos_service as ds

        descansos = ds.pendientes(session)
        if descansos:
            quienes = ", ".join(
                f"{str(d.employee_name or d.employee_code).split()[0]} {d.fecha:%d/%m}"
                for d in descansos
            )
            pendientes.append(f"{OJO} Días de descanso por responder: {quienes} → /descansos")
    except Exception:  # noqa: BLE001 — base sin la tabla todavía
        pass
    avisos = [a for a in asvc.listar_activos(session) if a.pide_acuse]
    sin_ver = [a for a in avisos if not asvc.quien_vio(session, a.id)]
    if sin_ver:
        pendientes.append(f"{MUDO} Avisos que nadie ha visto: {len(sin_ver)} → /avisos")
    if not pendientes:
        return [f"{BIEN} Nada esperando tu respuesta"]
    return pendientes
