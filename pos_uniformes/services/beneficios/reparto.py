"""Repartos exactos al centavo del motor de beneficios.

- `redondeo_tienda`: la regla R1 del ticket (la misma de
  `sale_rounding_service`; una prueba verifica que coinciden en los 100
  centavos).
- `clave_orden`: el orden determinista de I5/D1: (SKU tal como está
  guardado, linea_uid), comparado por puntos de código, sin `locale`.
- `mayor_residuo`: Q2. Truncar, repartir los centavos que faltan a los
  residuos mayores y desempatar con `clave_orden`. La suma es exacta.
- `repartir_redondeo`: I8 con los límites de D2.

Todo es puro: sin base, sin Qt, sin red, sin reloj.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from fractions import Fraction
from typing import Sequence

CENT = Decimal("0.01")
CERO = Decimal("0.00")


class ErrorDeReparto(ValueError):
    """Un reparto que no se puede hacer sin romper una regla."""


def a_centavos(valor: Decimal) -> int:
    """Pesos exactos a centavos enteros. Rechaza fracciones de centavo."""
    centavos = valor * 100
    if centavos != centavos.to_integral_value():
        raise ErrorDeReparto(f"{valor} tiene fracciones de centavo")
    return int(centavos)


def de_centavos(centavos: int) -> Decimal:
    return (Decimal(centavos) / 100).quantize(CENT)


# ─── R1 ──────────────────────────────────────────────────────────────────


def redondeo_tienda(total: Decimal) -> Decimal:
    """R1: de .01 a .19 baja al peso; de .20 a .69 va al medio peso; de .70
    en adelante sube al peso."""
    total = total.quantize(CENT)
    if total < 0:
        raise ErrorDeReparto("El total para redondeo no puede ser negativo.")
    pesos = total.to_integral_value(rounding=ROUND_FLOOR)
    centavos = (total - pesos).quantize(CENT)
    if centavos <= Decimal("0.19"):
        return pesos.quantize(CENT)
    if centavos <= Decimal("0.69"):
        return (pesos + Decimal("0.50")).quantize(CENT)
    return (pesos + 1).quantize(CENT)


# ─── I5 / D1 ─────────────────────────────────────────────────────────────


def clave_orden(sku: str | None, linea_uid: str) -> tuple[str, str]:
    """Clave de orden de una línea (I5 con D1).

    El SKU se usa exactamente como se guardó (sin espacios quitados ni
    mayúsculas) y se compara por puntos de código: la comparación nativa de
    `str` en Python, que no depende del idioma ni del sistema. Un SKU ausente
    vale "". El `linea_uid` desempata dos líneas con el mismo SKU; nunca el
    orden de captura."""
    return ("" if sku is None else str(sku), str(linea_uid))


# ─── Q2 ──────────────────────────────────────────────────────────────────


def mayor_residuo(total: Decimal, pesos: Sequence[Decimal], claves: Sequence[tuple]) -> list[Decimal]:
    """Reparte `total` (≥ 0, en centavos exactos) en proporción a `pesos`.

    Trunca cada parte al centavo y da los centavos que faltan a los residuos
    mayores; un empate lo resuelve la clave menor. La suma es exacta."""
    if len(pesos) != len(claves):
        raise ErrorDeReparto("pesos y claves de distinto tamaño")
    total_c = a_centavos(total)
    if total_c < 0:
        raise ErrorDeReparto("No se reparten importes negativos; el signo va aparte.")
    if any(p < 0 for p in pesos):
        raise ErrorDeReparto("Un peso no puede ser negativo.")
    suma = sum((Fraction(str(p)) for p in pesos), Fraction(0))
    if total_c == 0:
        return [CERO for _ in pesos]
    if suma == 0:
        raise ErrorDeReparto("No hay a quién repartir: todos los pesos son cero.")
    exactas = [Fraction(total_c) * Fraction(str(p)) / suma for p in pesos]
    enteras = [int(e) for e in exactas]  # las partes son ≥ 0: int trunca
    faltan = total_c - sum(enteras)
    orden = sorted(range(len(pesos)), key=lambda i: (-(exactas[i] - enteras[i]), claves[i]))
    for i in orden[:faltan]:
        enteras[i] += 1
    return [de_centavos(c) for c in enteras]


# ─── I8 / D2 ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RedondeoRepartido:
    partes: tuple[Decimal, ...]          # con signo, una por línea
    rondas: int                          # cuántas rondas hizo falta (trazabilidad)
    excepcion_d2: tuple[int, ...]        # índices de las líneas que absorbieron la excepción de D2
    importe_excepcion: Decimal           # cuánto se repartió por la excepción


def repartir_redondeo(
    ajuste: Decimal,
    cobrados: Sequence[Decimal],
    limites_superiores: Sequence[Decimal],
    claves: Sequence[tuple],
) -> RedondeoRepartido:
    """I8: reparte el ajuste de R1 entre las líneas.

    - Pesa cada línea su cobrado antes de redondear (una línea en $0 no
      absorbe nada).
    - Límite inferior: ninguna línea queda negativa.
    - Límite superior (D2): el precio de lista × cantidad.
    - Si a una línea le toca más de lo que puede absorber, recibe hasta su
      límite y el remanente se reparte otra vez, con el mismo método, entre
      las que todavía tienen capacidad.
    - D2: si un ajuste POSITIVO no cabe en los límites, se reparte el
      remanente estrictamente necesario entre las líneas con peso, por
      encima del límite, y se registra.
    """
    n = len(cobrados)
    if not (n == len(limites_superiores) == len(claves)):
        raise ErrorDeReparto("listas de distinto tamaño")
    signo = 1 if ajuste >= 0 else -1
    resto = abs(ajuste).quantize(CENT)
    asignado = [CERO] * n
    con_peso = [i for i in range(n) if cobrados[i] > 0]

    def capacidad(i: int) -> Decimal:
        if signo > 0:
            return max(limites_superiores[i] - cobrados[i] - asignado[i], CERO)
        return max(cobrados[i] - asignado[i], CERO)

    rondas = 0
    activos = [i for i in con_peso if capacidad(i) > 0]
    while resto > 0 and activos:
        rondas += 1
        partes = mayor_residuo(resto, [cobrados[i] for i in activos], [claves[i] for i in activos])
        for i, parte in zip(activos, partes):
            toma = min(parte, capacidad(i))
            asignado[i] += toma
            resto -= toma
        activos = [i for i in activos if capacidad(i) > 0]

    excepcion: tuple[int, ...] = ()
    importe_excepcion = CERO
    if resto > 0:
        if signo < 0:
            # No puede pasar: el ticket solo baja si sus líneas suman al menos el ajuste.
            raise ErrorDeReparto("El ajuste negativo no cabe en las líneas.")
        if not con_peso:
            raise ErrorDeReparto("No hay líneas con importe para absorber el redondeo.")
        rondas += 1
        partes = mayor_residuo(resto, [cobrados[i] for i in con_peso], [claves[i] for i in con_peso])
        excepcion = tuple(i for i, p in zip(con_peso, partes) if p > 0)
        importe_excepcion = resto
        for i, parte in zip(con_peso, partes):
            asignado[i] += parte
        resto = CERO

    return RedondeoRepartido(
        partes=tuple((a if signo > 0 else -a) for a in asignado),
        rondas=rondas,
        excepcion_d2=excepcion,
        importe_excepcion=importe_excepcion,
    )
