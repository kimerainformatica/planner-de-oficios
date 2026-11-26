"""Documentos redigidos no app: numeração, travamento (hash), permissões, etapas, prazos e o PDF no modelo da unidade.

O PDF segue os modelos .docx da unidade (Ofício e Memorando modelo padrão), e os outros modelos da instituição
seguem o mesmo padrão, mudando só o cabeçalho (`EstruturaDocumento`), a numeração e o recuo:
- A4; margens de 3 cm nas laterais e 2,5 cm em cima e embaixo; timbrado no topo e marca-d'água em página inteira;
- cabeçalho do documento (número, data, destinatário/De-Para, assunto) e blocos de assinatura em Arial 12;
- corpo (vocativo, parágrafos e fecho) em Times New Roman 12, justificado, espaçamento 1,5, recuo na 1ª linha
  do modelo (1,75 cm no ofício, 1,25 cm no memorando);
- páginas numeradas a partir da 2ª;
- assinatura de quem elaborou e o "De acordo" de quem valida, com espaço para assinar à mão e, se houver, o
  carimbo da assinatura eletrônica feita no app.

Assinatura eletrônica: cada documento escolhe (o modelo sugere) entre o app, com a senha, e o GOV.BR. No GOV.BR o PDF
da emissão fica guardado e o arquivo assinado que volta do portal é conferido (`assinatura_govbr.py`).
"""

import hashlib
import json
import re
import secrets
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4
from xml.sax.saxutils import escape

from fastapi import HTTPException, status
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import (
    TIPO_OFICIO,
    AlertaPrazo,
    Documento,
    EstruturaDocumento,
    EtapaDocumento,
    FormaAssinatura,
    Modulo,
    Oficio,
    PapelAssinatura,
    StatusDocumento,
    Usuario,
)
from app.services import modelos_documento as modelos
from app.services.armazenamento import caminho_absoluto
from app.services.assinatura_govbr import AssinaturaLida, normalizar_nome

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
PARTES_TIMBRADO = ("cabecalho", "fundo")  # imagem do topo e marca-d'água de página inteira
EXTENSOES_TIMBRADO = (".png", ".jpg", ".jpeg")
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I: o código pode ser digitado à mão


# ---------- regras ----------


def eh_admin(usuario: Usuario) -> bool:
    """Administrador do módulo Documentos (ou o MASTER): vê todos, cancela e cuida do timbrado."""
    return usuario.eh_admin_no(Modulo.DOCUMENTOS)


def pode_ver(doc: Documento, usuario: Usuario) -> bool:
    return doc.autor_id == usuario.id or doc.validador_id == usuario.id or eh_admin(usuario)


def filtro_visiveis(usuario: Usuario):
    """Os documentos que o usuário vê (o mesmo que `pode_ver`, para as consultas)."""
    if eh_admin(usuario):
        return Documento.id.is_not(None)
    return or_(Documento.autor_id == usuario.id, Documento.validador_id == usuario.id)


def pode_organizar(doc: Documento, usuario: Usuario) -> bool:
    """Pasta, prazo e conclusão: quem elaborou ou o administrador."""
    return doc.autor_id == usuario.id or eh_admin(usuario)


def buscar(db: Session, documento_id: int, usuario: Usuario) -> Documento:
    doc = db.get(Documento, documento_id)
    if doc is None or not pode_ver(doc, usuario):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    return doc


def exigir_rascunho_do_autor(doc: Documento, usuario: Usuario) -> None:
    if doc.autor_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só quem elaborou pode alterar o rascunho")
    if doc.status != StatusDocumento.RASCUNHO:
        raise HTTPException(status.HTTP_409_CONFLICT, "O documento já foi emitido e não pode mais ser alterado")


def papel_para_assinar(doc: Documento, usuario: Usuario) -> PapelAssinatura | None:
    """O papel que o usuário ainda pode assinar neste documento (None se nenhum)."""
    if doc.status != StatusDocumento.EMITIDO:
        return None
    feitos = {a.papel for a in doc.assinaturas}
    if doc.autor_id == usuario.id and PapelAssinatura.ELABORADOR not in feitos:
        return PapelAssinatura.ELABORADOR
    if doc.validador_id == usuario.id and doc.validador_nome and PapelAssinatura.VALIDADOR not in feitos:
        return PapelAssinatura.VALIDADOR
    return None


