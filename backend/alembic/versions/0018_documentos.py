"""Documentos: ofícios e memorandos redigidos no app (modelo da unidade), assinaturas e cargo/matrícula do usuário

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


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as t:
        t.add_column(sa.Column("cargo", sa.String(120)))
        t.add_column(sa.Column("matricula", sa.String(30)))

    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.Enum("OFICIO", "MEMORANDO", name="tipo_documento"), nullable=False),
        sa.Column("status", sa.Enum("RASCUNHO", "EMITIDO", "CANCELADO", name="status_documento"), nullable=False,
                  server_default="RASCUNHO"),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ano", sa.SmallInteger()),
        sa.Column("numero", sa.Integer()),
        sa.Column("data_documento", sa.Date()),
        sa.Column("assunto", sa.String(300), nullable=False, server_default=""),
        sa.Column("vocativo", sa.String(160), nullable=False, server_default=""),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("fecho", sa.String(120), nullable=False, server_default="Atenciosamente,"),
        sa.Column("dest_tratamento", sa.String(60)),
        sa.Column("dest_nome", sa.String(160)),
        sa.Column("dest_cargo", sa.String(160)),
        sa.Column("dest_endereco", sa.String(300)),
        sa.Column("de", sa.String(160)),
        sa.Column("para", sa.String(160)),
        sa.Column("oficio_tipo", sa.String(40),
                  sa.ForeignKey("tipos_oficio.codigo", ondelete="RESTRICT", onupdate="CASCADE")),
        sa.Column("destinatario_tipo", sa.Enum("SES", "ACQUA", "OUTROS", name="destinatario")),
        sa.Column("destinatario_setor", sa.String(120)),
        sa.Column("oficio_id", sa.Integer(), sa.ForeignKey("oficios.id", ondelete="SET NULL")),
        sa.Column("elaborador_nome", sa.String(120), nullable=False, server_default=""),
        sa.Column("elaborador_cargo", sa.String(120)),
        sa.Column("elaborador_ident", sa.String(30)),
        sa.Column("validador_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("validador_nome", sa.String(120)),
        sa.Column("validador_cargo", sa.String(120)),
        sa.Column("validador_ident", sa.String(30)),
        sa.Column("codigo", sa.String(12), unique=True),
        sa.Column("hash_conteudo", sa.String(64)),
        sa.Column("emitido_em", sa.DateTime()),
        sa.Column("cancelado_em", sa.DateTime()),
        sa.Column("cancelado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("motivo_cancelamento", sa.String(500)),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tipo", "autor_id", "ano", "numero", name="uk_documento_numero"),
    )
    op.create_index("idx_documento_autor", "documentos", ["autor_id", "status"])
    op.create_index("ix_documentos_oficio_id", "documentos", ["oficio_id"])
    op.create_index("ix_documentos_validador_id", "documentos", ["validador_id"])

    op.create_table(
        "documento_assinaturas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("papel", sa.Enum("ELABORADOR", "VALIDADOR", name="papel_assinatura"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("cargo", sa.String(120)),
        sa.Column("assinado_em", sa.DateTime(), nullable=False),
        sa.Column("ip", sa.String(45)),
        sa.UniqueConstraint("documento_id", "papel", name="uk_assinatura_papel"),
    )


def downgrade() -> None:
    op.drop_table("documento_assinaturas")
    op.drop_index("ix_documentos_validador_id", table_name="documentos")
    op.drop_index("ix_documentos_oficio_id", table_name="documentos")
    op.drop_index("idx_documento_autor", table_name="documentos")
    op.drop_table("documentos")
    with op.batch_alter_table("usuarios") as t:
        t.drop_column("matricula")
        t.drop_column("cargo")
