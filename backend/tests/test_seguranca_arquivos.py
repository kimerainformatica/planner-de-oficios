"""Lixeira de anexos, verificação dos arquivos, tipos cadastráveis, limite de login, sessões e setores."""

from pathlib import Path

PDF = b"%PDF-1.4 lixeira"


def criar(api, quem, numero, tipo="EPIS", **extra):
    corpo = {"numero": numero, "data_oficio": "2026-08-03", "tipo": tipo, **extra}
    r = api.post("/api/oficios", json=corpo, headers=quem)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def anexar(api, quem, oid, nome, conteudo=PDF, tipo="OFICIO"):
    r = api.post(f"/api/oficios/{oid}/anexos/{tipo}", files={"arquivo": (nome, conteudo, "application/pdf")},
                 headers=quem)
    assert r.status_code == 201, r.text
    return r.json()


def login(api, usuario, senha):
    return api.post("/api/auth/login", data={"username": usuario, "password": senha})


# ---------- lixeira de anexos ----------


def test_lixeira_restaura_versao_anterior(api, admin, ana, tmp_path):
    oid = criar(api, ana, "1")
    anexar(api, ana, oid, "v1.pdf", PDF + b"1")
    anexar(api, ana, oid, "v2.pdf", PDF + b"2")  # substitui: v1 vai para a lixeira

    # Só admin vê a lixeira
    assert api.get("/api/lixeira", headers=ana).status_code == 403
    itens = api.get("/api/lixeira", params={"oficio_id": oid}, headers=admin).json()
    assert [(i["nome_original"], i["motivo"], i["oficio_numero"], i["descartado_por_nome"]) for i in itens] == [
        ("v1.pdf", "SUBSTITUIDO", "1", "Ana")]
    assert api.get(f"/api/lixeira/{itens[0]['id']}/download", headers=admin).content == PDF + b"1"

    # Restaurar troca de lugar: v1 volta ao ofício e v2 vai para a lixeira
    assert api.post(f"/api/lixeira/{itens[0]['id']}/restaurar", headers=admin).status_code == 204
    anexos = api.get(f"/api/oficios/{oid}", headers=ana).json()["anexos"]
    assert [a["nome_original"] for a in anexos] == ["v1.pdf"]
    assert api.get(f"/api/anexos/{anexos[0]['id']}/download", headers=ana).content == PDF + b"1"
    itens = api.get("/api/lixeira", headers=admin).json()
    assert [i["nome_original"] for i in itens] == ["v2.pdf"]

    # Removido pelo dono também pode voltar
    assert api.delete(f"/api/anexos/{anexos[0]['id']}", headers=ana).status_code == 204
    removido = next(i for i in api.get("/api/lixeira", headers=admin).json() if i["motivo"] == "REMOVIDO")
    assert api.post(f"/api/lixeira/{removido['id']}/restaurar", headers=admin).status_code == 204
    assert [a["nome_original"] for a in api.get(f"/api/oficios/{oid}", headers=ana).json()["anexos"]] == ["v1.pdf"]

    # Apagar de vez tira o arquivo do disco; fica registrado na auditoria
    storage = Path(tmp_path / "storage")
    antes = len(list(storage.rglob("*.*")))
    item = api.get("/api/lixeira", headers=admin).json()[0]
    assert api.delete(f"/api/lixeira/{item['id']}", headers=ana).status_code == 403
    assert api.delete(f"/api/lixeira/{item['id']}", headers=admin).status_code == 204
    assert len(list(storage.rglob("*.*"))) == antes - 1
    acoes = [a["acao"] for a in api.get("/api/auditoria", params={"oficio_id": oid}, headers=admin).json()["itens"]]
    assert "ANEXO_RESTAURADO" in acoes and "ANEXO_APAGADO" in acoes


