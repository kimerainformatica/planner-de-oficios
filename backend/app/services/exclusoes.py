"""Exclusão de ofícios: direta (admin/master) ou por pedido do cliente aprovado por um admin."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AnexoLixeira, Auditoria, Oficio, SolicitacaoExclusao, StatusSolicitacao, Usuario
from app.schemas import SolicitacaoOut
from app.services import armazenamento
from app.services.auditoria import Acao, referencia, registrar


def montar_solicitacao(s: SolicitacaoExclusao) -> SolicitacaoOut:
    return SolicitacaoOut.model_validate(s).model_copy(
        update={
            "solicitante_nome": s.solicitante.nome if s.solicitante else None,
            "decidido_por_nome": s.decidido_por.nome if s.decidido_por else None,
        }
    )


def decidir(
    s: SolicitacaoExclusao, status: StatusSolicitacao, quem: Usuario, resposta: str | None = None
) -> None:
    s.status = status
    s.decidido_por_id = quem.id
    s.decidido_em = datetime.now()
    s.resposta = resposta


def excluir_oficio(db: Session, oficio: Oficio, admin: Usuario, settings: Settings, motivo: str | None = None) -> None:
    """Apaga o ofício, seus anexos (banco e disco, inclusive os da lixeira) e histórico; a auditoria permanece."""
    ref = referencia(oficio)
    pendente = oficio.exclusao_pendente
    if pendente is not None:
        decidir(pendente, StatusSolicitacao.APROVADA, admin, motivo)
    detalhes = {"numero": oficio.numero, "protocolo": oficio.protocolo, "dono": oficio.dono.nome,
                "anexos": [a.nome_original for a in oficio.anexos]}
    if motivo:
        detalhes["motivo"] = motivo
    registrar(db, admin, Acao.OFICIO_EXCLUIDO, f"Excluiu o ofício nº {oficio.numero}", oficio, ref=ref,
              detalhes=detalhes)
    caminhos = [a.caminho for a in oficio.anexos]
    caminhos += db.scalars(select(AnexoLixeira.caminho).where(AnexoLixeira.oficio_id == oficio.id)).all()
    db.flush()
    # Desliga explicitamente os registros que sobrevivem à exclusão (não depende do banco aplicar SET NULL)
    for modelo in (Auditoria, SolicitacaoExclusao):
        db.execute(update(modelo).where(modelo.oficio_id == oficio.id).values(oficio_id=None))
    db.delete(oficio)
    db.commit()
    for caminho in caminhos:
        armazenamento.remover_arquivo(caminho, settings)
