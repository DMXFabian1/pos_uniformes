"""El corte de caja es un tipo de trabajo propio, no un ticket más.

Daniel: "el corte solo debe salir en el satélite, no en la principal, ya que
por privacidad no queda a la mano". Desde que hay DOS PCs con impresora de
tickets, un corte encolado lo podía reclamar cualquiera de las dos — y el
corte lleva la venta del día, los pagos y los retiros.

Se resuelve con un tipo propio en vez de con un "destino" en cada trabajo: así
cada PC dice si imprime cortes en la misma lista donde ya dice si imprime
tickets o etiquetas, y no hay que inventar un nombre de máquina que luego
alguien renombre.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
"""

from __future__ import annotations

from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres 12+ admite ADD VALUE dentro de una transacción mientras el valor
    # nuevo no se USE en la misma; aquí solo se agrega. IF NOT EXISTS lo hace
    # repetible.
    op.execute("ALTER TYPE tipo_trabajo ADD VALUE IF NOT EXISTS 'CORTE'")


def downgrade() -> None:
    # Postgres no sabe quitar un valor de un enum. Dejarlo no estorba: ningún
    # trabajo nuevo lo usaría si se vuelve atrás, y borrar el tipo entero sería
    # mucho peor que un valor de más.
    pass
