"""Helpdesk das Manutenções Integradas: chamados, técnicos por empresa, prazo de 24 h corridas e relatório técnico.

Fixtures (conftest): paulo = operacional, marta = admin do módulo, tiago = técnico MSI,
carla = técnica REALIZA CLIMATIZAÇÃO. "Agora" = terça 20/10/2026 10:00. Prazos em horas corridas.
"""

from datetime import date, datetime

from app.services.manutencao import horas_entre, prazo_do_chamado

PDF = b"%PDF-1.4 relatorio externo do tecnico"


def empresas(api, quem):
    return {e["nome"]: e["id"] for e in api.get("/api/manutencao/empresas", headers=quem).json()}


def abrir(api, quem, empresa="MSI", **extra):
    corpo = {"empresa_id": empresas(api, quem)[empresa], "titulo": "Monitor sem imagem",
             "descricao": "O monitor multiparamétrico do leito 4 não liga.", "local": "UTI adulto", **extra}
    return api.post("/api/manutencao/chamados", json=corpo, headers=quem)


def tipos(chamado):
    return [i["tipo"] for i in chamado["interacoes"]]


# ---------- prazo em horas corridas ----------


def test_prazo_em_horas_corridas_conta_noites_e_fins_de_semana():
    # sexta 15:00 + 24 h = sábado 15:00 (noite e fim de semana contam)
    assert prazo_do_chamado(datetime(2026, 10, 16, 15), 24) == datetime(2026, 10, 17, 15)
    assert prazo_do_chamado(datetime(2026, 10, 20, 22), 48) == datetime(2026, 10, 22, 22)
    assert horas_entre(datetime(2026, 10, 16, 15), datetime(2026, 10, 17, 21, 30)) == 30.5
    assert horas_entre(datetime(2026, 10, 17, 15), datetime(2026, 10, 16, 15)) == -24


# ---------- abertura e prazo ----------


def test_operacional_abre_chamado_com_prazo_de_24h_corridas(api, paulo):
    r = abrir(api, paulo, ocorrido_em="2026-10-20T07:30:00")
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["codigo"] == "CH-00001" and c["status"] == "ABERTO"
    assert c["empresa"]["nome"] == "MSI" and c["solicitante"]["nome"] == "Paulo"
    assert c["ocorrido_em"] == "2026-10-20T07:30:00" and c["aberto_em"] == "2026-10-20T10:00:00"
    # terça 10:00 + 24 h corridas → quarta 10:00
    assert c["prazo_em"] == "2026-10-21T10:00:00" and c["prazo_horas"] == 24
    assert c["prazo"]["situacao"] == "NO_PRAZO" and c["prazo"]["horas_restantes"] == 24
    assert tipos(c) == ["ABERTURA"]
    assert c["pode_cancelar"] and not c["pode_responder"] and not c["pode_assumir"]


def test_data_do_problema_nao_pode_ser_futura(api, paulo):
    assert abrir(api, paulo, ocorrido_em="2026-10-21T10:00:00").status_code == 422


def test_tecnico_nao_abre_chamado(api, tiago):
    assert abrir(api, tiago).status_code == 403


def test_prazo_vencendo_e_atrasado(api, estado, paulo):
    oid = abrir(api, paulo).json()["id"]
    estado["agora"] = datetime(2026, 10, 21, 7)  # faltam 3 h (alerta: 4 h); a noite conta
    c = api.get(f"/api/manutencao/chamados/{oid}", headers=paulo).json()
    assert c["prazo"]["situacao"] == "VENCENDO" and c["prazo"]["horas_restantes"] == 3
    estado["agora"] = datetime(2026, 10, 21, 15)  # passou do prazo (quarta 10:00)
    c = api.get(f"/api/manutencao/chamados/{oid}", headers=paulo).json()
    assert c["prazo"]["situacao"] == "ATRASADO" and c["prazo"]["horas_restantes"] == -5
    lista = api.get("/api/manutencao/chamados", params={"situacao": "ATRASADO"}, headers=paulo).json()
    assert [x["id"] for x in lista["itens"]] == [oid]


# ---------- visibilidade ----------


def test_tecnico_ve_so_os_chamados_da_sua_empresa(api, paulo, tiago, carla):
    msi = abrir(api, paulo, "MSI").json()["id"]
    clima = abrir(api, paulo, "REALIZA CLIMATIZAÇÃO", titulo="Ar-condicionado do CC pingando").json()["id"]
    assert [c["id"] for c in api.get("/api/manutencao/chamados", headers=tiago).json()["itens"]] == [msi]
    assert [c["id"] for c in api.get("/api/manutencao/chamados", headers=carla).json()["itens"]] == [clima]
    assert api.get(f"/api/manutencao/chamados/{clima}", headers=tiago).status_code == 404
    assert api.post(f"/api/manutencao/chamados/{clima}/assumir", headers=tiago).status_code == 404


def test_todo_o_operacional_ve_todos_os_chamados(api, marta, paulo):
    criado = api.post("/api/usuarios", json={"nome": "Olga", "login": "olga", "senha": "12345678",
                                             "modulos": [{"modulo": "MANUTENCAO", "perfil": "CLIENTE"}]}, headers=marta)
    assert criado.status_code == 201
    olga = {"Authorization": "Bearer " + api.post(
        "/api/auth/login", data={"username": "olga", "password": "12345678"}).json()["access_token"]}
    oid = abrir(api, paulo).json()["id"]
    assert api.get("/api/manutencao/chamados", headers=olga).json()["total"] == 1
    assert api.get(f"/api/manutencao/chamados/{oid}", headers=olga).status_code == 200
    assert api.get("/api/manutencao/chamados", params={"meus": True}, headers=olga).json()["total"] == 0


