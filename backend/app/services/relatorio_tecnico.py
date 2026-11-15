"""PDF do relatório técnico (modelo próprio do sistema), com ReportLab."""

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Chamado, RelatorioTecnico, SituacaoEquipamento

ROTULO_SITUACAO = {
    SituacaoEquipamento.OPERANDO: "Operando normalmente",
    SituacaoEquipamento.OPERANDO_COM_RESTRICAO: "Operando com restrição",
    SituacaoEquipamento.PARADO: "Parado / fora de operação",
    SituacaoEquipamento.AGUARDANDO_PECA: "Aguardando peça",
    SituacaoEquipamento.NAO_SE_APLICA: "Não se aplica",
}

PRIMARIA = colors.HexColor("#0f7c72")
SUAVE = colors.HexColor("#4f6c72")
BORDA = colors.HexColor("#d5e4e5")
FUNDO = colors.HexColor("#f5fafa")


def _dh(d: datetime | None) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if d else "—"


def _txt(v: str | None) -> str:
    """Texto livre seguro para o Paragraph (escapa < > & e mantém as quebras de linha)."""
    return escape(v or "—").replace("\n", "<br/>")


def gerar_pdf(rel: RelatorioTecnico, chamado: Chamado, unidade: str | None = None) -> bytes:
    saida = BytesIO()
    doc = SimpleDocTemplate(
        saida, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"Relatório técnico {rel.codigo}", author=rel.tecnico.nome if rel.tecnico else "",
    )
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=PRIMARIA)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, leading=12, textColor=SUAVE)
    secao = ParagraphStyle("secao", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=PRIMARIA,
                           spaceBefore=8, spaceAfter=3)
    texto = ParagraphStyle("texto", fontName="Helvetica", fontSize=9.5, leading=13)
    rotulo = ParagraphStyle("rotulo", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=SUAVE)
    valor = ParagraphStyle("valor", fontName="Helvetica", fontSize=9.5, leading=12)

    # cada célula da grade tem rótulo + valor empilhados
    def celula(r: str, v: str) -> list:
        return [Paragraph(escape(r).upper(), rotulo), Paragraph(_txt(v), valor)]

    def bloco(titulo: str, conteudo: str | None) -> KeepTogether:
        return KeepTogether([Paragraph(escape(titulo), secao), Paragraph(_txt(conteudo), texto)])

    def grade_celulas(pares: list[tuple[str, str]]) -> Table:
        linhas = [[celula(*pares[i]), celula(*pares[i + 1]) if i + 1 < len(pares) else ""]
                  for i in range(0, len(pares), 2)]
        largura = (A4[0] - 32 * mm) / 2
        t = Table(linhas, colWidths=[largura, largura])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), FUNDO),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDA),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDA),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    tecnico = rel.tecnico.nome if rel.tecnico else "—"
    conteudo = [
        Paragraph(f"Relatório Técnico {rel.codigo}", h1),
        Paragraph(f"Manutenção Clínica · Instituto ACQUA{f' · {unidade}' if unidade else ''} · Chamado {chamado.codigo}", sub),
        Spacer(1, 5 * mm),
        Paragraph("Identificação do chamado", secao),
        grade_celulas([
            ("Chamado", f"{chamado.codigo} — {chamado.titulo}"),
            ("Empresa / modalidade", rel.empresa.nome),
            ("Solicitante", chamado.solicitante.nome),
            ("Local / setor", chamado.local or "—"),
            ("Ocorrido em", _dh(chamado.ocorrido_em)),
            ("Aberto em", _dh(chamado.aberto_em)),
        ]),
        bloco("Descrição do problema (informada na abertura)", chamado.descricao),
        Paragraph("Atendimento", secao),
        grade_celulas([
            ("Técnico responsável", tecnico),
            ("Atendido em", _dh(rel.atendido_em)),
            ("Equipamento", rel.equipamento or chamado.equipamento or "—"),
            ("Patrimônio / nº de série", rel.identificacao or "—"),
            ("Situação do equipamento", ROTULO_SITUACAO[rel.situacao_equipamento]),
            ("Relatório emitido em", _dh(rel.criado_em)),
        ]),
        bloco("Diagnóstico", rel.diagnostico),
        bloco("Causa provável", rel.causa),
        bloco("Serviço executado", rel.servico_executado),
        bloco("Peças e materiais", rel.pecas),
        bloco("Recomendações", rel.recomendacoes),
        Spacer(1, 16 * mm),
    ]
    assinaturas = Table(
        [["", "", ""], [Paragraph(f"<b>{escape(tecnico)}</b><br/>Técnico · {escape(rel.empresa.nome)}", sub), "",
                        Paragraph("<b>Responsável pelo setor</b><br/>Nome e assinatura", sub)]],
        colWidths=[78 * mm, 22 * mm, 78 * mm], rowHeights=[10 * mm, None],
    )
    assinaturas.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.8, colors.black), ("LINEABOVE", (2, 1), (2, 1), 0.8, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    conteudo.append(KeepTogether([assinaturas]))

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SUAVE)
        canvas.drawString(16 * mm, 8 * mm, f"{rel.codigo} · Chamado {chamado.codigo} · gerado pelo sistema")
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(conteudo, onFirstPage=rodape, onLaterPages=rodape)
    return saida.getvalue()
