"""Ofícios assinados pelo GOV.BR: o PDF emitido fica guardado e o arquivo assinado que volta é conferido.

Os certificados são de mentira, feitos na hora com a mesma estrutura (raiz → final → pessoa); pessoas e CPFs, fictícios.
"""

from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from asn1crypto import keys
from asn1crypto import x509 as asn1_x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.generic import NameObject, StreamObject
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers
from pyhanko_certvalidator.registry import SimpleCertificateStore

from app.config import get_settings
from app.main import app
from app.services.assinatura_govbr import cpf_valido, mascarar_cpf

CPF_ANA, CPF_BRUNO = "52998224725", "11144477735"


def _chave():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _nome(texto):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, texto)])


def _certificado(texto, chave, emissor=None, chave_emissor=None, ca=False, cpf=None, dias=365):
    agora = datetime.now(UTC)
    b = (x509.CertificateBuilder().subject_name(_nome(texto)).issuer_name(emissor.subject if emissor else _nome(texto))
         .public_key(chave.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(agora - timedelta(days=400)).not_valid_after(agora + timedelta(days=dias))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
         .add_extension(x509.KeyUsage(digital_signature=not ca, content_commitment=not ca, key_encipherment=False,
                                      data_encipherment=False, key_agreement=False, key_cert_sign=ca, crl_sign=ca,
                                      encipher_only=False, decipher_only=False), critical=True))
    if cpf:  # como na ICP-Brasil: nascimento (8) + CPF (11) + outros
        valor = f"01011990{cpf}{'0' * 26}".encode()
        outro = x509.OtherName(x509.ObjectIdentifier("2.16.76.1.3.1"), b"\x04" + bytes([len(valor)]) + valor)
        b = b.add_extension(x509.SubjectAlternativeName([outro]), critical=False)
    return b.sign(chave_emissor or chave, hashes.SHA256())


def _asn1(cert):
    return asn1_x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))


class Autoridade:
    """Uma cadeia de certificados (raiz e AC final) que emite certificados de pessoas."""

    def __init__(self, nome):
        self.chave_raiz, self.chave_final = _chave(), _chave()
        self.raiz = _certificado(f"Raiz {nome}", self.chave_raiz, ca=True)
        self.final = _certificado(f"AC Final {nome}", self.chave_final, self.raiz, self.chave_raiz, ca=True)

    def assinante(self, nome, cpf=None, dias=365):
        chave = _chave()
        cert = _certificado(nome, chave, self.final, self.chave_final, cpf=cpf, dias=dias)
        guardados = SimpleCertificateStore()
        guardados.register_multiple([_asn1(self.final)])
        der = chave.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
        return signers.SimpleSigner(signing_cert=_asn1(cert), signing_key=keys.PrivateKeyInfo.load(der),
                                    cert_registry=guardados)


@pytest.fixture(scope="module")
def govbr():
    return Autoridade("GOV.BR de teste")


@pytest.fixture(scope="module")
def outra():
    return Autoridade("qualquer")


