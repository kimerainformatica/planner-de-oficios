"""Regras do helpdesk da Manutenção Clínica.

Papéis no módulo:
- **Operacional** (CLIENTE): abre chamados e acompanha **todos** os chamados; comenta, cancela e reabre.
- **Técnico** (TECNICO, ligado a uma empresa): vê só os chamados da empresa dele; assume, responde, registra o
  diagnóstico (texto e/ou arquivo externo), faz o relatório técnico no modelo do sistema e conclui.
- **Administrador** (ADMIN do módulo) e **MASTER**: tudo, e cadastram as empresas.

Prazo: cada chamado tem `prazo_horas` horas úteis (da empresa, na abertura) para o **primeiro diagnóstico**.
A situação do prazo é calculada na hora (veja `situacao_prazo`).
"""

import enum
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    Chamado,
    ChamadoInteracao,
    EmpresaManutencao,
    Modulo,
    Perfil,
    StatusChamado,
    StatusOficio,
    TipoInteracao,
    Usuario,
)
from app.services.horas_uteis import Expediente
from app.services.prazos import CalendarioUtil

EMPRESAS_INICIAIS = ["MSI", "REALIZA PREDIAL", "REALIZA CLIMATIZAÇÃO"]
ABERTOS = {StatusChamado.ABERTO, StatusChamado.EM_ATENDIMENTO}
# Tipos de ofício usados na solicitação de peças/equipamentos feita a partir de um chamado
TIPOS_SOLICITACAO = ("PECAS_MANUTENCAO", "SOLICITACAO_EQUIPAMENTOS")
# Ofício ainda sem a entrega das peças/equipamentos
OFICIO_PENDENTE = {StatusOficio.PENDENTE_RESPOSTA, StatusOficio.PENDENTE_RECEBIMENTO}


def oficios_pendentes(chamado: Chamado) -> int:
    return sum(o.status in OFICIO_PENDENTE for o in chamado.oficios)


def texto_horas(h: float) -> str:
    """6.5 → "6 h 30 min"; 0.25 → "15 min"."""
    total = round(abs(h) * 60)
    hh, mm = divmod(total, 60)
    if hh == 0:
        return f"{mm} min"
    return f"{hh} h {mm} min" if mm else f"{hh} h"


def semear_empresas(db: Session) -> None:
    """Cadastra as empresas iniciais (se ainda não houver nenhuma)."""
    if db.scalar(select(EmpresaManutencao.id).limit(1)) is None:
        db.add_all(EmpresaManutencao(nome=n, prazo_horas=24) for n in EMPRESAS_INICIAIS)
        db.flush()


# ---------- papéis ----------


def papel(usuario: Usuario) -> Perfil | None:
    return usuario.perfil_no(Modulo.MANUTENCAO)


def eh_admin(usuario: Usuario) -> bool:
    return usuario.eh_admin_no(Modulo.MANUTENCAO)


def eh_tecnico(usuario: Usuario) -> bool:
    return papel(usuario) == Perfil.TECNICO


def eh_operacional(usuario: Usuario) -> bool:
    return papel(usuario) == Perfil.CLIENTE


def empresa_do_tecnico(usuario: Usuario) -> int | None:
    acesso = usuario.acesso_no(Modulo.MANUTENCAO)
    return acesso.empresa_id if acesso and acesso.perfil == Perfil.TECNICO else None


def escopo(usuario: Usuario) -> ColumnElement[bool]:
    """Operacional, admin e master veem todos os chamados; o técnico vê os da empresa dele."""
    if eh_tecnico(usuario):
        empresa = empresa_do_tecnico(usuario)
        return Chamado.empresa_id == empresa if empresa is not None else false()
    return true()


def buscar(db: Session, chamado_id: int, usuario: Usuario) -> Chamado:
    chamado = db.scalar(select(Chamado).where(Chamado.id == chamado_id, escopo(usuario)))
    if chamado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chamado não encontrado")
    return chamado


def _proibido(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, msg)


def exigir_atendente(usuario: Usuario) -> None:
    """Técnico (da empresa do chamado, garantido pelo escopo) ou admin."""
    if not (eh_tecnico(usuario) or eh_admin(usuario)):
        raise _proibido("Ação permitida apenas para o técnico da empresa ou administradores")


