"""lixeira de anexos: a versão anterior de um anexo substituído ou removido fica guardada

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TIPO_ANEXO = sa.Enum("OFICIO", "REFERENCIA", "RESPOSTA", "RECEBIMENTO", name="tipo_anexo")


def upgrade() -> None:
    op.create_table(
        "anexos_lixeira",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("oficio_id", sa.Integer(), sa.ForeignKey("oficios.id", ondelete="CASCADE",
                                                           name="fk_lixeira_oficio"), nullable=False),
        sa.Column("tipo", TIPO_ANEXO, nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("historico_id", sa.Integer(), sa.ForeignKey("historico_status.id", ondelete="SET NULL",
                                                              name="fk_lixeira_historico"), nullable=True),
        sa.Column("nome_original", sa.String(255), nullable=False),
        sa.Column("caminho", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("enviado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL",
                                                                name="fk_lixeira_enviado_por"), nullable=True),
        sa.Column("enviado_em", sa.DateTime(), nullable=False),
        sa.Column("motivo", sa.String(20), nullable=False),
        sa.Column("descartado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL",
                                                                   name="fk_lixeira_descartado_por"), nullable=True),
        sa.Column("descartado_em", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_anexos_lixeira_oficio_id", "anexos_lixeira", ["oficio_id"])
    op.create_index("idx_lixeira_data", "anexos_lixeira", ["descartado_em"])


def downgrade() -> None:
    # Os arquivos das versões guardadas continuam no disco (a verificação os aponta como sobras)
    op.drop_table("anexos_lixeira")
