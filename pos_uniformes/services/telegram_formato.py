"""El formato común de los mensajes del bot (Daniel, 2026-11-20: «Sí, en todos»).

Todos los mensajes se leen igual, de un vistazo en el celular:

    🧾 CORTE DE CAJA · vie 20 nov · 18:45     ← encabezado: emoji, título, cuándo
    💰 $12,345.00 en efectivo                 ← la cifra que importa, arriba

    Pagos $800.00 · retiros $200.00           ← el detalle
    Reactivo queda $1,500.00

y lo que se puede hacer va en botones, no en comandos que haya que escribir.

Texto plano (el bot no usa parse_mode): el título va en MAYÚSCULAS para que
se lea como título sin asteriscos. Funciones puras: no tocan la base ni la red.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

def _hoy() -> date:
    """El día de referencia para decidir si una fecha lleva año. Las pruebas
    lo fijan (conftest) para que no cambien de resultado al cambiar el año."""
    return date.today()


#: Separa el encabezado (y la cifra) del detalle.
SALTO = "\n\n"


def fecha_corta(cuando: date | datetime) -> str:
    """«vie 20 nov». El año solo si no es el de hoy («mié 9 sep 2025»): un
    corte viejo de /cortes no debe parecer de este año."""
    texto = f"{DIAS[cuando.weekday()]} {cuando.day} {MESES[cuando.month - 1]}"
    return texto if cuando.year == _hoy().year else f"{texto} {cuando.year}"


def dinero(monto) -> str:
    """«$12,345.00» (con «−» si es negativo)."""
    valor = Decimal(str(monto or 0)).quantize(Decimal("0.01"))
    signo = "−" if valor < 0 else ""
    return f"{signo}${abs(valor):,.2f}"


def encabezado(emoji: str, titulo: str, cuando: date | datetime | None = None, *,
               hora: bool = False) -> str:
    """«🧾 CORTE DE CAJA · vie 20 nov · 18:45». `cuando=None`: sin fecha (un
    menú o una ayuda). `hora`: solo si `cuando` es un datetime."""
    partes = [f"{emoji} {titulo.strip().upper()}".strip()]
    if cuando is not None:
        partes.append(fecha_corta(cuando))
        if hora and isinstance(cuando, datetime):
            partes.append(cuando.strftime("%H:%M"))
    return " · ".join(partes)


def cifra(monto, etiqueta: str = "", *, emoji: str = "💰") -> str:
    """La cifra principal: «💰 $12,345.00 en efectivo»."""
    texto = f"{emoji} {dinero(monto)}"
    return f"{texto} {etiqueta.strip()}" if etiqueta.strip() else texto


def mensaje(emoji: str, titulo: str, *, cuando: date | datetime | None = None,
            hora: bool = False, principal: str = "", detalle=(), pie: str = "") -> str:
    """Arma un mensaje completo.

    `principal`: la línea que importa (una `cifra(...)` o una frase corta);
    va pegada al encabezado. `detalle`: líneas (las vacías se saltan; un
    texto ya armado también sirve). `pie`: una nota al final, separada.
    """
    arriba = encabezado(emoji, titulo, cuando, hora=hora)
    if principal.strip():
        arriba += "\n" + principal.strip()
    if isinstance(detalle, str):
        cuerpo = detalle.strip()
    else:
        cuerpo = "\n".join(str(l) for l in detalle if str(l).strip())
    bloques = [arriba]
    if cuerpo:
        bloques.append(cuerpo)
    if pie.strip():
        bloques.append(pie.strip())
    return SALTO.join(bloques)


def quitar_encabezado(texto: str) -> str:
    """El mensaje sin su primera línea si es un encabezado: para pegar una
    lista debajo de otro mensaje sin repetir encabezado (2026-11-20)."""
    texto = (texto or "").strip()
    primera, _, resto = texto.partition("\n")
    return resto.strip() if es_encabezado(primera) else texto


def es_encabezado(linea: str) -> bool:
    """¿La línea ya es un encabezado de este formato? (para las pruebas)."""
    linea = (linea or "").strip()
    if " " not in linea:
        return False
    emoji, resto = linea.split(" ", 1)
    titulo = resto.split(" · ", 1)[0]
    return not emoji.isalnum() and titulo == titulo.upper() and any(c.isalpha() for c in titulo)
