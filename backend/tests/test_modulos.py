"""Módulos da plataforma: quem entra em qual módulo e quem administra o quê."""

OFICIOS_CLIENTE = {"modulo": "OFICIOS", "perfil": "CLIENTE"}
OFICIOS_ADMIN = {"modulo": "OFICIOS", "perfil": "ADMIN"}
MANUT_CLIENTE = {"modulo": "MANUTENCAO", "perfil": "CLIENTE"}
MANUT_ADMIN = {"modulo": "MANUTENCAO", "perfil": "ADMIN"}


def eu(api, quem):
    return api.get("/api/auth/me", headers=quem).json()


def criar_usuario(api, quem, login, modulos, **extra):
    corpo = {"nome": login.title(), "login": login, "senha": "12345678", "modulos": modulos, **extra}
    return api.post("/api/usuarios", json=corpo, headers=quem)


def papeis(usuario):
    return {a["modulo"]: a["perfil"] for a in usuario["modulos"]}


# ---------- o que cada um enxerga ----------


def test_cada_usuario_ve_so_os_modulos_habilitados(api, master, admin, ana, marta, paulo):
    def lista(quem):
        return {m["modulo"]: m["perfil"] for m in api.get("/api/modulos", headers=quem).json()}

    assert lista(master) == {"OFICIOS": "MASTER", "MANUTENCAO": "MASTER"}
    assert lista(admin) == {"OFICIOS": "ADMIN"}
    assert lista(ana) == {"OFICIOS": "CLIENTE"}
    # Operacionais da Manutenção também usam o Planner (regra), com papéis independentes
    assert lista(marta) == {"MANUTENCAO": "ADMIN", "OFICIOS": "CLIENTE"}
    assert lista(paulo) == {"MANUTENCAO": "CLIENTE", "OFICIOS": "CLIENTE"}
    assert papeis(eu(api, marta)) == {"MANUTENCAO": "ADMIN", "OFICIOS": "CLIENTE"}
    assert papeis(eu(api, master)) == {"OFICIOS": "MASTER", "MANUTENCAO": "MASTER"}


def test_sem_login_nao_lista_modulos(api):
    assert api.get("/api/modulos").status_code == 401


# ---------- acesso às rotas de cada módulo ----------


def test_planner_exige_acesso_ao_modulo(api, master, admin, ana, marta, paulo, tiago, carla):
    for quem in (master, admin, ana, marta, paulo):
        assert api.get("/api/oficios", headers=quem).status_code == 200
    for quem in (tiago, carla):  # técnicos das empresas: só a Manutenção
        assert api.get("/api/oficios", headers=quem).status_code == 403
        assert api.get("/api/dashboard/resumo", headers=quem).status_code in (403, 404, 422)  # nunca 200
        assert api.get("/api/feriados", headers=quem).status_code == 403
        assert api.get("/api/tipos", headers=quem).status_code == 403


def test_manutencao_exige_acesso_ao_modulo(api, master, admin, ana, marta, paulo):
    assert api.get("/api/manutencao/resumo", headers=ana).status_code == 403
    assert api.get("/api/manutencao/resumo", headers=admin).status_code == 403  # admin do Planner, não da Manutenção
    assert api.get("/api/manutencao/resumo").status_code == 401
    assert api.get("/api/manutencao/resumo", headers=master).json()["eh_admin"] is True
    assert api.get("/api/manutencao/resumo", headers=marta).json()["eh_admin"] is True
    resumo = api.get("/api/manutencao/resumo", headers=paulo).json()
    assert resumo["eh_admin"] is False and resumo["perfil"] == "CLIENTE"


def test_admin_de_um_modulo_nao_e_admin_do_outro(api, master):
    # Admin só do Planner e cliente da Manutenção
    assert criar_usuario(api, master, "zeca", [OFICIOS_ADMIN, MANUT_CLIENTE]).status_code == 201
    zeca = {"Authorization": "Bearer " + api.post(
        "/api/auth/login", data={"username": "zeca", "password": "12345678"}).json()["access_token"]}
    assert api.post("/api/feriados", json={"data": "2026-12-08", "descricao": "Padroeira"},
                    headers=zeca).status_code == 201  # poder de admin no Planner
    resumo = api.get("/api/manutencao/resumo", headers=zeca).json()
    assert resumo["eh_admin"] is False and resumo["perfil"] == "CLIENTE"  # sem poder de admin na Manutenção


def test_cliente_nao_e_dono_de_oficio_sem_acesso_ao_planner(api, admin, tiago):
    corpo = {"numero": "1", "data_oficio": "2026-10-01", "tipo": "COMUNICADOS", "dono_id": eu(api, tiago)["id"]}
    assert api.post("/api/oficios", json=corpo, headers=admin).status_code == 400


# ---------- cadastro: quem habilita quem ----------


