"""Manutenção preventiva: planos com periodicidade, agenda, realização com evidência, ateste e avisos internos.

Fixtures (conftest): paulo = operacional, marta = admin do módulo, tiago = técnico MSI,
carla = técnica REALIZA CLIMATIZAÇÃO. "Hoje" = terça 20/10/2026.
"""

from datetime import date, datetime

from app.models import UnidadePeriodo
from app.services.preventivas import data_da_ocorrencia, periodicidade

PDF = b"%PDF-1.4 checklist da preventiva"
URL = "/api/manutencao/preventivas"
PLANOS = "/api/manutencao/planos-preventiva"


def empresas(api, quem):
    return {e["nome"]: e["id"] for e in api.get("/api/manutencao/empresas", headers=quem).json()}


def plano(api, quem, empresa="MSI", **extra):
    corpo = {"empresa_id": empresas(api, quem)[empresa], "titulo": "Preventiva dos compressores",
             "descricao": "Drenar, verificar filtros e pressão.", "local": "Casa de máquinas",
             "intervalo": 1, "unidade": "MESES", "inicio": "2026-10-10", "tolerancia_dias": 5, **extra}
    return api.post(PLANOS, json=corpo, headers=quem)


def agenda(api, quem, **params):
    r = api.get(URL, params=params, headers=quem)
    assert r.status_code == 200, r.text
    return r.json()


def datas(api, quem, **params):
    return [(p["data_prevista"], p["situacao"]) for p in agenda(api, quem, **params)["itens"]]


def realizar(api, quem, pid, dia="2026-10-20", arquivo=True, **dados):
    arquivos = {"arquivo": ("checklist.pdf", PDF)} if arquivo else None
    return api.post(f"{URL}/{pid}/realizar", data={"realizada_em": dia, **dados}, files=arquivos, headers=quem)


# ---------- datas ----------


def test_datas_do_plano_e_nome_da_periodicidade():
    inicio = date(2026, 1, 31)
    assert [data_da_ocorrencia(inicio, k, 1, UnidadePeriodo.MESES) for k in range(4)] == [
        date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]  # mantém o dia do início
    assert data_da_ocorrencia(inicio, 2, 6, UnidadePeriodo.MESES) == date(2027, 1, 31)
    assert data_da_ocorrencia(date(2026, 10, 5), 3, 2, UnidadePeriodo.SEMANAS) == date(2026, 11, 16)
    assert data_da_ocorrencia(date(2026, 10, 5), 2, 45, UnidadePeriodo.DIAS) == date(2027, 1, 3)
    assert periodicidade(3, UnidadePeriodo.MESES) == "trimestral" and periodicidade(2, UnidadePeriodo.SEMANAS) == "quinzenal"
    assert periodicidade(45, UnidadePeriodo.DIAS) == "a cada 45 dias"


# ---------- planos ----------


def test_admin_cria_plano_e_as_datas_sao_geradas(api, marta, paulo, tiago):
    assert plano(api, paulo).status_code == 403  # só o administrador do módulo define a periodicidade
    assert plano(api, tiago).status_code == 403
    assert plano(api, marta, inicio="2026-07-01").status_code == 422  # mais de 60 dias atrás
    assert plano(api, marta, intervalo=0).status_code == 422

    r = plano(api, marta)
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["periodicidade"], p["empresa"]["nome"], p["proxima"], p["ativo"]) == ("mensal", "MSI", "2026-11-10", True)
    # Do início até 90 dias à frente (18/01/2027). A de 10/10 venceu em 15/10 (tolerância de 5 dias)
    assert datas(api, marta) == [("2026-10-10", "ATRASADA"), ("2026-11-10", "PROGRAMADA"), ("2026-12-10", "PROGRAMADA"),
                                 ("2027-01-10", "PROGRAMADA")]
    assert api.get(PLANOS, headers=marta).json()[0]["atrasadas"] == 1

    # Plano anual: além do início, sempre existe a próxima data, mesmo fora dos 90 dias
    plano(api, marta, titulo="Calibração anual", intervalo=12, inicio="2026-10-20", tolerancia_dias=10)
    assert datas(api, marta, plano_id=2) == [("2026-10-20", "NA_JANELA"), ("2027-10-20", "PROGRAMADA")]


def test_tecnico_ve_so_as_preventivas_da_sua_empresa(api, marta, paulo, tiago, carla):
    plano(api, marta)
    plano(api, marta, "REALIZA CLIMATIZAÇÃO", titulo="Limpeza dos filtros", inicio="2026-10-19")
    assert {p["empresa"]["nome"] for p in agenda(api, paulo)["itens"]} == {"MSI", "REALIZA CLIMATIZAÇÃO"}
    assert {p["empresa"]["nome"] for p in agenda(api, tiago)["itens"]} == {"MSI"}
    assert {p["empresa"]["nome"] for p in agenda(api, carla)["itens"]} == {"REALIZA CLIMATIZAÇÃO"}
    assert [p["titulo"] for p in api.get(PLANOS, headers=carla).json()] == ["Limpeza dos filtros"]
    da_msi = agenda(api, tiago)["itens"][0]["id"]
    assert realizar(api, carla, da_msi).status_code == 404


