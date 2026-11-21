"""Controle de Tetos: setores ligados aos usuários, tipos de teto com valor por vigência, lançamentos e indicadores.

"Hoje" nos testes = terça 20/10/2026 (outubro tem 31 dias). O master é o administrador geral do módulo.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.models import PeriodoTeto, TetoVigencia
from app.services.tetos import teto_entre, tetos_equivalentes

PDF = b"%PDF-1.4 nota fiscal"
T = "/api/tetos"


def vig(inicio, periodo, valor):
    return TetoVigencia(inicio=inicio, periodo=periodo, valor=valor)


# ---------- cálculo ----------


def test_proporcoes_entre_os_periodos():
    out = date(2026, 10, 20)
    assert tetos_equivalentes(PeriodoTeto.ANUAL, 12000, out) == {"diario": Decimal("32.26"), "mensal": 1000,
                                                                 "anual": 12000}
    assert tetos_equivalentes(PeriodoTeto.MENSAL, 3000, out)["anual"] == 36000
    assert tetos_equivalentes(PeriodoTeto.DIARIO, 50, out) == {"diario": 50, "mensal": 1550, "anual": 18250}

    anual = [vig(date(2026, 1, 1), PeriodoTeto.ANUAL, 12000)]
    assert teto_entre(anual, date(2026, 1, 1), date(2026, 12, 31)) == 12000  # o ano fecha exato
    assert teto_entre(anual, date(2026, 2, 1), date(2026, 2, 28)) == 1000  # qualquer mês = 1/12
    mensal = [vig(date(2026, 1, 1), PeriodoTeto.MENSAL, 3000)]
    assert teto_entre(mensal, date(2026, 2, 1), date(2026, 2, 28)) == 3000
    assert teto_entre(mensal, date(2026, 10, 1), date(2026, 10, 20)) == Decimal("1935.48")  # 3000 × 20/31


def test_novo_valor_vale_a_partir_da_data_e_o_primeiro_vale_para_tras():
    vigencias = [vig(date(2026, 3, 1), PeriodoTeto.MENSAL, 3000), vig(date(2026, 10, 16), PeriodoTeto.MENSAL, 6000)]
    # Outubro: 15 dias a 3.000/mês e 16 dias a 6.000/mês
    assert teto_entre(vigencias, date(2026, 10, 1), date(2026, 10, 31)) == Decimal("4548.39")
    # Antes da primeira vigência, vale a primeira
    assert teto_entre(vigencias, date(2026, 1, 1), date(2026, 1, 31)) == 3000


# ---------- montagem ----------


def criar_setor(api, quem, nome):
    r = api.post(f"{T}/setores", json={"nome": nome}, headers=quem)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def criar_usuario_do_setor(api, master, login, setor_id):
    r = api.post("/api/usuarios", json={
        "nome": login.title(), "login": login, "senha": f"senha-{login}",
        "modulos": [{"modulo": "TETOS", "perfil": "CLIENTE", "setor_id": setor_id}]}, headers=master)
    assert r.status_code == 201, r.text
    t = api.post("/api/auth/login", data={"username": login, "password": f"senha-{login}"})
    return {"Authorization": f"Bearer {t.json()['access_token']}"}


def criar_tipo(api, quem, setor_id, nome="Material de escritório", periodo="ANUAL", valor=12000, **extra):
    r = api.post(f"{T}/tipos", json={"setor_id": setor_id, "nome": nome, "periodo": periodo, "valor": valor,
                                     "inicio": "2026-01-01", **extra}, headers=quem)
    assert r.status_code == 201, r.text
    return r.json()


def lancar(api, quem, tipo_id, data, valor, descricao="Compra", arquivo=False, **extra):
    return api.post(f"{T}/gastos", data={"tipo_id": tipo_id, "data": data, "valor": valor, "descricao": descricao,
                                         **extra},
                    files={"arquivo": ("nota.pdf", PDF)} if arquivo else None, headers=quem)


@pytest.fixture
def cenario(api, master):
    ger = criar_setor(api, master, "Gerência Operacional")
    rh = criar_setor(api, master, "Recursos Humanos")
    joao = criar_usuario_do_setor(api, master, "joao.dantas", ger)
    lia = criar_usuario_do_setor(api, master, "lia", rh)
    escritorio = criar_tipo(api, master, ger)
    combustivel = criar_tipo(api, master, ger, nome="Combustível", periodo="MENSAL", valor=300, unidade="litros",
                             alerta_pct=90)
    copa = criar_tipo(api, master, rh, nome="Copa", periodo="MENSAL", valor=500)
    return {"ger": ger, "rh": rh, "joao": joao, "lia": lia, "escritorio": escritorio["id"],
            "combustivel": combustivel["id"], "copa": copa["id"]}


# ---------- usuários e permissões ----------


def test_usuario_do_setor_precisa_do_setor_e_o_login_mostra_o_setor(api, master, cenario):
    r = api.post("/api/usuarios", json={"nome": "Sem setor", "login": "semsetor", "senha": "senha-semsetor",
                                        "modulos": [{"modulo": "TETOS", "perfil": "CLIENTE"}]}, headers=master)
    assert r.status_code == 422 and "setor" in r.text
    eu = api.get("/api/auth/me", headers=cenario["joao"]).json()
    assert eu["modulos"] == [{"modulo": "TETOS", "perfil": "CLIENTE", "empresa_id": None, "empresa_nome": None,
                              "setor_id": cenario["ger"], "setor_nome": "Gerência Operacional"}]
    assert api.get(f"{T}/resumo", headers=cenario["joao"]).json() == {
        "eh_gestor": False, "setor": {"id": cenario["ger"], "nome": "Gerência Operacional"}}
    modulos = [m["modulo"] for m in api.get("/api/modulos", headers=cenario["joao"]).json()]
    assert modulos == ["TETOS"]


def test_so_o_administrador_define_setores_tipos_e_valores(api, cenario):
    joao = cenario["joao"]
    assert api.post(f"{T}/setores", json={"nome": "Outro"}, headers=joao).status_code == 403
    r = api.post(f"{T}/tipos", json={"setor_id": cenario["ger"], "nome": "Xerox", "periodo": "MENSAL", "valor": 10},
                 headers=joao)
    assert r.status_code == 403
    r = api.post(f"{T}/tipos/{cenario['escritorio']}/vigencias",
                 json={"periodo": "ANUAL", "valor": 99999, "inicio": "2026-10-01"}, headers=joao)
    assert r.status_code == 403
    assert api.patch(f"{T}/tipos/{cenario['escritorio']}", json={"alerta_pct": 50}, headers=joao).status_code == 403


def test_quem_nao_tem_o_modulo_nao_entra(api, ana):
    assert api.get(f"{T}/painel", headers=ana).status_code == 403


def test_cada_setor_ve_so_o_que_e_dele(api, master, cenario):
    joao, lia = cenario["joao"], cenario["lia"]
    assert [t["nome"] for t in api.get(f"{T}/tipos", headers=joao).json()] == ["Combustível", "Material de escritório"]
    assert [t["nome"] for t in api.get(f"{T}/tipos", headers=lia).json()] == ["Copa"]
    assert api.get(f"{T}/tipos/{cenario['copa']}", headers=joao).status_code == 404
    assert lancar(api, joao, cenario["copa"], "2026-10-20", "10").status_code == 404
    assert [s["nome"] for s in api.get(f"{T}/setores", headers=joao).json()] == ["Gerência Operacional"]
    g = lancar(api, lia, cenario["copa"], "2026-10-20", "45,90").json()
    assert api.patch(f"{T}/gastos/{g['id']}", json={"valor": 1}, headers=joao).status_code == 404
    assert api.delete(f"{T}/gastos/{g['id']}", headers=joao).status_code == 404
    assert api.get(f"{T}/gastos", params={"setor_id": cenario["rh"]}, headers=joao).status_code == 404
    # O administrador vê os dois setores
    nomes = [s["setor"]["nome"] for s in api.get(f"{T}/painel", headers=master).json()["setores"]]
    assert nomes == ["Gerência Operacional", "Recursos Humanos"]


# ---------- lançamentos ----------


def test_lancar_corrigir_e_excluir_gasto_com_comprovante(api, master, cenario):
    joao = cenario["joao"]
    r = lancar(api, joao, cenario["escritorio"], "2026-10-20", "1.234,56", "Papel A4 e toner", arquivo=True,
               documento="NF 4521")
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["valor"] == 1234.56 and g["documento"] == "NF 4521" and g["arquivo_nome"] == "nota.pdf"
    assert g["registrado_por"]["nome"] == "Joao.Dantas" and g["pode_editar"]
    assert api.get(f"{T}/gastos/{g['id']}/arquivo", headers=joao).content == PDF

    assert lancar(api, joao, cenario["escritorio"], "2026-10-21", "10").status_code == 422  # futuro
    assert lancar(api, joao, cenario["escritorio"], "2026-10-20", "0").status_code == 422
    assert lancar(api, joao, cenario["escritorio"], "2026-10-20", "10,555").status_code == 422

    r = api.patch(f"{T}/gastos/{g['id']}", json={"valor": 1200, "data": "2026-10-19"}, headers=joao)
    assert r.status_code == 200 and r.json()["valor"] == 1200 and r.json()["atualizado_por"]["nome"] == "Joao.Dantas"
    assert api.patch(f"{T}/gastos/{g['id']}", json={"valor": 1200}, headers=joao).status_code == 409

    lista = api.get(f"{T}/gastos", params={"busca": "toner"}, headers=joao).json()
    assert lista["total"] == 1 and lista["totais"][0]["total"] == 1200

    assert api.delete(f"{T}/gastos/{g['id']}", headers=joao).status_code == 204
    assert api.get(f"{T}/gastos", headers=joao).json()["total"] == 0
    atividades = [a["descricao"] for a in api.get("/api/auditoria", headers=master).json()["itens"]]
    assert any(a.startswith("Lançou R$ 1.234,56 em 20/10/2026") for a in atividades)
    assert any(a.startswith("Corrigiu o lançamento: R$ 1.200,00 em 19/10/2026") for a in atividades)
    assert any(a.startswith("Excluiu o lançamento") for a in atividades)


def test_tipo_desativado_nao_recebe_lancamento_e_com_lancamentos_nao_se_exclui(api, master, cenario):
    joao = cenario["joao"]
    assert lancar(api, joao, cenario["combustivel"], "2026-10-20", "40").status_code == 201
    assert api.delete(f"{T}/tipos/{cenario['combustivel']}", headers=master).status_code == 409
    assert api.patch(f"{T}/tipos/{cenario['combustivel']}", json={"ativo": False}, headers=master).status_code == 200
    assert lancar(api, joao, cenario["combustivel"], "2026-10-20", "40").status_code == 409
    assert [t["nome"] for t in api.get(f"{T}/tipos", headers=joao).json()] == ["Material de escritório"]
    # Sem lançamentos, exclui; setor com tipos ou usuários não se exclui
    assert api.delete(f"{T}/tipos/{cenario['escritorio']}", headers=master).status_code == 204
    assert api.delete(f"{T}/setores/{cenario['ger']}", headers=master).status_code == 409
    vazio = criar_setor(api, master, "Almoxarifado")
    assert api.delete(f"{T}/setores/{vazio}", headers=master).status_code == 204


# ---------- indicadores ----------


def test_painel_mostra_dia_mes_e_ano_com_situacao_e_projecao(api, cenario):
    joao = cenario["joao"]
    for dia, valor in (("2026-10-20", "150"), ("2026-10-05", "700"), ("2026-03-10", "2000")):
        assert lancar(api, joao, cenario["escritorio"], dia, valor).status_code == 201
    assert lancar(api, joao, cenario["combustivel"], "2026-10-02", "80").status_code == 201

    painel = api.get(f"{T}/painel", headers=joao).json()
    assert painel["referencia"] == "2026-10-20"
    setor = painel["setores"][0]
    esc = next(i for i in setor["tipos"] if i["tipo"]["nome"] == "Material de escritório")
    assert esc["dia"] == {"gasto": 150, "teto": 32.26, "percentual": 465.0, "restante": -117.74, "situacao": "ESTOURADO"}
    assert esc["mes"]["gasto"] == 850 and esc["mes"]["teto"] == 1000 and esc["mes"]["percentual"] == 85.0
    assert esc["mes"]["situacao"] == "ATENCAO"  # passou dos 80% de alerta
    assert esc["mes"]["teto_ate_hoje"] == pytest.approx(645.16)  # 1000 × 20/31
    assert esc["mes"]["projecao"] == pytest.approx(1317.5) and esc["mes"]["projecao_estoura"]
    assert esc["ano"] == {"gasto": 2850, "teto": 12000, "percentual": 23.8, "restante": 9150, "situacao": "NORMAL"}
    comb = next(i for i in setor["tipos"] if i["tipo"]["nome"] == "Combustível")
    assert comb["tipo"]["unidade"] == "litros" and comb["mes"]["situacao"] == "NORMAL"
    # Totais só somam a mesma unidade
    assert {t["unidade"]: t["mes"]["gasto"] for t in setor["totais"]} == {"R$": 850, "litros": 80}
    assert painel["em_atencao"] == 1 and painel["estourados"] == 0

    # Data de referência no passado (31/03): o mês de março estourou o teto
    set_ = api.get(f"{T}/painel", params={"data": "2026-03-31"}, headers=joao).json()["setores"][0]
    esc_marco = next(i for i in set_["tipos"] if i["tipo"]["nome"] == "Material de escritório")
    assert esc_marco["mes"]["gasto"] == 2000 and esc_marco["mes"]["situacao"] == "ESTOURADO"


def test_indicadores_dia_a_dia_mes_a_mes_e_ano_a_ano(api, master, cenario):
    joao = cenario["joao"]
    for dia, valor in (("2026-10-20", "150"), ("2026-10-05", "700"), ("2026-03-10", "2000"), ("2025-12-01", "500")):
        assert lancar(api, joao, cenario["escritorio"], dia, valor).status_code == 201
    # A partir de 16/10, o teto sobe para 24.000/ano
    r = api.post(f"{T}/tipos/{cenario['escritorio']}/vigencias",
                 json={"periodo": "ANUAL", "valor": 24000, "inicio": "2026-10-16", "motivo": "Novo contrato"},
                 headers=master)
    assert r.status_code == 200 and [v["valor"] for v in r.json()["vigencias"]] == [24000, 12000]

    ind = api.get(f"{T}/tipos/{cenario['escritorio']}/indicadores", headers=joao).json()
    assert (ind["ano"], ind["mes"], ind["referencia"]) == (2026, 10, "2026-10-20")
    assert len(ind["diario"]) == 31
    assert ind["diario"][4] == {"data": "2026-10-05", "gasto": 700, "teto": 32.26, "acumulado": 700,
                                "teto_acumulado": pytest.approx(161.29)}
    assert ind["diario"][19]["teto"] == pytest.approx(64.52)  # 2.000/mês ÷ 31 depois de 16/10
    assert ind["mensal"][2] == {"mes": 3, "gasto": 2000, "teto": 1000}
    assert ind["mensal"][9]["teto"] == pytest.approx(1516.13)  # 15 dias a 1.000/mês e 16 a 2.000/mês
    assert ind["anual"] == [{"ano": 2025, "gasto": 500, "teto": 12000},
                            {"ano": 2026, "gasto": 2850, "teto": pytest.approx(14516.13)}]

    # Um mês passado: os cartões ficam no fim do mês escolhido
    marco = api.get(f"{T}/tipos/{cenario['escritorio']}/indicadores", params={"ano": 2026, "mes": 3},
                    headers=joao).json()
    assert marco["referencia"] == "2026-03-31" and marco["resumo"]["mes"]["gasto"] == 2000

    # O valor só pode ser removido se sobrar outro
    vigencias = api.get(f"{T}/tipos/{cenario['escritorio']}", headers=master).json()["vigencias"]
    assert api.delete(f"{T}/vigencias/{vigencias[0]['id']}", headers=master).status_code == 200
    assert api.delete(f"{T}/vigencias/{vigencias[1]['id']}", headers=master).status_code == 409
