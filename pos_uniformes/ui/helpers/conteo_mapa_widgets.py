"""Piezas del mapa de conteos con los mismos widgets del kiosko.

Tarjetas `libretaCard` (redondeadas, crema), títulos `libretaSeccion`, la
barra pintada a mano (verde/ámbar/gris) y fichas de talla como etiquetas
redondeadas. Todo puro: recibe los dicts de `conteo_mapa_service` y emite
señales; el widget grande (`ConteoMapaWidget`) decide qué capa mostrar.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

VERDE, AMBAR, GRIS, FONDO = "#3d6b2f", "#c98a2b", "#b9b0a4", "#e6ddd0"
COLOR_ESTADO = {"al_dia": VERDE, "vieja": AMBAR, "nunca": GRIS}
FONDO_TALLA = {"al_dia": "#d9ecd0", "vieja": "#f6e3c6", "nunca": "#eee9e1"}
TEXTO_TALLA = {"al_dia": VERDE, "vieja": "#8a5a12", "nunca": "#6f675c"}
_TXT = "background: transparent;"
ORDEN_NIVELES = ["Preescolar", "Primaria", "Secundaria", "Preparatoria", "Varios niveles", "Sin nivel"]


def texto_cifras(c: dict) -> str:
    u = c.get("ultimo_dias")
    cuando = "nunca" if u is None else ("hoy" if u == 0 else f"hace {u} d")
    return f"{c.get('pct_al_dia', 0)}% al día · {cuando}"


class Semaforo(QWidget):
    """Barra de tres tramos (al día / viejas / nunca) con puntas redondeadas."""

    def __init__(self, cifras: dict, *, alto: int = 9, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._c = cifras
        self.setFixedHeight(alto)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        ruta = QPainterPath()
        ruta.addRoundedRect(0, 0, w, h, h / 2, h / 2)
        p.setClipPath(ruta)
        p.fillRect(0, 0, w, h, QColor(FONDO))
        total = self._c.get("tallas") or 0
        x = 0.0
        if total:
            for clave, color in (("al_dia", VERDE), ("viejas", AMBAR), ("nunca", GRIS)):
                ancho = w * self._c.get(clave, 0) / total
                if ancho > 0:
                    p.fillRect(int(x), 0, int(round(ancho)) + 1, h, QColor(color))
                x += ancho
        p.end()


class Leyenda(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ly = QHBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(12)
        for color, texto in ((VERDE, "al día"), (AMBAR, "ya venció"), (GRIS, "nunca contada"), ("#f4c48a", "en proceso")):
            punto = QLabel()
            punto.setFixedSize(10, 10)
            punto.setStyleSheet(f"background: {color}; border-radius: 3px;")
            ly.addWidget(punto)
            t = QLabel(texto)
            t.setStyleSheet(f"font-size: 11px; color: #8a8177; {_TXT}")
            ly.addWidget(t)
        ly.addStretch()


class Mosaico(QFrame):
    """Una escuela o un tipo de básicos. Clic → `elegido(clave)`."""

    elegido = pyqtSignal(str)

    def __init__(self, cifras: dict, clave: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clave = clave
        self.setObjectName("libretaCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        color = COLOR_ESTADO.get(cifras.get("estado", "nunca"), GRIS)
        fondo = "#fff4e5" if cifras.get("en_proceso") else "#fbf8f2"
        borde = "#e0b27a" if cifras.get("en_proceso") else "#ddd0c0"
        self.setStyleSheet(
            f"QFrame#libretaCard {{ background: {fondo}; border: 1px solid {borde}; border-left: 6px solid {color}; border-radius: 14px; }}"
            f"QFrame#libretaCard:hover {{ border: 1px solid #a84f2d; border-left: 6px solid {color}; }}"
        )
        ly = QVBoxLayout(self)
        ly.setContentsMargins(14, 10, 14, 10)
        ly.setSpacing(5)
        nombre = QLabel(cifras.get("nombre", ""))
        nombre.setWordWrap(True)
        nombre.setStyleSheet(f"font-size: 14px; font-weight: 800; color: #2c2a27; {_TXT}")
        ly.addWidget(nombre)
        ly.addWidget(Semaforo(cifras))
        linea = texto_cifras(cifras)
        if cifras.get("quien") and not cifras.get("en_proceso"):
            linea += f" · {cifras['quien']}"
        sub = QLabel(linea)
        sub.setStyleSheet(f"font-size: 11px; color: #8a8177; {_TXT}")
        ly.addWidget(sub)
        if cifras.get("en_proceso"):
            proc = QLabel(f"En proceso · {cifras['en_proceso']}")
            proc.setWordWrap(True)
            proc.setStyleSheet(f"font-size: 11px; font-weight: 800; color: #b45309; {_TXT}")
            ly.addWidget(proc)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.elegido.emit(self._clave)
        super().mousePressEvent(e)


def titulo_seccion(texto: str) -> QLabel:
    t = QLabel(texto.upper())
    t.setObjectName("libretaSeccion")
    return t


class CapaMapa(QWidget):
    """Capa 1: total + mosaicos por nivel + básicos por tipo."""

    elegido = pyqtSignal(str)

    def __init__(self, datos: dict, *, columnas: int = 4, filtro: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(8)
        t = datos["total"]
        total = QFrame()
        total.setObjectName("libretaCard")
        tl = QVBoxLayout(total)
        tl.setContentsMargins(16, 12, 16, 12)
        tl.setSpacing(6)
        enc = QLabel(
            f"<b style='font-size:15px'>Toda la tienda · {t['tallas']:,} tallas</b>"
            f"&nbsp;&nbsp;<span style='font-size:12px;color:#8a8177'>{t['al_dia']:,} al día · {t['viejas']:,} viejas · {t['nunca']:,} nunca</span>"
        )
        enc.setStyleSheet(f"color: #2c2a27; {_TXT}")
        tl.addWidget(enc)
        tl.addWidget(Semaforo(t, alto=11))
        tl.addWidget(Leyenda())
        ly.addWidget(total)

        q = filtro.strip().lower()
        escuelas = [e for e in datos["escuelas"] if not q or q in e["nombre"].lower()]
        niveles = sorted({e["nivel"] for e in escuelas}, key=lambda n: (ORDEN_NIVELES.index(n) if n in ORDEN_NIVELES else 99, n))
        for n in niveles:
            lista = [e for e in escuelas if e["nivel"] == n]
            ly.addWidget(titulo_seccion(f"{n}  ·  {len(lista)}"))
            ly.addWidget(self._rejilla([(e, f"e{e['escuela_id']}") for e in lista], columnas))
        if not q and datos.get("basicos"):
            ly.addWidget(titulo_seccion(f"Básicos  ·  {len(datos['basicos'])} tipos"))
            ly.addWidget(self._rejilla([({**b, "nombre": b["tipo_pieza"]}, f"b{b['tipo_pieza']}") for b in datos["basicos"]], columnas))
        if q and not escuelas:
            vacio = QLabel("Ninguna escuela con ese nombre.")
            vacio.setObjectName("libretaPanelVacio")
            ly.addWidget(vacio)
        ly.addStretch()

    def _rejilla(self, items: list[tuple[dict, str]], columnas: int) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(10)
        for i, (cifras, clave) in enumerate(items):
            m = Mosaico(cifras, clave)
            m.elegido.connect(self.elegido)
            g.addWidget(m, i // columnas, i % columnas)
        for c in range(columnas):
            g.setColumnStretch(c, 1)
        return w


class Prenda(QFrame):
    """Capa 2/3: una prenda con su barra; al tocarla se despliegan sus tallas."""

    def __init__(self, p: dict, *, abierta: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("libretaCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        ly = QVBoxLayout(self)
        ly.setContentsMargins(16, 10, 16, 10)
        ly.setSpacing(6)
        fila = QHBoxLayout()
        flecha = QLabel("▾" if abierta else "▸")
        flecha.setStyleSheet(f"font-size: 14px; color: #8a4326; {_TXT}")
        fila.addWidget(flecha)
        nombre = QLabel(p["nombre"])
        nombre.setStyleSheet(f"font-size: 14px; font-weight: 800; color: #2c2a27; {_TXT}")
        fila.addWidget(nombre)
        tipo = f"{p['tipo_pieza']} · " if p.get("tipo_pieza") else ""
        sub = QLabel(f"{tipo}{p['tallas']} tallas · {texto_cifras(p)}")
        sub.setStyleSheet(f"font-size: 12px; color: #8a8177; {_TXT}")
        fila.addWidget(sub, 1)
        ly.addLayout(fila)
        ly.addWidget(Semaforo(p))
        self._tallas = QWidget()
        g = QGridLayout(self._tallas)
        g.setContentsMargins(0, 4, 0, 0)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(6)
        for i, t in enumerate(p.get("tallas_detalle", [])):
            g.addWidget(self._ficha(t), i // 8, i % 8)
        g.setColumnStretch(8, 1)
        self._tallas.setVisible(abierta)
        ly.addWidget(self._tallas)

    @staticmethod
    def _ficha(t: dict) -> QLabel:
        est = t.get("estado", "nunca")
        color = (t.get("color") or "").strip()
        if color.lower() in ("sin color", "unico", "único"):
            color = ""
        dias = "nunca" if t.get("dias") is None else ("hoy" if t["dias"] == 0 else f"hace {t['dias']} d")
        f = QLabel(
            f"<b>{t['talla']}{(' ' + color) if color else ''}</b><br>"
            f"<span style='font-size:10px'>{dias} · {t.get('stock', 0)} pz</span>"
        )
        f.setAlignment(Qt.AlignmentFlag.AlignLeft)
        f.setStyleSheet(f"background: {FONDO_TALLA[est]}; color: {TEXTO_TALLA[est]}; border-radius: 8px; padding: 5px 9px; font-size: 13px;")
        return f

    def alternar(self) -> bool:
        """Despliega/pliega las tallas. Devuelve si quedaron desplegadas."""
        self._tallas.setVisible(self._tallas.isHidden())
        return not self._tallas.isHidden()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self.alternar()
        super().mousePressEvent(e)


class CapaDetalle(QWidget):
    """Una escuela o un tipo de básicos: encabezado + sus prendas."""

    volver = pyqtSignal()

    def __init__(self, d: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QPushButton

        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(8)
        enc = QFrame()
        enc.setObjectName("libretaCard")
        el = QVBoxLayout(enc)
        el.setContentsMargins(16, 12, 16, 12)
        el.setSpacing(6)
        fila = QHBoxLayout()
        atras = QPushButton("‹ Mapa")
        atras.setObjectName("secondaryButton")
        atras.setAutoDefault(False)
        atras.clicked.connect(self.volver)
        fila.addWidget(atras)
        titulo = QLabel(d["titulo"])
        titulo.setStyleSheet(f"font-size: 18px; font-weight: 800; color: #2c2a27; {_TXT}")
        fila.addWidget(titulo)
        sub = QLabel(f"{d['tallas']} tallas · {texto_cifras(d)}")
        sub.setStyleSheet(f"font-size: 12px; color: #8a8177; {_TXT}")
        fila.addWidget(sub, 1)
        el.addLayout(fila)
        el.addWidget(Semaforo(d, alto=11))
        el.addWidget(Leyenda())
        ly.addWidget(enc)
        pista = QLabel("Toca una prenda para ver sus tallas.")
        pista.setObjectName("libretaSubtitulo")
        ly.addWidget(pista)
        self.prendas: list[Prenda] = []
        for p in d.get("prendas", []):
            w = Prenda(p)
            self.prendas.append(w)
            ly.addWidget(w)
        if not d.get("prendas"):
            vacio = QLabel("Sin prendas para contar.")
            vacio.setObjectName("libretaPanelVacio")
            ly.addWidget(vacio)
        ly.addStretch()