def test_lixeira_evidencia_volta_para_o_mesmo_evento(api, admin, ana):
    oid = criar(api, ana, "2")
    r = api.patch(f"/api/oficios/{oid}/status", json={"status": "CONFIRMADO", "data_resposta": "2026-08-10"},
                  headers=ana).json()
    evento = r["historico"][-1]["id"]
    for nome in ("ev1.pdf", "ev2.pdf"):
        r = api.post(f"/api/oficios/{oid}/anexos/RESPOSTA", params={"historico_id": evento},
                     files={"arquivo": (nome, PDF, "application/pdf")}, headers=ana)
        assert r.status_code == 201
    item = api.get("/api/lixeira", headers=admin).json()[0]
    assert (item["tipo"], item["historico_id"]) == ("RESPOSTA", evento)
    assert api.post(f"/api/lixeira/{item['id']}/restaurar", headers=admin).status_code == 204
    historico = api.get(f"/api/oficios/{oid}", headers=ana).json()["historico"]
    assert next(h for h in historico if h["id"] == evento)["evidencia"]["nome_original"] == "ev1.pdf"


# ---------- verificação dos arquivos ----------


def test_verificacao_aponta_arquivo_sumido_ou_alterado(api, admin, ana, tmp_path):
    oid = criar(api, ana, "3")
    anexar(api, ana, oid, "doc.pdf")
    anexar(api, ana, oid, "ref.pdf", tipo="REFERENCIA")
    assert api.get("/api/arquivos/verificacao", headers=ana).status_code == 403
    r = api.post("/api/arquivos/verificacao", headers=admin).json()
    assert (r["arquivos"], r["problemas"], r["sem_registro"]) == (2, [], 0)

    storage = Path(tmp_path / "storage")
    doc, ref = sorted(storage.rglob("*.pdf"), key=lambda c: c.stat().st_mtime)
    doc.write_bytes(b"adulterado")
    ref.unlink()
    (storage / "sobra.pdf").write_bytes(b"x")
    r = api.post("/api/arquivos/verificacao", headers=admin).json()
    assert sorted((p["nome_original"], p["problema"], p["oficio_numero"]) for p in r["problemas"]) == [
        ("doc.pdf", "ALTERADO", "3"), ("ref.pdf", "AUSENTE", "3")]
    assert r["sem_registro"] == 1
    # A consulta devolve a última verificação sem refazer
    assert api.get("/api/arquivos/verificacao", headers=admin).json()["verificado_em"] == r["verificado_em"]


# ---------- tipos de ofício cadastráveis ----------


