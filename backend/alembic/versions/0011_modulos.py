"""módulos da plataforma: acesso e papel (ADMIN/CLIENTE) de cada usuário em cada módulo

Os usuários que já existem ficam com o mesmo papel no módulo Planner de Ofícios. A partir daqui,
`usuarios.perfil` é global (MASTER ou CLIENTE) e o papel nos módulos fica em `usuario_modulos`.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuario_modulos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo", sa.Enum("OFICIOS", "MANUTENCAO", name="modulo"), nullable=False),
        sa.Column("perfil", sa.Enum("MASTER", "ADMIN", "CLIENTE", name="perfil"), nullable=False),
        sa.UniqueConstraint("usuario_id", "modulo", name="uk_usuario_modulo"),
    )
    # Quem já usava o sistema (que não é MASTER) segue com o mesmo papel no Planner de Ofícios
    op.execute(
        "INSERT INTO usuario_modulos (usuario_id, modulo, perfil) "
        "SELECT id, 'OFICIOS', perfil FROM usuarios WHERE perfil <> 'MASTER'"
    )
    op.execute("UPDATE usuarios SET perfil = 'CLIENTE' WHERE perfil <> 'MASTER'")


def downgrade() -> None:
    # Volta o papel do Planner de Ofícios para a coluna global
    op.execute(
        "UPDATE usuarios SET perfil = 'ADMIN' WHERE perfil <> 'MASTER' AND id IN "
        "(SELECT usuario_id FROM usuario_modulos WHERE modulo = 'OFICIOS' AND perfil = 'ADMIN')"
    )
    op.drop_table("usuario_modulos")
