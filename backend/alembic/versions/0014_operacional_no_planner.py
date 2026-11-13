"""todo operacional da Manutenção Clínica também tem acesso ao Planner de Ofícios (como cliente, se ainda não tinha)

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-12
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO usuario_modulos (usuario_id, modulo, perfil) "
        "SELECT m.usuario_id, 'OFICIOS', 'CLIENTE' FROM usuario_modulos m "
        "WHERE m.modulo = 'MANUTENCAO' AND m.perfil IN ('CLIENTE', 'ADMIN') "
        "AND NOT EXISTS (SELECT 1 FROM usuario_modulos o WHERE o.usuario_id = m.usuario_id AND o.modulo = 'OFICIOS')"
    )


def downgrade() -> None:
    # Não há como saber quais acessos vieram desta regra: ficam como estão
    pass
