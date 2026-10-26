from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminDep, DbDep, SettingsDep, UsuarioDep, eh_admin
from app.models import Oficio, SolicitacaoExclusao, StatusSolicitacao
from app.schemas import SolicitacaoDecidir, SolicitacaoOut
from app.services.auditoria import Acao, registrar
from app.services.exclusoes import decidir, excluir_oficio, montar_solicitacao

router = APIRouter(prefix="/api/exclusoes", tags=["Pedidos de exclusão"])


@router.get("", response_model=list[SolicitacaoOut], summary="Admin: todos os pedidos · cliente: os seus")
def listar(
    db: DbDep,
    usuario: UsuarioDep,
    status_: Annotated[StatusSolicitacao | None, Query(alias="status")] = None,
):
    consulta = select(SolicitacaoExclusao).options(
        selectinload(SolicitacaoExclusao.solicitante), selectinload(SolicitacaoExclusao.decidido_por)
    )
    if not eh_admin(usuario):
        consulta = consulta.where(SolicitacaoExclusao.solicitante_id == usuario.id)
    if status_ is not None:
        consulta = consulta.where(SolicitacaoExclusao.status == status_)
    consulta = consulta.order_by(SolicitacaoExclusao.criado_em.desc(), SolicitacaoExclusao.id.desc()).limit(200)
    return [montar_solicitacao(s) for s in db.scalars(consulta)]


@router.get("/pendentes", summary="Quantidade de pedidos aguardando decisão (para o aviso no menu)")
def pendentes(db: DbDep, _: AdminDep):
    total = db.scalar(
        select(func.count()).select_from(SolicitacaoExclusao).where(
            SolicitacaoExclusao.status == StatusSolicitacao.PENDENTE
        )
    )
    return {"total": total or 0}


def _pendente(db: DbDep, pedido_id: int) -> SolicitacaoExclusao:
    pedido = db.get(SolicitacaoExclusao, pedido_id)
    if pedido is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    if pedido.status != StatusSolicitacao.PENDENTE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este pedido já foi decidido ou cancelado")
    return pedido


@router.post("/{pedido_id}/aprovar", status_code=status.HTTP_204_NO_CONTENT,
             summary="Aprova o pedido: o ofício é excluído")
def aprovar(pedido_id: int, dados: SolicitacaoDecidir, db: DbDep, settings: SettingsDep, admin: AdminDep):
    pedido = _pendente(db, pedido_id)
    oficio = db.scalar(select(Oficio).where(Oficio.id == pedido.oficio_id).options(
        selectinload(Oficio.anexos), selectinload(Oficio.dono), selectinload(Oficio.exclusao_pendente)))
    if oficio is None:  # o ofício já não existe: só encerra o pedido
        decidir(pedido, StatusSolicitacao.APROVADA, admin, dados.resposta)
        db.commit()
        return
    registrar(db, admin, Acao.EXCLUSAO_APROVADA, f"Aprovou o pedido de exclusão do ofício nº {oficio.numero}",
              oficio, detalhes={"motivo_do_pedido": pedido.motivo, **({"resposta": dados.resposta} if dados.resposta else {})})
    excluir_oficio(db, oficio, admin, settings, motivo=dados.resposta or f"Pedido aprovado: {pedido.motivo}")


@router.post("/{pedido_id}/recusar", response_model=SolicitacaoOut, summary="Recusa o pedido (o ofício continua)")
def recusar(pedido_id: int, dados: SolicitacaoDecidir, db: DbDep, admin: AdminDep):
    if not dados.resposta or not dados.resposta.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Explique o motivo da recusa")
    pedido = _pendente(db, pedido_id)
    decidir(pedido, StatusSolicitacao.RECUSADA, admin, dados.resposta.strip())
    oficio = db.get(Oficio, pedido.oficio_id) if pedido.oficio_id else None
    registrar(db, admin, Acao.EXCLUSAO_RECUSADA, f"Recusou o pedido de exclusão ({pedido.referencia})", oficio,
              ref=pedido.referencia, detalhes={"resposta": dados.resposta.strip()})
    db.commit()
    db.refresh(pedido)
    return montar_solicitacao(pedido)
