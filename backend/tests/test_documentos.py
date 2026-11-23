"""Documentos: ofícios e memorandos redigidos no app (rascunho → emissão → assinaturas → verificação).

O módulo é próprio (DOCUMENTOS) e se integra ao Planner de Ofícios quando o ofício é registrado lá."""

from io import BytesIO

import pytest
from PIL import Image

from app.database import get_db
from app.main import app
from app.models import Documento


def _usuario_id(api, master, login):
    return next(u["id"] for u in api.get("/api/usuarios", headers=master).json() if u["login"] == login)


def _liberar(api, master, login, perfil):
    """Acrescenta o módulo Documentos ao acesso que a pessoa já tem."""
    u = next(u for u in api.get("/api/usuarios", headers=master).json() if u["login"] == login)
    modulos = [{k: a[k] for k in ("modulo", "perfil", "empresa_id")} for a in u["modulos"]]
    r = api.patch(f"/api/usuarios/{u['id']}", json={"modulos": [*modulos, {"modulo": "DOCUMENTOS", "perfil": perfil}]},
                  headers=master)
    assert r.status_code == 200, r.text


@pytest.fixture(autouse=True)
def acesso_aos_documentos(api, master):
    for login in ("ana", "bruno", "paulo"):
        _liberar(api, master, login, "CLIENTE")
    _liberar(api, master, "admin", "ADMIN")


def _oficio_pronto(api, quem, **extra):
    doc = api.post("/api/documentos", json={"tipo": "OFICIO"}, headers=quem).json()
    dados = {"assunto": "Manutenção da climatização", "corpo": "Primeiro parágrafo.\n\nSegundo parágrafo.",
             "dest_nome": "Maria Exemplo", "dest_cargo": "Diretora", "oficio_tipo": "SERVICOS",
             "elaborador_cargo": "Gerente Operacional", **extra}
    r = api.patch(f"/api/documentos/{doc['id']}", json=dados, headers=quem)
    assert r.status_code == 200, r.text
    return r.json()


def _png() -> BytesIO:
    saida = BytesIO()
    Image.new("RGB", (400, 80), "teal").save(saida, format="PNG")
    saida.seek(0)
    return saida


def test_cargo_e_matricula_no_cadastro(api, master):
    r = api.post("/api/usuarios", json={"nome": "Lia", "login": "lia", "senha": "12345678", "cargo": "Coordenadora",
                                        "matricula": "4321", "modulos": [{"modulo": "OFICIOS", "perfil": "CLIENTE"}]},
                 headers=master)
    assert r.status_code == 201, r.text
    assert (r.json()["cargo"], r.json()["matricula"]) == ("Coordenadora", "4321")
    r = api.patch(f"/api/usuarios/{r.json()['id']}", json={"cargo": "", "matricula": "99"}, headers=master)
    assert (r.json()["cargo"], r.json()["matricula"]) == (None, "99")


def test_rascunho_emissao_e_cadastro_no_planner(api, ana, master):
    api.patch(f"/api/usuarios/{_usuario_id(api, master, 'ana')}", json={"cargo": "Gerente", "matricula": "1234"},
              headers=master)
    novo = api.post("/api/documentos", json={"tipo": "OFICIO"}, headers=ana).json()
    assert novo["status"] == "RASCUNHO" and novo["numero_formatado"] is None
    assert (novo["vocativo"], novo["fecho"], novo["dest_tratamento"]) == (
        "Prezado (a) Senhor (a),", "Atenciosamente,", "A/C sr. (sra.)")
    assert (novo["elaborador_nome"], novo["elaborador_cargo"], novo["elaborador_ident"]) == ("Ana", "Gerente", "1234")
    assert novo["pode_editar"] and "o assunto" in novo["pendencias"]

    r = api.post(f"/api/documentos/{novo['id']}/emitir", headers=ana)
    assert r.status_code == 422 and "o assunto" in r.json()["detail"]

    doc = _oficio_pronto(api, ana)
    assert doc["pendencias"] == []
    # o rascunho já sai em PDF (marcado como rascunho)
    pdf = api.get(f"/api/documentos/{doc['id']}/pdf", headers=ana)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    r = api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana)
    assert r.status_code == 200, r.text
    emitido = r.json()
    assert emitido["status"] == "EMITIDO" and emitido["numero_formatado"] == "001/2026"
    assert emitido["titulo"] == "Ofício nº 001/2026" and emitido["data_documento"] == "2026-10-20"
    assert len(emitido["codigo"]) == 9 and len(emitido["hash_conteudo"]) == 64
    assert not emitido["pode_editar"] and emitido["assinar_como"] == "ELABORADOR"

    # entrou no Planner como ofício da Ana, com o mesmo número, e aponta para o documento
    oficio = api.get(f"/api/oficios/{emitido['oficio_id']}", headers=ana).json()
    assert (oficio["numero"], oficio["tipo"], oficio["status"]) == ("001/2026", "SERVICOS", "PENDENTE_RESPOSTA")
    assert oficio["documento_id"] == doc["id"]

    # emitido não muda mais
    assert api.patch(f"/api/documentos/{doc['id']}", json={"assunto": "Outro"}, headers=ana).status_code == 409
    assert api.delete(f"/api/documentos/{doc['id']}", headers=ana).status_code == 409
    acoes = [a["acao"] for a in api.get("/api/auditoria", headers=master).json()["itens"]]
    assert "DOCUMENTO_EMITIDO" in acoes


