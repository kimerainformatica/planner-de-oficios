from datetime import date
from pathlib import Path

PDF = b"%PDF-1.4 conteudo de teste"


def criar(api, quem, numero, data, protocolo=None, **extra):
    corpo = {"numero": numero, "data_oficio": data, "tipo": "COMUNICADOS", "protocolo": protocolo or f"P-{numero}-{data}", **extra}
    return api.post("/api/oficios", json=corpo, headers=quem)


def meu_id(api, quem):
    return api.get("/api/auth/me", headers=quem).json()["id"]


def responder(api, oid, status, data_resposta=None, **extra):
    corpo = {"status": status, "data_resposta": data_resposta, **extra}
    return api.patch(f"/api/oficios/{oid}/status", json=corpo, headers=extra.pop("headers", None))


# ---------- autenticação ----------


def test_sem_login_e_401(api):
    assert api.get("/api/oficios").status_code == 401


def test_senha_errada(api):
    assert api.post("/api/auth/login", data={"username": "admin", "password": "errada"}).status_code == 401


def test_admin_cria_usuario_e_desativa(api, admin):
    r = api.post(
        "/api/usuarios", json={"nome": "Caio", "login": "caio", "senha": "12345678", "perfil": "CLIENTE"}, headers=admin
    )
    assert r.status_code == 201
    novo = api.post("/api/auth/login", data={"username": "caio", "password": "12345678"})
    assert novo.status_code == 200
    api.patch(f"/api/usuarios/{r.json()['id']}", json={"ativo": False}, headers=admin)
    token = {"Authorization": f"Bearer {novo.json()['access_token']}"}
    assert api.get("/api/oficios", headers=token).status_code == 401  # token antigo deixa de valer


def test_admin_nao_se_rebaixa(api, admin):
    r = api.patch(f"/api/usuarios/{meu_id(api, admin)}", json={"perfil": "CLIENTE"}, headers=admin)
    assert r.status_code == 400


def test_cliente_nao_gerencia_usuarios(api, ana):
    assert api.get("/api/usuarios", headers=ana).status_code == 403


# ---------- visibilidade por dono ----------


def test_cada_cliente_ve_so_os_seus_e_admin_ve_todos(api, admin, ana, bruno):
    oficio_ana = criar(api, ana, "1", "2026-10-01").json()
    criar(api, bruno, "1", "2026-10-01")
    assert oficio_ana["dono"]["nome"] == "Ana"

    assert [o["dono"]["nome"] for o in api.get("/api/oficios", headers=ana).json()["itens"]] == ["Ana"]
    assert [o["dono"]["nome"] for o in api.get("/api/oficios", headers=bruno).json()["itens"]] == ["Bruno"]
    assert api.get("/api/oficios", headers=admin).json()["total"] == 2
    filtrado = api.get("/api/oficios", params={"dono_id": meu_id(api, ana)}, headers=admin).json()
    assert [o["dono"]["nome"] for o in filtrado["itens"]] == ["Ana"]

    # Ofício de outro cliente "não existe" para quem não é dono
    assert api.get(f"/api/oficios/{oficio_ana['id']}", headers=bruno).status_code == 404
    assert api.patch(f"/api/oficios/{oficio_ana['id']}", json={"numero": "X"}, headers=bruno).status_code == 404

    assert api.get("/api/dashboard/resumo", headers=ana).json()["total"] == 1
    assert api.get("/api/dashboard/resumo", headers=admin).json()["total"] == 2


def test_numeracao_e_protocolo_sao_unicos_por_cliente(api, ana, bruno):
    assert criar(api, ana, "5", "2026-03-01", "ABC").status_code == 201
    assert criar(api, bruno, "5", "2026-03-01", "ABC").status_code == 201  # outro cliente: ok
    assert criar(api, ana, "6", "2026-03-01", "ABC").status_code == 409  # protocolo repetido
    assert criar(api, ana, "5", "2026-07-01", "XYZ").status_code == 409  # nº repetido no ano
    assert criar(api, ana, "5", "2025-07-01", "XYZ").status_code == 201  # outro ano: ok


