"""Contagem de dias úteis e classificação do nível de alerta.

Regra: conta-se os dias úteis APÓS o início do prazo até hoje (o próprio dia não conta).
O início do prazo é a data do ofício; se o ofício for reaberto, passa a ser a data da reabertura.
Ofícios com a resposta confirmada e entrega pendente contam o prazo da entrega a partir da data da resposta.
Dia útil = segunda a sexta que não esteja na tabela `feriados`.

Otimização: o nível de alerta não é gravado. Para filtrar no banco, calcula-se uma única vez
a "data limite" de cada nível (ex.: o prazo mais recente que já soma 30 dias úteis). Assim o
filtro vira uma comparação simples em `inicio_prazo`, que usa o índice (status, inicio_prazo).
"""

from bisect import bisect_right
from collections.abc import Iterable
from datetime import date, timedelta

from app.models import NivelAlerta, StatusOficio

UM_DIA = timedelta(days=1)


def _dias_semana_ate(d: date) -> int:
    """Quantidade de dias seg–sex de 01/01/0001 (uma segunda-feira) até `d`, inclusive."""
    semanas, resto = divmod(d.toordinal(), 7)
    return semanas * 5 + min(resto, 5)


class CalendarioUtil:
    def __init__(self, feriados: Iterable[date] = ()):
        self._feriados = set(feriados)
        self._feriados_em_dia_semana = sorted(f for f in self._feriados if f.weekday() < 5)

    def eh_dia_util(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self._feriados

    def dias_uteis_decorridos(self, inicio: date, fim: date) -> int:
        """Dias úteis no intervalo (inicio, fim]."""
        if fim <= inicio:
            return 0
        dias = _dias_semana_ate(fim) - _dias_semana_ate(inicio)
        feriados = bisect_right(self._feriados_em_dia_semana, fim) - bisect_right(
            self._feriados_em_dia_semana, inicio
        )
        return dias - feriados

    def data_limite(self, dias_uteis: int, hoje: date) -> date:
        """Início de prazo mais recente que, em `hoje`, já acumula `dias_uteis` dias úteis.

        Todo ofício com inicio_prazo <= data_limite atingiu o prazo.
        """
        if dias_uteis <= 0:
            return hoje
        d, contados = hoje, 0
        while True:
            if self.eh_dia_util(d):
                contados += 1
                if contados == dias_uteis:
                    return d - UM_DIA
            d -= UM_DIA


def classificar(
    status: StatusOficio,
    inicio_prazo: date,
    data_resposta: date | None,
    hoje: date,
    calendario: CalendarioUtil,
    dias_atencao: int,
    dias_critico: int,
) -> tuple[int, NivelAlerta | None]:
    """Retorna (dias úteis decorridos, nível de alerta).

    Pendente de resposta: dias desde o início do prazo. Pendente de recebimento: dias desde a resposta.
    Encerrados: dias do início do prazo até a resposta (tempo de resposta), sem nível de alerta.
    """
    if status == StatusOficio.PENDENTE_RESPOSTA:
        inicio = inicio_prazo
    elif status == StatusOficio.PENDENTE_RECEBIMENTO:
        inicio = data_resposta or inicio_prazo
    else:
        return calendario.dias_uteis_decorridos(inicio_prazo, data_resposta or hoje), None

    dias = calendario.dias_uteis_decorridos(inicio, hoje)
    if dias >= dias_critico:
        return dias, NivelAlerta.CRITICO
    if dias >= dias_atencao:
        return dias, NivelAlerta.ATENCAO
    return dias, NivelAlerta.NORMAL


def _pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados_nacionais(ano: int) -> list[tuple[date, str]]:
    """Feriados nacionais e pontos facultativos federais que costumam suspender o expediente.

    Feriados estaduais/municipais devem ser cadastrados manualmente.
    """
    pascoa = _pascoa(ano)
    datas = [
        (date(ano, 1, 1), "Confraternização Universal"),
        (pascoa - timedelta(days=48), "Carnaval (segunda-feira)"),
        (pascoa - timedelta(days=47), "Carnaval (terça-feira)"),
        (pascoa - timedelta(days=2), "Sexta-feira Santa"),
        (date(ano, 4, 21), "Tiradentes"),
        (date(ano, 5, 1), "Dia do Trabalho"),
        (pascoa + timedelta(days=60), "Corpus Christi"),
        (date(ano, 9, 7), "Independência do Brasil"),
        (date(ano, 10, 12), "Nossa Senhora Aparecida"),
        (date(ano, 11, 2), "Finados"),
        (date(ano, 11, 15), "Proclamação da República"),
        (date(ano, 12, 25), "Natal"),
    ]
    if ano >= 2024:
        datas.append((date(ano, 11, 20), "Dia Nacional de Zumbi e da Consciência Negra"))
    return sorted(datas)
