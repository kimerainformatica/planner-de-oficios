"""Esquemas dos documentos (redigidos no app a partir dos modelos da instituição), dos modelos e das pastas."""

from datetime import date, datetime

from pydantic import Field

from app.models import (
    AlertaPrazo,
    Destinatario,
    EstruturaDocumento,
    EtapaDocumento,
    FormaAssinatura,
    PapelAssinatura,
    StatusDocumento,
)
from app.schemas import Esquema


class Assinante(Esquema):
    """Quem pode dar o "De acordo" (usuários ativos do módulo Documentos)."""

    id: int
    nome: str
    cargo: str | None = None
    matricula: str | None = None


class AssinaturaOut(Esquema):
    papel: PapelAssinatura
    nome: str
    cargo: str | None
    assinado_em: datetime
    forma: FormaAssinatura = FormaAssinatura.APP
    cert_nome: str | None = None  # GOV.BR: nome no certificado
    cert_emissor: str | None = None


class DocumentoResumo(Esquema):
    id: int
    tipo: str  # código do modelo
    tipo_nome: str
    status: StatusDocumento
    etapa: EtapaDocumento
    titulo: str
    numero_formatado: str | None
    assunto: str
    destino: str | None  # destinatário (modelos externos) ou o "Para" (internos)
    elaborador_nome: str
    validador_nome: str | None
    data_documento: date | None
    atualizado_em: datetime
    forma_assinatura: FormaAssinatura
    assinaturas: int
    assinaturas_previstas: int
    minha_assinatura_pendente: bool
    pasta_id: int | None = None
    pasta_nome: str | None = None
    prazo: date | None = None
    alerta_prazo: AlertaPrazo | None = None  # só o documento em aberto (nem concluído nem cancelado)
    dias_prazo: int | None = None  # dias até o prazo; negativo: atrasado
    concluido_em: datetime | None = None


class PaginaDocumentos(Esquema):
    itens: list[DocumentoResumo]
    total: int
    pagina: int
    por_pagina: int


class ModeloResumo(Esquema):
    """O que a tela do documento precisa saber do formato (o da emissão ou, no rascunho, o do modelo hoje)."""

    nome: str
    estrutura: EstruturaDocumento
    recuo_cm: float
    mostrar_assunto: bool
    data_no_fim: bool
    rotulo_ident: str
    marcacao: bool = True


class DocumentoOut(Esquema):
    id: int
    tipo: str  # código do modelo
    tipo_nome: str
    modelo: ModeloResumo
    integra_planner: bool = False  # o modelo é o ofício: pode ser registrado no Planner de Ofícios
    status: StatusDocumento
    etapa: EtapaDocumento
    titulo: str
    numero_formatado: str | None
    data_documento: date | None
    autor_id: int
    assunto: str
    vocativo: str
    corpo: str
    fecho: str
    dest_tratamento: str | None
    dest_nome: str | None
    dest_cargo: str | None
    dest_endereco: str | None
    de: str | None
    para: str | None
    registrar_no_planner: bool
    oficio_tipo: str | None
    destinatario_tipo: Destinatario | None
    destinatario_setor: str | None
    oficio_id: int | None
    usa_planner: bool = False  # quem elaborou tem acesso ao Planner (pode registrar o ofício lá)
    elaborador_nome: str
    elaborador_cargo: str | None
    elaborador_ident: str | None
    validador_id: int | None
    validador_nome: str | None
    validador_cargo: str | None
    validador_ident: str | None
    codigo: str | None
    hash_conteudo: str | None
    forma_assinatura: FormaAssinatura
    emitido_em: datetime | None
    cancelado_em: datetime | None
    cancelado_por_nome: str | None = None
    motivo_cancelamento: str | None
    criado_em: datetime
    atualizado_em: datetime
    assinaturas: list[AssinaturaOut]
    pasta_id: int | None
    pasta_nome: str | None = None
    prazo: date | None
    alerta_prazo: AlertaPrazo | None = None
    dias_prazo: int | None = None
    concluido_em: datetime | None
    concluido_por_nome: str | None = None
    # O que quem está vendo pode fazer
    pode_editar: bool = False
    pode_cancelar: bool = False
    pode_organizar: bool = False  # pasta e prazo (quem elaborou ou o administrador)
    pode_concluir: bool = False
    pode_reabrir: bool = False
    assinar_como: PapelAssinatura | None = None  # assinatura de quem está vendo que ainda falta
    pode_enviar_assinado: bool = False  # GOV.BR: pode enviar o PDF assinado
    tem_assinado: bool = False  # GOV.BR: já há um PDF assinado guardado
    pendencias: list[str] = []  # o que falta para emitir (rascunho)


class DocumentoCriar(Esquema):
    tipo: str = Field(min_length=1, max_length=40, description="Código do modelo (ex.: OFICIO, MEMORANDO)")
    pasta_id: int | None = None
    prazo: date | None = None


