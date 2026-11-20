"""Controle de Tetos: módulo TETOS, setores (ligados aos usuários), tipos de teto, valores por vigência e lançamentos

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

MODULOS_ANTES = ("OFICIOS", "MANUTENCAO")
MODULOS_DEPOIS = ("OFICIOS", "MANUTENCAO", "TETOS")


def upgrade() -> None:
    op.alter_column("usuario_modulos", "modulo", existing_type=sa.Enum(*MODULOS_ANTES, name="modulo"),
                    type_=sa.Enum(*MODULOS_DEPOIS, name="modulo"), existing_nullable=False)

    op.create_table(
        "setores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(120), nullable=False, unique=True),
        sa.Column("descricao", sa.Text()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("usuario_modulos") as t:
        t.add_column(sa.Column("setor_id", sa.Integer()))
        t.create_foreign_key("fk_usuario_modulos_setor", "setores", ["setor_id"], ["id"], ondelete="RESTRICT")

    op.create_table(
        "tipos_teto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("descricao", sa.Text()),
        sa.Column("unidade", sa.String(20), nullable=False, server_default="R$"),
        sa.Column("alerta_pct", sa.SmallInteger(), nullable=False, server_default="80"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("setor_id", "nome", name="uk_tipo_teto_setor_nome"),
    )
    op.create_index("ix_tipos_teto_setor_id", "tipos_teto", ["setor_id"])

    op.create_table(
        "tetos_vigencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo_id", sa.Integer(), sa.ForeignKey("tipos_teto.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("periodo", sa.Enum("DIARIO", "MENSAL", "ANUAL", name="periodo_teto"), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("motivo", sa.String(500)),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tipo_id", "inicio", name="uk_teto_vigencia_inicio"),
    )
    op.create_index("ix_tetos_vigencias_tipo_id", "tetos_vigencias", ["tipo_id"])

    op.create_table(
        "gastos_teto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo_id", sa.Integer(), sa.ForeignKey("tipos_teto.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("setor_id", sa.Integer(), sa.ForeignKey("setores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("descricao", sa.String(300), nullable=False),
        sa.Column("documento", sa.String(60)),
        sa.Column("arquivo_nome", sa.String(255)),
        sa.Column("arquivo_caminho", sa.String(500)),
        sa.Column("arquivo_mime", sa.String(100)),
        sa.Column("arquivo_tamanho", sa.Integer()),
        sa.Column("arquivo_sha256", sa.String(64)),
        sa.Column("registrado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("registrado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("atualizado_em", sa.DateTime()),
    )
    op.create_index("idx_gasto_tipo_data", "gastos_teto", ["tipo_id", "data"])
    op.create_index("idx_gasto_setor_data", "gastos_teto", ["setor_id", "data"])


def downgrade() -> None:
    # Apaga os lançamentos, tipos e setores (os comprovantes ficam na pasta de armazenamento)
    op.drop_table("gastos_teto")
    op.drop_table("tetos_vigencias")
    op.drop_table("tipos_teto")
    op.execute("DELETE FROM usuario_modulos WHERE modulo = 'TETOS'")
    with op.batch_alter_table("usuario_modulos") as t:
        t.drop_constraint("fk_usuario_modulos_setor", type_="foreignkey")
        t.drop_column("setor_id")
    op.drop_table("setores")
    op.alter_column("usuario_modulos", "modulo", existing_type=sa.Enum(*MODULOS_DEPOIS, name="modulo"),
                    type_=sa.Enum(*MODULOS_ANTES, name="modulo"), existing_nullable=False)
