"""Planner de documentos: modelos de documento da instituição, pastas, prazo e conclusão

O ofício e o memorando viram os dois primeiros modelos, com os mesmos formatos de antes. Os documentos já emitidos
guardam o formato em que saíram (sem a marcação de seções e listas, como eram). O `tipo` do documento passa a ser o
código do modelo. Para voltar (downgrade), não pode haver documentos de outros modelos.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-25
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

FORMA = sa.Enum("APP", "GOVBR", name="forma_assinatura")
ESTRUTURA = sa.Enum("EXTERNO", "INTERNO", "SIMPLES", name="estrutura_documento")
TIPO_ANTIGO = sa.Enum("OFICIO", "MEMORANDO", name="tipo_documento")

MODELOS = [
    {"codigo": "OFICIO", "nome": "Ofício", "estrutura": "EXTERNO", "digitos": 3, "recuo_cm": 1.75,
     "descricao": "Comunicação externa da unidade, com destinatário por extenso. Pode ser registrado no Planner de "
                  "Ofícios na emissão.",
     "forma_assinatura": "GOVBR", "mostrar_assunto": True, "data_no_fim": False, "rotulo_ident": "ID: nº",
     "vocativo": "Prezado (a) Senhor (a),", "fecho": "Atenciosamente,", "texto_modelo": "", "sistema": True,
     "ativo": True},
    {"codigo": "MEMORANDO", "nome": "Memorando", "estrutura": "INTERNO", "digitos": 2, "recuo_cm": 1.25,
     "descricao": "Comunicação interna entre setores (De / Para).",
     "forma_assinatura": "APP", "mostrar_assunto": True, "data_no_fim": False, "rotulo_ident": "Matrícula",
     "vocativo": "Prezado(a),", "fecho": "Atenciosamente,", "texto_modelo": "", "sistema": True, "ativo": True},
]
CAMPOS_FORMATO = ("nome", "estrutura", "digitos", "recuo_cm", "mostrar_assunto", "data_no_fim", "rotulo_ident")


def upgrade() -> None:
    modelos = op.create_table(
        "modelos_documento",
        sa.Column("codigo", sa.String(40), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
        sa.Column("descricao", sa.String(300)),
        sa.Column("estrutura", ESTRUTURA, nullable=False),
        sa.Column("digitos", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column("recuo_cm", sa.Numeric(4, 2), nullable=False, server_default="1.25"),
        sa.Column("forma_assinatura", FORMA, nullable=False, server_default="APP"),
        sa.Column("mostrar_assunto", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("data_no_fim", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rotulo_ident", sa.String(30), nullable=False, server_default="Matrícula"),
        sa.Column("vocativo", sa.String(160), nullable=False, server_default=""),
        sa.Column("fecho", sa.String(120), nullable=False, server_default="Atenciosamente,"),
        sa.Column("texto_modelo", sa.Text(), nullable=False),
        sa.Column("sistema", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.bulk_insert(modelos, MODELOS)
    op.create_table(
        "pastas_documento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(80), nullable=False, unique=True),
        sa.Column("descricao", sa.String(200)),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("documentos") as t:
        t.alter_column("tipo", existing_type=TIPO_ANTIGO, type_=sa.String(40), existing_nullable=False)
        t.add_column(sa.Column("formato", sa.JSON()))
        t.add_column(sa.Column("pasta_id", sa.Integer()))
        t.add_column(sa.Column("prazo", sa.Date()))
        t.add_column(sa.Column("concluido_em", sa.DateTime()))
        t.add_column(sa.Column("concluido_por_id", sa.Integer()))
        t.create_index("ix_documentos_pasta_id", ["pasta_id"])
        t.create_foreign_key("fk_documento_modelo", "modelos_documento", ["tipo"], ["codigo"],
                             ondelete="RESTRICT", onupdate="CASCADE")
        t.create_foreign_key("fk_documento_pasta", "pastas_documento", ["pasta_id"], ["id"], ondelete="SET NULL")
        t.create_foreign_key("fk_documento_concluido_por", "usuarios", ["concluido_por_id"], ["id"],
                             ondelete="SET NULL")
    # os já emitidos (e os cancelados) ficam com o formato em que saíram
    for modelo in MODELOS:
        formato = {c: modelo[c] for c in CAMPOS_FORMATO} | {"marcacao": False}
        texto = json.dumps(formato, ensure_ascii=False).replace("'", "''")
        op.execute(f"UPDATE documentos SET formato = '{texto}', atualizado_em = atualizado_em "
                   f"WHERE tipo = '{modelo['codigo']}' AND status <> 'RASCUNHO'")


def downgrade() -> None:
    with op.batch_alter_table("documentos") as t:
        t.drop_constraint("fk_documento_concluido_por", type_="foreignkey")
        t.drop_constraint("fk_documento_pasta", type_="foreignkey")
        t.drop_constraint("fk_documento_modelo", type_="foreignkey")
        t.drop_index("ix_documentos_pasta_id")
        for coluna in ("concluido_por_id", "concluido_em", "prazo", "pasta_id", "formato"):
            t.drop_column(coluna)
        t.alter_column("tipo", existing_type=sa.String(40), type_=TIPO_ANTIGO, existing_nullable=False)
    op.drop_table("pastas_documento")
    op.drop_table("modelos_documento")
