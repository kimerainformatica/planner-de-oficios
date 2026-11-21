"""Esquemas dos documentos (ofícios e memorandos redigidos no app)."""

from datetime import date, datetime

from pydantic import Field

from app.models import Destinatario, PapelAssinatura, StatusDocumento, TipoDocumento
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


class DocumentoResumo(Esquema):
    id: int
    tipo: TipoDocumento
    status: StatusDocumento
    titulo: str
    numero_formatado: str | None
    assunto: str
    destino: str | None  # destinatário do ofício ou o "Para" do memorando
    elaborador_nome: str
    validador_nome: str | None
    data_documento: date | None
    atualizado_em: datetime
    assinaturas: int
    assinaturas_previstas: int
    minha_assinatura_pendente: bool


class PaginaDocumentos(Esquema):
    itens: list[DocumentoResumo]
    total: int
    pagina: int
    por_pagina: int


class DocumentoOut(Esquema):
    id: int
    tipo: TipoDocumento
    status: StatusDocumento
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
    emitido_em: datetime | None
    cancelado_em: datetime | None
    cancelado_por_nome: str | None = None
    motivo_cancelamento: str | None
    criado_em: datetime
    atualizado_em: datetime
    assinaturas: list[AssinaturaOut]
    # O que quem está vendo pode fazer
    pode_editar: bool = False
    pode_cancelar: bool = False
    assinar_como: PapelAssinatura | None = None
    pendencias: list[str] = []  # o que falta para emitir (rascunho)


class DocumentoCriar(Esquema):
    tipo: TipoDocumento


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


class TimbradoOut(Esquema):
    cabecalho: bool
    fundo: bool
    cidade: str
    uf: str


class Verificacao(Esquema):
    """Página pública de verificação: só o necessário para conferir o documento."""

    codigo: str
    tipo: TipoDocumento
    titulo: str
    status: StatusDocumento
    data_documento: date | None
    assunto: str
    elaborador_nome: str
    validador_nome: str | None
    emitido_em: datetime | None
    assinaturas: list[AssinaturaOut]
    integro: bool  # o conteúdo no banco ainda é o mesmo da emissão
    hash_conteudo: str | None
    cancelado_em: datetime | None
    motivo_cancelamento: str | None
    unidade: str | None
