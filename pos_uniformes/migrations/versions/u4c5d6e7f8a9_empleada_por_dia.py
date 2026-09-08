"""empleada_por_dia

Empleadas que solo trabajan ciertos días (p.ej. Naye, fines de semana):
`empleada_horario.modo_pago` = "semana" | "por_dia" y `dias_trabajo` (lista de
weekdays). En modo por_dia cobran por día trabajado (sueldo_base/6) al
terminar sus días. `empleada_pago` guarda días y tarifa para el desglose.
"""

revision = 'u4c5d6e7f8a9'
down_revision = 't3b4c5d6e7f8'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column('empleada_horario', sa.Column('modo_pago', sa.String(20), nullable=False, server_default='semana'))
    op.add_column('empleada_horario', sa.Column('dias_trabajo', sa.JSON(), nullable=True))
    op.add_column('empleada_pago', sa.Column('dias_trabajados', sa.Integer(), nullable=True))
    op.add_column('empleada_pago', sa.Column('tarifa_dia', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('empleada_pago', 'tarifa_dia')
    op.drop_column('empleada_pago', 'dias_trabajados')
    op.drop_column('empleada_horario', 'dias_trabajo')
    op.drop_column('empleada_horario', 'modo_pago')
