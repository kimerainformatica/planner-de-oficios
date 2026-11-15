"""Manutenção preventiva e avisos internos do módulo Manutenção Clínica (regras em services/preventivas.py).

Todas as rotas exigem acesso ao módulo (o MASTER sempre tem). O técnico vê só o que é da empresa dele.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import AgoraDep, DbDep, HojeDep, SettingsDep, UsuarioDep, exige_acesso_ao, exige_admin_do
from app.models import Chamado, EmpresaManutencao, Modulo, PlanoPreventiva, Preventiva, StatusPreventiva, Usuario
from app.schemas_manutencao import EmpresaResumo, PessoaOut
from app.schemas_preventivas import (
    Ateste,
    Aviso,
    Avisos,
    MotivoPreventiva,
    PaginaPreventivas,
    PlanoAtualizar,
    PlanoCriar,
    PlanoOut,
    PlanoRef,
    PreventivaOut,
    ResumoPreventivas,
)
from app.services import armazenamento
from app.services import manutencao as regras
from app.services import preventivas as prev
from app.services.manutencao import ABERTOS, SituacaoPrazo
from app.services.preventivas import SituacaoPreventiva

router = APIRouter(
    prefix="/api/manutencao", tags=["Manutenção Clínica · Preventivas"],
    dependencies=[Depends(exige_acesso_ao(Modulo.MANUTENCAO))],
)
AdminManutencao = Annotated[Usuario, Depends(exige_admin_do(Modulo.MANUTENCAO))]


# ---------- montagem das respostas ----------


def _pessoa(usuario: Usuario | None) -> PessoaOut | None:
    return PessoaOut.model_validate(usuario) if usuario else None


def _plano_ref(plano: PlanoPreventiva) -> PlanoRef:
    return PlanoRef.model_validate(plano).model_copy(
        update={"periodicidade": prev.periodicidade(plano.intervalo, plano.unidade)})


def _plano_out(plano: PlanoPreventiva, hoje: date) -> PlanoOut:
    situacoes = [(p, prev.situacao(p, hoje)) for p in plano.preventivas]
    proxima = min((p.data_prevista for p, s in situacoes if s in prev.PENDENTES and p.data_prevista >= hoje),
                  default=None)
    realizadas = sum(p.status == StatusPreventiva.REALIZADA for p, _ in situacoes)
    atrasadas = sum(s == SituacaoPreventiva.ATRASADA for _, s in situacoes)
    nao_realizadas = sum(s == SituacaoPreventiva.NAO_REALIZADA for _, s in situacoes)
    return PlanoOut.model_validate(plano).model_copy(update={
        "periodicidade": prev.periodicidade(plano.intervalo, plano.unidade), "proxima": proxima,
        "previstas": realizadas + atrasadas + nao_realizadas, "realizadas": realizadas, "atrasadas": atrasadas,
    })


def _preventiva_out(p: Preventiva, usuario: Usuario, hoje: date) -> PreventivaOut:
    fiscal = prev.eh_fiscal(usuario)
    programada = p.status == StatusPreventiva.PROGRAMADA
    return PreventivaOut(
        id=p.id, codigo=p.codigo, plano=_plano_ref(p.plano), empresa=EmpresaResumo.model_validate(p.empresa),
        data_prevista=p.data_prevista, limite=prev.limite(p), status=p.status, situacao=prev.situacao(p, hoje),
        dias=(p.data_prevista - hoje).days, realizada_em=p.realizada_em, executor=p.executor, observacao=p.observacao,
        registrada_em=p.registrada_em, registrada_por=_pessoa(p.registrada_por), arquivo_nome=p.arquivo_nome,
        arquivo_mime=p.arquivo_mime, arquivo_tamanho=p.arquivo_tamanho, motivo=p.motivo, atestada_em=p.atestada_em,
        atestada_por=_pessoa(p.atestada_por), ateste_obs=p.ateste_obs,
        # Só dá para registrar o que já está perto: evita "realizar" por engano uma data distante
        pode_realizar=programada and p.data_prevista <= hoje + timedelta(days=prev.ANTECIPACAO_DIAS),
        pode_atestar=fiscal and prev.aguardando_ateste(p),
        pode_nao_realizar=fiscal and programada and p.data_prevista <= hoje,
        pode_reabrir=regras.eh_admin(usuario) and not programada and p.atestada_em is None,
    )


def _buscar(db: Session, preventiva_id: int, usuario: Usuario) -> Preventiva:
    p = db.scalar(select(Preventiva).where(Preventiva.id == preventiva_id, prev.escopo(usuario)))
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preventiva não encontrada")
    return p


def _buscar_plano(db: Session, plano_id: int) -> PlanoPreventiva:
    plano = db.get(PlanoPreventiva, plano_id)
    if plano is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano de preventiva não encontrado")
    return plano


def _exigir_fiscal(usuario: Usuario) -> None:
    if not prev.eh_fiscal(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação permitida apenas para o operacional ou administradores")


def _exigir(p: Preventiva, esperado: StatusPreventiva, acao: str) -> None:
    if p.status != esperado:
        rotulo = {StatusPreventiva.PROGRAMADA: "programada", StatusPreventiva.REALIZADA: "já realizada",
                  StatusPreventiva.NAO_REALIZADA: "marcada como não realizada"}[p.status]
        raise HTTPException(status.HTTP_409_CONFLICT, f"Não é possível {acao} uma preventiva {rotulo}")


# ---------- planos ----------


@router.get("/planos-preventiva", response_model=list[PlanoOut])
def listar_planos(db: DbDep, usuario: UsuarioDep, hoje: HojeDep, empresa_id: int | None = None):
    prev.garantir(db, hoje)
    consulta = select(PlanoPreventiva).where(prev.escopo_planos(usuario))
    if empresa_id is not None:
        consulta = consulta.where(PlanoPreventiva.empresa_id == empresa_id)
    planos = db.scalars(consulta).unique().all()
    planos.sort(key=lambda p: (not p.ativo, p.empresa.nome, p.titulo.lower()))
    return [_plano_out(p, hoje) for p in planos]


@router.post("/planos-preventiva", response_model=PlanoOut, status_code=status.HTTP_201_CREATED)
def criar_plano(dados: PlanoCriar, db: DbDep, admin: AdminManutencao, hoje: HojeDep):
    empresa = db.get(EmpresaManutencao, dados.empresa_id)
    if empresa is None or not empresa.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empresa não encontrada ou inativa")
    if dados.inicio < hoje - timedelta(days=prev.RETROATIVO_DIAS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"A primeira preventiva pode ser de até {prev.RETROATIVO_DIAS} dias atrás")
    plano = PlanoPreventiva(**dados.model_dump(), criado_por_id=admin.id)
    for campo in ("descricao", "local", "equipamento"):
        setattr(plano, campo, (getattr(plano, campo) or "").strip() or None)
    db.add(plano)
    db.flush()
    prev.gerar(db, plano, hoje)
    db.commit()
    db.refresh(plano)
    return _plano_out(plano, hoje)


@router.patch("/planos-preventiva/{plano_id}", response_model=PlanoOut)
def atualizar_plano(plano_id: int, dados: PlanoAtualizar, db: DbDep, _: AdminManutencao, hoje: HojeDep):
    plano = _buscar_plano(db, plano_id)
    mudancas = dados.model_dump(exclude_unset=True)
    agenda_antes = (plano.intervalo, plano.unidade, plano.inicio, plano.ativo)
    for campo, valor in mudancas.items():
        if campo in ("descricao", "local", "equipamento"):
            setattr(plano, campo, (valor or "").strip() or None)
        elif valor is not None:
            setattr(plano, campo, valor)
    if (plano.intervalo, plano.unidade, plano.inicio, plano.ativo) != agenda_antes:
        # Mudou a agenda (ou o plano foi desativado/reativado): as programadas de hoje em diante são refeitas
        prev.refazer_futuras(db, plano, hoje)
    db.commit()
    db.refresh(plano)
    return _plano_out(plano, hoje)


@router.delete("/planos-preventiva/{plano_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_plano(plano_id: int, db: DbDep, _: AdminManutencao, hoje: HojeDep):
    plano = _buscar_plano(db, plano_id)
    com_registro = any(p.status != StatusPreventiva.PROGRAMADA or p.data_prevista < hoje for p in plano.preventivas)
    if com_registro:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "O plano tem preventivas vencidas ou registradas: desative-o em vez de excluir")
    db.delete(plano)
    db.commit()


# ---------- preventivas ----------


@router.get("/preventivas", response_model=PaginaPreventivas,
            summary="Agenda das preventivas, com o previsto x realizado por empresa")
def listar_preventivas(
    db: DbDep, usuario: UsuarioDep, hoje: HojeDep,
    de: date | None = None, ate: date | None = None,
    empresa_id: int | None = None, plano_id: int | None = None,
    situacao: SituacaoPreventiva | None = None,
    aguardando_ateste: bool = Query(False, description="Só as realizadas ainda sem ateste"),
):
    """Sem `de`/`ate`: todas as datas até o horizonte (use com `situacao` ou `aguardando_ateste`)."""
    prev.garantir(db, hoje)
    consulta = select(Preventiva).where(prev.escopo(usuario))
    if de is not None:
        consulta = consulta.where(Preventiva.data_prevista >= de)
    if ate is not None:
        consulta = consulta.where(Preventiva.data_prevista <= ate)
    if empresa_id is not None:
        consulta = consulta.where(Preventiva.empresa_id == empresa_id)
    if plano_id is not None:
        consulta = consulta.where(Preventiva.plano_id == plano_id)
    todas = db.scalars(consulta.order_by(Preventiva.data_prevista, Preventiva.id)).all()
    itens = todas
    if situacao is not None:
        itens = [p for p in itens if prev.situacao(p, hoje) == situacao]
    if aguardando_ateste:
        itens = [p for p in itens if prev.aguardando_ateste(p)]
    return PaginaPreventivas(
        de=de, ate=ate, itens=[_preventiva_out(p, usuario, hoje) for p in itens[:500]],
        # O resumo é do período inteiro (não muda com o filtro de situação)
        resumo=[ResumoPreventivas(**{**r, "empresa": EmpresaResumo.model_validate(r["empresa"])})
                for r in prev.resumo_por_empresa(todas, hoje)],
    )


@router.post("/preventivas/{preventiva_id}/realizar", response_model=PreventivaOut,
             summary="Registra a realização da preventiva, com a evidência (arquivo) opcional")
def realizar(
    preventiva_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep, agora: AgoraDep,
    realizada_em: Annotated[date, Form()],
    executor: Annotated[str | None, Form(max_length=120)] = None,
    observacao: Annotated[str | None, Form(max_length=5000)] = None,
    arquivo: Annotated[UploadFile | None, File()] = None,
):
    p = _buscar(db, preventiva_id, usuario)
    _exigir(p, StatusPreventiva.PROGRAMADA, "registrar a realização de")
    if realizada_em > hoje:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data da realização não pode estar no futuro")
    if realizada_em < p.data_prevista - timedelta(days=prev.ANTECIPACAO_DIAS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"A realização pode ser de até {prev.ANTECIPACAO_DIAS} dias antes da data prevista")
    if arquivo is not None and not arquivo.filename:
        arquivo = None
    salvo = armazenamento.salvar_upload(arquivo, settings) if arquivo is not None else None
    p.status = StatusPreventiva.REALIZADA
    p.realizada_em = realizada_em
    p.executor = (executor or "").strip() or usuario.nome
    p.observacao = (observacao or "").strip() or None
    p.registrada_em, p.registrada_por = agora, usuario
    p.motivo = None
    if salvo:
        p.arquivo_nome, p.arquivo_caminho, p.arquivo_mime = salvo.nome_original, salvo.caminho, salvo.mime_type
        p.arquivo_tamanho, p.arquivo_sha256 = salvo.tamanho_bytes, salvo.hash_sha256
    try:
        db.commit()
    except Exception:
        db.rollback()
        if salvo:
            armazenamento.remover_arquivo(salvo.caminho, settings)
        raise
    return _preventiva_out(p, usuario, hoje)


@router.post("/preventivas/{preventiva_id}/atestar", response_model=PreventivaOut,
             summary="Ateste do fiscal (operacional ou administrador): confirma que o serviço foi feito")
def atestar(preventiva_id: int, dados: Ateste, db: DbDep, usuario: UsuarioDep, hoje: HojeDep, agora: AgoraDep):
    p = _buscar(db, preventiva_id, usuario)
    _exigir_fiscal(usuario)
    _exigir(p, StatusPreventiva.REALIZADA, "atestar")
    if p.atestada_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A preventiva já foi atestada")
    p.atestada_em, p.atestada_por, p.ateste_obs = agora, usuario, (dados.observacao or "").strip() or None
    db.commit()
    return _preventiva_out(p, usuario, hoje)


@router.post("/preventivas/{preventiva_id}/nao-realizada", response_model=PreventivaOut,
             summary="Marca a preventiva como não realizada, com o motivo")
def nao_realizada(preventiva_id: int, dados: MotivoPreventiva, db: DbDep, usuario: UsuarioDep, hoje: HojeDep,
                  agora: AgoraDep):
    p = _buscar(db, preventiva_id, usuario)
    _exigir_fiscal(usuario)
    _exigir(p, StatusPreventiva.PROGRAMADA, "marcar como não realizada")
    if p.data_prevista > hoje:
        raise HTTPException(status.HTTP_409_CONFLICT, "A data prevista ainda não chegou")
    p.status, p.motivo = StatusPreventiva.NAO_REALIZADA, dados.motivo.strip()
    p.registrada_em, p.registrada_por = agora, usuario
    db.commit()
    return _preventiva_out(p, usuario, hoje)


@router.post("/preventivas/{preventiva_id}/reabrir", response_model=PreventivaOut,
             summary="Desfaz o registro (realização ou não realizada) de uma preventiva ainda sem ateste")
def reabrir(preventiva_id: int, db: DbDep, usuario: AdminManutencao, settings: SettingsDep, hoje: HojeDep):
    p = _buscar(db, preventiva_id, usuario)
    if p.status == StatusPreventiva.PROGRAMADA:
        raise HTTPException(status.HTTP_409_CONFLICT, "A preventiva não tem registro para desfazer")
    if p.atestada_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A preventiva já foi atestada e não pode ser reaberta")
    caminho = p.arquivo_caminho
    p.status = StatusPreventiva.PROGRAMADA
    p.realizada_em = p.executor = p.observacao = p.motivo = p.registrada_em = p.registrada_por = None
    p.arquivo_nome = p.arquivo_caminho = p.arquivo_mime = p.arquivo_tamanho = p.arquivo_sha256 = None
    db.commit()
    if caminho:
        armazenamento.remover_arquivo(caminho, settings)  # a evidência do registro desfeito sai junto
    return _preventiva_out(p, usuario, hoje)


@router.get("/preventivas/{preventiva_id}/arquivo", summary="Baixa a evidência da preventiva")
def baixar_evidencia(preventiva_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                     inline: bool = False, bruto: bool = False):
    p = _buscar(db, preventiva_id, usuario)
    if not p.arquivo_caminho:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esta preventiva não tem arquivo")
    caminho = armazenamento.caminho_absoluto(p.arquivo_caminho, settings)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_410_GONE, "O arquivo não está mais no servidor")
    return FileResponse(
        caminho, media_type="application/octet-stream" if bruto else p.arquivo_mime, filename=p.arquivo_nome,
        content_disposition_type="inline" if inline else "attachment", headers={"X-Content-Type-Options": "nosniff"},
    )


# ---------- avisos internos ----------


@router.get("/avisos", response_model=Avisos,
            summary="Pendências do módulo para quem consulta (o sistema não envia e-mail: os avisos ficam aqui)")
def avisos(db: DbDep, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep,
           agora: AgoraDep):
    prev.garantir(db, hoje)
    tecnico = regras.eh_tecnico(usuario)
    itens: list[Aviso] = []

    def aviso(chave: str, nivel: str, quantidade: int, singular: str, plural: str, link: str) -> None:
        if quantidade:
            itens.append(Aviso(chave=chave, nivel=nivel, quantidade=quantidade, link=link,
                               titulo=f"1 {singular}" if quantidade == 1 else f"{quantidade} {plural}"))

    # Chamados em aberto ainda sem diagnóstico
    pendentes = db.scalars(select(Chamado).where(
        regras.escopo(usuario), Chamado.status.in_(ABERTOS), Chamado.diagnosticado_em.is_(None))).all()
    situacoes = [regras.situacao_prazo(c, agora, settings).situacao for c in pendentes]
    atrasados = sum(s == SituacaoPrazo.ATRASADO for s in situacoes)
    vencendo = sum(s == SituacaoPrazo.VENCENDO for s in situacoes)
    aviso("CHAMADOS_ATRASADOS", "CRITICO", atrasados, "chamado com o diagnóstico atrasado",
          "chamados com o diagnóstico atrasado", "/manutencao/chamados?situacao=ATRASADO")
    aviso("CHAMADOS_VENCENDO", "ATENCAO", vencendo, "chamado com o prazo do diagnóstico vencendo",
          "chamados com o prazo do diagnóstico vencendo", "/manutencao/chamados?situacao=VENCENDO")
    if tecnico:
        aviso("CHAMADOS_AGUARDANDO", "INFO", len(pendentes) - atrasados - vencendo,
              "chamado aguardando o seu diagnóstico", "chamados aguardando o seu diagnóstico",
              "/manutencao/chamados?situacao=NO_PRAZO")

    # Preventivas
    abertas = db.scalars(select(Preventiva).where(
        prev.escopo(usuario), Preventiva.status == StatusPreventiva.PROGRAMADA,
        Preventiva.data_prevista <= hoje + timedelta(days=prev.AVISO_DIAS))).all()
    sit = [prev.situacao(p, hoje) for p in abertas]
    aviso("PREVENTIVAS_ATRASADAS", "CRITICO", sum(s == SituacaoPreventiva.ATRASADA for s in sit),
          "preventiva atrasada", "preventivas atrasadas", "/manutencao/preventivas?situacao=ATRASADA&todos=1")
    aviso("PREVENTIVAS_NA_JANELA", "ATENCAO", sum(s == SituacaoPreventiva.NA_JANELA for s in sit),
          "preventiva para realizar agora", "preventivas para realizar agora",
          "/manutencao/preventivas?situacao=NA_JANELA&todos=1")
    if not tecnico:
        sem_ateste = db.scalars(select(Preventiva).where(
            Preventiva.status == StatusPreventiva.REALIZADA, Preventiva.atestada_em.is_(None))).all()
        aviso("PREVENTIVAS_SEM_ATESTE", "ATENCAO", len(sem_ateste), "preventiva realizada aguardando o ateste",
              "preventivas realizadas aguardando o ateste", "/manutencao/preventivas?ateste=1&todos=1")

    ordem = {"CRITICO": 0, "ATENCAO": 1, "INFO": 2}
    itens.sort(key=lambda a: ordem[a.nivel])
    return Avisos(total=sum(a.quantidade for a in itens if a.nivel != "INFO"), itens=itens)
