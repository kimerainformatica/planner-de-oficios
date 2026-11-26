"""Planner de documentos (2.4): modelos da instituição, pastas, prazos com alerta, etapas e quadro."""

from datetime import date, timedelta

import pytest
from reportlab.platypus import KeepTogether, Paragraph, Table

from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import Documento
from app.services import documentos as regras

HOJE = date(2026, 10, 20)  # o "hoje" dos testes (conftest)
DECLARACAO = {
    "nome": "Declaração", "descricao": "Declarações da unidade", "estrutura": "SIMPLES", "digitos": 2,
    "recuo_cm": 1.5, "forma_assinatura": "APP", "mostrar_assunto": False, "data_no_fim": True,
    "rotulo_ident": "Matrícula", "vocativo": "", "fecho": "",
    "texto_modelo": "Declaramos, para os devidos fins, que [NOME] compareceu à unidade.\n# Observações\n- Primeiro item",
}


def _usuario_id(api, master, login):
    return next(u["id"] for u in api.get("/api/usuarios", headers=master).json() if u["login"] == login)


def _liberar(api, master, login, perfil):
    u = next(u for u in api.get("/api/usuarios", headers=master).json() if u["login"] == login)
    modulos = [{k: a[k] for k in ("modulo", "perfil", "empresa_id")} for a in u["modulos"]]
    r = api.patch(f"/api/usuarios/{u['id']}", json={"modulos": [*modulos, {"modulo": "DOCUMENTOS", "perfil": perfil}]},
                  headers=master)
    assert r.status_code == 200, r.text


@pytest.fixture(autouse=True)
def acesso_aos_documentos(api, master):
    for login in ("ana", "bruno"):
        _liberar(api, master, login, "CLIENTE")
    _liberar(api, master, "admin", "ADMIN")


def _textos(historia) -> list[str]:
    """Os textos do PDF na ordem em que saem (inclusive os de dentro de tabelas e blocos)."""
    saida = []
    for item in historia:
        if isinstance(item, Paragraph):
            saida.append(item.getPlainText())
        elif isinstance(item, KeepTogether):
            saida += _textos(item._content)
        elif isinstance(item, Table):
            saida += _textos([celula for linha in item._cellvalues for celula in linha])
    return saida


def _historia(documento_id):
    sessao = app.dependency_overrides[get_db]()
    db = next(sessao)
    try:
        return _textos(regras._historia(db.get(Documento, documento_id), app.dependency_overrides[get_settings](), HOJE))
    finally:
        sessao.close()


def test_modelos_da_instalacao_e_so_o_admin_cadastra(api, ana, admin):
    modelos = api.get("/api/documentos/modelos", headers=ana).json()
    assert [(m["codigo"], m["estrutura"], m["digitos"], m["forma_assinatura"], m["sistema"]) for m in modelos] == [
        ("MEMORANDO", "INTERNO", 2, "APP", True), ("OFICIO", "EXTERNO", 3, "GOVBR", True)]

    assert api.post("/api/documentos/modelos", json=DECLARACAO, headers=ana).status_code == 403
    r = api.post("/api/documentos/modelos", json=DECLARACAO, headers=admin)
    assert r.status_code == 201, r.text
    assert (r.json()["codigo"], r.json()["sistema"], r.json()["ativo"]) == ("DECLARACAO", False, True)
    assert api.post("/api/documentos/modelos", json={**DECLARACAO, "nome": "declaração"}, headers=admin).status_code == 409

    # ofício e memorando: estrutura e numeração fixas; não se desativam nem se apagam, mas os textos mudam
    assert api.patch("/api/documentos/modelos/OFICIO", json={"digitos": 2}, headers=admin).status_code == 422
    assert api.patch("/api/documentos/modelos/OFICIO", json={"ativo": False}, headers=admin).status_code == 422
    assert api.delete("/api/documentos/modelos/MEMORANDO", headers=admin).status_code == 409
    r = api.patch("/api/documentos/modelos/MEMORANDO", json={"recuo_cm": 1.5, "fecho": "Cordialmente,"}, headers=admin)
    assert r.status_code == 200 and (r.json()["recuo_cm"], r.json()["fecho"]) == (1.5, "Cordialmente,")
    assert api.patch("/api/documentos/modelos/MEMORANDO", json={"fecho": "x"}, headers=ana).status_code == 403

    # desativado: só o administrador vê; sem uso, pode ser apagado
    api.patch("/api/documentos/modelos/DECLARACAO", json={"ativo": False}, headers=admin)
    assert "DECLARACAO" not in [m["codigo"] for m in api.get("/api/documentos/modelos", headers=ana).json()]
    assert "DECLARACAO" in [m["codigo"] for m in api.get("/api/documentos/modelos", headers=admin).json()]
    assert api.delete("/api/documentos/modelos/DECLARACAO", headers=admin).status_code == 204

    # prévia em PDF, sem salvar nada
    r = api.post("/api/documentos/modelos/previa", json=DECLARACAO, headers=admin)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert api.post("/api/documentos/modelos/previa", json=DECLARACAO, headers=ana).status_code == 403
    assert "DECLARACAO" not in [m["codigo"] for m in api.get("/api/documentos/modelos", headers=admin).json()]


