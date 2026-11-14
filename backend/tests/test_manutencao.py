"""Helpdesk da Manutenção Clínica: chamados, técnicos por empresa, prazo de 24 h úteis e relatório técnico.

Fixtures (conftest): paulo = operacional, marta = admin do módulo, tiago = técnico MSI,
carla = técnica REALIZA CLIMATIZAÇÃO. "Agora" = terça 20/10/2026 10:00; expediente 08:00–18:00.
"""

from datetime import date, datetime

from app.services.horas_uteis import Expediente
from app.services.prazos import CalendarioUtil

PDF = b"%PDF-1.4 relatorio externo do tecnico"


def empresas(api, quem):
    return {e["nome"]: e["id"] for e in api.get("/api/manutencao/empresas", headers=quem).json()}


def abrir(api, quem, empresa="MSI", **extra):
    corpo = {"empresa_id": empresas(api, quem)[empresa], "titulo": "Monitor sem imagem",
             "descricao": "O monitor multiparamétrico do leito 4 não liga.", "local": "UTI adulto", **extra}
    return api.post("/api/manutencao/chamados", json=corpo, headers=quem)


def tipos(chamado):
    return [i["tipo"] for i in chamado["interacoes"]]


# ---------- horas úteis ----------


def test_horas_uteis_pulam_noite_fim_de_semana_e_feriado():
    exp = Expediente(CalendarioUtil([date(2026, 10, 12)]), datetime(1, 1, 1, 8).time(), datetime(1, 1, 1, 18).time())
    # sexta 15:00 + 24 h úteis: 3 h na sexta, 10 na segunda, 10 na terça, 1 na quarta
    assert exp.somar(datetime(2026, 10, 16, 15), 24) == datetime(2026, 10, 21, 9)
    # aberto à noite: começa a contar na abertura do dia útil seguinte
    assert exp.somar(datetime(2026, 10, 20, 22), 2) == datetime(2026, 10, 21, 10)
    # sábado 09:00, segunda 12/10 é feriado: começa na terça
    assert exp.somar(datetime(2026, 10, 10, 9), 1) == datetime(2026, 10, 13, 9)
    assert exp.horas_entre(datetime(2026, 10, 16, 15), datetime(2026, 10, 21, 9)) == 24
    assert exp.horas_entre(datetime(2026, 10, 21, 9), datetime(2026, 10, 16, 15)) == -24


def test_expediente_ate_meia_noite():
    exp = Expediente(CalendarioUtil(), datetime(1, 1, 1, 0).time(), datetime(1, 1, 1, 0).time())
    # dia útil inteiro: sexta 15:00 + 24 h = segunda 15:00 (sábado e domingo não contam)
    assert exp.somar(datetime(2026, 10, 16, 15), 24) == datetime(2026, 10, 19, 15)


# ---------- abertura e prazo ----------


def test_operacional_abre_chamado_com_prazo_de_24h_uteis(api, paulo):
    r = abrir(api, paulo, ocorrido_em="2026-10-20T07:30:00")
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["codigo"] == "CH-00001" and c["status"] == "ABERTO"
    assert c["empresa"]["nome"] == "MSI" and c["solicitante"]["nome"] == "Paulo"
    assert c["ocorrido_em"] == "2026-10-20T07:30:00" and c["aberto_em"] == "2026-10-20T10:00:00"
    # terça 10:00 + 24 h úteis: 8 h terça, 10 h quarta, 6 h quinta → quinta 14:00
    assert c["prazo_em"] == "2026-10-22T14:00:00" and c["prazo_horas"] == 24
    assert c["prazo"]["situacao"] == "NO_PRAZO" and c["prazo"]["horas_restantes"] == 24
    assert tipos(c) == ["ABERTURA"]
    assert c["pode_cancelar"] and not c["pode_responder"] and not c["pode_assumir"]


def test_data_do_problema_nao_pode_ser_futura(api, paulo):
    assert abrir(api, paulo, ocorrido_em="2026-10-21T10:00:00").status_code == 422


def test_tecnico_nao_abre_chamado(api, tiago):
    assert abrir(api, tiago).status_code == 403


