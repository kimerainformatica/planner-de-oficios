import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    JSON,
    Integer,
    Numeric,
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
    CLIENTE = "CLIENTE"  # nas Manutenções Integradas é o "operacional": abre e acompanha os chamados
    TECNICO = "TECNICO"  # só nas Manutenções Integradas: técnico de uma empresa, atende os chamados dela


PERFIS_ADMIN = {Perfil.MASTER, Perfil.ADMIN}


class Modulo(str, enum.Enum):
    """Módulos da plataforma. Para criar um novo: acrescente aqui, em services/modulos.py (nome e rota) e
    numa migração (o enum do banco)."""

    OFICIOS = "OFICIOS"  # Planner de Ofícios
    MANUTENCAO = "MANUTENCAO"  # Manutenções Integradas
    DOCUMENTOS = "DOCUMENTOS"  # Documentos: planner dos documentos da instituição (ofícios, memorandos…)


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
    # Bloco de assinatura dos documentos gerados (ofícios e memorandos; migração 0018)
    cargo: Mapped[str | None] = mapped_column(String(120))
    matricula: Mapped[str | None] = mapped_column(String(30))
    # Só para conferir quem assinou pelo GOV.BR (dado pessoal: a API só devolve mascarado; migração 0019)
    cpf: Mapped[str | None] = mapped_column(String(11))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # `perfil` é global: MASTER (acesso total a todos os módulos) ou CLIENTE (comum). O papel de quem não é
    # MASTER em cada módulo (ADMIN ou CLIENTE) vem de `modulos`.
    modulos: Mapped[list["UsuarioModulo"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", lazy="selectin", order_by="UsuarioModulo.modulo"
    )

    @property
    def eh_master(self) -> bool:
        return self.perfil == Perfil.MASTER

    def perfil_no(self, modulo: Modulo) -> Perfil | None:
        """MASTER em todos os módulos; senão o papel gravado para o módulo; None se não tem acesso."""
        if self.eh_master:
            return Perfil.MASTER
        for acesso in self.modulos:
            if acesso.modulo == modulo:
                return acesso.perfil
        return None

    def tem_acesso(self, modulo: Modulo) -> bool:
        return self.perfil_no(modulo) is not None

    def eh_admin_no(self, modulo: Modulo) -> bool:
        return self.perfil_no(modulo) in PERFIS_ADMIN

    def acesso_no(self, modulo: Modulo) -> "UsuarioModulo | None":
        return next((a for a in self.modulos if a.modulo == modulo), None)

    @property
    def modulos_efetivos(self) -> list["UsuarioModulo"]:
        """Acessos do usuário. O MASTER recebe um acesso MASTER (não gravado) em cada módulo."""
        if self.eh_master:
            return [UsuarioModulo(modulo=m, perfil=Perfil.MASTER) for m in Modulo]
        return list(self.modulos)


class UsuarioModulo(Base):
    """Acesso de um usuário a um módulo, com o papel dele ali (ADMIN, CLIENTE ou, na Manutenção, TECNICO).
    Um admin de um módulo não é admin dos outros. O técnico pertence a uma empresa (`empresa_id`)."""

    __tablename__ = "usuario_modulos"
    __table_args__ = (UniqueConstraint("usuario_id", "modulo", name="uk_usuario_modulo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    modulo: Mapped[Modulo] = mapped_column(Enum(Modulo, name="modulo"))
    perfil: Mapped[Perfil] = mapped_column(Enum(Perfil, name="perfil"), default=Perfil.CLIENTE)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"))

    usuario: Mapped[Usuario] = relationship(back_populates="modulos")
    empresa: Mapped["EmpresaManutencao | None"] = relationship(lazy="selectin")


# ================= Manutenções Integradas (helpdesk) =================


class StatusChamado(str, enum.Enum):
    ABERTO = "ABERTO"  # aguardando o técnico
    EM_ATENDIMENTO = "EM_ATENDIMENTO"  # um técnico assumiu ou já respondeu
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"


class TipoInteracao(str, enum.Enum):
    """Linha do tempo do chamado. Nada aqui é apagado: é o histórico do atendimento."""

    ABERTURA = "ABERTURA"
    COMENTARIO = "COMENTARIO"
    DIAGNOSTICO = "DIAGNOSTICO"  # resposta técnica (texto e/ou arquivo externo); a 1ª encerra o prazo
    RELATORIO = "RELATORIO"  # relatório técnico no modelo do sistema; também conta como diagnóstico
    ASSUMIDO = "ASSUMIDO"
    CONCLUSAO = "CONCLUSAO"
    REABERTURA = "REABERTURA"
    CANCELAMENTO = "CANCELAMENTO"
    OFICIO = "OFICIO"  # solicitação de peças/equipamentos registrada no Planner de Ofícios
    CORRECAO = "CORRECAO"  # correção de um registro (ex.: data e hora do diagnóstico)


class SituacaoEquipamento(str, enum.Enum):
    OPERANDO = "OPERANDO"
    OPERANDO_COM_RESTRICAO = "OPERANDO_COM_RESTRICAO"
    PARADO = "PARADO"
    AGUARDANDO_PECA = "AGUARDANDO_PECA"
    NAO_SE_APLICA = "NAO_SE_APLICA"


class EmpresaManutencao(Base):
    """Empresa / modalidade técnica que atende chamados (MSI, Realiza Predial, Realiza Climatização…)."""

    __tablename__ = "empresas_manutencao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    descricao: Mapped[str | None] = mapped_column(String(200))
    prazo_horas: Mapped[int] = mapped_column(Integer, default=24, server_default="24")  # horas corridas p/ diagnóstico
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Chamado(Base):
    __tablename__ = "chamados"
    __table_args__ = (
        Index("idx_chamado_status_empresa", "status", "empresa_id"),
        Index("idx_chamado_empresa_aberto", "empresa_id", "aberto_em"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"))
    solicitante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    tecnico_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))  # responsável
    titulo: Mapped[str] = mapped_column(String(150))
    descricao: Mapped[str] = mapped_column(Text)
    local: Mapped[str | None] = mapped_column(String(120))
    equipamento: Mapped[str | None] = mapped_column(String(120))
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime)  # data e hora do problema, informada na abertura
    aberto_em: Mapped[datetime] = mapped_column(DateTime)
    # Prazo do diagnóstico: `prazo_horas` horas corridas (da empresa, no momento da abertura) a partir da abertura
    prazo_horas: Mapped[int] = mapped_column(Integer)
    prazo_em: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[StatusChamado] = mapped_column(
        Enum(StatusChamado, name="status_chamado"), default=StatusChamado.ABERTO
    )
    # Data e hora do primeiro diagnóstico, informadas por quem registrou (podem ser corrigidas)
    diagnosticado_em: Mapped[datetime | None] = mapped_column(DateTime)
    diagnosticado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime)
    # Tempo de solução: do diagnóstico até a conclusão, em horas corridas, gravado ao concluir (apagado ao reabrir)
    solucao_horas_corridas: Mapped[float | None] = mapped_column(Float)

    empresa: Mapped[EmpresaManutencao] = relationship(lazy="joined")
    solicitante: Mapped[Usuario] = relationship(foreign_keys=[solicitante_id], lazy="joined")
    tecnico: Mapped[Usuario | None] = relationship(foreign_keys=[tecnico_id], lazy="joined")
    diagnosticado_por: Mapped[Usuario | None] = relationship(foreign_keys=[diagnosticado_por_id])
    interacoes: Mapped[list["ChamadoInteracao"]] = relationship(
        back_populates="chamado", cascade="all, delete-orphan", order_by="ChamadoInteracao.id"
    )
    relatorios: Mapped[list["RelatorioTecnico"]] = relationship(
        back_populates="chamado", cascade="all, delete-orphan", order_by="RelatorioTecnico.id"
    )
    # Ofícios do Planner com a solicitação de peças/equipamentos deste chamado
    oficios: Mapped[list["Oficio"]] = relationship(back_populates="chamado", lazy="selectin", order_by="Oficio.id")

    @property
    def codigo(self) -> str:
        return f"CH-{self.id:05d}"


class RelatorioTecnico(Base):
    """Relatório técnico no modelo do sistema (gera PDF)."""

    __tablename__ = "relatorios_tecnicos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"))
    tecnico_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"))
    criado_em: Mapped[datetime] = mapped_column(DateTime)
    atendido_em: Mapped[datetime] = mapped_column(DateTime)  # data e hora do atendimento técnico
    equipamento: Mapped[str | None] = mapped_column(String(120))
    identificacao: Mapped[str | None] = mapped_column(String(120))  # patrimônio / nº de série / tag
    diagnostico: Mapped[str] = mapped_column(Text)
    causa: Mapped[str | None] = mapped_column(Text)
    servico_executado: Mapped[str | None] = mapped_column(Text)
    pecas: Mapped[str | None] = mapped_column(Text)
    situacao_equipamento: Mapped[SituacaoEquipamento] = mapped_column(
        Enum(SituacaoEquipamento, name="situacao_equipamento"), default=SituacaoEquipamento.NAO_SE_APLICA
    )
    recomendacoes: Mapped[str | None] = mapped_column(Text)

    chamado: Mapped[Chamado] = relationship(back_populates="relatorios")
    tecnico: Mapped[Usuario | None] = relationship(lazy="joined")
    empresa: Mapped[EmpresaManutencao] = relationship(lazy="joined")

    @property
    def codigo(self) -> str:
        return f"RT-{self.id:05d}"