def test_documento_de_um_modelo_da_instituicao(api, ana, admin):
    api.post("/api/documentos/modelos", json=DECLARACAO, headers=admin)
    doc = api.post("/api/documentos", json={"tipo": "DECLARACAO"}, headers=ana).json()
    assert (doc["tipo"], doc["tipo_nome"], doc["titulo"], doc["etapa"]) == (
        "DECLARACAO", "Declaração", "Declaração (rascunho)", "RASCUNHO")
    assert (doc["corpo"], doc["vocativo"], doc["fecho"], doc["dest_tratamento"]) == (
        DECLARACAO["texto_modelo"], "", "", None)
    assert doc["modelo"]["estrutura"] == "SIMPLES" and not doc["integra_planner"] and not doc["registrar_no_planner"]
    assert doc["pendencias"] == ["o assunto", "o cargo de quem elaborou"]  # sem destinatário nem De/Para

    rota = f"/api/documentos/{doc['id']}"
    assert api.patch(rota, json={"registrar_no_planner": True}, headers=ana).status_code == 400  # só o ofício
    r = api.patch(rota, json={"assunto": "Comparecimento", "elaborador_cargo": "Gerente"}, headers=ana)
    assert r.json()["pendencias"] == []
    textos = _historia(doc["id"])
    assert textos[0] == "DECLARAÇÃO Nº ___/2026"
    assert not any("Assunto" in t for t in textos)  # o modelo não imprime a linha do assunto
    # seção e item de lista; a data vem depois do texto, antes da assinatura
    assert textos.index("Observações") < textos.index("Primeiro item") < textos.index("20 de outubro de 2026.")
    assert textos.index("20 de outubro de 2026.") < textos.index("Ana")

    emitido = api.post(f"{rota}/emitir", headers=ana).json()
    assert (emitido["titulo"], emitido["numero_formatado"], emitido["etapa"]) == (
        "Declaração nº 01/2026", "01/2026", "AGUARDANDO")

    # o modelo muda depois: o emitido continua como saiu, o rascunho novo segue o modelo
    r = api.patch("/api/documentos/modelos/DECLARACAO", headers=admin,
                  json={"nome": "Declaração de Comparecimento", "digitos": 3, "mostrar_assunto": True})
    assert r.status_code == 200 and r.json()["em_uso"] == 1
    de_novo = api.get(rota, headers=ana).json()
    assert de_novo["titulo"] == "Declaração nº 01/2026" and de_novo["modelo"]["mostrar_assunto"] is False
    assert _historia(doc["id"])[0] == "DECLARAÇÃO Nº 01/2026"
    assert api.get(f"/api/publico/verificar/{emitido['codigo']}").json()["integro"] is True
    novo = api.post("/api/documentos", json={"tipo": "DECLARACAO"}, headers=ana).json()
    assert novo["titulo"] == "Declaração de Comparecimento (rascunho)"

    # em uso não se apaga; desativado, não se cria nem se duplica
    assert api.delete("/api/documentos/modelos/DECLARACAO", headers=admin).status_code == 409
    api.patch("/api/documentos/modelos/DECLARACAO", json={"ativo": False}, headers=admin)
    assert api.post("/api/documentos", json={"tipo": "DECLARACAO"}, headers=ana).status_code == 422
    assert api.post(f"{rota}/duplicar", headers=ana).status_code == 422
    assert api.post("/api/documentos", json={"tipo": "NAO_EXISTE"}, headers=ana).status_code == 422


