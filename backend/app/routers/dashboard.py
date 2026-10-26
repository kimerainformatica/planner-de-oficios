from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import and_, case, func, select

from app.deps import CalendarioDep, DbDep, HojeDep, SettingsDep, UsuarioDep
from app.models import PERFIS_ADMIN, NivelAlerta, Oficio, StatusOficio, TipoOficio, Usuario
from app.schemas import Analise, ConsultaExportacao, FiltrosConsulta, Prazos, ResumoDashboard
from app.services import exportacao
from app.services import tipos
from app.services.analise import ROTULO_ALERTA, ROTULO_DESTINATARIO, ROTULO_STATUS, analisar, carregar_linhas
from app.services.oficios import Limites, escopo

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

FiltrosDep = Annotated[FiltrosConsulta, Query()]


@router.get("/resumo", response_model=ResumoDashboard, summary="Contadores (cliente: só os seus ofícios)")
def resumo(
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    usuario: UsuarioDep,
    dono_id: Annotated[int | None, Query(description="Admin: resumo de um cliente específico")] = None,
):
    limites = Limites.calcular(calendario, hoje, settings)
    filtros = [escopo(usuario)]
    if dono_id is not None:
        filtros.append(Oficio.dono_id == dono_id)

    def contar(condicao):
        return func.coalesce(func.sum(case((condicao, 1), else_=0)), 0)

    # Uma única consulta agregada para todos os cards (níveis: só os pendentes de resposta).
    pendente = Oficio.status == StatusOficio.PENDENTE_RESPOSTA
    linha = db.execute(
        select(
            func.count(Oficio.id),
            contar(Oficio.status == StatusOficio.CONFIRMADO),
            contar(Oficio.status == StatusOficio.NAO_CONFIRMADO),
            contar(pendente),
            contar(and_(pendente, limites.filtro(NivelAlerta.NORMAL))),
            contar(and_(pendente, limites.filtro(NivelAlerta.ATENCAO))),
            contar(and_(pendente, limites.filtro(NivelAlerta.CRITICO))),
            contar(Oficio.status == StatusOficio.PENDENTE_RECEBIMENTO),
            contar(Oficio.status == StatusOficio.RECEBIDO),
        ).where(*filtros)
    ).one()

    return ResumoDashboard(
        data_referencia=hoje,
        total=linha[0],
        confirmados=linha[1],
        nao_confirmados=linha[2],
        pendentes=linha[3],
        pendentes_normal=linha[4],
        pendentes_atencao=linha[5],
        pendentes_critico=linha[6],
        pendentes_recebimento=linha[7],
        recebidos=linha[8],
    )


@router.get("/prazos", response_model=Prazos, summary="Dias úteis que levam um pendente a atenção e a crítico")
def prazos(settings: SettingsDep, _: UsuarioDep):
    return Prazos(dias_atencao=settings.dias_atencao, dias_critico=settings.dias_critico)


@router.get("/analise", response_model=Analise, summary="Indicadores e agrupamentos para os gráficos do painel")
def analise(
    f: FiltrosDep, db: DbDep, settings: SettingsDep, calendario: CalendarioDep, hoje: HojeDep, usuario: UsuarioDep
):
    linhas = carregar_linhas(db, usuario, f, calendario, hoje, settings)
    return analisar(linhas, usuario, f, hoje, settings, tipos.listar(db))


def _descrever_filtros(f: FiltrosConsulta, db: DbDep) -> list[str]:
    partes = []
    if f.data_inicio or f.data_fim:
        de = f.data_inicio.strftime("%d/%m/%Y") if f.data_inicio else "início"
        ate = f.data_fim.strftime("%d/%m/%Y") if f.data_fim else "hoje"
        partes.append(f"Período: {de} a {ate}")
    if f.dono_id:
        dono = db.get(Usuario, f.dono_id)
        partes.append(f"Cliente: {dono.nome if dono else f.dono_id}")
    if f.tipo:
        tipo = db.get(TipoOficio, f.tipo)
        partes.append(f"Tipo: {tipo.nome if tipo else f.tipo}")
    if f.destinatario_tipo:
        partes.append(f"Destinatário: {ROTULO_DESTINATARIO[f.destinatario_tipo]}")
    if f.status:
        partes.append(f"Status: {ROTULO_STATUS[f.status]}")
    if f.alerta:
        partes.append(f"Prazo: {ROTULO_ALERTA[f.alerta]}")
    if f.busca:
        partes.append(f"Busca: {f.busca}")
    return partes


@router.get(
    "/exportar",
    summary="Exporta o painel filtrado (indicadores, gráficos e lista de ofícios) em Excel ou PDF",
    response_class=Response,
)
def exportar(
    f: Annotated[ConsultaExportacao, Query()],
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    usuario: UsuarioDep,
):
    formato = f.formato
    linhas = carregar_linhas(db, usuario, f, calendario, hoje, settings)
    dados = analisar(linhas, usuario, f, hoje, settings, tipos.listar(db))
    filtros = _descrever_filtros(f, db)
    admin = usuario.perfil in PERFIS_ADMIN
    gerar = exportacao.gerar_excel if formato == "xlsx" else exportacao.gerar_pdf
    conteudo = gerar(dados, linhas, filtros, admin)
    # octet-stream + nosniff: o Edge intercepta PDFs pedidos via fetch (ver routers/anexos.py)
    return Response(
        conteudo,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="oficios-{hoje:%Y-%m-%d}.{formato}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