class ChamadoInteracao(Base):
    __tablename__ = "chamado_interacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chamado_id: Mapped[int] = mapped_column(ForeignKey("chamados.id", ondelete="CASCADE"), index=True)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    tipo: Mapped[TipoInteracao] = mapped_column(Enum(TipoInteracao, name="tipo_interacao"))
    texto: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime)  # quando foi registrado no sistema
    # Resposta técnica e relatório: data e hora do diagnóstico/atendimento informadas por quem registrou
    ocorrido_em: Mapped[datetime | None] = mapped_column(DateTime)
    relatorio_id: Mapped[int | None] = mapped_column(ForeignKey("relatorios_tecnicos.id", ondelete="SET NULL"))
    # Arquivo anexado à interação (ex.: relatório externo do técnico, foto do problema)
    arquivo_nome: Mapped[str | None] = mapped_column(String(255))
    arquivo_caminho: Mapped[str | None] = mapped_column(String(500))
    arquivo_mime: Mapped[str | None] = mapped_column(String(100))
    arquivo_tamanho: Mapped[int | None] = mapped_column(Integer)
    arquivo_sha256: Mapped[str | None] = mapped_column(String(64))

    chamado: Mapped[Chamado] = relationship(back_populates="interacoes")
    autor: Mapped[Usuario | None] = relationship(lazy="joined")
    relatorio: Mapped[RelatorioTecnico | None] = relationship(lazy="joined")


