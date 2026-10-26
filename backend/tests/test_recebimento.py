"""Etapa de recebimento dos ofícios de itens: resposta confirmada → pendente de recebimento → recebido."""

from datetime import date

PDF = b"%PDF-1.4 entrega"


def criar(api, quem, numero, tipo="EPIS", data="2026-08-03"):
    r = api.post("/api/oficios", json={"numero": numero, "data_oficio": data, "tipo": tipo}, headers=quem)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def status(api, quem, oid, novo, **datas):
    return api.patch(f"/api/oficios/{oid}/status", json={"status": novo, **datas}, headers=quem)


def anexar(api, quem, oid, tipo, evento):
    arquivo = {"arquivo": ("entrega.pdf", PDF, "application/pdf")}
    return api.post(f"/api/oficios/{oid}/anexos/{tipo}", params={"historico_id": evento}, files=arquivo,
                    headers=quem)


def test_oficio_de_itens_fica_pendente_de_recebimento(api, ana, bruno):
    oid = criar(api, ana, "1")
    r = status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-08").json()
    # A resposta foi confirmada, mas a entrega não: o prazo do recebimento conta da resposta (30 dias úteis)
    assert (r["status"], r["data_resposta"], r["data_recebimento"]) == ("PENDENTE_RECEBIMENTO", "2026-09-08", None)
    assert (r["dias_uteis_decorridos"], r["nivel_alerta"]) == (30, "CRITICO")
    evento_resposta = r["historico"][-1]["id"]
    assert anexar(api, ana, oid, "RESPOSTA", evento_resposta).status_code == 201  # evidência da resposta
    assert anexar(api, ana, oid, "RECEBIMENTO", evento_resposta).status_code == 400  # ainda não houve entrega

    criticos = api.get("/api/oficios", params={"alerta": "CRITICO"}, headers=ana).json()["itens"]
    assert [o["id"] for o in criticos] == [oid]

    assert status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-08").status_code == 400  # já confirmado
    assert status(api, ana, oid, "RECEBIDO").status_code == 400  # falta a data
    assert status(api, ana, oid, "RECEBIDO", data_recebimento="2026-09-01").status_code == 400  # antes da resposta
    assert status(api, ana, oid, "RECEBIDO", data_recebimento="2026-10-21").status_code == 400  # futuro
    assert status(api, bruno, oid, "RECEBIDO", data_recebimento="2026-10-14").status_code == 404  # outro cliente

    r = status(api, ana, oid, "RECEBIDO", data_recebimento="2026-10-14", observacao="Entregue no almoxarifado")
    corpo = r.json()
    assert (corpo["status"], corpo["data_recebimento"], corpo["nivel_alerta"]) == ("RECEBIDO", "2026-10-14", None)
    recebimento = corpo["historico"][-1]
    assert (recebimento["status_anterior"], recebimento["data_recebimento"]) == ("PENDENTE_RECEBIMENTO", "2026-10-14")

    # Evidência da entrega fica no evento de recebimento; a de resposta não cabe nele
    assert anexar(api, ana, oid, "RECEBIMENTO", recebimento["id"]).status_code == 201
    assert anexar(api, ana, oid, "RESPOSTA", recebimento["id"]).status_code == 400
    detalhe = api.get(f"/api/oficios/{oid}", headers=ana).json()
    assert sorted(a["tipo"] for a in detalhe["anexos"]) == ["RECEBIMENTO", "RESPOSTA"]
    assert detalhe["historico"][-1]["evidencia"]["tipo"] == "RECEBIMENTO"

    # RECEBIDO é final
    assert status(api, ana, oid, "PENDENTE_RESPOSTA").status_code == 400

    atividade = api.get("/api/auditoria", params={"oficio_id": oid, "acao": "STATUS_ALTERADO"}, headers=ana).json()["itens"][0]
    assert atividade["descricao"] == "Confirmou o recebimento do ofício nº 1"
    assert atividade["detalhes"]["data_recebimento"] == "2026-10-14"


def test_nao_confirmado_e_reabertura_valem_para_itens(api, ana):
    oid = criar(api, ana, "1", tipo="PECAS_MANUTENCAO")
    assert status(api, ana, oid, "NAO_CONFIRMADO", data_resposta="2026-08-10").json()["status"] == "NAO_CONFIRMADO"
    assert status(api, ana, oid, "RECEBIDO", data_recebimento="2026-10-01").status_code == 400
    assert status(api, ana, oid, "PENDENTE_RESPOSTA").status_code == 200
    assert status(api, ana, oid, "CONFIRMADO", data_resposta="2026-10-20").json()["status"] == "PENDENTE_RECEBIMENTO"


def test_tipos_sem_recebimento_encerram_ao_confirmar(api, ana):
    oid = criar(api, ana, "1", tipo="COMUNICADOS")
    assert status(api, ana, oid, "PENDENTE_RECEBIMENTO", data_resposta="2026-08-10").status_code == 400
    assert status(api, ana, oid, "CONFIRMADO", data_resposta="2026-08-10").json()["status"] == "CONFIRMADO"
    assert status(api, ana, oid, "RECEBIDO", data_recebimento="2026-08-11").status_code == 400