def test_oficio_e_memorando_saem_como_antes(api, ana):
    oficio = api.post("/api/documentos", json={"tipo": "OFICIO"}, headers=ana).json()
    api.patch(f"/api/documentos/{oficio['id']}", headers=ana, json={
        "assunto": "Manutenção", "corpo": "Texto.", "dest_nome": "Maria Exemplo", "elaborador_cargo": "Gerente",
        "elaborador_ident": "1234", "registrar_no_planner": False})
    textos = _historia(oficio["id"])
    assert textos[:3] == ["Ofício nº ___/2026", "20 de outubro de 2026.", "A/C sr. (sra.)"]
    assert "Assunto: Manutenção" in textos and "ID: nº 1234" in textos

    memo = api.post("/api/documentos", json={"tipo": "MEMORANDO"}, headers=ana).json()
    api.patch(f"/api/documentos/{memo['id']}", headers=ana, json={
        "assunto": "Escala", "corpo": "Texto.", "de": "Gerência", "para": "RH", "elaborador_cargo": "Gerente",
        "elaborador_ident": "99"})
    textos = _historia(memo["id"])
    assert textos[:3] == ["MEMORANDO", "NÚMERO Nº: ___/2026", "20 de outubro de 2026"]
    assert textos[3:6] == ["De: Gerência", "Para: RH", "Assunto: Escala"] and "Matrícula 99" in textos


def test_marcacao_de_secoes_e_listas():
    e = regras._Estilos(1.25)
    com = [p for p in regras._corpo(e, "Texto.\n# Seção\n- item\n\n#sem espaço", marcacao=True)
           if isinstance(p, Paragraph)]
    assert [(p.style.name, p.getPlainText()) for p in com] == [
        ("paragrafo", "Texto."), ("secao", "Seção"), ("item", "item"), ("paragrafo", "#sem espaço")]
    # os emitidos antes da 2.4 continuam sem marcação, como saíram
    sem = [p for p in regras._corpo(e, "# Seção\n- item", marcacao=False) if isinstance(p, Paragraph)]
    assert [(p.style.name, p.getPlainText()) for p in sem] == [("paragrafo", "# Seção"), ("paragrafo", "- item")]


def test_pastas(api, ana, bruno, admin, master):
    assert api.post("/api/documentos/pastas", json={"nome": "RH"}, headers=ana).status_code == 403
    rh = api.post("/api/documentos/pastas", json={"nome": "Recursos Humanos", "descricao": "Pessoal"},
                  headers=admin).json()
    compras = api.post("/api/documentos/pastas", json={"nome": "Compras"}, headers=admin).json()
    assert api.post("/api/documentos/pastas", json={"nome": "compras"}, headers=admin).status_code == 409

    doc = api.post("/api/documentos", json={"tipo": "MEMORANDO", "pasta_id": rh["id"]}, headers=ana).json()
    assert (doc["pasta_id"], doc["pasta_nome"]) == (rh["id"], "Recursos Humanos")
    outro = api.post("/api/documentos", json={"tipo": "OFICIO"}, headers=ana).json()
    r = api.patch(f"/api/documentos/{outro['id']}/organizacao", json={"pasta_id": compras["id"]}, headers=ana)
    assert r.status_code == 200 and r.json()["pasta_nome"] == "Compras"

    def ids(consulta):
        return [d["id"] for d in api.get(f"/api/documentos?{consulta}", headers=ana).json()["itens"]]

    assert ids(f"pasta_id={rh['id']}") == [doc["id"]] and ids("pasta_id=0") == []
    # cada um conta só o que vê
    contagem = {p["nome"]: p["documentos"] for p in api.get("/api/documentos/pastas", headers=ana).json()}
    assert contagem == {"Compras": 1, "Recursos Humanos": 1}
    assert {p["documentos"] for p in api.get("/api/documentos/pastas", headers=bruno).json()} == {0}

    # quem dá o De acordo vê, mas só quem elaborou (ou o administrador) organiza
    api.patch(f"/api/documentos/{doc['id']}", json={"validador_id": _usuario_id(api, master, "bruno")}, headers=ana)
    assert api.patch(f"/api/documentos/{doc['id']}/organizacao", json={"prazo": None}, headers=bruno).status_code == 403
    assert api.patch(f"/api/documentos/{doc['id']}/organizacao", json={"pasta_id": compras["id"]},
                     headers=admin).status_code == 200

    # desativada: sai da escolha, mas quem já está nela fica
    api.patch(f"/api/documentos/pastas/{compras['id']}", json={"ativo": False}, headers=admin)
    assert [p["nome"] for p in api.get("/api/documentos/pastas", headers=ana).json()] == ["Recursos Humanos"]
    r = api.patch(f"/api/documentos/{outro['id']}/organizacao", json={"pasta_id": rh["id"]}, headers=ana)
    assert r.status_code == 200
    assert api.patch(f"/api/documentos/{outro['id']}/organizacao", json={"pasta_id": compras["id"]},
                     headers=ana).status_code == 422
    assert api.get(f"/api/documentos/{doc['id']}", headers=ana).json()["pasta_nome"] == "Compras"

    # apagada: os documentos ficam sem pasta
    assert api.delete(f"/api/documentos/pastas/{compras['id']}", headers=admin).status_code == 204
    assert api.get(f"/api/documentos/{doc['id']}", headers=ana).json()["pasta_id"] is None


