import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Perfil(str, enum.Enum):
    """MASTER: administrador geral (manda em tudo, inclusive em outros admins).
    ADMIN: vê todos os ofícios, exclui, decide pedidos de exclusão e gerencia clientes.
    CLIENTE: faz tudo nos próprios ofícios, mas a exclusão precisa ser aprovada por um admin."""

    MASTER = "MASTER"
    ADMIN = "ADMIN"
    CLIENTE = "CLIENTE"


PERFIS_ADMIN = {Perfil.MASTER, Perfil.ADMIN}


class StatusSolicitacao(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    RECUSADA = "RECUSADA"
    CANCELADA = "CANCELADA"


class StatusOficio(str, enum.Enum):
    PENDENTE_RESPOSTA = "PENDENTE_RESPOSTA"
    CONFIRMADO = "CONFIRMADO"
    NAO_CONFIRMADO = "NAO_CONFIRMADO"
    # Todos os tipos menos Comunicados: a resposta foi confirmada, falta confirmar a entrega
    PENDENTE_RECEBIMENTO = "PENDENTE_RECEBIMENTO"
    RECEBIDO = "RECEBIDO"


class TipoAnexo(str, enum.Enum):
    OFICIO = "OFICIO"
    REFERENCIA = "REFERENCIA"
    RESPOSTA = "RESPOSTA"  # evidência de uma resposta (ligada ao evento do histórico)
    RECEBIMENTO = "RECEBIMENTO"  # evidência da entrega (ligada ao evento de recebimento)


class Destinatario(str, enum.Enum):
    """SES e ACQUA levam o setor; OUTROS leva o destino por extenso (ambos em destinatario_setor)."""

    SES = "SES"
    ACQUA = "ACQUA"
    OUTROS = "OUTROS"


class NivelAlerta(str, enum.Enum):
    """Não é gravado no banco: calculado a partir da data do ofício (ver services/prazos.py)."""

    NORMAL = "NORMAL"
    ATENCAO = "ATENCAO"
    CRITICO = "CRITICO"


class TipoOficio(Base):
    """Tipos de ofício, cadastrados pelos administradores (migração 0009; antes eram fixos no código).

    O código é a chave usada nos ofícios, filtros e links; o nome pode mudar à vontade. Depois da resposta
    confirmada, os tipos que exigem entrega ficam PENDENTE_RECEBIMENTO até a entrega ser confirmada.
    """

    __tablename__ = "tipos_oficio"

    codigo: Mapped[str] = mapped_column(String(40), primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    nome_curto: Mapped[str | None] = mapped_column(String(40))  # lista e gráficos, quando o nome é longo
    exige_entrega: Mapped[bool] = mapped_column(Boolean, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)  # inativo: some do cadastro, continua nos filtros
    ordem: Mapped[int] = mapped_column(SmallInteger, default=0)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    login: Mapped[str] = mapped_column(String(60), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[Perfil] = mapped_column(Enum(Perfil, name="perfil"), default=Perfil.CLIENTE)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Vai no token; trocar a senha incrementa e derruba as sessões abertas (migração 0010)
    sessao_versao: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Oficio(Base):
    __tablename__ = "oficios"
    __table_args__ = (
        # Numeração e protocolo são únicos por dono: clientes diferentes podem ter o mesmo nº.
        UniqueConstraint("dono_id", "numero", "ano", name="uk_oficio_dono_numero_ano"),
        UniqueConstraint("dono_id", "protocolo", name="uk_oficio_dono_protocolo"),
        Index("idx_oficio_status_prazo", "status", "inicio_prazo"),  # consultas do admin
        Index("idx_oficio_dono_status_prazo", "dono_id", "status", "inicio_prazo"),  # consultas do cliente
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dono_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    numero: Mapped[str] = mapped_column(String(30))
    data_oficio: Mapped[date] = mapped_column(Date)
    # Preenchido pela aplicação a partir de data_oficio; existe para a unicidade número+ano.
    ano: Mapped[int] = mapped_column(SmallInteger)
    # Opcional. Vários NULL convivem com a unicidade (dono, protocolo).
    protocolo: Mapped[str | None] = mapped_column(String(50))
    # Nulo só em ofícios cadastrados antes da classificação existir.
    tipo: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("tipos_oficio.codigo", ondelete="RESTRICT", onupdate="CASCADE")
    )
    destinatario_tipo: Mapped[Destinatario | None] = mapped_column(Enum(Destinatario, name="destinatario"))
    destinatario_setor: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[StatusOficio] = mapped_column(
        Enum(StatusOficio, name="status_oficio"), default=StatusOficio.PENDENTE_RESPOSTA
    )
    # De onde os dias úteis são contados: a data do ofício, ou a data da última reabertura.
    inicio_prazo: Mapped[date] = mapped_column(Date)
    data_resposta: Mapped[date | None] = mapped_column(Date)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    dono: Mapped[Usuario] = relationship(foreign_keys=[dono_id])
    tipo_info: Mapped[TipoOficio | None] = relationship(viewonly=True)
    exclusao_pendente: Mapped["SolicitacaoExclusao | None"] = relationship(
        primaryjoin="and_(SolicitacaoExclusao.oficio_id == Oficio.id, SolicitacaoExclusao.status == 'PENDENTE')",
        viewonly=True,
        uselist=False,
    )
    anexos: Mapped[list["Anexo"]] = relationship(
        back_populates="oficio", cascade="all, delete-orphan", passive_deletes=True
    )
    historico: Mapped[list["HistoricoStatus"]] = relationship(
        back_populates="oficio",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="HistoricoStatus.id",
    )


class Anexo(Base):
    __tablename__ = "anexos"
    # Garante no banco: 1 documento do ofício + 1 de referência (ciclo = 0) e
    # 1 evidência por resposta ou recebimento registrado (ciclo = id do evento no histórico).
    __table_args__ = (UniqueConstraint("oficio_id", "tipo", "ciclo", name="uk_anexo_oficio_tipo_ciclo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oficio_id: Mapped[int] = mapped_column(ForeignKey("oficios.id", ondelete="CASCADE"))
    tipo: Mapped[TipoAnexo] = mapped_column(Enum(TipoAnexo, name="tipo_anexo"))
    ciclo: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    historico_id: Mapped[int | None] = mapped_column(ForeignKey("historico_status.id", ondelete="CASCADE"))
    nome_original: Mapped[str] = mapped_column(String(255))
    caminho: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    hash_sha256: Mapped[str] = mapped_column(String(64))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    enviado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    oficio: Mapped[Oficio] = relationship(back_populates="anexos")


class AnexoLixeira(Base):
    """Versão anterior de um anexo substituído ou removido (migração 0008). O arquivo continua no disco;
    um admin pode restaurá-lo ou apagá-lo de vez. Some junto com o ofício quando ele é excluído."""

    __tablename__ = "anexos_lixeira"
    __table_args__ = (Index("idx_lixeira_data", "descartado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oficio_id: Mapped[int] = mapped_column(ForeignKey("oficios.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[TipoAnexo] = mapped_column(Enum(TipoAnexo, name="tipo_anexo"))
    ciclo: Mapped[int] = mapped_column(Integer, default=0)
    historico_id: Mapped[int | None] = mapped_column(ForeignKey("historico_status.id", ondelete="SET NULL"))
    nome_original: Mapped[str] = mapped_column(String(255))
    caminho: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    hash_sha256: Mapped[str] = mapped_column(String(64))
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    enviado_em: Mapped[datetime] = mapped_column(DateTime)
    motivo: Mapped[str] = mapped_column(String(20))  # SUBSTITUIDO ou REMOVIDO
    descartado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    descartado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    oficio: Mapped[Oficio] = relationship()
    descartado_por: Mapped[Usuario | None] = relationship(foreign_keys=[descartado_por_id])


class HistoricoStatus(Base):
    __tablename__ = "historico_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oficio_id: Mapped[int] = mapped_column(ForeignKey("oficios.id", ondelete="CASCADE"), index=True)
    status_anterior: Mapped[StatusOficio | None] = mapped_column(Enum(StatusOficio, name="status_oficio"))
    status_novo: Mapped[StatusOficio] = mapped_column(Enum(StatusOficio, name="status_oficio"))
    # Data da resposta registrada nesta mudança; preserva cada ciclo mesmo após reabertura.
    data_resposta: Mapped[date | None] = mapped_column(Date)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(String(500))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    alterado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Resposta ou recebimento desfeito por um admin: o evento continua visível, mas deixa de valer
    anulado_em: Mapped[datetime | None] = mapped_column(DateTime)
    anulado_por_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL", name="fk_historico_anulado_por")
    )
    anulado_motivo: Mapped[str | None] = mapped_column(String(500))

    oficio: Mapped[Oficio] = relationship(back_populates="historico")
    usuario: Mapped[Usuario | None] = relationship(foreign_keys=[usuario_id])
    anulado_por: Mapped[Usuario | None] = relationship(foreign_keys=[anulado_por_id])
    evidencia: Mapped[Anexo | None] = relationship(
        primaryjoin="Anexo.historico_id == HistoricoStatus.id", viewonly=True, uselist=False
    )


class Feriado(Base):
    """Datas que não contam como dia útil (nacionais, estaduais, municipais, pontos facultativos)."""

    __tablename__ = "feriados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[date] = mapped_column(Date, unique=True)
    descricao: Mapped[str] = mapped_column(String(120))


class SolicitacaoExclusao(Base):
    """Pedido de exclusão feito por um cliente; um admin aprova (exclui o ofício) ou recusa.

    O pedido sobrevive à exclusão do ofício (oficio_id vira NULL) e guarda a referência em texto.
    """

    __tablename__ = "solicitacoes_exclusao"
    __table_args__ = (Index("idx_solicitacao_status", "status", "criado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    oficio_id: Mapped[int | None] = mapped_column(ForeignKey("oficios.id", ondelete="SET NULL"), index=True)
    referencia: Mapped[str] = mapped_column(String(200))
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    motivo: Mapped[str] = mapped_column(String(1000))
    status: Mapped[StatusSolicitacao] = mapped_column(
        Enum(StatusSolicitacao, name="status_solicitacao"), default=StatusSolicitacao.PENDENTE
    )
    resposta: Mapped[str | None] = mapped_column(String(1000))
    decidido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    solicitante: Mapped[Usuario | None] = relationship(foreign_keys=[solicitante_id])
    decidido_por: Mapped[Usuario | None] = relationship(foreign_keys=[decidido_por_id])


class Auditoria(Base):
    """Registro de toda alteração feita na plataforma: quem, quando, o quê (antes → depois)."""

    __tablename__ = "auditoria"
    __table_args__ = (
        Index("idx_auditoria_usuario_data", "usuario_id", "criado_em"),
        Index("idx_auditoria_data", "criado_em"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    oficio_id: Mapped[int | None] = mapped_column(ForeignKey("oficios.id", ondelete="SET NULL"), index=True)
    # Texto fixo (ex.: "Ofício nº 046/2026 · Nilde") para continuar legível após exclusões
    referencia: Mapped[str | None] = mapped_column(String(200))
    acao: Mapped[str] = mapped_column(String(40))
    descricao: Mapped[str] = mapped_column(String(500))
    detalhes: Mapped[dict | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    usuario: Mapped[Usuario | None] = relationship()
