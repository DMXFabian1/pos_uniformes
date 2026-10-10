"""Adornos festivos del ticket, dibujados a trazo sobre el ticket de puntos.

Daniel (2026-10-10) trajo ocho bocetos: el mismo ticket con lápices en Regreso
a clases, calaveritas en Día de Muertos, corazones en San Valentín… y pidió una
composición completa, no iconos sueltos: esquinas, marcos, separadores entre
productos, cabecera, total y un marco para los términos.

Tres reglas salen de que esto se imprime en papel térmico y de que el ticket ya
existe:

- **Blanco y negro, a trazo.** La térmica quema puntos: un gris es un tramado
  que se ve sucio y una mancha negra grande gasta cabeza y papel. Todo aquí son
  líneas de 2 a 3 puntos y rellenos chicos (un pétalo, una cuenca de ojo).
- **El texto manda.** Los adornos van donde ya había aire o en los bordes que
  ya existían: esquinas de las cajas, las reglas entre productos, los extremos
  de los renglones centrados, el marco de los términos. Ningún renglón de datos
  cambia de sitio ni de tamaño.
- **Solo en el ticket dibujado.** El texto de 38 columnas sigue siendo el mismo
  para la pantalla, QPrinter y ESC/POS en texto. Los adornos los pone
  `ticket_imagen_service.render_ticket` encima, y se apagan con un ajuste
  (`adornos_de_temporada`) o quitando la temporada.

El tema NO se pregunta a la fecha: se lee del propio ticket, del marcador
`[[IMG:halloween]]` que ya viaja en el texto. Así el ticket que se armó en un
kiosko y se imprime en la principal sale con los adornos del dibujo que trae.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

#: Trazo normal y trazo fino. 2 puntos a 203 dpi se ve; 1.2 es para detalles
#: interiores que a 2 se empastarían (los dientes de una calaverita).
TRAZO = 2.0
FINO = 1.3

Dibujo = Callable[["QPainter", float, float, float], None]  # noqa: F821


# ── Herramientas ─────────────────────────────────────────────────────────────


def _pluma(p, relleno: bool = False, grosor: float = TRAZO):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QBrush, QColor, QPen

    pen = QPen(QColor("black"))
    pen.setWidthF(grosor)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QBrush(QColor("black")) if relleno else Qt.BrushStyle.NoBrush)


def _pt(x, y):
    from PyQt6.QtCore import QPointF

    return QPointF(x, y)


def _rect(x, y, w, h):
    from PyQt6.QtCore import QRectF

    return QRectF(x, y, w, h)


def _poli(pts):
    from PyQt6.QtGui import QPolygonF

    return QPolygonF([_pt(a, b) for a, b in pts])


def _circulo(p, cx, cy, r, relleno=False, grosor=TRAZO):
    _pluma(p, relleno, grosor)
    p.drawEllipse(_pt(cx, cy), r, r)


def _espejo(p, dibujo: Dibujo, x: float, y: float, t: float, *, eje_x=False, eje_y=False):
    """Dibuja el motivo volteado: para la esquina derecha o la de abajo."""
    p.save()
    p.translate(x + (t if eje_x else 0), y + (t if eje_y else 0))
    p.scale(-1 if eje_x else 1, -1 if eje_y else 1)
    dibujo(p, 0, 0, t)
    p.restore()


# ── Motivos genéricos reutilizados por varios temas ──────────────────────────


def corazon(p, x, y, t, relleno=True):
    from PyQt6.QtGui import QPainterPath

    _pluma(p, relleno)
    path = QPainterPath(_pt(x + t / 2, y + t * 0.92))
    path.cubicTo(x - t * 0.05, y + t * 0.5, x + t * 0.05, y + t * 0.02, x + t / 2, y + t * 0.3)
    path.cubicTo(x + t * 0.95, y + t * 0.02, x + t * 1.05, y + t * 0.5, x + t / 2, y + t * 0.92)
    p.drawPath(path)


def corazon_doble(p, x, y, t):
    """Un corazón grande hueco con uno chico relleno adentro: con brillo."""
    corazon(p, x, y, t, relleno=False)
    corazon(p, x + t * 0.3, y + t * 0.32, t * 0.4, relleno=True)


def estrella(p, x, y, t, puntas: int = 5, relleno: bool = False):
    _pluma(p, relleno)
    cx, cy, r = x + t / 2, y + t / 2, t / 2
    pts = []
    for i in range(puntas * 2):
        rad = r if i % 2 == 0 else r * 0.45
        ang = -math.pi / 2 + i * math.pi / puntas
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    p.drawPolygon(_poli(pts))


def estrella_llena(p, x, y, t):
    estrella(p, x, y, t, relleno=True)


def destello(p, x, y, t):
    """Cuatro puntas finas y dos cruces chicas: la chispa."""
    _pluma(p, relleno=True)
    cx, cy, r = x + t / 2, y + t / 2, t / 2
    pts = []
    for i in range(8):
        rad = r if i % 2 == 0 else r * 0.16
        ang = -math.pi / 2 + i * math.pi / 4
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    p.drawPolygon(_poli(pts))
    _pluma(p, grosor=FINO)
    for dx, dy in ((0.78, 0.22), (0.22, 0.8)):
        px, py = x + t * dx, y + t * dy
        p.drawLine(_pt(px - t * 0.08, py), _pt(px + t * 0.08, py))
        p.drawLine(_pt(px, py - t * 0.08), _pt(px, py + t * 0.08))


def hoja(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    path = QPainterPath(_pt(x + t * 0.08, y + t * 0.88))
    path.quadTo(x + t * 0.05, y + t * 0.2, x + t * 0.92, y + t * 0.12)
    path.quadTo(x + t * 0.95, y + t * 0.8, x + t * 0.08, y + t * 0.88)
    p.drawPath(path)
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(x + t * 0.12, y + t * 0.84), _pt(x + t * 0.88, y + t * 0.16))
    for f in (0.3, 0.5, 0.7):
        px, py = x + t * (0.12 + 0.76 * f), y + t * (0.84 - 0.68 * f)
        p.drawLine(_pt(px, py), _pt(px + t * 0.12, py - t * 0.02))
        p.drawLine(_pt(px, py), _pt(px - t * 0.02, py - t * 0.12))


def ramita(p, x, y, t):
    """Una rama con hojitas a los lados, para esquinas y separadores."""
    _pluma(p)
    p.drawLine(_pt(x, y + t * 0.5), _pt(x + t, y + t * 0.5))
    _pluma(p, grosor=FINO)
    for i in range(4):
        px = x + t * (0.15 + i * 0.22)
        from PyQt6.QtGui import QPainterPath

        for lado in (-1, 1):
            path = QPainterPath(_pt(px, y + t * 0.5))
            path.quadTo(px + t * 0.06, y + t * (0.5 + lado * 0.3), px + t * 0.18, y + t * (0.5 + lado * 0.28))
            path.quadTo(px + t * 0.12, y + t * (0.5 + lado * 0.1), px, y + t * 0.5)
            p.drawPath(path)


def mono(p, x, y, t):
    """Un moño con sus dos lazos, el nudo y las colas."""
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    for lado in (-1, 1):
        path = QPainterPath(_pt(x + t / 2, y + t * 0.45))
        path.cubicTo(x + t * (0.5 + lado * 0.15), y + t * 0.05, x + t * (0.5 + lado * 0.55), y + t * 0.1,
                     x + t * (0.5 + lado * 0.48), y + t * 0.42)
        path.cubicTo(x + t * (0.5 + lado * 0.5), y + t * 0.62, x + t * (0.5 + lado * 0.2), y + t * 0.6,
                     x + t / 2, y + t * 0.45)
        p.drawPath(path)
        p.drawLine(_pt(x + t / 2, y + t * 0.5), _pt(x + t * (0.5 + lado * 0.3), y + t * 0.95))
    _circulo(p, x + t / 2, y + t * 0.45, t * 0.09, relleno=True)


def regalo(p, x, y, t):
    _pluma(p)
    p.drawRect(_rect(x + t * 0.12, y + t * 0.4, t * 0.76, t * 0.52))
    p.drawRect(_rect(x + t * 0.06, y + t * 0.32, t * 0.88, t * 0.14))
    p.drawLine(_pt(x + t / 2, y + t * 0.32), _pt(x + t / 2, y + t * 0.92))
    mono(p, x + t * 0.25, y + t * 0.02, t * 0.5)


# ── Día de Muertos ───────────────────────────────────────────────────────────


def cempasuchil(p, x, y, t):
    """Dos coronas de pétalos y el botón: la flor que se reconoce de lejos."""
    cx, cy, r = x + t / 2, y + t / 2, t * 0.48
    _pluma(p, grosor=TRAZO)
    for i in range(8):
        ang = i * math.pi / 4
        px, py = cx + r * 0.66 * math.cos(ang), cy + r * 0.66 * math.sin(ang)
        p.drawEllipse(_pt(px, py), r * 0.34, r * 0.34)
    _pluma(p, grosor=FINO)
    for i in range(6):
        ang = i * math.pi / 3 + math.pi / 6
        px, py = cx + r * 0.34 * math.cos(ang), cy + r * 0.34 * math.sin(ang)
        p.drawEllipse(_pt(px, py), r * 0.2, r * 0.2)
    _circulo(p, cx, cy, r * 0.14, relleno=True)


def petalo(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p, relleno=True)
    path = QPainterPath(_pt(x + t * 0.15, y + t * 0.85))
    path.quadTo(x + t * 0.1, y + t * 0.25, x + t * 0.85, y + t * 0.15)
    path.quadTo(x + t * 0.85, y + t * 0.75, x + t * 0.15, y + t * 0.85)
    p.drawPath(path)


def florecita(p, x, y, t):
    """Seis pétalos redondos y el botón: la flor chica de los separadores."""
    cx, cy, r = x + t / 2, y + t / 2, t * 0.46
    _pluma(p, grosor=FINO)
    for i in range(6):
        ang = i * math.pi / 3
        p.drawEllipse(_pt(cx + r * 0.62 * math.cos(ang), cy + r * 0.62 * math.sin(ang)), r * 0.36, r * 0.36)
    _circulo(p, cx, cy, r * 0.22, relleno=True, grosor=FINO)


def petalos(p, x, y, t):
    """Tres pétalos sueltos, como caídos."""
    petalo(p, x, y + t * 0.3, t * 0.45)
    petalo(p, x + t * 0.5, y, t * 0.45)
    petalo(p, x + t * 0.45, y + t * 0.5, t * 0.45)


def calaverita(p, x, y, t):
    """Calaverita de azúcar: cuencas con pétalos, nariz de corazón, dientes y
    una florecita en la frente."""
    _pluma(p)
    # Cráneo y mandíbula
    p.drawEllipse(_rect(x + t * 0.12, y + t * 0.02, t * 0.76, t * 0.66))
    p.drawRoundedRect(_rect(x + t * 0.27, y + t * 0.6, t * 0.46, t * 0.36), t * 0.1, t * 0.1)
    # Cuencas con pétalos alrededor
    for cx in (x + t * 0.36, x + t * 0.64):
        cy = y + t * 0.36
        _circulo(p, cx, cy, t * 0.1, relleno=True)
        _pluma(p, grosor=FINO)
        for i in range(6):
            ang = i * math.pi / 3
            p.drawEllipse(_pt(cx + t * 0.15 * math.cos(ang), cy + t * 0.15 * math.sin(ang)), t * 0.045, t * 0.045)
    # Nariz: corazón al revés
    _pluma(p, relleno=True)
    p.drawPolygon(_poli([(x + t * 0.45, y + t * 0.5), (x + t * 0.55, y + t * 0.5), (x + t * 0.5, y + t * 0.58)]))
    # Dientes
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(x + t * 0.3, y + t * 0.78), _pt(x + t * 0.7, y + t * 0.78))
    for f in (0.38, 0.46, 0.54, 0.62):
        p.drawLine(_pt(x + t * f, y + t * 0.68), _pt(x + t * f, y + t * 0.9))
    # Florecita en la frente
    _circulo(p, x + t / 2, y + t * 0.13, t * 0.035, relleno=True)
    for i in range(5):
        ang = -math.pi / 2 + i * 2 * math.pi / 5
        p.drawEllipse(_pt(x + t / 2 + t * 0.07 * math.cos(ang), y + t * 0.13 + t * 0.07 * math.sin(ang)), t * 0.03, t * 0.03)


def calavera_con_flores(p, x, y, t):
    """La calaverita con su corona de cempasúchil, para los flancos grandes."""
    calaverita(p, x + t * 0.1, y + t * 0.22, t * 0.8)
    cempasuchil(p, x + t * 0.32, y - t * 0.02, t * 0.36)
    cempasuchil(p, x + t * 0.02, y + t * 0.1, t * 0.28)
    cempasuchil(p, x + t * 0.7, y + t * 0.1, t * 0.28)


def papel_picado(p, x, y, t):
    """Una banderita de papel picado con sus cortes: rombos y una flor."""
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    path = QPainterPath(_pt(x + t * 0.06, y + t * 0.08))
    path.lineTo(x + t * 0.94, y + t * 0.08)
    path.lineTo(x + t * 0.94, y + t * 0.78)
    for i in range(4, 0, -1):
        xi = x + t * 0.06 + i * t * 0.22
        path.quadTo(xi - t * 0.11, y + t * 0.98, xi - t * 0.22, y + t * 0.78)
    path.closeSubpath()
    p.drawPath(path)
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(x - t * 0.05, y + t * 0.08), _pt(x + t * 1.05, y + t * 0.08))
    # Cortes: una flor en medio y rombos a los lados
    _circulo(p, x + t / 2, y + t * 0.42, t * 0.06, relleno=True, grosor=FINO)
    for i in range(6):
        ang = i * math.pi / 3
        p.drawEllipse(_pt(x + t / 2 + t * 0.13 * math.cos(ang), y + t * 0.42 + t * 0.13 * math.sin(ang)), t * 0.05, t * 0.05)
    for xi in (0.2, 0.8):
        p.drawPolygon(_poli([(x + t * xi, y + t * 0.3), (x + t * (xi + 0.07), y + t * 0.42),
                             (x + t * xi, y + t * 0.54), (x + t * (xi - 0.07), y + t * 0.42)]))
    for xi in (0.2, 0.5, 0.8):
        p.drawPolygon(_poli([(x + t * xi, y + t * 0.6), (x + t * (xi + 0.05), y + t * 0.68),
                             (x + t * xi, y + t * 0.76), (x + t * (xi - 0.05), y + t * 0.68)]))


def vela(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    p.drawRoundedRect(_rect(x + t * 0.32, y + t * 0.4, t * 0.36, t * 0.55), t * 0.05, t * 0.05)
    # Cera escurrida
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(x + t * 0.4, y + t * 0.4), _pt(x + t * 0.4, y + t * 0.58))
    p.drawLine(_pt(x + t * 0.6, y + t * 0.4), _pt(x + t * 0.6, y + t * 0.52))
    # Flama
    _pluma(p, relleno=True)
    path = QPainterPath(_pt(x + t / 2, y + t * 0.36))
    path.quadTo(x + t * 0.32, y + t * 0.2, x + t / 2, y + t * 0.02)
    path.quadTo(x + t * 0.68, y + t * 0.2, x + t / 2, y + t * 0.36)
    p.drawPath(path)


def esquina_muertos(p, x, y, t):
    """Esquina: una flor en el ángulo, una hoja por cada borde y un pétalo."""
    cempasuchil(p, x, y, t * 0.66)
    hoja(p, x + t * 0.6, y + t * 0.05, t * 0.4)
    p.save()
    p.translate(x + t * 0.05, y + t * 0.6)
    p.rotate(90)
    p.translate(0, -t * 0.4)
    _espejo(p, hoja, 0, 0, t * 0.4, eje_y=True)
    p.restore()
    petalo(p, x + t * 0.68, y + t * 0.62, t * 0.26)


# ── Halloween ────────────────────────────────────────────────────────────────


def murcielago(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p, relleno=True)
    path = QPainterPath(_pt(x + t / 2, y + t * 0.8))
    path.quadTo(x + t * 0.42, y + t * 0.55, x + t * 0.3, y + t * 0.58)
    path.quadTo(x + t * 0.18, y + t * 0.62, x + t * 0.02, y + t * 0.5)
    path.quadTo(x + t * 0.14, y + t * 0.42, x + t * 0.12, y + t * 0.3)
    path.quadTo(x + t * 0.3, y + t * 0.34, x + t * 0.4, y + t * 0.26)
    path.lineTo(x + t * 0.42, y + t * 0.1)
    path.lineTo(x + t * 0.48, y + t * 0.22)
    path.lineTo(x + t * 0.52, y + t * 0.22)
    path.lineTo(x + t * 0.58, y + t * 0.1)
    path.lineTo(x + t * 0.6, y + t * 0.26)
    path.quadTo(x + t * 0.7, y + t * 0.34, x + t * 0.88, y + t * 0.3)
    path.quadTo(x + t * 0.86, y + t * 0.42, x + t * 0.98, y + t * 0.5)
    path.quadTo(x + t * 0.82, y + t * 0.62, x + t * 0.7, y + t * 0.58)
    path.quadTo(x + t * 0.58, y + t * 0.55, x + t / 2, y + t * 0.8)
    p.drawPath(path)


def calabaza(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    p.drawEllipse(_rect(x + t * 0.05, y + t * 0.3, t * 0.9, t * 0.65))
    _pluma(p, grosor=FINO)
    p.drawEllipse(_rect(x + t * 0.3, y + t * 0.3, t * 0.4, t * 0.65))
    p.drawEllipse(_rect(x + t * 0.17, y + t * 0.3, t * 0.66, t * 0.65))
    _pluma(p)
    path = QPainterPath(_pt(x + t * 0.5, y + t * 0.3))
    path.quadTo(x + t * 0.48, y + t * 0.1, x + t * 0.62, y + t * 0.05)
    p.drawPath(path)
    # Cara
    _pluma(p, relleno=True)
    p.drawPolygon(_poli([(x + t * 0.3, y + t * 0.58), (x + t * 0.42, y + t * 0.58), (x + t * 0.36, y + t * 0.46)]))
    p.drawPolygon(_poli([(x + t * 0.58, y + t * 0.58), (x + t * 0.7, y + t * 0.58), (x + t * 0.64, y + t * 0.46)]))
    p.drawPolygon(_poli([(x + t * 0.3, y + t * 0.7), (x + t * 0.7, y + t * 0.7), (x + t * 0.62, y + t * 0.8),
                         (x + t * 0.55, y + t * 0.72), (x + t * 0.45, y + t * 0.72), (x + t * 0.38, y + t * 0.8)]))


def luna(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p, relleno=True)
    fuera = QPainterPath()
    fuera.addEllipse(_rect(x + t * 0.08, y + t * 0.08, t * 0.84, t * 0.84))
    dentro = QPainterPath()
    dentro.addEllipse(_rect(x + t * 0.3, y + t * 0.0, t * 0.84, t * 0.84))
    p.drawPath(fuera.subtracted(dentro))
    estrella(p, x + t * 0.62, y + t * 0.28, t * 0.22, puntas=4, relleno=True)


def fantasma(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    path = QPainterPath(_pt(x + t * 0.15, y + t * 0.9))
    path.lineTo(x + t * 0.15, y + t * 0.45)
    path.quadTo(x + t * 0.15, y + t * 0.05, x + t * 0.5, y + t * 0.05)
    path.quadTo(x + t * 0.85, y + t * 0.05, x + t * 0.85, y + t * 0.45)
    path.lineTo(x + t * 0.85, y + t * 0.9)
    for i in range(3, 0, -1):
        xi = x + t * 0.15 + i * t * 0.2333
        path.quadTo(xi - t * 0.1167, y + t * 0.75, xi - t * 0.2333, y + t * 0.9)
    p.drawPath(path)
    _circulo(p, x + t * 0.4, y + t * 0.4, t * 0.06, relleno=True)
    _circulo(p, x + t * 0.6, y + t * 0.4, t * 0.06, relleno=True)
    _pluma(p, grosor=FINO)
    p.drawEllipse(_rect(x + t * 0.44, y + t * 0.52, t * 0.12, t * 0.1))


def telarana(p, x, y, t):
    """Esquina de telaraña: radios desde el ángulo y tres hilos curvos."""
    from PyQt6.QtGui import QPainterPath

    _pluma(p, grosor=FINO)
    for i in range(5):
        ang = i * (math.pi / 2) / 4
        p.drawLine(_pt(x, y), _pt(x + t * math.cos(ang), y + t * math.sin(ang)))
    for r in (0.35, 0.65, 0.95):
        path = QPainterPath(_pt(x + t * r, y))
        for i in range(1, 5):
            ang = i * (math.pi / 2) / 4
            ang0 = (i - 0.5) * (math.pi / 2) / 4
            path.quadTo(x + t * r * 0.88 * math.cos(ang0), y + t * r * 0.88 * math.sin(ang0),
                        x + t * r * math.cos(ang), y + t * r * math.sin(ang))
        p.drawPath(path)


# ── Navidad ──────────────────────────────────────────────────────────────────


def rama_pino(p, x, y, t):
    _pluma(p)
    p.drawLine(_pt(x, y + t * 0.5), _pt(x + t, y + t * 0.5))
    _pluma(p, grosor=FINO)
    for i in range(7):
        xi = x + t * (0.08 + i * 0.14)
        p.drawLine(_pt(xi, y + t * 0.5), _pt(xi + t * 0.12, y + t * 0.12))
        p.drawLine(_pt(xi, y + t * 0.5), _pt(xi + t * 0.12, y + t * 0.88))
        p.drawLine(_pt(xi + t * 0.06, y + t * 0.5), _pt(xi + t * 0.16, y + t * 0.28))
        p.drawLine(_pt(xi + t * 0.06, y + t * 0.5), _pt(xi + t * 0.16, y + t * 0.72))


def campana(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    path = QPainterPath(_pt(x + t * 0.2, y + t * 0.75))
    path.quadTo(x + t * 0.3, y + t * 0.55, x + t * 0.3, y + t * 0.38)
    path.quadTo(x + t * 0.3, y + t * 0.12, x + t * 0.5, y + t * 0.1)
    path.quadTo(x + t * 0.7, y + t * 0.12, x + t * 0.7, y + t * 0.38)
    path.quadTo(x + t * 0.7, y + t * 0.55, x + t * 0.8, y + t * 0.75)
    path.closeSubpath()
    p.drawPath(path)
    _circulo(p, x + t * 0.5, y + t * 0.84, t * 0.08, relleno=True)
    _circulo(p, x + t * 0.5, y + t * 0.06, t * 0.05)
    mono(p, x + t * 0.3, y - t * 0.08, t * 0.4)


def esquina_pino(p, x, y, t):
    """Esquina: una estrella en el ángulo y una rama corta por el borde de
    arriba. A 28 puntos dos ramas cruzadas se empastaban en una mancha."""
    estrella(p, x + t * 0.02, y + t * 0.02, t * 0.4, relleno=True)
    rama_pino(p, x + t * 0.42, y + t * 0.05, t * 0.56)
    _circulo(p, x + t * 0.2, y + t * 0.7, t * 0.07, relleno=True)
    _circulo(p, x + t * 0.38, y + t * 0.82, t * 0.05, relleno=True)


def copo(p, x, y, t):
    _pluma(p, grosor=FINO)
    cx, cy, r = x + t / 2, y + t / 2, t * 0.46
    for i in range(6):
        ang = i * math.pi / 3
        ex, ey = cx + r * math.cos(ang), cy + r * math.sin(ang)
        p.drawLine(_pt(cx, cy), _pt(ex, ey))
        for f in (0.5, 0.75):
            bx, by = cx + r * f * math.cos(ang), cy + r * f * math.sin(ang)
            for d in (-1, 1):
                a2 = ang + d * math.pi / 5
                p.drawLine(_pt(bx, by), _pt(bx + r * 0.2 * math.cos(a2), by + r * 0.2 * math.sin(a2)))


# ── Año Nuevo y Reyes ────────────────────────────────────────────────────────


def corona(p, x, y, t):
    _pluma(p)
    base = y + t * 0.86
    p.drawPolygon(_poli([(x + t * 0.08, base), (x + t * 0.08, y + t * 0.36), (x + t * 0.3, y + t * 0.58),
                         (x + t * 0.5, y + t * 0.16), (x + t * 0.7, y + t * 0.58), (x + t * 0.92, y + t * 0.36),
                         (x + t * 0.92, base)]))
    p.drawLine(_pt(x + t * 0.08, base - t * 0.16), _pt(x + t * 0.92, base - t * 0.16))
    _pluma(p, relleno=True)
    for px, py in ((0.08, 0.36), (0.5, 0.16), (0.92, 0.36)):
        p.drawEllipse(_pt(x + t * px, y + t * py), t * 0.05, t * 0.05)
    _pluma(p, grosor=FINO)
    for px in (0.3, 0.5, 0.7):
        p.drawPolygon(_poli([(x + t * px, y + t * 0.64), (x + t * (px + 0.05), y + t * 0.72),
                             (x + t * px, y + t * 0.8), (x + t * (px - 0.05), y + t * 0.72)]))


def rosca(p, x, y, t):
    """La Rosca de Reyes: el anillo, las tiras de ate y el azúcar."""
    _pluma(p)
    p.drawEllipse(_rect(x + t * 0.06, y + t * 0.22, t * 0.88, t * 0.56))
    p.drawEllipse(_rect(x + t * 0.34, y + t * 0.4, t * 0.32, t * 0.2))
    _pluma(p, grosor=FINO)
    for ang in (-70, -20, 40, 110, 160, 220):
        a = math.radians(ang)
        p.drawLine(_pt(x + t / 2 + t * 0.19 * math.cos(a), y + t / 2 + t * 0.12 * math.sin(a)),
                   _pt(x + t / 2 + t * 0.42 * math.cos(a), y + t / 2 + t * 0.27 * math.sin(a)))
    for ang in (-45, 75, 190):
        a = math.radians(ang)
        _circulo(p, x + t / 2 + t * 0.32 * math.cos(a), y + t / 2 + t * 0.2 * math.sin(a), t * 0.03, relleno=True, grosor=FINO)


def estrella_fugaz(p, x, y, t):
    estrella(p, x + t * 0.5, y, t * 0.5, puntas=4, relleno=True)
    _pluma(p, grosor=FINO)
    for dy in (0.2, 0.3, 0.4):
        p.drawLine(_pt(x, y + t * (dy + 0.45)), _pt(x + t * 0.5, y + t * dy))


def esquina_reyes(p, x, y, t):
    corona(p, x, y, t * 0.55)
    destello(p, x + t * 0.62, y + t * 0.05, t * 0.3)
    estrella(p, x + t * 0.1, y + t * 0.62, t * 0.22, puntas=4, relleno=True)


# ── Independencia ────────────────────────────────────────────────────────────


def greca_mexicana(p, x, y, t):
    """Greca escalonada: la de los sarapes."""
    pts = []
    n = 4
    for i in range(n):
        x0 = x + t * i / n
        pts += [(x0, y + t * 0.75), (x0, y + t * 0.25), (x0 + t / n * 0.5, y + t * 0.25),
                (x0 + t / n * 0.5, y + t * 0.6), (x0 + t / n, y + t * 0.6)]
    _pluma(p, grosor=FINO)
    p.drawPolyline(_poli(pts))


def banderin(p, x, y, t):
    papel_picado(p, x, y, t)


def sol_azteca(p, x, y, t):
    _pluma(p)
    cx, cy, r = x + t / 2, y + t / 2, t * 0.46
    p.drawEllipse(_pt(cx, cy), r * 0.42, r * 0.42)
    _pluma(p, grosor=FINO)
    for i in range(12):
        ang = i * math.pi / 6
        r0 = r * (0.55 if i % 2 else 0.6)
        r1 = r * (0.8 if i % 2 else 1.0)
        p.drawLine(_pt(cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)), _pt(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)))
    _circulo(p, cx, cy, r * 0.12, relleno=True, grosor=FINO)


def esquina_mexico(p, x, y, t):
    # Cada banderita trae su hilo que se asoma 5 % a cada lado: por eso van
    # un poco metidas, para que el hilo no se salga del cuadro.
    papel_picado(p, x + t * 0.06, y + t * 0.02, t * 0.44)
    papel_picado(p, x + t * 0.5, y + t * 0.02, t * 0.44)
    # La greca va achatada: ancha como la esquina, pero de un tercio de alto,
    # para que quede debajo de las banderitas sin salirse del cuadro.
    p.save()
    p.translate(x + t * 0.05, y + t * 0.55)
    p.scale(1, 0.45)
    greca_mexicana(p, 0, 0, t * 0.9)
    p.restore()


# ── Regreso a clases ─────────────────────────────────────────────────────────


def lapiz(p, x, y, t):
    _pluma(p)
    p.save()
    p.translate(x + t / 2, y + t / 2)
    p.rotate(-45)
    w, h = t * 0.3, t * 1.0
    p.drawRect(_rect(-w / 2, -h / 2, w, h * 0.7))
    p.drawPolygon(_poli([(-w / 2, h * 0.2), (w / 2, h * 0.2), (0, h / 2)]))
    _pluma(p, relleno=True)
    p.drawPolygon(_poli([(-w * 0.18, h * 0.4), (w * 0.18, h * 0.4), (0, h / 2)]))
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(-w / 2, -h * 0.34), _pt(w / 2, -h * 0.34))
    p.drawLine(_pt(-w / 2, -h * 0.42), _pt(w / 2, -h * 0.42))
    p.drawLine(_pt(-w / 6, -h * 0.34), _pt(-w / 6, h * 0.2))
    p.restore()


def cuaderno(p, x, y, t):
    _pluma(p)
    p.drawRoundedRect(_rect(x + t * 0.18, y + t * 0.1, t * 0.66, t * 0.82), t * 0.04, t * 0.04)
    _pluma(p, grosor=FINO)
    for i in range(5):
        yi = y + t * (0.2 + i * 0.16)
        p.drawEllipse(_rect(x + t * 0.1, yi - t * 0.04, t * 0.14, t * 0.08))
    for i in range(4):
        yi = y + t * (0.36 + i * 0.14)
        p.drawLine(_pt(x + t * 0.34, yi), _pt(x + t * 0.74, yi))


def regla(p, x, y, t):
    _pluma(p)
    p.drawRect(_rect(x + t * 0.03, y + t * 0.32, t * 0.94, t * 0.36))
    _pluma(p, grosor=FINO)
    for i in range(1, 8):
        xi = x + t * 0.03 + i * t * 0.1175
        p.drawLine(_pt(xi, y + t * 0.32), _pt(xi, y + t * (0.52 if i % 2 else 0.44)))


def mochila(p, x, y, t):
    _pluma(p)
    p.drawRoundedRect(_rect(x + t * 0.18, y + t * 0.22, t * 0.64, t * 0.7), t * 0.12, t * 0.12)
    p.drawRoundedRect(_rect(x + t * 0.28, y + t * 0.56, t * 0.44, t * 0.3), t * 0.06, t * 0.06)
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(x + t * 0.38, y + t * 0.22), _pt(x + t * 0.42, y + t * 0.08))
    p.drawLine(_pt(x + t * 0.62, y + t * 0.22), _pt(x + t * 0.58, y + t * 0.08))
    p.drawLine(_pt(x + t * 0.42, y + t * 0.08), _pt(x + t * 0.58, y + t * 0.08))
    p.drawLine(_pt(x + t * 0.28, y + t * 0.4), _pt(x + t * 0.72, y + t * 0.4))


def manzana(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    path = QPainterPath(_pt(x + t / 2, y + t * 0.3))
    path.cubicTo(x + t * 0.2, y + t * 0.05, x - t * 0.02, y + t * 0.5, x + t * 0.25, y + t * 0.85)
    path.quadTo(x + t * 0.5, y + t * 1.0, x + t * 0.75, y + t * 0.85)
    path.cubicTo(x + t * 1.02, y + t * 0.5, x + t * 0.8, y + t * 0.05, x + t / 2, y + t * 0.3)
    p.drawPath(path)
    p.drawLine(_pt(x + t / 2, y + t * 0.3), _pt(x + t * 0.55, y + t * 0.08))
    hoja(p, x + t * 0.55, y + t * 0.02, t * 0.3)


def esquina_escuela(p, x, y, t):
    lapiz(p, x, y, t * 0.6)
    regla(p, x + t * 0.3, y + t * 0.55, t * 0.7)
    estrella(p, x + t * 0.66, y + t * 0.08, t * 0.26, relleno=True)


# ── San Valentín ─────────────────────────────────────────────────────────────


def rosa(p, x, y, t):
    """Una rosa vista desde arriba: espiral de pétalos y dos hojas."""
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    cx, cy = x + t / 2, y + t * 0.42
    path = QPainterPath(_pt(cx, cy))
    for i in range(1, 22):
        ang = i * 0.55
        r = t * 0.02 * i
        path.lineTo(cx + r * math.cos(ang), cy + r * 0.85 * math.sin(ang))
    p.drawPath(path)
    hoja(p, x + t * 0.02, y + t * 0.62, t * 0.4)
    _espejo(p, hoja, x + t * 0.58, y + t * 0.62, t * 0.4, eje_x=True)


def esquina_valentin(p, x, y, t):
    corazon_doble(p, x, y, t * 0.6)
    mono(p, x + t * 0.5, y + t * 0.05, t * 0.5)
    corazon(p, x + t * 0.12, y + t * 0.66, t * 0.28)
    corazon(p, x + t * 0.6, y + t * 0.6, t * 0.2)


def flecha_corazon(p, x, y, t):
    corazon(p, x + t * 0.2, y + t * 0.15, t * 0.6, relleno=False)
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(x, y + t * 0.85), _pt(x + t, y + t * 0.15))
    p.drawPolygon(_poli([(x + t, y + t * 0.15), (x + t * 0.82, y + t * 0.18), (x + t * 0.97, y + t * 0.33)]))
    p.drawLine(_pt(x, y + t * 0.85), _pt(x + t * 0.08, y + t * 0.7))
    p.drawLine(_pt(x, y + t * 0.85), _pt(x + t * 0.15, y + t * 0.92))


# ── Día de las Madres ────────────────────────────────────────────────────────


def flor(p, x, y, t):
    """Cinco pétalos con vena y el botón."""
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    cx, cy, r = x + t / 2, y + t / 2, t * 0.48
    for i in range(5):
        ang = -math.pi / 2 + i * 2 * math.pi / 5
        path = QPainterPath(_pt(cx, cy))
        a1, a2 = ang - 0.55, ang + 0.55
        path.cubicTo(cx + r * math.cos(a1), cy + r * math.sin(a1), cx + r * math.cos(a2), cy + r * math.sin(a2), cx, cy)
        p.drawPath(path)
        _pluma(p, grosor=FINO)
        p.drawLine(_pt(cx + r * 0.2 * math.cos(ang), cy + r * 0.2 * math.sin(ang)),
                   _pt(cx + r * 0.6 * math.cos(ang), cy + r * 0.6 * math.sin(ang)))
        _pluma(p)
    _circulo(p, cx, cy, r * 0.16, relleno=True)


def tulipan(p, x, y, t):
    from PyQt6.QtGui import QPainterPath

    _pluma(p)
    path = QPainterPath(_pt(x + t * 0.25, y + t * 0.45))
    path.quadTo(x + t * 0.2, y + t * 0.05, x + t * 0.38, y + t * 0.18)
    path.lineTo(x + t * 0.5, y + t * 0.05)
    path.lineTo(x + t * 0.62, y + t * 0.18)
    path.quadTo(x + t * 0.8, y + t * 0.05, x + t * 0.75, y + t * 0.45)
    path.quadTo(x + t * 0.5, y + t * 0.6, x + t * 0.25, y + t * 0.45)
    p.drawPath(path)
    p.drawLine(_pt(x + t / 2, y + t * 0.55), _pt(x + t / 2, y + t * 0.95))
    hoja(p, x + t * 0.5, y + t * 0.6, t * 0.35)


def ramo(p, x, y, t):
    flor(p, x + t * 0.3, y, t * 0.45)
    tulipan(p, x, y + t * 0.2, t * 0.45)
    flor(p, x + t * 0.58, y + t * 0.25, t * 0.4)
    hoja(p, x + t * 0.35, y + t * 0.5, t * 0.3)
    mono(p, x + t * 0.32, y + t * 0.58, t * 0.36)


def esquina_madres(p, x, y, t):
    flor(p, x, y, t * 0.5)
    ramita(p, x + t * 0.45, y + t * 0.05, t * 0.55)
    p.save()
    p.translate(x + t * 0.28, y + t * 0.45)
    p.rotate(90)
    ramita(p, 0, -t * 0.28, t * 0.55)
    p.restore()
    tulipan(p, x + t * 0.5, y + t * 0.45, t * 0.4)


# ── El catálogo ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Adorno:
    """El lenguaje gráfico de una temporada, zona por zona."""

    flanco: Dibujo                      # a los lados de ARTÍCULOS y de los Términos
    greca: tuple[Dibujo, ...]           # la greca antes del Gracias y sobre la caja del total
    esquina: Dibujo                     # las cuatro esquinas de cada caja (se espejea)
    mini: Dibujo                        # el separador entre productos y el remate del resumen
    cabecera: Dibujo                    # a los lados de «Ticket de venta», bajo el logo
    greca_con_linea: bool = True


#: Clave = archivo del dibujo de temporada (`temporada_service.ARCHIVOS`).
ADORNOS: dict[str, Adorno] = {
    "regreso_a_clases": Adorno(
        flanco=mochila, greca=(regla, cuaderno, lapiz, manzana), esquina=esquina_escuela,
        mini=lapiz, cabecera=cuaderno,
    ),
    "independencia": Adorno(
        flanco=sol_azteca, greca=(greca_mexicana,), esquina=esquina_mexico,
        mini=papel_picado, cabecera=papel_picado, greca_con_linea=False,
    ),
    "dia_de_muertos": Adorno(
        flanco=calavera_con_flores, greca=(cempasuchil, calaverita, petalos, vela),
        esquina=esquina_muertos, mini=florecita, cabecera=papel_picado,
    ),
    "halloween": Adorno(
        flanco=calabaza, greca=(murcielago, fantasma, luna, murcielago), esquina=telarana,
        mini=murcielago, cabecera=fantasma,
    ),
    "navidad": Adorno(
        flanco=campana, greca=(estrella_llena, regalo, copo, rama_pino), esquina=esquina_pino,
        mini=estrella_llena, cabecera=regalo,
    ),
    "anio_nuevo": Adorno(
        flanco=corona, greca=(destello, rosca, estrella_fugaz, regalo), esquina=esquina_reyes,
        mini=destello, cabecera=estrella_fugaz,
    ),
    "san_valentin": Adorno(
        flanco=rosa, greca=(corazon, mono, flecha_corazon, corazon_doble), esquina=esquina_valentin,
        mini=corazon, cabecera=mono,
    ),
    "dia_de_las_madres": Adorno(
        flanco=ramo, greca=(flor, hoja, tulipan, ramita), esquina=esquina_madres,
        mini=flor, cabecera=tulipan,
    ),
}

#: Aliases en inglés por si alguien los pide así (prompt de Daniel, 2026-10-10).
ALIAS = {
    "back_to_school": "regreso_a_clases", "mexican_independence": "independencia",
    "christmas": "navidad", "new_year_kings": "anio_nuevo",
    "valentines_day": "san_valentin", "mothers_day": "dia_de_las_madres",
}


def adorno_de(tema: str | None) -> Adorno | None:
    if not tema:
        return None
    return ADORNOS.get(ALIAS.get(tema, tema))


def tema_del_ticket(texto: str) -> str | None:
    """El tema que trae el propio ticket: su marcador `[[IMG:<temporada>]]`.

    Se lee del texto y no de la fecha porque el ticket se arma en una máquina
    y se imprime en otra: lo que mande es lo que viaja en el papel. El logo
    (`[[IMG:logo]]`) no es una temporada y no cuenta."""
    from pos_uniformes.services.temporada_service import (
        MARCADOR_FIN, MARCADOR_INICIO, partir_marcador,
    )

    for linea in (texto or "").split("\n"):
        s = linea.strip()
        if s.startswith(MARCADOR_INICIO) and s.endswith(MARCADOR_FIN):
            nombre, _ = partir_marcador(s[len(MARCADOR_INICIO):-len(MARCADOR_FIN)])
            if nombre in ADORNOS:
                return nombre
    return None


# ── Dónde se adorna ──────────────────────────────────────────────────────────

FLANCOS, GRECA, CABECERA, RESUMEN, DIVISOR, TERMINOS = (
    "flancos", "greca", "cabecera", "resumen", "divisor", "terminos",
)

#: Con más productos que esto, los separadores entre productos salen lisos:
#: en un ticket apretado el adorno estorba más de lo que adorna.
MAX_PRODUCTOS_CON_SEPARADOR = 10


def punto_de_adorno(linea: str, siguiente: str | None) -> str | None:
    """Qué adorno le toca a este renglón del texto, si alguno.

    - `flancos`: ARTÍCULOS, centrado con aire a los dos lados.
    - `terminos`: el título de los términos (flancos + abre el marco).
    - `greca`: el renglón vacío justo antes del «Gracias…» (cierra el marco).
    - `cabecera`: «Ticket de venta», bajo el logo.
    - `resumen`: «N artículos · M piezas», que deja aire a la derecha.
    - `divisor`: el renglón vacío entre el total y los términos.
    """
    s = (linea or "").replace("│", "").replace("║", "").strip()
    sig = (siguiente or "").replace("│", "").strip()
    if s in ("ARTÍCULOS", "ARTICULOS"):
        return FLANCOS
    if s in ("Términos y Condiciones", "Terminos y Condiciones"):
        return TERMINOS
    if s.startswith("Ticket de") or s.startswith("Nota de"):
        return CABECERA
    if " artículos" in s or " articulos" in s or " artículo" in s:
        return RESUMEN
    if not s and sig.startswith("Gracias por"):
        return GRECA
    if not s and sig in ("Términos y Condiciones", "Terminos y Condiciones"):
        return DIVISOR
    return None


def dibujar_flancos(p, adorno: Adorno, x_izq: float, x_der: float, y: float, tam: float,
                    dibujo: Dibujo | None = None) -> None:
    """El motivo a la izquierda y, en espejo, a la derecha."""
    dibujo = dibujo or adorno.flanco
    dibujo(p, x_izq, y, tam)
    _espejo(p, dibujo, x_der, y, tam, eje_x=True)


def dibujar_esquinas(p, adorno: Adorno, x0: float, y0: float, x1: float, y1: float,
                     tam: float) -> None:
    """Las cuatro esquinas de una caja, el motivo espejeado en cada una.

    Se limpia un cuadro blanco detrás para que el motivo se lea sobre la
    línea del marco y no se confunda con ella."""
    from PyQt6.QtGui import QColor

    # Se asoman 7 puntos fuera del marco y el resto queda adentro, en el aire
    # que la tapa y el fondo de la caja ya traen para esto. Más afuera se
    # saldrían del papel; más adentro pisarían el primer renglón.
    s = 7
    for (cx, cy, ex, ey) in ((x0 - s, y0 - s, False, False), (x1 - tam + s, y0 - s, True, False),
                             (x0 - s, y1 - tam + s, False, True), (x1 - tam + s, y1 - tam + s, True, True)):
        p.fillRect(int(cx - 2), int(cy - 2), int(tam + 4), int(tam + 4), QColor("white"))
        if ex or ey:
            _espejo(p, adorno.esquina, cx, cy, tam, eje_x=ex, eje_y=ey)
        else:
            adorno.esquina(p, cx, cy, tam)


def dibujar_mini_en_regla(p, adorno: Adorno, x0: float, x1: float, y_regla: float,
                          tam: float) -> None:
    """Un motivo chico montado al centro de una regla entre productos."""
    from PyQt6.QtGui import QColor

    cx = (x0 + x1) / 2 - tam / 2
    y = y_regla - tam / 2
    p.fillRect(int(cx - 5), int(y - 1), int(tam + 10), int(tam + 2), QColor("white"))
    adorno.mini(p, cx, y, tam)


def dibujar_greca(p, adorno: Adorno, x0: float, x1: float, y: float, tam: float,
                  paso: float | None = None) -> None:
    """Motivos repartidos de x0 a x1, con línea entre ellos si el tema la lleva."""
    from PyQt6.QtGui import QColor

    paso = paso or tam * 2.4
    n = max(1, int((x1 - x0) // paso))
    sobra = (x1 - x0) - n * paso
    x = x0 + sobra / 2
    if adorno.greca_con_linea:
        _pluma(p, grosor=FINO)
        p.drawLine(_pt(x0, y + tam / 2), _pt(x1, y + tam / 2))
    for i in range(n):
        cx = x + i * paso + (paso - tam) / 2
        if adorno.greca_con_linea:
            p.fillRect(int(cx - 3), int(y - 1), int(tam + 6), int(tam + 2), QColor("white"))
        adorno.greca[i % len(adorno.greca)](p, cx, y, tam)


def dibujar_sobre_regla(p, adorno: Adorno, x0: float, x1: float, y_regla: float,
                        tam: float) -> None:
    """Tres motivos montados sobre una regla doble (la caja del total)."""
    from PyQt6.QtGui import QColor

    y = y_regla - tam / 2
    for i, frac in enumerate((0.2, 0.5, 0.8)):
        cx = x0 + (x1 - x0) * frac - tam / 2
        p.fillRect(int(cx - 4), int(y - 1), int(tam + 8), int(tam + 2), QColor("white"))
        adorno.greca[(i * 2) % len(adorno.greca)](p, cx, y, tam)


def dibujar_divisor(p, adorno: Adorno, x0: float, x1: float, y: float, tam: float) -> None:
    """Un remate corto y centrado: línea, motivo, línea. Para los huecos."""
    cx = (x0 + x1) / 2
    _pluma(p, grosor=FINO)
    p.drawLine(_pt(cx - tam * 3.2, y + tam / 2), _pt(cx - tam * 0.8, y + tam / 2))
    p.drawLine(_pt(cx + tam * 0.8, y + tam / 2), _pt(cx + tam * 3.2, y + tam / 2))
    adorno.mini(p, cx - tam / 2, y, tam)


def dibujar_marco(p, adorno: Adorno, x0: float, y0: float, x1: float, y1: float,
                  tam: float, lateral: Dibujo | None = None) -> None:
    """El marco de los términos: línea fina, esquinas y un motivo a media
    altura en cada costado."""
    _pluma(p, grosor=FINO)
    p.drawRect(_rect(x0, y0, x1 - x0, y1 - y0))
    dibujar_esquinas(p, adorno, x0, y0, x1, y1, tam)
    if lateral is not None and (y1 - y0) > tam * 6:
        from PyQt6.QtGui import QColor

        ym = (y0 + y1) / 2 - tam * 0.4
        for cx, ex in ((x0 - tam * 0.4, False), (x1 - tam * 0.4, True)):
            p.fillRect(int(cx - 1), int(ym - 1), int(tam * 0.8 + 2), int(tam * 0.8 + 2), QColor("white"))
            if ex:
                _espejo(p, lateral, cx, ym, tam * 0.8, eje_x=True)
            else:
                lateral(p, cx, ym, tam * 0.8)