def test_numeracao_continua_a_do_planner(api, ana, bruno):
    api.post("/api/oficios", json={"numero": "007/2026", "data_oficio": "2026-10-01", "tipo": "SERVICOS"},
             headers=ana)
    doc = _oficio_pronto(api, ana)
    assert api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana).json()["numero_formatado"] == "008/2026"
    # cada pessoa tem a sua sequência, como no Planner
    doc = _oficio_pronto(api, bruno)
    assert api.post(f"/api/documentos/{doc['id']}/emitir", headers=bruno).json()["numero_formatado"] == "001/2026"
    # e o memorando tem a dele
    memo = api.post("/api/documentos", json={"tipo": "MEMORANDO"}, headers=ana).json()
    assert memo["vocativo"] == "Prezado(a),"
    api.patch(f"/api/documentos/{memo['id']}", json={"assunto": "Escala", "corpo": "Texto.", "de": "Gerência",
                                                     "para": "RH", "elaborador_cargo": "Gerente"}, headers=ana)
    r = api.post(f"/api/documentos/{memo['id']}/emitir", headers=ana).json()
    assert (r["numero_formatado"], r["oficio_id"]) == ("01/2026", None)


def test_de_acordo_assinatura_eletronica_e_visibilidade(api, ana, bruno, admin, paulo, master):
    api.patch(f"/api/usuarios/{_usuario_id(api, master, 'bruno')}", json={"cargo": "Diretor", "matricula": "77"},
              headers=master)
    bruno_id = _usuario_id(api, master, "bruno")
    assert any(p["id"] == bruno_id for p in api.get("/api/documentos/assinantes", headers=ana).json())
    doc = _oficio_pronto(api, ana, validador_id=bruno_id)
    assert (doc["validador_nome"], doc["validador_cargo"], doc["validador_ident"]) == ("Bruno", "Diretor", "77")
    me = _usuario_id(api, master, "ana")
    assert api.patch(f"/api/documentos/{doc['id']}", json={"validador_id": me}, headers=ana).status_code == 400

    # rascunho: o validador já enxerga, mas não edita; quem não participa não vê
    assert api.get(f"/api/documentos/{doc['id']}", headers=bruno).status_code == 200
    assert api.patch(f"/api/documentos/{doc['id']}", json={"assunto": "x"}, headers=bruno).status_code == 403
    assert api.get(f"/api/documentos/{doc['id']}", headers=paulo).status_code == 404
    assert api.get("/api/documentos", headers=admin).json()["total"] == 1
    assert api.get("/api/documentos", headers=paulo).json()["total"] == 0

    api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana)
    assert api.get("/api/documentos/resumo", headers=bruno).json() == {"para_assinar": 1}
    pendentes = api.get("/api/documentos", params={"escopo": "assinar"}, headers=bruno).json()["itens"]
    assert [d["minha_assinatura_pendente"] for d in pendentes] == [True]

    r = api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "errada"}, headers=bruno)
    assert r.status_code == 400 and r.json()["detail"] == "Senha incorreta"
    r = api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "senha-bruno"}, headers=bruno)
    assert r.status_code == 200, r.text
    assert [(a["papel"], a["nome"], a["cargo"]) for a in r.json()["assinaturas"]] == [("VALIDADOR", "Bruno", "Diretor")]
    assert api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "senha-bruno"},
                    headers=bruno).status_code == 409
    assert api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "senha-admin"},
                    headers=admin).status_code == 409  # o admin vê, mas não assina por ninguém
    r = api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "senha-ana"}, headers=ana).json()
    assert {a["papel"] for a in r["assinaturas"]} == {"ELABORADOR", "VALIDADOR"} and r["assinar_como"] is None
    assert api.get("/api/documentos/resumo", headers=bruno).json() == {"para_assinar": 0}
    pdf = api.get(f"/api/documentos/{doc['id']}/pdf", params={"bruto": True}, headers=ana)
    assert pdf.headers["content-type"] == "application/octet-stream" and pdf.content.startswith(b"%PDF")


