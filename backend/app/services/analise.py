"""Números do painel. O mesmo cálculo alimenta a tela, o Excel e o PDF, para nunca divergirem.

A agregação é feita em Python sobre as linhas filtradas: o nível de alerta e o tempo de resposta
dependem da contagem de dias úteis (feriados), que não é expressável de forma simples em SQL.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.models import PERFIS_ADMIN, Destinatario, NivelAlerta, Oficio, StatusOficio, TipoOficio, Usuario
from app.schemas import Analise, FiltrosConsulta, Grupo, Indicadores, Mes, Prazos
from app.services.oficios import Limites, filtros_sql
from app.services.prazos import CalendarioUtil, classificar

ROTULO_DESTINATARIO = {Destinatario.SES: "SES", Destinatario.ACQUA: "ACQUA", Destinatario.OUTROS: "Outros"}
ROTULO_STATUS = {
    StatusOficio.PENDENTE_RESPOSTA: "Pendente de resposta",
    StatusOficio.CONFIRMADO: "Confirmado",
    StatusOficio.NAO_CONFIRMADO: "Não confirmado",
    StatusOficio.PENDENTE_RECEBIMENTO: "Pendente de recebimento",
    StatusOficio.RECEBIDO: "Recebido",
}
ROTULO_ALERTA = {NivelAlerta.NORMAL: "No prazo", NivelAlerta.ATENCAO: "Atenção", NivelAlerta.CRITICO: "Crítico"}
SEM_TIPO = "Não classificado"
SEM_DESTINATARIO = "Não informado"
MAX_MESES = 24


@dataclass
class Linha:
    """Um ofício já com os valores calculados, pronto para tela ou exportação."""

    oficio: Oficio
    dono_nome: str
    dias_uteis: int  # da etapa atual (ver prazos.classificar)
    nivel: NivelAlerta | None
    tempo_resposta: int | None = None  # dias úteis do início do prazo até a resposta
    tempo_entrega: int | None = None  # dias úteis da resposta até o recebimento

    @property
    def tipo(self) -> str:
        return self.oficio.tipo_info.nome if self.oficio.tipo_info else SEM_TIPO

    @property
    def destinatario(self) -> str:
        o = self.oficio
        if not o.destinatario_tipo:
            return ""
        return f"{ROTULO_DESTINATARIO[o.destinatario_tipo]} · {o.destinatario_setor or ''}".strip(" ·")


def _media(valores: list[int]) -> float | None:
    return round(sum(valores) / len(valores), 1) if valores else None


@dataclass
class _Acumulador:
    total: int = 0
    por_status: dict[StatusOficio, int] = field(default_factory=lambda: defaultdict(int))
    # nível de alerta das duas etapas pendentes: {(status, nível): quantidade}
    alertas: dict[tuple[StatusOficio, NivelAlerta], int] = field(default_factory=lambda: defaultdict(int))
    tempos: list[int] = field(default_factory=list)
    entregas: list[int] = field(default_factory=list)

    def somar(self, linha: Linha) -> None:
        self.total += 1
        status = linha.oficio.status
        self.por_status[status] += 1
        if linha.nivel is not None:
            self.alertas[(status, linha.nivel)] += 1
        if linha.tempo_resposta is not None:
            self.tempos.append(linha.tempo_resposta)
        if linha.tempo_entrega is not None:
            self.entregas.append(linha.tempo_entrega)

    def alerta(self, nivel: NivelAlerta, status: StatusOficio | None = None) -> int:
        return sum(n for (s, v), n in self.alertas.items() if v == nivel and status in (None, s))

    def grupo(self, chave: str | None, rotulo: str) -> Grupo:
        s = self.por_status
        return Grupo(
            chave=chave,
            rotulo=rotulo,
            total=self.total,
            pendentes=s[StatusOficio.PENDENTE_RESPOSTA],
            pendentes_recebimento=s[StatusOficio.PENDENTE_RECEBIMENTO],
            confirmados=s[StatusOficio.CONFIRMADO],
            recebidos=s[StatusOficio.RECEBIDO],
            nao_confirmados=s[StatusOficio.NAO_CONFIRMADO],
            atencao=self.alerta(NivelAlerta.ATENCAO),
            criticos=self.alerta(NivelAlerta.CRITICO),
            tempo_medio_resposta=_media(self.tempos),
            tempo_medio_entrega=_media(self.entregas),
        )


def carregar_linhas(
    db: Session,
    usuario: Usuario,
    f: FiltrosConsulta,
    calendario: CalendarioUtil,
    hoje: date,
    settings: Settings,
) -> list[Linha]:
    filtros = filtros_sql(usuario, f, Limites.calcular(calendario, hoje, settings))
    consulta = (
        select(Oficio, Usuario.nome)
        .join(Usuario, Oficio.dono_id == Usuario.id)
        .where(*filtros)
        .options(joinedload(Oficio.tipo_info))
        .order_by(Oficio.data_oficio.desc(), Oficio.id.desc())
    )
    linhas = []
    for oficio, dono_nome in db.execute(consulta):
        dias, nivel = classificar(
            oficio.status,
            oficio.inicio_prazo,
            oficio.data_resposta,
            hoje,
            calendario,
            settings.dias_atencao,
            settings.dias_critico,
        )
        respondido = oficio.data_resposta and oficio.status != StatusOficio.PENDENTE_RESPOSTA
        recebido = oficio.data_recebimento and oficio.status == StatusOficio.RECEBIDO
        linhas.append(Linha(
            oficio, dono_nome, dias, nivel,
            tempo_resposta=calendario.dias_uteis_decorridos(oficio.inicio_prazo, oficio.data_resposta)
            if respondido else None,
            tempo_entrega=calendario.dias_uteis_decorridos(oficio.data_resposta, oficio.data_recebimento)
            if recebido else None,
        ))
    return linhas


def _meses(inicio: date, fim: date) -> list[str]:
    meses, (a, m) = [], (inicio.year, inicio.month)
    while (a, m) <= (fim.year, fim.month):
        meses.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return meses[-MAX_MESES:]


def analisar(
    linhas: list[Linha], usuario: Usuario, f: FiltrosConsulta, hoje: date, settings: Settings,
    tipos: list[TipoOficio],
) -> Analise:
    """tipos: todos os cadastrados, na ordem de exibição (os inativos só aparecem se tiverem ofícios)."""
    geral = _Acumulador()
    nomes_tipo = {t.codigo: t.nome for t in tipos}
    por_tipo: dict[str | None, _Acumulador] = {t.codigo: _Acumulador() for t in tipos if t.ativo}
    for t in tipos:
        if not t.ativo:
            por_tipo[t.codigo] = _Acumulador()  # mantém a ordem; sai do resultado se ficar vazio
    por_destinatario: dict[Destinatario | None, _Acumulador] = {d: _Acumulador() for d in Destinatario}
    por_setor: dict[tuple[Destinatario, str], _Acumulador] = defaultdict(_Acumulador)
    nomes_setor: dict[tuple[Destinatario, str], str] = {}
    por_cliente: dict[int, _Acumulador] = defaultdict(_Acumulador)
    nomes_cliente: dict[int, str] = {}
    cadastrados: dict[str, int] = defaultdict(int)
    respondidos: dict[str, int] = defaultdict(int)
    recebidos: dict[str, int] = defaultdict(int)

    for linha in linhas:
        o = linha.oficio
        geral.somar(linha)
        por_tipo.setdefault(o.tipo, _Acumulador()).somar(linha)
        por_destinatario.setdefault(o.destinatario_tipo, _Acumulador()).somar(linha)
        if o.destinatario_tipo and o.destinatario_setor:
            chave = (o.destinatario_tipo, o.destinatario_setor.strip().casefold())
            por_setor[chave].somar(linha)
            # linhas vêm da mais recente para a mais antiga: fica a grafia do primeiro ofício cadastrado
            nomes_setor[chave] = linha.destinatario
        por_cliente[o.dono_id].somar(linha)
        nomes_cliente[o.dono_id] = linha.dono_nome
        cadastrados[f"{o.data_oficio:%Y-%m}"] += 1
        if linha.tempo_resposta is not None:
            respondidos[f"{o.data_resposta:%Y-%m}"] += 1
        if linha.tempo_entrega is not None:
            recebidos[f"{o.data_recebimento:%Y-%m}"] += 1

    # Série mensal: período do filtro, ou do ofício mais antigo até hoje
    datas = [linha.oficio.data_oficio for linha in linhas]
    inicio = f.data_inicio or (min(datas) if datas else hoje)
    fim = f.data_fim or hoje
    por_mes = [Mes(mes=m, cadastrados=cadastrados[m], respondidos=respondidos[m], recebidos=recebidos[m])
               for m in _meses(inicio, fim)]

    g = geral.grupo(None, "")
    # Resposta confirmada inclui quem ainda aguarda a entrega e quem já recebeu
    confirmadas = g.confirmados + g.pendentes_recebimento + g.recebidos
    respondidos_total = confirmadas + g.nao_confirmados
    no_prazo = sum(1 for t in geral.tempos if t < settings.dias_atencao)
    entregas_no_prazo = sum(1 for t in geral.entregas if t < settings.dias_atencao)
    P, PR = StatusOficio.PENDENTE_RESPOSTA, StatusOficio.PENDENTE_RECEBIMENTO
    ativos = {t.codigo for t in tipos if t.ativo}

    return Analise(
        data_referencia=hoje,
        prazos=Prazos(dias_atencao=settings.dias_atencao, dias_critico=settings.dias_critico),
        indicadores=Indicadores(
            total=g.total,
            pendentes=g.pendentes,
            pendentes_normal=geral.alerta(NivelAlerta.NORMAL, P),
            pendentes_atencao=geral.alerta(NivelAlerta.ATENCAO, P),
            pendentes_critico=geral.alerta(NivelAlerta.CRITICO, P),
            pendentes_recebimento=g.pendentes_recebimento,
            recebimento_normal=geral.alerta(NivelAlerta.NORMAL, PR),
            recebimento_atencao=geral.alerta(NivelAlerta.ATENCAO, PR),
            recebimento_critico=geral.alerta(NivelAlerta.CRITICO, PR),
            confirmados=g.confirmados,
            recebidos=g.recebidos,
            nao_confirmados=g.nao_confirmados,
            taxa_confirmacao=round(confirmadas / respondidos_total, 4) if respondidos_total else None,
            tempo_medio_resposta=g.tempo_medio_resposta,
            respondidos_no_prazo=round(no_prazo / len(geral.tempos), 4) if geral.tempos else None,
            tempo_medio_entrega=g.tempo_medio_entrega,
            entregues_no_prazo=round(entregas_no_prazo / len(geral.entregas), 4) if geral.entregas else None,
            concluidos=g.confirmados + g.recebidos,
        ),
        por_tipo=[
            acc.grupo(t, nomes_tipo.get(t, t) if t else SEM_TIPO)
            for t, acc in por_tipo.items()
            if (t is not None and t in ativos) or acc.total
        ],
        por_destinatario=[
            acc.grupo(d.value if d else None, ROTULO_DESTINATARIO[d] if d else SEM_DESTINATARIO)
            for d, acc in por_destinatario.items()
            if d is not None or acc.total
        ],
        por_setor=sorted(
            (acc.grupo(f"{k[0].value}:{k[1]}", nomes_setor[k]) for k, acc in por_setor.items()),
            key=lambda g: (-g.total, g.rotulo),
        )[:10],
        por_cliente=sorted(
            (acc.grupo(str(i), nomes_cliente[i]) for i, acc in por_cliente.items()),
            key=lambda g: (-g.total, g.rotulo),
        )
        if usuario.perfil in PERFIS_ADMIN
        else [],
        por_mes=por_mes,
    )
