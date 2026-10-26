"""tipo de ofício, destinatário, protocolo opcional e evidência da resposta

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TIPO_OFICIO = sa.Enum(
    "SOLICITACAO_EQUIPAMENTOS", "EPIS", "SERVICOS", "IMOBILIARIO", "COMUNICADOS", "INSTRUMENTAIS", "OUTROS",
    name="tipo_oficio",
)
DESTINATARIO = sa.Enum("SES", "ACQUA", "OUTROS", name="destinatario")
TIPO_ANEXO_ANTIGO = sa.Enum("OFICIO", "REFERENCIA", name="tipo_anexo")
TIPO_ANEXO_NOVO = sa.Enum("OFICIO", "REFERENCIA", "RESPOSTA", name="tipo_anexo")


def upgrade() -> None:
    with op.batch_alter_table("oficios") as t:
        # Ofícios já cadastrados ficam sem tipo ("Não classificado") até alguém editar.
        t.add_column(sa.Column("tipo", TIPO_OFICIO, nullable=True))
        t.add_column(sa.Column("destinatario_tipo", DESTINATARIO, nullable=True))
        t.add_column(sa.Column("destinatario_setor", sa.String(length=120), nullable=True))
        t.alter_column("protocolo", existing_type=sa.String(length=50), nullable=True)

    with op.batch_alter_table("anexos") as t:
        t.alter_column("tipo", existing_type=TIPO_ANEXO_ANTIGO, type_=TIPO_ANEXO_NOVO, existing_nullable=False)
        t.add_column(sa.Column("ciclo", sa.Integer(), server_default="0", nullable=False))
        t.add_column(sa.Column("historico_id", sa.Integer(), nullable=True))
        t.create_foreign_key(
            "fk_anexo_historico", "historico_status", ["historico_id"], ["id"], ondelete="CASCADE"
        )
        # Cria a nova unicidade ANTES de remover a antiga: no MySQL o índice antigo também
        # atende a chave estrangeira de oficio_id, e não pode sumir sem substituto.
        t.create_unique_constraint("uk_anexo_oficio_tipo_ciclo", ["oficio_id", "tipo", "ciclo"])
        t.drop_constraint("uk_anexo_oficio_tipo", type_="unique")


def downgrade() -> None:
    op.execute("DELETE FROM anexos WHERE tipo = 'RESPOSTA'")
    with op.batch_alter_table("anexos") as t:
        t.create_unique_constraint("uk_anexo_oficio_tipo", ["oficio_id", "tipo"])
        t.drop_constraint("uk_anexo_oficio_tipo_ciclo", type_="unique")
        t.drop_constraint("fk_anexo_historico", type_="foreignkey")
        t.drop_column("historico_id")
        t.drop_column("ciclo")
        t.alter_column("tipo", existing_type=TIPO_ANEXO_NOVO, type_=TIPO_ANEXO_ANTIGO, existing_nullable=False)

    op.execute("UPDATE oficios SET protocolo = CONCAT('SEM-', id) WHERE protocolo IS NULL")
    with op.batch_alter_table("oficios") as t:
        t.alter_column("protocolo", existing_type=sa.String(length=50), nullable=False)
        t.drop_column("destinatario_setor")
        t.drop_column("destinatario_tipo")
        t.drop_column("tipo")
