"""Regras do Controle de Tetos: teto de cada dia (pelas vigências), consumo por período, situação e projeção.

Como o teto é definido: cada tipo tem vigências (valor + período base a partir de uma data). O teto de um dia sai
da vigência daquele dia, por proporção:

- DIARIO: o próprio valor;
- MENSAL: valor ÷ dias do mês;
- ANUAL: (valor ÷ 12) ÷ dias do mês. Ou seja, R$ 12.000/ano = R$ 1.000 em qualquer mês.

O teto de um período (mês, ano, ou do início do mês até hoje) é a soma dos tetos dos dias. Assim, um teto mensal
de R$ 3.000 dá exatamente R$ 3.000 no mês, um anual de R$ 12.000 dá R$ 12.000 no ano, e uma mudança de teto no meio
do mês vale só a partir do dia dela. A primeira vigência vale também para os dias anteriores a ela.
"""

from calendar import monthrange
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import GastoTeto, Modulo, Perfil, PeriodoTeto, Setor, TetoVigencia, TipoTeto, Usuario

CENTAVO = Decimal("0.01")
ZERO = Decimal("0")


class SituacaoTeto(str, Enum):
    NORMAL = "NORMAL"  # abaixo do alerta
    ATENCAO = "ATENCAO"  # atingiu o % de alerta do tipo
    ESTOURADO = "ESTOURADO"  # passou do teto
    SEM_TETO = "SEM_TETO"  # teto zero no período


