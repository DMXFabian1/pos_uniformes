"""Bot de Telegram para ordenar cosas desde el celular (solo Daniel).

Comandos:
    /corte        hace el corte ahora e imprime el ticket en la tienda
    /corte 5000   igual, pero se retiran $5,000 (el ticket cuadra con eso)
    /corte sintarjeta   igual, pero los cobros con tarjeta quedan ocultos
    /nocorte      deja pasar el corte que se propuso hoy
    /estado       qué hay en caja ahora mismo
    /hoy          cómo va el día ahora mismo, en un vistazo
    /pulso        ¿está todo en pie? la tienda entera en una pantalla
    /cortes       los últimos cortes; tocando uno se ajusta o se borra
    /ajustar N X  cambia la cifra de un corte, diciendo por qué
    /resumen      el resumen del día (el mismo de la noche)
    /pendientes   lo que falta por registrar
    /asistencia   quién vino hoy (deducido de su primer movimiento)
    /prenda       precio y existencia por talla
    /escuela      cómo va una escuela (contada, surtida, vendida)
    /contar       qué falta contar, lo rojo primero
    /faltas       lo que pidieron y no había
    /pagos        a quién le toca cobrar y cuánto
    /pagar X si   registra el pago (sin el "si" solo enseña el desglose)
    /retiro N X   saca del cajón dejando dicho para qué
    /cajon        corrige lo que NO salió del cajón, antes del corte
    /prestamos    aprobar o rechazar lo que pidieron
    /aviso X      pone X a pantalla completa en las pantallas de la tienda
    /avisos       los avisos puestos, quién los vio, y quitarlos
    /cartel X     igual, pero sin interrumpir: rota cuando nadie toca
    (una foto)    mandarle una foto al bot la pone a pantalla completa
    /ayuda        esta lista

Solo responde al chat configurado (POS_UNIFORMES_TELEGRAM_CHAT_ID); a
cualquier otro lo ignora. `atender_texto` es la lógica (testeable); el
`escuchar` hace long-polling contra la API.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

logger = logging.getLogger("telegram_bot")

CODIGO_REMOTO = "VEND-1"  # Daniel: el que manda /corte

AYUDA = (
    "CAJA\n"
    "/corte — hacer el corte ahora e imprimir el ticket en la tienda\n"
    "/corte 5000 — el mismo corte, pero se retiran $5,000\n"
    "/corte sintarjeta — sin que se vean los cobros con tarjeta\n"
    "   (se pueden juntar: /corte 5000 sintarjeta)\n"
    "/nocorte — dejar pasar el corte propuesto hoy\n"
    "/estado — qué hay en caja ahora\n"
    "/pulso — ¿está todo en pie? la tienda entera en una pantalla\n"
    "/hoy — cómo va el día ahora mismo\n"
    "/resumen — resumen del día (el de la noche, completo)\n"
    "/pendientes — lo que falta por registrar\n"
    "/cortes — los últimos cortes; toca uno para ajustarlo o borrarlo\n"
    "/cortes 30 — los de los últimos 30 días (para rastrear el dinero)\n"
    "/ajustar 12 12500 depósito al banco — cambia la cifra de ese corte\n"
    "/sintarjeta 12 — esconde los cobros con tarjeta de un corte ya hecho\n"
    "/retiro 500 gasolina — saca del cajón, con su motivo\n"
    "/cajon — desmarca lo que NO salió del cajón (una transferencia,\n"
    "   algo ya contado). Antes del corte\n"
    "\nPAGOS\n"
    "/pagos — a quién le toca cobrar y cuánto\n"
    "/pagar Fanny — el desglose; con «si» al final se registra\n"
    "/deshacerpago — deshace el último pago\n"
    "/prestamos — los préstamos que te pidieron, para aprobar o rechazar\n"
    "/descansos — los días que te pidieron, con cómo queda la semana\n"
    "/sonidos — los sonidos que puede hacer un aviso\n"
    "\nLA TIENDA\n"
    "/prenda playera justo sierra — precio y cuántas hay por talla\n"
    "/escuela conalep — cómo va esa escuela\n"
    "/contar — qué falta contar, lo más urgente primero\n"
    "/faltas — lo que pidieron y no había\n"
    "\nLAS PANTALLAS\n"
    "/aviso Junta a las 6 — sale a pantalla completa en la tienda\n"
    "/aviso 3h Hoy cerramos temprano — y se quita solo en 3 horas\n"
    "/aviso @caja2 Ven un momento — solo en esa pantalla\n"
    "/cartel Promoción de mochilas — rota sin interrumpir a nadie\n"
    "Mándame una foto y sale a pantalla completa (el pie de foto es el aviso)\n"
    "/avisos — los que están puestos, quién los vio, y quitarlos\n"
    "\nGENTE\n"
    "/asistencia — quién vino hoy, con un comando por empleada para marcar\n"
    "/falta_Fanny · /descanso_Fanny · /vino_Fanny — o con espacio: /falta Fanny\n"
    "\n/menu — los botones, para no acordarse de nada\n"
    "/ayuda — esta lista"
)


@dataclass(frozen=True)
class Comando:
    nombre: str
    argumento: str = ""


def parsear(texto: str) -> Comando | None:
    t = (texto or "").strip()
    if not t.startswith("/"):
        return None
    partes = t[1:].split(maxsplit=1)
    nombre = partes[0].split("@")[0].lower()
    argumento = partes[1].strip() if len(partes) > 1 else ""
    # "/falta_Fanny" (tocable en Telegram, una sola palabra) = "/falta Fanny".
    for base in ("falta", "descanso", "vino"):
        if nombre.startswith(base + "_") and len(nombre) > len(base) + 1:
            return Comando(base, (partes[0].split("@")[0][len(base) + 1:] + " " + argumento).strip())
    return Comando(nombre, argumento)


@dataclass(frozen=True)
class OpcionesCorte:
    """Lo que trae `/corte`. Son los mismos campos del diálogo del kiosko.

    `nota` se queda con lo que no es ninguna otra cosa: así `/corte 5000
    deposité al banco` guarda el motivo sin pedir una palabra clave más. Un
    corte sin explicación es el hueco que ya se tapó al ajustar; hacerlo de
    lejos no tenía por qué ser la excepción.
    """

    retirar: Decimal | None = None
    #: None = "como lo tengas guardado"; True/False = lo dijiste en el comando.
    #: Antes era un bool y su default (False) pisaba la preferencia del dueño,
    #: así que el celular enseñaba las tarjetas aunque el kiosko estuviera en
    #: ocultar (Daniel, 2026-10-07).
    sin_tarjeta: bool | None = None
    fondo: Decimal | None = None
    otros: Decimal | None = None
    nota: str = ""
    #: Lo que hay que decirle aunque el corte se haya hecho. Hoy solo una cosa:
    #: la nota menciona las tarjetas y nadie pidió ocultarlas, así que lo más
    #: probable es que la opción se escribiera mal y se haya guardado como
    #: recado — que es justo lo que pasó el 6-oct y no dio señal ninguna.
    aviso: str = ""


_SIN_TARJETA = {"sintarjeta", "sin-tarjeta", "sin_tarjeta", "st"}
#: Lo contrario, para un día suelto: «/corte contarjeta».
_CON_TARJETA = {"contarjeta", "con-tarjeta", "con_tarjeta", "contarjetas"}
#: «sin tarjeta» escrito con espacio: dos palabras que juntas son la opción.
#: Daniel lo escribió así el 6-oct, se guardó como NOTA y el corte salió con
#: las tarjetas — un dedazo que se veía igual que una decisión.
_PARTIDAS = {("sin", "tarjeta"), ("sin", "tarjetas"), ("con", "tarjeta"), ("con", "tarjetas")}
#: Palabras que presentan una cifra. Lo demás que no sea número es nota.
_FONDO = {"fondo", "reactivo"}
_OTROS = {"otros", "otro", "salida", "salidas", "gasto"}

_AYUDA_CORTE = (
    "Se usa así:\n"
    "/corte — con la cifra calculada\n"
    "/corte 5000 — se retiran $5,000\n"
    "/corte fondo 2000 — deja ese fondo en el cajón\n"
    "/corte otros 350 — descuenta una salida no apuntada\n"
    "/corte sintarjeta — sin los cobros con tarjeta\n"
    "/corte contarjeta — con ellos, aunque los tengas ocultos por default\n"
    "/corte 5000 deposité al banco — lo demás queda como nota\n"
    "(se pueden juntar: /corte 5000 fondo 2000 deposité al banco)"
)


def _cifra(palabra: str) -> Decimal | None:
    """'$5,000.50' → Decimal. None si no es un número."""
    crudo = palabra.strip().lower().replace("$", "").replace(",", "").replace("_", "")
    try:
        return Decimal(crudo).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def leer_opciones_corte(argumento: str) -> OpcionesCorte:
    """'5000 fondo 2000 deposité al banco' → todo lo del diálogo, en una línea."""
    retirar = fondo = otros = None
    sin_tarjeta: bool | None = None
    nota: list[str] = []

    palabras = (argumento or "").split()
    i = 0
    while i < len(palabras):
        palabra = palabras[i]
        limpia = palabra.strip().lower()
        siguiente_limpia = (
            palabras[i + 1].strip().lower() if i + 1 < len(palabras) else ""
        )
        if (limpia, siguiente_limpia) in _PARTIDAS:
            sin_tarjeta = limpia == "sin"
            i += 2
            continue
        if limpia in _SIN_TARJETA:
            sin_tarjeta = True
            i += 1
            continue
        if limpia in _CON_TARJETA:
            sin_tarjeta = False
            i += 1
            continue
        if limpia in _FONDO or limpia in _OTROS:
            siguiente = _cifra(palabras[i + 1]) if i + 1 < len(palabras) else None
            if siguiente is None:
                raise ValueError(f"Después de «{palabra}» falta la cantidad.\n\n" + _AYUDA_CORTE)
            if siguiente < 0:
                raise ValueError("Una cantidad no puede ser negativa.")
            if limpia in _FONDO:
                fondo = siguiente
            else:
                otros = siguiente
            i += 2
            continue
        valor = _cifra(palabra)
        if valor is not None and not nota:
            # La cifra suelta es lo que se retira, y solo si todavía no empezó
            # la nota: en «5000 deposité 2 cajas» el 2 es parte del recado.
            if valor < 0:
                raise ValueError("Lo que se retira no puede ser negativo.")
            retirar = valor
            i += 1
            continue
        nota.append(palabra)
        i += 1

    texto_nota = " ".join(nota).strip()
    aviso = ""
    if sin_tarjeta is None and "tarjet" in texto_nota.lower():
        aviso = (
            f"Ojo: «{texto_nota}» se guardó como NOTA, no como opción. "
            "Si querías esconder los cobros con tarjeta, se escribe "
            "«sintarjeta» (o «sin tarjeta»)."
        )
    return OpcionesCorte(
        retirar=retirar, sin_tarjeta=sin_tarjeta, fondo=fondo, otros=otros,
        nota=texto_nota, aviso=aviso,
    )


def atender_texto(texto: str, *, session_factory, hoy: date | None = None) -> str:
    """Devuelve la respuesta para un mensaje. `session_factory()` abre sesión."""
    cmd = parsear(texto)
    if cmd is None:
        return "No entendí. " + AYUDA
    if cmd.nombre in ("ayuda", "help", "start"):
        return AYUDA
    if cmd.nombre == "corte":
        from pos_uniformes.services.corte_remoto_service import hacer_corte_y_avisar

        try:
            opciones = leer_opciones_corte(cmd.argumento)
        except ValueError as exc:
            return str(exc)
        with session_factory() as session:
            mensaje = hacer_corte_y_avisar(
                session, creado_por=CODIGO_REMOTO,
                retirar=opciones.retirar, sin_tarjeta=opciones.sin_tarjeta,
                fondo=opciones.fondo, otros=opciones.otros, nota=opciones.nota,
            ).mensaje
        # El aviso va DESPUÉS y no cancela nada: el corte ya se hizo y hay que
        # decir lo que se guardó, no tragárselo.
        return mensaje + ("\n\n⚠️ " + opciones.aviso if opciones.aviso else "")
    if cmd.nombre == "nocorte":
        from pos_uniformes.services.corte_propuesta_service import cancelar

        if cancelar(hoy):
            return "Ok, hoy no se hace el corte. Cuando quieras, /corte."
        return "No hay ningún corte propuesto hoy. Si lo quieres hacer, /corte."
    if cmd.nombre == "estado":
        from pos_uniformes.services.corte_remoto_service import texto_estado_actual

        with session_factory() as session:
            return texto_estado_actual(session)
    if cmd.nombre == "resumen":
        from pos_uniformes.services.resumen_diario_service import formatear, recolectar

        with session_factory() as session:
            return formatear(recolectar(session, hoy))
    if cmd.nombre == "hoy":
        from pos_uniformes.services import asistencia_service as asis
        from pos_uniformes.services.resumen_diario_service import recolectar, texto_hoy

        with session_factory() as session:
            datos = recolectar(session, hoy)
            estan = [
                a.nombre for a in asis.asistencia_del_dia(session, hoy)
                if a.estado == asis.PRESENTE
            ]
            texto = texto_hoy(datos, quien_esta=estan)
            try:
                from pos_uniformes.services import comparativa_service as comp

                linea = comp.texto(comp.comparar(session, hoy))
            except Exception:  # noqa: BLE001 — el día sale igual sin comparación
                linea = ""
            return texto + (f"\n\n{linea}" if linea else "")
    if cmd.nombre in ("pulso", "pulse", "todo"):
        from pos_uniformes.services.telegram_pulso_service import pulso

        with session_factory() as session:
            return pulso(session, hoy=hoy)
    if cmd.nombre == "pendientes":
        from pos_uniformes.services.resumen_diario_service import texto_solo_pendientes

        with session_factory() as session:
            return texto_solo_pendientes(session, hoy) or "Sin pendientes. ✅"
    if cmd.nombre == "asistencia":
        with session_factory() as session:
            return mensaje_asistencia(session, hoy)[0]
    if cmd.nombre in ("menu", "menú"):
        from pos_uniformes.services import telegram_menu_service as menu

        with session_factory() as session:
            return menu.menu_raiz(session, hoy=hoy)[0]
    if cmd.nombre in ("prestamos", "préstamos"):
        from pos_uniformes.services import telegram_prestamos_service as prs

        with session_factory() as session:
            return prs.texto_y_botones(session)[0]
    if cmd.nombre == "aviso":
        from pos_uniformes.services import telegram_avisos_service as av

        with session_factory() as session:
            return av.mandar(session, cmd.argumento, quien=CODIGO_REMOTO)
    if cmd.nombre in ("cartel", "cartelera"):
        from pos_uniformes.services import telegram_avisos_service as av

        with session_factory() as session:
            return av.mandar(
                session, cmd.argumento, quien=CODIGO_REMOTO, interrumpe=False
            )
    if cmd.nombre == "avisos":
        from pos_uniformes.services import telegram_avisos_service as av

        with session_factory() as session:
            return av.resumen(session)
    if cmd.nombre in ("cajon", "cajón"):
        from pos_uniformes.services import telegram_cajon_service as cj

        with session_factory() as session:
            return cj.texto_y_botones(session)[0]
    if cmd.nombre == "cortes":
        from pos_uniformes.services import telegram_cortes_service as ct

        with session_factory() as session:
            return ct.resumen(session, dias=ct.dias_de_argumento(cmd.argumento))
    if cmd.nombre == "ajustar":
        from pos_uniformes.services import telegram_cortes_service as ct

        with session_factory() as session:
            return ct.ajustar(session, cmd.argumento, quien=CODIGO_REMOTO)
    if cmd.nombre in ("sintarjeta", "sin-tarjeta", "sin_tarjeta"):
        from pos_uniformes.services import telegram_cortes_service as ct

        with session_factory() as session:
            return ct.esconder_tarjetas(session, cmd.argumento, quien=CODIGO_REMOTO)
    if cmd.nombre in ("sonidos", "sonido"):
        from pos_uniformes.services import sonidos_service as sn

        nombres = sn.nombres()
        if not nombres:
            return (
                "No hay sonidos todavía.\n\n"
                "Se ponen como archivos .wav en pos_uniformes\\assets\\sonidos "
                "y entran a los kioskos con actualizar_pc_principal.bat."
            )
        lista = "\n".join(f"· sonido={n}" for n in nombres)
        return f"🔊 Sonidos que puedo poner en un aviso:\n\n{lista}\n\nEjemplo:\n/aviso sonido={nombres[0]} 🤡 Te veo..."
    if cmd.nombre == "descansos":
        from pos_uniformes.services import telegram_descansos_service as dsc

        with session_factory() as session:
            return dsc.texto_y_botones(session, hoy=hoy)[0]
    if cmd.nombre == "pagos":
        from pos_uniformes.services import telegram_pagos_service as pg

        with session_factory() as session:
            return pg.pagos(session, hoy=hoy)
    if cmd.nombre == "pagar":
        from pos_uniformes.services import telegram_pagos_service as pg

        with session_factory() as session:
            return pg.pagar(session, cmd.argumento, quien=CODIGO_REMOTO, hoy=hoy)
    if cmd.nombre == "retiro":
        from pos_uniformes.services import telegram_pagos_service as pg

        with session_factory() as session:
            return pg.retiro(session, cmd.argumento, quien=CODIGO_REMOTO)
    if cmd.nombre in ("deshacerpago", "deshacer_pago"):
        from pos_uniformes.services import telegram_pagos_service as pg

        with session_factory() as session:
            return pg.deshacer_pago(session, quien=CODIGO_REMOTO)
    if cmd.nombre in ("prenda", "precio"):
        from pos_uniformes.services import telegram_inventario_service as inv

        with session_factory() as session:
            return inv.prenda(session, cmd.argumento)
    if cmd.nombre == "contar":
        from pos_uniformes.services import telegram_inventario_service as inv

        with session_factory() as session:
            return inv.contar(session)
    if cmd.nombre == "escuela":
        from pos_uniformes.services import telegram_inventario_service as inv

        with session_factory() as session:
            return inv.escuela(session, cmd.argumento)
    if cmd.nombre == "faltas":
        from pos_uniformes.services import telegram_inventario_service as inv

        with session_factory() as session:
            return inv.faltas(session, hoy=hoy)
    if cmd.nombre in ("vino", "falta", "descanso"):
        from pos_uniformes.services import asistencia_service as asis

        accion = {"vino": asis.VINO, "falta": asis.NO_VINO, "descanso": asis.DESCANSA}[cmd.nombre]
        with session_factory() as session:
            code = asis.buscar_code(session, cmd.argumento)
            if code is None:
                return f"¿Quién? Escribe el nombre como aparece en la lista: /{cmd.nombre} Fanny"
            hecho = asis.marcar(session, code, accion, hoy)
            return hecho + "\n\n" + mensaje_asistencia(session, hoy)[0]
    return f"No conozco /{cmd.nombre}. " + AYUDA


#: Comandos cuya respuesta lleva botones. Sin esto, `/avisos` decía «toca uno
#: para quitarlo» y mandaba el texto pelón: no había nada que tocar, y había
#: que acordarse de entrar por el menú — justo lo que el menú vino a evitar.
_CON_BOTONES = {
    "avisos": ("pos_uniformes.services.telegram_avisos_service", "texto_y_botones"),
    "cajon": ("pos_uniformes.services.telegram_cajon_service", "texto_y_botones"),
    "cortes": ("pos_uniformes.services.telegram_cortes_service", "texto_y_botones"),
    "cajón": ("pos_uniformes.services.telegram_cajon_service", "texto_y_botones"),
    "prestamos": ("pos_uniformes.services.telegram_prestamos_service", "texto_y_botones"),
    "descansos": ("pos_uniformes.services.telegram_descansos_service", "texto_y_botones"),
    "préstamos": ("pos_uniformes.services.telegram_prestamos_service", "texto_y_botones"),
    "menu": ("pos_uniformes.services.telegram_menu_service", "menu_raiz"),
    "menú": ("pos_uniformes.services.telegram_menu_service", "menu_raiz"),
}


def responder(texto: str, *, session_factory, hoy: date | None = None) -> tuple[str, str]:
    """(respuesta, botones) para un mensaje. Es lo que usa el bucle del bot.

    `atender_texto` sigue devolviendo solo texto porque así se usa en mil
    lados; aquí se le agregan los botones a los pocos comandos que los tienen.
    """
    cmd = parsear(texto)
    destino = _CON_BOTONES.get(cmd.nombre) if cmd is not None else None
    if destino is None:
        return atender_texto(texto, session_factory=session_factory, hoy=hoy), ""
    modulo, funcion = destino
    try:
        import importlib

        hacer = getattr(importlib.import_module(modulo), funcion)
        # Si la función sabe recibir el argumento, se le pasa: sin esto
        # `/cortes 30` contestaba con los botones pero con los 14 días de
        # siempre, callado, que es la peor forma de ignorar algo.
        import inspect

        extra = {}
        if "argumento" in inspect.signature(hacer).parameters:
            extra["argumento"] = cmd.argumento
        with session_factory() as session:
            return hacer(session, **extra)
    except Exception:  # noqa: BLE001 — sin botones se contesta igual
        logger.exception("No se pudieron armar los botones de /%s", cmd.nombre)
        return atender_texto(texto, session_factory=session_factory, hoy=hoy), ""


def atender_foto(msg: dict, *, session_factory, token: str | None = None) -> str | None:
    """Una foto mandada al bot → aviso a pantalla completa. None si no hay foto.

    El pie de foto es el aviso, y ahí valen el plazo y la `@pantalla` igual que
    en `/aviso`. Mandar una foto es el gesto más corto que hay para poner algo
    en las pantallas, así que no lleva comando.
    """
    from pos_uniformes.services import telegram_service

    file_id = telegram_service.foto_mas_grande(msg)
    if not file_id:
        return None
    pie = (msg.get("caption") or "").strip()
    # Un pie que empieza con otro comando no es un aviso: se atiende como texto.
    if pie.startswith("/") and not pie.lower().startswith(("/aviso", "/cartel")):
        return atender_texto(pie, session_factory=session_factory)
    interrumpe = True
    if pie.lower().startswith("/cartel"):
        interrumpe = False
        pie = pie.split(maxsplit=1)[1].strip() if " " in pie else ""
    elif pie.lower().startswith("/aviso"):
        pie = pie.split(maxsplit=1)[1].strip() if " " in pie else ""

    from pos_uniformes.services import telegram_avisos_service as av

    with session_factory() as session:
        return av.mandar_foto(
            session, file_id=file_id, pie=pie, quien=CODIGO_REMOTO,
            token=token, interrumpe=interrumpe,
        )


def mensaje_asistencia(session, hoy: date | None = None) -> tuple[str, str]:
    """(texto, botones JSON) de la lista de asistencia de hoy.

    Los botones quedaron en desuso (Daniel prefiere los comandos tocables
    que van en el propio texto: /falta_Fanny, /descanso_Fanny); se devuelve
    "" para no mandarlos. La infraestructura de toques sigue viva por si
    vuelve a hacer falta."""
    from pos_uniformes.services import asistencia_service as asis

    lista = asis.asistencia_del_dia(session, hoy)
    return asis.texto_asistencia(lista, hoy), ""


def atender_toque(dato: str, *, session_factory, hoy: date | None = None) -> tuple[str, str, str] | None:
    """Un botón tocado: (aviso corto, texto nuevo, botones nuevos).

    Puede ser del menú (`m:…`) o de la lista de asistencia. None si no es de
    ninguno de los dos."""
    from pos_uniformes.services import asistencia_service as asis
    from pos_uniformes.services import telegram_menu_service as menu

    if menu.es_del_menu(dato):
        return menu.atender(dato, session_factory=session_factory, hoy=hoy)

    from pos_uniformes.services import telegram_avisos_service as av

    if av.es_de_avisos(dato):
        return av.atender(dato, session_factory=session_factory)

    from pos_uniformes.services import telegram_cajon_service as cj

    if cj.es_del_cajon(dato):
        return cj.atender(dato, session_factory=session_factory)

    from pos_uniformes.services import telegram_cortes_service as ct

    if ct.es_de_cortes(dato):
        return ct.atender(dato, session_factory=session_factory, quien=CODIGO_REMOTO)

    from pos_uniformes.services import telegram_corte_botones_service as cb

    if cb.es_de_corte(dato):
        return cb.atender(dato, session_factory=session_factory, quien=CODIGO_REMOTO)

    from pos_uniformes.services import telegram_prestamos_service as prs

    if prs.es_de_prestamos(dato):
        return prs.atender(dato, session_factory=session_factory, quien=CODIGO_REMOTO)

    from pos_uniformes.services import telegram_descansos_service as dsc

    if dsc.es_de_descansos(dato):
        return dsc.atender(dato, session_factory=session_factory, quien=CODIGO_REMOTO)

    toque = asis.interpretar_toque(dato)
    if toque is None:
        return None
    code, accion = toque
    with session_factory() as session:
        aviso = asis.marcar(session, code, accion, hoy)
        texto, botones = mensaje_asistencia(session, hoy)
    return aviso, texto, botones


MAX_ANTIGUEDAD_SEG = 10 * 60  # mensajes más viejos (bot apagado) no se ejecutan


def _es_viejo(msg: dict, ahora: float | None = None) -> bool:
    """Un /corte mandado ayer, con el bot apagado, no debe ejecutarse hoy."""
    try:
        fecha = float(msg.get("date") or 0)
    except (TypeError, ValueError):
        return False
    if not fecha:
        return False
    return ((ahora if ahora is not None else time.time()) - fecha) > MAX_ANTIGUEDAD_SEG


ESPERA_GETUPDATES_SEG = 25  # una vuelta cada ~25 s: alertas casi al momento y pocas consultas


def escuchar(*, session_factory, token: str, chat_id: str, una_vez: bool = False, alertas: bool = True, on_tick=None) -> None:
    """Long-polling: atiende mensajes del chat autorizado hasta que lo paren.
    En cada vuelta también manda las alertas encoladas (cortes, retiros) y
    lo que vea el vigilante (cierre sin corte, movimientos fuera de horario)."""
    from pos_uniformes.services import telegram_service
    from pos_uniformes.services.alertas_service import Vigilante, procesar

    offset = None
    vigilante = Vigilante() if alertas else None
    logger.info("Bot escuchando (chat %s)…", chat_id)
    try:
        asegurar_menu_fijado(session_factory=session_factory, token=token, chat_id=chat_id)
    except Exception:  # noqa: BLE001 — sin menú fijado, el bot funciona igual
        logger.exception("No se pudo dejar el menú fijado")

    def _mandar(texto: str) -> None:
        telegram_service.enviar_mensaje(texto, token=token, chat_id=chat_id)

    while True:
        if on_tick is not None:
            try:
                on_tick()  # latido: el vigía sabe que seguimos vivos
            except Exception:  # noqa: BLE001
                pass
        if alertas:
            procesar(session_factory, _mandar, vigilante)
        try:
            barrer_si_toca(token=token, chat_id=chat_id)
        except Exception:  # noqa: BLE001 — la limpieza nunca tumba el bot
            logger.exception("Falló el barrido de mensajes")
        try:
            datos = {"timeout": ESPERA_GETUPDATES_SEG}
            if offset is not None:
                datos["offset"] = offset
            payload = telegram_service._llamar(token, "getUpdates", datos, timeout=ESPERA_GETUPDATES_SEG + 15)
        except Exception as exc:  # noqa: BLE001
            logger.warning("getUpdates falló: %s", exc)
            # Se anota el hueco: el bot no puede avisar mientras está
            # incomunicado —esa es la falla— pero sí contarlo al volver.
            try:
                from pos_uniformes.services import bot_conexion_service as conexion

                conexion.anotar_fallo()
            except Exception:  # noqa: BLE001 — llevar la cuenta no tumba el bot
                pass
            time.sleep(10)
            if una_vez:
                return
            continue
        try:
            from pos_uniformes.services import bot_conexion_service as conexion

            de_regreso = conexion.anotar_ok()
            if de_regreso:
                _mandar(de_regreso)
        except Exception:  # noqa: BLE001
            logger.exception("No se pudo contar el hueco de conexión")
        for upd in payload.get("result", []):
            offset = int(upd["update_id"]) + 1
            toque = upd.get("callback_query")
            if toque:
                _atender_toque(toque, session_factory=session_factory, token=token, chat_id=chat_id)
                continue
            msg = upd.get("message") or {}
            chat = str((msg.get("chat") or {}).get("id", ""))
            texto = msg.get("text") or ""
            if chat != str(chat_id):
                logger.info("Mensaje ignorado de chat %s", chat)
                continue
            trae_foto = bool(telegram_service.foto_mas_grande(msg))
            botones = ""
            if _es_viejo(msg):
                logger.info("Mensaje viejo ignorado: %r", texto)
                if trae_foto:
                    respuesta = (
                        "Ya estoy en línea. No puse esa foto porque es de antes de "
                        "arrancar; si todavía la quieres en las pantallas, mándala otra vez."
                    )
                else:
                    respuesta = (
                        f"Ya estoy en línea. No atendí «{texto[:40]}» porque es de antes de arrancar; "
                        "si todavía lo quieres, mándalo otra vez."
                    ) if parsear(texto) else ""
                if not respuesta:
                    continue
            else:
                try:
                    if trae_foto:
                        respuesta = atender_foto(
                            msg, session_factory=session_factory, token=token
                        ) or ""
                    else:
                        respuesta, botones = responder(
                            texto, session_factory=session_factory
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Error atendiendo %r", texto)
                    respuesta = f"Falló: {exc}"
                if not respuesta:
                    continue
            try:
                telegram_service.enviar_mensaje(
                    respuesta, token=token, chat_id=chat_id, botones=botones or None
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo responder: %s", exc)
        if una_vez:
            return


def _atender_toque(toque: dict, *, session_factory, token: str, chat_id: str) -> None:
    """Un botón tocado en el celular: marca, avisa y reescribe la lista en el
    mismo mensaje. Solo del chat autorizado."""
    from pos_uniformes.services import telegram_service

    msg = toque.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    if chat != str(chat_id):
        logger.info("Toque ignorado de chat %s", chat)
        return
    dato = str(toque.get("data") or "")
    try:
        resultado = atender_toque(dato, session_factory=session_factory)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error atendiendo el toque %r", dato)
        resultado = (f"Falló: {exc}", "", "")
    try:
        telegram_service.responder_toque(str(toque.get("id", "")), resultado[0] if resultado else "", token=token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo responder el toque: %s", exc)
    if resultado and resultado[1] and msg.get("message_id") is not None:
        tocado = int(msg["message_id"])
        try:
            from pos_uniformes.services import telegram_limpieza_service as limpieza

            es_el_menu = tocado == limpieza.menu_fijado()
        except Exception:  # noqa: BLE001
            es_el_menu = False
        if es_el_menu:
            # El menú fijado se queda siendo el menú. Si se reescribiera, al
            # primer toque el tablero de arriba se convertiría en una lista de
            # cortes y ya no habría de dónde salir (2026-10-08).
            try:
                telegram_service.enviar_mensaje(
                    resultado[1], token=token, chat_id=chat_id, botones=resultado[2] or None
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo responder al menú: %s", exc)
            return
        try:
            telegram_service.editar_mensaje(
                tocado, resultado[1], token=token, chat_id=chat_id, botones=resultado[2]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo actualizar la lista: %s", exc)


def asegurar_menu_fijado(*, session_factory, token: str, chat_id: str) -> int:
    """Deja un menú fijado arriba del chat. Devuelve su id (0 si no se pudo).

    La primera vez lo manda y lo fija; después solo lo reescribe, porque
    mandar uno nuevo cada arranque dejaría el chat lleno de menús viejos
    —justo lo que se quiere evitar— y además desfijaría el anterior.
    """
    from pos_uniformes.services import telegram_limpieza_service as limpieza
    from pos_uniformes.services import telegram_menu_service as menu
    from pos_uniformes.services import telegram_service

    try:
        with session_factory() as session:
            texto, botones = menu.menu_raiz(session)
    except Exception:  # noqa: BLE001 — sin base, el menú sin el día puesto
        texto, botones = menu.menu_raiz()

    fijado = limpieza.menu_fijado()
    if fijado:
        try:
            telegram_service.editar_mensaje(
                fijado, texto, token=token, chat_id=chat_id, botones=botones
            )
            return fijado
        except Exception as exc:  # noqa: BLE001
            # Lo borró a mano, o es de hace mucho: se manda uno nuevo.
            logger.info("El menú fijado ya no se puede reescribir (%s)", exc)

    try:
        respuesta = telegram_service._llamar(token, "sendMessage", {
            "chat_id": chat_id, "text": texto, "reply_markup": botones,
            "disable_web_page_preview": "true",
        })
        mid = int((respuesta.get("result") or {}).get("message_id") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo mandar el menú: %s", exc)
        return 0
    if mid:
        limpieza.recordar_menu(mid)
        telegram_service.fijar_mensaje(mid, token=token, chat_id=chat_id)
    return mid


def barrer_si_toca(*, token: str, chat_id: str) -> int:
    """Borra los mensajes del bot que ya cumplieron 24 horas.

    Se llama en cada vuelta del long-polling, pero el servicio decide cuándo
    de verdad toca: barrer cada 25 segundos sería una llamada por mensaje para
    nada."""
    from pos_uniformes.services import telegram_limpieza_service as limpieza
    from pos_uniformes.services import telegram_service

    if not limpieza.toca_barrer():
        return 0
    return limpieza.barrer(
        borrar=lambda mid: telegram_service.borrar_mensaje(
            mid, token=token, chat_id=chat_id
        )
    )
