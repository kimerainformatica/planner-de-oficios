"""Correções do admin/master: resposta, recebimento, desfazer etapa e remover evidências."""

PDF = b"%PDF-1.4 evidencia"


def criar(api, quem, numero, tipo="COMUNICADOS", data="2026-09-01"):
    r = api.post("/api/oficios", json={"numero": numero, "data_oficio": data, "tipo": tipo}, headers=quem)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def status(api, quem, oid, novo, **datas):
    return api.patch(f"/api/oficios/{oid}/status", json={"status": novo, **datas}, headers=quem)


def anexar(api, quem, oid, tipo, evento):
    return api.post(f"/api/oficios/{oid}/anexos/{tipo}", params={"historico_id": evento},
                    files={"arquivo": ("e.pdf", PDF, "application/pdf")}, headers=quem)


def ativos(oficio):
    return [h for h in oficio["historico"] if h["anulado_em"] is None]


def test_so_admin_e_master_corrigem(api, admin, master, ana):
    oid = criar(api, ana, "1")
    status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-10")
    url = f"/api/oficios/{oid}"
    assert api.patch(f"{url}/resposta", json={"data_resposta": "2026-09-11"}, headers=ana).status_code == 403
    assert api.post(f"{url}/desfazer", json={"motivo": "Registro errado"}, headers=ana).status_code == 403
    assert api.patch(f"{url}/resposta", json={"data_resposta": "2026-09-11"}, headers=admin).status_code == 200
    assert api.patch(f"{url}/resposta", json={"data_resposta": "2026-09-12"}, headers=master).status_code == 200


def test_corrigir_data_e_observacao_da_resposta(api, admin, ana):
    oid = criar(api, ana, "1")
    status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-10", observacao="Respondido por e-mail")
    url = f"/api/oficios/{oid}/resposta"
    assert api.patch(url, json={"data_resposta": "2026-08-31"}, headers=admin).status_code == 400  # antes do ofício
    assert api.patch(url, json={"data_resposta": "2026-10-21"}, headers=admin).status_code == 400  # futuro

    r = api.patch(url, json={"data_resposta": "2026-09-15", "observacao": "Respondido pelo SEI"}, headers=admin).json()
    assert (r["status"], r["data_resposta"]) == ("CONFIRMADO", "2026-09-15")
    resposta = r["historico"][-1]
    assert (resposta["data_resposta"], resposta["observacao"], resposta["anulado_em"]) == (
        "2026-09-15", "Respondido pelo SEI", None)
    atividade = api.get("/api/auditoria", params={"oficio_id": oid, "acao": "RESPOSTA_CORRIGIDA"},
                        headers=admin).json()["itens"][0]
    assert atividade["detalhes"]["data_resposta"] == {"de": "2026-09-10", "para": "2026-09-15"}
    assert atividade["usuario_nome"] == "Admin"


def test_mudar_resultado_anula_a_resposta_e_leva_a_evidencia(api, admin, ana):
    oid = criar(api, ana, "1")
    r = status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-10").json()
    antigo = r["historico"][-1]["id"]
    assert anexar(api, ana, oid, "RESPOSTA", antigo).status_code == 201

    r = api.patch(f"/api/oficios/{oid}/resposta", json={"status": "NAO_CONFIRMADO"}, headers=admin).json()
    assert r["status"] == "NAO_CONFIRMADO"
    anulado = next(h for h in r["historico"] if h["id"] == antigo)
    assert (anulado["anulado_por_nome"], anulado["anulado_motivo"]) == ("Admin", "Resultado da resposta corrigido")
    nova = ativos(r)[-1]
    assert (nova["status_novo"], nova["data_resposta"]) == ("NAO_CONFIRMADO", "2026-09-10")
    assert nova["evidencia"]["nome_original"] == "e.pdf"  # a evidência acompanha a resposta corrigida
    assert anexar(api, ana, oid, "RESPOSTA", antigo).status_code == 400  # evento anulado não recebe evidência

    # Voltar para Confirmado num ofício de itens leva à etapa de recebimento
    api.patch(f"/api/oficios/{oid}", json={"tipo": "EPIS"}, headers=ana)
    r = api.patch(f"/api/oficios/{oid}/resposta", json={"status": "CONFIRMADO"}, headers=admin).json()
    assert r["status"] == "PENDENTE_RECEBIMENTO"


