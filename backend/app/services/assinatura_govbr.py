"""Conferência dos PDFs assinados no portal GOV.BR (assinador.iti.br).

O app não assina por ninguém: a pessoa baixa o PDF emitido, assina no portal com a conta dela e envia o arquivo de
volta. Aqui se confere, sem internet:
- que é o MESMO documento: o arquivo começa com os bytes do PDF que o app guardou e o que foi acrescentado é só
  assinatura (uma alteração do conteúdo em cima do original, mesmo assinada, é recusada);
- que cada assinatura está íntegra, cobre o documento e vem de um certificado da cadeia GOV.BR dentro da validade.
Não consulta a lista de certificados revogados (o servidor pode estar sem internet): o validar.iti.gov.br consulta.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from asn1crypto import pem, x509
from pyhanko.pdf_utils import generic
from pyhanko.pdf_utils.misc import PdfError
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.diff_analysis import ModificationLevel
from pyhanko.sign.validation import KeyUsageConstraints, validate_pdf_signature
from pyhanko.sign.validation.status import SignatureCoverageLevel
from pyhanko_certvalidator import ValidationContext

OID_CPF_ICP_BRASIL = "2.16.76.1.3.1"  # nascimento (8 dígitos) + CPF (11) + outros
USO_DA_CHAVE = KeyUsageConstraints(key_usage={"digital_signature", "non_repudiation"}, match_all_key_usages=False)

ALTERADO = "O conteúdo do documento foi alterado depois da emissão. O arquivo não foi aceito."


class AssinaturaInvalida(ValueError):
    """O arquivo não pode ser aceito; a mensagem é mostrada a quem enviou."""


@dataclass(frozen=True)
class AssinaturaLida:
    nome: str
    cpf: str | None  # só os dígitos; nem todo certificado traz
    emissor: str
    serie: str
    momento: datetime | None  # hora informada na assinatura, no fuso do servidor
    impressao: str  # SHA-256 da assinatura (identifica a mesma assinatura em envios diferentes)


def normalizar_nome(nome: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.casefold().split())


def cpf_valido(cpf: str) -> bool:
    if not re.fullmatch(r"[0-9]{11}", cpf) or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d) * (n + 1 - i) for i, d in enumerate(cpf[:n]))
        if int(cpf[n]) != soma * 10 % 11 % 10:
            return False
    return True


def mascarar_cpf(cpf: str | None) -> str | None:
    """Como o validador do governo mostra: só os seis dígitos do meio."""
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**" if cpf else None


@lru_cache
def _certificados(pasta: Path) -> tuple[tuple[x509.Certificate, ...], tuple[x509.Certificate, ...]]:
    """(raízes, intermediários) dos .pem da pasta."""
    raizes, outros = [], []
    for arquivo in sorted(pasta.rglob("*.pem")):
        for _, _, der in pem.unarmor(arquivo.read_bytes(), multiple=True):
            cert = x509.Certificate.load(der)
            (raizes if cert.self_signed != "no" else outros).append(cert)
    return tuple(raizes), tuple(outros)


def _cpf_do_certificado(cert: x509.Certificate) -> str | None:
    candidatos: list[str] = []
    if cert.subject_alt_name_value is not None:
        for nome in cert.subject_alt_name_value:
            if nome.name == "other_name" and nome.chosen["type_id"].dotted == OID_CPF_ICP_BRASIL:
                valor = nome.chosen["value"].native
                texto = valor.decode("latin-1", "ignore") if isinstance(valor, bytes) else str(valor)
                candidatos.append(texto[8:19])
    assunto = cert.subject.native
    nome_comum = re.search(r":([0-9]{11})$", str(assunto.get("common_name", "")))
    if nome_comum:
        candidatos.append(nome_comum.group(1))
    candidatos.append(re.sub(r"[^0-9]", "", str(assunto.get("serial_number", ""))))
    return next((c for c in candidatos if cpf_valido(c)), None)


def _ler(embutida) -> AssinaturaLida:
    cert = embutida.signer_cert
    momento = embutida.self_reported_timestamp
    if momento is not None and momento.tzinfo is not None:
        momento = momento.astimezone().replace(tzinfo=None)
    return AssinaturaLida(
        nome=re.sub(r":[0-9]+$", "", str(cert.subject.native.get("common_name", ""))).strip()[:160],
        cpf=_cpf_do_certificado(cert), emissor=str(cert.issuer.native.get("common_name", ""))[:160],
        serie=f"{cert.serial_number:x}"[:64], momento=momento.replace(microsecond=0) if momento else None,
        impressao=hashlib.sha256(embutida.pkcs7_content).hexdigest(),
    )


# ---------- mesmo documento ----------
# O que a assinatura pode acrescentar ao catálogo do PDF; o resto tem de continuar igual
RAIZ_LIVRE = {"/Type", "/Pages", "/AcroForm", "/Perms", "/DSS", "/Extensions", "/Version", "/Metadata"}


def _resumo(obj, caminho: tuple = ()) -> str:
    """Impressão digital de um objeto do PDF com tudo o que ele usa (fontes, imagens…)."""
    if isinstance(obj, generic.IndirectObject):
        if obj.idnum in caminho:
            return f"volta:{caminho.index(obj.idnum)}"
        caminho = (*caminho, obj.idnum)
        obj = obj.get_object()
    sha = hashlib.sha256()
    if isinstance(obj, generic.DictionaryObject):
        sha.update(b"stream" if isinstance(obj, generic.StreamObject) else b"dict")
        fora = {"/Length", "/Filter", "/DecodeParms"} if isinstance(obj, generic.StreamObject) else set()
        for chave in sorted(k for k in obj if k not in fora):
            sha.update(f"{chave}={_resumo(obj.raw_get(chave), caminho)};".encode())
        if isinstance(obj, generic.StreamObject):
            sha.update(obj.data)
    elif isinstance(obj, generic.ArrayObject):
        sha.update(b"lista")
        for i in range(len(obj)):
            sha.update(_resumo(obj.raw_get(i), caminho).encode())
    else:
        sha.update(f"{type(obj).__name__}:{obj!r}".encode())
    return sha.hexdigest()


def _paginas(no, herdado: dict) -> list[tuple[dict, list]]:
    """(conteúdo, anotações) de cada página, com o que ela herda dos grupos de páginas."""
    no = no.get_object() if isinstance(no, generic.IndirectObject) else no
    proprio = {k: _resumo(no.raw_get(k)) for k in no if k not in ("/Parent", "/Kids", "/Count", "/Annots", "/Type")}
    if "/Kids" not in no:
        return [({**herdado, **proprio}, list(no["/Annots"]) if "/Annots" in no else [])]
    return [p for filho in no["/Kids"] for p in _paginas(filho, {**herdado, **proprio})]


def _tipo_do_campo(campo):
    while campo is not None:
        if "/FT" in campo:
            return campo["/FT"]
        campo = campo["/Parent"] if "/Parent" in campo else None
    return None


def _campos_so_de_assinatura(campos) -> bool:
    for campo in campos:
        campo = campo.get_object() if isinstance(campo, generic.IndirectObject) else campo
        if "/Kids" in campo and "/FT" not in campo:
            if not _campos_so_de_assinatura(campo["/Kids"]):
                return False
        elif _tipo_do_campo(campo) != "/Sig":
            return False
    return True


def _exigir_mesmo_conteudo(leitor: PdfFileReader, base: bytes) -> None:
    """Páginas, textos, fontes e imagens iguais aos da base; de novo, só campos de assinatura."""
    antes, depois = PdfFileReader(BytesIO(base), strict=False).root, leitor.root
    for chave in (set(antes) | set(depois)) - RAIZ_LIVRE:
        if chave not in antes or chave not in depois or _resumo(antes.raw_get(chave)) != _resumo(depois.raw_get(chave)):
            raise AssinaturaInvalida(ALTERADO)
    paginas = _paginas(depois.raw_get("/Pages"), {})
    if [p for p, _ in _paginas(antes.raw_get("/Pages"), {})] != [p for p, _ in paginas]:
        raise AssinaturaInvalida(ALTERADO)
    for anotacao in (a for _, anotacoes in paginas for a in anotacoes):
        anotacao = anotacao.get_object() if isinstance(anotacao, generic.IndirectObject) else anotacao
        if anotacao["/Subtype"] != "/Widget" or _tipo_do_campo(anotacao) != "/Sig" or {"/A", "/AA"} & set(anotacao):
            raise AssinaturaInvalida(ALTERADO)
    formulario = depois["/AcroForm"] if "/AcroForm" in depois else {}
    if "/XFA" in formulario or not _campos_so_de_assinatura(formulario["/Fields"] if "/Fields" in formulario else []):
        raise AssinaturaInvalida(ALTERADO)


def _conferir_assinatura(embutida, raizes, outros, ultima: bool) -> AssinaturaLida:
    lida = _ler(embutida)
    quem = lida.nome or "pessoa não identificada"
    contexto = ValidationContext(trust_roots=list(raizes), other_certs=list(outros), allow_fetching=False)
    situacao = validate_pdf_signature(embutida, contexto, key_usage_settings=USO_DA_CHAVE)
    if not (situacao.intact and situacao.valid):
        raise AssinaturaInvalida(f"A assinatura de {quem} não confere com o documento")
    if not situacao.trusted:
        raise AssinaturaInvalida(f"A assinatura de {quem} não é do GOV.BR ou o certificado está fora da validade")
    cobre = situacao.coverage >= SignatureCoverageLevel.ENTIRE_REVISION
    if ultima and situacao.coverage != SignatureCoverageLevel.ENTIRE_FILE:
        # depois da última assinatura só uma revisão de verdade, com os dados de validação dela (nunca bytes soltos)
        cobre = (cobre and situacao.modification_level <= ModificationLevel.LTA_UPDATES
                 and embutida.reader.total_revisions - 1 > embutida.signed_revision)
    if not (cobre and situacao.bottom_line):
        raise AssinaturaInvalida(f"O documento foi alterado depois da assinatura de {quem}")
    return lida


def conferir(novo: bytes, base: bytes, pasta_certificados: Path) -> list[AssinaturaLida]:
    """Assinaturas do PDF enviado, se ele for a versão guardada (`base`) mais assinaturas GOV.BR válidas."""
    if not novo.startswith(base):
        raise AssinaturaInvalida(
            "Este arquivo não é o PDF baixado daqui. Baixe de novo o documento nesta tela (a versão mais recente), "
            "assine esse arquivo no GOV.BR e envie o resultado, sem imprimir nem converter.")
    raizes, outros = _certificados(pasta_certificados)
    if not raizes:
        raise AssinaturaInvalida("O servidor está sem os certificados do GOV.BR: avise o administrador")
    try:
        leitor = PdfFileReader(BytesIO(novo), strict=False)
        if leitor.encrypted:
            raise AssinaturaInvalida("O PDF está protegido por senha")
        embutidas = leitor.embedded_regular_signatures
        if not embutidas:
            raise AssinaturaInvalida(
                "O arquivo não tem assinatura digital. Assine no portal GOV.BR e envie o PDF assinado.")
        _exigir_mesmo_conteudo(leitor, base)
        return [_conferir_assinatura(e, raizes, outros, e is embutidas[-1]) for e in embutidas]
    except AssinaturaInvalida:
        raise
    except Exception as erro:  # arquivo de fora: estrutura inesperada é sempre recusada, nunca aceita
        detalhe = "está danificado" if isinstance(erro, PdfError) else "tem uma assinatura que não foi possível ler"
        raise AssinaturaInvalida(f"O PDF {detalhe}") from erro