def test_verificacao_publica_e_integridade(api, ana):
    doc = _oficio_pronto(api, ana)
    assert api.get("/api/publico/verificar/AAAA-BBBB").status_code == 404
    emitido = api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana).json()
    codigo = emitido["codigo"]
    r = api.get(f"/api/publico/verificar/{codigo.replace('-', '').lower()}")  # sem login, sem hífen, minúsculo
    assert r.status_code == 200, r.text
    v = r.json()
    assert (v["titulo"], v["status"], v["integro"], v["elaborador_nome"]) == ("Ofício nº 001/2026", "EMITIDO", True, "Ana")
    assert "corpo" not in v  # a página pública não mostra o texto

    # alguém mexe no texto direto no banco: a verificação acusa
    db = next(app.dependency_overrides[get_db]())
    registro = db.get(Documento, doc["id"])
    registro.corpo = "Texto adulterado."
    db.commit()
    assert api.get(f"/api/publico/verificar/{codigo}").json()["integro"] is False


def test_cancelamento_e_duplicacao(api, ana, bruno, admin, master):
    doc = _oficio_pronto(api, ana, validador_id=_usuario_id(api, master, "bruno"))
    assert 'o cargo de quem dá o "De acordo"' in doc["pendencias"]  # o Bruno não tem cargo no cadastro
    doc = api.patch(f"/api/documentos/{doc['id']}", json={"validador_cargo": "Diretor"}, headers=ana).json()
    assert api.post(f"/api/documentos/{doc['id']}/cancelar", json={"motivo": "Erro no texto"},
                    headers=ana).status_code == 409  # rascunho: descarta, não cancela
    assert api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana).status_code == 200
    assert api.post(f"/api/documentos/{doc['id']}/cancelar", json={"motivo": "Erro no texto"},
                    headers=bruno).status_code == 403
    r = api.post(f"/api/documentos/{doc['id']}/cancelar", json={"motivo": "Erro no texto"}, headers=ana)
    assert r.status_code == 200 and r.json()["status"] == "CANCELADO"
    assert r.json()["cancelado_por_nome"] == "Ana"
    assert api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "senha-bruno"},
                    headers=bruno).status_code == 409
    v = api.get(f"/api/publico/verificar/{r.json()['codigo']}").json()
    assert (v["status"], v["motivo_cancelamento"]) == ("CANCELADO", "Erro no texto")

    copia = api.post(f"/api/documentos/{doc['id']}/duplicar", headers=ana)
    assert copia.status_code == 201
    c = copia.json()
    assert (c["status"], c["numero_formatado"], c["assunto"], c["validador_nome"]) == (
        "RASCUNHO", None, "Manutenção da climatização", "Bruno")
    assert api.delete(f"/api/documentos/{c['id']}", headers=ana).status_code == 204


