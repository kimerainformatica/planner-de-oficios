"""Modelos de documento da instituição: os que vêm com o sistema, o formato copiado na emissão e as validações."""

import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import TIPO_MEMORANDO, TIPO_OFICIO, EstruturaDocumento, FormaAssinatura, ModeloDocumento

# O que define a aparência do documento. Na emissão vai para `Documento.formato` (com `marcacao`).
CAMPOS_FORMATO = ("nome", "estrutura", "digitos", "recuo_cm", "mostrar_assunto", "data_no_fim", "rotulo_ident")

# Os mesmos que a migração 0020 cadastra (a instalação nova e os testes usam estes).
MODELOS_INICIAIS = [
    {
        "codigo": TIPO_OFICIO, "nome": "Ofício", "estrutura": EstruturaDocumento.EXTERNO, "digitos": 3,
        "descricao": "Comunicação externa da unidade, com destinatário por extenso. Pode ser registrado no Planner "
                     "de Ofícios na emissão.",
        "recuo_cm": 1.75, "forma_assinatura": FormaAssinatura.GOVBR, "mostrar_assunto": True, "data_no_fim": False,
        "rotulo_ident": "ID: nº", "vocativo": "Prezado (a) Senhor (a),", "fecho": "Atenciosamente,",
        "texto_modelo": "", "sistema": True, "ativo": True,
    },
    {
        "codigo": TIPO_MEMORANDO, "nome": "Memorando", "estrutura": EstruturaDocumento.INTERNO, "digitos": 2,
        "descricao": "Comunicação interna entre setores (De / Para).",
        "recuo_cm": 1.25, "forma_assinatura": FormaAssinatura.APP, "mostrar_assunto": True, "data_no_fim": False,
        "rotulo_ident": "Matrícula", "vocativo": "Prezado(a),", "fecho": "Atenciosamente,",
        "texto_modelo": "", "sistema": True, "ativo": True,
    },
]


def semear(db: Session) -> None:
    """Cadastra o ofício e o memorando se ainda não existirem (instalação nova e testes)."""
    for dados in MODELOS_INICIAIS:
        if db.get(ModeloDocumento, dados["codigo"]) is None:
            db.add(ModeloDocumento(**dados))
    db.commit()


def formato(modelo: ModeloDocumento) -> dict:
    """O formato do modelo hoje, como vai para o documento na emissão.

    `marcacao`: linhas do texto que começam com "# " viram títulos de seção e com "- ", itens de lista (os documentos
    emitidos antes da 2.4 ficam sem marcação, como eram)."""
    valores = {campo: getattr(modelo, campo) for campo in CAMPOS_FORMATO}
    valores["estrutura"] = EstruturaDocumento(valores["estrutura"]).value
    valores["recuo_cm"] = float(valores["recuo_cm"])
    return {**valores, "marcacao": True}


def gerar_codigo(db: Session, nome: str) -> str:
    """"Declaração de Comparecimento" -> "DECLARACAO_DE_COMPARECIMENTO" (com sufixo se já existir)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Z0-9]+", "_", sem_acento.upper()).strip("_")[:34] or "MODELO"
    codigo, n = base, 2
    while db.get(ModeloDocumento, codigo) is not None:
        codigo, n = f"{base}_{n}", n + 1
    return codigo


def para_novo_documento(db: Session, codigo: str) -> ModeloDocumento:
    """O modelo de um documento novo: precisa existir e estar ativo."""
    modelo = db.get(ModeloDocumento, codigo)
    if modelo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Modelo de documento desconhecido: {codigo}")
    if not modelo.ativo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"O modelo {modelo.nome} está desativado: peça ao administrador para reativar")
    return modelo