def papeis_pendentes(doc: Documento) -> list[PapelAssinatura]:
    """As assinaturas que ainda faltam no documento emitido."""
    if doc.status != StatusDocumento.EMITIDO:
        return []
    feitos = {a.papel for a in doc.assinaturas}
    previstos = [PapelAssinatura.ELABORADOR] + ([PapelAssinatura.VALIDADOR] if doc.validador_nome else [])
    return [p for p in previstos if p not in feitos]


def pode_enviar_assinado(doc: Documento, usuario: Usuario) -> bool:
    """Quem participa (ou o administrador) envia o PDF assinado; a pessoa conferida é a do certificado, não a que envia."""
    return doc.forma_assinatura == FormaAssinatura.GOVBR and pode_ver(doc, usuario) and bool(papeis_pendentes(doc))


def papel_da_assinatura(doc: Documento, lida: AssinaturaLida) -> PapelAssinatura | None:
    """De quem é a assinatura do certificado: pelo CPF (se o certificado e o cadastro têm) ou pelo nome completo."""
    pessoas = [(PapelAssinatura.ELABORADOR, doc.elaborador_nome, doc.autor)]
    if doc.validador_nome:
        pessoas.append((PapelAssinatura.VALIDADOR, doc.validador_nome, doc.validador))
    for papel, nome, usuario in pessoas:
        if usuario is not None and usuario.cpf and lida.cpf:
            if usuario.cpf == lida.cpf:
                return papel
        elif normalizar_nome(nome) and normalizar_nome(nome) == normalizar_nome(lida.nome):
            return papel
    return None


def etapa(doc: Documento) -> EtapaDocumento:
    if doc.status == StatusDocumento.RASCUNHO:
        return EtapaDocumento.RASCUNHO
    if doc.status == StatusDocumento.CANCELADO:
        return EtapaDocumento.CANCELADO
    if doc.concluido_em is not None:
        return EtapaDocumento.CONCLUIDO
    return EtapaDocumento.AGUARDANDO if papeis_pendentes(doc) else EtapaDocumento.ASSINADO


def em_aberto(doc: Documento) -> bool:
    """O prazo conta enquanto o documento não for concluído nem cancelado (o rascunho também conta)."""
    return doc.status != StatusDocumento.CANCELADO and doc.concluido_em is None


def dias_para_o_prazo(doc: Documento, hoje: date) -> int | None:
    """Dias até o prazo (negativo: atrasado), só para o documento em aberto."""
    return (doc.prazo - hoje).days if doc.prazo is not None and em_aberto(doc) else None


def alerta_prazo(doc: Documento, hoje: date, dias_atencao: int) -> AlertaPrazo | None:
    falta = dias_para_o_prazo(doc, hoje)
    if falta is None:
        return None
    if falta < 0:
        return AlertaPrazo.ATRASADO
    return AlertaPrazo.ATENCAO if falta <= dias_atencao else AlertaPrazo.EM_DIA


def formato_de(doc: Documento) -> dict:
    """O formato que vale para o documento: o copiado na emissão ou, no rascunho, o do modelo hoje."""
    return doc.formato if doc.formato else modelos.formato(doc.modelo)


def estrutura_de(doc: Documento) -> EstruturaDocumento:
    return EstruturaDocumento(formato_de(doc)["estrutura"])