def test_tipos_cadastro_e_regra_de_entrega(api, admin, ana):
    tipos = api.get("/api/tipos", headers=ana).json()
    assert [t["codigo"] for t in tipos][:3] == ["SOLICITACAO_EQUIPAMENTOS", "PECAS_MANUTENCAO", "EPIS"]
    assert next(t for t in tipos if t["codigo"] == "COMUNICADOS")["exige_entrega"] is False

    # Cliente não cadastra; admin cria com código gerado a partir do nome
    assert api.post("/api/tipos", json={"nome": "Medicamentos"}, headers=ana).status_code == 403
    r = api.post("/api/tipos", json={"nome": "Peças de Reposição", "exige_entrega": False}, headers=admin)
    assert r.status_code == 201, r.text
    novo = r.json()
    assert (novo["codigo"], novo["exige_entrega"], novo["ativo"]) == ("PECAS_DE_REPOSICAO", False, True)
    assert api.post("/api/tipos", json={"nome": "peças de reposição"}, headers=admin).status_code == 409

    # Ofício do tipo novo: sem etapa de entrega, a resposta confirmada encerra
    oid = criar(api, ana, "10", tipo="PECAS_DE_REPOSICAO")
    r = api.patch(f"/api/oficios/{oid}/status", json={"status": "CONFIRMADO", "data_resposta": "2026-08-10"},
                  headers=ana).json()
    assert r["status"] == "CONFIRMADO"

    # Passar a exigir entrega leva os confirmados do tipo para a etapa de entrega, com histórico
    r = api.patch("/api/tipos/PECAS_DE_REPOSICAO", json={"exige_entrega": True}, headers=admin)
    assert r.status_code == 200 and r.json()["em_uso"] == 1
    o = api.get(f"/api/oficios/{oid}", headers=ana).json()
    assert o["status"] == "PENDENTE_RECEBIMENTO"
    assert o["historico"][-1]["observacao"] == "O tipo passou a exigir confirmação do recebimento"

    # Desativado: some do cadastro de ofícios novos, mas os existentes continuam com ele
    assert api.patch("/api/tipos/PECAS_DE_REPOSICAO", json={"ativo": False}, headers=admin).status_code == 200
    r = api.post("/api/oficios", json={"numero": "11", "data_oficio": "2026-08-03", "tipo": "PECAS_DE_REPOSICAO"},
                 headers=ana)
    assert r.status_code == 422
    assert api.patch(f"/api/oficios/{oid}", json={"observacao": "ok"}, headers=ana).status_code == 200
    assert api.post("/api/oficios", json={"numero": "12", "data_oficio": "2026-08-03", "tipo": "NAO_EXISTE"},
                    headers=ana).status_code == 422

    # Renomear não muda o código; o painel usa o nome novo
    api.patch("/api/tipos/PECAS_DE_REPOSICAO", json={"nome": "Reposição"}, headers=admin)
    grupos = api.get("/api/dashboard/analise", headers=admin).json()["por_tipo"]
    assert {"chave": "PECAS_DE_REPOSICAO", "rotulo": "Reposição"}.items() <= next(
        g for g in grupos if g["chave"] == "PECAS_DE_REPOSICAO").items()

    # Em uso não se apaga; sem uso, sim
    assert api.delete("/api/tipos/PECAS_DE_REPOSICAO", headers=admin).status_code == 409
    api.post("/api/tipos", json={"nome": "Engano"}, headers=admin)
    assert api.delete("/api/tipos/ENGANO", headers=admin).status_code == 204


# ---------- login e sessões ----------


def test_login_bloqueia_apos_5_erros(api):
    for _ in range(4):
        assert login(api, "ana", "errada").status_code == 401
    assert login(api, "ana", "senha-ana").status_code == 200  # acertar zera a contagem
    for _ in range(5):
        assert login(api, "ana", "errada").status_code == 401
    r = login(api, "ana", "senha-ana")
    assert r.status_code == 429 and "Tente de novo em 5 minutos" in r.json()["detail"]
    assert login(api, "bruno", "senha-bruno").status_code == 200  # outros logins seguem normais


def test_trocar_senha_encerra_sessoes(api, admin, ana):
    assert api.get("/api/auth/me", headers=ana).status_code == 200
    ana_id = api.get("/api/auth/me", headers=ana).json()["id"]
    api.patch(f"/api/usuarios/{ana_id}", json={"nome": "Ana Maria"}, headers=admin)
    assert api.get("/api/auth/me", headers=ana).status_code == 200  # outras alterações não derrubam
    assert api.patch(f"/api/usuarios/{ana_id}", json={"senha": "nova-senha-1"}, headers=admin).status_code == 200
    assert api.get("/api/auth/me", headers=ana).status_code == 401
    assert login(api, "ana", "nova-senha-1").status_code == 200


# ---------- sugestão de setores ----------


def test_setores_sugeridos_sem_duplicar(api, admin, ana, bruno):
    for n, setor in enumerate(["Almoxarifado", "almoxarifado ", "Almoxarifado", "CME", "Farmácia"]):
        criar(api, ana, f"s{n}", destinatario_tipo="SES", destinatario_setor=setor)
    criar(api, bruno, "b1", destinatario_tipo="SES", destinatario_setor="Compras")
    criar(api, ana, "a1", destinatario_tipo="ACQUA", destinatario_setor="Obras")

    r = api.get("/api/oficios/setores", params={"destinatario_tipo": "SES"}, headers=ana)
    assert r.json() == ["Almoxarifado", "CME", "Farmácia"]  # só os da Ana; grafia mais usada
    r = api.get("/api/oficios/setores", params={"destinatario_tipo": "SES"}, headers=admin)
    assert r.json() == ["Almoxarifado", "CME", "Compras", "Farmácia"]