def exigir_solicitante(usuario: Usuario) -> None:
    """Lado de quem pede o serviço: operacional ou admin."""
    if not (eh_operacional(usuario) or eh_admin(usuario)):
        raise _proibido("Ação permitida apenas para o operacional ou administradores")


def exigir_status(chamado: Chamado, permitidos: set[StatusChamado], acao: str) -> None:
    if chamado.status not in permitidos:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Não é possível {acao} um chamado {ROTULO_STATUS[chamado.status]}")


ROTULO_STATUS = {
    StatusChamado.ABERTO: "aberto",
    StatusChamado.EM_ATENDIMENTO: "em atendimento",
    StatusChamado.CONCLUIDO: "concluído",
    StatusChamado.CANCELADO: "cancelado",
}


# ---------- linha do tempo ----------


def registrar(db: Session, chamado: Chamado, autor: Usuario | None, tipo: TipoInteracao, agora: datetime,
              texto: str | None = None, **extra) -> ChamadoInteracao:
    # chamado=... já coloca a interação em chamado.interacoes (back_populates)
    interacao = ChamadoInteracao(chamado=chamado, autor=autor, tipo=tipo, texto=texto, criado_em=agora, **extra)
    chamado.atualizado_em = agora
    db.add(interacao)
    return interacao


def marcar_atendimento(chamado: Chamado, usuario: Usuario) -> None:
    """Primeiro contato do técnico: o chamado entra em atendimento e ele vira o responsável (se não houver)."""
    if chamado.status == StatusChamado.ABERTO:
        chamado.status = StatusChamado.EM_ATENDIMENTO
    if chamado.tecnico_id is None and eh_tecnico(usuario):
        chamado.tecnico = usuario


def marcar_diagnostico(chamado: Chamado, usuario: Usuario, agora: datetime) -> None:
    """O primeiro diagnóstico (resposta técnica, arquivo externo ou relatório) encerra o prazo."""
    marcar_atendimento(chamado, usuario)
    if chamado.diagnosticado_em is None:
        chamado.diagnosticado_em = agora
        chamado.diagnosticado_por = usuario


# ---------- prazo ----------


class SituacaoPrazo(str, enum.Enum):
    NO_PRAZO = "NO_PRAZO"
    VENCENDO = "VENCENDO"  # sem diagnóstico e com poucas horas úteis restantes
    ATRASADO = "ATRASADO"  # sem diagnóstico e o prazo já passou
    CUMPRIDO = "CUMPRIDO"  # diagnosticado dentro do prazo
    CUMPRIDO_COM_ATRASO = "CUMPRIDO_COM_ATRASO"
    SUSPENSO = "SUSPENSO"  # cancelado antes do diagnóstico


@dataclass(frozen=True)
class Prazo:
    situacao: SituacaoPrazo
    horas_restantes: float | None  # horas úteis até o prazo (negativo = atrasado); None se já diagnosticado
    horas_ate_diagnostico: float | None  # horas úteis da abertura até o diagnóstico


def expediente(calendario: CalendarioUtil, settings: Settings) -> Expediente:
    return Expediente(calendario, settings.manutencao_expediente_inicio, settings.manutencao_expediente_fim)


def situacao_prazo(chamado: Chamado, agora: datetime, exp: Expediente, settings: Settings) -> Prazo:
    if chamado.diagnosticado_em is not None:
        horas = round(exp.horas_entre(chamado.aberto_em, chamado.diagnosticado_em), 2)
        no_prazo = chamado.diagnosticado_em <= chamado.prazo_em
        return Prazo(SituacaoPrazo.CUMPRIDO if no_prazo else SituacaoPrazo.CUMPRIDO_COM_ATRASO, None, horas)
    if chamado.status == StatusChamado.CANCELADO:
        return Prazo(SituacaoPrazo.SUSPENSO, None, None)
    restantes = round(exp.horas_entre(agora, chamado.prazo_em), 2)
    if agora > chamado.prazo_em:
        return Prazo(SituacaoPrazo.ATRASADO, restantes, None)
    if restantes <= settings.manutencao_alerta_horas:
        return Prazo(SituacaoPrazo.VENCENDO, restantes, None)
    return Prazo(SituacaoPrazo.NO_PRAZO, restantes, None)