def test_admin_habilita_so_nos_modulos_que_administra(api, admin, marta):
    assert criar_usuario(api, admin, "leo", [MANUT_CLIENTE]).status_code == 403  # admin do Planner, não da Manutenção
    assert criar_usuario(api, marta, "leo", [OFICIOS_CLIENTE]).status_code == 403
    assert criar_usuario(api, admin, "leo", []).status_code == 422  # precisa habilitar em algum módulo
    novo = criar_usuario(api, admin, "leo", [OFICIOS_CLIENTE])
    assert novo.status_code == 201 and papeis(novo.json()) == {"OFICIOS": "CLIENTE"}
    ok = criar_usuario(api, marta, "lia", [MANUT_CLIENTE])
    # o operacional ganha junto o acesso de cliente ao Planner, mesmo a admin não administrando o Planner
    assert ok.status_code == 201 and papeis(ok.json()) == {"MANUTENCAO": "CLIENTE", "OFICIOS": "CLIENTE"}


def test_so_o_master_cria_administradores_e_masters(api, master, admin, marta):
    assert criar_usuario(api, marta, "user_x1", [MANUT_ADMIN]).status_code == 403
    assert criar_usuario(api, marta, "user_x2", [MANUT_CLIENTE], master=True).status_code == 403
    r = criar_usuario(api, master, "user_x3", [OFICIOS_ADMIN, MANUT_CLIENTE])
    assert r.status_code == 201 and papeis(r.json()) == {"OFICIOS": "ADMIN", "MANUTENCAO": "CLIENTE"}
    m = criar_usuario(api, master, "user_x4", [OFICIOS_CLIENTE], master=True)  # master ignora a lista de módulos
    assert m.json()["perfil"] == "MASTER" and papeis(m.json()) == {"OFICIOS": "MASTER", "MANUTENCAO": "MASTER"}


def test_modulo_repetido_ou_master_na_lista_e_recusado(api, master):
    assert criar_usuario(api, master, "user_y1", [OFICIOS_CLIENTE, OFICIOS_ADMIN]).status_code == 422
    assert criar_usuario(api, master, "user_y2", [{"modulo": "OFICIOS", "perfil": "MASTER"}]).status_code == 422
    assert criar_usuario(api, master, "user_y3", [{"modulo": "OUTRO", "perfil": "CLIENTE"}]).status_code == 422


# ---------- edição: cada admin mexe só no módulo dele ----------


def test_cada_admin_ve_so_os_usuarios_do_seu_modulo(api, master, admin, marta, ana, paulo):
    criar_usuario(api, master, "duplo", [OFICIOS_CLIENTE, MANUT_CLIENTE])

    def logins(quem):
        return {u["login"] for u in api.get("/api/usuarios", headers=quem).json()}

    assert logins(admin) == {"admin", "ana", "bruno", "duplo", "marta", "paulo"}  # operacionais usam o Planner
    assert logins(marta) == {"marta", "paulo", "tiago", "carla", "duplo"}
    assert {"master", "marta", "paulo"} <= logins(master)
    filtrado = api.get("/api/usuarios", params={"modulo": "MANUTENCAO"}, headers=master).json()
    assert {u["login"] for u in filtrado} == {"master", "marta", "paulo", "tiago", "carla", "duplo"}


def test_admin_do_planner_nao_mexe_na_conta_de_quem_usa_outro_modulo(api, master, admin, marta):
    duplo = criar_usuario(api, master, "duplo", [OFICIOS_CLIENTE, MANUT_CLIENTE]).json()
    url = f"/api/usuarios/{duplo['id']}"
    # Trocar nome, senha ou situação atingiria também a Manutenção
    assert api.patch(url, json={"nome": "Novo"}, headers=admin).status_code == 403
    assert api.patch(url, json={"senha": "outra-senha-1"}, headers=admin).status_code == 403
    assert api.patch(url, json={"ativo": False}, headers=admin).status_code == 403
    # Operacional da Manutenção não perde o Planner (regra)
    r = api.patch(url, json={"modulos": []}, headers=admin)
    assert r.status_code == 400 and "precisa ter acesso ao Planner" in r.json()["detail"]
    # O admin da Manutenção não mexe no papel do Planner
    assert api.patch(url, json={"modulos": [OFICIOS_ADMIN]}, headers=marta).status_code == 403
    # O MASTER edita tudo
    r = api.patch(url, json={"nome": "Novo", "modulos": [OFICIOS_CLIENTE, MANUT_ADMIN]}, headers=master)
    assert r.status_code == 200 and r.json()["nome"] == "Novo"
    assert papeis(r.json()) == {"OFICIOS": "CLIENTE", "MANUTENCAO": "ADMIN"}


def test_habilitar_usuario_existente_em_outro_modulo(api, admin, marta, ana):
    id_ana = eu(api, ana)["id"]
    # A Manutenção habilita a Ana (que já usa o Planner) sem mexer no papel dela no Planner
    r = api.patch(f"/api/usuarios/{id_ana}", json={"modulos": [MANUT_CLIENTE]}, headers=marta)
    assert r.status_code == 200
    assert papeis(r.json()) == {"OFICIOS": "CLIENTE", "MANUTENCAO": "CLIENTE"}
    assert api.get("/api/manutencao/resumo", headers=ana).status_code == 200
    assert api.get("/api/oficios", headers=ana).status_code == 200