def pendencias_para_emitir(doc: Documento) -> list[str]:
    faltas = []
    if not doc.assunto.strip():
        faltas.append("o assunto")
    if not doc.corpo.strip():
        faltas.append("o texto")
    estrutura = estrutura_de(doc)
    if estrutura == EstruturaDocumento.EXTERNO and not (doc.dest_nome or "").strip():
        faltas.append("o nome do destinatário")
    if doc.tipo == TIPO_OFICIO and doc.registrar_no_planner and not doc.oficio_tipo:
        faltas.append("o tipo de ofício (para o cadastro no Planner)")
    if estrutura == EstruturaDocumento.INTERNO:
        if not (doc.de or "").strip():
            faltas.append("o setor de origem (De)")
        if not (doc.para or "").strip():
            faltas.append("o setor de destino (Para)")
    if not (doc.elaborador_cargo or "").strip():
        faltas.append("o cargo de quem elaborou")
    if doc.validador_nome and not (doc.validador_cargo or "").strip():
        faltas.append('o cargo de quem dá o "De acordo"')
    return faltas


def _numero_inicial(texto: str) -> int | None:
    m = re.match(r"\s*0*(\d{1,6})", texto or "")
    return int(m.group(1)) if m else None


def proximo_numero(db: Session, tipo: str, autor_id: int, ano: int) -> int:
    """Sequência por autor, modelo e ano. O ofício continua a numeração que o autor já usa no Planner."""
    maior = db.scalar(select(func.max(Documento.numero)).where(
        Documento.tipo == tipo, Documento.autor_id == autor_id, Documento.ano == ano)) or 0
    if tipo == TIPO_OFICIO:
        for numero in db.scalars(select(Oficio.numero).where(Oficio.dono_id == autor_id, Oficio.ano == ano)):
            maior = max(maior, _numero_inicial(numero) or 0)
    return maior + 1


def novo_codigo(db: Session) -> str:
    while True:
        bruto = "".join(secrets.choice(ALFABETO) for _ in range(8))
        codigo = f"{bruto[:4]}-{bruto[4:]}"
        if db.scalar(select(Documento.id).where(Documento.codigo == codigo)) is None:
            return codigo


def normalizar_codigo(codigo: str) -> str:
    bruto = re.sub(r"[^A-Za-z0-9]", "", codigo).upper()
    return f"{bruto[:4]}-{bruto[4:]}" if len(bruto) == 8 else bruto


def conteudo(doc: Documento) -> dict:
    """O que o documento diz. O hash disso fica gravado na emissão e é conferido na verificação."""
    campos = ["numero", "ano", "assunto", "vocativo", "corpo", "fecho", "dest_tratamento", "dest_nome", "dest_cargo",
              "dest_endereco", "de", "para", "elaborador_nome", "elaborador_cargo", "elaborador_ident",
              "validador_nome", "validador_cargo", "validador_ident"]
    valores = {c: getattr(doc, c) for c in campos}
    valores["tipo"] = doc.tipo
    valores["data_documento"] = doc.data_documento.isoformat() if doc.data_documento else None
    return valores


def calcular_hash(doc: Documento) -> str:
    texto = json.dumps(conteudo(doc), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ---------- arquivos guardados (GOV.BR) ----------


def guardar_pdf(conteudo: bytes, ano: int, settings: Settings) -> tuple[str, str]:
    """Grava um PDF novo (os anteriores nunca são trocados) e devolve o caminho relativo e o SHA-256."""
    relativo = str(PurePosixPath("documentos", str(ano), f"{uuid4().hex}.pdf"))
    destino = caminho_absoluto(relativo, settings)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    return relativo, hashlib.sha256(conteudo).hexdigest()


def _ler_guardado(relativo: str, esperado: str | None, settings: Settings) -> bytes | None:
    """O arquivo guardado, ou None se ele sumiu ou não é mais o mesmo."""
    caminho = caminho_absoluto(relativo, settings)
    if not caminho.is_file():
        return None
    conteudo = caminho.read_bytes()
    return conteudo if hashlib.sha256(conteudo).hexdigest() == esperado else None


def arquivo_vigente(doc: Documento, settings: Settings) -> bytes | None:
    """A última versão assinada ou, sem assinatura, o PDF da emissão (None se o documento não guarda arquivo)."""
    if doc.arquivo_assinado:
        conteudo = _ler_guardado(doc.arquivo_assinado, doc.arquivo_assinado_hash, settings)
    elif doc.arquivo_original:
        conteudo = _ler_guardado(doc.arquivo_original, doc.arquivo_original_hash, settings)
    else:
        return None
    if conteudo is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O arquivo guardado deste documento sumiu ou foi alterado. "
                                                      "Avise o administrador para recuperar do backup.")
    return conteudo


