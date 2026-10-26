from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, and_, func, or_, select, true
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.models import (
    PERFIS_ADMIN,
    HistoricoStatus,
    NivelAlerta,
    Oficio,
    SolicitacaoExclusao,
    StatusOficio,
    Usuario,
)
from app.schemas import FiltrosConsulta, HistoricoOut, OficioDetalhe, OficioOut
from app.services.exclusoes import montar_solicitacao
from app.services.prazos import CalendarioUtil, classificar
from app.services.tipos import exige_recebimento

P = StatusOficio.PENDENTE_RESPOSTA
PR = StatusOficio.PENDENTE_RECEBIMENTO

# Transições de status permitidas. CONFIRMADO e RECEBIDO são finais.
# Nos tipos com etapa de entrega, confirmar a resposta leva a PENDENTE_RECEBIMENTO (ver alterar_status).
TRANSICOES: dict[StatusOficio, set[StatusOficio]] = {
    StatusOficio.PENDENTE_RESPOSTA: {StatusOficio.CONFIRMADO, StatusOficio.NAO_CONFIRMADO, PR},
    StatusOficio.NAO_CONFIRMADO: {StatusOficio.PENDENTE_RESPOSTA},
    StatusOficio.PENDENTE_RECEBIMENTO: {StatusOficio.RECEBIDO},
    StatusOficio.CONFIRMADO: set(),
    StatusOficio.RECEBIDO: set(),
}


# ---------- visibilidade e permissões ----------


def escopo(usuario: Usuario) -> ColumnElement[bool]:
    """Admin e master veem todos os ofícios; cliente vê só os seus."""
    return true() if usuario.perfil in PERFIS_ADMIN else Oficio.dono_id == usuario.id


def buscar_oficio(db: Session, oficio_id: int, usuario: Usuario, detalhe: bool = False) -> Oficio:
    """Ofício de outro cliente responde 404, para não revelar que existe."""
    opcoes = [selectinload(Oficio.anexos), selectinload(Oficio.dono)]
    if detalhe:
        historico = selectinload(Oficio.historico)
        opcoes += [
            historico.selectinload(HistoricoStatus.usuario),
            historico.selectinload(HistoricoStatus.anulado_por),
            historico.selectinload(HistoricoStatus.evidencia),
            selectinload(Oficio.exclusao_pendente).selectinload(SolicitacaoExclusao.solicitante),
        ]
    oficio = db.scalar(select(Oficio).where(Oficio.id == oficio_id, escopo(usuario)).options(*opcoes))
    if oficio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ofício não encontrado")
    return oficio


def filtros_sql(usuario: Usuario, f: FiltrosConsulta, limites: "Limites | None" = None) -> list[ColumnElement[bool]]:
    """Condições comuns à lista, ao painel e às exportações (sempre dentro do escopo do usuário)."""
    filtros = [escopo(usuario)]
    if f.dono_id is not None:
        filtros.append(Oficio.dono_id == f.dono_id)
    if f.status is not None:
        filtros.append(Oficio.status == f.status)
    if f.alerta is not None and limites is not None:
        filtros.append(limites.filtro(f.alerta))
    if f.tipo is not None:
        filtros.append(Oficio.tipo == f.tipo)
    if f.destinatario_tipo is not None:
        filtros.append(Oficio.destinatario_tipo == f.destinatario_tipo)
    if f.busca and f.busca.strip():
        termo = f"%{f.busca.strip()}%"
        filtros.append(
            or_(
                Oficio.numero.like(termo),
                Oficio.protocolo.like(termo),
                Oficio.destinatario_setor.like(termo),
                Oficio.observacao.like(termo),
            )
        )
    if f.data_inicio:
        filtros.append(Oficio.data_oficio >= f.data_inicio)
    if f.data_fim:
        filtros.append(Oficio.data_oficio <= f.data_fim)
    return filtros


# ---------- prazos ----------