def test_prazo_vencendo_e_atrasado(api, estado, paulo):
    oid = abrir(api, paulo).json()["id"]
    estado["agora"] = datetime(2026, 10, 22, 11)  # faltam 3 h úteis (alerta: 4 h)
    c = api.get(f"/api/manutencao/chamados/{oid}", headers=paulo).json()
    assert c["prazo"]["situacao"] == "VENCENDO" and c["prazo"]["horas_restantes"] == 3
    estado["agora"] = datetime(2026, 10, 23, 9)  # passou do prazo (quinta 14:00)
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
    estado["agora"] = datetime(2026, 10, 21, 9, 30)  # quarta 09:30: 9,5 h úteis depois da abertura
    corpo = {"atendido_em": "2026-10-21T09:00:00", "equipamento": "Monitor Dixtal DX-2023", "identificacao": "PAT 4471",
             "diagnostico": "Fonte de alimentação em curto.", "causa": "Oscilação na rede elétrica <220V>",
             "servico_executado": "Troca da fonte.\nTeste de funcionamento ok.", "pecas": "Fonte 12V",
             "situacao_equipamento": "OPERANDO", "recomendacoes": "Instalar no-break."}
    r = api.post(f"/api/manutencao/chamados/{oid}/relatorios", json=corpo, headers=tiago)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["prazo"]["situacao"] == "CUMPRIDO" and c["prazo"]["horas_ate_diagnostico"] == 9.5
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
    # terça 10:00 → sexta 09:00: 8 + 10 + 10 + 1 = 29 h úteis (prazo de 24)
    assert c["prazo"]["situacao"] == "CUMPRIDO_COM_ATRASO" and c["prazo"]["horas_ate_diagnostico"] == 29


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
    assert p["expediente"] == "08:00–18:00" and len(p["urgentes"]) == 2

    do_tiago = api.get("/api/manutencao/painel", headers=tiago).json()
    assert do_tiago["empresa_do_tecnico"]["nome"] == "MSI" and do_tiago["aguardando_diagnostico"] == 1


# ---------- tempo de solução ----------


def test_tempo_de_solucao_apos_o_diagnostico_fica_registrado(api, estado, paulo, tiago):
    oid = abrir(api, paulo).json()["id"]
    url = f"/api/manutencao/chamados/{oid}"
    api.post(f"{url}/interacoes", data={"texto": "Fonte queimada", "diagnostico": "true"}, headers=tiago)  # ter 10:00
    estado["agora"] = datetime(2026, 10, 21, 11, 30)  # qua 11:30
    c = api.get(url, headers=tiago).json()
    assert c["execucao_horas_uteis"] == 11.5 and c["solucao_horas_uteis"] is None  # em execução há 11,5 h úteis

    c = api.post(f"{url}/concluir", json={"texto": "Fonte trocada"}, headers=tiago).json()
    # ter 10:00 → qua 11:30: 8 h + 3,5 h úteis; 25,5 h corridas
    assert (c["solucao_horas_uteis"], c["solucao_horas_corridas"], c["execucao_horas_uteis"]) == (11.5, 25.5, None)
    conclusao = c["interacoes"][-1]["texto"]
    assert conclusao.startswith("Fonte trocada") and "11 h 30 min úteis (25 h 30 min corridas)" in conclusao

    estado["agora"] = datetime(2026, 10, 22, 9)
    c = api.post(f"{url}/reabrir", json={"motivo": "Voltou a desligar"}, headers=paulo).json()
    assert c["solucao_horas_uteis"] is None  # reaberto: o tempo volta a contar
    estado["agora"] = datetime(2026, 10, 22, 10)
    c = api.post(f"{url}/concluir", json={}, headers=tiago).json()
    assert c["solucao_horas_uteis"] == 20  # do diagnóstico (ter 10:00) até a nova conclusão (qui 10:00)

    p = api.get("/api/manutencao/painel", headers=paulo).json()
    assert next(e for e in p["por_empresa"] if e["empresa"]["nome"] == "MSI")["media_horas_solucao"] == 20


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