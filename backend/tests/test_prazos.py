from datetime import date, timedelta

from app.config import Settings
from app.models import NivelAlerta, StatusOficio
from app.services.prazos import Calendario, _pascoa, classificar, feriados_nacionais


def test_dias_corridos_contam_fim_de_semana_e_feriado():
    cal = Calendario()
    assert cal.dias_decorridos(date(2026, 10, 16), date(2026, 10, 19)) == 3  # sex -> seg
    assert cal.dias_decorridos(date(2026, 10, 16), date(2026, 10, 18)) == 2  # sex -> dom
    assert cal.dias_decorridos(date(2026, 10, 9), date(2026, 10, 13)) == 4  # com o feriado de 12/10
    assert cal.dias_decorridos(date(2026, 10, 20), date(2026, 10, 20)) == 0
    assert cal.dias_decorridos(date(2026, 10, 21), date(2026, 10, 20)) == 0  # nunca negativo


def test_data_limite_e_a_fronteira_exata():
    cal = Calendario()
    for deslocamento in range(14):
        hoje = date(2026, 10, 8) + timedelta(days=deslocamento)
        for n in range(1, 60):
            limite = cal.data_limite(n, hoje)
            assert cal.dias_decorridos(limite, hoje) >= n
            assert cal.dias_decorridos(limite + timedelta(days=1), hoje) < n


def test_niveis_de_alerta():
    cal, hoje = Calendario(), date(2026, 10, 20)

    def nivel(d):
        return classificar(StatusOficio.PENDENTE_RESPOSTA, d, None, hoje, cal, 15, 30)

    assert nivel(date(2026, 10, 6)) == (14, NivelAlerta.NORMAL)
    assert nivel(date(2026, 10, 5)) == (15, NivelAlerta.ATENCAO)
    assert nivel(date(2026, 9, 21)) == (29, NivelAlerta.ATENCAO)
    assert nivel(date(2026, 9, 20)) == (30, NivelAlerta.CRITICO)


def test_respondido_nao_tem_alerta_e_conta_ate_a_resposta():
    cal = Calendario()
    dias, nivel = classificar(
        StatusOficio.CONFIRMADO, date(2026, 9, 1), date(2026, 9, 8), date(2026, 10, 20), cal, 15, 30
    )
    assert (dias, nivel) == (7, None)


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
