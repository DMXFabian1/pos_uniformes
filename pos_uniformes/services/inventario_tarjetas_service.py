"""Tarjetas que filtran y «Para atender» de la pestaña Inventario (tanda 3).

Reglas puras, sin Qt ni base: reciben las filas del snapshot de Inventario
(las mismas de la tabla) y deciden qué talla cae en cada tarjeta.

Las cuatro tarjetas:
- «En negativo»: el total es menor que 0 (se vendió sin haberse contado).
- «Se acabó»: el total es exactamente 0.
- «Quedan pocas»: de 1 a `UMBRAL_BAJO` (3), o por debajo de su mínimo.
- «Sin contar al día»: nunca se contó, o su último conteo tiene más de
  `DIAS_CONTEO_AL_DIA` días. Va en gris: son muchas y no son emergencia.

Tanda 5: «Se va a acabar» (ritmo de venta de la Libreta, ver
`inventario_ritmo_service`) NO es una quinta tarjeta: a 1366 px cinco
tarjetas no caben sin partir sus criterios en dos renglones. Es un filtro
más (`SE_VA_A_ACABAR`) que se prende desde «Para atender», y sube en esa
lista junto con las agotadas que se venden o que la gente pidió.

Como en los chips de la tanda 1, los conjuntos (Pants 3pz con receta, el
marcador viejo `stock_minimo < 0`) no cuentan en ninguna tarjeta: su número
sale de sus piezas y ya se ve en la pieza que falta.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence

from pos_uniformes.services.inventario_ritmo_service import (
    SE_ACABO_Y_SE_VENDE,
    SE_VA_A_ACABAR as ESTADO_SE_VA_A_ACABAR,
    estado_de_fila,
    pedidas_de_fila,
    ritmo_de_fila,
)
from pos_uniformes.services.inventario_existencia_service import (
    AGOTADO,
    BAJO,
    BAJO_MINIMO,
    NEGATIVO,
    UMBRAL_BAJO,
    clasificar_existencia,
    es_fila_virtual,
)

#: Un conteo «al día» tiene a lo más estos días. 60 = unos dos meses: la
#: tienda cuenta por jornada en el kiosko y una vuelta completa a todas las
#: escuelas tarda varias semanas; pasado eso, la cifra ya no es confiable.
DIAS_CONTEO_AL_DIA = 60

#: Cuántas tallas enseña «Para atender» en la ficha vacía.
LIMITE_PARA_ATENDER = 5

EN_NEGATIVO = "negativo"
SE_ACABO = "se_acabo"
QUEDAN_POCAS = "pocas"
SIN_CONTAR = "sin_contar"

TARJETAS = (EN_NEGATIVO, SE_ACABO, QUEDAN_POCAS, SIN_CONTAR)

#: Filtro sin tarjeta propia (tanda 5): se vende y alcanza para menos de
#: `DIAS_PARA_ACABARSE` días, o ya se acabó y se sigue vendiendo.
SE_VA_A_ACABAR = "acabarse"
FILTROS = TARJETAS + (SE_VA_A_ACABAR,)


@dataclass(frozen=True)
class TarjetaInfo:
    llave: str
    titulo: str
    criterio: str
    tono: str  # danger | muted | warning | neutral


INFO_TARJETAS: dict[str, TarjetaInfo] = {
    EN_NEGATIVO: TarjetaInfo(EN_NEGATIVO, "En negativo", "Se vendió más de lo que había", "danger"),
    SE_ACABO: TarjetaInfo(SE_ACABO, "Se acabó", "Hay 0 en total", "muted"),
    QUEDAN_POCAS: TarjetaInfo(QUEDAN_POCAS, "Quedan pocas", f"De 1 a {UMBRAL_BAJO}, o bajo su mínimo", "warning"),
    SIN_CONTAR: TarjetaInfo(SIN_CONTAR, "Sin contar al día", f"Nunca, o hace más de {DIAS_CONTEO_AL_DIA} días", "neutral"),
}

#: Lo que dice cada tarjeta al pasar el mouse: el criterio completo.
AVISO_TARJETAS: dict[str, str] = {
    EN_NEGATIVO: "El total (tienda + bodega + piso) es menor que 0: se vendió más de lo que el sistema tenía.",
    SE_ACABO: "El total (tienda + bodega + piso) es exactamente 0.",
    QUEDAN_POCAS: f"Quedan de 1 a {UMBRAL_BAJO} piezas, o menos que el mínimo de la talla.",
    SIN_CONTAR: f"Nunca se ha contado, o su último conteo fue hace más de {DIAS_CONTEO_AL_DIA} días.",
    SE_VA_A_ACABAR: "Con lo que se vendió en la Libreta en 30 días, alcanza para menos de 2 semanas, o ya se acabó y se sigue vendiendo.",
}


def _stock(fila: Mapping[str, object]) -> int:
    try:
        return int(fila.get("stock_actual") or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _minimo(fila: Mapping[str, object]) -> int | None:
    valor = fila.get("stock_minimo")
    try:
        return int(valor) if valor is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _como_utc(valor: object) -> datetime | None:
    if not isinstance(valor, datetime):
        return None
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)


def dias_desde_conteo(fila: Mapping[str, object], *, ahora: datetime) -> int | None:
    """Días completos desde el último conteo; None si nunca se contó."""
    conteo = _como_utc(fila.get("ultimo_conteo_at"))
    if conteo is None:
        return None
    return max(0, (_como_utc(ahora) - conteo).days)  # type: ignore[operator]


def sin_contar_al_dia(fila: Mapping[str, object], *, ahora: datetime, dias: int = DIAS_CONTEO_AL_DIA) -> bool:
    """Nunca contada, o contada hace MÁS de `dias` días (el día 60 todavía está al día)."""
    transcurridos = dias_desde_conteo(fila, ahora=ahora)
    return transcurridos is None or transcurridos > dias


def en_tarjeta(fila: Mapping[str, object], tarjeta: str, *, ahora: datetime) -> bool:
    """¿La talla cae en esa tarjeta? Una tarjeta vacía o desconocida deja pasar todo."""
    if tarjeta not in FILTROS:
        return True
    if es_fila_virtual(fila):
        return False
    if tarjeta == SE_VA_A_ACABAR:
        return estado_de_fila(fila) is not None
    if tarjeta == SIN_CONTAR:
        return sin_contar_al_dia(fila, ahora=ahora)
    clase = clasificar_existencia(_stock(fila), stock_minimo=_minimo(fila))
    if tarjeta == EN_NEGATIVO:
        return clase == NEGATIVO
    if tarjeta == SE_ACABO:
        return clase == AGOTADO
    return clase in (BAJO, BAJO_MINIMO)


@dataclass(frozen=True)
class ConteoTarjetas:
    negativo: int
    se_acabo: int
    pocas: int
    sin_contar: int
    acabarse: int = 0

    def de(self, tarjeta: str) -> int:
        return {
            EN_NEGATIVO: self.negativo,
            SE_ACABO: self.se_acabo,
            QUEDAN_POCAS: self.pocas,
            SIN_CONTAR: self.sin_contar,
            SE_VA_A_ACABAR: self.acabarse,
        }.get(tarjeta, 0)


def contar_tarjetas(filas: Iterable[Mapping[str, object]], *, ahora: datetime) -> ConteoTarjetas:
    """El número grande de cada tarjeta: el mismo criterio que su filtro."""
    cuentas = dict.fromkeys(FILTROS, 0)
    for fila in filas:
        for tarjeta in FILTROS:
            if en_tarjeta(fila, tarjeta, ahora=ahora):
                cuentas[tarjeta] += 1
    return ConteoTarjetas(
        negativo=cuentas[EN_NEGATIVO],
        se_acabo=cuentas[SE_ACABO],
        pocas=cuentas[QUEDAN_POCAS],
        sin_contar=cuentas[SIN_CONTAR],
        acabarse=cuentas[SE_VA_A_ACABAR],
    )


def filtrar_por_tarjeta(
    filas: Sequence[Mapping[str, object]], tarjeta: str | None, *, ahora: datetime
) -> list:
    if not tarjeta:
        return list(filas)
    return [fila for fila in filas if en_tarjeta(fila, tarjeta, ahora=ahora)]


def para_atender(
    filas: Iterable[Mapping[str, object]], *, limite: int = LIMITE_PARA_ATENDER
) -> list:
    """Las tallas más urgentes para la ficha vacía.

    1. En negativo, de la más negativa a la menos: se vendió sin contar.
    2. Se acabó (0) y se vende o la pidieron (tanda 5): de la más pedida y
       vendida a la menos. Es lo que hay que pedir ya.
    3. Se va a acabar (tanda 5): de la que menos días alcanza a la que más.
    4. Se acabó y SÍ se había contado, de la contada más reciente a la más
       vieja: ese cero es de verdad. Un cero que nunca se contó no dice nada
       (la mayoría de los ~2,000 ceros son eso), así que va al final, en el
       orden de la tabla.

    Solo tallas activas y sin conjuntos. Sin dato de ventas ni de demanda
    (la Libreta no respondió, o quien mira no es ADMIN) queda como en la tanda 3.
    """
    negativos: list[tuple[int, int, Mapping[str, object]]] = []
    ceros_que_piden: list[tuple[int, int, int, Mapping[str, object]]] = []
    por_acabarse: list[tuple[float, int, Mapping[str, object]]] = []
    ceros_contados: list[tuple[float, int, Mapping[str, object]]] = []
    ceros_sin_contar: list[tuple[int, Mapping[str, object]]] = []
    for posicion, fila in enumerate(filas):
        if not bool(fila.get("variante_activa", True)) or es_fila_virtual(fila):
            continue
        stock = _stock(fila)
        if stock < 0:
            negativos.append((stock, posicion, fila))
            continue
        estado = estado_de_fila(fila)
        if stock == 0:
            pedidas = pedidas_de_fila(fila)
            ritmo = ritmo_de_fila(fila)
            vendidas = ritmo.vendidas if ritmo else 0
            if pedidas > 0 or estado == SE_ACABO_Y_SE_VENDE:
                ceros_que_piden.append((-(pedidas + vendidas), -pedidas, posicion, fila))
                continue
            conteo = _como_utc(fila.get("ultimo_conteo_at"))
            if conteo is not None:
                ceros_contados.append((-conteo.timestamp(), posicion, fila))
            else:
                ceros_sin_contar.append((posicion, fila))
        elif estado == ESTADO_SE_VA_A_ACABAR:
            ritmo = ritmo_de_fila(fila)
            alcanza = ritmo.dias_alcanza if ritmo and ritmo.dias_alcanza is not None else 0.0
            por_acabarse.append((alcanza, posicion, fila))
    ordenadas = (
        [f for *_, f in sorted(negativos, key=lambda t: (t[0], t[1]))]
        + [f for *_, f in sorted(ceros_que_piden, key=lambda t: t[:3])]
        + [f for *_, f in sorted(por_acabarse, key=lambda t: (t[0], t[1]))]
        + [f for *_, f in sorted(ceros_contados, key=lambda t: (t[0], t[1]))]
        + [f for _, f in ceros_sin_contar]
    )
    return ordenadas[: max(0, limite)]


def motivo_para_atender(fila: Mapping[str, object]) -> str:
    """Una frase corta junto a la talla en «Para atender»."""
    stock = _stock(fila)
    if stock < 0:
        return f"En negativo ({stock:+d})".replace("-", "−")
    pedidas = pedidas_de_fila(fila)
    ritmo = ritmo_de_fila(fila)
    if stock == 0:
        if pedidas > 0:
            return f"Se acabó · la pidieron {pedidas} {'vez' if pedidas == 1 else 'veces'}"
        if ritmo is not None and ritmo.estado == SE_ACABO_Y_SE_VENDE:
            return f"Se acabó y se vende ({round(ritmo.por_semana) or '<1'}/sem)"
        if fila.get("ultimo_conteo_at") is None:
            return "Se acabó · nunca contada"
        return "Se acabó"
    if ritmo is not None and ritmo.estado == ESTADO_SE_VA_A_ACABAR:
        return f"Se va a acabar · {ritmo.texto_alcanza()}"
    return ""


def tono_para_atender(fila: Mapping[str, object]) -> str:
    """Rojo: solo el negativo. Ámbar: agotada que se vende o piden, y la que se va a acabar. Gris: lo demás.

    El rojo queda para lo que está mal (negativo, precio que baja); una
    agotada que piden es «hay que pedir», y ya destaca por subir en la lista.
    """
    stock = _stock(fila)
    if stock < 0:
        return "danger"
    if stock == 0 and (pedidas_de_fila(fila) > 0 or estado_de_fila(fila) == SE_ACABO_Y_SE_VENDE):
        return "warning"
    if stock > 0 and estado_de_fila(fila) == ESTADO_SE_VA_A_ACABAR:
        return "warning"
    return "muted"