def test_admin_cadastra_em_nome_do_cliente(api, admin, ana, bruno):
    r = criar(api, admin, "1", "2026-10-01", dono_id=meu_id(api, ana))
    assert r.json()["dono"]["nome"] == "Ana"
    assert api.get("/api/oficios", headers=ana).json()["total"] == 1
    # Cliente não consegue cadastrar em nome de outro: o campo é ignorado
    r = criar(api, ana, "2", "2026-10-01", dono_id=meu_id(api, bruno))
    assert r.json()["dono"]["nome"] == "Ana"


def test_cliente_responde_so_os_proprios(api, ana, bruno):
    oid = criar(api, ana, "1", "2026-10-01").json()["id"]
    assert responder(api, oid, "NAO_CONFIRMADO", "2026-10-02", headers=bruno).status_code == 404
    r = responder(api, oid, "NAO_CONFIRMADO", "2026-10-02", headers=ana)
    assert r.status_code == 200
    r = responder(api, oid, "PENDENTE_RESPOSTA", observacao="Reenviado", headers=ana)
    assert r.json()["inicio_prazo"] == "2026-10-20"
    r = responder(api, oid, "CONFIRMADO", "2026-10-20", headers=ana)
    assert [h["usuario_nome"] for h in r.json()["historico"]] == ["Ana"] * 4
    assert responder(api, oid, "PENDENTE_RESPOSTA", headers=ana).status_code == 400  # confirmado é final


def test_permissoes_do_cliente(api, admin, ana):
    oid = criar(api, ana, "1", "2026-10-01").json()["id"]
    assert api.patch(f"/api/oficios/{oid}", json={"observacao": "ok"}, headers=ana).status_code == 200
    assert api.delete(f"/api/oficios/{oid}", headers=ana).status_code == 403  # precisa pedir a um admin

    responder(api, oid, "CONFIRMADO", "2026-10-02", headers=admin)  # admin responde ofício de cliente
    # Confirmado: o cliente, como o admin, ainda corrige dados e documentos (só o status é final)
    assert api.patch(f"/api/oficios/{oid}", json={"observacao": "x"}, headers=ana).status_code == 200
    pdf = {"arquivo": ("o.pdf", PDF, "application/pdf")}
    assert api.post(f"/api/oficios/{oid}/anexos/OFICIO", files=pdf, headers=ana).status_code == 201
    assert responder(api, oid, "PENDENTE_RESPOSTA", headers=ana).status_code == 400

# ---------- cadastro ----------


def test_novo_oficio_sempre_entra_pendente(api, ana):
    r = criar(api, ana, "10", "2026-10-15", status="CONFIRMADO")
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["status"] == "PENDENTE_RESPOSTA"
    assert corpo["inicio_prazo"] == "2026-10-15"
    assert corpo["nivel_alerta"] == "NORMAL"
    assert corpo["dias_uteis_decorridos"] == 3
    assert [(h["status_novo"], h["usuario_nome"]) for h in corpo["historico"]] == [("PENDENTE_RESPOSTA", "Ana")]


def test_data_futura_rejeitada(api, ana):
    assert criar(api, ana, "1", "2999-01-01").status_code == 422


def test_editar_data_move_o_prazo(api, ana):
    oficio = criar(api, ana, "1", "2026-10-01", observacao="nota").json()
    r = api.patch(
        f"/api/oficios/{oficio['id']}", json={"observacao": None, "data_oficio": "2026-09-01"}, headers=ana
    )
    assert r.json()["observacao"] is None
    assert r.json()["inicio_prazo"] == "2026-09-01"
    assert r.json()["nivel_alerta"] == "CRITICO"


# ---------- prazos e alertas ----------


def test_alertas_filtros_e_dashboard(api, admin):
    # Hoje (fixo nos testes) = 20/10/2026
    criar(api, admin, "1", "2026-09-30")  # 14 dias úteis -> NORMAL
    criar(api, admin, "2", "2026-09-29")  # 15 -> ATENCAO
    criar(api, admin, "3", "2026-09-09")  # 29 -> ATENCAO
    criar(api, admin, "4", "2026-09-08")  # 30 -> CRITICO
    respondido = criar(api, admin, "5", "2026-08-01").json()
    responder(api, respondido["id"], "CONFIRMADO", "2026-08-10", headers=admin)

    def numeros(alerta):
        r = api.get("/api/oficios", params={"alerta": alerta, "ordem": "antigos"}, headers=admin)
        return [o["numero"] for o in r.json()["itens"]]

    assert numeros("NORMAL") == ["1"]
    assert numeros("ATENCAO") == ["3", "2"]
    assert numeros("CRITICO") == ["4"]

    resumo = api.get("/api/dashboard/resumo", headers=admin).json()
    assert resumo | {"data_referencia": None} == {
        "data_referencia": None,
        "total": 5,
        "confirmados": 1,
        "nao_confirmados": 0,
        "pendentes": 4,
        "pendentes_normal": 1,
        "pendentes_atencao": 2,
        "pendentes_critico": 1,
        "pendentes_recebimento": 0,
        "recebidos": 0,
    }

    # Cadastrar o feriado de 12/10 tira um dia útil de todos.
    r = api.post("/api/feriados", json={"data": "2026-10-12", "descricao": "N. Sra."}, headers=admin)
    assert r.status_code == 201
    assert numeros("NORMAL") == ["2", "1"]
    assert numeros("CRITICO") == []


