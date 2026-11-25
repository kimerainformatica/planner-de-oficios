"""Regras do helpdesk das Manutenções Integradas.

Papéis no módulo:
- **Operacional** (CLIENTE): abre chamados e acompanha **todos** os chamados; comenta, cancela e reabre.
- **Técnico** (TECNICO, ligado a uma empresa): vê só os chamados da empresa dele; assume, responde, registra o
  diagnóstico (texto e/ou arquivo externo), faz o relatório técnico no modelo do sistema e conclui.
- **Administrador** (ADMIN do módulo) e **MASTER**: tudo, e cadastram as empresas.

Prazo: cada chamado tem `prazo_horas` horas **corridas** (da empresa, na abertura), contadas da abertura, para o
**primeiro diagnóstico** (24 h = 1 dia corrido; noites, fins de semana e feriados contam). A situação do prazo é
calculada na hora (veja `situacao_prazo`).

Data do diagnóstico: é a informada por quem registra (a data e a hora em que o técnico diagnosticou, não a do
registro no sistema) e pode ser corrigida depois (`corrigir_diagnostico`).
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    Chamado,
    ChamadoInteracao,
    EmpresaManutencao,
    Modulo,
    Oficio,
    Perfil,
    StatusChamado,
    StatusOficio,
    TipoInteracao,
    Usuario,
)

EMPRESAS_INICIAIS = ["MSI", "REALIZA PREDIAL", "REALIZA CLIMATIZAÇÃO"]
ABERTOS = {StatusChamado.ABERTO, StatusChamado.EM_ATENDIMENTO}
# Tipos de ofício usados na solicitação de peças/equipamentos feita a partir de um chamado
TIPOS_SOLICITACAO = ("PECAS_MANUTENCAO", "SOLICITACAO_EQUIPAMENTOS")
# Ofício ainda sem a entrega das peças/equipamentos
OFICIO_PENDENTE = {StatusOficio.PENDENTE_RESPOSTA, StatusOficio.PENDENTE_RECEBIMENTO}


ROTULO_OFICIO = {
    StatusOficio.PENDENTE_RESPOSTA: "aguardando resposta",
    StatusOficio.CONFIRMADO: "resposta confirmada",
    StatusOficio.NAO_CONFIRMADO: "resposta não confirmada",
    StatusOficio.PENDENTE_RECEBIMENTO: "aguardando entrega",
    StatusOficio.RECEBIDO: "entregue",
}


def numero_oficio(oficio: Oficio) -> str:
    """"45" → "45/2026"; "072/2026" fica como está (o número já traz o ano)."""
    return oficio.numero if str(oficio.ano) in oficio.numero else f"{oficio.numero}/{oficio.ano}"


def oficios_pendentes(chamado: Chamado) -> int:
    return sum(o.status in OFICIO_PENDENTE for o in chamado.oficios)


def pode_desvincular(usuario: Usuario, oficio: Oficio) -> bool:
    """Quem desfaz o vínculo de um ofício com o chamado: o dono do ofício ou um administrador (de um dos módulos)."""
    return oficio.dono_id == usuario.id or eh_admin(usuario) or usuario.eh_admin_no(Modulo.OFICIOS)


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


def marcar_diagnostico(chamado: Chamado, usuario: Usuario, quando: datetime) -> None:
    """O primeiro diagnóstico (resposta técnica, arquivo externo ou relatório) encerra o prazo.

    `quando` é a data e a hora do diagnóstico informadas por quem registra (já validadas por `validar_data_diagnostico`).
    """
    marcar_atendimento(chamado, usuario)
    if chamado.diagnosticado_em is None:
        chamado.diagnosticado_em = quando
        chamado.diagnosticado_por = usuario


def validar_data_diagnostico(chamado: Chamado, quando: datetime, agora: datetime) -> datetime:
    """Data e hora do diagnóstico: entre a abertura do chamado e agora (e antes da conclusão, se já concluído)."""
    quando = quando.replace(tzinfo=None, second=0, microsecond=0)
    if quando > agora + timedelta(minutes=10):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data do diagnóstico não pode estar no futuro")
    if quando < chamado.aberto_em.replace(second=0, microsecond=0):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"A data do diagnóstico não pode ser anterior à abertura do chamado ({chamado.aberto_em:%d/%m/%Y %H:%M})")
    if chamado.concluido_em is not None and quando > chamado.concluido_em:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"A data do diagnóstico não pode ser posterior à conclusão ({chamado.concluido_em:%d/%m/%Y %H:%M})")
    return max(quando, chamado.aberto_em)


def validar_data_resposta(chamado: Chamado, quando: datetime, agora: datetime,
                          principal: bool) -> datetime:
    """Data de uma resposta técnica ou relatório. O diagnóstico (`principal`) segue `validar_data_diagnostico`; um
    complemento, além disso, não pode ser anterior ao diagnóstico."""
    quando = validar_data_diagnostico(chamado, quando, agora)
    if not principal and chamado.diagnosticado_em is not None and quando < chamado.diagnosticado_em.replace(second=0):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"Um complemento não pode ser anterior ao diagnóstico ({chamado.diagnosticado_em:%d/%m/%Y %H:%M})")
    return quando


def aplicar_data(chamado: Chamado, interacao: ChamadoInteracao | None, novo: datetime) -> None:
    """Muda a data informada de uma resposta técnica/relatório. Se ela for o diagnóstico do chamado, o chamado
    (prazo e tempo de solução) e o relatório (PDF) acompanham."""
    if interacao is not None:
        interacao.ocorrido_em = novo
        if interacao.relatorio is not None:
            interacao.relatorio.atendido_em = novo
    if interacao is None or interacao is interacao_do_diagnostico(chamado):
        chamado.diagnosticado_em = novo
        if chamado.concluido_em is not None:
            chamado.solucao_horas_corridas = max(horas_entre(novo, chamado.concluido_em), 0.0)


def rotulo_registro(chamado: Chamado, interacao: ChamadoInteracao) -> str:
    """"Diagnóstico", "Complemento do diagnóstico" ou "Relatório técnico RT-…" (para a linha do tempo)."""
    if interacao.relatorio is not None:
        return f"Relatório técnico {interacao.relatorio.codigo}"
    return "Diagnóstico" if interacao is interacao_do_diagnostico(chamado) else "Complemento do diagnóstico"


def interacao_do_diagnostico(chamado: Chamado) -> ChamadoInteracao | None:
    """A resposta técnica ou o relatório que contou como o primeiro diagnóstico."""
    return next((i for i in chamado.interacoes
                 if i.tipo in (TipoInteracao.DIAGNOSTICO, TipoInteracao.RELATORIO)), None)


def horas_entre(inicio: datetime, fim: datetime) -> float:
    """Horas corridas de `inicio` a `fim` (negativo se `fim` vier antes)."""
    return round((fim - inicio).total_seconds() / 3600, 2)


# ---------- prazo ----------


class SituacaoPrazo(str, enum.Enum):
    NO_PRAZO = "NO_PRAZO"
    VENCENDO = "VENCENDO"  # sem diagnóstico e com poucas horas restantes
    ATRASADO = "ATRASADO"  # sem diagnóstico e o prazo já passou
    CUMPRIDO = "CUMPRIDO"  # diagnosticado dentro do prazo
    CUMPRIDO_COM_ATRASO = "CUMPRIDO_COM_ATRASO"
    SUSPENSO = "SUSPENSO"  # cancelado antes do diagnóstico


@dataclass(frozen=True)
class Prazo:
    situacao: SituacaoPrazo
    horas_restantes: float | None  # horas corridas até o prazo (negativo = atrasado); None se já diagnosticado
    horas_ate_diagnostico: float | None  # horas corridas da abertura até o diagnóstico


def prazo_do_chamado(aberto_em: datetime, prazo_horas: int) -> datetime:
    """Limite do diagnóstico: `prazo_horas` horas corridas depois da abertura."""
    return aberto_em + timedelta(hours=prazo_horas)


def situacao_prazo(chamado: Chamado, agora: datetime, settings: Settings) -> Prazo:
    if chamado.diagnosticado_em is not None:
        horas = max(horas_entre(chamado.aberto_em, chamado.diagnosticado_em), 0.0)
        no_prazo = chamado.diagnosticado_em <= chamado.prazo_em
        return Prazo(SituacaoPrazo.CUMPRIDO if no_prazo else SituacaoPrazo.CUMPRIDO_COM_ATRASO, None, horas)
    if chamado.status == StatusChamado.CANCELADO:
        return Prazo(SituacaoPrazo.SUSPENSO, None, None)
    restantes = horas_entre(agora, chamado.prazo_em)
    if agora > chamado.prazo_em:
        return Prazo(SituacaoPrazo.ATRASADO, restantes, None)
    if restantes <= settings.manutencao_alerta_horas:
        return Prazo(SituacaoPrazo.VENCENDO, restantes, None)
    return Prazo(SituacaoPrazo.NO_PRAZO, restantes, None)