def arquivos_integros(doc: Documento, settings: Settings) -> bool:
    return all(
        _ler_guardado(relativo, esperado, settings) is not None
        for relativo, esperado in ((doc.arquivo_original, doc.arquivo_original_hash),
                                   (doc.arquivo_assinado, doc.arquivo_assinado_hash)) if relativo
    )


def pdf_atual(doc: Documento, settings: Settings, hoje: date, url_verificacao: str | None = None) -> bytes:
    """O PDF que vale: o guardado (GOV.BR) ou o gerado na hora. O cancelado sai sempre marcado."""
    if doc.status == StatusDocumento.EMITIDO:
        guardado = arquivo_vigente(doc, settings)
        if guardado is not None:
            return guardado
    return gerar_pdf(doc, settings, hoje, url_verificacao)


# ---------- datas ----------


def data_por_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def local_e_data(estrutura: EstruturaDocumento, d: date, settings: Settings) -> str:
    """Externo (ofício): "São Luís, 20 de novembro de 2026." Interno (memorando): "São Luís - MA, 20 de novembro de
    2026". Simples (declaração…): "São Luís - MA, 20 de novembro de 2026."."""
    cidade, uf = settings.documentos_cidade.strip(), settings.documentos_uf.strip()
    if estrutura == EstruturaDocumento.EXTERNO:
        return f"{cidade}, {data_por_extenso(d)}." if cidade else f"{data_por_extenso(d)}."
    local = f"{cidade} - {uf}" if cidade and uf else cidade
    texto = f"{local}, {data_por_extenso(d)}" if local else data_por_extenso(d)
    return f"{texto}." if estrutura == EstruturaDocumento.SIMPLES else texto


# ---------- timbrado ----------


def pasta_timbrado(settings: Settings) -> Path:
    return settings.storage_dir / "timbrado"


def arquivo_timbrado(settings: Settings, parte: str) -> Path | None:
    for ext in EXTENSOES_TIMBRADO:
        caminho = pasta_timbrado(settings) / f"{parte}{ext}"
        if caminho.is_file():
            return caminho
    return None


# ---------- PDF ----------


@lru_cache
def _fontes() -> dict[str, str]:
    """Arial e Times New Roman do sistema; sem elas, as equivalentes embutidas do PDF (Helvetica e Times)."""
    pastas = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/msttcorefonts"),
              Path("/usr/share/fonts/truetype/ms-fonts")]
    nomes = {"arial": ("arial.ttf", "arialbd.ttf"), "times": ("times.ttf", "timesbd.ttf")}
    fontes = {"arial": "Helvetica", "arial-b": "Helvetica-Bold", "times": "Times-Roman", "times-b": "Times-Bold"}
    for familia, (normal, negrito) in nomes.items():
        for pasta in pastas:
            n, b = pasta / normal, pasta / negrito
            if not (n.is_file() and b.is_file()):
                n, b = pasta / normal.capitalize(), pasta / negrito.capitalize()
            if n.is_file() and b.is_file():
                rotulo = "Arial" if familia == "arial" else "TimesNewRoman"
                pdfmetrics.registerFont(TTFont(rotulo, str(n)))
                pdfmetrics.registerFont(TTFont(f"{rotulo}-Bold", str(b)))
                pdfmetrics.registerFontFamily(rotulo, normal=rotulo, bold=f"{rotulo}-Bold", italic=rotulo,
                                              boldItalic=f"{rotulo}-Bold")
                fontes[familia], fontes[f"{familia}-b"] = rotulo, f"{rotulo}-Bold"
                break
    return fontes


def _t(texto: str | None) -> str:
    return escape(texto or "")


L, A = A4
MARGEM_LAT, MARGEM_INF = 3 * cm, 2.5 * cm