@pytest.fixture(autouse=True)
def confianca(api, govbr, tmp_path):
    pasta = tmp_path / "certificados" / "govbr"
    pasta.mkdir(parents=True)
    for nome, cert in (("raiz", govbr.raiz), ("final", govbr.final)):
        (pasta / f"{nome}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    settings = app.dependency_overrides[get_settings]()
    settings.certificados_dir = tmp_path / "certificados"
    return settings


@pytest.fixture(autouse=True)
def acesso_aos_documentos(api, master):
    for u in api.get("/api/usuarios", headers=master).json():
        if u["login"] in ("ana", "bruno", "paulo"):
            modulos = [{k: a[k] for k in ("modulo", "perfil", "empresa_id")} for a in u["modulos"]]
            r = api.patch(f"/api/usuarios/{u['id']}", headers=master,
                          json={"modulos": [*modulos, {"modulo": "DOCUMENTOS", "perfil": "CLIENTE"}]})
            assert r.status_code == 200, r.text


def _id(api, master, login):
    return next(u["id"] for u in api.get("/api/usuarios", headers=master).json() if u["login"] == login)


def _emitir(api, quem, **extra):
    doc = api.post("/api/documentos", json={"tipo": "OFICIO"}, headers=quem).json()
    dados = {"assunto": "Manutenção", "corpo": "Primeiro parágrafo.", "dest_nome": "Maria Exemplo",
             "registrar_no_planner": False, "elaborador_cargo": "Gerente", **extra}
    assert api.patch(f"/api/documentos/{doc['id']}", json=dados, headers=quem).status_code == 200
    r = api.post(f"/api/documentos/{doc['id']}/emitir", headers=quem)
    assert r.status_code == 200, r.text
    return r.json()


def _pdf(api, doc, quem):
    return api.get(f"/api/documentos/{doc['id']}/pdf", headers=quem).content


def _assinar(pdf, assinante, campo="Assinatura1"):
    escritor = IncrementalPdfFileWriter(BytesIO(pdf))
    # com o carimbo visível na página, como o do portal
    fields.append_signature_field(escritor, fields.SigFieldSpec(campo, on_page=0, box=(90, 90, 300, 130)))
    return signers.sign_pdf(escritor, signers.PdfSignatureMetadata(field_name=campo), signer=assinante).getvalue()


def _enviar(api, doc, conteudo, quem):
    return api.post(f"/api/documentos/{doc['id']}/assinado", headers=quem,
                    files={"arquivo": ("oficio-assinado.pdf", BytesIO(conteudo), "application/pdf")})


def test_oficio_assinado_pelos_dois(api, ana, bruno, master, govbr):
    doc = _emitir(api, ana, validador_id=_id(api, master, "bruno"), validador_cargo="Diretor")
    assert doc["forma_assinatura"] == "GOVBR" and doc["pode_enviar_assinado"] and not doc["tem_assinado"]
    assert api.post(f"/api/documentos/{doc['id']}/assinar", json={"senha": "senha-ana"}, headers=ana).status_code == 409
    original = _pdf(api, doc, ana)
    assert original == _pdf(api, doc, ana)  # o arquivo é guardado: não muda de um download para outro

    r = _enviar(api, doc, _assinar(original, govbr.assinante("ANA")), ana)
    assert r.status_code == 200, r.text
    feito = r.json()
    assert [(a["papel"], a["forma"], a["cert_nome"]) for a in feito["assinaturas"]] == [("ELABORADOR", "GOVBR", "ANA")]
    assert feito["assinaturas"][0]["cert_emissor"] == "AC Final GOV.BR de teste"
    assert feito["tem_assinado"] and feito["pode_enviar_assinado"] and feito["assinar_como"] is None
    assert api.get("/api/documentos/resumo", headers=bruno).json()["para_assinar"] == 1

    # o De acordo é assinado em cima da versão da Ana
    com_ana = _pdf(api, doc, bruno)
    assert com_ana.startswith(original) and len(com_ana) > len(original)
    r = _enviar(api, doc, _assinar(com_ana, govbr.assinante("Bruno"), "Assinatura2"), bruno)
    assert r.status_code == 200, r.text
    assert {a["papel"] for a in r.json()["assinaturas"]} == {"ELABORADOR", "VALIDADOR"}
    assert r.json()["pode_enviar_assinado"] is False
    assert _pdf(api, doc, ana).startswith(com_ana)
    assert _enviar(api, doc, com_ana, ana).status_code == 409  # já tem todas

    v = api.get(f"/api/publico/verificar/{doc['codigo']}").json()
    assert v["integro"] and [a["forma"] for a in v["assinaturas"]] == ["GOVBR", "GOVBR"]
    acoes = [a for a in api.get("/api/auditoria", headers=master).json()["itens"] if a["acao"] == "DOCUMENTO_ASSINADO"]
    assert len(acoes) == 2 and "GOV.BR" in acoes[0]["descricao"]


def test_duas_assinaturas_num_envio_so(api, ana, master, govbr):
    doc = _emitir(api, ana, validador_nome="João da Conceição", validador_cargo="Diretor")  # pessoa sem login
    pdf = _assinar(_pdf(api, doc, ana), govbr.assinante("Ana"))
    pdf = _assinar(pdf, govbr.assinante("JOAO DA CONCEICAO"), "Assinatura2")
    r = _enviar(api, doc, pdf, ana)
    assert r.status_code == 200, r.text
    assert {a["papel"] for a in r.json()["assinaturas"]} == {"ELABORADOR", "VALIDADOR"}


def test_recusa_certificado_de_fora_vencido_ou_de_outra_pessoa(api, ana, govbr, outra):
    doc = _emitir(api, ana)
    original = _pdf(api, doc, ana)
    r = _enviar(api, doc, _assinar(original, outra.assinante("Ana")), ana)
    assert r.status_code == 422 and "não é do GOV.BR" in r.json()["detail"]
    r = _enviar(api, doc, _assinar(original, govbr.assinante("Ana", dias=-5)), ana)
    assert r.status_code == 422 and "fora da validade" in r.json()["detail"]
    r = _enviar(api, doc, _assinar(original, govbr.assinante("Fulano de Tal")), ana)
    assert r.status_code == 422 and "Fulano de Tal" in r.json()["detail"]
    assert api.get(f"/api/documentos/{doc['id']}", headers=ana).json()["assinaturas"] == []


def test_recusa_outro_arquivo_sem_assinatura_ou_estragado(api, ana, govbr):
    doc, outro = _emitir(api, ana), _emitir(api, ana)
    original = _pdf(api, doc, ana)
    r = _enviar(api, doc, _assinar(_pdf(api, outro, ana), govbr.assinante("Ana")), ana)
    assert r.status_code == 422 and "não é o PDF baixado daqui" in r.json()["detail"]
    r = _enviar(api, doc, original, ana)
    assert r.status_code == 422 and "não tem assinatura" in r.json()["detail"]
    assert _enviar(api, doc, b"isto nao e pdf", ana).status_code == 415
    assert _enviar(api, doc, original + b"\nlixo no fim", ana).status_code == 422
    assinado = bytearray(_assinar(original, govbr.assinante("Ana")))
    assert _enviar(api, doc, bytes(assinado) + b"\n%comentario", ana).status_code == 422  # mexido depois de assinar
    meio = len(original) + 200
    assinado[meio] ^= 0x01
    assert _enviar(api, doc, bytes(assinado), ana).status_code == 422
    assert api.get(f"/api/documentos/{doc['id']}", headers=ana).json()["tem_assinado"] is False


def test_recusa_conteudo_alterado_antes_de_assinar(api, ana, govbr):
    """O começo do arquivo é o original, mas uma atualização troca o conteúdo da página e só então é assinada."""
    doc = _emitir(api, ana)
    escritor = IncrementalPdfFileWriter(BytesIO(_pdf(api, doc, ana)))
    pagina = escritor.root["/Pages"]["/Kids"][0].get_object()
    pagina[NameObject("/Contents")] = escritor.add_object(StreamObject(stream_data=b"BT ET"))
    escritor.update_container(pagina)
    saida = BytesIO()
    escritor.write(saida)
    r = _enviar(api, doc, _assinar(saida.getvalue(), govbr.assinante("Ana")), ana)
    assert r.status_code == 422 and "alterado depois da emissão" in r.json()["detail"]


def test_de_acordo_precisa_partir_da_versao_mais_recente(api, ana, bruno, master, govbr):
    doc = _emitir(api, ana, validador_id=_id(api, master, "bruno"), validador_cargo="Diretor")
    original = _pdf(api, doc, ana)
    com_ana = _assinar(original, govbr.assinante("Ana"))
    assert _enviar(api, doc, com_ana, ana).status_code == 200
    r = _enviar(api, doc, _assinar(original, govbr.assinante("Bruno")), bruno)  # assinou a cópia antiga
    assert r.status_code == 422 and "versão mais recente" in r.json()["detail"]
    assert _enviar(api, doc, com_ana, ana).status_code == 422  # sem assinatura nova
    r = _enviar(api, doc, _assinar(com_ana, govbr.assinante("Ana"), "Assinatura2"), ana)
    assert r.status_code == 422 and "já assinou" in r.json()["detail"]


def test_quem_pode_enviar(api, ana, paulo, marta, govbr):
    doc = _emitir(api, ana)
    assinado = _assinar(_pdf(api, doc, ana), govbr.assinante("Ana"))
    assert _enviar(api, doc, assinado, paulo).status_code == 404  # não participa
    assert _enviar(api, doc, assinado, marta).status_code == 403  # não tem o módulo


def test_memorando_continua_com_a_assinatura_do_app(api, ana, govbr):
    memo = api.post("/api/documentos", json={"tipo": "MEMORANDO"}, headers=ana).json()
    assert memo["forma_assinatura"] == "APP"
    api.patch(f"/api/documentos/{memo['id']}", headers=ana,
              json={"assunto": "Escala", "corpo": "Texto.", "de": "Gerência", "para": "RH", "elaborador_cargo": "Gerente"})
    memo = api.post(f"/api/documentos/{memo['id']}/emitir", headers=ana).json()
    assert memo["pode_enviar_assinado"] is False
    assert _enviar(api, memo, _assinar(_pdf(api, memo, ana), govbr.assinante("Ana")), ana).status_code == 409
    r = api.post(f"/api/documentos/{memo['id']}/assinar", json={"senha": "senha-ana"}, headers=ana)
    assert r.status_code == 200 and r.json()["assinaturas"][0]["forma"] == "APP"


def test_cpf_no_cadastro_so_sai_mascarado(api, master):
    assert cpf_valido(CPF_ANA) and not cpf_valido("52998224724") and not cpf_valido("11111111111")
    ana_id = _id(api, master, "ana")
    assert api.patch(f"/api/usuarios/{ana_id}", json={"cpf": "123.456.789-00"}, headers=master).status_code == 422
    r = api.patch(f"/api/usuarios/{ana_id}", json={"cpf": "529.982.247-25"}, headers=master)
    assert r.status_code == 200 and r.json()["cpf_mascarado"] == mascarar_cpf(CPF_ANA) == "***.982.247-**"
    for resposta in (api.get("/api/usuarios", headers=master), api.get("/api/auditoria", headers=master)):
        assert CPF_ANA not in resposta.text and "529.982.247-25" not in resposta.text
    r = api.patch(f"/api/usuarios/{ana_id}", json={"nome": "Ana"}, headers=master)
    assert r.json()["cpf_mascarado"] == "***.982.247-**"  # não veio: não muda
    assert api.patch(f"/api/usuarios/{ana_id}", json={"cpf": ""}, headers=master).json()["cpf_mascarado"] is None


def test_com_cpf_no_cadastro_vale_o_cpf(api, ana, master, govbr):
    api.patch(f"/api/usuarios/{_id(api, master, 'ana')}", json={"cpf": CPF_ANA}, headers=master)
    doc = _emitir(api, ana)
    original = _pdf(api, doc, ana)
    r = _enviar(api, doc, _assinar(original, govbr.assinante("Ana", cpf=CPF_BRUNO)), ana)  # homônima
    assert r.status_code == 422
    r = _enviar(api, doc, _assinar(original, govbr.assinante("ANA MARIA DE SOUZA", cpf=CPF_ANA)), ana)
    assert r.status_code == 200, r.text
    assert r.json()["assinaturas"][0]["nome"] == "Ana" and r.json()["assinaturas"][0]["cert_nome"] == "ANA MARIA DE SOUZA"
    assert CPF_ANA not in r.text and CPF_ANA not in api.get(f"/api/publico/verificar/{doc['codigo']}").text


def test_cancelado_e_arquivo_guardado_alterado(api, ana, govbr, confianca):
    doc = _emitir(api, ana)
    assinado = _assinar(_pdf(api, doc, ana), govbr.assinante("Ana"))
    assert _enviar(api, doc, assinado, ana).status_code == 200
    guardados = list((confianca.storage_dir / "documentos").rglob("*.pdf"))
    assert len(guardados) == 2  # o da emissão continua guardado

    rota = f"/api/documentos/{doc['id']}/pdf"
    alvo = next(g for g in guardados if g.read_bytes() == assinado)
    alvo.write_bytes(assinado + b" ")  # alguém mexe no arquivo no servidor
    assert api.get(f"/api/publico/verificar/{doc['codigo']}").json()["integro"] is False
    assert api.get(rota, headers=ana).status_code == 409
    alvo.write_bytes(assinado)
    assert api.get(f"/api/publico/verificar/{doc['codigo']}").json()["integro"] is True

    api.post(f"/api/documentos/{doc['id']}/cancelar", json={"motivo": "Erro no texto"}, headers=ana)
    assert api.get(rota, headers=ana).content != assinado  # sai marcado como cancelado
    assert api.get(rota, params={"assinado": True}, headers=ana).content == assinado
    assert _enviar(api, doc, assinado, ana).status_code == 409


def test_cadeia_do_govbr_que_vai_com_o_sistema():
    """Os arquivos de certificados/govbr são os publicados pelo ITI (impressões digitais no LEIA-ME)."""
    from app.config import BASE_DIR

    esperado = {"1-raiz.pem": "163bd003bc0df2beab88174b6d5b450b6e1dc973a64b2dc2a33218544f49ef4e",
                "2-intermediaria.pem": "c96f8b6de022119717dfd2aeb6334e98036aaeb5c3818b4d84be1d267926d2e7",
                "3-final.pem": "96bb5c41859fc51d88f305517be641d9ef4a5d601b1bb2352e7161e97ff8b852"}
    certs = {p.name: x509.load_pem_x509_certificate(p.read_bytes())
             for p in (BASE_DIR / "certificados" / "govbr").glob("*.pem")}
    assert {n: c.fingerprint(hashes.SHA256()).hex() for n, c in certs.items()} == esperado
    certs["3-final.pem"].verify_directly_issued_by(certs["2-intermediaria.pem"])
    certs["2-intermediaria.pem"].verify_directly_issued_by(certs["1-raiz.pem"])


def test_memorando_pode_ser_assinado_pelo_govbr(api, ana, govbr):
    """A forma de assinatura é de cada documento: o modelo só sugere (o memorando sugere o app)."""
    memo = api.post("/api/documentos", json={"tipo": "MEMORANDO"}, headers=ana).json()
    r = api.patch(f"/api/documentos/{memo['id']}", headers=ana, json={
        "assunto": "Escala", "corpo": "Texto.", "de": "Gerência", "para": "RH", "elaborador_cargo": "Gerente",
        "forma_assinatura": "GOVBR"})
    assert r.json()["forma_assinatura"] == "GOVBR"
    memo = api.post(f"/api/documentos/{memo['id']}/emitir", headers=ana).json()
    assert memo["pode_enviar_assinado"] and memo["etapa"] == "AGUARDANDO"
    assert api.post(f"/api/documentos/{memo['id']}/assinar", json={"senha": "senha-ana"}, headers=ana).status_code == 409
    r = _enviar(api, memo, _assinar(_pdf(api, memo, ana), govbr.assinante("ANA")), ana)
    assert r.status_code == 200, r.text
    assert r.json()["etapa"] == "ASSINADO" and r.json()["assinaturas"][0]["forma"] == "GOVBR"
    # emitido, a forma não muda mais
    assert api.patch(f"/api/documentos/{memo['id']}", json={"forma_assinatura": "APP"}, headers=ana).status_code == 409