def test_alerta_avanca_com_o_tempo(api, ana, estado):
    oficio = criar(api, ana, "1", "2026-10-19").json()
    assert oficio["nivel_alerta"] == "NORMAL"
    estado["hoje"] = date(2026, 11, 9)  # 15 dias úteis depois
    assert api.get(f"/api/oficios/{oficio['id']}", headers=ana).json()["nivel_alerta"] == "ATENCAO"
    estado["hoje"] = date(2026, 11, 30)  # 30 dias úteis depois
    assert api.get(f"/api/oficios/{oficio['id']}", headers=ana).json()["nivel_alerta"] == "CRITICO"


def test_feriados_nacionais_endpoint(api, admin):
    assert len(api.post("/api/feriados/nacionais/2026", headers=admin).json()) == 13
    assert api.post("/api/feriados/nacionais/2026", headers=admin).json() == []  # não duplica


# ---------- status e reabertura ----------


def test_fluxo_de_status(api, admin, ana):
    oid = criar(api, ana, "1", "2026-10-01").json()["id"]

    assert responder(api, oid, "NAO_CONFIRMADO", headers=admin).status_code == 400  # sem data
    assert responder(api, oid, "NAO_CONFIRMADO", "2026-09-01", headers=admin).status_code == 400  # antes do ofício

    r = responder(api, oid, "NAO_CONFIRMADO", "2026-10-05", headers=admin)
    assert r.json()["status"] == "NAO_CONFIRMADO" and r.json()["nivel_alerta"] is None

    assert responder(api, oid, "PENDENTE_RESPOSTA", observacao="Reenviado", headers=admin).status_code == 200
    r = responder(api, oid, "CONFIRMADO", "2026-10-20", headers=admin)
    assert r.json()["status"] == "CONFIRMADO"
    assert [h["status_novo"] for h in r.json()["historico"]] == [
        "PENDENTE_RESPOSTA",
        "NAO_CONFIRMADO",
        "PENDENTE_RESPOSTA",
        "CONFIRMADO",
    ]
    # CONFIRMADO é final
    assert responder(api, oid, "PENDENTE_RESPOSTA", headers=admin).status_code == 400
    assert responder(api, oid, "NAO_CONFIRMADO", "2026-10-20", headers=admin).status_code == 400


def test_reabertura_zera_o_prazo_e_mantem_historico(api, admin, ana, estado):
    oid = criar(api, ana, "1", "2026-09-01").json()["id"]
    assert api.get(f"/api/oficios/{oid}", headers=ana).json()["nivel_alerta"] == "CRITICO"
    responder(api, oid, "NAO_CONFIRMADO", "2026-10-01", headers=admin)

    r = responder(api, oid, "PENDENTE_RESPOSTA", observacao="Reaberto", headers=admin).json()
    assert r["data_oficio"] == "2026-09-01"  # a data do ofício não muda
    assert r["inicio_prazo"] == "2026-10-20"  # o prazo recomeça hoje
    assert r["data_resposta"] is None
    assert (r["dias_uteis_decorridos"], r["nivel_alerta"]) == (0, "NORMAL")
    ciclo_anterior = r["historico"][1]
    assert (ciclo_anterior["status_novo"], ciclo_anterior["data_resposta"]) == ("NAO_CONFIRMADO", "2026-10-01")

    # Resposta do novo ciclo não pode ser anterior à reabertura
    assert responder(api, oid, "CONFIRMADO", "2026-10-05", headers=admin).status_code == 400

    # Editar a data do ofício não mexe no prazo reaberto
    r = api.patch(f"/api/oficios/{oid}", json={"data_oficio": "2026-08-31"}, headers=ana).json()
    assert r["inicio_prazo"] == "2026-10-20"
    assert api.patch(f"/api/oficios/{oid}", json={"data_oficio": "2026-10-20"}, headers=ana).status_code == 200

    estado["hoje"] = date(2026, 11, 10)  # 15 dias úteis após a reabertura
    assert api.get(f"/api/oficios/{oid}", headers=ana).json()["nivel_alerta"] == "ATENCAO"