def test_trocar_tipo_entra_e_sai_da_etapa_de_recebimento(api, ana, estado):
    oid = criar(api, ana, "1", tipo="COMUNICADOS")
    status(api, ana, oid, "CONFIRMADO", data_resposta="2026-08-10")

    r = api.patch(f"/api/oficios/{oid}", json={"tipo": "MOBILIARIOS"}, headers=ana).json()
    assert r["status"] == "PENDENTE_RECEBIMENTO"
    assert (r["historico"][-1]["status_anterior"], r["historico"][-1]["status_novo"]) == (
        "CONFIRMADO", "PENDENTE_RECEBIMENTO")
    status(api, ana, oid, "RECEBIDO", data_recebimento="2026-08-20")

    r = api.patch(f"/api/oficios/{oid}", json={"tipo": "COMUNICADOS"}, headers=ana).json()
    assert (r["status"], r["data_recebimento"]) == ("CONFIRMADO", None)
    assert [h["status_novo"] for h in r["historico"]] == [
        "PENDENTE_RESPOSTA", "CONFIRMADO", "PENDENTE_RECEBIMENTO", "RECEBIDO", "CONFIRMADO"]
    edicao = api.get("/api/auditoria", params={"oficio_id": oid, "acao": "OFICIO_EDITADO"}, headers=ana).json()["itens"][0]
    assert edicao["detalhes"]["status"] == {"de": "RECEBIDO", "para": "CONFIRMADO"}

    # Pendente de resposta: trocar o tipo não mexe no status
    outro = criar(api, ana, "2", tipo="COMUNICADOS")
    r = api.patch(f"/api/oficios/{outro}", json={"tipo": "EPIS"}, headers=ana).json()
    assert (r["status"], len(r["historico"])) == ("PENDENTE_RESPOSTA", 1)


def test_painel_conta_a_etapa_de_recebimento(api, admin, ana):
    recebido = criar(api, ana, "1", data="2026-08-03")
    status(api, ana, recebido, "CONFIRMADO", data_resposta="2026-08-10")  # 5 dias úteis
    status(api, ana, recebido, "RECEBIDO", data_recebimento="2026-08-24")  # 10 dias úteis após a resposta
    aguardando = criar(api, ana, "2", data="2026-09-01")
    status(api, ana, aguardando, "CONFIRMADO", data_resposta="2026-09-29")  # 15 dias úteis desde a resposta
    servico = criar(api, ana, "3", tipo="COMUNICADOS", data="2026-10-01")
    status(api, ana, servico, "CONFIRMADO", data_resposta="2026-10-06")

    a = api.get("/api/dashboard/analise", headers=admin).json()
    i = a["indicadores"]
    assert (i["pendentes"], i["pendentes_recebimento"], i["confirmados"], i["recebidos"]) == (0, 1, 1, 1)
    assert (i["recebimento_atencao"], i["recebimento_critico"]) == (1, 0)
    assert i["taxa_confirmacao"] == 1.0
    assert i["tempo_medio_entrega"] == 10.0
    assert (i["concluidos"], i["entregues_no_prazo"]) == (2, 1.0)  # recebido + comunicado confirmado
    epis = next(g for g in a["por_tipo"] if g["chave"] == "EPIS")
    assert (epis["pendentes_recebimento"], epis["recebidos"], epis["atencao"]) == (1, 1, 1)
    meses = {m["mes"]: m for m in a["por_mes"]}
    assert meses["2026-08"]["recebidos"] == 1

    resumo = api.get("/api/dashboard/resumo", headers=admin).json()
    assert (resumo["pendentes"], resumo["pendentes_atencao"], resumo["pendentes_recebimento"],
            resumo["recebidos"]) == (0, 0, 1, 1)

    filtrado = api.get("/api/oficios", params={"status": "PENDENTE_RECEBIMENTO"}, headers=admin).json()
    assert [o["numero"] for o in filtrado["itens"]] == ["2"]

    r = api.get("/api/dashboard/exportar", params={"formato": "xlsx"}, headers=admin)
    assert r.status_code == 200
    r = api.get("/api/dashboard/exportar", params={"formato": "pdf"}, headers=admin)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_alerta_do_recebimento_avanca_com_o_tempo(api, ana, estado):
    oid = criar(api, ana, "1", data="2026-10-01")
    r = status(api, ana, oid, "CONFIRMADO", data_resposta="2026-10-20").json()
    assert (r["dias_uteis_decorridos"], r["nivel_alerta"]) == (0, "NORMAL")
    estado["hoje"] = date(2026, 11, 10)
    assert api.get(f"/api/oficios/{oid}", headers=ana).json()["nivel_alerta"] == "ATENCAO"


def test_servicos_e_outros_exigem_entrega_e_prazo_mostra_os_dois_tempos(api, ana):
    for numero, tipo in (("10", "SERVICOS"), ("11", "OUTROS")):
        oid = criar(api, ana, numero, tipo=tipo)
        r = status(api, ana, oid, "CONFIRMADO", data_resposta="2026-08-10").json()  # 5 dias úteis após 03/08
        assert (r["status"], r["dias_resposta"], r["dias_entrega"]) == ("PENDENTE_RECEBIMENTO", 5, None)
        r = status(api, ana, oid, "RECEBIDO", data_recebimento="2026-08-24").json()  # 10 dias úteis após a resposta
        assert (r["status"], r["dias_resposta"], r["dias_entrega"]) == ("RECEBIDO", 5, 10)
    comunicado = criar(api, ana, "12", tipo="COMUNICADOS")
    r = status(api, ana, comunicado, "CONFIRMADO", data_resposta="2026-08-10").json()
    assert (r["status"], r["dias_resposta"], r["dias_entrega"]) == ("CONFIRMADO", 5, None)
    pendente = api.get(f"/api/oficios/{criar(api, ana, '13')}", headers=ana).json()
    assert (pendente["dias_resposta"], pendente["dias_entrega"]) == (None, None)
