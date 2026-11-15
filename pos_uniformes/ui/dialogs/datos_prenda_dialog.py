"""«📝 Editar datos» de la prenda (tanda 5 del alta, 2026-11-15).

La ventanita hermana de «✏️ Corregir prenda»: marca, categoría, tipo de
prenda, pieza, atributo, nivel, escuela, género, escudo, ubicación,
descripción y el costo de todas las tallas. Todas las listas son cerradas
(no se escribe: se elige). Reemplaza al editor viejo de la prenda.

Las reglas viven en `services/datos_prenda_service.py`; aquí solo hay
pantalla. Cancelar no cambia nada.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QGridLayout, QLineEdit, QWidget

from pos_uniformes.services import datos_prenda_service as dp
from pos_uniformes.ui.dialogs.ficha_prenda_dialogs import _etiqueta, _poner, _primer_error, _Ventanita

SUB_DATOS = ("Lo que no es nombre, color ni precio. Se elige de la lista; los códigos, "
             "los precios y la existencia se quedan igual.")
SIN_VALOR = "—"

#: Orden de la rejilla (dos columnas).
CAMPOS_LISTA = ("marca", "categoria", "tipo_prenda", "tipo_pieza", "atributo", "nivel_educativo",
                "escuela", "genero", "escudo")


class DatosPrendaDialog(_Ventanita):
    ANCHO = 660

    def __init__(self, parent: QWidget | None, *, session_factory, usuario_id: int, producto_id: int,
                 **kw) -> None:
        super().__init__(parent, session_factory=session_factory, usuario_id=usuario_id,
                         titulo="Editar datos de la prenda", **kw)
        self.producto_id = int(producto_id)
        self.ops: dp.OpcionesDatos = self._con_sesion(dp.opciones_datos)
        self.plan: dp.PlanDatos = self._con_sesion(lambda s: dp.planear_datos(s, self.producto_id))
        antes = self.plan.antes
        self.sub.setText(SUB_DATOS)
        self.nombre = _etiqueta("npFrase", self.plan.nombre_antes)
        self.cuerpo.addWidget(self.nombre)

        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(12)
        rejilla.setVerticalSpacing(6)
        self.combos: dict[str, QComboBox] = {}
        for i, campo in enumerate(CAMPOS_LISTA):
            combo = QComboBox()
            combo.setObjectName("npCampo")
            combo.setAccessibleName(dp.ROTULOS[campo])
            if campo == "genero":
                opciones = list(self.ops.generos)
            elif campo == "escudo":
                opciones = list(self.ops.escudos)
            else:
                opciones = list(self.ops.listas[campo])
            if campo in dp.OPCIONALES:
                combo.addItem(SIN_VALOR, "")
            for valor in opciones:
                combo.addItem(valor, valor)
            if antes[campo] and combo.findData(antes[campo]) < 0:
                combo.addItem(antes[campo], antes[campo])  # un valor viejo (o inactivo) se respeta
            combo.setCurrentIndex(max(0, combo.findData(antes[campo])))
            combo.currentIndexChanged.connect(lambda _i: self.replanear())
            fila, col = divmod(i, 2)
            rejilla.addWidget(_etiqueta("npEtiqueta", dp.ROTULOS[campo].upper(), envolver=False), fila, col * 2)
            rejilla.addWidget(combo, fila, col * 2 + 1)
            self.combos[campo] = combo
        fila = (len(CAMPOS_LISTA) + 1) // 2
        self.ubicacion = QLineEdit(antes["ubicacion"])
        self.costo = QLineEdit()
        self.costo.setPlaceholderText("Igual para todas las tallas (opcional)")
        self.descripcion = QLineEdit(antes["descripcion"])
        for campo in (self.ubicacion, self.costo, self.descripcion):
            campo.setObjectName("npCampo")
            campo.textEdited.connect(lambda _t: self.rebote.start())
        self.costo.setAccessibleName("Costo")
        rejilla.addWidget(_etiqueta("npEtiqueta", "UBICACIÓN", envolver=False), fila, 0)
        rejilla.addWidget(self.ubicacion, fila, 1)
        rejilla.addWidget(_etiqueta("npEtiqueta", "COSTO", envolver=False), fila, 2)
        rejilla.addWidget(self.costo, fila, 3)
        rejilla.addWidget(_etiqueta("npEtiqueta", "DESCRIPCIÓN", envolver=False), fila + 1, 0)
        rejilla.addWidget(self.descripcion, fila + 1, 1, 1, 3)
        rejilla.setColumnStretch(1, 1)
        rejilla.setColumnStretch(3, 1)
        self.cuerpo.addLayout(rejilla)

        self.cuerpo.addWidget(_etiqueta("npSeccion", "ASÍ QUEDA", envolver=False))
        self.frase = _etiqueta("npFichaLinea")
        self.avisos = _etiqueta("npNota")
        self.cuerpo.addWidget(self.frase)
        self.cuerpo.addWidget(self.avisos)
        self.replanear()

    def cambios(self) -> dict[str, str]:
        datos = {campo: str(combo.currentData() or "") for campo, combo in self.combos.items()}
        datos["ubicacion"] = self.ubicacion.text()
        datos["descripcion"] = self.descripcion.text()
        return {k: v for k, v in datos.items() if v != self.plan.antes.get(k)}

    def replanear(self) -> None:
        self.plan = self._con_sesion(lambda s: dp.planear_datos(
            s, self.producto_id, cambios=self.cambios(), costo=self.costo.text()))
        plan = self.plan
        self.nombre.setText(plan.nombre)
        self.frase.setText(plan.resumen)
        _poner(self.avisos, " ".join(plan.avisos))
        bloqueo = _primer_error(plan.errores) or ("" if plan.hay_cambios else "Sin cambios todavía.")
        self._pintar_barra("Guardar datos", bloqueo)

    def guardar(self):
        plan = self.plan
        return self._con_sesion(lambda s: dp.aplicar_datos(s, plan, self._usuario(s), commit=True))


__all__ = ["DatosPrendaDialog"]
