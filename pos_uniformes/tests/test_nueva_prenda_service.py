"""Lo que lee y dice la pantalla «Nueva prenda» (tanda 3, 2026-11-13)."""

from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine

from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import nueva_prenda_service as np
from pos_uniformes.services.catalog_service import CatalogService
from tests._ayuda_mini_caja import MiniCaja

JARAL = "Ignacio Allende (Jaral)"


class EscuelasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.caja = MiniCaja(create_engine("sqlite://"))
        self.s = self.caja.s

    def test_cada_escuela_con_su_nivel_y_sus_prendas(self) -> None:
        escuelas = {(e.nombre, e.nivel): e for e in np.escuelas_para_elegir(self.s)}
        self.assertEqual(escuelas[("Ignacio Allende", "Primaria")].prendas, 7)
        self.assertEqual(escuelas[(JARAL, "Primaria")].prendas, 4)
        self.assertEqual(escuelas[(JARAL, "Primaria")].texto, f"{JARAL} · Primaria · 4 prendas")
        self.assertEqual(escuelas[("Técnica 18", "Secundaria")].detalle, "Secundaria · 1 prenda")

    def test_escuela_sin_prendas_sale_sin_nivel(self) -> None:
        self.caja._escuela("Rancho Nuevo")
        self.s.commit()
        nueva = [e for e in np.escuelas_para_elegir(self.s) if e.nombre == "Rancho Nuevo"]
        self.assertEqual(len(nueva), 1)
        self.assertIsNone(nueva[0].nivel)
        self.assertEqual(nueva[0].detalle, "sin prendas todavía")

    def test_escuela_con_dos_niveles_sale_dos_veces(self) -> None:
        self.caja.prod("Benito Juárez", "Chamarra", nivel="Secundaria")
        self.s.commit()
        niveles = sorted(e.nivel for e in np.escuelas_para_elegir(self.s) if e.nombre == "Benito Juárez")
        self.assertEqual(niveles, ["Primaria", "Secundaria"])

    def test_filtrar_sin_acentos_ni_mayusculas(self) -> None:
        escuelas = np.escuelas_para_elegir(self.s)
        self.assertEqual([e.nombre for e in np.filtrar_escuelas(escuelas, "ignacio JARAL")], [JARAL])
        self.assertEqual([e.nombre for e in np.filtrar_escuelas(escuelas, "tecnica")], ["Técnica 18"])
        self.assertEqual([e.nombre for e in np.filtrar_escuelas(escuelas, "benito juarez")], ["Benito Juárez"])
        self.assertEqual(len(np.filtrar_escuelas(escuelas, "  ")), len(escuelas))
        self.assertEqual(
            sorted(e.nombre for e in np.filtrar_escuelas(escuelas, "allende")), ["Ignacio Allende", JARAL]
        )

    def test_ultimas_altas_las_mas_recientes_primero(self) -> None:
        with patch.object(CatalogService, "_avisar_busqueda"):
            plan = alta.planear_desde_modelo(self.s, JARAL, "Pants Suelto", color="Gris")
            alta.aplicar(self.s, plan, self.caja.admin, commit=True)
        ultimas = np.ultimas_altas(self.s)
        self.assertEqual(len(ultimas), np.ULTIMAS_ALTAS)
        self.assertEqual(ultimas[0].nombre, "Pants Suelto Ignacio Allende (Jaral)")
        self.assertEqual(ultimas[0].tipo_pieza, "Pants Suelto")
        self.assertEqual(ultimas[0].nivel, "Primaria")

    def test_opciones_listas_cerradas(self) -> None:
        ops = np.opciones(self.s)
        self.assertEqual(ops.colores[0], "Sin color")
        self.assertIn("Gris", ops.colores)
        self.assertIn("Blanco", ops.colores)
        self.assertNotIn("Blanca", ops.colores)
        self.assertEqual(ops.marcas, ("Sin marca",))
        self.assertEqual(ops.generos, ("Unisex",))
        self.assertEqual(ops.escudos, ("Con Escudo",))
        self.assertEqual(ops.niveles, ("Primaria", "Secundaria"))
        self.assertIn("Pants Suelto", ops.piezas)
        self.assertGreater(ops.usos_color["Gris"], 0)


class _T:
    def __init__(self, talla, precio, error=""):
        self.talla, self.precio, self.error = talla, None if precio is None else Decimal(precio), error


class _P:
    def __init__(self, escuela, tallas, errores=(), grupo="Deportivo", resumen=""):
        self.escuela, self.tallas, self.errores = escuela, tallas, list(errores)
        self.tipo_pieza, self.nombre_sin_escuela = "Pants Suelto", "Pants Suelto"
        self.grupo, self.grupo_previsto, self.ligar, self.resumen = grupo, grupo, True, resumen


