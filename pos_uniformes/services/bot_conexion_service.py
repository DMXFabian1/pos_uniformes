"""El bot lleva cuenta de cuándo no pudo hablar, y lo dice al volver.

El 02/10 la PC de la tienda se quedó sin salida a internet y el bot llevaba
horas muerto: sin resumen, sin alertas, sin `/corte`. Daniel se enteró **por
accidente**, porque intentó actualizar. Con él fuera una semana, eso se habría
visto exactamente igual que una tienda tranquila.

El bot no puede avisar mientras está incomunicado — esa es justo la falla. Lo
que sí puede es **anotar el hueco** y contarlo apenas recupera la línea, para
que el silencio no pase por normalidad.

Qué cuenta como hueco, a propósito:

- Solo cuando una consulta a Telegram **falla**. Es decir, el bot estaba vivo y
  no alcanzaba la red.
- **No** cuenta la noche. Si la PC se apaga al cerrar, ninguna consulta falla y
  no hay nada que reportar; avisar «estuve 15 h callado» cada mañana sería
  ruido, y el ruido se ignora — que es como se pierde el aviso que sí importa.

El estado vive en un JSON local porque tiene que sobrevivir a que el supervisor
reinicie el bot: si se cayó a las 9 y el proceso se reinició a las 11, el hueco
sigue siendo de dos horas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

#: Un sondeo suelto que falla no es un apagón: la red parpadea. Por debajo de
#: esto no se dice nada.
MINIMO_PARA_AVISAR = timedelta(minutes=5)

_ARCHIVO = "bot_conexion.json"


def ruta_estado() -> Path:
    from pos_uniformes.utils.config import runtime_base_dir

    return runtime_base_dir() / "data" / _ARCHIVO


@dataclass(frozen=True)
class Estado:
    caido_desde: datetime | None = None
    ultimo_ok: datetime | None = None


def _leer() -> Estado:
    try:
        datos = json.loads(ruta_estado().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — sin archivo o ilegible: como si nada
        return Estado()
    return Estado(caido_desde=_fecha(datos.get("caido_desde")), ultimo_ok=_fecha(datos.get("ultimo_ok")))


def _fecha(valor) -> datetime | None:
    try:
        momento = datetime.fromisoformat(str(valor))
    except (TypeError, ValueError):
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _guardar(estado: Estado) -> None:
    ruta = ruta_estado()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(
                {
                    "caido_desde": estado.caido_desde.isoformat() if estado.caido_desde else None,
                    "ultimo_ok": estado.ultimo_ok.isoformat() if estado.ultimo_ok else None,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:  # noqa: BLE001 — llevar la cuenta jamás puede tumbar el bot
        pass


def anotar_fallo(ahora: datetime | None = None) -> None:
    """Una consulta a Telegram no pasó. Marca el inicio del hueco si es el primero."""
    ahora = ahora or datetime.now(timezone.utc)
    estado = _leer()
    if estado.caido_desde is not None:
        return  # ya veníamos caídos: el hueco empezó antes
    _guardar(Estado(caido_desde=ahora, ultimo_ok=estado.ultimo_ok))


def anotar_ok(ahora: datetime | None = None) -> str | None:
    """Volvió la línea. Devuelve el mensaje del hueco, o None si no hay qué contar."""
    ahora = ahora or datetime.now(timezone.utc)
    estado = _leer()
    _guardar(Estado(caido_desde=None, ultimo_ok=ahora))
    if estado.caido_desde is None:
        return None
    hueco = ahora - estado.caido_desde
    if hueco < MINIMO_PARA_AVISAR:
        return None
    return texto_del_hueco(estado.caido_desde, ahora)


def _local(momento: datetime) -> datetime:
    return momento.astimezone()


def duracion_legible(hueco: timedelta) -> str:
    """'1 h 20 min', '45 min', '2 días'. Para leerlo de un vistazo."""
    seg = int(max(0, hueco.total_seconds()))
    if seg < 3600:
        return f"{max(1, seg // 60)} min"
    if seg < 86400:
        horas, resto = divmod(seg, 3600)
        minutos = resto // 60
        return f"{horas} h" + (f" {minutos} min" if minutos else "")
    dias = seg // 86400
    return "1 día" if dias == 1 else f"{dias} días"


def texto_del_hueco(desde: datetime, hasta: datetime) -> str:
    """Lo que se le manda a Daniel cuando el bot recupera la línea."""
    d, h = _local(desde), _local(hasta)
    mismo_dia = d.date() == h.date()
    rango = (
        f"de las {d:%H:%M} a las {h:%H:%M}"
        if mismo_dia
        else f"desde el {d:%d/%m} a las {d:%H:%M} hasta hoy {h:%H:%M}"
    )
    return (
        f"📡 Volví a tener línea.\n\n"
        f"Estuve {duracion_legible(hasta - desde)} sin poder hablar, {rango}.\n"
        "En ese rato no te llegó nada: ni resumen, ni alertas, ni los avisos de "
        "préstamos o gastos.\n\n"
        "Lo que quedó en cola ya te va llegando. Para ver qué pasó mientras:\n"
        "/hoy · /cortes · /prestamos"
    )
