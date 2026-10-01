"""Mandar un aviso a las pantallas de la tienda desde el celular.

Daniel (01/10): "me gustaría enviar mensajes desde Telegram y se vean como
aviso". Un `/aviso` escrito desde donde sea aparece a pantalla completa en los
satélites, encima de lo que estén haciendo.

Mandar de lejos cambia dos cosas respecto del aviso que se creaba en el propio
kiosko:

- **Nadie vuelve a pasar a apagarlo.** Por eso todo aviso de Telegram vence por
  su cuenta (12 h por omisión, `/aviso 3h …` para otra cosa). Un «hoy cerramos
  temprano» no puede seguir en la cartelera la semana que entra.
- **Nadie contesta.** Por eso pide acuse: en la pantalla hay un botón
  «Enterada» y al tocarlo le llega a Daniel quién lo vio y en cuál pantalla.
  Sin eso, mandar un aviso es hablarle a una pared.

Este módulo es solo texto y botones; el aviso lo guarda `anuncio_service` y lo
pinta el overlay del satélite.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

#: Prefijo de los botones de avisos (máx. 64 bytes por regla de Telegram).
PREFIJO = "av:"

#: Si no se dice otra cosa, un aviso vive 12 h: alcanza para el día de trabajo
#: y no sobrevive a la noche.
HORAS_DEFAULT = 12.0

#: Arriba de esto el texto ya no cabe en letras grandes y va como mensaje.
LARGO_TITULO = 60

_PLAZO = re.compile(r"^(\d{1,3})\s*(m|min|minutos?|h|hs?|horas?|d|d[ií]as?)$", re.IGNORECASE)


def leer_plazo(palabra: str) -> float | None:
    """'3h' → 3.0 horas; '30m' → 0.5; '2d' → 48. None si no es un plazo.

    Se lee solo la primera palabra del aviso, y solo si tiene forma de plazo:
    así «5 playeras llegaron» no se interpreta como cinco de algo.
    """
    m = _PLAZO.match((palabra or "").strip())
    if m is None:
        return None
    cantidad = int(m.group(1))
    unidad = m.group(2).lower()
    if unidad.startswith("m"):
        return cantidad / 60
    if unidad.startswith("d"):
        return cantidad * 24.0
    return float(cantidad)


def partir_texto(texto: str) -> tuple[str | None, str | None]:
    """(título, mensaje) para que se vea bien en una pantalla grande.

    Un aviso corto va todo de título, en letras grandes: es lo que se lee de
    lejos. Uno largo va de mensaje. Si trae renglones, el primero es el título.
    """
    t = (texto or "").strip()
    if not t:
        return None, None
    if "\n" in t:
        cabeza, resto = t.split("\n", 1)
        return cabeza.strip() or None, resto.strip() or None
    if len(t) <= LARGO_TITULO:
        return t, None
    return None, t


def hace_cuanto(momento: datetime | None, ahora: datetime | None = None) -> str:
    """'hace 5 min', 'hace 2 h', 'ahora'. Vacío si no hay fecha."""
    if momento is None:
        return ""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    seg = (ahora - momento).total_seconds()
    if seg < 60:
        return "ahora"
    if seg < 3600:
        return f"hace {int(seg // 60)} min"
    if seg < 86400:
        return f"hace {int(seg // 3600)} h"
    dias = int(seg // 86400)
    return "hace 1 día" if dias == 1 else f"hace {dias} días"


def falta_para(expira: datetime | None, ahora: datetime | None = None) -> str:
    """'se quita en 3 h' / 'sin vencimiento'. Para que se sepa qué pasa luego."""
    if expira is None:
        return "sin vencimiento"
    if expira.tzinfo is None:
        expira = expira.replace(tzinfo=timezone.utc)
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        ahora = ahora.replace(tzinfo=timezone.utc)
    seg = (expira - ahora).total_seconds()
    if seg <= 0:
        return "ya venció"
    if seg < 3600:
        return f"se quita en {max(1, int(seg // 60))} min"
    if seg < 86400:
        return f"se quita en {int(seg // 3600)} h"
    return f"se quita en {int(seg // 86400)} días"


# ── Mandar ───────────────────────────────────────────────────────────────────


def mandar(session, argumento: str, *, quien: str = "telegram") -> str:
    """`/aviso [plazo] texto` → lo crea y pide que aparezca ya. Hace commit.

    Devuelve lo que se le contesta en el chat: qué se mandó, a cuántas
    pantallas y cuándo se quita solo.
    """
    from pos_uniformes.services import anuncio_service as asvc

    crudo = (argumento or "").strip()
    if not crudo:
        return (
            "¿Qué aviso? Se usa así:\n"
            "/aviso Junta a las 6\n"
            "/aviso 3h Hoy cerramos temprano — se quita en 3 horas\n"
            "/aviso 30m Ya voy para allá\n\n"
            "Sale a pantalla completa en las pantallas de la tienda y te digo "
            "quién lo vio. Si no dices plazo, se quita solo en 12 h.\n"
            "Para ver los que están puestos: /avisos"
        )

    horas = HORAS_DEFAULT
    partes = crudo.split(maxsplit=1)
    plazo = leer_plazo(partes[0]) if len(partes) > 1 else None
    if plazo is not None:
        horas = plazo
        crudo = partes[1].strip()
    if not crudo:
        return "Me dijiste el plazo pero no el aviso. Ejemplo: /aviso 3h Hoy cerramos temprano"

    titulo, mensaje = partir_texto(crudo)
    anuncio = asvc.crear_anuncio(
        session,
        titulo=titulo,
        mensaje=mensaje,
        pide_acuse=True,
        expira_en=asvc.vence_en(horas),
        prioridad=10,  # por encima de la cartelera de siempre
        creado_por=(quien or "telegram")[:60],
    )
    asvc.notificar(session, "inmediato", anuncio.id)
    session.commit()

    pantallas = _cuantas_pantallas(session)
    donde = "las pantallas" if pantallas is None else _plural(pantallas, "pantalla", "pantallas")
    return (
        f"📣 Aviso puesto en {donde}:\n\n"
        f"«{(titulo or mensaje or '').strip()}»\n\n"
        f"{falta_para(anuncio.expira_en).capitalize()}. "
        "Te aviso aquí mismo en cuanto alguien toque «Enterada».\n"
        "Para quitarlo antes: /avisos"
    )


def _plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno}" if n == 1 else f"{n} {varios}"


def _cuantas_pantallas(session) -> int | None:
    """Cuántos satélites están encendidos. None si no se pudo saber."""
    try:
        from pos_uniformes.services import satelite_registry_service as rsvc

        return sum(1 for s in rsvc.listar_con_estado(session) if s["online"])
    except Exception:  # noqa: BLE001 — el aviso ya salió; esto es solo el adorno
        return None


# ── Ver y quitar ─────────────────────────────────────────────────────────────


def _nombres_de_pantallas(session) -> dict[str, str]:
    try:
        from pos_uniformes.services import satelite_registry_service as rsvc

        return {s["identificador"]: s["nombre"] for s in rsvc.listar_con_estado(session)}
    except Exception:  # noqa: BLE001
        return {}


def _etiqueta(anuncio) -> str:
    texto = (anuncio.titulo or anuncio.mensaje or "").strip().replace("\n", " ")
    if not texto:
        return "(imagen)"
    return texto if len(texto) <= 40 else texto[:39] + "…"


def resumen(session) -> str:
    """Los avisos que están puestos ahora, con quién los vio."""
    from pos_uniformes.services import anuncio_service as asvc

    activos = asvc.listar_activos(session)
    if not activos:
        return (
            "No hay ningún aviso puesto.\n\n"
            "Para poner uno: /aviso Junta a las 6"
        )

    nombres = _nombres_de_pantallas(session)
    lineas = [f"📣 {_plural(len(activos), 'aviso puesto', 'avisos puestos')}:"]
    for a in activos:
        lineas.append("")
        lineas.append(f"«{_etiqueta(a)}»")
        detalle = [hace_cuanto(a.creado_en), falta_para(a.expira_en)]
        lineas.append("   " + " · ".join(x for x in detalle if x))
        if a.pide_acuse:
            vistos = asvc.quien_vio(session, a.id)
            if not vistos:
                lineas.append("   ⏳ Nadie lo ha visto todavía")
            for v in vistos:
                pantalla = v.satelite_nombre or nombres.get(v.satelite) or v.satelite or "?"
                quien = v.empleada or "alguien"
                lineas.append(f"   ✅ {quien} en {pantalla} · {hace_cuanto(v.visto_en)}")
    lineas.append("")
    lineas.append("Toca uno para quitarlo de las pantallas.")
    return "\n".join(lineas)


def texto_y_botones(session) -> tuple[str, str]:
    """(texto, botones) de la pantalla de avisos del menú."""
    from pos_uniformes.services import anuncio_service as asvc
    from pos_uniformes.services import telegram_service

    activos = asvc.listar_activos(session)
    filas = [[(f"🗑 {_etiqueta(a)}", f"{PREFIJO}quitar:{a.id}")] for a in activos]
    if len(activos) > 1:
        filas.append([("🗑 Quitar todos", f"{PREFIJO}todos")])
    filas.append([("‹ Menú", "m:raiz")])
    return resumen(session), telegram_service.teclado(filas)


def es_de_avisos(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def atender(dato: str, *, session_factory) -> tuple[str, str, str]:
    """Un botón de avisos: (aviso corto, texto nuevo, botones nuevos)."""
    from pos_uniformes.services import anuncio_service as asvc

    accion = str(dato or "")[len(PREFIJO):]

    if accion.startswith("quitar:"):
        try:
            anuncio_id = int(accion.split(":", 1)[1])
        except ValueError:
            return "No conozco ese botón", "", ""
        with session_factory() as session:
            quitado = asvc.desactivar(session, anuncio_id)
            session.commit()
            texto, botones = texto_y_botones(session)
        return ("Quitado" if quitado else "Ya no estaba"), texto, botones

    if accion == "todos":
        with session_factory() as session:
            cuantos = asvc.desactivar_todos(session)
            session.commit()
            texto, botones = texto_y_botones(session)
        return f"Se quitaron {cuantos}", texto, botones

    # "av:" pelón o "av:ver": la lista.
    with session_factory() as session:
        texto, botones = texto_y_botones(session)
    return "", texto, botones


# ── Lo que se le manda a Daniel cuando alguien acusa ─────────────────────────


def aviso_de_acuse(
    *, etiqueta: str, empleada: str | None, pantalla: str | None, faltan: int | None = None
) -> str:
    """El mensaje que recibe Daniel cuando tocan «Enterada» en una pantalla."""
    quien = (empleada or "Alguien").strip()
    donde = (pantalla or "").strip()
    linea = f"✅ {quien} vio el aviso"
    if donde:
        linea += f" en {donde}"
    partes = [linea, "", f"«{etiqueta}»"]
    if faltan:
        partes.append("")
        partes.append(
            f"Falta {_plural(faltan, 'pantalla', 'pantallas')} por verlo."
            if faltan > 0
            else ""
        )
    return "\n".join(x for x in partes if x is not None)
