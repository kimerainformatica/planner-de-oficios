"""Tipos de ofício cadastráveis: consulta, regra da etapa de entrega e validação nos ofícios."""

import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TipoOficio


def listar(db: Session) -> list[TipoOficio]:
    return list(db.scalars(select(TipoOficio).order_by(TipoOficio.ordem, TipoOficio.nome)))


def exige_recebimento(db: Session, codigo: str | None) -> bool:
    """Depois da resposta confirmada, o ofício fica PENDENTE_RECEBIMENTO até a entrega ser confirmada.

    Ofícios antigos sem tipo seguem a regra anterior (sem etapa de entrega).
    """
    if codigo is None:
        return False
    tipo = db.get(TipoOficio, codigo)
    return tipo is not None and tipo.exige_entrega


def validar_para_oficio(db: Session, codigo: str, atual: str | None = None) -> None:
    """Tipo de um ofício novo ou editado: precisa existir e estar ativo (manter o tipo atual sempre vale)."""
    if codigo == atual:
        return
    tipo = db.get(TipoOficio, codigo)
    if tipo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Tipo de ofício desconhecido: {codigo}")
    if not tipo.ativo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"O tipo {tipo.nome} está desativado")


def gerar_codigo(db: Session, nome: str) -> str:
    """"Peças de Reposição" -> "PECAS_DE_REPOSICAO" (com sufixo se já existir)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Z0-9]+", "_", sem_acento.upper()).strip("_")[:34] or "TIPO"
    codigo, n = base, 2
    while db.get(TipoOficio, codigo) is not None:
        codigo, n = f"{base}_{n}", n + 1
    return codigo


# Tipos de uma instalação nova (os mesmos que a migração 0009 cadastra). Usado pelos testes.
TIPOS_INICIAIS = [
    ("SOLICITACAO_EQUIPAMENTOS", "Equipamentos", None, True),
    ("PECAS_MANUTENCAO", "Peças para Manutenção/Engenharia Clínica", "Peças / Eng. Clínica", True),
    ("EPIS", "EPI's", None, True),
    ("SERVICOS", "Serviços", None, True),
    ("MOBILIARIOS", "Mobiliários", None, True),
    ("COMUNICADOS", "Comunicados", None, False),
    ("INSTRUMENTAIS", "Instrumentais", None, True),
    ("OUTROS", "Outros", None, True),
]


def semear(db: Session) -> None:
    db.add_all(TipoOficio(codigo=c, nome=n, nome_curto=curto, exige_entrega=e, ativo=True, ordem=i)
               for i, (c, n, curto, e) in enumerate(TIPOS_INICIAIS, 1))
