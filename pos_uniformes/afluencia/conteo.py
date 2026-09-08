"""Lógica pura del conteo de afluencia: líneas de cruce y acumulación por hora.

Sin dependencias pesadas para poder probarla en la suite del POS. El detector
(YOLO + tracker) entrega por cuadro una lista de `(id_track, x, y)` con el punto
de los pies de cada persona en coordenadas normalizadas (0..1); aquí se decide
si esa persona cruzó la línea de la puerta y hacia qué lado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

LADOS = ("abajo", "arriba", "izquierda", "derecha")


@dataclass(frozen=True)
class Linea:
    """Segmento en coordenadas normalizadas (0..1) y qué lado es el interior."""

    x1: float
    y1: float
    x2: float
    y2: float
    lado_dentro: str = "abajo"

    def __post_init__(self) -> None:
        if self.lado_dentro not in LADOS:
            raise ValueError(f"lado_dentro inválido: {self.lado_dentro!r} (usa {LADOS})")
        if (self.x1, self.y1) == (self.x2, self.y2):
            raise ValueError("la línea necesita dos puntos distintos")

    def _cruz(self, x: float, y: float) -> float:
        return (self.x2 - self.x1) * (y - self.y1) - (self.y2 - self.y1) * (x - self.x1)

    def _referencia_dentro(self) -> tuple[float, float]:
        mx, my = (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2
        return {
            "abajo": (mx, my + 0.1),
            "arriba": (mx, my - 0.1),
            "izquierda": (mx - 0.1, my),
            "derecha": (mx + 0.1, my),
        }[self.lado_dentro]

    def lado(self, x: float, y: float) -> int:
        """+1 si el punto está del lado de adentro, -1 afuera, 0 sobre la línea."""
        c = self._cruz(x, y)
        if abs(c) < 1e-9:
            return 0
        rx, ry = self._referencia_dentro()
        ref = self._cruz(rx, ry)
        return 1 if (c > 0) == (ref > 0) else -1

    def dentro_del_segmento(self, x: float, y: float, margen: float = 0.05) -> bool:
        """True si la proyección del punto cae dentro del segmento (con margen).

        Evita contar a quien cruza la recta lejos de la puerta (p.ej. por un
        pasillo lateral que está en la misma prolongación de la línea).
        """
        dx, dy = self.x2 - self.x1, self.y2 - self.y1
        largo2 = dx * dx + dy * dy
        t = ((x - self.x1) * dx + (y - self.y1) * dy) / largo2
        return -margen <= t <= 1 + margen


@dataclass
class ContadorLinea:
    """Cuenta cruces de una línea por id de track (entra = hacia adentro)."""

    linea: Linea
    entradas: int = 0
    salidas: int = 0
    _lado_por_id: dict[int, int] = field(default_factory=dict)

    def actualizar(self, detecciones: list[tuple[int, float, float]]) -> list[tuple[int, str]]:
        """Recibe (id, x, y) por persona en el cuadro; devuelve eventos (id, 'entra'|'sale')."""
        eventos: list[tuple[int, str]] = []
        for track_id, x, y in detecciones:
            lado = self.linea.lado(x, y)
            if lado == 0:
                continue
            previo = self._lado_por_id.get(track_id)
            if previo is not None and previo != lado and self.linea.dentro_del_segmento(x, y):
                if lado > 0:
                    self.entradas += 1
                    eventos.append((track_id, "entra"))
                else:
                    self.salidas += 1
                    eventos.append((track_id, "sale"))
            self._lado_por_id[track_id] = lado
        return eventos

    def olvidar_ausentes(self, ids_activos: set[int]) -> None:
        """Suelta tracks que ya no aparecen (el tracker reutiliza ids tarde o temprano)."""
        for track_id in list(self._lado_por_id):
            if track_id not in ids_activos:
                del self._lado_por_id[track_id]

    def tomar_y_reiniciar(self) -> tuple[int, int]:
        e, s = self.entradas, self.salidas
        self.entradas = self.salidas = 0
        return e, s


@dataclass
class ContadorPaso:
    """Personas distintas vistas por la cámara (quienes pasan por la banqueta)."""

    pasan: int = 0
    _vistos: set[int] = field(default_factory=set)
    _max_recordados: int = 5000

    def actualizar(self, ids: list[int]) -> int:
        nuevos = 0
        for track_id in ids:
            if track_id not in self._vistos:
                self._vistos.add(track_id)
                nuevos += 1
        self.pasan += nuevos
        if len(self._vistos) > self._max_recordados:
            # El tracker numera creciente; basta con recordar los últimos.
            self._vistos = set(sorted(self._vistos)[-self._max_recordados // 2 :])
        return nuevos

    def tomar_y_reiniciar(self) -> int:
        p = self.pasan
        self.pasan = 0
        return p


def inicio_de_hora(momento: datetime) -> datetime:
    return momento.replace(minute=0, second=0, microsecond=0)


@dataclass
class AcumuladorHora:
    """Suma entradas/salidas/pasan por (cámara, hora) hasta que se vacía a la base."""

    _pendientes: dict[tuple[str, datetime], dict[str, int]] = field(default_factory=dict)

    def agregar(self, camara: str, momento: datetime, *, entradas: int = 0, salidas: int = 0, pasan: int = 0) -> None:
        if not (entradas or salidas or pasan):
            return
        clave = (camara, inicio_de_hora(momento))
        fila = self._pendientes.setdefault(clave, {"entradas": 0, "salidas": 0, "pasan": 0})
        fila["entradas"] += entradas
        fila["salidas"] += salidas
        fila["pasan"] += pasan

    def vaciar(self) -> list[tuple[str, datetime, int, int, int]]:
        """Devuelve (camara, hora, entradas, salidas, pasan) y limpia."""
        filas = [
            (camara, hora, v["entradas"], v["salidas"], v["pasan"])
            for (camara, hora), v in sorted(self._pendientes.items(), key=lambda kv: (kv[0][1], kv[0][0]))
        ]
        self._pendientes.clear()
        return filas

    def vacio(self) -> bool:
        return not self._pendientes


def pies(bbox: tuple[float, float, float, float], ancho: float, alto: float) -> tuple[float, float]:
    """Punto de los pies (centro inferior del bbox) normalizado a 0..1."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2 / ancho, y2 / alto)


def duracion_legible(segundos: float) -> str:
    return str(timedelta(seconds=int(segundos)))
