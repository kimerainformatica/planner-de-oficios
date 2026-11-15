"""Módulo Manutenção Clínica: helpdesk de chamados técnicos (regras em services/manutencao.py).

Todas as rotas exigem acesso ao módulo (o MASTER sempre tem).
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.deps import AgoraDep, DbDep, SettingsDep, UsuarioDep, exige_acesso_ao, exige_admin_do
from app.models import (
    Anexo,
    Chamado,
    ChamadoInteracao,
    EmpresaManutencao,
    Modulo,
    Oficio,
    Perfil,
    RelatorioTecnico,
    StatusChamado,
    TipoInteracao,
    TipoOficio,
    Usuario,
    UsuarioModulo,
)
from app.schemas import OficioCriar
from app.schemas_manutencao import (
    ChamadoCriar,
    ChamadoDetalhe,
    ChamadoOut,
    ColunaQuadro,
    Conclusao,
    CorrecaoDiagnostico,
    RelatorioAtualizar,
    RespostaAtualizar,
    OficioDisponivel,
    OficioResumo,
    OficioVinculado,
    QuadroOut,
    ResumoQuadro,
    SolicitacaoPecasCriar,
    TipoSolicitacao,
    EmpresaAtualizar,
    EmpresaCriar,
    EmpresaOut,
    EmpresaResumo,
    InteracaoOut,
    Motivo,
    PaginaChamados,
    PainelEmpresa,
    PainelManutencao,
    PrazoOut,
    RelatorioCriar,
    RelatorioOut,
)
from app.services import armazenamento
from app.services import manutencao as regras
from app.services.manutencao import ABERTOS, SituacaoPrazo
from app.services.auditoria import Acao
from app.services.auditoria import registrar as registrar_atividade
from app.services.modulos import CATALOGO
from app.services.oficios import cadastrar_oficio
from app.services.oficios import escopo as escopo_planner
from app.services.relatorio_tecnico import gerar_pdf

router = APIRouter(
    prefix="/api/manutencao", tags=["Manutenção Clínica"], dependencies=[Depends(exige_acesso_ao(Modulo.MANUTENCAO))]
)
AdminManutencao = Annotated[Usuario, Depends(exige_admin_do(Modulo.MANUTENCAO))]


# ---------- montagem das respostas ----------


def _chamado_out(c: Chamado, agora, settings) -> ChamadoOut:
    p = regras.situacao_prazo(c, agora, settings)
    # atributos só para a resposta (não são colunas)
    c.prazo = PrazoOut(situacao=p.situacao, horas_restantes=p.horas_restantes,
                       horas_ate_diagnostico=p.horas_ate_diagnostico)
    c.execucao_horas = (
        regras.horas_entre(c.diagnosticado_em, agora)
        if c.diagnosticado_em is not None and c.status in ABERTOS else None
    )
    c.oficios_pendentes = regras.oficios_pendentes(c)
    c.oficios_resumo = [OficioResumo(id=o.id, numero=o.numero, status=o.status) for o in _oficios(c)]
    return ChamadoOut.model_validate(c)


def _oficios(c: Chamado) -> list[Oficio]:
    """Ofícios do chamado na ordem do cadastro (um recém-vinculado entra no fim da lista em memória)."""
    return sorted(c.oficios, key=lambda o: o.id)


def _detalhe(c: Chamado, usuario: Usuario, agora, settings) -> ChamadoDetalhe:
    atendente = regras.eh_tecnico(usuario) or regras.eh_admin(usuario)
    solicitante = regras.eh_operacional(usuario) or regras.eh_admin(usuario)
    pode_oficios = solicitante and c.status in ABERTOS
    interacoes = []
    for i in c.interacoes:
        dados = InteracaoOut.model_validate(i)
        dados.autor_papel = i.autor.perfil_no(Modulo.MANUTENCAO) if i.autor else None
        interacoes.append(dados)
    oficios = [
        OficioVinculado.model_validate(o).model_copy(update={
            "tipo_nome": o.tipo_info.nome if o.tipo_info else o.tipo, "dono_nome": o.dono.nome if o.dono else None,
            "pode_desvincular": pode_oficios and regras.pode_desvincular(usuario, o),
        })
        for o in _oficios(c)
    ]
    return ChamadoDetalhe(
        **_chamado_out(c, agora, settings).model_dump(),
        interacoes=interacoes,
        oficios=oficios,
        pode_solicitar_pecas=pode_oficios,
        pode_assumir=regras.eh_tecnico(usuario) and c.status in ABERTOS and c.tecnico_id != usuario.id,
        pode_responder=atendente and c.status in ABERTOS,
        pode_comentar=c.status != StatusChamado.CANCELADO,
        pode_concluir=atendente and c.status in ABERTOS and c.diagnosticado_em is not None,
        pode_corrigir_diagnostico=atendente and c.diagnosticado_em is not None and c.status != StatusChamado.CANCELADO,
        diagnostico_interacao_id=principal.id if (principal := regras.interacao_do_diagnostico(c)) else None,
        pode_reabrir=solicitante and c.status == StatusChamado.CONCLUIDO,
        pode_cancelar=solicitante and c.status in ABERTOS,
    )


# ---------- módulo ----------


class ResumoManutencao(BaseModel):
    modulo: Modulo
    nome: str
    perfil: Perfil  # papel de quem consulta neste módulo
    eh_admin: bool
    eh_tecnico: bool
    empresa: EmpresaResumo | None


@router.get("/resumo", response_model=ResumoManutencao)
def resumo(usuario: UsuarioDep, db: DbDep):
    """Identificação do módulo e do papel do usuário nele (o técnico vem com a empresa dele)."""
    empresa_id = regras.empresa_do_tecnico(usuario)
    empresa = db.get(EmpresaManutencao, empresa_id) if empresa_id else None
    return ResumoManutencao(
        modulo=Modulo.MANUTENCAO, nome=CATALOGO[Modulo.MANUTENCAO].nome, perfil=regras.papel(usuario),
        eh_admin=regras.eh_admin(usuario), eh_tecnico=regras.eh_tecnico(usuario),
        empresa=EmpresaResumo.model_validate(empresa) if empresa else None,
    )


@router.get("/painel", response_model=PainelManutencao)
def painel(db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep):
    chamados = db.scalars(select(Chamado).where(regras.escopo(usuario))).all()
    situacoes = {c.id: regras.situacao_prazo(c, agora, settings) for c in chamados}
    abertos = [c for c in chamados if c.status in ABERTOS]

    por_empresa = []
    empresas = {c.empresa_id: c.empresa for c in chamados}
    for empresa in sorted(empresas.values(), key=lambda e: e.nome):
        doe = [c for c in chamados if c.empresa_id == empresa.id]
        diag = [situacoes[c.id] for c in doe if c.diagnosticado_em is not None]
        horas = [s.horas_ate_diagnostico for s in diag if s.horas_ate_diagnostico is not None]
        solucoes = [c.solucao_horas_corridas for c in doe if c.solucao_horas_corridas is not None]
        por_empresa.append(PainelEmpresa(
            empresa=EmpresaResumo.model_validate(empresa),
            abertos=sum(c.status in ABERTOS for c in doe),
            aguardando_diagnostico=sum(c.status in ABERTOS and c.diagnosticado_em is None for c in doe),
            atrasados=sum(situacoes[c.id].situacao == SituacaoPrazo.ATRASADO for c in doe),
            concluidos=sum(c.status == StatusChamado.CONCLUIDO for c in doe),
            diagnosticados=len(diag),
            no_prazo_pct=round(100 * sum(s.situacao == SituacaoPrazo.CUMPRIDO for s in diag) / len(diag), 1)
            if diag else None,
            media_horas_diagnostico=round(sum(horas) / len(horas), 1) if horas else None,
            media_horas_solucao=round(sum(solucoes) / len(solucoes), 1) if solucoes else None,
        ))

    pendentes = [c for c in abertos if c.diagnosticado_em is None]
    pendentes.sort(key=lambda c: c.prazo_em)
    empresa_id = regras.empresa_do_tecnico(usuario)
    empresa_tec = db.get(EmpresaManutencao, empresa_id) if empresa_id else None
    return PainelManutencao(
        papel=regras.papel(usuario), eh_admin=regras.eh_admin(usuario),
        empresa_do_tecnico=EmpresaResumo.model_validate(empresa_tec) if empresa_tec else None,
        abertos=sum(c.status == StatusChamado.ABERTO for c in chamados),
        em_atendimento=sum(c.status == StatusChamado.EM_ATENDIMENTO for c in chamados),
        aguardando_diagnostico=len(pendentes),
        vencendo=sum(situacoes[c.id].situacao == SituacaoPrazo.VENCENDO for c in pendentes),
        atrasados=sum(situacoes[c.id].situacao == SituacaoPrazo.ATRASADO for c in pendentes),
        concluidos=sum(c.status == StatusChamado.CONCLUIDO for c in chamados),
        cancelados=sum(c.status == StatusChamado.CANCELADO for c in chamados),
        por_empresa=por_empresa,
        urgentes=[_chamado_out(c, agora, settings) for c in pendentes[:8]],
    )


# ---------- empresas ----------


def _empresa_out(db: Session, e: EmpresaManutencao) -> EmpresaOut:
    tecnicos = db.scalar(select(func.count()).select_from(UsuarioModulo).where(
        UsuarioModulo.empresa_id == e.id, UsuarioModulo.perfil == Perfil.TECNICO))
    chamados = db.scalar(select(func.count()).select_from(Chamado).where(Chamado.empresa_id == e.id))
    out = EmpresaOut.model_validate(e)
    out.tecnicos, out.chamados = tecnicos or 0, chamados or 0
    return out


@router.get("/empresas", response_model=list[EmpresaOut])
def listar_empresas(db: DbDep, _: UsuarioDep, ativas: bool = False):
    consulta = select(EmpresaManutencao).order_by(EmpresaManutencao.nome)
    if ativas:
        consulta = consulta.where(EmpresaManutencao.ativo.is_(True))
    return [_empresa_out(db, e) for e in db.scalars(consulta)]


def _nome_livre(db: Session, nome: str, exceto: int | None = None) -> None:
    consulta = select(EmpresaManutencao.id).where(func.lower(EmpresaManutencao.nome) == nome.lower())
    if exceto is not None:
        consulta = consulta.where(EmpresaManutencao.id != exceto)
    if db.scalar(consulta):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe a empresa {nome}")


@router.post("/empresas", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def criar_empresa(dados: EmpresaCriar, db: DbDep, _: AdminManutencao):
    _nome_livre(db, dados.nome)
    empresa = EmpresaManutencao(**dados.model_dump())
    db.add(empresa)
    db.commit()
    return _empresa_out(db, empresa)


@router.patch("/empresas/{empresa_id}", response_model=EmpresaOut)
def atualizar_empresa(empresa_id: int, dados: EmpresaAtualizar, db: DbDep, _: AdminManutencao):
    empresa = db.get(EmpresaManutencao, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada")
    if dados.nome is not None:
        _nome_livre(db, dados.nome, exceto=empresa.id)
    # O novo prazo vale para os próximos chamados; os já abertos mantêm o prazo da abertura
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if valor is not None or campo == "descricao":
            setattr(empresa, campo, valor)
    db.commit()
    return _empresa_out(db, empresa)


@router.delete("/empresas/{empresa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_empresa(empresa_id: int, db: DbDep, _: AdminManutencao):
    empresa = db.get(EmpresaManutencao, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa não encontrada")
    out = _empresa_out(db, empresa)
    if out.chamados or out.tecnicos:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "A empresa tem chamados ou técnicos: desative-a em vez de excluir")
    db.delete(empresa)
    db.commit()


# ---------- chamados ----------


@router.get("/chamados", response_model=PaginaChamados)
def listar_chamados(
    db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep,
    status_: Annotated[list[StatusChamado] | None, Query(alias="status")] = None,
    empresa_id: int | None = None,
    situacao: SituacaoPrazo | None = None,
    busca: str | None = None,
    meus: bool = Query(False, description="Só os que eu abri ou dos quais sou o técnico responsável"),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
):
    consulta = select(Chamado).where(regras.escopo(usuario))
    if status_:
        consulta = consulta.where(Chamado.status.in_(status_))
    if empresa_id is not None:
        consulta = consulta.where(Chamado.empresa_id == empresa_id)
    if meus:
        consulta = consulta.where(or_(Chamado.solicitante_id == usuario.id, Chamado.tecnico_id == usuario.id))
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        numero = busca.strip().upper().removeprefix("CH-").lstrip("0")
        filtros = [Chamado.titulo.ilike(termo), Chamado.descricao.ilike(termo), Chamado.local.ilike(termo),
                   Chamado.equipamento.ilike(termo)]
        if numero.isdigit():
            filtros.append(Chamado.id == int(numero))
        consulta = consulta.where(or_(*filtros))
    # Em aberto primeiro (o prazo mais próximo no topo); depois os encerrados, do mais recente
    chamados = db.scalars(consulta.order_by(Chamado.aberto_em.desc())).all()
    itens = [_chamado_out(c, agora, settings) for c in chamados]
    if situacao is not None:
        itens = [c for c in itens if c.prazo.situacao == situacao]
    itens.sort(key=lambda c: (c.status not in ABERTOS, c.prazo_em if c.status in ABERTOS else -c.aberto_em.timestamp()))
    inicio = (pagina - 1) * por_pagina
    return PaginaChamados(itens=itens[inicio:inicio + por_pagina], total=len(itens), pagina=pagina,
                          por_pagina=por_pagina)


@router.post("/chamados", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED)
def abrir_chamado(dados: ChamadoCriar, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                  agora: AgoraDep):
    regras.exigir_solicitante(usuario)
    empresa = db.get(EmpresaManutencao, dados.empresa_id)
    if empresa is None or not empresa.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empresa não encontrada ou inativa")
    ocorrido = (dados.ocorrido_em or agora).replace(tzinfo=None, microsecond=0)
    if ocorrido > agora + timedelta(minutes=10):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data e hora do problema não pode estar no futuro")

    chamado = Chamado(
        empresa=empresa, solicitante=usuario, titulo=dados.titulo, descricao=dados.descricao, local=dados.local or None,
        equipamento=dados.equipamento or None, ocorrido_em=ocorrido, aberto_em=agora,
        prazo_horas=empresa.prazo_horas, prazo_em=regras.prazo_do_chamado(agora, empresa.prazo_horas),
        status=StatusChamado.ABERTO, atualizado_em=agora,
    )
    db.add(chamado)
    regras.registrar(db, chamado, usuario, TipoInteracao.ABERTURA, agora,
                     f"Chamado aberto para {empresa.nome}. Prazo para o diagnóstico: {regras.texto_horas(empresa.prazo_horas)} "
                     f"corridas, até {chamado.prazo_em:%d/%m/%Y %H:%M}.")
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.get("/chamados/{chamado_id}", response_model=ChamadoDetalhe)
def ver_chamado(chamado_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    return _detalhe(chamado, usuario, agora, settings)


@router.post("/chamados/{chamado_id}/assumir", response_model=ChamadoDetalhe)
def assumir(chamado_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
            agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    if not regras.eh_tecnico(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só técnicos assumem chamados")
    regras.exigir_status(chamado, ABERTOS, "assumir")
    anterior = chamado.tecnico.nome if chamado.tecnico else None
    chamado.tecnico = usuario
    if chamado.status == StatusChamado.ABERTO:
        chamado.status = StatusChamado.EM_ATENDIMENTO
    texto = f"{usuario.nome} assumiu o chamado" + (f" (antes com {anterior})" if anterior else "")
    regras.registrar(db, chamado, usuario, TipoInteracao.ASSUMIDO, agora, texto)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.post("/chamados/{chamado_id}/interacoes", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED,
             summary="Comentário ou resposta técnica (diagnóstico), com arquivo opcional (ex.: relatório externo)")
def responder(
    chamado_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep,
    texto: Annotated[str | None, Form(max_length=10000)] = None,
    diagnostico: Annotated[bool, Form(description="Resposta técnica: a primeira encerra o prazo")] = False,
    diagnosticado_em: Annotated[datetime | None, Form(
        description="Resposta técnica: data e hora em que o diagnóstico foi feito (padrão: agora)")] = None,
    arquivo: Annotated[UploadFile | None, File()] = None,
):
    chamado = regras.buscar(db, chamado_id, usuario)
    texto = (texto or "").strip() or None
    if arquivo is not None and not arquivo.filename:
        arquivo = None
    if texto is None and arquivo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Escreva uma mensagem ou anexe um arquivo")
    quando = None
    if diagnostico:
        regras.exigir_atendente(usuario)
        regras.exigir_status(chamado, ABERTOS, "responder")
        quando = regras.validar_data_resposta(chamado, diagnosticado_em or agora, agora,
                                              principal=chamado.diagnosticado_em is None)
    elif chamado.status == StatusChamado.CANCELADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "O chamado foi cancelado")

    salvo = armazenamento.salvar_upload(arquivo, settings) if arquivo is not None else None
    extra = {}
    if salvo:
        extra = dict(arquivo_nome=salvo.nome_original, arquivo_caminho=salvo.caminho, arquivo_mime=salvo.mime_type,
                     arquivo_tamanho=salvo.tamanho_bytes, arquivo_sha256=salvo.hash_sha256)
    tipo = TipoInteracao.DIAGNOSTICO if diagnostico else TipoInteracao.COMENTARIO
    regras.registrar(db, chamado, usuario, tipo, agora, texto, ocorrido_em=quando, **extra)
    if diagnostico:
        regras.marcar_diagnostico(chamado, usuario, quando)
    elif regras.eh_tecnico(usuario) and chamado.status in ABERTOS:
        regras.marcar_atendimento(chamado, usuario)
    try:
        db.commit()
    except Exception:
        db.rollback()
        if salvo:
            armazenamento.remover_arquivo(salvo.caminho, settings)
        raise
    return _detalhe(chamado, usuario, agora, settings)


@router.post("/chamados/{chamado_id}/relatorios", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED,
             summary="Relatório técnico no modelo do sistema (conta como diagnóstico)")
def criar_relatorio(chamado_id: int, dados: RelatorioCriar, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                    agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_atendente(usuario)
    regras.exigir_status(chamado, ABERTOS, "registrar relatório em")
    atendido = (dados.atendido_em or agora).replace(tzinfo=None, microsecond=0)
    if atendido > agora + timedelta(minutes=10):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data do atendimento não pode estar no futuro")
    # Primeiro diagnóstico: a data e a hora do atendimento são as do diagnóstico; senão, é um complemento
    atendido = regras.validar_data_resposta(chamado, atendido, agora, principal=chamado.diagnosticado_em is None)
    relatorio = RelatorioTecnico(
        chamado=chamado, tecnico=usuario, empresa=chamado.empresa, criado_em=agora, atendido_em=atendido,
        **dados.model_dump(exclude={"atendido_em"}),
    )
    db.add(relatorio)
    db.flush()  # o relatório precisa de id para o código RT-…
    regras.registrar(db, chamado, usuario, TipoInteracao.RELATORIO, agora,
                     f"Relatório técnico {relatorio.codigo} registrado", relatorio=relatorio, ocorrido_em=atendido)
    regras.marcar_diagnostico(chamado, usuario, atendido)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.patch("/chamados/{chamado_id}/diagnostico", response_model=ChamadoDetalhe,
              summary="Corrige a data e a hora do diagnóstico (fica registrado na linha do tempo)")
def corrigir_diagnostico(chamado_id: int, dados: CorrecaoDiagnostico, db: DbDep, usuario: UsuarioDep,
                         settings: SettingsDep, agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_atendente(usuario)
    if chamado.status == StatusChamado.CANCELADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "O chamado foi cancelado")
    if chamado.diagnosticado_em is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O chamado ainda não tem diagnóstico")
    novo = regras.validar_data_diagnostico(chamado, dados.diagnosticado_em, agora)
    anterior = chamado.diagnosticado_em
    if novo == anterior:
        raise HTTPException(status.HTTP_409_CONFLICT, "O diagnóstico já está com essa data e hora")
    regras.aplicar_data(chamado, regras.interacao_do_diagnostico(chamado), novo)
    texto = f"Data e hora do diagnóstico corrigidas: de {anterior:%d/%m/%Y %H:%M} para {novo:%d/%m/%Y %H:%M}."
    if dados.motivo and dados.motivo.strip():
        texto += f"\nMotivo: {dados.motivo.strip()}"
    regras.registrar(db, chamado, usuario, TipoInteracao.CORRECAO, agora, texto)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


# ---------- edição do diagnóstico e dos complementos (seção Diagnóstico técnico) ----------

ROTULO_CAMPO_RELATORIO = {
    "equipamento": "equipamento", "identificacao": "patrimônio / nº de série", "diagnostico": "diagnóstico",
    "causa": "causa provável", "servico_executado": "serviço executado", "pecas": "peças e materiais",
    "situacao_equipamento": "situação do equipamento", "recomendacoes": "recomendações",
}


def _registro_tecnico(db: Session, interacao_id: int, usuario: Usuario) -> tuple[ChamadoInteracao, Chamado]:
    """Resposta técnica ou relatório que o usuário pode editar (técnico da empresa ou administrador)."""
    interacao = db.get(ChamadoInteracao, interacao_id)
    if interacao is None or interacao.tipo not in (TipoInteracao.DIAGNOSTICO, TipoInteracao.RELATORIO):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resposta técnica não encontrada")
    chamado = regras.buscar(db, interacao.chamado_id, usuario)
    regras.exigir_atendente(usuario)
    if chamado.status == StatusChamado.CANCELADO:
        raise HTTPException(status.HTTP_409_CONFLICT, "O chamado foi cancelado")
    return interacao, chamado


def _mudar_data(chamado: Chamado, interacao: ChamadoInteracao, quando: datetime, agora) -> str | None:
    principal = interacao is regras.interacao_do_diagnostico(chamado)
    novo = regras.validar_data_resposta(chamado, quando, agora, principal=principal)
    anterior = interacao.ocorrido_em or interacao.criado_em
    if novo == anterior:
        return None
    regras.aplicar_data(chamado, interacao, novo)
    return f"data e hora de {anterior:%d/%m/%Y %H:%M} para {novo:%d/%m/%Y %H:%M}"


def _registrar_edicao(db: Session, chamado: Chamado, interacao: ChamadoInteracao, usuario: Usuario, agora,
                      mudancas: list[str], motivo: str | None) -> None:
    if not mudancas:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nada foi alterado")
    texto = f"{regras.rotulo_registro(chamado, interacao)} editado: {'; '.join(mudancas)}."
    if motivo and motivo.strip():
        texto += f"\nMotivo: {motivo.strip()}"
    regras.registrar(db, chamado, usuario, TipoInteracao.CORRECAO, agora, texto)


@router.patch("/interacoes/{interacao_id}", response_model=ChamadoDetalhe,
              summary="Edita uma resposta técnica (diagnóstico ou complemento): data e hora e resumo")
def editar_resposta(interacao_id: int, dados: RespostaAtualizar, db: DbDep, usuario: UsuarioDep,
                    settings: SettingsDep, agora: AgoraDep):
    interacao, chamado = _registro_tecnico(db, interacao_id, usuario)
    campos = dados.model_fields_set
    mudancas = []
    if "ocorrido_em" in campos and dados.ocorrido_em is not None:
        if (m := _mudar_data(chamado, interacao, dados.ocorrido_em, agora)):
            mudancas.append(m)
    if "texto" in campos:
        if interacao.relatorio is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Edite o relatório técnico pelos campos dele")
        texto = (dados.texto or "").strip() or None
        if texto is None and not interacao.arquivo_caminho:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "Escreva o resumo do diagnóstico ou anexe o relatório externo")
        if texto != interacao.texto:
            interacao.texto = texto
            mudancas.append("resumo do diagnóstico")
    _registrar_edicao(db, chamado, interacao, usuario, agora, mudancas, dados.motivo)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.patch("/relatorios/{relatorio_id}", response_model=ChamadoDetalhe,
              summary="Edita o relatório técnico (campos e data do atendimento; o PDF acompanha)")
def editar_relatorio(relatorio_id: int, dados: RelatorioAtualizar, db: DbDep, usuario: UsuarioDep,
                     settings: SettingsDep, agora: AgoraDep):
    relatorio = db.get(RelatorioTecnico, relatorio_id)
    if relatorio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado")
    chamado = regras.buscar(db, relatorio.chamado_id, usuario)
    interacao = next((i for i in chamado.interacoes if i.relatorio_id == relatorio.id), None)
    if interacao is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado")
    interacao, chamado = _registro_tecnico(db, interacao.id, usuario)
    campos = dados.model_fields_set - {"motivo", "atendido_em"}
    mudancas = []
    if "atendido_em" in dados.model_fields_set and dados.atendido_em is not None:
        if (m := _mudar_data(chamado, interacao, dados.atendido_em, agora)):
            mudancas.append(m.replace("data e hora", "data e hora do atendimento", 1))
    alterados = []
    for campo in ROTULO_CAMPO_RELATORIO:
        if campo not in campos:
            continue
        valor = getattr(dados, campo)
        if isinstance(valor, str):
            valor = valor.strip() or None
        if campo == "diagnostico" and not valor:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O diagnóstico do relatório é obrigatório")
        if campo == "situacao_equipamento" and valor is None:
            continue
        if valor != getattr(relatorio, campo):
            setattr(relatorio, campo, valor)
            alterados.append(ROTULO_CAMPO_RELATORIO[campo])
    if alterados:
        mudancas.append(", ".join(alterados))
    _registrar_edicao(db, chamado, interacao, usuario, agora, mudancas, dados.motivo)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.put("/interacoes/{interacao_id}/arquivo", response_model=ChamadoDetalhe,
            summary="Anexa ou substitui o relatório externo de uma resposta técnica ou de um relatório")
def anexar_relatorio_externo(
    interacao_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep,
    arquivo: Annotated[UploadFile, File()],
    motivo: Annotated[str | None, Form(max_length=2000)] = None,
):
    """O arquivo anterior não é apagado: fica no registro da correção, na linha do tempo, e pode ser baixado."""
    interacao, chamado = _registro_tecnico(db, interacao_id, usuario)
    if not arquivo.filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Escolha o arquivo do relatório externo")
    salvo = armazenamento.salvar_upload(arquivo, settings)
    campos = ("arquivo_nome", "arquivo_caminho", "arquivo_mime", "arquivo_tamanho", "arquivo_sha256")
    anterior = {c: getattr(interacao, c) for c in campos} if interacao.arquivo_caminho else None
    interacao.arquivo_nome, interacao.arquivo_caminho, interacao.arquivo_mime = (
        salvo.nome_original, salvo.caminho, salvo.mime_type)
    interacao.arquivo_tamanho, interacao.arquivo_sha256 = salvo.tamanho_bytes, salvo.hash_sha256
    rotulo = regras.rotulo_registro(chamado, interacao)
    # Anexado por quem registrou, logo depois do registro (ex.: relatório do sistema + arquivo da empresa no mesmo
    # envio): faz parte do registro, não é uma correção
    junto_do_registro = (anterior is None and interacao.autor_id == usuario.id
                         and agora - interacao.criado_em <= timedelta(minutes=10))
    if anterior:
        texto = (f"{rotulo}: relatório externo substituído por {salvo.nome_original}. "
                 f"O arquivo anterior ({anterior['arquivo_nome']}) fica guardado neste registro.")
    else:
        texto = f"{rotulo}: relatório externo anexado ({salvo.nome_original})."
    if motivo and motivo.strip():
        texto += f"\nMotivo: {motivo.strip()}"
    if junto_do_registro:
        chamado.atualizado_em = agora
    else:
        regras.registrar(db, chamado, usuario, TipoInteracao.CORRECAO, agora, texto, **(anterior or {}))
    try:
        db.commit()
    except Exception:
        db.rollback()
        armazenamento.remover_arquivo(salvo.caminho, settings)
        raise
    return _detalhe(chamado, usuario, agora, settings)


@router.get("/relatorios/{relatorio_id}", response_model=RelatorioOut)
def ver_relatorio(relatorio_id: int, db: DbDep, usuario: UsuarioDep):
    relatorio = db.get(RelatorioTecnico, relatorio_id)
    if relatorio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado")
    regras.buscar(db, relatorio.chamado_id, usuario)  # respeita a visibilidade do chamado
    return relatorio


@router.get("/relatorios/{relatorio_id}/pdf", summary="PDF do relatório técnico")
def pdf_relatorio(relatorio_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                  bruto: Annotated[bool, Query(description="application/octet-stream (usado pelo front-end)")] = False):
    relatorio = db.get(RelatorioTecnico, relatorio_id)
    if relatorio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relatório não encontrado")
    chamado = regras.buscar(db, relatorio.chamado_id, usuario)
    conteudo = gerar_pdf(relatorio, chamado, settings.unidade_nome.strip() or None)
    nome = f"relatorio-{relatorio.codigo}-{chamado.codigo}.pdf"
    return Response(
        conteudo, media_type="application/octet-stream" if bruto else "application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"', "X-Content-Type-Options": "nosniff"},
    )


@router.get("/interacoes/{interacao_id}/arquivo", summary="Baixa o arquivo de uma interação do chamado")
def baixar_arquivo(interacao_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                   inline: bool = False, bruto: bool = False):
    interacao = db.get(ChamadoInteracao, interacao_id)
    if interacao is None or not interacao.arquivo_caminho:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado")
    regras.buscar(db, interacao.chamado_id, usuario)
    caminho = armazenamento.caminho_absoluto(interacao.arquivo_caminho, settings)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_410_GONE, "O arquivo não está mais no servidor")
    return FileResponse(
        caminho, media_type="application/octet-stream" if bruto else interacao.arquivo_mime,
        filename=interacao.arquivo_nome, content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/quadro", response_model=QuadroOut, summary="Quadro de acompanhamento dos chamados (por etapa)")
def quadro(
    db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep,
    meus: bool = Query(False, description="Só os que assumi (técnico) ou abri (operacional)"),
    empresa_id: int | None = None,
    dias: int = Query(30, ge=1, le=365, description="Concluídos e indicadores dos últimos N dias"),
):
    consulta = select(Chamado).where(regras.escopo(usuario), Chamado.status != StatusChamado.CANCELADO)
    if empresa_id is not None:
        consulta = consulta.where(Chamado.empresa_id == empresa_id)
    if meus:
        consulta = consulta.where(or_(Chamado.tecnico_id == usuario.id, Chamado.solicitante_id == usuario.id))
    chamados = db.scalars(consulta).all()
    inicio = agora - timedelta(days=dias)

    abertos = [c for c in chamados if c.status in ABERTOS]
    pecas = [c for c in abertos if regras.oficios_pendentes(c)]
    sem_diag = [c for c in abertos if c not in pecas and c.diagnosticado_em is None]
    execucao = [c for c in abertos if c not in pecas and c.diagnosticado_em is not None]
    concluidos = [c for c in chamados if c.status == StatusChamado.CONCLUIDO and c.concluido_em >= inicio]
    sem_diag.sort(key=lambda c: c.prazo_em)
    execucao.sort(key=lambda c: c.diagnosticado_em)
    pecas.sort(key=lambda c: c.aberto_em)
    concluidos.sort(key=lambda c: c.concluido_em, reverse=True)

    def out(lista):
        return [_chamado_out(c, agora, settings) for c in lista]

    situacoes = {c.id: regras.situacao_prazo(c, agora, settings) for c in chamados}
    diag_periodo = [situacoes[c.id] for c in chamados if c.diagnosticado_em is not None and c.diagnosticado_em >= inicio]
    horas_diag = [s.horas_ate_diagnostico for s in diag_periodo if s.horas_ate_diagnostico is not None]
    solucoes = [c.solucao_horas_corridas for c in concluidos if c.solucao_horas_corridas is not None]

    empresa_ref = empresa_id or regras.empresa_do_tecnico(usuario)
    empresa = db.get(EmpresaManutencao, empresa_ref) if empresa_ref else None
    return QuadroOut(
        empresa=EmpresaResumo.model_validate(empresa) if empresa else None, meus=meus, dias=dias,
        resumo=ResumoQuadro(
            em_aberto=len(abertos),
            aguardando_diagnostico=sum(c.diagnosticado_em is None for c in abertos),
            atrasados=sum(situacoes[c.id].situacao == SituacaoPrazo.ATRASADO for c in abertos),
            aguardando_pecas=len(pecas),
            concluidos_periodo=len(concluidos),
            diagnostico_no_prazo_pct=round(
                100 * sum(s.situacao == SituacaoPrazo.CUMPRIDO for s in diag_periodo) / len(diag_periodo), 1)
            if diag_periodo else None,
            media_horas_diagnostico=round(sum(horas_diag) / len(horas_diag), 1) if horas_diag else None,
            media_horas_solucao=round(sum(solucoes) / len(solucoes), 1) if solucoes else None,
        ),
        colunas=[
            ColunaQuadro(chave="AGUARDANDO_DIAGNOSTICO", titulo="Aguardando diagnóstico",
                         descricao="O prazo está correndo: o mais perto do vencimento primeiro.", chamados=out(sem_diag)),
            ColunaQuadro(chave="EM_EXECUCAO", titulo="Em execução",
                         descricao="Diagnosticados, com o serviço em andamento.", chamados=out(execucao)),
            ColunaQuadro(chave="AGUARDANDO_PECAS", titulo="Aguardando peças / equipamentos",
                         descricao="Com ofício no Planner de Ofícios ainda sem resposta ou entrega.", chamados=out(pecas)),
            ColunaQuadro(chave="CONCLUIDOS", titulo=f"Concluídos ({dias} dias)",
                         descricao="Com o tempo de solução depois do diagnóstico.", chamados=out(concluidos)),
        ],
    )


# ---------- solicitação de peças e equipamentos (ofício no Planner) ----------


@router.get("/tipos-solicitacao", response_model=list[TipoSolicitacao])
def tipos_solicitacao(db: DbDep, _: UsuarioDep):
    """Tipos de ofício aceitos na solicitação de peças/equipamentos (os ativos no Planner)."""
    tipos = db.scalars(select(TipoOficio).where(
        TipoOficio.codigo.in_(regras.TIPOS_SOLICITACAO), TipoOficio.ativo.is_(True)).order_by(TipoOficio.ordem))
    return [TipoSolicitacao(codigo=t.codigo, nome=t.nome) for t in tipos]


@router.post("/chamados/{chamado_id}/oficios", response_model=ChamadoDetalhe, status_code=status.HTTP_201_CREATED,
             summary="Solicita peças ou equipamentos: cadastra um ofício no Planner ligado ao chamado")
def solicitar_pecas(chamado_id: int, dados: SolicitacaoPecasCriar, db: DbDep, usuario: UsuarioDep,
                    settings: SettingsDep, agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_solicitante(usuario)
    regras.exigir_status(chamado, ABERTOS, "solicitar peças para")
    if dados.tipo not in regras.TIPOS_SOLICITACAO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use o tipo de peças ou de equipamentos")
    observacao = (f"Solicitação de peças/equipamentos do chamado {chamado.codigo} ({chamado.empresa.nome}): "
                  f"{chamado.titulo}.\nItens: {dados.itens}")
    try:
        oficio_dados = OficioCriar(
            numero=dados.numero, data_oficio=dados.data_oficio, tipo=dados.tipo, protocolo=dados.protocolo,
            destinatario_tipo=dados.destinatario_tipo, destinatario_setor=dados.destinatario_setor,
            observacao=observacao,
        )
    except ValidationError as erro:
        mensagem = "; ".join(e["msg"].removeprefix("Value error, ") for e in erro.errors())
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem) from None
    # O ofício fica em nome de quem pede; os administradores do Planner o acompanham como os demais
    oficio = cadastrar_oficio(db, oficio_dados, usuario.id, usuario)
    oficio.chamado = chamado
    nome_tipo = db.get(TipoOficio, dados.tipo).nome
    regras.registrar(db, chamado, usuario, TipoInteracao.OFICIO, agora,
                     f"Solicitação registrada no Planner de Ofícios: ofício nº {regras.numero_oficio(oficio)} "
                     f"({nome_tipo}).\nItens: {dados.itens}")
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


# ---------- ofícios que já existem no Planner: vincular ao chamado ----------


@router.get("/oficios-disponiveis", response_model=list[OficioDisponivel],
            summary="Ofícios já cadastrados no Planner, ainda sem chamado, que o usuário pode vincular")
def oficios_disponiveis(db: DbDep, usuario: UsuarioDep, busca: str | None = None,
                        limite: int = Query(20, ge=1, le=50)):
    """Vale a visibilidade do Planner: o administrador de lá encontra todos; os demais, só os próprios."""
    regras.exigir_solicitante(usuario)
    consulta = select(Oficio).where(escopo_planner(usuario), Oficio.chamado_id.is_(None))
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        consulta = consulta.where(or_(Oficio.numero.like(termo), Oficio.protocolo.like(termo),
                                      Oficio.destinatario_setor.like(termo), Oficio.observacao.like(termo)))
    oficios = db.scalars(consulta.order_by(Oficio.data_oficio.desc(), Oficio.id.desc()).limit(limite)).all()
    return [
        OficioDisponivel.model_validate(o).model_copy(update={
            "tipo_nome": o.tipo_info.nome if o.tipo_info else o.tipo, "dono_nome": o.dono.nome if o.dono else None,
        })
        for o in oficios
    ]


@router.put("/chamados/{chamado_id}/oficios/{oficio_id}", response_model=ChamadoDetalhe,
            summary="Vincula ao chamado um ofício que já existe no Planner")
def vincular_oficio(chamado_id: int, oficio_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                    agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_solicitante(usuario)
    regras.exigir_status(chamado, ABERTOS, "vincular um ofício a")
    # Ofício que o usuário não vê no Planner responde 404, para não revelar que existe
    oficio = db.scalar(select(Oficio).where(Oficio.id == oficio_id, escopo_planner(usuario)))
    if oficio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ofício não encontrado no Planner")
    if oficio.chamado_id == chamado.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "O ofício já está vinculado a este chamado")
    if oficio.chamado_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"O ofício já está vinculado ao chamado {oficio.chamado.codigo}. Desvincule-o de lá antes")
    # A atividade é registrada antes do vínculo para não ser espelhada (a linha do tempo recebe o texto abaixo)
    registrar_atividade(db, usuario, Acao.OFICIO_EDITADO,
                        f"Vinculou o ofício nº {oficio.numero} ao chamado {chamado.codigo} da Manutenção Clínica", oficio)
    oficio.chamado = chamado
    nome_tipo = oficio.tipo_info.nome if oficio.tipo_info else "sem tipo"
    regras.registrar(db, chamado, usuario, TipoInteracao.OFICIO, agora,
                     f"Ofício nº {regras.numero_oficio(oficio)} ({nome_tipo}), já cadastrado no Planner de Ofícios, "
                     f"vinculado a este chamado. Situação no Planner: {regras.ROTULO_OFICIO[oficio.status]}.")
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.delete("/chamados/{chamado_id}/oficios/{oficio_id}", response_model=ChamadoDetalhe,
               summary="Desfaz o vínculo do ofício com o chamado (o ofício continua no Planner)")
def desvincular_oficio(chamado_id: int, oficio_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                       agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_solicitante(usuario)
    regras.exigir_status(chamado, ABERTOS, "desvincular um ofício de")
    oficio = next((o for o in chamado.oficios if o.id == oficio_id), None)
    if oficio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ofício não encontrado neste chamado")
    if not regras.pode_desvincular(usuario, oficio):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Só o dono do ofício ou um administrador desfaz o vínculo com o chamado")
    oficio.chamado = None
    db.flush()  # o vínculo sai antes da atividade, para ela não ser espelhada no chamado
    registrar_atividade(db, usuario, Acao.OFICIO_EDITADO,
                        f"Desvinculou o ofício nº {oficio.numero} do chamado {chamado.codigo} da Manutenção Clínica",
                        oficio)
    regras.registrar(db, chamado, usuario, TipoInteracao.OFICIO, agora,
                     f"Ofício nº {regras.numero_oficio(oficio)} desvinculado deste chamado. Ele continua no Planner "
                     "de Ofícios.")
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.get("/chamados/{chamado_id}/oficios/anexos/{anexo_id}",
            summary="Baixa um documento do ofício de peças/equipamentos (anexado no Planner) a partir do chamado")
def baixar_anexo_oficio(chamado_id: int, anexo_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
                        inline: bool = False, bruto: bool = False):
    chamado = regras.buscar(db, chamado_id, usuario)  # quem vê o chamado (inclusive o técnico) vê os documentos
    anexo = db.get(Anexo, anexo_id)
    if anexo is None or anexo.oficio_id not in {o.id for o in chamado.oficios}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado neste chamado")
    caminho = armazenamento.caminho_absoluto(anexo.caminho, settings)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_410_GONE, "O arquivo deste documento não está mais no servidor")
    return FileResponse(
        caminho, media_type="application/octet-stream" if bruto else anexo.mime_type, filename=anexo.nome_original,
        content_disposition_type="inline" if inline else "attachment", headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/chamados/{chamado_id}/concluir", response_model=ChamadoDetalhe)
def concluir(chamado_id: int, dados: Conclusao, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
             agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_atendente(usuario)
    regras.exigir_status(chamado, ABERTOS, "concluir")
    if chamado.diagnosticado_em is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Registre o diagnóstico (resposta técnica ou relatório) antes de concluir")
    chamado.status = StatusChamado.CONCLUIDO
    chamado.concluido_em = agora
    # Registro do tempo de solução: do diagnóstico até agora, em horas corridas
    chamado.solucao_horas_corridas = max(regras.horas_entre(chamado.diagnosticado_em, agora), 0.0)
    tempo = f"Tempo de solução após o diagnóstico: {regras.texto_horas(chamado.solucao_horas_corridas)}."
    texto = f"{dados.texto}\n\n{tempo}" if dados.texto else f"Chamado concluído. {tempo}"
    regras.registrar(db, chamado, usuario, TipoInteracao.CONCLUSAO, agora, texto)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.post("/chamados/{chamado_id}/reabrir", response_model=ChamadoDetalhe)
def reabrir(chamado_id: int, dados: Motivo, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
            agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_solicitante(usuario)
    regras.exigir_status(chamado, {StatusChamado.CONCLUIDO}, "reabrir")
    chamado.status = StatusChamado.EM_ATENDIMENTO
    chamado.concluido_em = None
    # A solução anterior não resolveu: o tempo volta a contar do diagnóstico e é gravado na nova conclusão
    chamado.solucao_horas_corridas = None
    regras.registrar(db, chamado, usuario, TipoInteracao.REABERTURA, agora, dados.motivo)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)


@router.post("/chamados/{chamado_id}/cancelar", response_model=ChamadoDetalhe)
def cancelar(chamado_id: int, dados: Motivo, db: DbDep, usuario: UsuarioDep, settings: SettingsDep,
             agora: AgoraDep):
    chamado = regras.buscar(db, chamado_id, usuario)
    regras.exigir_solicitante(usuario)
    regras.exigir_status(chamado, ABERTOS, "cancelar")
    chamado.status = StatusChamado.CANCELADO
    chamado.cancelado_em = agora
    regras.registrar(db, chamado, usuario, TipoInteracao.CANCELAMENTO, agora, dados.motivo)
    db.commit()
    return _detalhe(chamado, usuario, agora, settings)
