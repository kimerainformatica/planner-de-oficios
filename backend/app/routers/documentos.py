"""Documentos: o planner dos documentos da instituição, redigidos no app a partir dos modelos e impressos no modelo da
unidade.

Módulo próprio (DOCUMENTOS), integrado ao Planner de Ofícios: com "registrar no Planner", o ofício emitido é
cadastrado lá em nome de quem elaborou (que precisa usar o Planner).
Fluxo: rascunho (só quem elaborou edita) → emissão (número, data, código de verificação; o ofício entra no Planner)
→ assinaturas → conclusão (ou cancelamento com motivo). Assinaturas: à mão no papel ou eletrônicas, no app (com a
senha) ou no GOV.BR (enviando o PDF assinado de volta para a conferência); cada documento escolhe, o modelo sugere.
Organização: pasta e prazo (com alerta), lista e quadro por etapa. Modelos e pastas: `documentos_modelos.py`.
A verificação pública (sem login) confere o código impresso no rodapé e o QR code.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.deps import AgoraDep, DbDep, HojeDep, SettingsDep, UsuarioDep, exige_acesso_ao
from app.config import Settings
from app.models import (
    TIPO_OFICIO,
    AssinaturaDocumento,
    Documento,
    EstruturaDocumento,
    EtapaDocumento,
    FormaAssinatura,
    Modulo,
    PapelAssinatura,
    PastaDocumento,
    StatusDocumento,
    Usuario,
)
from app.schemas import OficioCriar
from app.schemas_documentos import (
    Assinante,
    Assinar,
    AssinaturaOut,
    Cancelar,
    ColunaQuadro,
    DocumentoAtualizar,
    DocumentoCriar,
    DocumentoOut,
    DocumentoResumo,
    ModeloResumo,
    Organizar,
    PaginaDocumentos,
    Quadro,
    TimbradoOut,
    Verificacao,
)
from app.seguranca import verificar_senha
from app.services import documentos as regras
from app.services import limite_login
from app.services import modelos_documento as modelos
from app.services.armazenamento import remover_arquivo
from app.services.assinatura_govbr import AssinaturaInvalida, conferir, mascarar_cpf
from app.services.auditoria import Acao, registrar
from app.services.oficios import cadastrar_oficio
from app.services.tipos import validar_para_oficio

router = APIRouter(prefix="/api/documentos", tags=["Documentos"],
                   dependencies=[Depends(exige_acesso_ao(Modulo.DOCUMENTOS))])
publico = APIRouter(prefix="/api/publico", tags=["Documentos"])

LIMITE_TIMBRADO_MB = 5
TEXTOS_OPCIONAIS = {"dest_tratamento", "dest_nome", "dest_cargo", "dest_endereco", "de", "para", "oficio_tipo",
                    "destinatario_setor", "elaborador_cargo", "elaborador_ident", "validador_nome", "validador_cargo",
                    "validador_ident"}


def _ref(doc: Documento) -> str:
    return f"{doc.titulo} · {doc.assunto[:60]}" if doc.assunto else doc.titulo


def _organizacao(doc: Documento, hoje: date, settings: Settings) -> dict:
    """Modelo, etapa, pasta e prazo: o que a lista, o quadro e o detalhe mostram igual."""
    return {"tipo_nome": doc.nome_tipo, "etapa": regras.etapa(doc), "pasta_nome": doc.pasta.nome if doc.pasta else None,
            "alerta_prazo": regras.alerta_prazo(doc, hoje, settings.documentos_dias_atencao),
            "dias_prazo": regras.dias_para_o_prazo(doc, hoje)}


def _saida(doc: Documento, usuario: Usuario, hoje: date, settings: Settings) -> DocumentoOut:
    dados = {campo: getattr(doc, campo) for campo in DocumentoOut.model_fields if hasattr(doc, campo)}
    dados.update(_organizacao(doc, hoje, settings))
    formato = regras.formato_de(doc)
    dados["modelo"] = ModeloResumo(**{c: formato[c] for c in ModeloResumo.model_fields if c in formato})
    dados["integra_planner"] = doc.tipo == TIPO_OFICIO
    dados["assinaturas"] = [AssinaturaOut.model_validate(a) for a in doc.assinaturas]
    dados["cancelado_por_nome"] = doc.cancelado_por.nome if doc.cancelado_por else None
    dados["concluido_por_nome"] = doc.concluido_por.nome if doc.concluido_por else None
    dados["usa_planner"] = doc.autor.tem_acesso(Modulo.OFICIOS)
    autor = doc.autor_id == usuario.id
    dados["pode_editar"] = autor and doc.status == StatusDocumento.RASCUNHO
    dados["pode_cancelar"] = doc.status == StatusDocumento.EMITIDO and (autor or regras.eh_admin(usuario))
    organiza = regras.pode_organizar(doc, usuario)
    dados["pode_organizar"] = organiza
    dados["pode_concluir"] = organiza and doc.status == StatusDocumento.EMITIDO and doc.concluido_em is None
    dados["pode_reabrir"] = organiza and doc.status == StatusDocumento.EMITIDO and doc.concluido_em is not None
    dados["assinar_como"] = regras.papel_para_assinar(doc, usuario)
    dados["pode_enviar_assinado"] = regras.pode_enviar_assinado(doc, usuario)
    dados["tem_assinado"] = doc.arquivo_assinado is not None
    dados["pendencias"] = regras.pendencias_para_emitir(doc) if doc.status == StatusDocumento.RASCUNHO else []
    return DocumentoOut.model_validate(dados)


def _destino(doc: Documento) -> str | None:
    estrutura = regras.estrutura_de(doc)
    if estrutura == EstruturaDocumento.EXTERNO:
        return doc.dest_nome
    return doc.para if estrutura == EstruturaDocumento.INTERNO else None


def _resumo(doc: Documento, usuario: Usuario, hoje: date, settings: Settings) -> DocumentoResumo:
    return DocumentoResumo(
        id=doc.id, tipo=doc.tipo, status=doc.status, titulo=doc.titulo, numero_formatado=doc.numero_formatado,
        assunto=doc.assunto, destino=_destino(doc),
        elaborador_nome=doc.elaborador_nome, validador_nome=doc.validador_nome, data_documento=doc.data_documento,
        atualizado_em=doc.atualizado_em, forma_assinatura=doc.forma_assinatura, assinaturas=len(doc.assinaturas),
        assinaturas_previstas=2 if doc.validador_nome else 1,
        minha_assinatura_pendente=doc.concluido_em is None and regras.papel_para_assinar(doc, usuario) is not None,
        pasta_id=doc.pasta_id, prazo=doc.prazo, concluido_em=doc.concluido_em, **_organizacao(doc, hoje, settings),
    )


def _sem_assinatura(papel: PapelAssinatura):
    return not_(exists().where(AssinaturaDocumento.documento_id == Documento.id, AssinaturaDocumento.papel == papel))


def _aguardando(usuario: Usuario):
    """Documentos emitidos em que falta a assinatura eletrônica do usuário (o concluído sai das pendências)."""
    return and_(
        Documento.status == StatusDocumento.EMITIDO,
        Documento.concluido_em.is_(None),
        or_(
            and_(Documento.autor_id == usuario.id, _sem_assinatura(PapelAssinatura.ELABORADOR)),
            and_(Documento.validador_id == usuario.id, Documento.validador_nome.is_not(None),
                 _sem_assinatura(PapelAssinatura.VALIDADOR)),
        ),
    )


def _pendente():
    """Falta assinatura eletrônica prevista (de quem elaborou ou do De acordo)."""
    return or_(_sem_assinatura(PapelAssinatura.ELABORADOR),
               and_(Documento.validador_nome.is_not(None), _sem_assinatura(PapelAssinatura.VALIDADOR)))


def _na_etapa(etapa: EtapaDocumento):
    """O mesmo que `regras.etapa`, para as consultas."""
    emitido = Documento.status == StatusDocumento.EMITIDO
    return {
        EtapaDocumento.RASCUNHO: Documento.status == StatusDocumento.RASCUNHO,
        EtapaDocumento.AGUARDANDO: and_(emitido, Documento.concluido_em.is_(None), _pendente()),
        EtapaDocumento.ASSINADO: and_(emitido, Documento.concluido_em.is_(None), not_(_pendente())),
        EtapaDocumento.CONCLUIDO: and_(emitido, Documento.concluido_em.is_not(None)),
        EtapaDocumento.CANCELADO: Documento.status == StatusDocumento.CANCELADO,
    }[etapa]


def _com_prazo(prazo: str, hoje: date, dias_atencao: int):
    """Documentos em aberto com prazo: atrasados, em alerta (atrasados e em atenção) ou qualquer prazo."""
    aberto = and_(Documento.status != StatusDocumento.CANCELADO, Documento.concluido_em.is_(None),
                  Documento.prazo.is_not(None))
    if prazo == "atrasados":
        return and_(aberto, Documento.prazo < hoje)
    if prazo == "alerta":
        return and_(aberto, Documento.prazo <= hoje + timedelta(days=dias_atencao))
    return aberto


def _visiveis(usuario: Usuario):
    return regras.filtro_visiveis(usuario)


@dataclass
class _Consulta:
    escopo: str
    tipo: str | None
    situacao: StatusDocumento | None
    etapa: EtapaDocumento | None
    pasta_id: int | None
    prazo: str | None
    busca: str | None


def _consulta(
    escopo: Annotated[str, Query(pattern="^(meus|assinar|todos)$")] = "todos",
    tipo: Annotated[str | None, Query(max_length=40, description="Código do modelo")] = None,
    situacao: Annotated[StatusDocumento | None, Query(alias="status")] = None,
    etapa: EtapaDocumento | None = None,
    pasta_id: Annotated[int | None, Query(ge=0, description="0: sem pasta")] = None,
    prazo: Annotated[str | None, Query(pattern="^(atrasados|alerta|com_prazo)$")] = None,
    busca: Annotated[str | None, Query(max_length=100)] = None,
) -> _Consulta:
    return _Consulta(escopo, tipo, situacao, etapa, pasta_id, prazo, busca)


ConsultaDep = Annotated[_Consulta, Depends(_consulta)]


def _filtros(c: _Consulta, usuario: Usuario, hoje: date, settings: Settings) -> list:
    filtros = [_visiveis(usuario)]
    if c.escopo == "meus":
        filtros.append(Documento.autor_id == usuario.id)
    elif c.escopo == "assinar":
        filtros.append(_aguardando(usuario))
    if c.tipo:
        filtros.append(Documento.tipo == c.tipo)
    if c.situacao:
        filtros.append(Documento.status == c.situacao)
    if c.etapa:
        filtros.append(_na_etapa(c.etapa))
    if c.pasta_id is not None:
        filtros.append(Documento.pasta_id == c.pasta_id if c.pasta_id else Documento.pasta_id.is_(None))
    if c.prazo:
        filtros.append(_com_prazo(c.prazo, hoje, settings.documentos_dias_atencao))
    if c.busca and c.busca.strip():
        termo = f"%{c.busca.strip()}%"
        filtros.append(or_(Documento.assunto.ilike(termo), Documento.dest_nome.ilike(termo),
                           Documento.para.ilike(termo), Documento.de.ilike(termo),
                           Documento.elaborador_nome.ilike(termo), Documento.codigo.ilike(termo)))
    return filtros


def _ordem(ordem: str) -> tuple:
    if ordem == "prazo":  # o prazo mais próximo primeiro; sem prazo no fim
        return Documento.prazo.is_(None), Documento.prazo.asc(), Documento.atualizado_em.desc(), Documento.id.desc()
    return Documento.atualizado_em.desc(), Documento.id.desc()


def _pasta_valida(db: Session, pasta_id: int, atual: int | None = None) -> PastaDocumento:
    pasta = db.get(PastaDocumento, pasta_id)
    if pasta is None or (not pasta.ativo and pasta_id != atual):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pasta não encontrada ou desativada")
    return pasta


def _validador(db: Session, usuario_id: int, autor: Usuario) -> Usuario:
    pessoa = db.get(Usuario, usuario_id)
    if pessoa is None or not pessoa.ativo or not pessoa.tem_acesso(Modulo.DOCUMENTOS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Quem dá o De acordo precisa ser um usuário ativo do módulo Documentos")
    if pessoa.id == autor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Quem elaborou não pode dar o próprio De acordo")
    return pessoa


def _nome_arquivo(doc: Documento) -> str:
    base = unicodedata.normalize("NFKD", doc.titulo).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return f"{base}-{doc.id}.pdf" if doc.numero is None else f"{base}.pdf"


def _exigir_admin(usuario: Usuario) -> None:
    if not regras.eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o administrador do módulo Documentos muda o timbrado")


# ---------- consulta ----------


@router.get("", response_model=PaginaDocumentos,
            summary="Lista os documentos (os seus, os para assinar ou todos; por modelo, etapa, pasta e prazo)")
def listar(
    db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep, consulta: ConsultaDep,
    ordem: Annotated[str, Query(pattern="^(recentes|prazo)$")] = "recentes",
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 30,
):
    filtros = _filtros(consulta, usuario, hoje, settings)
    total = db.scalar(select(func.count()).select_from(Documento).where(*filtros))
    itens = db.scalars(select(Documento).where(*filtros).order_by(*_ordem(ordem))
                       .offset((pagina - 1) * por_pagina).limit(por_pagina)).unique().all()
    return PaginaDocumentos(itens=[_resumo(d, usuario, hoje, settings) for d in itens], total=total, pagina=pagina,
                            por_pagina=por_pagina)


@router.get("/quadro", response_model=Quadro, summary="Os documentos por etapa (as colunas do quadro)")
def quadro(db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep, consulta: ConsultaDep,
           por_coluna: Annotated[int, Query(ge=1, le=100)] = 40):
    base = _filtros(consulta, usuario, hoje, settings)
    colunas = []
    for etapa in EtapaDocumento:
        filtros = [*base, _na_etapa(etapa)]
        fechada = etapa in (EtapaDocumento.CONCLUIDO, EtapaDocumento.CANCELADO)  # os mais recentes primeiro
        itens = db.scalars(select(Documento).where(*filtros).order_by(*_ordem("recentes" if fechada else "prazo"))
                           .limit(por_coluna)).unique().all()
        colunas.append(ColunaQuadro(
            etapa=etapa, total=db.scalar(select(func.count()).select_from(Documento).where(*filtros)),
            itens=[_resumo(d, usuario, hoje, settings) for d in itens]))
    return Quadro(colunas=colunas)


@router.get("/resumo", summary="Contadores do menu: aguardando a assinatura do usuário e prazos em alerta")
def resumo(db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep):
    meus = or_(Documento.autor_id == usuario.id, Documento.validador_id == usuario.id)
    alerta = _com_prazo("alerta", hoje, settings.documentos_dias_atencao)
    return {"para_assinar": db.scalar(select(func.count()).select_from(Documento).where(_aguardando(usuario))),
            "prazos": db.scalar(select(func.count()).select_from(Documento).where(meus, alerta))}


@router.get("/assinantes", response_model=list[Assinante], summary="Usuários que podem dar o De acordo")
def assinantes(db: DbDep, usuario: UsuarioDep):
    pessoas = db.scalars(select(Usuario).where(Usuario.ativo.is_(True)).order_by(Usuario.nome)).unique().all()
    return [p for p in pessoas if p.tem_acesso(Modulo.DOCUMENTOS) and p.id != usuario.id]


@router.get("/timbrado", response_model=TimbradoOut, summary="Situação do timbrado (cabeçalho e marca-d'água)")
def timbrado(settings: SettingsDep):
    return TimbradoOut(cabecalho=regras.arquivo_timbrado(settings, "cabecalho") is not None,
                       fundo=regras.arquivo_timbrado(settings, "fundo") is not None,
                       cidade=settings.documentos_cidade.strip(), uf=settings.documentos_uf.strip())


def _parte(parte: str) -> str:
    if parte not in regras.PARTES_TIMBRADO:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parte do timbrado desconhecida (use cabecalho ou fundo)")
    return parte


def _nome_parte(parte: str) -> str:
    return "cabeçalho" if parte == "cabecalho" else "marca-d'água"


@router.get("/timbrado/{parte}", summary="Imagem do timbrado")
def imagem_timbrado(parte: str, settings: SettingsDep):
    caminho = regras.arquivo_timbrado(settings, _parte(parte))
    if caminho is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Imagem não enviada")
    return FileResponse(caminho, headers={"Cache-Control": "no-cache"})


@router.put("/timbrado/{parte}", response_model=TimbradoOut,
            summary="Envia o cabeçalho ou a marca-d'água (PNG ou JPG; só o administrador do módulo)")
def enviar_timbrado(parte: str, settings: SettingsDep, db: DbDep, usuario: UsuarioDep,
                    arquivo: Annotated[UploadFile, File()]):
    _parte(parte)
    _exigir_admin(usuario)
    nome = arquivo.filename or ""
    ext = "." + nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    if ext not in regras.EXTENSOES_TIMBRADO:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Envie uma imagem PNG ou JPG")
    conteudo = arquivo.file.read(LIMITE_TIMBRADO_MB * 1024 * 1024 + 1)
    if len(conteudo) > LIMITE_TIMBRADO_MB * 1024 * 1024:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Imagem maior que {LIMITE_TIMBRADO_MB} MB")
    try:
        with Image.open(BytesIO(conteudo)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O arquivo não é uma imagem válida") from None
    pasta = regras.pasta_timbrado(settings)
    pasta.mkdir(parents=True, exist_ok=True)
    for antiga in regras.EXTENSOES_TIMBRADO:
        (pasta / f"{parte}{antiga}").unlink(missing_ok=True)
    (pasta / f"{parte}{ext}").write_bytes(conteudo)
    registrar(db, usuario, Acao.TIMBRADO_ALTERADO, f"Trocou o {_nome_parte(parte)} do timbrado dos documentos",
              ref="Timbrado dos documentos")
    db.commit()
    return timbrado(settings)


@router.delete("/timbrado/{parte}", response_model=TimbradoOut, summary="Remove o cabeçalho ou a marca-d'água")
def remover_timbrado(parte: str, settings: SettingsDep, db: DbDep, usuario: UsuarioDep):
    _parte(parte)
    _exigir_admin(usuario)
    for ext in regras.EXTENSOES_TIMBRADO:
        (regras.pasta_timbrado(settings) / f"{parte}{ext}").unlink(missing_ok=True)
    registrar(db, usuario, Acao.TIMBRADO_ALTERADO, f"Removeu o {_nome_parte(parte)} do timbrado dos documentos",
              ref="Timbrado dos documentos")
    db.commit()
    return timbrado(settings)


@router.get("/{documento_id}", response_model=DocumentoOut)
def detalhar(documento_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep):
    return _saida(regras.buscar(db, documento_id, usuario), usuario, hoje, settings)


@router.get("/{documento_id}/pdf", summary="PDF do documento no modelo da unidade (rascunho sai marcado)")
def pdf(documento_id: int, request: Request, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep,
        bruto: Annotated[bool, Query(description="application/octet-stream (usado pelo front-end)")] = False,
        assinado: Annotated[bool, Query(description="O arquivo assinado no GOV.BR, mesmo que cancelado")] = False):
    doc = regras.buscar(db, documento_id, usuario)
    if assinado:
        if not doc.arquivo_assinado:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Este documento não tem arquivo assinado")
        conteudo = regras.arquivo_vigente(doc, settings)
    else:
        url = regras.url_publica(settings, str(request.base_url), doc.codigo) if doc.codigo else None
        conteudo = regras.pdf_atual(doc, settings, hoje, url)
    return Response(
        conteudo, media_type="application/octet-stream" if bruto else "application/pdf",
        headers={"Content-Disposition": f'inline; filename="{_nome_arquivo(doc)}"',
                 "X-Content-Type-Options": "nosniff"},
    )


# ---------- rascunho ----------


@router.post("", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED,
             summary="Começa um rascunho do modelo (com os textos do modelo e os dados de quem elabora)")
def criar(dados: DocumentoCriar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep):
    modelo = modelos.para_novo_documento(db, dados.tipo)
    doc = Documento(
        tipo=modelo.codigo, status=StatusDocumento.RASCUNHO, autor_id=usuario.id, assunto="",
        corpo=modelo.texto_modelo, vocativo=modelo.vocativo, fecho=modelo.fecho,
        dest_tratamento="A/C sr. (sra.)" if modelo.estrutura == EstruturaDocumento.EXTERNO else None,
        registrar_no_planner=modelo.codigo == TIPO_OFICIO and usuario.tem_acesso(Modulo.OFICIOS),
        forma_assinatura=modelo.forma_assinatura,
        elaborador_nome=usuario.nome, elaborador_cargo=usuario.cargo, elaborador_ident=usuario.matricula,
        pasta=_pasta_valida(db, dados.pasta_id) if dados.pasta_id else None, prazo=dados.prazo,
    )
    db.add(doc)
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


@router.patch("/{documento_id}", response_model=DocumentoOut, summary="Salva o rascunho (só quem elaborou)")
def atualizar(documento_id: int, dados: DocumentoAtualizar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep,
              settings: SettingsDep):
    doc = regras.buscar(db, documento_id, usuario)
    regras.exigir_rascunho_do_autor(doc, usuario)
    valores = dados.model_dump(exclude_unset=True)
    if valores.get("forma_assinatura") is None:
        valores.pop("forma_assinatura", None)
    if "validador_id" in valores:
        escolhido = valores.pop("validador_id")
        if escolhido is None:
            doc.validador_id = None
        elif escolhido != doc.validador_id:
            pessoa = _validador(db, escolhido, usuario)
            doc.validador_id = pessoa.id
            # nome, cargo e ID vêm do cadastro, a não ser que tenham sido informados juntos
            valores.setdefault("validador_nome", pessoa.nome)
            valores.setdefault("validador_cargo", pessoa.cargo)
            valores.setdefault("validador_ident", pessoa.matricula)
    if valores.get("registrar_no_planner") is None:
        valores.pop("registrar_no_planner", None)
    elif valores["registrar_no_planner"] and doc.tipo != TIPO_OFICIO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Só o ofício é registrado no Planner de Ofícios")
    elif valores["registrar_no_planner"] and not usuario.tem_acesso(Modulo.OFICIOS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Você não usa o Planner de Ofícios: peça o acesso a um administrador para registrar lá")
    if valores.get("oficio_tipo"):
        validar_para_oficio(db, valores["oficio_tipo"], doc.oficio_tipo)
    for campo, valor in valores.items():
        if campo in TEXTOS_OPCIONAIS:
            valor = valor if isinstance(valor, str) and valor.strip() else None
        elif campo not in ("destinatario_tipo", "registrar_no_planner") and valor is None:
            valor = ""
        setattr(doc, campo, valor)
    if not doc.validador_nome:  # sem De acordo
        doc.validador_id = doc.validador_cargo = doc.validador_ident = doc.validador_nome = None
    if doc.destinatario_tipo is None:
        doc.destinatario_setor = None
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Descarta o rascunho")
def excluir(documento_id: int, db: DbDep, usuario: UsuarioDep):
    doc = regras.buscar(db, documento_id, usuario)
    regras.exigir_rascunho_do_autor(doc, usuario)
    db.delete(doc)
    db.commit()


@router.post("/{documento_id}/duplicar", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED,
             summary="Novo rascunho com o mesmo texto (para corrigir um emitido ou reaproveitar)")
def duplicar(documento_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep):
    origem = regras.buscar(db, documento_id, usuario)
    modelos.para_novo_documento(db, origem.tipo)  # o modelo pode ter sido desativado
    meu = origem.autor_id == usuario.id
    copia = Documento(
        tipo=origem.tipo, status=StatusDocumento.RASCUNHO, autor_id=usuario.id,
        **{c: getattr(origem, c) for c in ("assunto", "vocativo", "corpo", "fecho", "dest_tratamento", "dest_nome",
                                           "dest_cargo", "dest_endereco", "de", "para", "oficio_tipo",
                                           "destinatario_tipo", "destinatario_setor")},
        registrar_no_planner=origem.registrar_no_planner and usuario.tem_acesso(Modulo.OFICIOS),
        forma_assinatura=origem.forma_assinatura,
        pasta=origem.pasta if origem.pasta is not None and origem.pasta.ativo else None,
        elaborador_nome=usuario.nome,
        elaborador_cargo=origem.elaborador_cargo if meu else usuario.cargo,
        elaborador_ident=origem.elaborador_ident if meu else usuario.matricula,
    )
    if origem.validador_nome and origem.validador_id != usuario.id:
        copia.validador_id, copia.validador_nome = origem.validador_id, origem.validador_nome
        copia.validador_cargo, copia.validador_ident = origem.validador_cargo, origem.validador_ident
    db.add(copia)
    db.commit()
    return _saida(regras.buscar(db, copia.id, usuario), usuario, hoje, settings)


# ---------- emissão, assinatura e cancelamento ----------


@router.post("/{documento_id}/emitir", response_model=DocumentoOut,
             summary="Emite: dá número, data e código de verificação; o ofício pode ser cadastrado no Planner")
def emitir(documento_id: int, request: Request, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep,
           agora: AgoraDep):
    doc = regras.buscar(db, documento_id, usuario)
    regras.exigir_rascunho_do_autor(doc, usuario)
    faltas = regras.pendencias_para_emitir(doc)
    if faltas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Para emitir, preencha " + ", ".join(faltas) + ".")
    integrar = doc.tipo == TIPO_OFICIO and doc.registrar_no_planner
    if integrar and not usuario.tem_acesso(Modulo.OFICIOS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Você não usa o Planner de Ofícios: desmarque o registro no Planner ou peça o acesso")
    doc.formato = modelos.formato(doc.modelo)  # daqui em diante o documento não muda se o modelo mudar
    doc.ano, doc.data_documento = hoje.year, hoje
    doc.numero = regras.proximo_numero(db, doc.tipo, usuario.id, hoje.year)
    doc.elaborador_nome = usuario.nome
    doc.codigo = regras.novo_codigo(db)
    doc.emitido_em = regras.instante(agora)
    doc.status = StatusDocumento.EMITIDO
    oficio = None
    if integrar:
        try:
            dados = OficioCriar(numero=doc.numero_formatado, data_oficio=hoje, tipo=doc.oficio_tipo,
                                destinatario_tipo=doc.destinatario_tipo, destinatario_setor=doc.destinatario_setor,
                                observacao=f"Redigido e emitido no app (Documentos). Assunto: {doc.assunto}"[:5000])
        except ValidationError as erro:
            mensagem = str(erro.errors()[0].get("msg", "Dados do Planner inválidos")).removeprefix("Value error, ")
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, mensagem) from None
        oficio = cadastrar_oficio(db, dados, usuario.id, usuario)
        doc.oficio_id = oficio.id
    doc.hash_conteudo = regras.calcular_hash(doc)
    registrar(db, usuario, Acao.DOCUMENTO_EMITIDO, f"Emitiu o {doc.titulo} ({doc.assunto[:120]})", oficio,
              ref=_ref(doc), detalhes={"codigo": doc.codigo, "hash": doc.hash_conteudo})
    guardado = None
    if doc.forma_assinatura == FormaAssinatura.GOVBR:  # a assinatura vale para este arquivo: ele não é mais gerado
        url = regras.url_publica(settings, str(request.base_url), doc.codigo)
        guardado, resumo_sha = regras.guardar_pdf(regras.gerar_pdf(doc, settings, hoje, url), hoje.year, settings)
        doc.arquivo_original, doc.arquivo_original_hash = guardado, resumo_sha
    try:
        db.commit()
    except BaseException:
        if guardado:
            remover_arquivo(guardado, settings)
        raise
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


@router.post("/{documento_id}/assinar", response_model=DocumentoOut,
             summary="Assina no app (quem elaborou ou quem dá o De acordo), confirmando a senha")
def assinar(documento_id: int, dados: Assinar, request: Request, db: DbDep, usuario: UsuarioDep,
            settings: SettingsDep, agora: AgoraDep, hoje: HojeDep):
    doc = regras.buscar(db, documento_id, usuario)
    papel = regras.papel_para_assinar(doc, usuario)
    if doc.forma_assinatura == FormaAssinatura.GOVBR:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este documento é assinado pelo GOV.BR: envie o PDF assinado")
    if papel is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Não há assinatura sua pendente neste documento")
    ip = request.client.host if request.client else "?"
    limite_login.verificar(usuario.login, ip)  # as mesmas regras de bloqueio do login
    if not verificar_senha(dados.senha, usuario.senha_hash):
        limite_login.registrar_erro(usuario.login, ip, settings)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha incorreta")
    limite_login.registrar_sucesso(usuario.login, ip)
    elaborador = papel == PapelAssinatura.ELABORADOR
    doc.assinaturas.append(AssinaturaDocumento(
        papel=papel, usuario_id=usuario.id, assinado_em=regras.instante(agora), ip=ip[:45],
        nome=doc.elaborador_nome if elaborador else doc.validador_nome,
        cargo=doc.elaborador_cargo if elaborador else doc.validador_cargo,
    ))
    como = "como quem elaborou" if elaborador else "com o De acordo"
    registrar(db, usuario, Acao.DOCUMENTO_ASSINADO, f"Assinou eletronicamente o {doc.titulo} {como}", doc.oficio,
              ref=_ref(doc))
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


@router.post("/{documento_id}/assinado", response_model=DocumentoOut,
             summary="Recebe o PDF assinado no GOV.BR, confere o certificado e registra as assinaturas novas")
def enviar_assinado(documento_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep,
                    hoje: HojeDep, arquivo: Annotated[UploadFile, File()]):
    regras.buscar(db, documento_id, usuario)
    # trava o documento: dois envios ao mesmo tempo não podem partir da mesma versão
    doc = db.scalars(select(Documento).where(Documento.id == documento_id).with_for_update()
                     .execution_options(populate_existing=True)).unique().one()
    if doc.forma_assinatura != FormaAssinatura.GOVBR:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este documento é assinado no app, com a senha")
    if doc.status != StatusDocumento.EMITIDO:
        raise HTTPException(status.HTTP_409_CONFLICT, "Só um documento emitido recebe assinatura")
    pendentes = regras.papeis_pendentes(doc)
    if not pendentes:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este documento já tem todas as assinaturas")
    limite = settings.upload_max_mb * 1024 * 1024
    novo = arquivo.file.read(limite + 1)
    if len(novo) > limite:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Arquivo maior que {settings.upload_max_mb} MB")
    if not novo.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Envie o PDF assinado no GOV.BR")
    base = regras.arquivo_vigente(doc, settings)
    if base is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O PDF da emissão não está guardado: cancele e emita de novo")
    try:
        lidas = conferir(novo, base, settings.certificados_dir)
    except AssinaturaInvalida as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None

    conhecidas = {a.impressao for a in doc.assinaturas}
    novas = [lida for lida in lidas if lida.impressao not in conhecidas]
    if not novas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Este arquivo não traz nenhuma assinatura nova")
    momento_agora = regras.instante(agora)
    for lida in novas:
        papel = regras.papel_da_assinatura(doc, lida)
        if papel is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"A assinatura é de {lida.nome}, que não é quem elaborou nem quem dá o De acordo. Se for a mesma pessoa, "
                "peça ao administrador para informar o CPF ou o nome completo no cadastro de usuários.")
        if papel not in pendentes:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{lida.nome} já assinou este documento")
        pendentes.remove(papel)
        elaborador = papel == PapelAssinatura.ELABORADOR
        # a hora é a informada na assinatura, se for possível (o relógio é o do portal); senão, a do recebimento
        plausivel = lida.momento is not None and doc.emitido_em <= lida.momento <= momento_agora
        doc.assinaturas.append(AssinaturaDocumento(
            papel=papel, usuario_id=doc.autor_id if elaborador else doc.validador_id,
            nome=doc.elaborador_nome if elaborador else doc.validador_nome,
            cargo=doc.elaborador_cargo if elaborador else doc.validador_cargo,
            assinado_em=lida.momento if plausivel else momento_agora, forma=FormaAssinatura.GOVBR,
            cert_nome=lida.nome, cert_cpf=mascarar_cpf(lida.cpf), cert_emissor=lida.emissor, cert_serie=lida.serie,
            impressao=lida.impressao,
        ))
        como = "como quem elaborou" if elaborador else "com o De acordo"
        registrar(db, usuario, Acao.DOCUMENTO_ASSINADO,
                  f"Enviou o {doc.titulo} assinado pelo GOV.BR por {lida.nome} {como}"[:500], doc.oficio, ref=_ref(doc),
                  detalhes={"certificado": lida.serie, "emissor": lida.emissor})
    guardado, resumo_sha = regras.guardar_pdf(novo, doc.ano, settings)
    doc.arquivo_assinado, doc.arquivo_assinado_hash = guardado, resumo_sha
    try:
        db.commit()
    except BaseException:
        remover_arquivo(guardado, settings)
        raise
    return _saida(regras.buscar(db, documento_id, usuario), usuario, hoje, settings)


@router.post("/{documento_id}/cancelar", response_model=DocumentoOut,
             summary="Cancela um documento emitido (quem elaborou ou o administrador), com o motivo")
def cancelar(documento_id: int, dados: Cancelar, db: DbDep, usuario: UsuarioDep, agora: AgoraDep, hoje: HojeDep,
             settings: SettingsDep):
    doc = regras.buscar(db, documento_id, usuario)
    if doc.status != StatusDocumento.EMITIDO:
        raise HTTPException(status.HTTP_409_CONFLICT, "Só um documento emitido pode ser cancelado")
    if doc.autor_id != usuario.id and not regras.eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só quem elaborou ou o administrador cancela o documento")
    doc.status = StatusDocumento.CANCELADO
    doc.cancelado_em, doc.cancelado_por_id = regras.instante(agora), usuario.id
    doc.motivo_cancelamento = dados.motivo
    registrar(db, usuario, Acao.DOCUMENTO_CANCELADO, f"Cancelou o {doc.titulo}: {dados.motivo}", doc.oficio,
              ref=_ref(doc))
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


# ---------- organização: pasta, prazo e conclusão ----------


def _exigir_organizador(doc: Documento, usuario: Usuario) -> None:
    if not regras.pode_organizar(doc, usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só quem elaborou ou o administrador organiza este documento")


@router.patch("/{documento_id}/organizacao", response_model=DocumentoOut,
              summary="Muda a pasta e o prazo (quem elaborou ou o administrador; em qualquer etapa)")
def organizar(documento_id: int, dados: Organizar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep,
              settings: SettingsDep):
    doc = regras.buscar(db, documento_id, usuario)
    _exigir_organizador(doc, usuario)
    valores = dados.model_dump(exclude_unset=True)
    mudancas = []
    if "pasta_id" in valores and valores["pasta_id"] != doc.pasta_id:
        doc.pasta = _pasta_valida(db, valores["pasta_id"], doc.pasta_id) if valores["pasta_id"] else None
        mudancas.append(f"pasta: {doc.pasta.nome}" if doc.pasta else "sem pasta")
    if "prazo" in valores and valores["prazo"] != doc.prazo:
        doc.prazo = valores["prazo"]
        mudancas.append(f"prazo: {doc.prazo:%d/%m/%Y}" if doc.prazo else "sem prazo")
    if mudancas:
        registrar(db, usuario, Acao.DOCUMENTO_ORGANIZADO, f"Organizou o {doc.titulo} ({'; '.join(mudancas)})",
                  doc.oficio, ref=_ref(doc))
        db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


@router.post("/{documento_id}/concluir", response_model=DocumentoOut,
             summary="Marca o documento emitido como concluído (entregue, respondido ou arquivado): o prazo para")
def concluir(documento_id: int, db: DbDep, usuario: UsuarioDep, agora: AgoraDep, hoje: HojeDep,
             settings: SettingsDep):
    doc = regras.buscar(db, documento_id, usuario)
    _exigir_organizador(doc, usuario)
    if doc.status != StatusDocumento.EMITIDO:
        raise HTTPException(status.HTTP_409_CONFLICT, "Só um documento emitido pode ser concluído")
    if doc.concluido_em is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O documento já está concluído")
    doc.concluido_em, doc.concluido_por_id = regras.instante(agora), usuario.id
    registrar(db, usuario, Acao.DOCUMENTO_CONCLUIDO, f"Concluiu o {doc.titulo}", doc.oficio, ref=_ref(doc))
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


@router.post("/{documento_id}/reabrir", response_model=DocumentoOut, summary="Desfaz a conclusão do documento")
def reabrir(documento_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep, settings: SettingsDep):
    doc = regras.buscar(db, documento_id, usuario)
    _exigir_organizador(doc, usuario)
    if doc.status != StatusDocumento.EMITIDO or doc.concluido_em is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O documento não está concluído")
    doc.concluido_em = doc.concluido_por_id = None
    registrar(db, usuario, Acao.DOCUMENTO_REABERTO, f"Reabriu o {doc.titulo}", doc.oficio, ref=_ref(doc))
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario, hoje, settings)


# ---------- verificação pública ----------


@publico.get("/verificar/{codigo}", response_model=Verificacao,
             summary="Confere um documento pelo código de verificação (sem login)")
def verificar(codigo: str, db: DbDep, settings: SettingsDep):
    doc = db.scalar(select(Documento).where(Documento.codigo == regras.normalizar_codigo(codigo)[:12]))
    if doc is None or doc.status == StatusDocumento.RASCUNHO:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhum documento com este código")
    return Verificacao(
        codigo=doc.codigo, tipo=doc.tipo, titulo=doc.titulo, status=doc.status, data_documento=doc.data_documento,
        assunto=doc.assunto, elaborador_nome=doc.elaborador_nome, validador_nome=doc.validador_nome,
        emitido_em=doc.emitido_em, forma_assinatura=doc.forma_assinatura,
        assinaturas=[AssinaturaOut.model_validate(a) for a in doc.assinaturas],
        integro=regras.calcular_hash(doc) == doc.hash_conteudo and regras.arquivos_integros(doc, settings),
        hash_conteudo=doc.hash_conteudo,
        cancelado_em=doc.cancelado_em, motivo_cancelamento=doc.motivo_cancelamento,
        unidade=settings.unidade_nome.strip() or None,
    )