class DocumentoAtualizar(Esquema):
    """Campos omitidos não mudam. Os opcionais aceitam null (ou texto vazio) para apagar."""

    assunto: str | None = Field(default=None, max_length=300)
    vocativo: str | None = Field(default=None, max_length=160)
    corpo: str | None = Field(default=None, max_length=30000)
    fecho: str | None = Field(default=None, max_length=120)
    dest_tratamento: str | None = Field(default=None, max_length=60)
    dest_nome: str | None = Field(default=None, max_length=160)
    dest_cargo: str | None = Field(default=None, max_length=160)
    dest_endereco: str | None = Field(default=None, max_length=300)
    de: str | None = Field(default=None, max_length=160)
    para: str | None = Field(default=None, max_length=160)
    registrar_no_planner: bool | None = Field(default=None, description="Ofício: cadastrar no Planner ao emitir")
    forma_assinatura: FormaAssinatura | None = Field(default=None, description="App (senha) ou GOV.BR")
    oficio_tipo: str | None = Field(default=None, max_length=40)
    destinatario_tipo: Destinatario | None = None
    destinatario_setor: str | None = Field(default=None, max_length=120)
    elaborador_cargo: str | None = Field(default=None, max_length=120)
    elaborador_ident: str | None = Field(default=None, max_length=30)
    validador_id: int | None = Field(default=None, description="Usuário do De acordo (preenche nome, cargo e ID)")
    validador_nome: str | None = Field(default=None, max_length=120)
    validador_cargo: str | None = Field(default=None, max_length=120)
    validador_ident: str | None = Field(default=None, max_length=30)


class Assinar(Esquema):
    senha: str = Field(min_length=1, max_length=128, description="Senha de quem assina, confirmada na hora")


class Cancelar(Esquema):
    motivo: str = Field(min_length=5, max_length=500)


class Organizar(Esquema):
    """Pasta e prazo (omitidos não mudam; null tira). Valem em qualquer etapa e não mexem no conteúdo."""

    pasta_id: int | None = None
    prazo: date | None = None


class ColunaQuadro(Esquema):
    etapa: EtapaDocumento
    total: int
    itens: list[DocumentoResumo]  # os primeiros (por prazo, depois os mais recentes)


class Quadro(Esquema):
    colunas: list[ColunaQuadro]


# ---------- modelos de documento ----------


class ModeloEntrada(Esquema):
    nome: str = Field(min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=300)
    estrutura: EstruturaDocumento
    digitos: int = Field(default=2, ge=2, le=4, description="Algarismos do número (2: 01/2026, 3: 001/2026)")
    recuo_cm: float = Field(default=1.25, ge=0, le=5, description="Recuo da 1ª linha do parágrafo")
    forma_assinatura: FormaAssinatura = FormaAssinatura.APP
    mostrar_assunto: bool = True
    data_no_fim: bool = False
    rotulo_ident: str = Field(default="Matrícula", max_length=30)
    vocativo: str = Field(default="", max_length=160)
    fecho: str = Field(default="Atenciosamente,", max_length=120)
    texto_modelo: str = Field(default="", max_length=30000)
    ativo: bool = True


class ModeloAtualizar(Esquema):
    """Campos omitidos não mudam. No ofício e no memorando a estrutura e a numeração ficam como estão."""

    nome: str | None = Field(default=None, min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=300)
    estrutura: EstruturaDocumento | None = None
    digitos: int | None = Field(default=None, ge=2, le=4)
    recuo_cm: float | None = Field(default=None, ge=0, le=5)
    forma_assinatura: FormaAssinatura | None = None
    mostrar_assunto: bool | None = None
    data_no_fim: bool | None = None
    rotulo_ident: str | None = Field(default=None, max_length=30)
    vocativo: str | None = Field(default=None, max_length=160)
    fecho: str | None = Field(default=None, max_length=120)
    texto_modelo: str | None = Field(default=None, max_length=30000)
    ativo: bool | None = None


class ModeloOut(Esquema):
    codigo: str
    nome: str
    descricao: str | None
    estrutura: EstruturaDocumento
    digitos: int
    recuo_cm: float
    forma_assinatura: FormaAssinatura
    mostrar_assunto: bool
    data_no_fim: bool
    rotulo_ident: str
    vocativo: str
    fecho: str
    texto_modelo: str
    sistema: bool
    ativo: bool
    em_uso: int = 0  # documentos feitos com o modelo (só para o administrador)


# ---------- pastas ----------


class PastaEntrada(Esquema):
    nome: str = Field(min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=200)


class PastaAtualizar(Esquema):
    nome: str | None = Field(default=None, min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=200)
    ativo: bool | None = None


class PastaOut(Esquema):
    id: int
    nome: str
    descricao: str | None
    ativo: bool
    documentos: int = 0  # documentos da pasta que quem consulta vê


class TimbradoOut(Esquema):
    cabecalho: bool
    fundo: bool
    cidade: str
    uf: str


class Verificacao(Esquema):
    """Página pública de verificação: só o necessário para conferir o documento."""

    codigo: str
    tipo: str
    titulo: str
    status: StatusDocumento
    data_documento: date | None
    assunto: str
    elaborador_nome: str
    validador_nome: str | None
    emitido_em: datetime | None
    forma_assinatura: FormaAssinatura
    assinaturas: list[AssinaturaOut]
    integro: bool  # o conteúdo no banco ainda é o mesmo da emissão
    hash_conteudo: str | None
    cancelado_em: datetime | None
    motivo_cancelamento: str | None
    unidade: str | None
