"""etapa de entrega também para Serviços e Outros (só Comunicados dispensam)

Ofícios desses tipos já CONFIRMADOS passam a PENDENTE_RECEBIMENTO, com um evento no histórico.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-24
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

NOVOS_TIPOS = "('SERVICOS', 'OUTROS')"
MOTIVO = "O tipo passou a exigir confirmação do recebimento"


def upgrade() -> None:
    op.execute(
        "INSERT INTO historico_status (oficio_id, status_anterior, status_novo, data_resposta, observacao) "
        f"SELECT id, 'CONFIRMADO', 'PENDENTE_RECEBIMENTO', data_resposta, '{MOTIVO}' FROM oficios "
        f"WHERE status = 'CONFIRMADO' AND tipo IN {NOVOS_TIPOS}"
    )
    op.execute(f"UPDATE oficios SET status = 'PENDENTE_RECEBIMENTO' WHERE status = 'CONFIRMADO' AND tipo IN {NOVOS_TIPOS}")


def downgrade() -> None:
    # Volta a encerrar em CONFIRMADO; recebimentos registrados ficam só no histórico
    op.execute(f"UPDATE oficios SET status = 'CONFIRMADO', data_recebimento = NULL "
               f"WHERE status IN ('PENDENTE_RECEBIMENTO', 'RECEBIDO') AND tipo IN {NOVOS_TIPOS}")
    op.execute(f"DELETE FROM historico_status WHERE observacao = '{MOTIVO}' AND usuario_id IS NULL "
               f"AND oficio_id IN (SELECT id FROM (SELECT id FROM oficios WHERE tipo IN {NOVOS_TIPOS}) AS t)")
