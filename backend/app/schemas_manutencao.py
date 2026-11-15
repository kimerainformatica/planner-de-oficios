"""Entrada e saída da API do módulo Manutenção Clínica (helpdesk)."""

from datetime import date, datetime

from pydantic import Field

from app.models import Destinatario, Perfil, SituacaoEquipamento, StatusChamado, StatusOficio, TipoAnexo, TipoInteracao
from app.schemas import Esquema
from app.services.manutencao import SituacaoPrazo

# ---------- empresas ----------


class EmpresaOut(Esquema):
    id: int
    nome: str
    descricao: str | None
    prazo_horas: int
    ativo: bool
    tecnicos: int = 0
    chamados: int = 0


class EmpresaCriar(Esquema):
    nome: str = Field(min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=200)
    prazo_horas: int = Field(default=24, ge=1, le=720, description="Horas corridas para o diagnóstico (24 = 1 dia)")


class EmpresaAtualizar(Esquema):
    nome: str | None = Field(default=None, min_length=2, max_length=80)
    descricao: str | None = Field(default=None, max_length=200)
    prazo_horas: int | None = Field(default=None, ge=1, le=720)
    ativo: bool | None = None


# ---------- chamados ----------


class PessoaOut(Esquema):
    id: int
    nome: str


class EmpresaResumo(Esquema):
    id: int
    nome: str


class PrazoOut(Esquema):
    situacao: SituacaoPrazo
    horas_restantes: float | None
    horas_ate_diagnostico: float | None


class ChamadoOut(Esquema):
    id: int
    codigo: str
    titulo: str
    descricao: str
    local: str | None
    equipamento: str | None
    empresa: EmpresaResumo
    solicitante: PessoaOut
    tecnico: PessoaOut | None
    status: StatusChamado
    ocorrido_em: datetime
    aberto_em: datetime
    prazo_horas: int
    prazo_em: datetime
    diagnosticado_em: datetime | None
    concluido_em: datetime | None
    cancelado_em: datetime | None
    atualizado_em: datetime
    prazo: PrazoOut
    # Tempo de solução: do diagnóstico até a conclusão, em horas corridas (gravado ao concluir)
    solucao_horas_corridas: float | None = None
    execucao_horas: float | None = None  # em aberto e já diagnosticado: horas corridas desde o diagnóstico
    oficios_pendentes: int = 0  # solicitações de peças/equipamentos ainda não entregues
    oficios_resumo: list["OficioResumo"] = []  # nº e status de cada ofício (cartões do quadro)


class RelatorioOut(Esquema):
    id: int
    codigo: str
    chamado_id: int
    tecnico: PessoaOut | None
    empresa: EmpresaResumo
    criado_em: datetime
    atendido_em: datetime
    equipamento: str | None
    identificacao: str | None
    diagnostico: str
    causa: str | None
    servico_executado: str | None
    pecas: str | None
    situacao_equipamento: SituacaoEquipamento
    recomendacoes: str | None


class InteracaoOut(Esquema):
    id: int
    tipo: TipoInteracao
    texto: str | None
    criado_em: datetime
    ocorrido_em: datetime | None = None  # resposta técnica/relatório: data e hora informadas do diagnóstico
    autor: PessoaOut | None
    autor_papel: Perfil | None = None  # papel do autor no módulo (para a tela mostrar "Técnico", "Operacional"…)
    relatorio: RelatorioOut | None
    arquivo_nome: str | None
    arquivo_mime: str | None
    arquivo_tamanho: int | None


class OficioResumo(Esquema):
    id: int
    numero: str
    status: StatusOficio


class AnexoOficio(Esquema):
    """Documento anexado ao ofício no Planner (o chamado mostra e deixa baixar)."""

    id: int
    tipo: TipoAnexo
    nome_original: str
    mime_type: str
    tamanho_bytes: int
    enviado_em: datetime


class OficioVinculado(Esquema):
    """Ofício do Planner ligado ao chamado: solicitação feita pelo chamado ou ofício que já existia e foi vinculado."""

    id: int
    numero: str
    data_oficio: date
    tipo: str | None
    tipo_nome: str | None = None
    protocolo: str | None
    status: StatusOficio
    data_resposta: date | None
    data_recebimento: date | None
    observacao: str | None
    dono_id: int
    dono_nome: str | None = None
    anexos: list[AnexoOficio] = []
    pode_desvincular: bool = False  # para quem consulta, agora


class OficioDisponivel(Esquema):
    """Ofício já cadastrado no Planner, ainda sem chamado, que quem consulta pode vincular."""

    id: int
    numero: str
    ano: int
    data_oficio: date
    tipo_nome: str | None = None
    protocolo: str | None
    status: StatusOficio
    observacao: str | None
    dono_nome: str | None = None


class ChamadoDetalhe(ChamadoOut):
    interacoes: list[InteracaoOut]
    oficios: list[OficioVinculado] = []
    pode_solicitar_pecas: bool = False
    # O que quem consulta pode fazer agora (a tela mostra só os botões permitidos)
    pode_assumir: bool
    pode_responder: bool  # diagnóstico, relatório e arquivo técnico
    pode_comentar: bool
    pode_concluir: bool
    # Editar o diagnóstico e os complementos: data e hora, resumo, campos do relatório e o relatório externo
    pode_corrigir_diagnostico: bool = False
    diagnostico_interacao_id: int | None = None  # a resposta técnica ou o relatório que contou como diagnóstico
    pode_reabrir: bool
    pode_cancelar: bool


