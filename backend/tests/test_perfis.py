"""MASTER/ADMIN/CLIENTE, pedidos de exclusão e registro de atividades."""

from pathlib import Path

PDF = b"%PDF-1.4 x"


def criar(api, quem, numero, **extra):
    corpo = {"numero": numero, "data_oficio": "2026-10-01", "tipo": "EPIS", **extra}
    return api.post("/api/oficios", json=corpo, headers=quem).json()


def me(api, quem):
    return api.get("/api/auth/me", headers=quem).json()


# ---------- pedidos de exclusão ----------


def test_cliente_pede_exclusao_e_admin_recusa(api, admin, ana, bruno):
    oid = criar(api, ana, "1")["id"]
    url = f"/api/oficios/{oid}/exclusao"
    assert api.post(url, json={"motivo": "curto"}, headers=bruno).status_code == 404  # não é dele
    assert api.post(url, json={"motivo": "abc"}, headers=ana).status_code == 422  # motivo curto demais
    r = api.post(url, json={"motivo": "Cadastrado em duplicidade"}, headers=ana)
    assert r.status_code == 201 and r.json()["status"] == "PENDENTE"
    assert api.post(url, json={"motivo": "De novo, por favor"}, headers=ana).status_code == 409

    detalhe = api.get(f"/api/oficios/{oid}", headers=ana).json()
    assert detalhe["exclusao_pendente"]["motivo"] == "Cadastrado em duplicidade"
    assert detalhe["exclusao_pendente"]["solicitante_nome"] == "Ana"
    assert api.get("/api/exclusoes/pendentes", headers=admin).json() == {"total": 1}
    assert api.get("/api/exclusoes/pendentes", headers=ana).status_code == 403

    pedido = api.get("/api/exclusoes", params={"status": "PENDENTE"}, headers=admin).json()[0]
    assert api.post(f"/api/exclusoes/{pedido['id']}/recusar", json={}, headers=admin).status_code == 422
    assert api.post(f"/api/exclusoes/{pedido['id']}/recusar", json={"resposta": "x"}, headers=ana).status_code == 403
    r = api.post(f"/api/exclusoes/{pedido['id']}/recusar", json={"resposta": "Ofício ainda em uso"}, headers=admin)
    assert r.json()["status"] == "RECUSADA" and r.json()["decidido_por_nome"] == "Admin"
    assert api.get(f"/api/oficios/{oid}", headers=ana).json()["exclusao_pendente"] is None  # continua existindo
    meus = api.get("/api/exclusoes", headers=ana).json()
    assert [(p["status"], p["resposta"]) for p in meus] == [("RECUSADA", "Ofício ainda em uso")]
    assert api.get("/api/exclusoes", headers=bruno).json() == []


def test_admin_aprova_e_oficio_some(api, admin, ana, tmp_path):
    oid = criar(api, ana, "1")["id"]
    api.post(f"/api/oficios/{oid}/anexos/OFICIO", files={"arquivo": ("o.pdf", PDF)}, headers=ana)
    api.post(f"/api/oficios/{oid}/exclusao", json={"motivo": "Cadastrado por engano"}, headers=ana)
    pedido = api.get("/api/exclusoes", headers=admin).json()[0]

    assert api.post(f"/api/exclusoes/{pedido['id']}/aprovar", json={}, headers=admin).status_code == 204
    assert api.get(f"/api/oficios/{oid}", headers=ana).status_code == 404
    assert list(Path(tmp_path / "storage").rglob("*.*")) == []  # arquivos apagados
    p = api.get("/api/exclusoes", headers=ana).json()[0]
    assert (p["status"], p["oficio_id"], p["referencia"]) == ("APROVADA", None, "Ofício nº 1 · Ana")
    assert api.post(f"/api/exclusoes/{pedido['id']}/aprovar", json={}, headers=admin).status_code == 409

    # A trilha continua legível depois da exclusão
    acoes = [(e["acao"], e["referencia"]) for e in api.get("/api/auditoria", headers=admin).json()["itens"]]
    assert ("OFICIO_EXCLUIDO", "Ofício nº 1 · Ana") in acoes
    assert ("EXCLUSAO_APROVADA", "Ofício nº 1 · Ana") in acoes
    assert ("EXCLUSAO_SOLICITADA", "Ofício nº 1 · Ana") in acoes