def test_mudar_a_periodicidade_refaz_so_as_datas_futuras(api, marta):
    pid = plano(api, marta).json()["id"]
    r = api.patch(f"{PLANOS}/{pid}", json={"intervalo": 2, "inicio": "2026-11-05"}, headers=marta)
    assert r.status_code == 200 and r.json()["periodicidade"] == "bimestral"
    # A vencida (10/10) fica; as programadas dão lugar às novas datas
    assert datas(api, marta) == [("2026-10-10", "ATRASADA"), ("2026-11-05", "PROGRAMADA"), ("2027-01-05", "PROGRAMADA")]

    # Desativar tira as futuras; excluir só é possível sem nada vencido ou registrado
    api.patch(f"{PLANOS}/{pid}", json={"ativo": False}, headers=marta)
    assert datas(api, marta) == [("2026-10-10", "ATRASADA")]
    assert api.delete(f"{PLANOS}/{pid}", headers=marta).status_code == 409
    novo = plano(api, marta, titulo="Outro", inicio="2026-11-01").json()["id"]
    assert api.delete(f"{PLANOS}/{novo}", headers=marta).status_code == 204


def test_as_datas_sao_completadas_com_o_passar_do_tempo(api, estado, marta):
    plano(api, marta)
    estado["hoje"] = date(2027, 2, 1)
    previstas = [d for d, _ in datas(api, marta)]
    assert previstas[-1] == "2027-04-10" and len(previstas) == 7  # out/2026 a abr/2027, sem repetir


# ---------- realização, ateste e fiscalização ----------


def test_tecnico_registra_a_realizacao_com_evidencia_e_o_operacional_atesta(api, marta, paulo, tiago, carla):
    plano(api, marta, inicio="2026-10-18")
    p = agenda(api, tiago)["itens"][0]
    pid = p["id"]
    assert (p["situacao"], p["limite"], p["dias"], p["pode_realizar"], p["pode_atestar"]) == (
        "NA_JANELA", "2026-10-23", -2, True, False)

    assert realizar(api, tiago, pid, dia="2026-10-21").status_code == 422  # data futura
    r = realizar(api, tiago, pid, dia="2026-10-19", observacao="Filtros trocados.")
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["situacao"], p["executor"], p["registrada_por"]["nome"], p["arquivo_nome"]) == (
        "REALIZADA", "Tiago", "Tiago", "checklist.pdf")
    assert realizar(api, tiago, pid).status_code == 409  # já registrada

    # A evidência: quem vê a preventiva baixa; a técnica de outra empresa não
    assert api.get(f"{URL}/{pid}/arquivo", headers=paulo).content == PDF
    assert api.get(f"{URL}/{pid}/arquivo", headers=carla).status_code == 404

    # O ateste é de quem fiscaliza (operacional ou administrador), nunca do técnico
    assert api.post(f"{URL}/{pid}/atestar", json={}, headers=tiago).status_code == 403
    r = api.post(f"{URL}/{pid}/atestar", json={"observacao": "Conferido no local."}, headers=paulo)
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["atestada_por"]["nome"], p["ateste_obs"], p["pode_atestar"], p["pode_reabrir"]) == (
        "Paulo", "Conferido no local.", False, False)
    assert api.post(f"{URL}/{pid}/atestar", json={}, headers=paulo).status_code == 409
    assert api.post(f"{URL}/{pid}/reabrir", headers=marta).status_code == 409  # atestada não reabre


def test_nao_realizada_reabrir_e_realizacao_com_atraso(api, marta, paulo, tiago):
    plano(api, marta)  # 10/10 já venceu (tolerância até 15/10)
    itens = agenda(api, paulo)["itens"]
    vencida, futura = itens[0]["id"], itens[1]["id"]

    assert api.post(f"{URL}/{futura}/nao-realizada", json={"motivo": "Equipamento em uso"}, headers=paulo).status_code == 409
    assert api.post(f"{URL}/{vencida}/nao-realizada", json={"motivo": "Sem acesso"}, headers=tiago).status_code == 403
    r = api.post(f"{URL}/{vencida}/nao-realizada", json={"motivo": "Empresa não compareceu"}, headers=paulo)
    assert r.status_code == 200 and (r.json()["situacao"], r.json()["motivo"]) == ("NAO_REALIZADA", "Empresa não compareceu")

    # A administradora desfaz o registro; depois a empresa registra, com atraso e sem arquivo
    assert api.post(f"{URL}/{vencida}/reabrir", headers=paulo).status_code == 403
    assert api.post(f"{URL}/{vencida}/reabrir", headers=marta).json()["situacao"] == "ATRASADA"
    r = realizar(api, tiago, vencida, dia="2026-10-19", arquivo=False, executor="Equipe MSI")
    assert r.status_code == 200, r.text
    assert (r.json()["situacao"], r.json()["executor"], r.json()["arquivo_nome"]) == (
        "REALIZADA_COM_ATRASO", "Equipe MSI", None)

    # Reabrir uma realizada apaga a evidência
    outra = realizar(api, tiago, futura, dia="2026-10-20").json()
    assert api.get(f"{URL}/{outra['id']}/arquivo", headers=paulo).status_code == 200
    assert api.post(f"{URL}/{outra['id']}/reabrir", headers=marta).json()["arquivo_nome"] is None
    assert api.get(f"{URL}/{outra['id']}/arquivo", headers=paulo).status_code == 404