@dataclass(frozen=True)
class Limites:
    """Datas de corte do dia: ofícios pendentes com início <= limite atingiram o nível.

    O início é inicio_prazo para quem aguarda resposta e data_resposta para quem aguarda recebimento.
    """

    atencao: date
    critico: date

    @classmethod
    def calcular(cls, calendario: CalendarioUtil, hoje: date, settings: Settings) -> "Limites":
        return cls(
            atencao=calendario.data_limite(settings.dias_atencao, hoje),
            critico=calendario.data_limite(settings.dias_critico, hoje),
        )

    def _nivel(self, nivel: NivelAlerta, inicio) -> ColumnElement[bool]:
        if nivel == NivelAlerta.CRITICO:
            return inicio <= self.critico
        if nivel == NivelAlerta.ATENCAO:
            return and_(inicio > self.critico, inicio <= self.atencao)
        return inicio > self.atencao

    def filtro(self, nivel: NivelAlerta) -> ColumnElement[bool]:
        return or_(
            and_(Oficio.status == P, self._nivel(nivel, Oficio.inicio_prazo)),
            and_(Oficio.status == PR, self._nivel(nivel, Oficio.data_resposta)),
        )


def montar_oficio(
    oficio: Oficio, calendario: CalendarioUtil, hoje: date, settings: Settings, detalhe: bool = False
) -> OficioOut:
    dias, nivel = classificar(
        oficio.status,
        oficio.inicio_prazo,
        oficio.data_resposta,
        hoje,
        calendario,
        settings.dias_atencao,
        settings.dias_critico,
    )
    respondido = oficio.data_resposta is not None and oficio.status != P
    recebido = oficio.data_recebimento is not None and oficio.status == StatusOficio.RECEBIDO
    dados = {
        **{campo: getattr(oficio, campo) for campo in OficioOut.model_fields if hasattr(oficio, campo)},
        "dias_uteis_decorridos": dias,
        "nivel_alerta": nivel,
        "dias_resposta": calendario.dias_uteis_decorridos(oficio.inicio_prazo, oficio.data_resposta)
        if respondido else None,
        "dias_entrega": calendario.dias_uteis_decorridos(oficio.data_resposta, oficio.data_recebimento)
        if recebido else None,
    }
    if not detalhe:
        return OficioOut.model_validate(dados)
    dados["historico"] = [
        HistoricoOut.model_validate(h).model_copy(update={
            "usuario_nome": h.usuario.nome if h.usuario else None,
            "anulado_por_nome": h.anulado_por.nome if h.anulado_por else None,
        })
        for h in oficio.historico
    ]  # a evidência de cada resposta vem junto (relationship HistoricoStatus.evidencia)
    if oficio.exclusao_pendente is not None:
        dados["exclusao_pendente"] = montar_solicitacao(oficio.exclusao_pendente)
    return OficioDetalhe.model_validate(dados)


# ---------- regras de negócio ----------


def verificar_duplicidade(
    db: Session, dono_id: int, numero: str, ano: int, protocolo: str | None, ignorar_id: int | None = None
) -> None:
    def existe(*condicoes) -> bool:
        consulta = select(Oficio.id).where(Oficio.dono_id == dono_id, *condicoes)
        if ignorar_id is not None:
            consulta = consulta.where(Oficio.id != ignorar_id)
        return db.scalar(consulta.limit(1)) is not None

    if protocolo and existe(Oficio.protocolo == protocolo):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe um ofício com o protocolo {protocolo}")
    if existe(Oficio.numero == numero, Oficio.ano == ano):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe o ofício nº {numero} em {ano}")


def registrar_historico(
    db: Session,
    oficio: Oficio,
    anterior: StatusOficio | None,
    novo: StatusOficio,
    usuario: Usuario,
    observacao: str | None,
) -> HistoricoStatus:
    evento = HistoricoStatus(
        oficio=oficio,
        status_anterior=anterior,
        status_novo=novo,
        data_resposta=oficio.data_resposta,
        data_recebimento=oficio.data_recebimento,
        observacao=observacao,
        usuario_id=usuario.id,
    )
    db.add(evento)
    return evento