def test_cancelar_pedido_e_exclusao_direta(api, admin, ana):
    oid = criar(api, ana, "1")["id"]
    url = f"/api/oficios/{oid}/exclusao"
    api.post(url, json={"motivo": "Vou refazer depois"}, headers=ana)
    assert api.delete(url, headers=ana).status_code == 204
    assert api.delete(url, headers=ana).status_code == 404  # nada pendente
    assert api.get("/api/exclusoes", headers=ana).json()[0]["status"] == "CANCELADA"

    # Admin excluindo direto um ofício com pedido pendente encerra o pedido como aprovado
    api.post(url, json={"motivo": "Agora sim, pode excluir"}, headers=ana)
    assert api.delete(f"/api/oficios/{oid}", headers=admin).status_code == 204
    status = [p["status"] for p in api.get("/api/exclusoes", headers=ana).json()]
    assert sorted(status) == ["APROVADA", "CANCELADA"]


# ---------- registro de atividades ----------


def test_auditoria_registra_alteracoes_na_conta_de_quem_fez(api, admin, ana, bruno):
    oid = criar(api, ana, "1", protocolo="P-1")["id"]
    api.patch(f"/api/oficios/{oid}", json={"protocolo": "P-2", "tipo": "COMUNICADOS"}, headers=ana)
    api.patch(f"/api/oficios/{oid}", json={"protocolo": "P-2"}, headers=ana)  # nada mudou: não registra
    api.patch(f"/api/oficios/{oid}/status", json={"status": "CONFIRMADO", "data_resposta": "2026-10-05"},
              headers=admin)
    criar(api, bruno, "9")

    da_ana = api.get("/api/auditoria", headers=ana).json()
    acoes = [(e["acao"], e["usuario_nome"]) for e in da_ana["itens"]]
    # A Ana vê o que ela fez e o que o admin fez no ofício dela, mas nada do Bruno
    assert acoes == [("STATUS_ALTERADO", "Admin"), ("OFICIO_EDITADO", "Ana"), ("OFICIO_CRIADO", "Ana")]
    edicao = da_ana["itens"][1]
    assert edicao["detalhes"] == {"protocolo": {"de": "P-1", "para": "P-2"}, "tipo": {"de": "EPIS", "para": "COMUNICADOS"}}
    assert da_ana["itens"][0]["detalhes"]["status"] == {"de": "PENDENTE_RESPOSTA", "para": "CONFIRMADO"}

    tudo = api.get("/api/auditoria", headers=admin).json()
    assert tudo["total"] == 4
    so_bruno = api.get("/api/auditoria", params={"usuario_id": me(api, bruno)["id"]}, headers=admin).json()
    assert [e["descricao"] for e in so_bruno["itens"]] == ["Cadastrou o ofício nº 9"]
    assert edicao["descricao"] == "Editou o ofício nº 1 (tipo, protocolo)"
    do_oficio = api.get("/api/auditoria", params={"oficio_id": oid}, headers=ana).json()
    assert do_oficio["total"] == 3