def test_prazos_etapas_e_quadro(api, ana):
    def memorando(assunto, **organizacao):
        d = api.post("/api/documentos", json={"tipo": "MEMORANDO", **organizacao}, headers=ana).json()
        api.patch(f"/api/documentos/{d['id']}", headers=ana, json={
            "assunto": assunto, "corpo": "Texto.", "de": "Gerência", "para": "RH", "elaborador_cargo": "Gerente"})
        return d["id"]

    atrasado = memorando("Atrasado", prazo=str(HOJE - timedelta(days=1)))
    atencao = memorando("Atenção", prazo=str(HOJE + timedelta(days=3)))  # DOCUMENTOS_DIAS_ATENCAO = 3
    em_dia = memorando("Em dia", prazo=str(HOJE + timedelta(days=10)))
    sem_prazo = memorando("Sem prazo")

    def ver(documento_id):
        return api.get(f"/api/documentos/{documento_id}", headers=ana).json()

    assert (ver(atrasado)["alerta_prazo"], ver(atrasado)["dias_prazo"]) == ("ATRASADO", -1)
    assert [ver(i)["alerta_prazo"] for i in (atencao, em_dia, sem_prazo)] == ["ATENCAO", "EM_DIA", None]

    def assuntos(consulta):
        return [d["assunto"] for d in api.get(f"/api/documentos?{consulta}", headers=ana).json()["itens"]]

    assert assuntos("prazo=atrasados") == ["Atrasado"]
    assert sorted(assuntos("prazo=alerta")) == ["Atenção", "Atrasado"]
    assert assuntos("ordem=prazo") == ["Atrasado", "Atenção", "Em dia", "Sem prazo"]
    assert api.get("/api/documentos/resumo", headers=ana).json()["prazos"] == 2

    # etapas: emitido sem a assinatura eletrônica → aguardando; assinado → assinado; concluído; cancelado
    for documento_id in (atrasado, atencao, em_dia):
        assert api.post(f"/api/documentos/{documento_id}/emitir", headers=ana).status_code == 200
    api.post(f"/api/documentos/{atencao}/assinar", json={"senha": "senha-ana"}, headers=ana)
    r = api.post(f"/api/documentos/{atrasado}/concluir", headers=ana)
    assert r.status_code == 200
    assert (r.json()["etapa"], r.json()["alerta_prazo"], r.json()["concluido_por_nome"]) == ("CONCLUIDO", None, "Ana")
    assert api.post(f"/api/documentos/{atrasado}/concluir", headers=ana).status_code == 409
    assert api.post(f"/api/documentos/{sem_prazo}/concluir", headers=ana).status_code == 409  # rascunho
    api.post(f"/api/documentos/{em_dia}/cancelar", json={"motivo": "Não vale mais"}, headers=ana)
    # o concluído sai das pendências de assinatura (mesmo sem a assinatura eletrônica: pode ter sido à mão)
    assert api.get("/api/documentos/resumo", headers=ana).json()["para_assinar"] == 0
    assert assuntos("escopo=assinar") == []

    quadro = api.get("/api/documentos/quadro", headers=ana).json()
    assert {c["etapa"]: [d["assunto"] for d in c["itens"]] for c in quadro["colunas"]} == {
        "RASCUNHO": ["Sem prazo"], "AGUARDANDO": [], "ASSINADO": ["Atenção"], "CONCLUIDO": ["Atrasado"],
        "CANCELADO": ["Em dia"]}
    assert [c["total"] for c in api.get("/api/documentos/quadro?prazo=alerta", headers=ana).json()["colunas"]] == [
        0, 0, 1, 0, 0]
    assert api.get("/api/documentos/resumo", headers=ana).json()["prazos"] == 1

    # reaberto, o prazo volta a contar
    r = api.post(f"/api/documentos/{atrasado}/reabrir", headers=ana)
    assert (r.json()["etapa"], r.json()["alerta_prazo"]) == ("AGUARDANDO", "ATRASADO")
    assert api.post(f"/api/documentos/{atrasado}/reabrir", headers=ana).status_code == 409
    assert assuntos("etapa=AGUARDANDO") == ["Atrasado"]
    r = api.patch(f"/api/documentos/{atrasado}/organizacao", json={"prazo": None}, headers=ana)
    assert r.json()["prazo"] is None and r.json()["alerta_prazo"] is None