class _Estilos:
    def __init__(self, recuo_cm: float):
        f = _fontes()
        self.simples = ParagraphStyle("simples", fontName=f["arial"], fontSize=12, leading=14)
        self.cab = ParagraphStyle("cab", parent=self.simples, leading=18, alignment=TA_JUSTIFY)  # 1,5
        self.direita = ParagraphStyle("direita", parent=self.simples, alignment=TA_RIGHT)
        self.centro = ParagraphStyle("centro", parent=self.simples, alignment=TA_CENTER)
        self.centro_neg = ParagraphStyle("centro_neg", parent=self.centro, fontName=f["arial-b"])
        self.titulo = ParagraphStyle("titulo", parent=self.centro_neg, leading=18)
        self.corpo = ParagraphStyle("corpo", fontName=f["times"], fontSize=12, leading=18, alignment=TA_JUSTIFY)
        self.fecho = ParagraphStyle("fecho", parent=self.corpo, alignment=TA_LEFT)
        self.paragrafo = ParagraphStyle("paragrafo", parent=self.corpo, firstLineIndent=recuo_cm * cm)
        self.secao = ParagraphStyle("secao", parent=self.corpo, fontName=f["times-b"], alignment=TA_LEFT)
        self.item = ParagraphStyle("item", parent=self.corpo, leftIndent=recuo_cm * cm + 0.5 * cm,
                                   bulletIndent=recuo_cm * cm)
        self.carimbo = ParagraphStyle("carimbo", fontName=f["arial"], fontSize=7.5, leading=9.5, alignment=TA_CENTER,
                                      textColor=colors.HexColor("#0f5f57"))


def _bloco_assinatura(e: _Estilos, nome: str, cargo: str | None, ident: str | None, ident_rotulo: str,
                      assinatura, rotulo: str | None = None):
    """Espaço para assinar à mão; com assinatura eletrônica, o carimbo dela ocupa esse espaço."""
    bloco = []
    if rotulo:
        bloco.append(Paragraph(_t(rotulo), e.centro_neg))
    if assinatura is not None:
        texto = (f"Documento assinado eletronicamente por <b>{_t(assinatura.nome)}</b>"
                 f"{', ' + _t(assinatura.cargo) if assinatura.cargo else ''}, em "
                 f"{assinatura.assinado_em:%d/%m/%Y}, às {assinatura.assinado_em:%H:%M}.")
        carimbo = Table([[Paragraph(texto, e.carimbo)]], colWidths=[8.6 * cm], rowHeights=[1.05 * cm])
        carimbo.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#0f7c72")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2faf9")),
        ]))
        bloco += [Spacer(1, 0.2 * cm), carimbo, Spacer(1, 0.15 * cm)]
    else:
        bloco.append(Spacer(1, 1.4 * cm))
    bloco += [Paragraph("_" * 38, e.centro), Paragraph(_t(nome), e.centro_neg)]
    if cargo:
        bloco.append(Paragraph(_t(cargo), e.centro))
    if ident:
        bloco.append(Paragraph(_t(f"{ident_rotulo} {ident}".strip()), e.centro))
    return KeepTogether(bloco)


def _corpo(e: _Estilos, corpo: str, marcacao: bool) -> list:
    """Cada linha é um parágrafo. Com marcação, "# " abre um título de seção e "- " um item de lista."""
    h: list = []
    for linha in corpo.splitlines():
        texto = linha.strip()
        if not texto:
            continue
        if marcacao and texto.startswith("# ") and texto[2:].strip():
            h += [Spacer(1, 6), Paragraph(_t(texto[2:].strip()), e.secao)]
        elif marcacao and texto[:2] in ("- ", "• ") and texto[2:].strip():
            h.append(Paragraph(_t(texto[2:].strip()), e.item, bulletText="•"))
        else:
            h.append(Paragraph(_t(texto), e.paragrafo))
    return h


