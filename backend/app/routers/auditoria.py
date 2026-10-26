from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.deps import DbDep, UsuarioDep, eh_admin
from app.models import Auditoria, Oficio
from app.schemas import AuditoriaOut, PaginaAuditoria

router = APIRouter(prefix="/api/auditoria", tags=["Registro de atividades"])


@router.get(
    "",
    response_model=PaginaAuditoria,
    summary="Admin/master: tudo · cliente: o que fez e o que foi feito nos seus ofícios",
)
def listar(
    db: DbDep,
    usuario: UsuarioDep,
    usuario_id: Annotated[int | None, Query(description="Filtra por quem fez")] = None,
    oficio_id: int | None = None,
    acao: str | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=200)] = 50,
):
    filtros = []
    if not eh_admin(usuario):
        meus_oficios = select(Oficio.id).where(Oficio.dono_id == usuario.id)
        filtros.append(or_(Auditoria.usuario_id == usuario.id, Auditoria.oficio_id.in_(meus_oficios)))
    if usuario_id is not None:
        filtros.append(Auditoria.usuario_id == usuario_id)
    if oficio_id is not None:
        filtros.append(Auditoria.oficio_id == oficio_id)
    if acao:
        filtros.append(Auditoria.acao == acao)
    if data_inicio:
        filtros.append(Auditoria.criado_em >= data_inicio)
    if data_fim:
        filtros.append(Auditoria.criado_em < data_fim + timedelta(days=1))

    total = db.scalar(select(func.count()).select_from(Auditoria).where(*filtros)) or 0
    entradas = db.scalars(
        select(Auditoria)
        .where(*filtros)
        .options(selectinload(Auditoria.usuario))
        .order_by(Auditoria.criado_em.desc(), Auditoria.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return PaginaAuditoria(
        itens=[
            AuditoriaOut.model_validate(e).model_copy(update={"usuario_nome": e.usuario.nome if e.usuario else None})
            for e in entradas
        ],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
    )
