"""perfil MASTER, pedidos de exclusão e registro de atividades (auditoria)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

PERFIL_ANTIGO = sa.Enum("ADMIN", "CLIENTE", name="perfil")
PERFIL_NOVO = sa.Enum("MASTER", "ADMIN", "CLIENTE", name="perfil")
STATUS_SOLICITACAO = sa.Enum("PENDENTE", "APROVADA", "RECUSADA", "CANCELADA", name="status_solicitacao")


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as t:
        t.alter_column("perfil", existing_type=PERFIL_ANTIGO, type_=PERFIL_NOVO, existing_nullable=False)

    op.create_table(
        "solicitacoes_exclusao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("oficio_id", sa.Integer(), nullable=True),
        sa.Column("referencia", sa.String(length=200), nullable=False),
        sa.Column("solicitante_id", sa.Integer(), nullable=True),
        sa.Column("motivo", sa.String(length=1000), nullable=False),
        sa.Column("status", STATUS_SOLICITACAO, nullable=False),
        sa.Column("resposta", sa.String(length=1000), nullable=True),
        sa.Column("decidido_por_id", sa.Integer(), nullable=True),
        sa.Column("decidido_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["oficio_id"], ["oficios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["solicitante_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decidido_por_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_solicitacao_status", "solicitacoes_exclusao", ["status", "criado_em"])
    op.create_index(op.f("ix_solicitacoes_exclusao_oficio_id"), "solicitacoes_exclusao", ["oficio_id"])

    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("oficio_id", sa.Integer(), nullable=True),
        sa.Column("referencia", sa.String(length=200), nullable=True),
        sa.Column("acao", sa.String(length=40), nullable=False),
        sa.Column("descricao", sa.String(length=500), nullable=False),
        sa.Column("detalhes", sa.JSON(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["oficio_id"], ["oficios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_auditoria_usuario_data", "auditoria", ["usuario_id", "criado_em"])
    op.create_index("idx_auditoria_data", "auditoria", ["criado_em"])
    op.create_index(op.f("ix_auditoria_oficio_id"), "auditoria", ["oficio_id"])


def downgrade() -> None:
    op.drop_table("auditoria")
    op.drop_table("solicitacoes_exclusao")
    op.execute("UPDATE usuarios SET perfil = 'ADMIN' WHERE perfil = 'MASTER'")
    with op.batch_alter_table("usuarios") as t:
        t.alter_column("perfil", existing_type=PERFIL_NOVO, type_=PERFIL_ANTIGO, existing_nullable=False)
