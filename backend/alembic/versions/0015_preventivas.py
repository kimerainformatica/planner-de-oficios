"""manutenção preventiva: planos (periodicidade por empresa) e as preventivas previstas, com realização e ateste

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planos_preventiva",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("descricao", sa.Text()),
        sa.Column("local", sa.String(120)),
        sa.Column("equipamento", sa.String(120)),
        sa.Column("intervalo", sa.Integer(), nullable=False),
        sa.Column("unidade", sa.Enum("DIAS", "SEMANAS", "MESES", name="unidade_periodo"), nullable=False),
        sa.Column("inicio", sa.Date(), nullable=False),
        sa.Column("tolerancia_dias", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_planos_preventiva_empresa_id", "planos_preventiva", ["empresa_id"])

    op.create_table(
        "preventivas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plano_id", sa.Integer(), sa.ForeignKey("planos_preventiva.id", ondelete="CASCADE"), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("data_prevista", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("PROGRAMADA", "REALIZADA", "NAO_REALIZADA", name="status_preventiva"),
                  nullable=False, server_default="PROGRAMADA"),
        sa.Column("realizada_em", sa.Date()),
        sa.Column("executor", sa.String(120)),
        sa.Column("observacao", sa.Text()),
        sa.Column("registrada_em", sa.DateTime()),
        sa.Column("registrada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("arquivo_nome", sa.String(255)),
        sa.Column("arquivo_caminho", sa.String(500)),
        sa.Column("arquivo_mime", sa.String(100)),
        sa.Column("arquivo_tamanho", sa.Integer()),
        sa.Column("arquivo_sha256", sa.String(64)),
        sa.Column("motivo", sa.Text()),
        sa.Column("atestada_em", sa.DateTime()),
        sa.Column("atestada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("ateste_obs", sa.Text()),
        sa.UniqueConstraint("plano_id", "data_prevista", name="uk_preventiva_plano_data"),
    )
    op.create_index("idx_preventiva_empresa_data", "preventivas", ["empresa_id", "data_prevista"])
    op.create_index("idx_preventiva_status_data", "preventivas", ["status", "data_prevista"])


def downgrade() -> None:
    # Apaga os planos e os registros das preventivas (os arquivos de evidência ficam na pasta de armazenamento)
    op.drop_table("preventivas")
    op.drop_table("planos_preventiva")
