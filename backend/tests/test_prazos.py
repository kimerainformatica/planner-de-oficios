import random
from datetime import date, timedelta

from app.config import Settings
from app.models import NivelAlerta, StatusOficio
from app.services.prazos import CalendarioUtil, _pascoa, classificar, feriados_nacionais


def contagem_ingenua(cal: CalendarioUtil, inicio: date, fim: date) -> int:
    total, d = 0, inicio + timedelta(days=1)
    while d <= fim:
        total += cal.eh_dia_util(d)
        d += timedelta(days=1)
    return total


def test_fim_de_semana_nao_conta():
    cal = CalendarioUtil()
    assert cal.dias_uteis_decorridos(date(2026, 10, 16), date(2026, 10, 19)) == 1  # sex -> seg
    assert cal.dias_uteis_decorridos(date(2026, 10, 16), date(2026, 10, 18)) == 0  # sex -> dom
    assert cal.dias_uteis_decorridos(date(2026, 10, 20), date(2026, 10, 20)) == 0


def test_feriado_nao_conta():
    cal = CalendarioUtil([date(2026, 10, 12)])
    assert cal.dias_uteis_decorridos(date(2026, 10, 9), date(2026, 10, 13)) == 1


def test_contagem_rapida_igual_a_ingenua():
    rnd = random.Random(42)
    feriados = [date(2026, 1, 1) + timedelta(days=rnd.randrange(700)) for _ in range(40)]
    cal = CalendarioUtil(feriados)
    for _ in range(500):
        inicio = date(2025, 12, 1) + timedelta(days=rnd.randrange(700))
        fim = inicio + timedelta(days=rnd.randrange(120))
        assert cal.dias_uteis_decorridos(inicio, fim) == contagem_ingenua(cal, inicio, fim)


def test_data_limite_e_a_fronteira_exata():
    cal = CalendarioUtil(d for d, _ in feriados_nacionais(2026))
    for deslocamento in range(14):  # vários "hoje", incluindo fins de semana e feriados
        hoje = date(2026, 10, 8) + timedelta(days=deslocamento)
        for n in range(1, 40):
            limite = cal.data_limite(n, hoje)
            assert cal.dias_uteis_decorridos(limite, hoje) >= n
            assert cal.dias_uteis_decorridos(limite + timedelta(days=1), hoje) < n


def test_niveis_de_alerta():
    cal, hoje = CalendarioUtil(), date(2026, 10, 20)

    def nivel(d):
        return classificar(StatusOficio.PENDENTE_RESPOSTA, d, None, hoje, cal, 15, 30)

    assert nivel(date(2026, 9, 30)) == (14, NivelAlerta.NORMAL)
    assert nivel(date(2026, 9, 29)) == (15, NivelAlerta.ATENCAO)
    assert nivel(date(2026, 9, 9)) == (29, NivelAlerta.ATENCAO)
    assert nivel(date(2026, 9, 8)) == (30, NivelAlerta.CRITICO)


def test_respondido_nao_tem_alerta_e_conta_ate_a_resposta():
    cal = CalendarioUtil()
    dias, nivel = classificar(
        StatusOficio.CONFIRMADO, date(2026, 9, 1), date(2026, 9, 8), date(2026, 10, 20), cal, 15, 30
    )
    assert (dias, nivel) == (5, None)


def test_feriados_moveis():
    assert _pascoa(2024) == date(2024, 3, 31)
    assert _pascoa(2025) == date(2025, 4, 20)
    assert _pascoa(2026) == date(2026, 4, 5)
    datas = dict(feriados_nacionais(2026))
    assert datas[date(2026, 2, 16)].startswith("Carnaval")
    assert datas[date(2026, 4, 3)] == "Sexta-feira Santa"
    assert datas[date(2026, 6, 4)] == "Corpus Christi"
    assert date(2026, 11, 20) in datas


def test_padrao_de_alerta_e_30_atencao_e_45_critico():
    campos = Settings.model_fields
    assert (campos["dias_atencao"].default, campos["dias_critico"].default) == (30, 45)


def test_limites_vem_da_configuracao(api, ana):
    assert api.get("/api/dashboard/prazos", headers=ana).json() == {"dias_atencao": 15, "dias_critico": 30}
    assert api.get("/api/dashboard/analise", headers=ana).json()["prazos"] == {"dias_atencao": 15, "dias_critico": 30}
    assert api.get("/api/dashboard/prazos").status_code == 401