def test_previsto_x_realizado_por_empresa(api, marta, paulo, tiago, carla):
    plano(api, marta, inicio="2026-09-10")  # MSI: 10/09 e 10/10 vencidas
    plano(api, marta, "REALIZA CLIMATIZAÇÃO", titulo="Limpeza dos filtros", inicio="2026-10-19")
    msi = agenda(api, tiago, de="2026-09-01", ate="2026-10-31")["itens"]
    realizar(api, tiago, msi[0]["id"], dia="2026-09-12")
    realizar(api, carla, agenda(api, carla)["itens"][0]["id"], dia="2026-10-20")

    resumo = {r["empresa"]["nome"]: r for r in agenda(api, paulo, de="2026-09-01", ate="2026-10-31")["resumo"]}
    m = resumo["MSI"]
    assert (m["previstas"], m["realizadas"], m["no_prazo"], m["atrasadas"], m["aguardando_ateste"], m["cumprimento_pct"]) == (
        2, 1, 1, 1, 1, 50.0)
    assert resumo["REALIZA CLIMATIZAÇÃO"]["cumprimento_pct"] == 100.0

    # Filtros: situação e "aguardando ateste" (o resumo continua sendo o do período)
    assert datas(api, paulo, situacao="ATRASADA") == [("2026-10-10", "ATRASADA")]
    pendentes = agenda(api, paulo, aguardando_ateste=True)
    assert len(pendentes["itens"]) == 2 and len(pendentes["resumo"]) == 2
    novembro = agenda(api, paulo, empresa_id=m["empresa"]["id"], de="2026-11-01", ate="2026-11-30")
    assert [p["situacao"] for p in novembro["itens"]] == ["PROGRAMADA"]


# ---------- avisos internos e unidade ----------


def test_avisos_internos_por_papel(api, estado, marta, paulo, tiago, carla):
    def avisos(quem):
        a = api.get("/api/manutencao/avisos", headers=quem).json()
        return a["total"], {i["chave"]: i["quantidade"] for i in a["itens"]}

    assert avisos(paulo) == (0, {})
    plano(api, marta)  # 10/10 atrasada
    plano(api, marta, titulo="Calibração", inicio="2026-10-22")  # na janela
    api.post("/api/manutencao/chamados", headers=paulo, json={
        "empresa_id": empresas(api, paulo)["MSI"], "titulo": "Monitor sem imagem", "descricao": "Não liga no leito 4."})

    assert avisos(tiago) == (2, {"PREVENTIVAS_ATRASADAS": 1, "PREVENTIVAS_NA_JANELA": 1, "CHAMADOS_AGUARDANDO": 1})
    assert avisos(carla) == (0, {})  # nada da empresa dela
    assert avisos(paulo) == (2, {"PREVENTIVAS_ATRASADAS": 1, "PREVENTIVAS_NA_JANELA": 1})

    # O chamado atrasa e a preventiva realizada passa a esperar o ateste do operacional
    estado["agora"] = datetime(2026, 10, 26, 10)
    estado["hoje"] = date(2026, 10, 26)
    na_janela = next(p for p in agenda(api, tiago)["itens"] if p["plano"]["titulo"] == "Calibração")
    realizar(api, tiago, na_janela["id"], dia="2026-10-23")
    total, itens = avisos(paulo)
    assert itens == {"CHAMADOS_ATRASADOS": 1, "PREVENTIVAS_ATRASADAS": 1, "PREVENTIVAS_SEM_ATESTE": 1} and total == 3
    assert "PREVENTIVAS_SEM_ATESTE" not in avisos(tiago)[1]
    primeiro = api.get("/api/manutencao/avisos", headers=paulo).json()["itens"][0]
    assert primeiro["nivel"] == "CRITICO" and primeiro["link"].startswith("/manutencao/")


def test_planner_sem_acesso_as_preventivas(api, ana):
    assert api.get(URL, headers=ana).status_code == 403
    assert api.get("/api/manutencao/avisos", headers=ana).status_code == 403


def test_unidade_do_servidor_e_publica(api):
    assert api.get("/api/unidade").json() == {"nome": None, "descricao": None}