def alterar_status(
    db: Session,
    oficio: Oficio,
    novo: StatusOficio,
    data_resposta: date | None,
    data_recebimento: date | None,
    observacao: str | None,
    usuario: Usuario,
    hoje: date,
) -> StatusOficio:
    """Aplica a mudança e devolve o status gravado (pode diferir do pedido, ver abaixo)."""
    atual = oficio.status
    exige = exige_recebimento(db, oficio.tipo)
    if novo == StatusOficio.CONFIRMADO and exige:
        # A resposta confirmada ainda depende da entrega (itens ou serviço)
        novo = PR
    elif novo in (PR, StatusOficio.RECEBIDO) and not exige:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este tipo de ofício não exige confirmação de recebimento")
    if novo == atual:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O ofício já está neste status")
    if novo not in TRANSICOES[atual]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Não é permitido mudar de {atual.value} para {novo.value}"
        )

    if novo == P:
        # Reabertura: o prazo recomeça do zero hoje. O ciclo anterior fica no histórico.
        oficio.data_resposta = None
        oficio.inicio_prazo = hoje
    elif novo == StatusOficio.RECEBIDO:
        if data_recebimento is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe a data do recebimento")
        if data_recebimento < oficio.data_resposta or data_recebimento > hoje:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A data do recebimento deve estar entre a data da resposta e hoje",
            )
        oficio.data_recebimento = data_recebimento
    else:
        if data_resposta is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Informe a data da resposta")
        if data_resposta < oficio.inicio_prazo or data_resposta > hoje:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A data da resposta deve estar entre o início do prazo e hoje",
            )
        oficio.data_resposta = data_resposta

    oficio.status = novo
    registrar_historico(db, oficio, atual, novo, usuario, observacao)
    return novo


def ajustar_etapa_recebimento(db: Session, oficio: Oficio, usuario: Usuario) -> StatusOficio | None:
    """Após trocar o tipo de um ofício (ou a regra do tipo): entra ou sai da etapa de recebimento.

    Devolve o status anterior quando houve mudança. O histórico registra o motivo.
    """
    atual = oficio.status
    exige = exige_recebimento(db, oficio.tipo)
    if exige and atual == StatusOficio.CONFIRMADO:
        novo, motivo = PR, "O tipo passou a exigir confirmação do recebimento"
    elif not exige and atual in (PR, StatusOficio.RECEBIDO):
        novo, motivo = StatusOficio.CONFIRMADO, "O tipo deixou de exigir confirmação do recebimento"
        oficio.data_recebimento = None  # o recebimento registrado continua no histórico
    else:
        return None
    oficio.status = novo
    registrar_historico(db, oficio, atual, novo, usuario, motivo)
    return atual


# ---------- correções do admin (resposta e recebimento) ----------

RESULTADOS = {StatusOficio.CONFIRMADO, StatusOficio.NAO_CONFIRMADO, PR}


def _ativos(oficio: Oficio) -> list[HistoricoStatus]:
    return [h for h in oficio.historico if h.anulado_em is None]


def evento_resposta_atual(oficio: Oficio) -> HistoricoStatus | None:
    """A resposta que vale no ciclo atual (None se o ofício aguarda resposta)."""
    if oficio.status == P:
        return None
    for h in reversed(_ativos(oficio)):
        if h.status_anterior == P and h.status_novo in RESULTADOS:
            return h
        if h.status_novo == P:
            return None
    return None


def evento_recebimento_atual(oficio: Oficio) -> HistoricoStatus | None:
    if oficio.status != StatusOficio.RECEBIDO:
        return None
    return next((h for h in reversed(_ativos(oficio)) if h.status_novo == StatusOficio.RECEBIDO), None)


def _anular_desde(oficio: Oficio, evento: HistoricoStatus, usuario: Usuario, motivo: str) -> None:
    """Anula o evento e os que vieram depois dele (ex.: ajustes de etapa por troca de tipo)."""
    agora = func.now()  # mesmo relógio de alterado_em (o do banco)
    for h in _ativos(oficio):
        if h.id >= evento.id:
            h.anulado_em, h.anulado_por, h.anulado_motivo = agora, usuario, motivo


def _validar_data_resposta(oficio: Oficio, data: date, hoje: date) -> None:
    if data < oficio.inicio_prazo or data > hoje:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A data da resposta deve estar entre o início do prazo e hoje")
    if oficio.data_recebimento and data > oficio.data_recebimento:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A data da resposta não pode ser posterior ao recebimento")