def test_timbrado_so_o_admin_muda(api, ana, admin):
    assert api.get("/api/documentos/timbrado", headers=ana).json()["cabecalho"] is False
    arquivo = {"arquivo": ("timbre.png", _png(), "image/png")}
    assert api.put("/api/documentos/timbrado/cabecalho", files=arquivo, headers=ana).status_code == 403
    falso = {"arquivo": ("timbre.png", BytesIO(b"nao e imagem"), "image/png")}
    assert api.put("/api/documentos/timbrado/cabecalho", files=falso, headers=admin).status_code == 400
    texto = {"arquivo": ("timbre.txt", _png(), "text/plain")}
    assert api.put("/api/documentos/timbrado/cabecalho", files=texto, headers=admin).status_code == 415
    r = api.put("/api/documentos/timbrado/cabecalho", files={"arquivo": ("timbre.png", _png(), "image/png")},
                headers=admin)
    assert r.status_code == 200 and r.json()["cabecalho"] is True
    api.put("/api/documentos/timbrado/fundo", files={"arquivo": ("fundo.png", _png(), "image/png")}, headers=admin)
    assert api.get("/api/documentos/timbrado/cabecalho", headers=ana).status_code == 200
    doc = _oficio_pronto(api, ana)
    assert api.get(f"/api/documentos/{doc['id']}/pdf", headers=ana).content.startswith(b"%PDF")
    assert api.delete("/api/documentos/timbrado/fundo", headers=admin).json()["fundo"] is False


def test_so_quem_tem_o_modulo(api, tiago, marta):
    assert api.get("/api/documentos", headers=tiago).status_code == 403
    assert api.get("/api/documentos", headers=marta).status_code == 403  # usa o Planner, mas não o módulo
    assert api.get("/api/publico/verificar/AAAA-BBBB").status_code == 404  # a verificação é pública


def test_oficio_sem_registro_no_planner(api, ana):
    doc = _oficio_pronto(api, ana, registrar_no_planner=False, oficio_tipo=None)
    assert doc["registrar_no_planner"] is False and doc["pendencias"] == []  # sem Planner, o tipo não é exigido
    r = api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana).json()
    assert (r["numero_formatado"], r["oficio_id"]) == ("001/2026", None)
    assert api.get("/api/oficios", headers=ana).json()["total"] == 0


def test_redator_sem_acesso_ao_planner(api, master):
    r = api.post("/api/usuarios", headers=master, json={
        "nome": "Rita", "login": "rita", "senha": "senha-rita", "cargo": "Secretária",
        "modulos": [{"modulo": "DOCUMENTOS", "perfil": "CLIENTE"}]})
    assert r.status_code == 201, r.text
    rita = {"Authorization": "Bearer " + api.post("/api/auth/login", data={"username": "rita", "password": "senha-rita"}
                                                   ).json()["access_token"]}
    doc = api.post("/api/documentos", json={"tipo": "OFICIO"}, headers=rita).json()
    assert (doc["registrar_no_planner"], doc["usa_planner"]) == (False, False)
    assert api.patch(f"/api/documentos/{doc['id']}", json={"registrar_no_planner": True},
                     headers=rita).status_code == 400
    api.patch(f"/api/documentos/{doc['id']}", json={"assunto": "Pedido", "corpo": "Texto.", "dest_nome": "Fulano"},
              headers=rita)
    assert api.post(f"/api/documentos/{doc['id']}/emitir", headers=rita).json()["status"] == "EMITIDO"
    assert api.get("/api/oficios", headers=rita).status_code == 403  # continua sem o Planner


def test_pdf_pelo_oficio_no_planner(api, ana, bruno, master):
    doc = _oficio_pronto(api, ana)
    emitido = api.post(f"/api/documentos/{doc['id']}/emitir", headers=ana).json()
    rota = f"/api/oficios/{emitido['oficio_id']}/documento/pdf"
    assert api.get(rota, headers=ana).content.startswith(b"%PDF")
    assert api.get(rota, headers=bruno).status_code == 404  # o ofício é da Ana
    # um admin do Planner sem o módulo Documentos baixa pelo ofício
    r = api.post("/api/usuarios", headers=master, json={
        "nome": "Otto", "login": "otto", "senha": "senha-otto", "modulos": [{"modulo": "OFICIOS", "perfil": "ADMIN"}]})
    otto = {"Authorization": "Bearer " + api.post("/api/auth/login", data={"username": "otto", "password": "senha-otto"}
                                                   ).json()["access_token"]}
    assert r.status_code == 201
    assert api.get(f"/api/documentos/{doc['id']}", headers=otto).status_code == 403
    pdf = api.get(rota, params={"bruto": True}, headers=otto)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    sem_doc = api.post("/api/oficios", json={"numero": "050/2026", "data_oficio": "2026-10-01", "tipo": "SERVICOS"},
                       headers=ana).json()
    assert api.get(f"/api/oficios/{sem_doc['id']}/documento/pdf", headers=ana).status_code == 404