class TextosTests(unittest.TestCase):
    def test_boton(self) -> None:
        diez = [_T(str(n), 245) for n in range(10)]
        self.assertEqual(np.texto_boton([_P("A", diez)]), "Dar de alta 10 tallas")
        self.assertEqual(np.texto_boton([_P("A", diez[:1])]), "Dar de alta 1 talla")
        self.assertEqual(np.texto_boton([_P("A", diez), _P("B", diez), _P("C", diez)]),
                         "Dar de alta 3 prendas (30 tallas)")
        self.assertEqual(np.texto_boton([_P("A", [])]), "Dar de alta")

    def test_nota_bloqueo(self) -> None:
        ok = [_T("4", 245), _T("6", 245)]
        self.assertEqual(np.nota_bloqueo([_P("A", ok)]), "")
        self.assertEqual(np.nota_bloqueo([_P("A", [])]), "Marca al menos una talla.")
        faltan = [_T("4", None, "Falta el precio."), _T("6", None, "Falta el precio."), _T("8", 245)]
        self.assertEqual(np.nota_bloqueo([_P("A", faltan)]), "Falta precio en 2 tallas.")
        cero = [_T("4", 0, "El precio no puede quedar en $0."), _T("6", 245)]
        self.assertEqual(np.nota_bloqueo([_P("A", cero)]), "La talla 4 está en $0.")
        self.assertEqual(np.nota_bloqueo([_P("A", ok), _P("B", ok, ["Ya existe «X»."])]), "B: Ya existe «X».")

    def test_frase_confirmar_varias_escuelas(self) -> None:
        tallas = [_T("4", 245), _T("GD", 295)]
        uno = _P("A", tallas, resumen="Se crean 2 tallas de …")
        self.assertEqual(np.frase_confirmar([uno]), "Se crean 2 tallas de …")
        self.assertEqual(
            np.frase_confirmar([_P("A", tallas), _P("B", tallas), _P("C", tallas)]),
            "Se crean 3 prendas de Pants Suelto (6 tallas), una para cada escuela: A, B y C, "
            "de $245 a $295. Quedan en su uniforme Deportivo.",
        )

    def test_detalle_confirmar(self) -> None:
        a = _P("Jaral", [_T("4", 245), _T("6", 245)])
        a.receta_texto = "Receta Chamarra: se completa."
        a.tallas[0].llegan, a.tallas[1].llegan = 4, 2
        b = _P("B", [_T("4", 245)])
        b.receta_texto = ""
        b.tallas[0].llegan = 0
        self.assertEqual(np.detalle_confirmar([a, b]),
                         "Receta Chamarra: se completa.\nLlegan 6 piezas de Jaral: entran como entrada normal.")
        a.receta_texto, a.tallas[1].llegan = "", 0
        a.tallas[0].llegan = 1
        self.assertEqual(np.detalle_confirmar([a]), "Llega 1 pieza de Jaral: entra como entrada normal.")
        self.assertEqual(np.detalle_confirmar([]), "")

    def test_frase_listo(self) -> None:
        t = [alta.TallaCreada(1, "SKU1", "4", "Gris", Decimal(245)),
             alta.TallaCreada(2, "SKU2", "GD", "Gris", Decimal(295))]
        uno = alta.ResultadoAlta(productos=(alta.ProductoCreado(
            1, "Pants Suelto Jaral", "Jaral", tuple(t), uniforme="Deportivo",
            recetas=("Chamarra Deportiva Jaral: Pants 2pz + Pants Suelto (se completó)",)),))
        self.assertEqual(
            np.frase_listo(uno),
            "2 tallas de Pants Suelto Jaral, de $245 a $295. "
            "Quedó en su uniforme Deportivo y en la receta de Chamarra Deportiva Jaral.",
        )
        self.assertEqual(np.frase_listo(alta.ResultadoAlta()), "")

    def test_conteos_dicen_de_que_es_el_total(self) -> None:
        # «Le falta», la talla gris y «Hacer la misma…» cuentan cosas distintas:
        # cada frase nombra su total.
        self.assertEqual(np.texto_pieza_comparada(4, 10), "la tienen 4 de las 10 escuelas")
        self.assertEqual(np.texto_pieza_comparada(1, 1), "la tienen 1 de 1 escuela")
        t = alta.TallaPlan(talla="EXG", precio=None, texto_cobertura="la tienen 1 de 4",
                           cobertura_tienen=1, cobertura_total=4)
        self.assertEqual(np.texto_cobertura_talla(t, "Pants Suelto"), "la tienen 1 de las 4 prendas de Pants Suelto")
        self.assertEqual(np.texto_cobertura_talla(t, None), "la tienen 1 de las 4 prendas")
        sin = alta.TallaPlan(talla="18", precio=None)
        self.assertEqual(np.texto_cobertura_talla(sin, "Pants Suelto"), "")
        self.assertEqual(np.texto_le_falta_a(6, "Primaria"), "le falta a 6 escuelas de primaria")
        self.assertEqual(np.texto_le_falta_a(1, None), "le falta a 1 escuela")

    def test_fecha_corta(self) -> None:
        self.assertEqual(np.fecha_corta(datetime(2026, 11, 8)), "8-nov")
        self.assertEqual(np.fecha_corta(None), "")


if __name__ == "__main__":
    unittest.main()