def test_auditoria_de_anexos_usuarios_e_feriados(api, master, ana):
    oid = criar(api, ana, "1")["id"]
    api.post(f"/api/oficios/{oid}/anexos/OFICIO", files={"arquivo": ("a.pdf", PDF)}, headers=ana)
    api.post(f"/api/oficios/{oid}/anexos/OFICIO", files={"arquivo": ("b.pdf", PDF)}, headers=ana)
    anexo = api.get(f"/api/oficios/{oid}", headers=ana).json()["anexos"][0]
    api.delete(f"/api/anexos/{anexo['id']}", headers=ana)
    api.post("/api/usuarios", json={"nome": "Caio", "login": "caio", "senha": "12345678"}, headers=master)
    api.post("/api/feriados", json={"data": "2026-12-08", "descricao": "Padroeira"}, headers=master)

    acoes = [e["acao"] for e in api.get("/api/auditoria", headers=master).json()["itens"]]
    assert acoes[:5] == ["FERIADO_CRIADO", "USUARIO_CRIADO", "ANEXO_REMOVIDO", "ANEXO_SUBSTITUIDO", "ANEXO_ENVIADO"]


# ---------- MASTER x ADMIN ----------


def test_hierarquia_master_admin(api, master, admin, ana):
    novo = {"nome": "Outro", "login": "outro", "senha": "12345678"}
    assert api.post("/api/usuarios", json={**novo, "perfil": "ADMIN"}, headers=admin).status_code == 403
    assert api.post("/api/usuarios", json={**novo, "perfil": "MASTER"}, headers=admin).status_code == 403
    cliente = api.post("/api/usuarios", json=novo, headers=admin)
    assert cliente.status_code == 201  # admin gerencia clientes

    id_master = me(api, master)["id"]
    id_admin = me(api, admin)["id"]
    assert api.patch(f"/api/usuarios/{id_master}", json={"nome": "X"}, headers=admin).status_code == 403
    assert api.patch(f"/api/usuarios/{cliente.json()['id']}", json={"perfil": "ADMIN"}, headers=admin).status_code == 403
    assert api.patch(f"/api/usuarios/{id_admin}", json={"nome": "Admin 2"}, headers=admin).status_code == 200  # o próprio

    # MASTER manda em todos
    assert api.patch(f"/api/usuarios/{id_admin}", json={"ativo": False}, headers=master).status_code == 200
    assert api.patch(f"/api/usuarios/{cliente.json()['id']}", json={"perfil": "ADMIN"}, headers=master).status_code == 200
    assert api.patch(f"/api/usuarios/{id_master}", json={"perfil": "ADMIN"}, headers=master).status_code == 400
    assert api.post("/api/usuarios", json={"nome": "Master 2", "login": "master2", "senha": "12345678", "perfil": "MASTER"},
                    headers=master).status_code == 201

    # Cliente continua sem acesso à gestão
    assert api.get("/api/usuarios", headers=ana).status_code == 403
    # MASTER também vê todos os ofícios
    criar(api, ana, "1")
    assert api.get("/api/oficios", headers=master).json()["total"] == 1


def test_trocar_login(api, master, admin, ana):
    id_ana = me(api, ana)["id"]
    assert api.patch(f"/api/usuarios/{id_ana}", json={"login": "admin"}, headers=master).status_code == 409
    assert api.patch(f"/api/usuarios/{id_ana}", json={"login": "ADMIN"}, headers=master).status_code == 409
    assert api.patch(f"/api/usuarios/{id_ana}", json={"login": "com espaço"}, headers=master).status_code == 422
    r = api.patch(f"/api/usuarios/{id_ana}", json={"login": "ana.souza"}, headers=admin)  # admin gerencia clientes
    assert r.status_code == 200 and r.json()["login"] == "ana.souza"
    # Senha continua a mesma; só o login muda
    assert api.post("/api/auth/login", data={"username": "ana.souza", "password": "senha-ana"}).status_code == 200
    assert api.post("/api/auth/login", data={"username": "ana", "password": "senha-ana"}).status_code == 401
    ultima = api.get("/api/auditoria", headers=master).json()["itens"][0]
    assert ultima["descricao"] == "Alterou o usuário Ana (login)"
    assert ultima["detalhes"] == {"login": {"de": "ana", "para": "ana.souza"}}
