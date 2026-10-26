"""tipos de ofício: adiciona PECAS_MANUTENCAO e troca IMOBILIARIO por MOBILIARIOS

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ANTIGOS = ["SOLICITACAO_EQUIPAMENTOS", "EPIS", "SERVICOS", "IMOBILIARIO", "COMUNICADOS", "INSTRUMENTAIS", "OUTROS"]
NOVOS = ["SOLICITACAO_EQUIPAMENTOS", "PECAS_MANUTENCAO", "EPIS", "SERVICOS", "MOBILIARIOS", "COMUNICADOS",
         "INSTRUMENTAIS", "OUTROS"]
TODOS = ANTIGOS[:4] + ["PECAS_MANUTENCAO", "MOBILIARIOS"] + ANTIGOS[4:]


def _tipo(valores: list[str]) -> sa.Enum:
    return sa.Enum(*valores, name="tipo_oficio")


def _trocar(de: list[str], intermediario: list[str], para: list[str], antigo: str, novo: str) -> None:
    # 1) aceita os dois códigos, 2) converte os ofícios, 3) remove o código que saiu
    with op.batch_alter_table("oficios") as t:
        t.alter_column("tipo", existing_type=_tipo(de), type_=_tipo(intermediario), existing_nullable=True)
    op.execute(f"UPDATE oficios SET tipo = '{novo}' WHERE tipo = '{antigo}'")
    with op.batch_alter_table("oficios") as t:
        t.alter_column("tipo", existing_type=_tipo(intermediario), type_=_tipo(para), existing_nullable=True)


def upgrade() -> None:
    _trocar(ANTIGOS, TODOS, NOVOS, "IMOBILIARIO", "MOBILIARIOS")


def downgrade() -> None:
    op.execute("UPDATE oficios SET tipo = 'OUTROS' WHERE tipo = 'PECAS_MANUTENCAO'")
    _trocar(NOVOS, TODOS, ANTIGOS, "MOBILIARIOS", "IMOBILIARIO")