def test_planner_sem_acesso_ao_helpdesk(api, ana, admin):
    assert api.get("/api/manutencao/chamados", headers=ana).status_code == 403
    assert api.get("/api/manutencao/painel", headers=admin).status_code == 403


# ---------- atendimento ----------


def test_tecnico_assume_e_responde_com_arquivo_externo(api, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    r = api.post(f"/api/manutencao/chamados/{oid}/assumir", headers=tiago).json()
    assert r["status"] == "EM_ATENDIMENTO" and r["tecnico"]["nome"] == "Tiago"
    assert r["prazo"]["situacao"] == "NO_PRAZO"  # assumir não é diagnóstico

    r = api.post(f"/api/manutencao/chamados/{oid}/interacoes", data={"texto": "Fonte queimada.", "diagnostico": "true"},
                 files={"arquivo": ("laudo-msi.pdf", PDF, "application/pdf")}, headers=tiago)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["diagnosticado_em"] == "2026-10-20T10:00:00"
    assert c["prazo"]["situacao"] == "CUMPRIDO" and c["prazo"]["horas_ate_diagnostico"] == 0
    resposta = c["interacoes"][-1]
    assert resposta["tipo"] == "DIAGNOSTICO" and resposta["arquivo_nome"] == "laudo-msi.pdf"
    assert resposta["autor_papel"] == "TECNICO"

    baixado = api.get(f"/api/manutencao/interacoes/{resposta['id']}/arquivo", headers=paulo)
    assert baixado.status_code == 200 and baixado.content == PDF


def test_operacional_comenta_mas_nao_diagnostica(api, paulo):
    oid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{oid}/interacoes"
    assert api.post(url, data={"texto": "Já reiniciei", "diagnostico": "true"}, headers=paulo).status_code == 403
    r = api.post(url, data={"texto": "Foto do painel"}, files={"arquivo": ("foto.png", b"\x89PNG..", "image/png")},
                 headers=paulo)
    assert r.status_code == 201
    c = r.json()
    assert c["status"] == "ABERTO" and c["diagnosticado_em"] is None and tipos(c) == ["ABERTURA", "COMENTARIO"]
    assert api.post(url, data={}, headers=paulo).status_code == 422  # sem texto nem arquivo


def test_comentario_do_tecnico_inicia_atendimento_sem_encerrar_o_prazo(api, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    c = api.post(f"/api/manutencao/chamados/{oid}/interacoes", data={"texto": "A caminho"}, headers=tiago).json()
    assert c["status"] == "EM_ATENDIMENTO" and c["tecnico"]["nome"] == "Tiago" and c["diagnosticado_em"] is None


def test_relatorio_tecnico_no_modelo_do_sistema_gera_pdf(api, estado, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    estado["agora"] = datetime(2026, 10, 21, 9, 30)  # registrado na quarta 09:30; atendido às 09:00
    corpo = {"atendido_em": "2026-10-21T09:00:00", "equipamento": "Monitor Dixtal DX-2023", "identificacao": "PAT 4471",
             "diagnostico": "Fonte de alimentação em curto.", "causa": "Oscilação na rede elétrica <220V>",
             "servico_executado": "Troca da fonte.\nTeste de funcionamento ok.", "pecas": "Fonte 12V",
             "situacao_equipamento": "OPERANDO", "recomendacoes": "Instalar no-break."}
    r = api.post(f"/api/manutencao/chamados/{oid}/relatorios", json=corpo, headers=tiago)
    assert r.status_code == 201, r.text
    c = r.json()
    # o diagnóstico vale da hora do atendimento (ter 10:00 → qua 09:00 = 23 h), não da hora do registro
    assert c["prazo"]["situacao"] == "CUMPRIDO" and c["prazo"]["horas_ate_diagnostico"] == 23
    assert c["diagnosticado_em"] == "2026-10-21T09:00:00" and c["interacoes"][-1]["ocorrido_em"] == "2026-10-21T09:00:00"
    rel = c["interacoes"][-1]["relatorio"]
    assert rel["codigo"] == "RT-00001" and rel["tecnico"]["nome"] == "Tiago" and rel["empresa"]["nome"] == "MSI"

    pdf = api.get(f"/api/manutencao/relatorios/{rel['id']}/pdf", headers=paulo)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert "RT-00001" in pdf.headers["content-disposition"]
    assert api.get(f"/api/manutencao/relatorios/{rel['id']}", headers=paulo).json()["pecas"] == "Fonte 12V"


def test_relatorio_e_so_do_tecnico_ou_admin(api, paulo, carla):
    oid = abrir(api, paulo).json()["id"]
    corpo = {"diagnostico": "Teste de permissão"}
    assert api.post(f"/api/manutencao/chamados/{oid}/relatorios", json=corpo, headers=paulo).status_code == 403
    assert api.post(f"/api/manutencao/chamados/{oid}/relatorios", json=corpo, headers=carla).status_code == 404


def test_diagnostico_depois_do_prazo_fica_com_atraso(api, estado, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    estado["agora"] = datetime(2026, 10, 23, 9)
    c = api.post(f"/api/manutencao/chamados/{oid}/interacoes", data={"texto": "Placa danificada", "diagnostico": "true"},
                 headers=tiago).json()
    # terça 10:00 → sexta 09:00: 71 h corridas (prazo de 24)
    assert c["prazo"]["situacao"] == "CUMPRIDO_COM_ATRASO" and c["prazo"]["horas_ate_diagnostico"] == 71


def test_concluir_reabrir_e_cancelar(api, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{oid}"
    assert api.post(f"{url}/concluir", json={}, headers=tiago).status_code == 409  # sem diagnóstico
    api.post(f"{url}/interacoes", data={"texto": "Cabo solto", "diagnostico": "true"}, headers=tiago)
    assert api.post(f"{url}/concluir", json={}, headers=paulo).status_code == 403  # operacional não conclui
    c = api.post(f"{url}/concluir", json={"texto": "Cabo reconectado"}, headers=tiago).json()
    assert c["status"] == "CONCLUIDO" and c["pode_reabrir"] is False  # técnico não reabre
    assert api.post(f"{url}/interacoes", data={"texto": "x", "diagnostico": "true"}, headers=tiago).status_code == 409

    assert api.post(f"{url}/reabrir", json={"motivo": "Quero reabrir"}, headers=tiago).status_code == 403
    c = api.post(f"{url}/reabrir", json={"motivo": "Voltou a falhar"}, headers=paulo).json()
    assert c["status"] == "EM_ATENDIMENTO" and c["concluido_em"] is None
    assert c["prazo"]["situacao"] == "CUMPRIDO"  # o diagnóstico já tinha sido feito
    assert tipos(c) == ["ABERTURA", "DIAGNOSTICO", "CONCLUSAO", "REABERTURA"]

    assert api.post(f"{url}/cancelar", json={"motivo": "Não precisa"}, headers=tiago).status_code == 403
    c = api.post(f"{url}/cancelar", json={"motivo": "Equipamento substituído"}, headers=paulo).json()
    assert c["status"] == "CANCELADO" and not c["pode_comentar"]
    assert api.post(f"{url}/interacoes", data={"texto": "oi"}, headers=paulo).status_code == 409


def test_data_e_hora_do_diagnostico_informadas_e_corrigidas(api, estado, paulo, tiago, carla, marta):
    oid = abrir(api, paulo).json()["id"]  # ter 20/10 10:00; prazo até qua 21/10 10:00
    url = f"/api/manutencao/chamados/{oid}"
    assert api.patch(f"{url}/diagnostico", json={"diagnosticado_em": "2026-10-20T11:00"},
                     headers=tiago).status_code == 409  # ainda sem diagnóstico
    estado["agora"] = datetime(2026, 10, 22, 15)  # o laudo externo só é anexado na quinta
    base = {"texto": "Laudo da MSI em anexo", "diagnostico": "true"}
    assert api.post(f"{url}/interacoes", data={**base, "diagnosticado_em": "2026-10-20T09:00"},
                    headers=tiago).status_code == 422  # antes da abertura
    assert api.post(f"{url}/interacoes", data={**base, "diagnosticado_em": "2026-10-23T09:00"},
                    headers=tiago).status_code == 422  # no futuro

    r = api.post(f"{url}/interacoes", data={**base, "diagnosticado_em": "2026-10-21T08:30"},
                 files={"arquivo": ("laudo-msi.pdf", PDF)}, headers=tiago)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["diagnosticado_em"] == "2026-10-21T08:30:00" and c["prazo"]["situacao"] == "CUMPRIDO"
    assert c["prazo"]["horas_ate_diagnostico"] == 22.5 and c["pode_corrigir_diagnostico"]
    diag = c["interacoes"][-1]
    assert (diag["ocorrido_em"], diag["criado_em"]) == ("2026-10-21T08:30:00", "2026-10-22T15:00:00")

    # Correção: o técnico da empresa ou o administrador; o operacional não
    corpo = {"diagnosticado_em": "2026-10-21T11:00", "motivo": "Horário do laudo"}
    assert api.patch(f"{url}/diagnostico", json=corpo, headers=paulo).status_code == 403
    assert api.patch(f"{url}/diagnostico", json=corpo, headers=carla).status_code == 404
    c = api.patch(f"{url}/diagnostico", json=corpo, headers=tiago).json()
    assert c["diagnosticado_em"] == "2026-10-21T11:00:00" and c["prazo"]["situacao"] == "CUMPRIDO_COM_ATRASO"
    correcao = c["interacoes"][-1]
    assert correcao["tipo"] == "CORRECAO" and correcao["autor"]["nome"] == "Tiago"
    assert "de 21/10/2026 08:30 para 21/10/2026 11:00" in correcao["texto"] and "Motivo: Horário do laudo" in correcao["texto"]
    assert next(i for i in c["interacoes"] if i["tipo"] == "DIAGNOSTICO")["ocorrido_em"] == "2026-10-21T11:00:00"
    assert api.patch(f"{url}/diagnostico", json=corpo, headers=tiago).status_code == 409  # mesma data

    # Concluído: corrigir a data refaz o tempo de solução, que não pode passar da conclusão
    api.post(f"{url}/concluir", json={}, headers=tiago)  # qui 22/10 15:00 → 28 h depois do diagnóstico
    estado["agora"] = datetime(2026, 10, 23, 9)
    c = api.patch(f"{url}/diagnostico", json={"diagnosticado_em": "2026-10-21T15:00"}, headers=marta).json()
    assert c["solucao_horas_corridas"] == 24
    assert api.patch(f"{url}/diagnostico", json={"diagnosticado_em": "2026-10-22T16:00"},
                     headers=marta).status_code == 422  # depois da conclusão


def test_corrigir_a_data_de_um_relatorio_atualiza_o_relatorio(api, estado, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{oid}"
    estado["agora"] = datetime(2026, 10, 21, 9, 30)
    assert api.post(f"{url}/relatorios", json={"diagnostico": "Fonte em curto", "atendido_em": "2026-10-20T08:00:00"},
                    headers=tiago).status_code == 422  # antes da abertura
    c = api.post(f"{url}/relatorios", json={"diagnostico": "Fonte em curto", "atendido_em": "2026-10-21T09:00:00"},
                 headers=tiago).json()
    rel = c["interacoes"][-1]["relatorio"]
    c = api.patch(f"{url}/diagnostico", json={"diagnosticado_em": "2026-10-20T16:45"}, headers=tiago).json()
    assert c["prazo"]["horas_ate_diagnostico"] == 6.75
    assert api.get(f"/api/manutencao/relatorios/{rel['id']}", headers=paulo).json()["atendido_em"] == "2026-10-20T16:45:00"


def test_secao_diagnostico_editar_resumo_e_substituir_o_relatorio_externo(api, estado, paulo, tiago, carla):
    oid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{oid}"
    estado["agora"] = datetime(2026, 10, 21, 9)
    c = api.post(f"{url}/interacoes", data={"diagnostico": "true", "diagnosticado_em": "2026-10-20T16:00"},
                 files={"arquivo": ("laudo-v1.pdf", PDF)}, headers=tiago).json()
    diag = c["diagnostico_interacao_id"]
    assert diag == c["interacoes"][-1]["id"] and c["interacoes"][-1]["texto"] is None  # só o arquivo externo

    # Resumo e data editados juntos; o operacional e a técnica de outra empresa não editam
    corpo = {"texto": "Válvula travada, conforme laudo.", "ocorrido_em": "2026-10-20T15:30", "motivo": "Revisão"}
    assert api.patch(f"/api/manutencao/interacoes/{diag}", json=corpo, headers=paulo).status_code == 403
    assert api.patch(f"/api/manutencao/interacoes/{diag}", json=corpo, headers=carla).status_code == 404
    c = api.patch(f"/api/manutencao/interacoes/{diag}", json=corpo, headers=tiago).json()
    assert c["diagnosticado_em"] == "2026-10-20T15:30:00" and c["prazo"]["horas_ate_diagnostico"] == 5.5
    original = next(i for i in c["interacoes"] if i["id"] == diag)
    assert (original["texto"], original["ocorrido_em"]) == ("Válvula travada, conforme laudo.", "2026-10-20T15:30:00")
    edicao = c["interacoes"][-1]
    assert edicao["tipo"] == "CORRECAO" and edicao["texto"].startswith("Diagnóstico editado: data e hora de 20/10/2026 16:00")
    assert "resumo do diagnóstico" in edicao["texto"] and "Motivo: Revisão" in edicao["texto"]
    assert api.patch(f"/api/manutencao/interacoes/{diag}", json=corpo, headers=tiago).status_code == 409  # nada mudou

    # Substituir o relatório externo: o novo fica no diagnóstico, o anterior fica guardado na correção
    url_arq = f"/api/manutencao/interacoes/{diag}/arquivo"
    c = api.put(url_arq, files={"arquivo": ("laudo-v2.pdf", b"%PDF-1.4 v2")}, headers=tiago).json()
    assert next(i for i in c["interacoes"] if i["id"] == diag)["arquivo_nome"] == "laudo-v2.pdf"
    guardado = c["interacoes"][-1]
    assert guardado["tipo"] == "CORRECAO" and guardado["arquivo_nome"] == "laudo-v1.pdf"
    assert api.get(f"/api/manutencao/interacoes/{guardado['id']}/arquivo", headers=paulo).content == PDF
    assert api.get(f"/api/manutencao/interacoes/{diag}/arquivo", headers=paulo).content == b"%PDF-1.4 v2"

    # Complemento: relatório no modelo do sistema, que não pode ser anterior ao diagnóstico
    rel = {"diagnostico": "Troca da válvula feita", "atendido_em": "2026-10-20T14:00:00"}
    assert api.post(f"{url}/relatorios", json=rel, headers=tiago).status_code == 422
    c = api.post(f"{url}/relatorios", json={**rel, "atendido_em": "2026-10-21T08:00:00"}, headers=tiago).json()
    assert c["diagnosticado_em"] == "2026-10-20T15:30:00" and c["diagnostico_interacao_id"] == diag  # não muda
    complemento = c["interacoes"][-1]
    rid = complemento["relatorio"]["id"]
    # O relatório também recebe o arquivo externo (interligado) e é editado pelos campos dele
    api.put(f"/api/manutencao/interacoes/{complemento['id']}/arquivo", files={"arquivo": ("os-123.pdf", PDF)}, headers=tiago)
    assert api.patch(f"/api/manutencao/interacoes/{complemento['id']}", json={"texto": "x"}, headers=tiago).status_code == 422
    c = api.patch(f"/api/manutencao/relatorios/{rid}", json={"causa": "Desgaste", "situacao_equipamento": "OPERANDO"},
                  headers=tiago).json()
    assert c["interacoes"][-1]["texto"].startswith(f"Relatório técnico {complemento['relatorio']['codigo']} editado: causa provável")
    r = api.get(f"/api/manutencao/relatorios/{rid}", headers=paulo).json()
    assert (r["causa"], r["situacao_equipamento"]) == ("Desgaste", "OPERANDO")
    assert next(i for i in c["interacoes"] if i["id"] == complemento["id"])["arquivo_nome"] == "os-123.pdf"


# ---------- empresas ----------


def test_admin_cadastra_empresas_e_o_prazo_vale_para_os_novos(api, marta, paulo):
    assert api.post("/api/manutencao/empresas", json={"nome": "Nova"}, headers=paulo).status_code == 403
    assert api.post("/api/manutencao/empresas", json={"nome": "msi"}, headers=marta).status_code == 409
    nova = api.post("/api/manutencao/empresas", json={"nome": "Elétrica Sul", "prazo_horas": 8}, headers=marta)
    assert nova.status_code == 201
    eid = nova.json()["id"]

    c = abrir(api, paulo, "Elétrica Sul").json()
    assert c["prazo_horas"] == 8 and c["prazo_em"] == "2026-10-20T18:00:00"
    api.patch(f"/api/manutencao/empresas/{eid}", json={"prazo_horas": 48}, headers=marta)
    assert api.get(f"/api/manutencao/chamados/{c['id']}", headers=paulo).json()["prazo_horas"] == 8  # mantém

    assert api.delete(f"/api/manutencao/empresas/{eid}", headers=marta).status_code == 409  # tem chamado
    api.patch(f"/api/manutencao/empresas/{eid}", json={"ativo": False}, headers=marta)
    assert abrir(api, paulo, "Elétrica Sul").status_code == 400  # inativa
    assert "Elétrica Sul" not in {e["nome"] for e in
                                  api.get("/api/manutencao/empresas", params={"ativas": True}, headers=paulo).json()}


def test_empresas_iniciais(api, paulo):
    lista = api.get("/api/manutencao/empresas", headers=paulo).json()
    assert {e["nome"]: (e["prazo_horas"], e["tecnicos"]) for e in lista} == {
        "MSI": (24, 1), "REALIZA PREDIAL": (24, 0), "REALIZA CLIMATIZAÇÃO": (24, 1)}


# ---------- cadastro de técnicos ----------


def test_admin_do_modulo_cadastra_tecnico_com_empresa(api, marta, admin):
    ids = empresas(api, marta)
    tecnico = {"modulo": "MANUTENCAO", "perfil": "TECNICO", "empresa_id": ids["REALIZA PREDIAL"]}
    base = {"nome": "Rui", "login": "rui", "senha": "12345678"}
    assert api.post("/api/usuarios", json={**base, "modulos": [{**tecnico, "empresa_id": None}]},
                    headers=marta).status_code == 422
    assert api.post("/api/usuarios", json={**base, "modulos": [{**tecnico, "modulo": "OFICIOS"}]},
                    headers=marta).status_code == 422
    assert api.post("/api/usuarios", json={**base, "modulos": [tecnico]}, headers=admin).status_code == 403
    r = api.post("/api/usuarios", json={**base, "modulos": [tecnico]}, headers=marta)
    assert r.status_code == 201
    assert r.json()["modulos"] == [{"modulo": "MANUTENCAO", "perfil": "TECNICO", "empresa_id": ids["REALIZA PREDIAL"],
                                    "empresa_nome": "REALIZA PREDIAL"}]
    rui = {"Authorization": "Bearer " + api.post(
        "/api/auth/login", data={"username": "rui", "password": "12345678"}).json()["access_token"]}
    resumo = api.get("/api/manutencao/resumo", headers=rui).json()
    assert resumo["eh_tecnico"] and resumo["empresa"]["nome"] == "REALIZA PREDIAL"
    ultima = api.get("/api/usuarios", headers=marta).json()
    assert any(u["login"] == "rui" for u in ultima)


# ---------- painel ----------


def test_painel_por_empresa(api, estado, paulo, tiago, marta):
    abrir(api, paulo, "MSI")
    segundo = abrir(api, paulo, "MSI").json()["id"]
    abrir(api, paulo, "REALIZA PREDIAL")
    api.post(f"/api/manutencao/chamados/{segundo}/interacoes", data={"texto": "ok", "diagnostico": "true"}, headers=tiago)
    estado["agora"] = datetime(2026, 10, 23, 9)  # os sem diagnóstico atrasaram

    p = api.get("/api/manutencao/painel", headers=marta).json()
    assert (p["abertos"], p["em_atendimento"], p["aguardando_diagnostico"], p["atrasados"]) == (2, 1, 2, 2)
    msi = next(e for e in p["por_empresa"] if e["empresa"]["nome"] == "MSI")
    assert (msi["abertos"], msi["atrasados"], msi["diagnosticados"], msi["no_prazo_pct"]) == (2, 1, 1, 100.0)
    assert len(p["urgentes"]) == 2

    do_tiago = api.get("/api/manutencao/painel", headers=tiago).json()
    assert do_tiago["empresa_do_tecnico"]["nome"] == "MSI" and do_tiago["aguardando_diagnostico"] == 1


# ---------- tempo de solução ----------


def test_tempo_de_solucao_apos_o_diagnostico_fica_registrado(api, estado, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{oid}"
    api.post(f"{url}/interacoes", data={"texto": "Fonte queimada", "diagnostico": "true"}, headers=tiago)  # ter 10:00
    estado["agora"] = datetime(2026, 10, 21, 11, 30)  # qua 11:30
    c = api.get(url, headers=tiago).json()
    assert c["execucao_horas"] == 25.5 and c["solucao_horas_corridas"] is None  # em execução há 25,5 h

    c = api.post(f"{url}/concluir", json={"texto": "Fonte trocada"}, headers=tiago).json()
    # ter 10:00 → qua 11:30: 25,5 h corridas
    assert (c["solucao_horas_corridas"], c["execucao_horas"]) == (25.5, None)
    conclusao = c["interacoes"][-1]["texto"]
    assert conclusao.startswith("Fonte trocada") and "Tempo de solução após o diagnóstico: 25 h 30 min." in conclusao

    estado["agora"] = datetime(2026, 10, 22, 9)
    c = api.post(f"{url}/reabrir", json={"motivo": "Voltou a desligar"}, headers=paulo).json()
    assert c["solucao_horas_corridas"] is None  # reaberto: o tempo volta a contar
    estado["agora"] = datetime(2026, 10, 22, 10)
    c = api.post(f"{url}/concluir", json={}, headers=tiago).json()
    assert c["solucao_horas_corridas"] == 48  # do diagnóstico (ter 10:00) até a nova conclusão (qui 10:00)

    p = api.get("/api/manutencao/painel", headers=paulo).json()
    assert next(e for e in p["por_empresa"] if e["empresa"]["nome"] == "MSI")["media_horas_solucao"] == 48


# ---------- solicitação de peças e equipamentos (Planner de Ofícios) ----------


PECAS = {"tipo": "PECAS_MANUTENCAO", "numero": "45", "data_oficio": "2026-10-20", "destinatario_tipo": "SES",
         "destinatario_setor": "Almoxarifado central", "itens": "1 fonte 12V para monitor Dixtal"}


def test_tipos_de_solicitacao(api, paulo):
    assert [t["codigo"] for t in api.get("/api/manutencao/tipos-solicitacao", headers=paulo).json()] == [
        "SOLICITACAO_EQUIPAMENTOS", "PECAS_MANUTENCAO"]


def test_operacional_solicita_pecas_e_o_oficio_vai_para_o_planner(api, paulo, tiago, admin):
    chamado = abrir(api, paulo).json()
    url = f"/api/manutencao/chamados/{chamado['id']}/oficios"
    assert api.post(url, json=PECAS, headers=tiago).status_code == 403  # técnico não solicita
    assert api.post(url, json={**PECAS, "tipo": "COMUNICADOS"}, headers=paulo).status_code == 400
    assert api.post(url, json={**PECAS, "destinatario_setor": None}, headers=paulo).status_code == 422

    r = api.post(url, json=PECAS, headers=paulo)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["oficios_pendentes"] == 1 and c["interacoes"][-1]["tipo"] == "OFICIO"
    vinculado = c["oficios"][0]
    assert (vinculado["numero"], vinculado["status"], vinculado["tipo_nome"], vinculado["dono_nome"]) == (
        "45", "PENDENTE_RESPOSTA", "Peças para Manutenção/Engenharia Clínica", "Paulo")
    assert api.post(url, json=PECAS, headers=paulo).status_code == 409  # mesmo nº no mesmo ano

    # No Planner, o administrador vê o ofício com a origem no chamado
    oficio = api.get(f"/api/oficios/{vinculado['id']}", headers=admin).json()
    assert oficio["chamado"] == {"id": chamado["id"], "codigo": chamado["codigo"], "titulo": chamado["titulo"]}
    assert oficio["dono"]["nome"] == "Paulo" and "Itens: 1 fonte 12V" in oficio["observacao"]
    assert oficio["tipo"] == "PECAS_MANUTENCAO" and oficio["status"] == "PENDENTE_RESPOSTA"

    # O técnico acompanha a solicitação pelo chamado
    assert api.get(f"/api/manutencao/chamados/{chamado['id']}", headers=tiago).json()["oficios"][0]["numero"] == "45"


def test_quadro_do_tecnico_acompanha_cada_etapa(api, estado, paulo, tiago, carla, admin):
    def colunas(quem, **params):
        q = api.get("/api/manutencao/quadro", params=params, headers=quem).json()
        return {col["chave"]: [c["id"] for c in col["chamados"]] for col in q["colunas"]}, q

    a = abrir(api, paulo, titulo="Monitor A").json()["id"]
    b = abrir(api, paulo, titulo="Bomba de infusão B").json()["id"]
    c = abrir(api, paulo, titulo="Desfibrilador C").json()["id"]
    abrir(api, paulo, "REALIZA CLIMATIZAÇÃO", titulo="Ar do CC")  # de outra empresa
    for oid in (b, c):
        api.post(f"/api/manutencao/chamados/{oid}/interacoes", data={"texto": "Diagnóstico", "diagnostico": "true"},
                 headers=tiago)
    api.post(f"/api/manutencao/chamados/{c}/oficios", json=PECAS, headers=paulo)

    cols, q = colunas(tiago)
    assert cols == {"AGUARDANDO_DIAGNOSTICO": [a], "EM_EXECUCAO": [b], "AGUARDANDO_PECAS": [c], "CONCLUIDOS": []}
    assert q["empresa"]["nome"] == "MSI"
    assert (q["resumo"]["em_aberto"], q["resumo"]["aguardando_pecas"], q["resumo"]["aguardando_diagnostico"]) == (3, 1, 1)

    # As peças chegaram (o Planner registra a entrega): o chamado volta para "em execução"
    oficio = api.get(f"/api/manutencao/chamados/{c}", headers=paulo).json()["oficios"][0]["id"]
    api.patch(f"/api/oficios/{oficio}/status", json={"status": "CONFIRMADO", "data_resposta": "2026-10-20"}, headers=admin)
    api.patch(f"/api/oficios/{oficio}/status", json={"status": "RECEBIDO", "data_recebimento": "2026-10-20"}, headers=admin)
    estado["agora"] = datetime(2026, 10, 20, 15)
    api.post(f"/api/manutencao/chamados/{b}/concluir", json={}, headers=tiago)
    cols, q = colunas(tiago)
    assert cols["AGUARDANDO_PECAS"] == [] and cols["EM_EXECUCAO"] == [c] and cols["CONCLUIDOS"] == [b]
    assert q["resumo"]["media_horas_solucao"] == 5 and q["resumo"]["diagnostico_no_prazo_pct"] == 100

    # "Só os meus": os que o técnico assumiu/respondeu; a técnica de outra empresa não vê os da MSI
    assert colunas(tiago, meus=True)[0]["AGUARDANDO_DIAGNOSTICO"] == []
    assert sum(len(v) for v in colunas(carla)[0].values()) == 1

def test_documento_e_andamento_feitos_no_planner_aparecem_no_chamado(api, paulo, tiago, carla, admin):
    chamado = abrir(api, paulo).json()
    cid = chamado["id"]
    oid = api.post(f"/api/manutencao/chamados/{cid}/oficios", json=PECAS, headers=paulo).json()["oficios"][0]["id"]

    # O operacional também usa o Planner: abre o próprio ofício lá e anexa o documento
    assert api.get(f"/api/oficios/{oid}", headers=paulo).status_code == 200
    r = api.post(f"/api/oficios/{oid}/anexos/OFICIO", files={"arquivo": ("oficio-45.pdf", PDF)}, headers=paulo)
    assert r.status_code == 201, r.text

    c = api.get(f"/api/manutencao/chamados/{cid}", headers=tiago).json()
    anexo = c["oficios"][0]["anexos"][0]
    assert (anexo["tipo"], anexo["nome_original"]) == ("OFICIO", "oficio-45.pdf")
    ultimo = c["interacoes"][-1]
    assert ultimo["tipo"] == "OFICIO" and ultimo["texto"].startswith("Planner de Ofícios · Anexou")
    assert ultimo["autor"]["nome"] == "Paulo"
    # O técnico baixa o documento pelo chamado; a técnica de outra empresa não
    url_anexo = f"/api/manutencao/chamados/{cid}/oficios/anexos/{anexo['id']}"
    baixado = api.get(url_anexo, headers=tiago)
    assert baixado.status_code == 200 and baixado.content == PDF
    assert api.get(url_anexo, headers=carla).status_code == 404

    # Resposta e entrega registradas no Planner atualizam o chamado e o quadro
    def coluna_do_chamado():
        q = api.get("/api/manutencao/quadro", headers=tiago).json()
        return next(col["chave"] for col in q["colunas"] if any(x["id"] == cid for x in col["chamados"]))

    assert coluna_do_chamado() == "AGUARDANDO_PECAS"
    api.patch(f"/api/oficios/{oid}/status", json={"status": "CONFIRMADO", "data_resposta": "2026-10-20"}, headers=admin)
    c = api.get(f"/api/manutencao/chamados/{cid}", headers=paulo).json()
    assert c["oficios"][0]["status"] == "PENDENTE_RECEBIMENTO" and c["oficios_resumo"][0]["status"] == "PENDENTE_RECEBIMENTO"
    assert c["interacoes"][-1]["texto"].startswith("Planner de Ofícios ·") and c["interacoes"][-1]["autor"]["nome"] == "Admin"
    assert coluna_do_chamado() == "AGUARDANDO_PECAS"  # respondido, mas ainda não entregue
    api.patch(f"/api/oficios/{oid}/status", json={"status": "RECEBIDO", "data_recebimento": "2026-10-20"}, headers=admin)
    assert coluna_do_chamado() == "AGUARDANDO_DIAGNOSTICO"  # entregue: volta para a etapa em que estava

# ---------- ofícios que já existem no Planner: vincular ao chamado ----------


def oficio_no_planner(api, quem, numero="70", **extra):
    corpo = {"numero": numero, "data_oficio": "2026-10-15", "tipo": "PECAS_MANUTENCAO",
             "observacao": "Compra de fontes 12V", **extra}
    r = api.post("/api/oficios", json=corpo, headers=quem)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def disponiveis(api, quem, **params):
    return [o["id"] for o in api.get("/api/manutencao/oficios-disponiveis", params=params, headers=quem).json()]


def test_operacional_vincula_oficio_que_ja_existe_no_planner(api, paulo, tiago, ana, admin):
    oid = oficio_no_planner(api, paulo)
    alheio = oficio_no_planner(api, ana, numero="71")
    chamado = abrir(api, paulo).json()
    cid = chamado["id"]

    # A busca segue a visibilidade do Planner: o operacional (cliente lá) só encontra os próprios ofícios
    assert disponiveis(api, paulo) == [oid]
    assert disponiveis(api, paulo, busca="fontes") == [oid] and disponiveis(api, paulo, busca="tomógrafo") == []
    assert api.get("/api/manutencao/oficios-disponiveis", headers=tiago).status_code == 403

    url = f"/api/manutencao/chamados/{cid}/oficios"
    assert api.put(f"{url}/{oid}", headers=tiago).status_code == 403  # técnico não vincula
    assert api.put(f"{url}/{alheio}", headers=paulo).status_code == 404  # ofício de outro cliente
    r = api.put(f"{url}/{oid}", headers=paulo)
    assert r.status_code == 200, r.text
    c = r.json()
    vinculado = c["oficios"][0]
    assert (vinculado["id"], vinculado["numero"], vinculado["status"], vinculado["pode_desvincular"]) == (
        oid, "70", "PENDENTE_RESPOSTA", True)
    assert c["oficios_pendentes"] == 1
    ultimo = c["interacoes"][-1]
    assert ultimo["tipo"] == "OFICIO" and "já cadastrado no Planner de Ofícios" in ultimo["texto"]
    assert tipos(c).count("OFICIO") == 1  # o vínculo não é espelhado duas vezes na linha do tempo

    # Um ofício fica em um chamado só, e some da lista dos disponíveis
    assert api.put(f"{url}/{oid}", headers=paulo).status_code == 409
    outro = abrir(api, paulo, titulo="Bomba de infusão").json()
    r = api.put(f"/api/manutencao/chamados/{outro['id']}/oficios/{oid}", headers=paulo)
    assert r.status_code == 409 and chamado["codigo"] in r.json()["detail"]
    assert disponiveis(api, paulo) == []

    # No Planner o ofício mostra o chamado, e a atividade fica registrada
    assert api.get(f"/api/oficios/{oid}", headers=paulo).json()["chamado"]["id"] == cid
    atividade = api.get("/api/auditoria", params={"oficio_id": oid, "acao": "OFICIO_EDITADO"}, headers=admin).json()
    assert atividade["itens"][0]["descricao"].startswith("Vinculou o ofício nº 70 ao chamado")

    # Daí em diante vale a regra de sempre: o que é feito no Planner aparece no chamado
    api.post(f"/api/oficios/{oid}/anexos/OFICIO", files={"arquivo": ("oficio-70.pdf", PDF)}, headers=paulo)
    c = api.get(f"/api/manutencao/chamados/{cid}", headers=tiago).json()
    assert c["oficios"][0]["anexos"][0]["nome_original"] == "oficio-70.pdf"
    assert c["interacoes"][-1]["texto"].startswith("Planner de Ofícios · Anexou")
    assert c["oficios"][0]["pode_desvincular"] is False  # o técnico só acompanha


def test_desvincular_oficio_do_chamado(api, paulo, marta, ana, master):
    def coluna(cid):
        q = api.get("/api/manutencao/quadro", headers=paulo).json()
        return next(col["chave"] for col in q["colunas"] if any(x["id"] == cid for x in col["chamados"]))

    oid = oficio_no_planner(api, ana)
    cid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{cid}/oficios/{oid}"

    # Quem vê tudo no Planner (master ou administrador de lá) vincula o ofício de qualquer cliente
    assert disponiveis(api, master) == [oid]
    assert api.put(url, headers=master).status_code == 200
    assert coluna(cid) == "AGUARDANDO_PECAS"

    # O operacional acompanha, mas não desfaz o vínculo de um ofício que não é dele; a administradora desfaz
    assert api.get(f"/api/manutencao/chamados/{cid}", headers=paulo).json()["oficios"][0]["pode_desvincular"] is False
    assert api.delete(url, headers=paulo).status_code == 403
    r = api.delete(url, headers=marta)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["oficios"] == [] and c["oficios_pendentes"] == 0
    assert "desvinculado deste chamado" in c["interacoes"][-1]["texto"]
    assert coluna(cid) == "AGUARDANDO_DIAGNOSTICO"
    assert api.delete(url, headers=marta).status_code == 404

    # O ofício continua no Planner, sem o chamado, e volta a ficar disponível
    oficio = api.get(f"/api/oficios/{oid}", headers=ana).json()
    assert oficio["chamado"] is None and oficio["status"] == "PENDENTE_RESPOSTA"
    assert disponiveis(api, master) == [oid]

    # Chamado encerrado não recebe vínculo
    api.post(f"/api/manutencao/chamados/{cid}/cancelar", json={"motivo": "Aberto por engano"}, headers=paulo)
    assert api.put(url, headers=master).status_code == 409
