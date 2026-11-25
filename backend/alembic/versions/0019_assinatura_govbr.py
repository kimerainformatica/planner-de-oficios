"""Ofícios assinados pelo GOV.BR: forma de assinatura, PDF guardado, dados do certificado e CPF do usuário

Os documentos já emitidos continuam com a assinatura do app; os ofícios em rascunho passam para o GOV.BR.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

FORMA = sa.Enum("APP", "GOVBR", name="forma_assinatura")


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as t:
        t.add_column(sa.Column("cpf", sa.String(11)))
    with op.batch_alter_table("documentos") as t:
        t.add_column(sa.Column("forma_assinatura", FORMA, nullable=False, server_default="APP"))
        t.add_column(sa.Column("arquivo_original", sa.String(255)))
        t.add_column(sa.Column("arquivo_original_hash", sa.String(64)))
        t.add_column(sa.Column("arquivo_assinado", sa.String(255)))
        t.add_column(sa.Column("arquivo_assinado_hash", sa.String(64)))
    op.execute("UPDATE documentos SET forma_assinatura = 'GOVBR', atualizado_em = atualizado_em "
               "WHERE tipo = 'OFICIO' AND status = 'RASCUNHO'")
    with op.batch_alter_table("documento_assinaturas") as t:
        t.add_column(sa.Column("forma", FORMA, nullable=False, server_default="APP"))
        t.add_column(sa.Column("cert_nome", sa.String(160)))
        t.add_column(sa.Column("cert_cpf", sa.String(14)))
        t.add_column(sa.Column("cert_emissor", sa.String(160)))
        t.add_column(sa.Column("cert_serie", sa.String(64)))
        t.add_column(sa.Column("impressao", sa.String(64)))


def downgrade() -> None:
    with op.batch_alter_table("documento_assinaturas") as t:
        for coluna in ("impressao", "cert_serie", "cert_emissor", "cert_cpf", "cert_nome", "forma"):
            t.drop_column(coluna)
    with op.batch_alter_table("documentos") as t:
        for coluna in ("arquivo_assinado_hash", "arquivo_assinado", "arquivo_original_hash", "arquivo_original",
                       "forma_assinatura"):
            t.drop_column(coluna)
    with op.batch_alter_table("usuarios") as t:
        t.drop_column("cpf")
