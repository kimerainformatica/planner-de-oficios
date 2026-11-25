"""Entrada e saída da API da manutenção preventiva e dos avisos internos (módulo Manutenções Integradas)."""

from datetime import date, datetime

from pydantic import Field

from app.models import StatusPreventiva, UnidadePeriodo
from app.schemas import Esquema
from app.schemas_manutencao import EmpresaResumo, PessoaOut
from app.services.preventivas import SituacaoPreventiva

# ---------- planos ----------


class PlanoCriar(Esquema):
    empresa_id: int
    titulo: str = Field(min_length=3, max_length=150)
    descricao: str | None = Field(default=None, max_length=5000, description="Escopo: o que verificar ou fazer")
    local: str | None = Field(default=None, max_length=120)
    equipamento: str | None = Field(default=None, max_length=120)
    intervalo: int = Field(ge=1, le=120, description="A cada quantos dias, semanas ou meses")
    unidade: UnidadePeriodo
    inicio: date = Field(description="Data da primeira preventiva")
    tolerancia_dias: int = Field(default=5, ge=0, le=60)


class PlanoAtualizar(Esquema):
    titulo: str | None = Field(default=None, min_length=3, max_length=150)
    descricao: str | None = Field(default=None, max_length=5000)
    local: str | None = Field(default=None, max_length=120)
    equipamento: str | None = Field(default=None, max_length=120)
    intervalo: int | None = Field(default=None, ge=1, le=120)
    unidade: UnidadePeriodo | None = None
    inicio: date | None = Field(default=None, description="Próxima data, quando a periodicidade muda")
    tolerancia_dias: int | None = Field(default=None, ge=0, le=60)
    ativo: bool | None = None


class PlanoOut(Esquema):
    id: int
    empresa: EmpresaResumo
    titulo: str
    descricao: str | None
    local: str | None
    equipamento: str | None
    intervalo: int
    unidade: UnidadePeriodo
    periodicidade: str = ""  # "mensal", "a cada 45 dias"…
    inicio: date
    tolerancia_dias: int
    ativo: bool
    proxima: date | None = None  # próxima preventiva ainda programada
    previstas: int = 0  # as que já deveriam ter sido feitas, mais as já registradas
    realizadas: int = 0
    atrasadas: int = 0


# ---------- preventivas ----------


class PlanoRef(Esquema):
    id: int
    titulo: str
    descricao: str | None
    local: str | None
    equipamento: str | None
    tolerancia_dias: int
    periodicidade: str = ""


class PreventivaOut(Esquema):
    id: int
    codigo: str
    plano: PlanoRef
    empresa: EmpresaResumo
    data_prevista: date
    limite: date  # último dia para contar como feita no prazo
    status: StatusPreventiva
    situacao: SituacaoPreventiva
    dias: int  # dias até a data prevista (negativo: já passou)
    realizada_em: date | None
    executor: str | None
    observacao: str | None
    registrada_em: datetime | None
    registrada_por: PessoaOut | None
    arquivo_nome: str | None
    arquivo_mime: str | None
    arquivo_tamanho: int | None
    motivo: str | None
    atestada_em: datetime | None
    atestada_por: PessoaOut | None
    ateste_obs: str | None
    # O que quem consulta pode fazer agora
    pode_realizar: bool = False
    pode_atestar: bool = False
    pode_nao_realizar: bool = False
    pode_reabrir: bool = False


class ResumoPreventivas(Esquema):
    """Previsto x realizado de uma empresa no período (fiscalização)."""

    empresa: EmpresaResumo
    previstas: int
    realizadas: int
    no_prazo: int
    com_atraso: int
    atrasadas: int
    nao_realizadas: int
    aguardando_ateste: int
    atestadas: int
    cumprimento_pct: float | None  # realizadas ÷ (realizadas + atrasadas + não realizadas)


class PaginaPreventivas(Esquema):
    de: date | None
    ate: date | None
    itens: list[PreventivaOut]
    resumo: list[ResumoPreventivas]


class Ateste(Esquema):
    observacao: str | None = Field(default=None, max_length=2000)


class MotivoPreventiva(Esquema):
    motivo: str = Field(min_length=3, max_length=2000)


# ---------- avisos internos ----------


class Aviso(Esquema):
    chave: str
    nivel: str  # CRITICO | ATENCAO | INFO
    quantidade: int
    titulo: str
    link: str  # tela que mostra os itens


class Avisos(Esquema):
    total: int  # itens críticos e de atenção (o número que aparece no menu)
    itens: list[Aviso]
