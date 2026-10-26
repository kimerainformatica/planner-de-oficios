"""correções do admin: resposta/recebimento desfeito fica no histórico como anulado

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("historico_status", sa.Column("anulado_em", sa.DateTime(), nullable=True))
    op.add_column("historico_status", sa.Column("anulado_por_id", sa.Integer(), nullable=True))
    op.add_column("historico_status", sa.Column("anulado_motivo", sa.String(length=500), nullable=True))
    op.create_foreign_key("fk_historico_anulado_por", "historico_status", "usuarios", ["anulado_por_id"], ["id"],
                          ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_historico_anulado_por", "historico_status", type_="foreignkey")
    op.drop_column("historico_status", "anulado_motivo")
    op.drop_column("historico_status", "anulado_por_id")
    op.drop_column("historico_status", "anulado_em")
