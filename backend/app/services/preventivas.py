"""Regras da manutenção preventiva (módulo Manutenção Clínica).

- **Plano**: a rotina de uma empresa técnica (o que fazer, onde) e a periodicidade, definida pelo administrador.
- **Preventiva**: cada data prevista do plano. São criadas com antecedência (`HORIZONTE_DIAS`) e completadas
  sempre que as telas são abertas (`garantir`), sem tarefa agendada.
- **Realização**: registrada pelo técnico da empresa (ou pelo operacional/administrador), com evidência opcional.
- **Ateste**: o operacional ou o administrador confirma que o serviço foi feito. É a base da fiscalização.

A situação é calculada na hora (`situacao`): a preventiva conta como feita no prazo até `tolerancia_dias` dias
depois da data prevista.
"""

import calendar
import enum
from datetime import date, timedelta

from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.orm import Session

from app.models import PlanoPreventiva, Preventiva, StatusPreventiva, UnidadePeriodo, Usuario
from app.services import manutencao as regras

HORIZONTE_DIAS = 90  # as preventivas são criadas até esta distância (e sempre existe a próxima de cada plano)
AVISO_DIAS = 7  # a preventiva entra "na janela" quando faltam até N dias para a data prevista
RETROATIVO_DIAS = 60  # um plano novo pode começar até N dias atrás (para registrar o que já venceu)
ANTECIPACAO_DIAS = 90  # a realização pode ser registrada até N dias antes da data prevista
MAX_OCORRENCIAS = 2000  # trava de segurança da geração


class SituacaoPreventiva(str, enum.Enum):
    PROGRAMADA = "PROGRAMADA"  # ainda longe da data
    NA_JANELA = "NA_JANELA"  # perto da data, ou depois dela mas dentro da tolerância
    ATRASADA = "ATRASADA"  # passou da tolerância sem registro
    REALIZADA = "REALIZADA"  # feita no prazo
    REALIZADA_COM_ATRASO = "REALIZADA_COM_ATRASO"
    NAO_REALIZADA = "NAO_REALIZADA"


PENDENTES = {SituacaoPreventiva.PROGRAMADA, SituacaoPreventiva.NA_JANELA, SituacaoPreventiva.ATRASADA}

_NOMES = {
    (1, UnidadePeriodo.DIAS): "diária",
    (1, UnidadePeriodo.SEMANAS): "semanal",
    (2, UnidadePeriodo.SEMANAS): "quinzenal",
    (1, UnidadePeriodo.MESES): "mensal",
    (2, UnidadePeriodo.MESES): "bimestral",
    (3, UnidadePeriodo.MESES): "trimestral",
    (4, UnidadePeriodo.MESES): "quadrimestral",
    (6, UnidadePeriodo.MESES): "semestral",
    (12, UnidadePeriodo.MESES): "anual",
}
_PLURAL = {UnidadePeriodo.DIAS: "dias", UnidadePeriodo.SEMANAS: "semanas", UnidadePeriodo.MESES: "meses"}


def periodicidade(intervalo: int, unidade: UnidadePeriodo) -> str:
    """(3, MESES) → "trimestral"; (45, DIAS) → "a cada 45 dias"."""
    return _NOMES.get((intervalo, unidade)) or f"a cada {intervalo} {_PLURAL[unidade]}"


def data_da_ocorrencia(inicio: date, k: int, intervalo: int, unidade: UnidadePeriodo) -> date:
    """A k-ésima data do plano (k = 0 é o início). Nos meses, mantém o dia do início (ou o último dia do mês)."""
    n = k * intervalo
    if unidade == UnidadePeriodo.DIAS:
        return inicio + timedelta(days=n)
    if unidade == UnidadePeriodo.SEMANAS:
        return inicio + timedelta(weeks=n)
    meses = inicio.month - 1 + n
    ano, mes = inicio.year + meses // 12, meses % 12 + 1
    return date(ano, mes, min(inicio.day, calendar.monthrange(ano, mes)[1]))


def limite(p: Preventiva) -> date:
    """Último dia em que a preventiva ainda conta como feita no prazo."""
    return p.data_prevista + timedelta(days=p.plano.tolerancia_dias)


def situacao(p: Preventiva, hoje: date) -> SituacaoPreventiva:
    if p.status == StatusPreventiva.NAO_REALIZADA:
        return SituacaoPreventiva.NAO_REALIZADA
    if p.status == StatusPreventiva.REALIZADA:
        no_prazo = p.realizada_em is not None and p.realizada_em <= limite(p)
        return SituacaoPreventiva.REALIZADA if no_prazo else SituacaoPreventiva.REALIZADA_COM_ATRASO
    if hoje > limite(p):
        return SituacaoPreventiva.ATRASADA
    if hoje >= p.data_prevista - timedelta(days=AVISO_DIAS):
        return SituacaoPreventiva.NA_JANELA
    return SituacaoPreventiva.PROGRAMADA