class ChamadoCriar(Esquema):
    empresa_id: int
    titulo: str = Field(min_length=3, max_length=150)
    descricao: str = Field(min_length=5, max_length=5000)
    local: str | None = Field(default=None, max_length=120)
    equipamento: str | None = Field(default=None, max_length=120)
    ocorrido_em: datetime | None = Field(default=None, description="Data e hora do problema (padrão: agora)")


class TipoSolicitacao(Esquema):
    codigo: str
    nome: str


class SolicitacaoPecasCriar(Esquema):
    """Ofício de solicitação de peças ou equipamentos, registrado no Planner de Ofícios e ligado ao chamado."""

    tipo: str = Field(description="SOLICITACAO_EQUIPAMENTOS ou PECAS_MANUTENCAO (GET /api/manutencao/tipos-solicitacao)")
    numero: str = Field(min_length=1, max_length=30)
    data_oficio: date
    protocolo: str | None = Field(default=None, max_length=50)
    destinatario_tipo: Destinatario | None = None
    destinatario_setor: str | None = Field(default=None, max_length=120)
    itens: str = Field(min_length=3, max_length=4000, description="Peças ou equipamentos solicitados")


class RespostaAtualizar(Esquema):
    """Edição de uma resposta técnica (o diagnóstico ou um complemento). Só os campos enviados mudam."""

    ocorrido_em: datetime | None = Field(default=None, description="Data e hora do diagnóstico")
    texto: str | None = Field(default=None, max_length=10000, description="Resumo do diagnóstico")
    motivo: str | None = Field(default=None, max_length=2000)


class RelatorioAtualizar(Esquema):
    """Edição do relatório técnico. Só os campos enviados mudam."""

    atendido_em: datetime | None = None
    equipamento: str | None = Field(default=None, max_length=120)
    identificacao: str | None = Field(default=None, max_length=120)
    diagnostico: str | None = Field(default=None, min_length=5, max_length=10000)
    causa: str | None = Field(default=None, max_length=5000)
    servico_executado: str | None = Field(default=None, max_length=10000)
    pecas: str | None = Field(default=None, max_length=5000)
    situacao_equipamento: SituacaoEquipamento | None = None
    recomendacoes: str | None = Field(default=None, max_length=5000)
    motivo: str | None = Field(default=None, max_length=2000)


class CorrecaoDiagnostico(Esquema):
    diagnosticado_em: datetime = Field(description="Data e hora corretas do diagnóstico")
    motivo: str | None = Field(default=None, max_length=2000)


class Motivo(Esquema):
    motivo: str = Field(min_length=3, max_length=2000)


class Conclusao(Esquema):
    texto: str | None = Field(default=None, max_length=5000, description="Resumo da solução")


class RelatorioCriar(Esquema):
    atendido_em: datetime | None = Field(default=None, description="Data e hora do atendimento (padrão: agora)")
    equipamento: str | None = Field(default=None, max_length=120)
    identificacao: str | None = Field(default=None, max_length=120)
    diagnostico: str = Field(min_length=5, max_length=10000)
    causa: str | None = Field(default=None, max_length=5000)
    servico_executado: str | None = Field(default=None, max_length=10000)
    pecas: str | None = Field(default=None, max_length=5000)
    situacao_equipamento: SituacaoEquipamento = SituacaoEquipamento.NAO_SE_APLICA
    recomendacoes: str | None = Field(default=None, max_length=5000)


class PaginaChamados(Esquema):
    itens: list[ChamadoOut]
    total: int
    pagina: int
    por_pagina: int


# ---------- painel ----------


class PainelEmpresa(Esquema):
    empresa: EmpresaResumo
    abertos: int  # aberto + em atendimento
    aguardando_diagnostico: int
    atrasados: int
    concluidos: int
    diagnosticados: int
    no_prazo_pct: float | None  # % dos diagnósticos feitos dentro do prazo
    media_horas_diagnostico: float | None
    media_horas_solucao: float | None = None  # do diagnóstico à conclusão, em horas corridas


class PainelManutencao(Esquema):
    papel: Perfil
    eh_admin: bool
    empresa_do_tecnico: EmpresaResumo | None
    abertos: int
    em_atendimento: int
    aguardando_diagnostico: int
    vencendo: int
    atrasados: int
    concluidos: int
    cancelados: int
    por_empresa: list[PainelEmpresa]
    urgentes: list[ChamadoOut]  # sem diagnóstico, os mais perto do prazo (ou já atrasados)


# ---------- quadro de acompanhamento (técnico) ----------


class ColunaQuadro(Esquema):
    chave: str  # AGUARDANDO_DIAGNOSTICO | EM_EXECUCAO | AGUARDANDO_PECAS | CONCLUIDOS
    titulo: str
    descricao: str
    chamados: list[ChamadoOut]


class ResumoQuadro(Esquema):
    em_aberto: int
    aguardando_diagnostico: int
    atrasados: int
    aguardando_pecas: int
    concluidos_periodo: int
    diagnostico_no_prazo_pct: float | None
    media_horas_diagnostico: float | None
    media_horas_solucao: float | None


class QuadroOut(Esquema):
    empresa: EmpresaResumo | None  # a do técnico (ou a filtrada)
    meus: bool
    dias: int
    resumo: ResumoQuadro
    colunas: list[ColunaQuadro]


# ChamadoOut usa OficioResumo, definido depois dele
for _modelo in (ChamadoOut, ChamadoDetalhe, PaginaChamados, PainelManutencao, ColunaQuadro, QuadroOut):
    _modelo.model_rebuild()