# ---------- manutenção preventiva (migração 0015) ----------


class UnidadePeriodo(str, enum.Enum):
    DIAS = "DIAS"
    SEMANAS = "SEMANAS"
    MESES = "MESES"


class StatusPreventiva(str, enum.Enum):
    PROGRAMADA = "PROGRAMADA"
    REALIZADA = "REALIZADA"
    NAO_REALIZADA = "NAO_REALIZADA"  # não foi feita, com o motivo registrado


class PlanoPreventiva(Base):
    """Rotina de manutenção preventiva de uma empresa técnica: o que fazer e de quanto em quanto tempo.
    A periodicidade é definida aqui (o contrato prevê a preventiva, mas não fixa os períodos)."""

    __tablename__ = "planos_preventiva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"), index=True)
    titulo: Mapped[str] = mapped_column(String(150))
    descricao: Mapped[str | None] = mapped_column(Text)  # escopo: o que deve ser verificado/feito
    local: Mapped[str | None] = mapped_column(String(120))
    equipamento: Mapped[str | None] = mapped_column(String(120))
    intervalo: Mapped[int] = mapped_column(Integer)  # a cada `intervalo` `unidade`
    unidade: Mapped[UnidadePeriodo] = mapped_column(Enum(UnidadePeriodo, name="unidade_periodo"))
    inicio: Mapped[date] = mapped_column(Date)  # data da primeira preventiva (as demais contam a partir dela)
    # Dias corridos, depois da data prevista, em que a preventiva ainda conta como feita no prazo
    tolerancia_dias: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    empresa: Mapped[EmpresaManutencao] = relationship(lazy="joined")
    preventivas: Mapped[list["Preventiva"]] = relationship(
        back_populates="plano", cascade="all, delete-orphan", passive_deletes=True, order_by="Preventiva.data_prevista"
    )


