"""Documentos vira módulo próprio (DOCUMENTOS) e o ofício escolhe se é registrado no Planner

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

MODULOS_ANTES = ("OFICIOS", "MANUTENCAO")
MODULOS_DEPOIS = ("OFICIOS", "MANUTENCAO", "DOCUMENTOS")


def upgrade() -> None:
    op.alter_column("usuario_modulos", "modulo", existing_type=sa.Enum(*MODULOS_ANTES, name="modulo"),
                    type_=sa.Enum(*MODULOS_DEPOIS, name="modulo"), existing_nullable=False)
    with op.batch_alter_table("documentos") as t:
        t.add_column(sa.Column("registrar_no_planner", sa.Boolean(), nullable=False, server_default="1"))


def downgrade() -> None:
    with op.batch_alter_table("documentos") as t:
        t.drop_column("registrar_no_planner")
    op.execute("DELETE FROM usuario_modulos WHERE modulo = 'DOCUMENTOS'")
    op.alter_column("usuario_modulos", "modulo", existing_type=sa.Enum(*MODULOS_DEPOIS, name="modulo"),
                    type_=sa.Enum(*MODULOS_ANTES, name="modulo"), existing_nullable=False)
