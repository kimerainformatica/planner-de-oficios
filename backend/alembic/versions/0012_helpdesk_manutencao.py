"""helpdesk da Manutenção Clínica: empresas técnicas, técnicos, chamados, interações e relatórios técnicos

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

PERFIS_ANTES = ("MASTER", "ADMIN", "CLIENTE")
PERFIS_DEPOIS = ("MASTER", "ADMIN", "CLIENTE", "TECNICO")


def upgrade() -> None:
    empresas = op.create_table(
        "empresas_manutencao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
        sa.Column("descricao", sa.String(200)),
        sa.Column("prazo_horas", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.bulk_insert(empresas, [{"nome": n, "prazo_horas": 24, "ativo": True}
                              for n in ("MSI", "REALIZA PREDIAL", "REALIZA CLIMATIZAÇÃO")])

    # Técnico: novo papel (só na Manutenção), ligado a uma empresa
    op.alter_column("usuario_modulos", "perfil", existing_type=sa.Enum(*PERFIS_ANTES, name="perfil"),
                    type_=sa.Enum(*PERFIS_DEPOIS, name="perfil"), existing_nullable=False)
    op.add_column("usuario_modulos", sa.Column("empresa_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_usuario_modulo_empresa", "usuario_modulos", "empresas_manutencao",
                          ["empresa_id"], ["id"], ondelete="RESTRICT")

    op.create_table(
        "chamados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("solicitante_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tecnico_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("local", sa.String(120)),
        sa.Column("equipamento", sa.String(120)),
        sa.Column("ocorrido_em", sa.DateTime(), nullable=False),
        sa.Column("aberto_em", sa.DateTime(), nullable=False),
        sa.Column("prazo_horas", sa.Integer(), nullable=False),
        sa.Column("prazo_em", sa.DateTime(), nullable=False),
        sa.Column("status", sa.Enum("ABERTO", "EM_ATENDIMENTO", "CONCLUIDO", "CANCELADO", name="status_chamado"),
                  nullable=False),
        sa.Column("diagnosticado_em", sa.DateTime()),
        sa.Column("diagnosticado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("concluido_em", sa.DateTime()),
        sa.Column("cancelado_em", sa.DateTime()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_chamado_status_empresa", "chamados", ["status", "empresa_id"])
    op.create_index("idx_chamado_empresa_aberto", "chamados", ["empresa_id", "aberto_em"])

    op.create_table(
        "relatorios_tecnicos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamado_id", sa.Integer(), sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tecnico_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atendido_em", sa.DateTime(), nullable=False),
        sa.Column("equipamento", sa.String(120)),
        sa.Column("identificacao", sa.String(120)),
        sa.Column("diagnostico", sa.Text(), nullable=False),
        sa.Column("causa", sa.Text()),
        sa.Column("servico_executado", sa.Text()),
        sa.Column("pecas", sa.Text()),
        sa.Column("situacao_equipamento", sa.Enum("OPERANDO", "OPERANDO_COM_RESTRICAO", "PARADO", "AGUARDANDO_PECA",
                                                  "NAO_SE_APLICA", name="situacao_equipamento"), nullable=False),
        sa.Column("recomendacoes", sa.Text()),
    )

    op.create_table(
        "chamado_interacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chamado_id", sa.Integer(), sa.ForeignKey("chamados.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("tipo", sa.Enum("ABERTURA", "COMENTARIO", "DIAGNOSTICO", "RELATORIO", "ASSUMIDO", "CONCLUSAO",
                                  "REABERTURA", "CANCELAMENTO", name="tipo_interacao"), nullable=False),
        sa.Column("texto", sa.Text()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("relatorio_id", sa.Integer(), sa.ForeignKey("relatorios_tecnicos.id", ondelete="SET NULL")),
        sa.Column("arquivo_nome", sa.String(255)),
        sa.Column("arquivo_caminho", sa.String(500)),
        sa.Column("arquivo_mime", sa.String(100)),
        sa.Column("arquivo_tamanho", sa.Integer()),
        sa.Column("arquivo_sha256", sa.String(64)),
    )


def downgrade() -> None:
    op.drop_table("chamado_interacoes")
    op.drop_table("relatorios_tecnicos")
    op.drop_table("chamados")
    op.drop_constraint("fk_usuario_modulo_empresa", "usuario_modulos", type_="foreignkey")
    op.drop_column("usuario_modulos", "empresa_id")
    op.execute("DELETE FROM usuario_modulos WHERE perfil = 'TECNICO'")
    op.alter_column("usuario_modulos", "perfil", existing_type=sa.Enum(*PERFIS_DEPOIS, name="perfil"),
                    type_=sa.Enum(*PERFIS_ANTES, name="perfil"), existing_nullable=False)
    op.drop_table("empresas_manutencao")