# ---------- anexos ----------


def test_anexos(api, admin, ana, bruno, tmp_path):
    oid = criar(api, ana, "1", "2026-10-01").json()["id"]
    url = f"/api/oficios/{oid}/anexos"
    storage = Path(tmp_path / "storage")

    r = api.post(f"{url}/OFICIO", files={"arquivo": ("oficio.pdf", PDF, "application/pdf")}, headers=ana)
    assert r.status_code == 201, r.text
    assert r.json()["mime_type"] == "application/pdf"
    r = api.post(f"{url}/REFERENCIA", files={"arquivo": ("ref.png", b"\x89PNG..", "image/png")}, headers=ana)
    assert r.status_code == 201
    assert len(list(storage.rglob("*.*"))) == 2

    # Reenviar o documento do ofício substitui o anterior (continua 1 de cada tipo); a versão antiga vai
    # para a lixeira e o arquivo dela fica no disco
    r = api.post(f"{url}/OFICIO", files={"arquivo": ("v2.pdf", PDF + b"v2", "application/pdf")}, headers=admin)
    assert r.status_code == 201
    anexos = api.get(f"/api/oficios/{oid}", headers=ana).json()["anexos"]
    assert sorted((a["tipo"], a["nome_original"]) for a in anexos) == [("OFICIO", "v2.pdf"), ("REFERENCIA", "ref.png")]
    assert len(list(storage.rglob("*.*"))) == 3
    assert [i["nome_original"] for i in api.get("/api/lixeira", headers=admin).json()] == ["oficio.pdf"]

    oficio_anexo = next(a for a in anexos if a["tipo"] == "OFICIO")
    r = api.get(f"/api/anexos/{oficio_anexo['id']}/download", headers=ana)
    assert r.content == PDF + b"v2"
    assert r.headers["content-type"] == "application/pdf"
    assert "v2.pdf" in r.headers["content-disposition"]
    r = api.get(f"/api/anexos/{oficio_anexo['id']}/download", params={"bruto": True}, headers=ana)
    assert r.content == PDF + b"v2"
    assert r.headers["content-type"] == "application/octet-stream"

    # Outro cliente não vê nem envia
    assert api.get(f"/api/anexos/{oficio_anexo['id']}/download", headers=bruno).status_code == 404
    assert api.delete(f"/api/anexos/{oficio_anexo['id']}", headers=bruno).status_code == 404
    assert api.post(f"{url}/OFICIO", files={"arquivo": ("x.pdf", PDF)}, headers=bruno).status_code == 404

    # Validações
    assert api.post(f"{url}/OFICIO", files={"arquivo": ("x.exe", b"MZ")}, headers=ana).status_code == 415
    grande = b"0" * (1024 * 1024 + 1)
    assert api.post(f"{url}/OFICIO", files={"arquivo": ("g.pdf", grande)}, headers=ana).status_code == 413
    assert api.post(f"{url}/OUTRO", files={"arquivo": ("x.pdf", PDF)}, headers=ana).status_code == 422
    assert len(list(storage.rglob("*.*"))) == 3  # uploads recusados não deixam lixo

    # Dono remove o próprio anexo (vai para a lixeira); admin exclui o ofício e todos os arquivos somem,
    # inclusive os da lixeira
    referencia = next(a for a in anexos if a["tipo"] == "REFERENCIA")
    assert api.delete(f"/api/anexos/{referencia['id']}", headers=ana).status_code == 204
    assert len(api.get("/api/lixeira", headers=admin).json()) == 2
    assert api.delete(f"/api/oficios/{oid}", headers=admin).status_code == 204
    assert list(storage.rglob("*.*")) == []
    assert api.get("/api/lixeira", headers=admin).json() == []
