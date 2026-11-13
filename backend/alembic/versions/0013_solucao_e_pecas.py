"""tempo de solução do chamado e solicitação de peças/equipamentos (ofício do Planner ligado ao chamado)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

TIPOS_ANTES = ("ABERTURA", "COMENTARIO", "DIAGNOSTICO", "RELATORIO", "ASSUMIDO", "CONCLUSAO", "REABERTURA",
               "CANCELAMENTO")
TIPOS_DEPOIS = (*TIPOS_ANTES, "OFICIO")


def upgrade() -> None:
    op.add_column("chamados", sa.Column("solucao_horas_uteis", sa.Float()))
    op.add_column("chamados", sa.Column("solucao_horas_corridas", sa.Float()))
    op.alter_column("chamado_interacoes", "tipo", existing_type=sa.Enum(*TIPOS_ANTES, name="tipo_interacao"),
                    type_=sa.Enum(*TIPOS_DEPOIS, name="tipo_interacao"), existing_nullable=False)
    op.add_column("oficios", sa.Column("chamado_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_oficio_chamado", "oficios", "chamados", ["chamado_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_oficios_chamado_id", "oficios", ["chamado_id"])


def downgrade() -> None:
    op.drop_constraint("fk_oficio_chamado", "oficios", type_="foreignkey")
    op.drop_index("ix_oficios_chamado_id", "oficios")
    op.drop_column("oficios", "chamado_id")
    op.execute("DELETE FROM chamado_interacoes WHERE tipo = 'OFICIO'")
    op.alter_column("chamado_interacoes", "tipo", existing_type=sa.Enum(*TIPOS_DEPOIS, name="tipo_interacao"),
                    type_=sa.Enum(*TIPOS_ANTES, name="tipo_interacao"), existing_nullable=False)
    op.drop_column("chamados", "solucao_horas_corridas")
    op.drop_column("chamados", "solucao_horas_uteis")