def dec(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def arredondar(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO)


def dias_do_mes(d: date) -> int:
    return monthrange(d.year, d.month)[1]


def fim_do_mes(d: date) -> date:
    return d.replace(day=dias_do_mes(d))


# ---------- teto ----------


def vigencia_em(vigencias: Sequence[TetoVigencia], dia: date) -> TetoVigencia | None:
    """A vigência daquele dia (as vigências vêm ordenadas pelo início). Antes da primeira, vale a primeira."""
    escolhida = vigencias[0] if vigencias else None
    for v in vigencias:
        if v.inicio <= dia:
            escolhida = v
        else:
            break
    return escolhida


def teto_do_dia(vigencias: Sequence[TetoVigencia], dia: date) -> Decimal:
    v = vigencia_em(vigencias, dia)
    if v is None:
        return ZERO
    valor = dec(v.valor)
    if v.periodo == PeriodoTeto.DIARIO:
        return valor
    mensal = valor if v.periodo == PeriodoTeto.MENSAL else valor / 12
    return mensal / dias_do_mes(dia)


def teto_entre(vigencias: Sequence[TetoVigencia], inicio: date, fim: date) -> Decimal:
    """Soma dos tetos dos dias de `inicio` a `fim` (inclusive), arredondada no centavo."""
    total, dia = ZERO, inicio
    while dia <= fim:
        total += teto_do_dia(vigencias, dia)
        dia += timedelta(days=1)
    return arredondar(total)


def tetos_equivalentes(periodo: PeriodoTeto, valor, referencia: date) -> dict[str, Decimal]:
    """Os três tetos de uma vigência, para mostrar no cadastro (o diário e o mensal no mês de `referencia`)."""
    valor = dec(valor)
    dias_mes = dias_do_mes(referencia)
    dias_ano = 366 if monthrange(referencia.year, 2)[1] == 29 else 365
    if periodo == PeriodoTeto.DIARIO:
        return {"diario": arredondar(valor), "mensal": arredondar(valor * dias_mes), "anual": arredondar(valor * dias_ano)}
    mensal = valor if periodo == PeriodoTeto.MENSAL else valor / 12
    anual = valor if periodo == PeriodoTeto.ANUAL else valor * 12
    return {"diario": arredondar(mensal / dias_mes), "mensal": arredondar(mensal), "anual": arredondar(anual)}


# ---------- consumo ----------


@dataclass
class Consumo:
    gasto: Decimal
    teto: Decimal
    percentual: float | None  # gasto ÷ teto × 100 (None sem teto)
    restante: Decimal
    situacao: SituacaoTeto


def consumo(gasto: Decimal, teto: Decimal, alerta_pct: int) -> Consumo:
    gasto, teto = arredondar(dec(gasto)), arredondar(dec(teto))
    if teto <= 0:
        return Consumo(gasto, teto, None, ZERO - gasto, SituacaoTeto.SEM_TETO)
    pct = float(gasto / teto * 100)
    if gasto > teto:
        situacao = SituacaoTeto.ESTOURADO
    elif pct >= alerta_pct:
        situacao = SituacaoTeto.ATENCAO
    else:
        situacao = SituacaoTeto.NORMAL
    return Consumo(gasto, teto, round(pct, 1), teto - gasto, situacao)


def projecao_do_mes(gasto_ate_hoje: Decimal, referencia: date, hoje: date) -> Decimal:
    """No mês corrente: no ritmo atual, quanto se gasta até o fim do mês. Em meses passados: o próprio gasto."""
    if (referencia.year, referencia.month) != (hoje.year, hoje.month):
        return arredondar(dec(gasto_ate_hoje))
    return arredondar(dec(gasto_ate_hoje) / hoje.day * dias_do_mes(hoje))


def somar(gastos_por_dia: dict[date, Decimal], inicio: date, fim: date) -> Decimal:
    return sum((v for d, v in gastos_por_dia.items() if inicio <= d <= fim), ZERO)


def serie_diaria(vigencias, gastos_por_dia: dict[date, Decimal], ano: int, mes: int) -> list[dict]:
    primeiro = date(ano, mes, 1)
    linhas, acumulado, teto_acumulado = [], ZERO, ZERO
    for i in range(dias_do_mes(primeiro)):
        dia = primeiro + timedelta(days=i)
        gasto, teto = gastos_por_dia.get(dia, ZERO), teto_do_dia(vigencias, dia)
        acumulado += gasto
        teto_acumulado += teto
        linhas.append({"data": dia, "gasto": arredondar(gasto), "teto": arredondar(teto),
                       "acumulado": arredondar(acumulado), "teto_acumulado": arredondar(teto_acumulado)})
    return linhas


def serie_mensal(vigencias, gastos_por_dia: dict[date, Decimal], ano: int) -> list[dict]:
    linhas = []
    for mes in range(1, 13):
        inicio = date(ano, mes, 1)
        fim = fim_do_mes(inicio)
        linhas.append({"mes": mes, "gasto": arredondar(somar(gastos_por_dia, inicio, fim)),
                       "teto": teto_entre(vigencias, inicio, fim)})
    return linhas


def serie_anual(vigencias, gastos_por_dia: dict[date, Decimal], anos: Iterable[int]) -> list[dict]:
    return [{"ano": a, "gasto": arredondar(somar(gastos_por_dia, date(a, 1, 1), date(a, 12, 31))),
             "teto": teto_entre(vigencias, date(a, 1, 1), date(a, 12, 31))} for a in anos]


# ---------- papéis e visibilidade ----------


def papel(usuario: Usuario) -> Perfil | None:
    return usuario.perfil_no(Modulo.TETOS)


def eh_gestor(usuario: Usuario) -> bool:
    """Administrador do módulo (ou MASTER): define setores, tipos e tetos, e vê todos os setores."""
    return usuario.eh_admin_no(Modulo.TETOS)


def setor_do(usuario: Usuario) -> Setor | None:
    acesso = usuario.acesso_no(Modulo.TETOS)
    return acesso.setor if acesso else None


def setor_visivel(usuario: Usuario, setor_id: int) -> bool:
    if eh_gestor(usuario):
        return True
    meu = setor_do(usuario)
    return meu is not None and meu.id == setor_id


def exigir_gestor(usuario: Usuario) -> None:
    if not eh_gestor(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Só o administrador do Controle de Tetos define setores, tipos e valores de teto")


def buscar_tipo(db: Session, tipo_id: int, usuario: Usuario) -> TipoTeto:
    tipo = db.get(TipoTeto, tipo_id)
    if tipo is None or not setor_visivel(usuario, tipo.setor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo de teto não encontrado")
    return tipo


def buscar_gasto(db: Session, gasto_id: int, usuario: Usuario) -> GastoTeto:
    gasto = db.get(GastoTeto, gasto_id)
    if gasto is None or not setor_visivel(usuario, gasto.setor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lançamento não encontrado")
    return gasto


def formatar(valor: Decimal, unidade: str) -> str:
    """R$ 1.234,56 · 12,5 litros (para as descrições do registro de atividades)."""
    texto = f"{arredondar(dec(valor)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}" if unidade.strip().upper() == "R$" else f"{texto} {unidade}"
