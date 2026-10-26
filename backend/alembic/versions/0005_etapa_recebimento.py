"""etapa de recebimento: status PENDENTE_RECEBIMENTO/RECEBIDO, data do recebimento e evidência da entrega

Ofícios de itens (equipamentos, peças, EPI's, mobiliários, instrumentais) já CONFIRMADOS passam a
PENDENTE_RECEBIMENTO, com um evento no histórico explicando a mudança.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

STATUS_ANTIGO = sa.Enum("PENDENTE_RESPOSTA", "CONFIRMADO", "NAO_CONFIRMADO", name="status_oficio")
STATUS_NOVO = sa.Enum("PENDENTE_RESPOSTA", "CONFIRMADO", "NAO_CONFIRMADO", "PENDENTE_RECEBIMENTO", "RECEBIDO",
                      name="status_oficio")
ANEXO_ANTIGO = sa.Enum("OFICIO", "REFERENCIA", "RESPOSTA", name="tipo_anexo")
ANEXO_NOVO = sa.Enum("OFICIO", "REFERENCIA", "RESPOSTA", "RECEBIMENTO", name="tipo_anexo")
TIPOS_ITENS = "('SOLICITACAO_EQUIPAMENTOS', 'PECAS_MANUTENCAO', 'EPIS', 'MOBILIARIOS', 'INSTRUMENTAIS')"
MOTIVO = "O tipo passou a exigir confirmação do recebimento"


def _enums(status_de: sa.Enum, status_para: sa.Enum, anexo_de: sa.Enum, anexo_para: sa.Enum) -> None:
    with op.batch_alter_table("oficios") as t:
        t.alter_column("status", existing_type=status_de, type_=status_para, existing_nullable=False)
    with op.batch_alter_table("historico_status") as t:
        t.alter_column("status_anterior", existing_type=status_de, type_=status_para, existing_nullable=True)
        t.alter_column("status_novo", existing_type=status_de, type_=status_para, existing_nullable=False)
    with op.batch_alter_table("anexos") as t:
        t.alter_column("tipo", existing_type=anexo_de, type_=anexo_para, existing_nullable=False)


def upgrade() -> None:
    _enums(STATUS_ANTIGO, STATUS_NOVO, ANEXO_ANTIGO, ANEXO_NOVO)
    op.add_column("oficios", sa.Column("data_recebimento", sa.Date(), nullable=True))
    op.add_column("historico_status", sa.Column("data_recebimento", sa.Date(), nullable=True))

    op.execute(
        "INSERT INTO historico_status (oficio_id, status_anterior, status_novo, data_resposta, observacao) "
        f"SELECT id, 'CONFIRMADO', 'PENDENTE_RECEBIMENTO', data_resposta, '{MOTIVO}' FROM oficios "
        f"WHERE status = 'CONFIRMADO' AND tipo IN {TIPOS_ITENS}"
    )
    op.execute(f"UPDATE oficios SET status = 'PENDENTE_RECEBIMENTO' WHERE status = 'CONFIRMADO' AND tipo IN {TIPOS_ITENS}")


def downgrade() -> None:
    op.execute("UPDATE oficios SET status = 'CONFIRMADO' WHERE status IN ('PENDENTE_RECEBIMENTO', 'RECEBIDO')")
    op.execute(f"DELETE FROM historico_status WHERE observacao = '{MOTIVO}'")
    for coluna in ("status_anterior", "status_novo"):
        op.execute(f"UPDATE historico_status SET {coluna} = 'CONFIRMADO' "
                   f"WHERE {coluna} IN ('PENDENTE_RECEBIMENTO', 'RECEBIDO')")
    # Evidência da entrega vira evidência de resposta (o evento é outro, então não colide)
    op.execute("UPDATE anexos SET tipo = 'RESPOSTA' WHERE tipo = 'RECEBIMENTO'")
    op.drop_column("historico_status", "data_recebimento")
    op.drop_column("oficios", "data_recebimento")
    _enums(STATUS_NOVO, STATUS_ANTIGO, ANEXO_NOVO, ANEXO_ANTIGO)