class Preventiva(Base):
    """Uma ocorrência do plano: a preventiva prevista para uma data, com o registro da realização e o ateste."""

    __tablename__ = "preventivas"
    __table_args__ = (
        UniqueConstraint("plano_id", "data_prevista", name="uk_preventiva_plano_data"),
        Index("idx_preventiva_empresa_data", "empresa_id", "data_prevista"),
        Index("idx_preventiva_status_data", "status", "data_prevista"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plano_id: Mapped[int] = mapped_column(ForeignKey("planos_preventiva.id", ondelete="CASCADE"))
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas_manutencao.id", ondelete="RESTRICT"))
    data_prevista: Mapped[date] = mapped_column(Date)
    status: Mapped[StatusPreventiva] = mapped_column(
        Enum(StatusPreventiva, name="status_preventiva"), default=StatusPreventiva.PROGRAMADA
    )
    # Realização (registrada pelo técnico da empresa, pelo operacional ou pelo administrador)
    realizada_em: Mapped[date | None] = mapped_column(Date)
    executor: Mapped[str | None] = mapped_column(String(120))  # quem executou o serviço
    observacao: Mapped[str | None] = mapped_column(Text)
    registrada_em: Mapped[datetime | None] = mapped_column(DateTime)
    registrada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Evidência: checklist, ordem de serviço ou relatório da empresa
    arquivo_nome: Mapped[str | None] = mapped_column(String(255))
    arquivo_caminho: Mapped[str | None] = mapped_column(String(500))
    arquivo_mime: Mapped[str | None] = mapped_column(String(100))
    arquivo_tamanho: Mapped[int | None] = mapped_column(Integer)
    arquivo_sha256: Mapped[str | None] = mapped_column(String(64))
    motivo: Mapped[str | None] = mapped_column(Text)  # por que não foi realizada
    # Ateste de quem fiscaliza (operacional ou administrador): confirma que o serviço foi feito
    atestada_em: Mapped[datetime | None] = mapped_column(DateTime)
    atestada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    ateste_obs: Mapped[str | None] = mapped_column(Text)

    plano: Mapped[PlanoPreventiva] = relationship(back_populates="preventivas", lazy="joined")
    empresa: Mapped[EmpresaManutencao] = relationship(lazy="joined")
    registrada_por: Mapped[Usuario | None] = relationship(foreign_keys=[registrada_por_id], lazy="joined")
    atestada_por: Mapped[Usuario | None] = relationship(foreign_keys=[atestada_por_id], lazy="joined")

    @property
    def codigo(self) -> str:
        return f"PV-{self.id:05d}"


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
    # De onde os dias (corridos) são contados: a data do ofício, ou a data da última reabertura.
    inicio_prazo: Mapped[date] = mapped_column(Date)
    data_resposta: Mapped[date | None] = mapped_column(Date)
    data_recebimento: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    # Solicitação de peças/equipamentos feita a partir de um chamado das Manutenções Integradas (migração 0013)
    chamado_id: Mapped[int | None] = mapped_column(ForeignKey("chamados.id", ondelete="SET NULL"), index=True)

    dono: Mapped[Usuario] = relationship(foreign_keys=[dono_id])
    chamado: Mapped["Chamado | None"] = relationship(back_populates="oficios", lazy="selectin")
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
    # Ofício redigido e emitido no app (Documentos), quando for o caso
    documento_gerado: Mapped["Documento | None"] = relationship(
        primaryjoin="Documento.oficio_id == Oficio.id", viewonly=True, uselist=False, lazy="select"
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
    """Feriados cadastrados (nacionais, estaduais, municipais). Desde a 2.2 não entram nos prazos, que são em dias corridos."""

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


# ================= Documentos (planner dos documentos redigidos no app) =================


class EstruturaDocumento(str, enum.Enum):
    """Como o cabeçalho do documento é montado (timbrado, fontes, margens e assinaturas são iguais para todos)."""

    EXTERNO = "EXTERNO"  # para fora da unidade: número, data e destinatário por extenso (como o ofício)
    INTERNO = "INTERNO"  # entre setores: título e número na mesma linha, De e Para (como o memorando)
    SIMPLES = "SIMPLES"  # sem destinatário: título centralizado (declaração, relatório, ata, termo…)


# Modelos que vêm com o sistema. O ofício continua a numeração do Planner de Ofícios e pode ser registrado lá.
TIPO_OFICIO = "OFICIO"
TIPO_MEMORANDO = "MEMORANDO"


class EtapaDocumento(str, enum.Enum):
    """Coluna do documento no quadro (calculada, não gravada)."""

    RASCUNHO = "RASCUNHO"
    AGUARDANDO = "AGUARDANDO"  # emitido, falta assinatura eletrônica
    ASSINADO = "ASSINADO"  # emitido, com todas as assinaturas eletrônicas previstas
    CONCLUIDO = "CONCLUIDO"  # marcado como concluído (entregue, respondido ou arquivado)
    CANCELADO = "CANCELADO"


class AlertaPrazo(str, enum.Enum):
    """Situação do prazo de um documento em aberto (calculada)."""

    EM_DIA = "EM_DIA"
    ATENCAO = "ATENCAO"  # vence hoje ou em até DOCUMENTOS_DIAS_ATENCAO dias
    ATRASADO = "ATRASADO"


class StatusDocumento(str, enum.Enum):
    RASCUNHO = "RASCUNHO"  # editável, sem número e sem validade
    EMITIDO = "EMITIDO"  # número, data e código de verificação; o conteúdo não muda mais
    CANCELADO = "CANCELADO"  # continua consultável (a verificação mostra o cancelamento)


class PapelAssinatura(str, enum.Enum):
    ELABORADOR = "ELABORADOR"  # quem elaborou (o autor)
    VALIDADOR = "VALIDADOR"  # o "De acordo"


class FormaAssinatura(str, enum.Enum):
    APP = "APP"  # login + senha no app
    GOVBR = "GOVBR"  # no portal GOV.BR, com certificado; o PDF assinado é enviado de volta


class ModeloDocumento(Base):
    """Modelo de documento da instituição (ofício, memorando, declaração…), cadastrado pelo administrador.

    Define o cabeçalho (estrutura), a numeração, o recuo do parágrafo, os textos com que o rascunho começa e a forma
    de assinatura sugerida (cada documento escolhe a sua). Na emissão o formato é copiado para o documento
    (`Documento.formato`): mudar o modelo depois não muda os documentos já emitidos.
    """

    __tablename__ = "modelos_documento"

    codigo: Mapped[str] = mapped_column(String(40), primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    descricao: Mapped[str | None] = mapped_column(String(300))
    estrutura: Mapped[EstruturaDocumento] = mapped_column(Enum(EstruturaDocumento, name="estrutura_documento"))
    digitos: Mapped[int] = mapped_column(SmallInteger, default=2)  # do número: 2 → 01/2026, 3 → 001/2026
    recuo_cm: Mapped[float] = mapped_column(Numeric(4, 2, asdecimal=False), default=1.25)  # 1ª linha do parágrafo
    forma_assinatura: Mapped[FormaAssinatura] = mapped_column(
        Enum(FormaAssinatura, name="forma_assinatura"), default=FormaAssinatura.APP
    )
    mostrar_assunto: Mapped[bool] = mapped_column(Boolean, default=True)  # imprime a linha "Assunto:"
    data_no_fim: Mapped[bool] = mapped_column(Boolean, default=False)  # local e data depois do texto
    rotulo_ident: Mapped[str] = mapped_column(String(30), default="Matrícula")  # antes da matrícula na assinatura
    vocativo: Mapped[str] = mapped_column(String(160), default="")
    fecho: Mapped[str] = mapped_column(String(120), default="Atenciosamente,")
    texto_modelo: Mapped[str] = mapped_column(Text, default="")  # o texto com que o rascunho começa
    sistema: Mapped[bool] = mapped_column(Boolean, default=False)  # ofício e memorando: não se apagam
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PastaDocumento(Base):
    """Pasta para organizar os documentos (um setor, um assunto, um projeto…). O documento fica em uma ou em
    nenhuma; a pasta não muda quem pode ver o documento."""

    __tablename__ = "pastas_documento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    descricao: Mapped[str | None] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Documento(Base):
    """Documento redigido a partir de um modelo (ofício, memorando, declaração…) e impresso no modelo da unidade
    (timbrado, margens, fontes).

    O número é sequencial por autor, modelo e ano e só é dado na emissão (rascunho apagado não abre buraco).
    No ofício ele segue a numeração do Planner do autor (ex.: 012/2026) e, com `registrar_no_planner`, a emissão
    cadastra o ofício lá.
    Emitido, o conteúdo fica travado e o hash dele vai para a verificação. Com a assinatura do app o PDF é sempre
    gerado a partir do banco, com as assinaturas que houver; com a do GOV.BR o PDF da emissão fica guardado, porque a
    assinatura vale para aquele arquivo, e cada envio assinado é acrescentado a ele.
    Pasta, prazo e conclusão organizam o trabalho: mudam a qualquer momento e não fazem parte do conteúdo.
    """

    __tablename__ = "documentos"
    __table_args__ = (
        UniqueConstraint("tipo", "autor_id", "ano", "numero", name="uk_documento_numero"),
        Index("idx_documento_autor", "autor_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(  # código do modelo
        String(40), ForeignKey("modelos_documento.codigo", ondelete="RESTRICT", onupdate="CASCADE")
    )
    status: Mapped[StatusDocumento] = mapped_column(
        Enum(StatusDocumento, name="status_documento"), default=StatusDocumento.RASCUNHO
    )
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    ano: Mapped[int | None] = mapped_column(SmallInteger)
    numero: Mapped[int | None] = mapped_column(Integer)
    data_documento: Mapped[date | None] = mapped_column(Date)

    assunto: Mapped[str] = mapped_column(String(300), default="")
    vocativo: Mapped[str] = mapped_column(String(160), default="")
    corpo: Mapped[str] = mapped_column(Text, default="")
    fecho: Mapped[str] = mapped_column(String(120), default="Atenciosamente,")
    # Ofício (e os modelos externos): destinatário por extenso
    dest_tratamento: Mapped[str | None] = mapped_column(String(60))
    dest_nome: Mapped[str | None] = mapped_column(String(160))
    dest_cargo: Mapped[str | None] = mapped_column(String(160))
    dest_endereco: Mapped[str | None] = mapped_column(String(300))
    # Memorando (e os modelos internos): setores de origem e destino
    de: Mapped[str | None] = mapped_column(String(160))
    para: Mapped[str | None] = mapped_column(String(160))
    # Ofício: integração com o Planner de Ofícios (a emissão cadastra o ofício lá) e a classificação usada
    registrar_no_planner: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    oficio_tipo: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("tipos_oficio.codigo", ondelete="RESTRICT", onupdate="CASCADE")
    )
    destinatario_tipo: Mapped[Destinatario | None] = mapped_column(Enum(Destinatario, name="destinatario"))
    destinatario_setor: Mapped[str | None] = mapped_column(String(120))
    oficio_id: Mapped[int | None] = mapped_column(ForeignKey("oficios.id", ondelete="SET NULL"), index=True)

    # Blocos de assinatura como saem impressos (o elaborador é o autor; o validador é o "De acordo")
    elaborador_nome: Mapped[str] = mapped_column(String(120), default="")
    elaborador_cargo: Mapped[str | None] = mapped_column(String(120))
    elaborador_ident: Mapped[str | None] = mapped_column(String(30))
    validador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    validador_nome: Mapped[str | None] = mapped_column(String(120))
    validador_cargo: Mapped[str | None] = mapped_column(String(120))
    validador_ident: Mapped[str | None] = mapped_column(String(30))

    codigo: Mapped[str | None] = mapped_column(String(12), unique=True)  # código de verificação
    hash_conteudo: Mapped[str | None] = mapped_column(String(64))
    forma_assinatura: Mapped[FormaAssinatura] = mapped_column(
        Enum(FormaAssinatura, name="forma_assinatura"), default=FormaAssinatura.APP, server_default="APP"
    )
    # GOV.BR: o PDF da emissão e a última versão assinada (caminhos relativos ao storage)
    arquivo_original: Mapped[str | None] = mapped_column(String(255))
    arquivo_original_hash: Mapped[str | None] = mapped_column(String(64))
    arquivo_assinado: Mapped[str | None] = mapped_column(String(255))
    arquivo_assinado_hash: Mapped[str | None] = mapped_column(String(64))
    # Formato do modelo na emissão (estrutura, numeração, recuo…): o documento não muda se o modelo mudar depois
    formato: Mapped[dict | None] = mapped_column(JSON)
    # Organização: fora do conteúdo (não entra no hash), muda a qualquer momento
    pasta_id: Mapped[int | None] = mapped_column(ForeignKey("pastas_documento.id", ondelete="SET NULL"), index=True)
    prazo: Mapped[date | None] = mapped_column(Date)  # data-limite; conta até o documento ser concluído
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime)
    concluido_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    emitido_em: Mapped[datetime | None] = mapped_column(DateTime)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime)
    cancelado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(500))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    autor: Mapped[Usuario] = relationship(foreign_keys=[autor_id], lazy="joined")
    validador: Mapped[Usuario | None] = relationship(foreign_keys=[validador_id], lazy="joined")
    cancelado_por: Mapped[Usuario | None] = relationship(foreign_keys=[cancelado_por_id])
    oficio: Mapped[Oficio | None] = relationship(lazy="joined")
    modelo: Mapped[ModeloDocumento] = relationship(lazy="joined")
    pasta: Mapped[PastaDocumento | None] = relationship(lazy="joined")
    concluido_por: Mapped[Usuario | None] = relationship(foreign_keys=[concluido_por_id])
    assinaturas: Mapped[list["AssinaturaDocumento"]] = relationship(
        back_populates="documento", cascade="all, delete-orphan", lazy="selectin", order_by="AssinaturaDocumento.id"
    )

    def _do_formato(self, campo: str):
        """O valor da emissão (`formato`) ou, no rascunho, o do modelo."""
        return (self.formato or {}).get(campo, getattr(self.modelo, campo))

    @property
    def nome_tipo(self) -> str:
        return self._do_formato("nome")

    @property
    def numero_formatado(self) -> str | None:
        if self.numero is None:
            return None
        return f"{self.numero:0{self._do_formato('digitos')}d}/{self.ano}"

    @property
    def titulo(self) -> str:
        nome = self.nome_tipo
        return f"{nome} nº {self.numero_formatado}" if self.numero is not None else f"{nome} (rascunho)"


class AssinaturaDocumento(Base):
    """Assinatura eletrônica: feita no app (login + senha confirmada na hora) ou no GOV.BR (certificado conferido no
    PDF enviado). Guarda como o bloco saiu."""

    __tablename__ = "documento_assinaturas"
    __table_args__ = (UniqueConstraint("documento_id", "papel", name="uk_assinatura_papel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id", ondelete="CASCADE"))
    papel: Mapped[PapelAssinatura] = mapped_column(Enum(PapelAssinatura, name="papel_assinatura"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(120))
    cargo: Mapped[str | None] = mapped_column(String(120))
    assinado_em: Mapped[datetime] = mapped_column(DateTime)
    ip: Mapped[str | None] = mapped_column(String(45))
    forma: Mapped[FormaAssinatura] = mapped_column(
        Enum(FormaAssinatura, name="forma_assinatura"), default=FormaAssinatura.APP, server_default="APP"
    )
    # GOV.BR: dados do certificado (CPF mascarado) e o SHA-256 da assinatura
    cert_nome: Mapped[str | None] = mapped_column(String(160))
    cert_cpf: Mapped[str | None] = mapped_column(String(14))
    cert_emissor: Mapped[str | None] = mapped_column(String(160))
    cert_serie: Mapped[str | None] = mapped_column(String(64))
    impressao: Mapped[str | None] = mapped_column(String(64))

    documento: Mapped[Documento] = relationship(back_populates="assinaturas")
