"""Contagem de dias corridos e classificação do nível de alerta.

Regra: conta-se os dias corridos APÓS o início do prazo até hoje (o próprio dia não conta), sábados, domingos e
feriados inclusive. O início do prazo é a data do ofício; se o ofício for reaberto, passa a ser a data da
reabertura. Ofícios com a resposta confirmada e entrega pendente contam o prazo da entrega a partir da resposta.

Otimização: o nível de alerta não é gravado. Para filtrar no banco, calcula-se uma única vez a "data limite" de
cada nível (o prazo mais recente que já soma N dias). Assim o filtro vira uma comparação simples em
`inicio_prazo`, que usa o índice (status, inicio_prazo).

Os feriados continuam cadastrados (tabela `feriados`), mas não entram mais na contagem.
"""

from datetime import date, timedelta

from app.models import NivelAlerta, StatusOficio


class Calendario:
    """Contagem de prazos em dias corridos."""

    @staticmethod
    def dias_decorridos(inicio: date, fim: date) -> int:
        """Dias corridos no intervalo (inicio, fim]."""
        return max(0, (fim - inicio).days)

    @staticmethod
    def data_limite(dias: int, hoje: date) -> date:
        """Início de prazo mais recente que, em `hoje`, já acumula `dias` dias corridos.

        Todo ofício com inicio_prazo <= data_limite atingiu o prazo.
        """
        return hoje - timedelta(days=max(dias, 0))


def classificar(
    status: StatusOficio,
    inicio_prazo: date,
    data_resposta: date | None,
    hoje: date,
    calendario: Calendario,
    dias_atencao: int,
    dias_critico: int,
) -> tuple[int, NivelAlerta | None]:
    """Retorna (dias corridos decorridos, nível de alerta).

    Pendente de resposta: dias desde o início do prazo. Pendente de recebimento: dias desde a resposta.
    Encerrados: dias do início do prazo até a resposta (tempo de resposta), sem nível de alerta.
    """
    if status == StatusOficio.PENDENTE_RESPOSTA:
        inicio = inicio_prazo
    elif status == StatusOficio.PENDENTE_RECEBIMENTO:
        inicio = data_resposta or inicio_prazo
    else:
        return calendario.dias_decorridos(inicio_prazo, data_resposta or hoje), None

    dias = calendario.dias_decorridos(inicio, hoje)
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
