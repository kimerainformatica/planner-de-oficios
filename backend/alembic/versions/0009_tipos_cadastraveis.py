"""tipos de ofício cadastráveis: saem do código (enum) para a tabela tipos_oficio

Cada tipo diz se exige a etapa de entrega (antes: todos menos Comunicados, fixo no código).
Os códigos dos tipos existentes não mudam, então ofícios, filtros e links continuam valendo.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# (código, nome, nome curto, exige entrega) na ordem de exibição de antes
TIPOS = [
    ("SOLICITACAO_EQUIPAMENTOS", "Equipamentos", None, True),
    ("PECAS_MANUTENCAO", "Peças para Manutenção/Engenharia Clínica", "Peças / Eng. Clínica", True),
    ("EPIS", "EPI's", None, True),
    ("SERVICOS", "Serviços", None, True),
    ("MOBILIARIOS", "Mobiliários", None, True),
    ("COMUNICADOS", "Comunicados", None, False),
    ("INSTRUMENTAIS", "Instrumentais", None, True),
    ("OUTROS", "Outros", None, True),
]
ENUM_ANTIGO = sa.Enum(*(t[0] for t in TIPOS), name="tipo_oficio")


def upgrade() -> None:
    tabela = op.create_table(
        "tipos_oficio",
        sa.Column("codigo", sa.String(40), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("nome_curto", sa.String(40), nullable=True),
        sa.Column("exige_entrega", sa.Boolean(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("ordem", sa.SmallInteger(), nullable=False),
    )
    op.bulk_insert(tabela, [
        {"codigo": c, "nome": n, "nome_curto": curto, "exige_entrega": e, "ativo": True, "ordem": i}
        for i, (c, n, curto, e) in enumerate(TIPOS, 1)
    ])
    with op.batch_alter_table("oficios") as t:
        t.alter_column("tipo", existing_type=ENUM_ANTIGO, type_=sa.String(40), existing_nullable=True)
        t.create_foreign_key("fk_oficio_tipo", "tipos_oficio", ["tipo"], ["codigo"], ondelete="RESTRICT",
                             onupdate="CASCADE")


def downgrade() -> None:
    # Tipos criados depois desta migração não cabem no enum antigo: viram "Outros"
    codigos = ", ".join(f"'{t[0]}'" for t in TIPOS)
    with op.batch_alter_table("oficios") as t:
        t.drop_constraint("fk_oficio_tipo", type_="foreignkey")
    if op.get_bind().dialect.name == "mysql":
        op.drop_index("fk_oficio_tipo", table_name="oficios")  # índice que o MySQL cria junto com a FK
    op.execute(f"UPDATE oficios SET tipo = 'OUTROS' WHERE tipo IS NOT NULL AND tipo NOT IN ({codigos})")
    with op.batch_alter_table("oficios") as t:
        t.alter_column("tipo", existing_type=sa.String(40), type_=ENUM_ANTIGO, existing_nullable=True)
    op.drop_table("tipos_oficio")
