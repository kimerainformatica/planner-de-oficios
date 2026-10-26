from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminDep, CalendarioDep, DbDep, HojeDep, SettingsDep, UsuarioDep, eh_admin
from app.models import Destinatario, Oficio, SolicitacaoExclusao, StatusOficio, StatusSolicitacao, Usuario
from app.schemas import (
    ConsultaLista,
    EtapaDesfazer,
    OficioAtualizar,
    OficioCriar,
    OficioDetalhe,
    PaginaOficios,
    RecebimentoCorrigir,
    RespostaCorrigir,
    SolicitacaoCriar,
    SolicitacaoOut,
    StatusAlterar,
    validar_destinatario,
)
from app.services.auditoria import Acao, campos_legiveis, diferencas, registrar
from app.services.exclusoes import decidir, excluir_oficio, montar_solicitacao
from app.services.oficios import (
    Limites,
    ajustar_etapa_recebimento,
    alterar_status,
    buscar_oficio,
    corrigir_recebimento,
    corrigir_resposta,
    desfazer_etapa,
    escopo,
    filtros_sql,
    montar_oficio,
    registrar_historico,
    verificar_duplicidade,
)
from app.services.tipos import validar_para_oficio

# Campos que aceitam null no PATCH para serem apagados (os demais são obrigatórios).
APAGAVEIS = {"observacao", "protocolo", "destinatario_tipo", "destinatario_setor"}

router = APIRouter(prefix="/api/oficios", tags=["Ofícios"])


@router.get("", response_model=PaginaOficios, summary="Lista ofícios (cliente vê só os seus)")
def listar(
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    usuario: UsuarioDep,
    f: Annotated[ConsultaLista, Query()],
):
    filtros = filtros_sql(usuario, f, Limites.calcular(calendario, hoje, settings))
    total = db.scalar(select(func.count()).select_from(Oficio).where(*filtros)) or 0
    ordenacao = Oficio.data_oficio.desc() if f.ordem == "recentes" else Oficio.data_oficio.asc()
    pagina, por_pagina = f.pagina, f.por_pagina
    oficios = db.scalars(
        select(Oficio)
        .where(*filtros)
        .options(selectinload(Oficio.anexos), selectinload(Oficio.dono))
        .order_by(ordenacao, Oficio.id)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()

    return PaginaOficios(
        itens=[montar_oficio(o, calendario, hoje, settings) for o in oficios],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
    )


@router.get("/setores", response_model=list[str],
            summary="Setores/destinos já usados, para sugerir ao digitar (cliente: dos próprios ofícios)")
def setores(db: DbDep, usuario: UsuarioDep, destinatario_tipo: Destinatario):
    linhas = db.execute(
        select(Oficio.destinatario_setor, func.count())
        .where(escopo(usuario), Oficio.destinatario_tipo == destinatario_tipo, Oficio.destinatario_setor.is_not(None))
        .group_by(Oficio.destinatario_setor)
    ).all()
    # "Almoxarifado" e "almoxarifado " viram uma sugestão só, com a grafia mais usada
    grupos: dict[str, tuple[str, int]] = {}
    for setor, n in linhas:
        chave = " ".join(setor.split()).casefold()
        grafia, total = grupos.get(chave, (setor.strip(), 0))
        grupos[chave] = (grafia if total >= n else setor.strip(), total + n)
    return sorted((g for g, _ in grupos.values()), key=str.casefold)


@router.post("", response_model=OficioDetalhe, status_code=status.HTTP_201_CREATED)
def criar(
    dados: OficioCriar,
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    usuario: UsuarioDep,
):
    dono_id = usuario.id
    if eh_admin(usuario) and dados.dono_id is not None:
        dono = db.get(Usuario, dados.dono_id)
        if dono is None or not dono.ativo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "O cliente informado não existe ou está inativo")
        dono_id = dono.id

    ano = dados.data_oficio.year
    validar_para_oficio(db, dados.tipo)
    verificar_duplicidade(db, dono_id, dados.numero, ano, dados.protocolo)
    # Todo ofício novo entra como PENDENTE_RESPOSTA, sem exceção.
    oficio = Oficio(
        **dados.model_dump(exclude={"dono_id"}),
        ano=ano,
        dono_id=dono_id,
        status=StatusOficio.PENDENTE_RESPOSTA,
        inicio_prazo=dados.data_oficio,
        criado_por_id=usuario.id,
    )
    db.add(oficio)
    registrar_historico(db, oficio, None, StatusOficio.PENDENTE_RESPOSTA, usuario, "Cadastro do ofício")
    db.flush()
    registrar(db, usuario, Acao.OFICIO_CRIADO, f"Cadastrou o ofício nº {oficio.numero}", oficio,
              detalhes=diferencas({}, dados.model_dump(exclude={"dono_id"}, exclude_none=True)))
    db.commit()
    return montar_oficio(buscar_oficio(db, oficio.id, usuario, detalhe=True), calendario, hoje, settings, detalhe=True)


