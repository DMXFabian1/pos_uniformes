"""¿Dónde está parado cada préstamo, y qué se le va a descontar?

Daniel vio que un préstamo no se le bajaba del sueldo. Hay dos razones
posibles y se ven distinto desde afuera: que el préstamo se quedó en
"pedido" (nadie lo aprobó, así que no se cobra y está bien), o que la
base no tiene la tabla todavía (y entonces el programa devuelve cero
callado, que es el caso que hay que descubrir).
"""
from __future__ import annotations

from decimal import Decimal


def main() -> int:
    from pos_uniformes.database.connection import get_session
    from pos_uniformes.database.models import PrestamoEmpleada
    from pos_uniformes.services import nomina_service, prestamos_service

    with get_session() as session:
        try:
            filas = list(session.query(PrestamoEmpleada).order_by(PrestamoEmpleada.id).all())
        except Exception as exc:  # noqa: BLE001
            print("LA BASE NO TIENE LA TABLA prestamo_empleada.")
            print("Eso explica todo: el programa devuelve cero y no descuenta nada.")
            print(f"Falta correr la migración. Detalle: {exc}")
            return 1

        if not filas:
            print("No hay ningún préstamo registrado en la base.")
        else:
            print(f"{len(filas)} préstamo(s):")
            for p in filas:
                cuando = p.created_at.strftime("%d/%m/%Y %H:%M") if p.created_at else "?"
                print(
                    f"  #{p.id}  {p.employee_code:8} {p.employee_name[:20]:20} "
                    f"${Decimal(str(p.monto)):>9,.2f}  {p.estado.upper():10} {cuando}"
                    + (f"  (resolvió {p.resuelto_por})" if p.resuelto_por else "")
                )

        print()
        print("Lo que se le descontaría en el próximo pago:")
        codigos = sorted({p.employee_code for p in filas})
        for code in codigos:
            porcobrar = prestamos_service.total_por_cobrar(session, code)
            det = nomina_service.pago_pendiente(session, code)
            print(
                f"  {code:8} préstamo ${porcobrar:>9,.2f}   "
                f"a pagar ${det.total:>9,.2f}   (el detalle trae ${det.prestamos:,.2f})"
            )
            if porcobrar and not det.prestamos:
                print("    OJO: hay préstamo por cobrar y el pago no lo trae. Eso es el bug.")

        print()
        print("Y lo que el corte va a apartar para pagarle:")
        for a in nomina_service.avisos_de_pago(session):
            prest = Decimal(str(getattr(a, "prestamos", 0) or 0))
            print(f"  {a.employee_code:8} ${Decimal(str(a.total_estimado)):>9,.2f}  (ya sin ${prest:,.2f} de préstamo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