def test_recebimento_corrigir_e_desfazer(api, admin, ana):
    oid = criar(api, ana, "1", tipo="EPIS")
    status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-10")
    url = f"/api/oficios/{oid}"
    assert api.patch(f"{url}/recebimento", json={"data_recebimento": "2026-09-20"},
                     headers=admin).status_code == 400  # ainda não recebido
    r = status(api, ana, oid, "RECEBIDO", data_recebimento="2026-09-20").json()
    recebimento = r["historico"][-1]["id"]
    assert anexar(api, ana, oid, "RECEBIMENTO", recebimento).status_code == 201

    assert api.patch(f"{url}/recebimento", json={"data_recebimento": "2026-09-09"},
                     headers=admin).status_code == 400  # antes da resposta
    r = api.patch(f"{url}/recebimento", json={"data_recebimento": "2026-09-22", "observacao": "Conferido"},
                  headers=admin).json()
    assert (r["data_recebimento"], r["historico"][-1]["data_recebimento"], r["historico"][-1]["observacao"]) == (
        "2026-09-22", "2026-09-22", "Conferido")
    assert api.patch(f"{url}/resposta", json={"data_resposta": "2026-09-25"},
                     headers=admin).status_code == 400  # resposta depois da entrega
    assert api.patch(f"{url}/resposta", json={"status": "NAO_CONFIRMADO"},
                     headers=admin).status_code == 409  # desfazer o recebimento antes

    assert api.post(f"{url}/desfazer", json={"motivo": "x"}, headers=admin).status_code == 422  # motivo curto
    r = api.post(f"{url}/desfazer", json={"motivo": "Itens ainda não chegaram"}, headers=admin).json()
    assert (r["status"], r["data_recebimento"], r["data_resposta"]) == ("PENDENTE_RECEBIMENTO", None, "2026-09-10")
    desfeito = next(h for h in r["historico"] if h["id"] == recebimento)
    assert desfeito["anulado_motivo"] == "Itens ainda não chegaram"
    assert desfeito["evidencia"] is not None  # o comprovante continua visível no evento desfeito

    r = api.post(f"{url}/desfazer", json={"motivo": "Resposta lançada no ofício errado"}, headers=admin).json()
    assert (r["status"], r["data_resposta"], r["inicio_prazo"]) == ("PENDENTE_RESPOSTA", None, "2026-09-01")
    assert [h["status_novo"] for h in ativos(r)] == ["PENDENTE_RESPOSTA"]
    assert api.post(f"{url}/desfazer", json={"motivo": "De novo"}, headers=admin).status_code == 400

    # O fluxo normal continua depois da correção
    assert status(api, ana, oid, "CONFIRMADO", data_resposta="2026-10-01").json()["status"] == "PENDENTE_RECEBIMENTO"
    atividade = api.get("/api/auditoria", params={"oficio_id": oid, "acao": "ETAPA_DESFEITA"},
                        headers=admin).json()["itens"]
    assert [a["descricao"] for a in atividade] == ["Desfez a resposta do ofício nº 1",
                                                    "Desfez o recebimento do ofício nº 1"]


def test_desfazer_resposta_apos_troca_de_tipo_anula_o_ajuste(api, admin, ana):
    oid = criar(api, ana, "1")
    status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-10")
    api.patch(f"/api/oficios/{oid}", json={"tipo": "MOBILIARIOS"}, headers=ana)  # CONFIRMADO -> PENDENTE_RECEBIMENTO
    r = api.post(f"/api/oficios/{oid}/desfazer", json={"motivo": "Resposta registrada por engano"},
                 headers=admin).json()
    assert r["status"] == "PENDENTE_RESPOSTA"
    assert sum(h["anulado_em"] is not None for h in r["historico"]) == 2  # resposta + ajuste de etapa


def test_so_admin_remove_evidencia(api, admin, ana):
    oid = criar(api, ana, "1")
    r = status(api, ana, oid, "CONFIRMADO", data_resposta="2026-09-10").json()
    evidencia = anexar(api, ana, oid, "RESPOSTA", r["historico"][-1]["id"]).json()
    assert api.delete(f"/api/anexos/{evidencia['id']}", headers=ana).status_code == 403
    assert api.delete(f"/api/anexos/{evidencia['id']}", headers=admin).status_code == 204
