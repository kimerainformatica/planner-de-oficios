"""prazos em dias/horas corridas: refaz o prazo dos chamados e guarda a data informada do diagnóstico

- chamados.prazo_em passa a ser aberto_em + prazo_horas horas corridas (antes: horas úteis no expediente);
- chamados.solucao_horas_uteis sai (o tempo de solução fica só em horas corridas);
- chamado_interacoes.ocorrido_em: data e hora do diagnóstico/atendimento informadas por quem registrou;
- tipo de interação CORRECAO (ex.: data do diagnóstico corrigida).

Os ofícios não mudam no banco: os dias corridos são calculados na hora a partir das mesmas datas.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-14
"""

from datetime import timedelta

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

TIPOS_ANTES = ("ABERTURA", "COMENTARIO", "DIAGNOSTICO", "RELATORIO", "ASSUMIDO", "CONCLUSAO", "REABERTURA",
               "CANCELAMENTO", "OFICIO")
TIPOS_DEPOIS = (*TIPOS_ANTES, "CORRECAO")


def upgrade() -> None:
    op.add_column("chamado_interacoes", sa.Column("ocorrido_em", sa.DateTime()))
    op.alter_column("chamado_interacoes", "tipo", existing_type=sa.Enum(*TIPOS_ANTES, name="tipo_interacao"),
                    type_=sa.Enum(*TIPOS_DEPOIS, name="tipo_interacao"), existing_nullable=False)

    conexao = op.get_bind()
    chamados = sa.table("chamados", sa.column("id", sa.Integer), sa.column("aberto_em", sa.DateTime),
                        sa.column("prazo_horas", sa.Integer), sa.column("prazo_em", sa.DateTime))
    for cid, aberto, horas in conexao.execute(sa.select(chamados.c.id, chamados.c.aberto_em, chamados.c.prazo_horas)).all():
        conexao.execute(chamados.update().where(chamados.c.id == cid)
                        .values(prazo_em=aberto + timedelta(hours=horas)))

    # As respostas técnicas e os relatórios já registrados: a data informada é a do registro
    interacoes = sa.table("chamado_interacoes", sa.column("tipo", sa.String), sa.column("criado_em", sa.DateTime),
                          sa.column("ocorrido_em", sa.DateTime))
    conexao.execute(interacoes.update().where(interacoes.c.tipo.in_(("DIAGNOSTICO", "RELATORIO")))
                    .values(ocorrido_em=interacoes.c.criado_em))
    op.drop_column("chamados", "solucao_horas_uteis")


def downgrade() -> None:
    # O prazo em horas úteis e o tempo de solução em horas úteis não são recalculados: restaure o backup para tê-los.
    op.add_column("chamados", sa.Column("solucao_horas_uteis", sa.Float()))
    op.execute("DELETE FROM chamado_interacoes WHERE tipo = 'CORRECAO'")
    op.alter_column("chamado_interacoes", "tipo", existing_type=sa.Enum(*TIPOS_DEPOIS, name="tipo_interacao"),
                    type_=sa.Enum(*TIPOS_ANTES, name="tipo_interacao"), existing_nullable=False)
    op.drop_column("chamado_interacoes", "ocorrido_em")
