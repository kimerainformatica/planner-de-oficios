"""Horas úteis: só contam as horas do expediente em dias úteis (segunda a sexta, sem os feriados cadastrados).

Exemplo com expediente das 08:00 às 18:00 (10 h por dia): um chamado aberto na sexta às 15:00 com prazo de 24 h
úteis usa 3 h na sexta, 10 h na segunda, 10 h na terça e vence na quarta às 09:00.
"""

from datetime import date, datetime, time, timedelta

from app.services.prazos import CalendarioUtil

UM_DIA = timedelta(days=1)


class Expediente:
    def __init__(self, calendario: CalendarioUtil, inicio: time, fim: time):
        if fim != time(0) and fim <= inicio:
            raise ValueError("O fim do expediente deve ser depois do início")
        self.calendario = calendario
        self.inicio = inicio
        self.fim = fim

    def _abre(self, d: date) -> datetime:
        return datetime.combine(d, self.inicio)

    def _fecha(self, d: date) -> datetime:
        # fim 00:00 = meia-noite do dia seguinte
        return datetime.combine(d + UM_DIA, time(0)) if self.fim == time(0) else datetime.combine(d, self.fim)

    def _proximo_dia_util(self, d: date) -> date:
        d += UM_DIA
        while not self.calendario.eh_dia_util(d):
            d += UM_DIA
        return d

    def _ajustar(self, momento: datetime) -> datetime:
        """O próprio momento, se estiver no expediente; senão, a próxima abertura."""
        d = momento.date()
        if self.calendario.eh_dia_util(d):
            if momento < self._abre(d):
                return self._abre(d)
            if momento < self._fecha(d):
                return momento
        return self._abre(self._proximo_dia_util(d))

    def somar(self, inicio: datetime, horas: float) -> datetime:
        """Momento em que se completam `horas` horas úteis a partir de `inicio`."""
        restante = timedelta(hours=horas)
        atual = self._ajustar(inicio)
        while True:
            disponivel = self._fecha(atual.date()) - atual
            if restante <= disponivel:
                return atual + restante
            restante -= disponivel
            atual = self._abre(self._proximo_dia_util(atual.date()))

    def horas_entre(self, a: datetime, b: datetime) -> float:
        """Horas úteis no intervalo (a, b). Negativo se b vier antes de a."""
        if b < a:
            return -self.horas_entre(b, a)
        total = timedelta()
        d = a.date()
        while d <= b.date():
            if self.calendario.eh_dia_util(d):
                ini = max(a, self._abre(d))
                fim = min(b, self._fecha(d))
                if fim > ini:
                    total += fim - ini
            d += UM_DIA
        return total.total_seconds() / 3600