@router.get("/{oficio_id}", response_model=OficioDetalhe)
def detalhar(
    oficio_id: int, db: DbDep, settings: SettingsDep, calendario: CalendarioDep, hoje: HojeDep, usuario: UsuarioDep
):
    return montar_oficio(buscar_oficio(db, oficio_id, usuario, detalhe=True), calendario, hoje, settings, detalhe=True)


@router.patch("/{oficio_id}", response_model=OficioDetalhe, summary="Edita os dados (dono ou admin)")
def atualizar(
    oficio_id: int,
    dados: OficioAtualizar,
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    usuario: UsuarioDep,
):
    oficio = buscar_oficio(db, oficio_id, usuario, detalhe=True)
    alteracoes = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None or k in APAGAVEIS}
    numero = alteracoes.get("numero", oficio.numero)
    data_oficio = alteracoes.get("data_oficio", oficio.data_oficio)
    protocolo = alteracoes.get("protocolo", oficio.protocolo)
    try:
        validar_destinatario(
            alteracoes.get("destinatario_tipo", oficio.destinatario_tipo),
            alteracoes.get("destinatario_setor", oficio.destinatario_setor),
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e

    reaberto = any(
        h.status_anterior is not None and h.status_novo == StatusOficio.PENDENTE_RESPOSTA for h in oficio.historico
    )
    limite = oficio.inicio_prazo if reaberto else oficio.data_resposta
    if limite and data_oficio > limite:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "A data do ofício não pode ser posterior à resposta ou à reabertura"
        )
    verificar_duplicidade(db, oficio.dono_id, numero, data_oficio.year, protocolo, ignorar_id=oficio.id)
    if "tipo" in alteracoes:
        validar_para_oficio(db, alteracoes["tipo"], atual=oficio.tipo)

    antes = {campo: getattr(oficio, campo) for campo in alteracoes}
    for campo, valor in alteracoes.items():
        setattr(oficio, campo, valor)
    oficio.ano = data_oficio.year
    if not reaberto:
        oficio.inicio_prazo = data_oficio  # nunca reaberto: o prazo acompanha a data do ofício
    mudancas = diferencas(antes, alteracoes)
    if "tipo" in mudancas and (status_antes := ajustar_etapa_recebimento(db, oficio, usuario)):
        mudancas["status"] = {"de": status_antes.value, "para": oficio.status.value}
    if mudancas:
        registrar(db, usuario, Acao.OFICIO_EDITADO,
                  f"Editou o ofício nº {oficio.numero} ({campos_legiveis(mudancas)})", oficio, detalhes=mudancas)
    db.commit()
    return montar_oficio(buscar_oficio(db, oficio_id, usuario, detalhe=True), calendario, hoje, settings, detalhe=True)


@router.patch(
    "/{oficio_id}/status",
    response_model=OficioDetalhe,
    summary="Registra resposta ou reabre (cliente: só nos próprios ofícios)",
)
def mudar_status(
    oficio_id: int,
    dados: StatusAlterar,
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    usuario: UsuarioDep,
):
    # buscar_oficio aplica o escopo: ofício de outro cliente responde 404.
    oficio = buscar_oficio(db, oficio_id, usuario)
    anterior = oficio.status
    novo = alterar_status(db, oficio, dados.status, dados.data_resposta, dados.data_recebimento, dados.observacao,
                          usuario, hoje)
    acao = {StatusOficio.PENDENTE_RESPOSTA: "Reabriu o ofício",
            StatusOficio.RECEBIDO: "Confirmou o recebimento do ofício"}.get(novo, "Registrou resposta no ofício")
    data_registrada = {"data_recebimento": dados.data_recebimento} if novo == StatusOficio.RECEBIDO else {
        "data_resposta": dados.data_resposta}
    registrar(db, usuario, Acao.STATUS_ALTERADO, f"{acao} nº {oficio.numero}", oficio,
              detalhes={"status": {"de": anterior.value, "para": novo.value},
                        **{k: str(v) for k, v in data_registrada.items() if v},
                        **({"observacao": dados.observacao} if dados.observacao else {})})
    db.commit()
    return montar_oficio(buscar_oficio(db, oficio_id, usuario, detalhe=True), calendario, hoje, settings, detalhe=True)


# ---------- correções do admin ----------


@router.patch("/{oficio_id}/resposta", response_model=OficioDetalhe,
              summary="Admin/master: corrige resultado, data e observação da resposta atual")
