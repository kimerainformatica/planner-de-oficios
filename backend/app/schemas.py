from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import Destinatario, NivelAlerta, Perfil, StatusOficio, StatusSolicitacao, TipoAnexo


class Esquema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# ---------- Usuários / autenticação ----------


class UsuarioOut(Esquema):
    id: int
    nome: str
    login: str
    perfil: Perfil
    ativo: bool


class UsuarioCriar(Esquema):
    nome: str = Field(min_length=1, max_length=120)
    login: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9._-]+$")
    senha: str = Field(min_length=8, max_length=128)
    perfil: Perfil = Perfil.CLIENTE


class UsuarioAtualizar(Esquema):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    login: str | None = Field(default=None, min_length=3, max_length=60, pattern=r"^[A-Za-z0-9._-]+$")
    senha: str | None = Field(default=None, min_length=8, max_length=128)
    perfil: Perfil | None = None
    ativo: bool | None = None


class Token(Esquema):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


# ---------- Ofícios ----------


class OficioCriar(Esquema):
    numero: str = Field(min_length=1, max_length=30)
    data_oficio: date
    tipo: str = Field(min_length=1, max_length=40, description="Código de um tipo ativo (GET /api/tipos)")
    protocolo: str | None = Field(default=None, max_length=50)
    destinatario_tipo: Destinatario | None = None
    destinatario_setor: str | None = Field(default=None, max_length=120)
    observacao: str | None = Field(default=None, max_length=5000)
    dono_id: int | None = Field(
        default=None, description="Só para admin: cadastra em nome de um cliente. Ignorado para clientes."
    )

    @field_validator("protocolo", "destinatario_setor", "observacao", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("data_oficio")
    @classmethod
    def nao_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("A data do ofício não pode estar no futuro")
        return v

    @model_validator(mode="after")
    def destinatario_completo(self):
        validar_destinatario(self.destinatario_tipo, self.destinatario_setor)
        return self


def validar_destinatario(tipo: Destinatario | None, setor: str | None) -> None:
    if tipo and not setor:
        alvo = "o destino" if tipo == Destinatario.OUTROS else "o setor"
        raise ValueError(f"Informe {alvo} do destinatário {tipo.value}")
    if setor and not tipo:
        raise ValueError("Escolha o destinatário (SES, ACQUA ou Outros)")


class OficioAtualizar(Esquema):
    """Campos omitidos não mudam. protocolo, destinatário e observação aceitam null para apagar."""

    numero: str | None = Field(default=None, min_length=1, max_length=30)
    data_oficio: date | None = None
    tipo: str | None = Field(default=None, min_length=1, max_length=40)
    protocolo: str | None = Field(default=None, max_length=50)
    destinatario_tipo: Destinatario | None = None
    destinatario_setor: str | None = Field(default=None, max_length=120)
    observacao: str | None = Field(default=None, max_length=5000)

    @field_validator("protocolo", "destinatario_setor", "observacao", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("data_oficio")
    @classmethod
    def nao_futura(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("A data do ofício não pode estar no futuro")
        return v


class StatusAlterar(Esquema):
    """CONFIRMADO em ofício com etapa de entrega vira PENDENTE_RECEBIMENTO; RECEBIDO pede data_recebimento."""

    status: StatusOficio
    data_resposta: date | None = None
    data_recebimento: date | None = None
    observacao: str | None = Field(default=None, max_length=500)


class RespostaCorrigir(Esquema):
    """Admin: corrige a resposta do ciclo atual. Campos omitidos não mudam."""

    status: StatusOficio | None = Field(default=None, description="CONFIRMADO ou NAO_CONFIRMADO")
    data_resposta: date | None = None
    observacao: str | None = Field(default=None, max_length=500)

    @field_validator("observacao", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class RecebimentoCorrigir(Esquema):
    """Admin: corrige o recebimento registrado. Campos omitidos não mudam."""

    data_recebimento: date | None = None
    observacao: str | None = Field(default=None, max_length=500)

    @field_validator("observacao", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class EtapaDesfazer(Esquema):
    motivo: str = Field(min_length=5, max_length=500)


class AnexoOut(Esquema):
    id: int
    tipo: TipoAnexo
    historico_id: int | None = None
    nome_original: str
    mime_type: str
    tamanho_bytes: int
    enviado_em: datetime


class HistoricoOut(Esquema):
    id: int
    status_anterior: StatusOficio | None
    status_novo: StatusOficio
    data_resposta: date | None
    data_recebimento: date | None = None
    observacao: str | None
    alterado_em: datetime
    usuario_nome: str | None = None
    evidencia: AnexoOut | None = None
    anulado_em: datetime | None = None
    anulado_por_nome: str | None = None
    anulado_motivo: str | None = None


class DonoOut(Esquema):
    id: int
    nome: str


class OficioOut(Esquema):
    id: int
    dono: DonoOut
    numero: str
    data_oficio: date
    tipo: str | None
    protocolo: str | None
    destinatario_tipo: Destinatario | None
    destinatario_setor: str | None
    status: StatusOficio
    inicio_prazo: date
    data_resposta: date | None
    data_recebimento: date | None = None
    observacao: str | None
    criado_em: datetime
    atualizado_em: datetime
    dias_uteis_decorridos: int = Field(description="Da etapa atual: aguardando resposta/entrega, ou até a resposta")
    dias_resposta: int | None = Field(default=None, description="Dias úteis do início do prazo até a resposta")
    dias_entrega: int | None = Field(default=None, description="Dias úteis da resposta até a entrega (recebidos)")
    nivel_alerta: NivelAlerta | None
    anexos: list[AnexoOut]


class SolicitacaoOut(Esquema):
    id: int
    oficio_id: int | None
    referencia: str
    motivo: str
    status: StatusSolicitacao
    resposta: str | None
    criado_em: datetime
    decidido_em: datetime | None
    solicitante_nome: str | None = None
    decidido_por_nome: str | None = None


class SolicitacaoCriar(Esquema):
    motivo: str = Field(min_length=5, max_length=1000)


class SolicitacaoDecidir(Esquema):
    resposta: str | None = Field(default=None, max_length=1000)


class OficioDetalhe(OficioOut):
    historico: list[HistoricoOut]
    exclusao_pendente: SolicitacaoOut | None = None


class AuditoriaOut(Esquema):
    id: int
    criado_em: datetime
    usuario_id: int | None
    usuario_nome: str | None = None
    acao: str
    descricao: str
    referencia: str | None
    oficio_id: int | None
    detalhes: dict | None


class PaginaAuditoria(Esquema):
    itens: list[AuditoriaOut]
    total: int
    pagina: int
    por_pagina: int


class PaginaOficios(Esquema):
    itens: list[OficioOut]
    total: int
    pagina: int
    por_pagina: int


class ResumoDashboard(Esquema):
    data_referencia: date
    total: int
    confirmados: int
    nao_confirmados: int
    pendentes: int
    pendentes_normal: int
    pendentes_atencao: int
    pendentes_critico: int
    pendentes_recebimento: int
    recebidos: int


# ---------- Feriados ----------


class FeriadoCriar(Esquema):
    data: date
    descricao: str = Field(min_length=1, max_length=120)


class FeriadoOut(FeriadoCriar):
    id: int


# ---------- Filtros e análise (lista, painel e exportações usam os mesmos filtros) ----------


class FiltrosConsulta(BaseModel):
    status: StatusOficio | None = None
    alerta: NivelAlerta | None = None
    busca: str | None = Field(default=None, max_length=80, description="Número, protocolo, setor/destino ou observação")
    dono_id: int | None = Field(default=None, description="Admin: só os ofícios de um cliente")
    tipo: str | None = Field(default=None, max_length=40)
    destinatario_tipo: Destinatario | None = None
    data_inicio: date | None = Field(default=None, description="Data do ofício a partir de")
    data_fim: date | None = Field(default=None, description="Data do ofício até")


class Indicadores(Esquema):
    total: int
    pendentes: int
    pendentes_normal: int
    pendentes_atencao: int
    pendentes_critico: int
    pendentes_recebimento: int
    recebimento_normal: int
    recebimento_atencao: int
    recebimento_critico: int
    confirmados: int = Field(description="Status CONFIRMADO (tipos que não exigem recebimento)")
    recebidos: int
    nao_confirmados: int
    taxa_confirmacao: float | None = Field(
        description="Respostas confirmadas (inclusive as que aguardam ou já tiveram recebimento) ÷ respondidos"
    )
    tempo_medio_resposta: float | None = Field(description="Média de dias úteis até a resposta")
    respondidos_no_prazo: float | None = Field(description="Fração respondida antes do nível de atenção")
    tempo_medio_entrega: float | None = Field(description="Média de dias úteis da resposta até o recebimento")
    entregues_no_prazo: float | None = Field(description="Fração entregue antes do nível de atenção (desde a resposta)")
    concluidos: int = Field(description="Encerrados com sucesso: recebidos + confirmados sem etapa de entrega")


class Grupo(Esquema):
    chave: str | None
    rotulo: str
    total: int
    pendentes: int
    pendentes_recebimento: int
    confirmados: int
    recebidos: int
    nao_confirmados: int
    atencao: int  # pendentes de resposta ou de recebimento
    criticos: int
    tempo_medio_resposta: float | None
    tempo_medio_entrega: float | None


class Mes(Esquema):
    mes: str  # "2026-10"
    cadastrados: int
    respondidos: int
    recebidos: int


class Prazos(Esquema):
    """Dias úteis em que o ofício pendente entra em atenção e fica crítico (configuração do servidor)."""

    dias_atencao: int
    dias_critico: int


class Analise(Esquema):
    data_referencia: date
    prazos: Prazos
    indicadores: Indicadores
    por_tipo: list[Grupo]
    por_destinatario: list[Grupo]
    por_setor: list[Grupo]
    por_cliente: list[Grupo]
    por_mes: list[Mes]


class ConsultaLista(FiltrosConsulta):
    ordem: Literal["recentes", "antigos"] = "recentes"
    pagina: int = Field(default=1, ge=1)
    por_pagina: int = Field(default=20, ge=1, le=100)


class ConsultaExportacao(FiltrosConsulta):
    formato: Literal["xlsx", "pdf"]


# ---------- Tipos de ofício (cadastro dos administradores) ----------


class TipoOficioOut(Esquema):
    codigo: str
    nome: str
    nome_curto: str | None
    exige_entrega: bool
    ativo: bool
    ordem: int
    em_uso: int = Field(default=0, description="Quantos ofícios usam o tipo")


class TipoOficioCriar(Esquema):
    nome: str = Field(min_length=2, max_length=80)
    nome_curto: str | None = Field(default=None, max_length=40)
    exige_entrega: bool = True

    @field_validator("nome_curto", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class TipoOficioAtualizar(Esquema):
    """Campos omitidos não mudam; nome_curto aceita null para apagar."""

    nome: str | None = Field(default=None, min_length=2, max_length=80)
    nome_curto: str | None = Field(default=None, max_length=40)
    exige_entrega: bool | None = None
    ativo: bool | None = None
    ordem: int | None = Field(default=None, ge=0, le=999)

    @field_validator("nome_curto", mode="before")
    @classmethod
    def vazio_vira_nulo(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


# ---------- Lixeira de anexos e verificação dos arquivos ----------


class AnexoLixeiraOut(Esquema):
    id: int
    oficio_id: int
    oficio_numero: str = ""
    tipo: TipoAnexo
    historico_id: int | None
    nome_original: str
    mime_type: str
    tamanho_bytes: int
    enviado_em: datetime
    motivo: Literal["SUBSTITUIDO", "REMOVIDO"]
    descartado_em: datetime
    descartado_por_nome: str | None = None


class ProblemaArquivo(Esquema):
    origem: Literal["anexo", "lixeira"]
    id: int
    oficio_id: int
    oficio_numero: str
    nome_original: str
    problema: Literal["AUSENTE", "ALTERADO"]


class VerificacaoArquivos(Esquema):
    verificado_em: datetime
    arquivos: int = Field(description="Arquivos conferidos (anexos + lixeira)")
    problemas: list[ProblemaArquivo]
    sem_registro: int = Field(description="Arquivos na pasta que nenhum anexo usa (sobras; não são apagados)")