def _historia(doc: Documento, settings: Settings, hoje: date) -> list:
    f = formato_de(doc)
    estrutura = EstruturaDocumento(f["estrutura"])
    e = _Estilos(float(f["recuo_cm"]))
    externo = estrutura == EstruturaDocumento.EXTERNO
    data = doc.data_documento or hoje
    numero = doc.numero_formatado or f"___/{data.year}"
    quando = local_e_data(estrutura, data, settings)
    nome, data_no_topo = f["nome"], not f["data_no_fim"]
    h: list = []
    if externo:
        h += [Paragraph(f"{_t(nome)} nº {_t(numero)}", e.simples), Spacer(1, 14)]
        if data_no_topo:
            h += [Paragraph(_t(quando), e.direita), Spacer(1, 14)]
        if doc.dest_tratamento:
            h.append(Paragraph(_t(doc.dest_tratamento), e.simples))
        h.append(Paragraph(f"<b>{_t(doc.dest_nome)}</b>", e.simples))
        h += [Paragraph(_t(linha), e.simples) for linha in (doc.dest_cargo, doc.dest_endereco) if linha]
        h.append(Spacer(1, 14))
        if f["mostrar_assunto"]:
            h.append(Paragraph(f"Assunto: <b>{_t(doc.assunto)}</b>", e.cab))
        h.append(Spacer(1, 18))
    elif estrutura == EstruturaDocumento.INTERNO:
        largura = (L - 2 * MARGEM_LAT) / 2
        topo = Table([[Paragraph(f"<b>{_t(nome.upper())}</b>", e.simples),
                       Paragraph(f"<b>NÚMERO Nº: {_t(numero)}</b>", e.direita)]], colWidths=[largura, largura])
        topo.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        h += [topo, Spacer(1, 14)]
        h += [Paragraph(f"<b>{_t(quando)}</b>", e.direita), Spacer(1, 28)] if data_no_topo else [Spacer(1, 14)]
        h += [Paragraph(f"<b>De:</b> {_t(doc.de)}", e.cab), Paragraph(f"<b>Para:</b> {_t(doc.para)}", e.cab)]
        if f["mostrar_assunto"]:
            h.append(Paragraph(f"<b>Assunto:</b> {_t(doc.assunto)}", e.cab))
        h.append(Spacer(1, 18))
    else:  # simples: título centralizado, sem destinatário
        h += [Paragraph(f"{_t(nome.upper())} Nº {_t(numero)}", e.titulo), Spacer(1, 18)]
        if data_no_topo:
            h += [Paragraph(_t(quando), e.direita), Spacer(1, 18)]
        if f["mostrar_assunto"]:
            h += [Paragraph(f"<b>Assunto:</b> {_t(doc.assunto)}", e.cab), Spacer(1, 18)]
    if doc.vocativo.strip():
        h.append(Paragraph(_t(doc.vocativo), e.corpo))
        if not externo:
            h.append(Spacer(1, 18))
    h += _corpo(e, doc.corpo, bool(f.get("marcacao")))
    h.append(Spacer(1, 18 if externo else 28))
    if not data_no_topo:
        h += [Paragraph(_t(quando), e.direita), Spacer(1, 18)]
    if doc.fecho.strip():
        h += [Paragraph(_t(doc.fecho), e.fecho), Spacer(1, 0.6 * cm)]

    feitas = {a.papel: a for a in doc.assinaturas}
    rotulo_ident = f["rotulo_ident"]
    h.append(_bloco_assinatura(e, doc.elaborador_nome, doc.elaborador_cargo, doc.elaborador_ident, rotulo_ident,
                               feitas.get(PapelAssinatura.ELABORADOR)))
    if doc.validador_nome:
        h += [Spacer(1, 0.8 * cm),
              _bloco_assinatura(e, doc.validador_nome, doc.validador_cargo, doc.validador_ident, rotulo_ident,
                                feitas.get(PapelAssinatura.VALIDADOR), rotulo="De acordo" if externo else "De acordo:")]
    return h