def editar_resposta(
    oficio_id: int,
    dados: RespostaCorrigir,
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    admin: AdminDep,
):
    oficio = buscar_oficio(db, oficio_id, admin, detalhe=True)
    mudancas = corrigir_resposta(db, oficio, dados.model_dump(exclude_unset=True), admin, hoje)
    if mudancas:
        registrar(db, admin, Acao.RESPOSTA_CORRIGIDA,
                  f"Corrigiu a resposta do ofício nº {oficio.numero} ({campos_legiveis(mudancas)})", oficio,
                  detalhes=mudancas)
    db.commit()
    return montar_oficio(buscar_oficio(db, oficio_id, admin, detalhe=True), calendario, hoje, settings, detalhe=True)


@router.patch("/{oficio_id}/recebimento", response_model=OficioDetalhe,
              summary="Admin/master: corrige data e observação do recebimento")
def editar_recebimento(
    oficio_id: int,
    dados: RecebimentoCorrigir,
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    admin: AdminDep,
):
    oficio = buscar_oficio(db, oficio_id, admin, detalhe=True)
    mudancas = corrigir_recebimento(oficio, dados.model_dump(exclude_unset=True), hoje)
    if mudancas:
        registrar(db, admin, Acao.RECEBIMENTO_CORRIGIDO,
                  f"Corrigiu o recebimento do ofício nº {oficio.numero} ({campos_legiveis(mudancas)})", oficio,
                  detalhes=mudancas)
    db.commit()
    return montar_oficio(buscar_oficio(db, oficio_id, admin, detalhe=True), calendario, hoje, settings, detalhe=True)


@router.post("/{oficio_id}/desfazer", response_model=OficioDetalhe,
             summary="Admin/master: desfaz o recebimento ou, sem ele, a resposta (fica no histórico como desfeito)")
def desfazer(
    oficio_id: int,
    dados: EtapaDesfazer,
    db: DbDep,
    settings: SettingsDep,
    calendario: CalendarioDep,
    hoje: HojeDep,
    admin: AdminDep,
):
    oficio = buscar_oficio(db, oficio_id, admin, detalhe=True)
    anterior, etapa = desfazer_etapa(oficio, dados.motivo, admin)
    registrar(db, admin, Acao.ETAPA_DESFEITA, f"Desfez {etapa} do ofício nº {oficio.numero}", oficio,
              detalhes={"status": {"de": anterior.value, "para": oficio.status.value}, "motivo": dados.motivo})
    db.commit()
    return montar_oficio(buscar_oficio(db, oficio_id, admin, detalhe=True), calendario, hoje, settings, detalhe=True)


@router.delete("/{oficio_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Exclui direto (admin/master). Clientes usam POST /exclusao para pedir.")
def excluir(oficio_id: int, db: DbDep, settings: SettingsDep, admin: AdminDep):
    excluir_oficio(db, buscar_oficio(db, oficio_id, admin, detalhe=True), admin, settings)


# ---------- pedido de exclusão (cliente) ----------


@router.post("/{oficio_id}/exclusao", response_model=SolicitacaoOut, status_code=status.HTTP_201_CREATED,
             summary="Pede a um admin a exclusão do ofício")
def solicitar_exclusao(oficio_id: int, dados: SolicitacaoCriar, db: DbDep, usuario: UsuarioDep):
    oficio = buscar_oficio(db, oficio_id, usuario, detalhe=True)
    if oficio.exclusao_pendente is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um pedido de exclusão aguardando um administrador")
    pedido = SolicitacaoExclusao(oficio_id=oficio.id, referencia=f"Ofício nº {oficio.numero} · {oficio.dono.nome}",
                                 solicitante_id=usuario.id, motivo=dados.motivo)
    db.add(pedido)
    registrar(db, usuario, Acao.EXCLUSAO_SOLICITADA, f"Pediu a exclusão do ofício nº {oficio.numero}", oficio,
              detalhes={"motivo": dados.motivo})
    db.commit()
    db.refresh(pedido)
    return montar_solicitacao(pedido)


@router.delete("/{oficio_id}/exclusao", status_code=status.HTTP_204_NO_CONTENT,
               summary="Cancela o pedido de exclusão pendente")
def cancelar_exclusao(oficio_id: int, db: DbDep, usuario: UsuarioDep):
    oficio = buscar_oficio(db, oficio_id, usuario, detalhe=True)
    pedido = oficio.exclusao_pendente
    if pedido is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não há pedido de exclusão pendente")
    if pedido.solicitante_id != usuario.id and not eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só quem pediu pode cancelar")
    pedido = db.get(SolicitacaoExclusao, pedido.id)
    decidir(pedido, StatusSolicitacao.CANCELADA, usuario)
    registrar(db, usuario, Acao.EXCLUSAO_CANCELADA, f"Cancelou o pedido de exclusão do ofício nº {oficio.numero}",
              oficio)
    db.commit()