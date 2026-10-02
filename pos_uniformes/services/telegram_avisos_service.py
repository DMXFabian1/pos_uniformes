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

Lo que se controla desde el chat (Daniel, 01/10: "me gustaría controlarlos de
telegram"):

- `/aviso texto` — a todas las pantallas, pide acuse, vence en 12 h.
- `/aviso 3h texto` — con su propio plazo (`30m`, `2d` también).
- `/aviso @caja2 texto` — a una sola pantalla.
- **Una foto** mandada al bot, sin comando: sale a pantalla completa. Lo que
  escribas de pie de foto es el aviso, y ahí también valen el plazo y la
  pantalla.
- `/cartel texto` — el que NO interrumpe: solo rota cuando nadie está tocando
  la pantalla, sin botón «Enterada». Para promos y recordatorios.
- `/avisos` — los puestos; tocando uno se abre con sus botones: quitarlo,
  darle más tiempo, o reponerlo para que lo vuelvan a acusar.

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


def _clave(nombre: str) -> str:
    """«Caja 2» → «caja2»: así `@caja2` encuentra la pantalla sin pelear con
    espacios ni acentos, que es lo que no se puede escribir en un @."""
    from pos_uniformes.utils.text_normalization import normalize_text_unicode

    return "".join(c for c in normalize_text_unicode(nombre) if c.isalnum())


def pantallas(session) -> list[dict]:
    """Los satélites conocidos con su nombre y su @ para escribirlo. [] si no se pudo."""
    try:
        from pos_uniformes.services import satelite_registry_service as rsvc

        return [
            {
                "identificador": s["identificador"],
                "nombre": s["nombre"],
                "online": s["online"],
                "arroba": "@" + _clave(s["nombre"]),
            }
            for s in rsvc.listar_con_estado(session)
        ]
    except Exception:  # noqa: BLE001
        return []


def buscar_pantalla(session, nombre: str) -> dict | None:
    """La pantalla cuyo nombre coincide con lo que se escribió tras el @.

    Exacta primero; si no, la única que empieza con eso. Si hay dos que empiezan
    igual no se adivina: mandar un aviso a la pantalla equivocada es peor que
    pedir que lo escriba completo.
    """
    buscado = _clave(nombre)
    if not buscado:
        return None
    todas = pantallas(session)
    for p in todas:
        if _clave(p["nombre"]) == buscado:
            return p
    empiezan = [p for p in todas if _clave(p["nombre"]).startswith(buscado)]
    return empiezan[0] if len(empiezan) == 1 else None


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


AYUDA_CORTA = (
    "¿Qué aviso? Se usa así:\n"
    "/aviso Junta a las 6\n"
    "/aviso 3h Hoy cerramos temprano — se quita en 3 horas\n"
    "/aviso @caja2 Ven un momento — solo en esa pantalla\n"
    "/cartel Promoción de mochilas — rota sin interrumpir\n\n"
    "También puedes mandarme una foto: sale a pantalla completa, y lo que "
    "escribas de pie de foto es el aviso.\n"
    "Sin plazo se quita solo en 12 h. Para ver los puestos: /avisos"
)


class AvisoVacio(ValueError):
    """No había qué mandar (ni texto ni imagen)."""


def _leer_prefijos(session, crudo: str) -> tuple[str, float, dict | None, list[str]]:
    """Come los `3h` y `@caja2` del principio. (resto, horas, pantalla, quejas).

    Solo del principio y solo si tienen esa forma: así «5 playeras llegaron» o
    un correo en el texto no se confunden con órdenes.
    """
    horas = HORAS_DEFAULT
    pantalla: dict | None = None
    quejas: list[str] = []
    while crudo:
        partes = crudo.split(maxsplit=1)
        primera = partes[0]
        resto = partes[1].strip() if len(partes) > 1 else ""
        if primera.startswith("@") and len(primera) > 1:
            encontrada = buscar_pantalla(session, primera[1:])
            if encontrada is None:
                quejas.append(
                    f"No encontré la pantalla «{primera}», así que lo puse en todas."
                )
            else:
                pantalla = encontrada
            crudo = resto
            continue
        plazo = leer_plazo(primera)
        # Un plazo solo es plazo si queda aviso después: «/aviso 3h» a secas es
        # un aviso que dice «3h», no un plazo sin recado.
        if plazo is not None and resto:
            horas = plazo
            crudo = resto
            continue
        break
    return crudo, horas, pantalla, quejas


def mandar(
    session,
    argumento: str,
    *,
    quien: str = "telegram",
    imagen: bytes | None = None,
    imagen_mime: str | None = None,
    interrumpe: bool = True,
) -> str:
    """`/aviso [plazo] [@pantalla] texto` → lo crea y lo pone. Hace commit.

    `imagen`: los bytes ya reducidos de una foto mandada al bot.
    `interrumpe=False` es `/cartel`: rota en la cartelera sin tapar a nadie ni
    pedir acuse. Devuelve lo que se contesta en el chat.
    """
    from pos_uniformes.services import anuncio_service as asvc

    crudo = (argumento or "").strip()
    if not crudo and imagen is None:
        return AYUDA_CORTA

    crudo, horas, pantalla, quejas = _leer_prefijos(session, crudo)
    if not crudo and imagen is None:
        return AYUDA_CORTA

    titulo, mensaje = partir_texto(crudo)
    anuncio = asvc.crear_anuncio(
        session,
        titulo=titulo,
        mensaje=mensaje,
        imagen=imagen,
        imagen_mime=imagen_mime,
        destinos=[pantalla["identificador"]] if pantalla else None,
        pide_acuse=interrumpe,
        expira_en=asvc.vence_en(horas),
        # Un aviso pasa por delante de la cartelera; un cartel se forma en la fila.
        prioridad=10 if interrumpe else 0,
        creado_por=(quien or "telegram")[:60],
    )
    if interrumpe:
        asvc.notificar(session, "inmediato", anuncio.id)
    session.commit()

    que = "📣 Aviso" if interrumpe else "🖼 Cartel"
    if pantalla:
        donde = f"en {pantalla['nombre']}"
        if not pantalla["online"]:
            donde += " (está apagada: lo verá al encender)"
    else:
        cuantas = _cuantas_pantallas(session)
        donde = (
            "en las pantallas"
            if cuantas is None
            else f"en {_plural(cuantas, 'pantalla', 'pantallas')}"
        )
    lineas = [f"{que} puesto {donde}:", ""]
    cuerpo = (titulo or mensaje or "").strip()
    lineas.append(f"«{cuerpo}»" if cuerpo else "(solo la imagen)")
    if imagen is not None and cuerpo:
        lineas.append("(con tu foto)")
    lineas.append("")
    lineas.append(falta_para(anuncio.expira_en).capitalize() + ".")
    if interrumpe:
        lineas.append('Te aviso aquí mismo en cuanto alguien toque «Enterada».')
    else:
        lineas.append("No interrumpe a nadie: sale cuando la pantalla está sola.")
    lineas.append("Para quitarlo o darle más tiempo: /avisos")
    if quejas:
        lineas.append("")
        lineas.extend(quejas)
    return "\n".join(lineas)


def mandar_foto(
    session,
    *,
    file_id: str,
    pie: str = "",
    quien: str = "telegram",
    token: str | None = None,
    interrumpe: bool = True,
) -> str:
    """Una foto mandada al bot → aviso a pantalla completa. Hace commit.

    Baja el archivo, lo reduce como cualquier imagen de anuncio y lo manda. Si
    la bajada o la imagen fallan se dice por qué y no se crea nada: más vale no
    poner nada que poner un cuadro en negro en la tienda.
    """
    from pos_uniformes.services.anuncio_image_service import preparar_imagen
    from pos_uniformes.services.telegram_service import bajar_archivo

    try:
        crudos = bajar_archivo(file_id, token=token)
    except Exception as exc:  # noqa: BLE001
        return f"No pude bajar la foto de Telegram: {exc}"
    try:
        datos, mime = preparar_imagen(crudos)
    except Exception as exc:  # noqa: BLE001
        return f"No pude usar esa imagen: {exc}"
    return mandar(
        session, pie, quien=quien, imagen=datos, imagen_mime=mime, interrumpe=interrumpe
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


def _etiqueta(anuncio) -> str:
    texto = (anuncio.titulo or anuncio.mensaje or "").strip().replace("\n", " ")
    if not texto:
        return "(imagen)"
    return texto if len(texto) <= 40 else texto[:39] + "…"


def _renglones_de(session, anuncio, nombres: dict[str, str]) -> list[str]:
    """Las dos o tres líneas que describen un aviso: de cuándo es, a dónde va,
    y quién lo ha visto."""
    from pos_uniformes.services import anuncio_service as asvc

    lineas = [f"«{_etiqueta(anuncio)}»"]
    detalle = [hace_cuanto(anuncio.creado_en), falta_para(anuncio.expira_en)]
    if anuncio.destinos:
        detalle.append("solo " + ", ".join(nombres.get(d, d) for d in anuncio.destinos))
    if anuncio.imagen is not None:
        detalle.append("🖼 con foto")
    if not anuncio.pide_acuse:
        detalle.append("no interrumpe")
    lineas.append("   " + " · ".join(x for x in detalle if x))
    if anuncio.pide_acuse:
        vistos = asvc.quien_vio(session, anuncio.id)
        if not vistos:
            lineas.append("   ⏳ Nadie lo ha visto todavía")
        for v in vistos:
            pantalla = v.satelite_nombre or nombres.get(v.satelite) or v.satelite or "?"
            quien = v.empleada or "alguien"
            lineas.append(f"   ✅ {quien} en {pantalla} · {hace_cuanto(v.visto_en)}")
    return lineas


def resumen(session) -> str:
    """Los avisos que están puestos ahora, con quién los vio."""
    from pos_uniformes.services import anuncio_service as asvc

    activos = asvc.listar_activos(session)
    if not activos:
        lineas = ["No hay ningún aviso puesto.", "", "Para poner uno: /aviso Junta a las 6"]
        nombres = pantallas(session)
        if nombres:
            lineas.append("")
            lineas.append("Pantallas: " + " · ".join(
                f"{'🟢' if p['online'] else '⚪'} {p['nombre']} ({p['arroba']})" for p in nombres
            ))
            lineas.append("Para una sola: /aviso " + nombres[0]["arroba"] + " Ven un momento")
        return "\n".join(lineas)

    nombres = {p["identificador"]: p["nombre"] for p in pantallas(session)}
    lineas = [f"📣 {_plural(len(activos), 'aviso puesto', 'avisos puestos')}:"]
    for a in activos:
        lineas.append("")
        lineas.extend(_renglones_de(session, a, nombres))
    lineas.append("")
    lineas.append("Toca uno para quitarlo o darle más tiempo.")
    return "\n".join(lineas)


def detalle(session, anuncio_id: int) -> tuple[str, list[list[tuple[str, str]]]]:
    """(texto, filas de botones) de UN aviso: quitarlo, alargarlo, reponerlo."""
    from pos_uniformes.services import anuncio_service as asvc

    anuncio = asvc.obtener(session, int(anuncio_id))
    if anuncio is None:
        return "Ese aviso ya no existe.", []
    nombres = {p["identificador"]: p["nombre"] for p in pantallas(session)}
    texto = "\n".join(_renglones_de(session, anuncio, nombres))
    if not anuncio.activo:
        texto += "\n\n(ya no está en las pantallas)"
        return texto, [[("🔄 Ponerlo otra vez", f"{PREFIJO}otra:{anuncio.id}")]]
    filas = [
        [("🗑 Quitarlo", f"{PREFIJO}quitar:{anuncio.id}")],
        [("⏱ +3 h", f"{PREFIJO}mas:{anuncio.id}:3"), ("⏱ +12 h", f"{PREFIJO}mas:{anuncio.id}:12")],
    ]
    if anuncio.pide_acuse:
        filas.append([("🔄 Que lo vean otra vez", f"{PREFIJO}otra:{anuncio.id}")])
    return texto, filas


def texto_y_botones(session) -> tuple[str, str]:
    """(texto, botones) de la pantalla de avisos del menú."""
    from pos_uniformes.services import anuncio_service as asvc
    from pos_uniformes.services import telegram_service

    activos = asvc.listar_activos(session)
    filas = [[(_etiqueta(a), f"{PREFIJO}ver:{a.id}")] for a in activos]
    if len(activos) > 1:
        filas.append([("🗑 Quitar todos", f"{PREFIJO}todos")])
    filas.append([("‹ Menú", "m:raiz")])
    return resumen(session), telegram_service.teclado(filas)


def es_de_avisos(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def _con_volver(filas: list[list[tuple[str, str]]]) -> str:
    from pos_uniformes.services import telegram_service

    return telegram_service.teclado(filas + [[("‹ Avisos", f"{PREFIJO}lista")]])


def _partes(accion: str) -> list[str]:
    return accion.split(":")


def atender(dato: str, *, session_factory) -> tuple[str, str, str]:
    """Un botón de avisos: (aviso corto, texto nuevo, botones nuevos)."""
    from pos_uniformes.services import anuncio_service as asvc

    accion = str(dato or "")[len(PREFIJO):]
    partes = _partes(accion)
    nombre = partes[0] if partes else ""

    def _id() -> int | None:
        try:
            return int(partes[1])
        except (IndexError, ValueError):
            return None

    if nombre == "ver":
        anuncio_id = _id()
        if anuncio_id is None:
            return "No conozco ese botón", "", ""
        with session_factory() as session:
            texto, filas = detalle(session, anuncio_id)
        return "", texto, _con_volver(filas)

    if nombre == "quitar":
        anuncio_id = _id()
        if anuncio_id is None:
            return "No conozco ese botón", "", ""
        with session_factory() as session:
            quitado = asvc.desactivar(session, anuncio_id)
            session.commit()
            texto, botones = texto_y_botones(session)
        return ("Quitado" if quitado else "Ya no estaba"), texto, botones

    if nombre == "mas":
        anuncio_id = _id()
        try:
            horas = float(partes[2])
        except (IndexError, ValueError):
            horas = 3.0
        if anuncio_id is None:
            return "No conozco ese botón", "", ""
        with session_factory() as session:
            anuncio = asvc.alargar(session, anuncio_id, horas)
            session.commit()
            if anuncio is None:
                texto, botones = texto_y_botones(session)
                return "Ese aviso ya no existe", texto, botones
            cuanto = falta_para(anuncio.expira_en)
            texto, filas = detalle(session, anuncio_id)
        return cuanto.capitalize(), texto, _con_volver(filas)

    if nombre == "otra":
        anuncio_id = _id()
        if anuncio_id is None:
            return "No conozco ese botón", "", ""
        with session_factory() as session:
            nuevo = asvc.reponer(session, anuncio_id)
            if nuevo is not None and nuevo.pide_acuse:
                asvc.notificar(session, "inmediato", nuevo.id)
            session.commit()
            if nuevo is None:
                texto, botones = texto_y_botones(session)
                return "Ese aviso ya no existe", texto, botones
            texto, filas = detalle(session, nuevo.id)
        return "Puesto otra vez", texto, _con_volver(filas)

    if nombre == "todos":
        with session_factory() as session:
            cuantos = asvc.desactivar_todos(session)
            session.commit()
            texto, botones = texto_y_botones(session)
        return f"Se quitaron {cuantos}", texto, botones

    # "av:" pelón o "av:lista": la lista.
    with session_factory() as session:
        texto, botones = texto_y_botones(session)
    return "", texto, botones


# ── Lo que se le manda a Daniel cuando alguien acusa ─────────────────────────


def aviso_de_acuse(
    *, etiqueta: str, empleada: str | None, pantalla: str | None, faltan: int | None = None
) -> str:
    """El mensaje que recibe Daniel cuando tocan «Enterada» en una pantalla.

    Cierra el tema cuando ya no falta nadie: así no se queda esperando otro
    mensaje que no va a llegar.
    """
    quien = (empleada or "Alguien").strip()
    donde = (pantalla or "").strip()
    linea = f"✅ {quien} vio el aviso"
    if donde:
        linea += f" en {donde}"
    partes = [linea, "", f"«{etiqueta}»", ""]
    if faltan:
        verbo = "Falta" if faltan == 1 else "Faltan"
        partes.append(f"{verbo} {_plural(faltan, 'pantalla', 'pantallas')} por verlo.")
    else:
        partes.append("Ya lo vieron. El aviso se quitó de las pantallas.")
    return "\n".join(partes)