def aguardando_ateste(p: Preventiva) -> bool:
    return p.status == StatusPreventiva.REALIZADA and p.atestada_em is None


# ---------- visibilidade ----------


def escopo(usuario: Usuario) -> ColumnElement[bool]:
    """Operacional, admin e master veem as preventivas de todas as empresas; o técnico, as da empresa dele."""
    if regras.eh_tecnico(usuario):
        empresa = regras.empresa_do_tecnico(usuario)
        return Preventiva.empresa_id == empresa if empresa is not None else false()
    return true()


def escopo_planos(usuario: Usuario) -> ColumnElement[bool]:
    if regras.eh_tecnico(usuario):
        empresa = regras.empresa_do_tecnico(usuario)
        return PlanoPreventiva.empresa_id == empresa if empresa is not None else false()
    return true()


def eh_fiscal(usuario: Usuario) -> bool:
    """Quem atesta e fiscaliza: o operacional ou o administrador (nunca o técnico da empresa)."""
    return regras.eh_operacional(usuario) or regras.eh_admin(usuario)


# ---------- geração das datas ----------


def gerar(db: Session, plano: PlanoPreventiva, hoje: date, desde: date | None = None) -> int:
    """Cria as preventivas do plano que ainda não existem, do início até o horizonte, e garante a próxima.

    `desde`: não cria nada antes desta data (usado depois de mudar a periodicidade, para não inventar atrasos).
    Devolve quantas criou (sem commit).
    """
    if not plano.ativo:
        return 0
    existentes = set(db.scalars(select(Preventiva.data_prevista).where(Preventiva.plano_id == plano.id))) \
        if plano.id else set()
    fim = hoje + timedelta(days=HORIZONTE_DIAS)
    tem_futura = any(d > hoje for d in existentes)  # sempre existe uma data depois de hoje
    criadas = 0
    for k in range(MAX_OCORRENCIAS):
        prevista = data_da_ocorrencia(plano.inicio, k, plano.intervalo, plano.unidade)
        if prevista > fim and tem_futura:
            break
        if desde is not None and prevista < desde:
            continue
        if prevista not in existentes:
            db.add(Preventiva(plano=plano, empresa_id=plano.empresa_id, data_prevista=prevista))
            criadas += 1
        tem_futura = tem_futura or prevista > hoje
    return criadas


def garantir(db: Session, hoje: date) -> None:
    """Completa as datas dos planos ativos (chamada ao abrir as telas). Nunca preenche para trás."""
    criadas = 0
    for plano in db.scalars(select(PlanoPreventiva).where(PlanoPreventiva.ativo.is_(True))):
        ultima = db.scalar(select(Preventiva.data_prevista).where(Preventiva.plano_id == plano.id)
                           .order_by(Preventiva.data_prevista.desc()).limit(1))
        criadas += gerar(db, plano, hoje, desde=ultima + timedelta(days=1) if ultima else hoje)
    if criadas:
        db.commit()


def refazer_futuras(db: Session, plano: PlanoPreventiva, hoje: date) -> None:
    """Depois de mudar a periodicidade, o início ou a situação do plano: troca as preventivas ainda programadas
    de hoje em diante pelas datas novas. O que já venceu ou foi registrado fica como está."""
    for p in list(plano.preventivas):
        if p.status == StatusPreventiva.PROGRAMADA and p.data_prevista >= hoje:
            plano.preventivas.remove(p)  # delete-orphan apaga
    db.flush()
    gerar(db, plano, hoje, desde=hoje)


# ---------- indicadores ----------


def resumo_por_empresa(preventivas: list[Preventiva], hoje: date) -> list[dict]:
    """Previsto x realizado por empresa, para a fiscalização.

    O cumprimento considera só o que já deveria ter sido feito: as realizadas, as não realizadas e as atrasadas.
    """
    por_empresa: dict[int, dict] = {}
    for p in preventivas:
        s = situacao(p, hoje)
        r = por_empresa.setdefault(p.empresa_id, dict(
            empresa=p.empresa, previstas=0, realizadas=0, no_prazo=0, com_atraso=0, atrasadas=0, nao_realizadas=0,
            aguardando_ateste=0, atestadas=0))
        r["previstas"] += 1
        if p.status == StatusPreventiva.REALIZADA:
            r["realizadas"] += 1
            r["no_prazo" if s == SituacaoPreventiva.REALIZADA else "com_atraso"] += 1
            r["aguardando_ateste" if p.atestada_em is None else "atestadas"] += 1
        elif s == SituacaoPreventiva.ATRASADA:
            r["atrasadas"] += 1
        elif s == SituacaoPreventiva.NAO_REALIZADA:
            r["nao_realizadas"] += 1
    saida = []
    for r in sorted(por_empresa.values(), key=lambda r: r["empresa"].nome):
        devidas = r["realizadas"] + r["atrasadas"] + r["nao_realizadas"]
        r["cumprimento_pct"] = round(100 * r["realizadas"] / devidas, 1) if devidas else None
        saida.append(r)
    return saida
