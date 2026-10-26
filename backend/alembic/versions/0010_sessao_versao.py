"""versão da sessão do usuário: trocar a senha encerra as sessões abertas

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("sessao_versao", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("usuarios", "sessao_versao")
