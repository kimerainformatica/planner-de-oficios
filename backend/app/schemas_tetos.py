"""Esquemas do Controle de Tetos. Valores saem como número (float, já arredondado no centavo)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from app.models import PeriodoTeto
from app.schemas import Esquema
from app.schemas_manutencao import PessoaOut
from app.services.tetos import SituacaoTeto

Valor = Field(gt=0, max_digits=14, decimal_places=2)


def _vazio_vira_nulo(v):
    return None if isinstance(v, str) and not v.strip() else v


# ---------- setores ----------


class SetorRef(Esquema):
    id: int
    nome: str


class SetorOut(Esquema):
    id: int
    nome: str
    descricao: str | None
    ativo: bool
    usuarios: list[PessoaOut] = []  # quem lança os gastos do setor
    tipos: int = 0


class SetorCriar(Esquema):
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=2000)

    _limpa = field_validator("descricao", mode="before")(_vazio_vira_nulo)


class SetorAtualizar(Esquema):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=2000)
    ativo: bool | None = None


# ---------- tipos e valores de teto ----------


class Equivalentes(Esquema):
    """O teto da vigência nos três períodos (diário e mensal no mês de referência)."""

    diario: float
    mensal: float
    anual: float


class VigenciaOut(Esquema):
    id: int
    inicio: date
    periodo: PeriodoTeto
    valor: float
    motivo: str | None
    criado_por: PessoaOut | None
    criado_em: datetime
    equivalentes: Equivalentes


class TipoRef(Esquema):
    id: int
    nome: str
    unidade: str


class TipoOut(Esquema):
    id: int
    setor: SetorRef
    nome: str
    descricao: str | None
    unidade: str
    alerta_pct: int
    ativo: bool
    periodo: PeriodoTeto | None  # da vigência atual
    valor: float | None
    vigente_desde: date | None
    equivalentes: Equivalentes | None
    lancamentos: int = 0
    vigencias: list[VigenciaOut] = []  # só no detalhe


class TipoCriar(Esquema):
    setor_id: int
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=2000)
    unidade: str = Field(default="R$", min_length=1, max_length=20, description="R$, litros, resmas, kWh…")
    alerta_pct: int = Field(default=80, ge=1, le=100, description="% do teto que acende a atenção")
    periodo: PeriodoTeto
    valor: Decimal = Valor
    inicio: date | None = Field(default=None, description="Vale a partir de (padrão: 1º dia do mês corrente)")

    _limpa = field_validator("descricao", mode="before")(_vazio_vira_nulo)


class TipoAtualizar(Esquema):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=2000)
    unidade: str | None = Field(default=None, min_length=1, max_length=20)
    alerta_pct: int | None = Field(default=None, ge=1, le=100)
    ativo: bool | None = None


class VigenciaCriar(Esquema):
    """Novo valor de teto a partir de `inicio`. Na mesma data de uma vigência existente, substitui o valor dela."""

    periodo: PeriodoTeto
    valor: Decimal = Valor
    inicio: date
    motivo: str | None = Field(default=None, max_length=500)

    _limpa = field_validator("motivo", mode="before")(_vazio_vira_nulo)


# ---------- lançamentos ----------


class GastoOut(Esquema):
    id: int
    tipo: TipoRef
    setor: SetorRef
    data: date
    valor: float
    descricao: str
    documento: str | None
    arquivo_nome: str | None
    arquivo_tamanho: int | None
    registrado_por: PessoaOut | None
    registrado_em: datetime
    atualizado_por: PessoaOut | None
    atualizado_em: datetime | None
    pode_editar: bool


class GastoAtualizar(Esquema):
    data: date | None = None
    valor: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    descricao: str | None = Field(default=None, min_length=2, max_length=300)
    documento: str | None = Field(default=None, max_length=60)
    tipo_id: int | None = None


class TotalTipo(Esquema):
    tipo: TipoRef
    total: float
    quantidade: int


class PaginaGastos(Esquema):
    itens: list[GastoOut]
    total: int
    pagina: int
    por_pagina: int
    totais: list[TotalTipo]  # soma de cada tipo no filtro (cada um na unidade dele)


# ---------- indicadores ----------


class ConsumoOut(Esquema):
    gasto: float
    teto: float
    percentual: float | None
    restante: float
    situacao: SituacaoTeto


class ConsumoMes(ConsumoOut):
    teto_ate_hoje: float  # teto do 1º dia do mês até a data de referência (o "ritmo" esperado)
    projecao: float  # no ritmo atual, quanto se gasta até o fim do mês
    projecao_estoura: bool


class IndicadorTipo(Esquema):
    tipo: TipoOut
    dia: ConsumoOut
    mes: ConsumoMes
    ano: ConsumoOut


class TotalUnidade(Esquema):
    """Soma dos tipos de mesma unidade (só se somam valores na mesma unidade)."""

    unidade: str
    mes: ConsumoOut
    ano: ConsumoOut


class PainelSetor(Esquema):
    setor: SetorRef
    tipos: list[IndicadorTipo]
    totais: list[TotalUnidade]


class PainelTetos(Esquema):
    referencia: date
    setores: list[PainelSetor]
    estourados: int  # tipos com o mês acima do teto
    em_atencao: int


class PontoDiario(Esquema):
    data: date
    gasto: float
    teto: float
    acumulado: float
    teto_acumulado: float


class PontoMensal(Esquema):
    mes: int
    gasto: float
    teto: float


class PontoAnual(Esquema):
    ano: int
    gasto: float
    teto: float


class IndicadoresTipo(Esquema):
    referencia: date
    ano: int
    mes: int
    resumo: IndicadorTipo
    diario: list[PontoDiario]  # dias do mês escolhido
    mensal: list[PontoMensal]  # meses do ano escolhido
    anual: list[PontoAnual]  # do primeiro ano com teto ou gasto até o ano de referência


class ResumoTetos(Esquema):
    """O que o usuário é no módulo (a tela usa para montar o menu)."""

    eh_gestor: bool
    setor: SetorRef | None
