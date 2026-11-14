"""La ficha «Así queda» de «Nueva prenda» (tanda 3 del alta, 2026-11-13).

A la derecha, como la ficha de Inventario: el nombre exacto que se guarda,
la escuela, cuántas tallas y de cuánto a cuánto, el color, en qué uniforme
queda, qué pasa con la receta y, solo si hay algo real, los avisos. Nada en
rojo antes de empezar: los errores de cada talla se ven en la tabla, aquí
solo los de toda la prenda.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from pos_uniformes.services import nueva_prenda_service as np_service


def _etiqueta(nombre: str, texto: str = "", *, envolver: bool = True) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName(nombre)
    etiqueta.setWordWrap(envolver)
    return etiqueta


def _repulir(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class FichaAsiQueda(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("npFicha")
        caja = QVBoxLayout(self)
        caja.setContentsMargins(18, 16, 18, 16)
        caja.setSpacing(10)
        caja.addWidget(_etiqueta("npSeccion", "ASÍ QUEDA", envolver=False))

        self.total = QFrame()
        self.total.setObjectName("npFichaTotal")
        caja_total = QVBoxLayout(self.total)
        caja_total.setContentsMargins(16, 14, 16, 14)
        caja_total.setSpacing(4)
        self.nombre = _etiqueta("npFichaNombre")
        self.sub = _etiqueta("npFichaSub")
        self.rango = _etiqueta("npFichaRango")
        for w in (self.nombre, self.sub, self.rango):
            caja_total.addWidget(w)
        caja.addWidget(self.total)

        self.color = _etiqueta("npFichaLinea")
        self.uniforme = _etiqueta("npFichaLinea")
        self.receta = _etiqueta("npFichaLinea")
        self.llegan = _etiqueta("npFichaLinea")
        self.otras = _etiqueta("npFichaLinea")
        self.titulo_avisos = _etiqueta("npSeccion", "AVISOS", envolver=False)
        self.avisos = _etiqueta("npFichaLinea")
        self.avisos.setProperty("tono", "warning")
        self.errores = _etiqueta("npFichaLinea")
        self.errores.setProperty("tono", "danger")
        for w in (self.color, self.uniforme, self.receta, self.llegan, self.otras,
                  self.titulo_avisos, self.avisos, self.errores):
            caja.addWidget(w)
        caja.addStretch(1)

    @staticmethod
    def _poner(etiqueta: QLabel, texto: str) -> None:
        etiqueta.setText(texto)
        etiqueta.setVisible(bool(texto))

    def mostrar(self, planes) -> None:
        if not planes:
            return
        plan = planes[0]
        self.nombre.setText(plan.nombre or plan.nombre_sin_escuela)
        sub = " · ".join(p for p in (plan.escuela, plan.nivel) if p)
        self.sub.setText(sub)
        self.rango.setText(plan.texto_rango)
        color = plan.color if plan.color and plan.color != np_service.SIN_COLOR else "sin color"
        self._poner(self.color, f"Color: {color}")
        grupo = (plan.grupo or plan.grupo_previsto) if plan.ligar else None
        self._poner(self.uniforme, f"Queda en su uniforme: {grupo}" if grupo else "")
        self._poner(self.receta, plan.receta_texto)
        llegan = sum(int(t.llegan or 0) for t in plan.tallas)
        self._poner(self.llegan, f"Llegan {llegan} {'pieza' if llegan == 1 else 'piezas'}: entran como entrada normal."
                    if llegan else "")
        otras = [p for p in planes[1:]]
        if otras:
            nombres = "\n".join(f"• {p.nombre}" for p in otras)
            self._poner(self.otras, f"También para {len(otras)} {'escuela' if len(otras) == 1 else 'escuelas'} más:\n{nombres}")
        else:
            self._poner(self.otras, "")
        avisos = list(dict.fromkeys(a for p in planes for a in p.avisos))
        self._poner(self.avisos, "\n".join(f"⚠ {a}" for a in avisos))
        errores = []
        for p in planes:
            for e in p.errores:
                errores.append(e if p is plan else f"{p.escuela}: {e}")
        self._poner(self.errores, "\n".join(dict.fromkeys(errores)))
        self.titulo_avisos.setVisible(bool(avisos or errores))
        for w in (self.avisos, self.errores):
            _repulir(w)

    def textos(self) -> str:
        """Todo lo visible, en texto (para las pruebas)."""
        partes = [self.nombre.text(), self.sub.text(), self.rango.text()]
        for w in (self.color, self.uniforme, self.receta, self.llegan, self.otras, self.avisos, self.errores):
            if not w.isHidden():
                partes.append(w.text())
        return "\n".join(partes)


__all__ = ["FichaAsiQueda"]