def _desenhar_pagina(doc: Documento, settings: Settings, url_verificacao: str | None):
    cabecalho = arquivo_timbrado(settings, "cabecalho")
    fundo = arquivo_timbrado(settings, "fundo")
    f = _fontes()
    marca = {StatusDocumento.RASCUNHO: ("RASCUNHO", colors.Color(0.55, 0.55, 0.55, alpha=0.16)),
             StatusDocumento.CANCELADO: ("CANCELADO", colors.Color(0.8, 0.1, 0.1, alpha=0.16))}.get(doc.status)

    def desenhar(c, pdf):
        c.saveState()
        if fundo:
            c.drawImage(ImageReader(str(fundo)), 0, 0, width=L, height=A, mask="auto")
        if cabecalho:
            leitor = ImageReader(str(cabecalho))
            lw, lh = leitor.getSize()
            larg = min(21.96 * cm, L)
            c.drawImage(leitor, (L - larg) / 2, A - larg * lh / lw, width=larg, height=larg * lh / lw, mask="auto")
        if marca:
            c.saveState()
            c.translate(L / 2, A / 2)
            c.rotate(45)
            c.setFont(f["arial-b"], 86)
            c.setFillColor(marca[1])
            c.drawCentredString(0, -30, marca[0])
            c.restoreState()
        if pdf.page >= 2:  # regra do modelo: numerar a partir da 2ª página
            c.setFont(f["arial"], 10)
            c.drawRightString(L - MARGEM_LAT, 1.25 * cm, str(pdf.page))
        c.setFont(f["arial"], 7)
        c.setFillGray(0.4)
        if doc.status == StatusDocumento.RASCUNHO:
            c.drawString(MARGEM_LAT, 1.25 * cm, "Rascunho: sem número e sem validade.")
        elif doc.codigo:
            x = MARGEM_LAT
            if url_verificacao:
                qr = QrCodeWidget(url_verificacao, barLevel="M")
                x0, y0, x1, y1 = qr.getBounds()
                lado = 1.55 * cm
                desenho = Drawing(lado, lado, transform=[lado / (x1 - x0), 0, 0, lado / (y1 - y0), 0, 0])
                desenho.add(qr)
                renderPDF.draw(desenho, c, MARGEM_LAT - 0.15 * cm, 0.55 * cm)
                x += 1.6 * cm
            linhas = [f"Documento emitido pelo Planner de Ofícios em {doc.emitido_em:%d/%m/%Y às %H:%M}.",
                      f"Código de verificação: {doc.codigo}"]
            if url_verificacao:
                linhas.append(f"Confira a autenticidade em {url_verificacao}")
            if doc.status == StatusDocumento.CANCELADO:
                linhas.append("DOCUMENTO CANCELADO: sem validade.")
            elif doc.forma_assinatura == FormaAssinatura.GOVBR:
                linhas.append("Assinado pelo GOV.BR: confira o arquivo em https://validar.iti.gov.br")
            for i, linha in enumerate(linhas):
                c.drawString(x, 1.75 * cm - i * 0.33 * cm, linha)
        c.restoreState()

    return desenhar


def gerar_pdf(doc: Documento, settings: Settings, hoje: date, url_verificacao: str | None = None) -> bytes:
    saida = BytesIO()
    topo = 5.0 * cm if arquivo_timbrado(settings, "cabecalho") else 2.5 * cm  # o texto começa abaixo do timbre
    pdf = BaseDocTemplate(saida, pagesize=A4, title=doc.titulo, author=doc.elaborador_nome, subject=doc.assunto,
                          creator="Planner de Ofícios")
    quadro = Frame(MARGEM_LAT, MARGEM_INF, L - 2 * MARGEM_LAT, A - topo - MARGEM_INF, id="texto",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    pdf.addPageTemplates([PageTemplate(id="p", frames=[quadro],
                                       onPage=_desenhar_pagina(doc, settings, url_verificacao))])
    pdf.build(_historia(doc, settings, hoje))
    return saida.getvalue()


def url_publica(settings: Settings, base: str, codigo: str) -> str:
    """Endereço da página de verificação (o do .env, se houver; senão o endereço por onde o app foi aberto)."""
    raiz = (settings.documentos_url_publica.strip() or base).rstrip("/")
    return f"{raiz}/verificar/{codigo}"


def instante(agora: datetime) -> datetime:
    return agora.replace(microsecond=0)