def corrigir_resposta(db: Session, oficio: Oficio, dados: dict, usuario: Usuario, hoje: date) -> dict:
    """Admin corrige resultado, data e observação da resposta atual. Devolve as mudanças para a auditoria.

    Mudar o resultado anula a resposta antiga e registra a nova (a evidência acompanha); só data e
    observação são corrigidas no próprio evento.
    """
    evento = evento_resposta_atual(oficio)
    if evento is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este ofício não tem resposta registrada no ciclo atual")
    data = dados.get("data_resposta") or oficio.data_resposta
    _validar_data_resposta(oficio, data, hoje)
    observacao = dados["observacao"] if "observacao" in dados else evento.observacao

    novo = dados.get("status")
    if novo is not None and novo not in (StatusOficio.CONFIRMADO, StatusOficio.NAO_CONFIRMADO):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O resultado da resposta deve ser Confirmado ou Não confirmado")
    if novo == StatusOficio.CONFIRMADO and exige_recebimento(db, oficio.tipo):
        novo = PR
    muda_resultado = novo is not None and (novo == StatusOficio.NAO_CONFIRMADO) != (
        evento.status_novo == StatusOficio.NAO_CONFIRMADO)

    mudancas: dict = {}
    if data != oficio.data_resposta:
        mudancas["data_resposta"] = {"de": str(oficio.data_resposta), "para": str(data)}
    if observacao != evento.observacao:
        mudancas["observacao"] = {"de": evento.observacao, "para": observacao}

    if muda_resultado:
        if oficio.status == StatusOficio.RECEBIDO:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Desfaça o recebimento antes de mudar o resultado da resposta")
        mudancas["status"] = {"de": oficio.status.value, "para": novo.value}
        _anular_desde(oficio, evento, usuario, "Resultado da resposta corrigido")
        oficio.status, oficio.data_resposta = novo, data
        novo_evento = registrar_historico(db, oficio, P, novo, usuario, observacao)
        db.flush()
        # A evidência da resposta continua valendo para a resposta corrigida
        for anexo in oficio.anexos:
            if anexo.historico_id == evento.id:
                anexo.historico_id = anexo.ciclo = novo_evento.id
        return mudancas

    oficio.data_resposta = data
    evento.observacao = observacao
    for h in _ativos(oficio):
        if h.id >= evento.id:
            h.data_resposta = data  # eventos do ciclo guardam a data da resposta
    return mudancas


def corrigir_recebimento(oficio: Oficio, dados: dict, hoje: date) -> dict:
    evento = evento_recebimento_atual(oficio)
    if evento is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este ofício não tem recebimento registrado")
    data = dados.get("data_recebimento") or oficio.data_recebimento
    if data < oficio.data_resposta or data > hoje:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "A data do recebimento deve estar entre a data da resposta e hoje")
    observacao = dados["observacao"] if "observacao" in dados else evento.observacao
    mudancas: dict = {}
    if data != oficio.data_recebimento:
        mudancas["data_recebimento"] = {"de": str(oficio.data_recebimento), "para": str(data)}
    if observacao != evento.observacao:
        mudancas["observacao"] = {"de": evento.observacao, "para": observacao}
    oficio.data_recebimento = evento.data_recebimento = data
    evento.observacao = observacao
    return mudancas


def desfazer_etapa(oficio: Oficio, motivo: str, usuario: Usuario) -> tuple[StatusOficio, str]:
    """Desfaz o recebimento (volta a aguardar a entrega) ou, sem ele, a resposta (volta a aguardar resposta).

    O prazo não reinicia: não é uma reabertura, é a correção de um registro.
    """
    evento = evento_recebimento_atual(oficio)
    etapa = "o recebimento"
    if evento is None:
        evento, etapa = evento_resposta_atual(oficio), "a resposta"
    if evento is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Não há resposta nem recebimento para desfazer")
    anterior = oficio.status
    _anular_desde(oficio, evento, usuario, motivo)
    oficio.status = evento.status_anterior
    oficio.data_recebimento = None
    if oficio.status == P:
        oficio.data_resposta = None
    return anterior, etapa