def test_admin_nao_altera_acesso_de_administrador_nem_de_master(api, master, admin, marta):
    id_marta, id_master = eu(api, marta)["id"], eu(api, master)["id"]
    outro_admin = criar_usuario(api, master, "outro", [MANUT_ADMIN]).json()
    # marta não mexe em outro admin da Manutenção nem no master
    assert api.patch(f"/api/usuarios/{outro_admin['id']}", json={"modulos": [MANUT_CLIENTE]},
                     headers=marta).status_code == 403
    assert api.patch(f"/api/usuarios/{outro_admin['id']}", json={"nome": "X"}, headers=marta).status_code == 403
    assert api.patch(f"/api/usuarios/{id_master}", json={"modulos": [MANUT_CLIENTE]}, headers=marta).status_code == 403
    assert api.patch(f"/api/usuarios/{id_master}", json={"nome": "X"}, headers=marta).status_code == 403
    # ... nem se promove
    assert api.patch(f"/api/usuarios/{id_marta}", json={"modulos": [MANUT_ADMIN, OFICIOS_ADMIN]},
                     headers=marta).status_code == 400  # o próprio acesso não se altera
    assert api.patch(f"/api/usuarios/{id_marta}", json={"nome": "Marta M."}, headers=marta).status_code == 200


def test_so_o_master_concede_acesso_total(api, master, admin, ana):
    id_ana = eu(api, ana)["id"]
    assert api.patch(f"/api/usuarios/{id_ana}", json={"master": True}, headers=admin).status_code == 403
    r = api.patch(f"/api/usuarios/{id_ana}", json={"master": True}, headers=master)
    assert r.status_code == 200 and r.json()["perfil"] == "MASTER"
    assert api.get("/api/manutencao/resumo", headers=ana).status_code == 200  # agora vê tudo
    r = api.patch(f"/api/usuarios/{id_ana}", json={"master": False, "modulos": [OFICIOS_CLIENTE]}, headers=master)
    assert papeis(r.json()) == {"OFICIOS": "CLIENTE"}
    assert api.get("/api/manutencao/resumo", headers=ana).status_code == 403


def test_alterar_acesso_vale_na_hora_e_fica_na_auditoria(api, master, ana):
    id_ana = eu(api, ana)["id"]
    msi = next(e["id"] for e in api.get("/api/manutencao/empresas", headers=master).json() if e["nome"] == "MSI")
    assert api.get("/api/oficios", headers=ana).status_code == 200
    # Vira técnica da MSI (técnico não usa o Planner): perde o Planner na hora
    r = api.patch(f"/api/usuarios/{id_ana}",
                  json={"modulos": [{"modulo": "MANUTENCAO", "perfil": "TECNICO", "empresa_id": msi}]}, headers=master)
    assert r.status_code == 200, r.text
    assert api.get("/api/oficios", headers=ana).status_code == 403  # o mesmo token, já sem acesso ao Planner
    ultima = api.get("/api/auditoria", headers=master).json()["itens"][0]
    assert ultima["descricao"] == "Alterou o usuário Ana (acesso aos módulos)"
    assert ultima["detalhes"]["modulos"] == {
        "de": "Planner de Ofícios (cliente)", "para": "Manutenção Clínica (técnico · MSI)"}


def test_todo_operacional_tem_o_planner(api, master, marta):
    # Criado pelo master só com a Manutenção: ganha o Planner como cliente
    r = criar_usuario(api, master, "op1", [MANUT_ADMIN])
    assert papeis(r.json()) == {"MANUTENCAO": "ADMIN", "OFICIOS": "CLIENTE"}
    # Quem já administra o Planner continua administrador lá (os papéis são independentes)
    r = criar_usuario(api, master, "op2", [MANUT_CLIENTE, OFICIOS_ADMIN])
    assert papeis(r.json()) == {"MANUTENCAO": "CLIENTE", "OFICIOS": "ADMIN"}
    # Técnico das empresas não recebe o Planner
    msi = next(e["id"] for e in api.get("/api/manutencao/empresas", headers=marta).json() if e["nome"] == "MSI")
    r = criar_usuario(api, marta, "tec1", [{"modulo": "MANUTENCAO", "perfil": "TECNICO", "empresa_id": msi}])
    assert papeis(r.json()) == {"MANUTENCAO": "TECNICO"}
    # Técnico que vira operacional passa a ter o Planner
    r = api.patch(f"/api/usuarios/{r.json()['id']}", json={"modulos": [MANUT_CLIENTE]}, headers=marta)
    assert papeis(r.json()) == {"MANUTENCAO": "CLIENTE", "OFICIOS": "CLIENTE"}
    # A admin da Manutenção continua gerindo a conta do operacional (o Planner veio junto com o papel)
    assert api.patch(f"/api/usuarios/{r.json()['id']}", json={"nome": "Operacional 1"}, headers=marta).status_code == 200


def test_ultimo_master_nao_deixa_de_ser_master(api, master):
    id_master = eu(api, master)["id"]
    assert api.patch(f"/api/usuarios/{id_master}", json={"master": False}, headers=master).status_code == 400
