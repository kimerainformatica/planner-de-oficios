"""Documentos: ofícios e memorandos redigidos no app, impressos no modelo da unidade.

Módulo próprio (DOCUMENTOS), integrado ao Planner de Ofícios: com "registrar no Planner", o ofício emitido é
cadastrado lá em nome de quem elaborou (que precisa usar o Planner).
Fluxo: rascunho (só quem elaborou edita) → emissão (número, data, código de verificação; o ofício entra no Planner)
→ assinaturas (à mão no papel e/ou eletrônicas no app, com a senha) → se preciso, cancelamento com motivo.
A verificação pública (sem login) confere o código impresso no rodapé e o QR code.
"""

import re
import unicodedata
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.deps import AgoraDep, DbDep, HojeDep, SettingsDep, UsuarioDep, exige_acesso_ao
from app.models import (
    AssinaturaDocumento,
    Documento,
    Modulo,
    PapelAssinatura,
    StatusDocumento,
    TipoDocumento,
    Usuario,
)
from app.schemas import OficioCriar
from app.schemas_documentos import (
    Assinante,
    Assinar,
    AssinaturaOut,
    Cancelar,
    DocumentoAtualizar,
    DocumentoCriar,
    DocumentoOut,
    DocumentoResumo,
    PaginaDocumentos,
    TimbradoOut,
    Verificacao,
)
from app.seguranca import verificar_senha
from app.services import documentos as regras
from app.services import limite_login
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


def _saida(doc: Documento, usuario: Usuario) -> DocumentoOut:
    dados = {campo: getattr(doc, campo) for campo in DocumentoOut.model_fields if hasattr(doc, campo)}
    dados["assinaturas"] = [AssinaturaOut.model_validate(a) for a in doc.assinaturas]
    dados["cancelado_por_nome"] = doc.cancelado_por.nome if doc.cancelado_por else None
    dados["usa_planner"] = doc.autor.tem_acesso(Modulo.OFICIOS)
    autor = doc.autor_id == usuario.id
    dados["pode_editar"] = autor and doc.status == StatusDocumento.RASCUNHO
    dados["pode_cancelar"] = doc.status == StatusDocumento.EMITIDO and (autor or regras.eh_admin(usuario))
    dados["assinar_como"] = regras.papel_para_assinar(doc, usuario)
    dados["pendencias"] = regras.pendencias_para_emitir(doc) if doc.status == StatusDocumento.RASCUNHO else []
    return DocumentoOut.model_validate(dados)


def _resumo(doc: Documento, usuario: Usuario) -> DocumentoResumo:
    return DocumentoResumo(
        id=doc.id, tipo=doc.tipo, status=doc.status, titulo=doc.titulo, numero_formatado=doc.numero_formatado,
        assunto=doc.assunto, destino=doc.dest_nome if doc.tipo == TipoDocumento.OFICIO else doc.para,
        elaborador_nome=doc.elaborador_nome, validador_nome=doc.validador_nome, data_documento=doc.data_documento,
        atualizado_em=doc.atualizado_em, assinaturas=len(doc.assinaturas),
        assinaturas_previstas=2 if doc.validador_nome else 1,
        minha_assinatura_pendente=regras.papel_para_assinar(doc, usuario) is not None,
    )


def _sem_assinatura(papel: PapelAssinatura):
    return not_(exists().where(AssinaturaDocumento.documento_id == Documento.id, AssinaturaDocumento.papel == papel))


def _aguardando(usuario: Usuario):
    """Documentos emitidos em que falta a assinatura eletrônica do usuário."""
    return and_(
        Documento.status == StatusDocumento.EMITIDO,
        or_(
            and_(Documento.autor_id == usuario.id, _sem_assinatura(PapelAssinatura.ELABORADOR)),
            and_(Documento.validador_id == usuario.id, Documento.validador_nome.is_not(None),
                 _sem_assinatura(PapelAssinatura.VALIDADOR)),
        ),
    )


def _visiveis(usuario: Usuario):
    if regras.eh_admin(usuario):
        return Documento.id.is_not(None)
    return or_(Documento.autor_id == usuario.id, Documento.validador_id == usuario.id)


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


@router.get("", response_model=PaginaDocumentos, summary="Lista os documentos (os seus, os para assinar ou todos)")
def listar(
    db: DbDep, usuario: UsuarioDep,
    escopo: Annotated[str, Query(pattern="^(meus|assinar|todos)$")] = "todos",
    tipo: TipoDocumento | None = None,
    situacao: Annotated[StatusDocumento | None, Query(alias="status")] = None,
    busca: Annotated[str | None, Query(max_length=100)] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 30,
):
    filtros = [_visiveis(usuario)]
    if escopo == "meus":
        filtros.append(Documento.autor_id == usuario.id)
    elif escopo == "assinar":
        filtros.append(_aguardando(usuario))
    if tipo:
        filtros.append(Documento.tipo == tipo)
    if situacao:
        filtros.append(Documento.status == situacao)
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        filtros.append(or_(Documento.assunto.ilike(termo), Documento.dest_nome.ilike(termo),
                           Documento.para.ilike(termo), Documento.de.ilike(termo),
                           Documento.elaborador_nome.ilike(termo), Documento.codigo.ilike(termo)))
    total = db.scalar(select(func.count()).select_from(Documento).where(*filtros))
    itens = db.scalars(select(Documento).where(*filtros).order_by(Documento.atualizado_em.desc(), Documento.id.desc())
                       .offset((pagina - 1) * por_pagina).limit(por_pagina)).unique().all()
    return PaginaDocumentos(itens=[_resumo(d, usuario) for d in itens], total=total, pagina=pagina,
                            por_pagina=por_pagina)


@router.get("/resumo", summary="Quantos documentos aguardam a assinatura do usuário (contador do menu)")
def resumo(db: DbDep, usuario: UsuarioDep):
    return {"para_assinar": db.scalar(select(func.count()).select_from(Documento).where(_aguardando(usuario)))}


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
def detalhar(documento_id: int, db: DbDep, usuario: UsuarioDep):
    return _saida(regras.buscar(db, documento_id, usuario), usuario)


@router.get("/{documento_id}/pdf", summary="PDF do documento no modelo da unidade (rascunho sai marcado)")
def pdf(documento_id: int, request: Request, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep,
        bruto: Annotated[bool, Query(description="application/octet-stream (usado pelo front-end)")] = False):
    doc = regras.buscar(db, documento_id, usuario)
    url = regras.url_publica(settings, str(request.base_url), doc.codigo) if doc.codigo else None
    conteudo = regras.gerar_pdf(doc, settings, hoje, url)
    return Response(
        conteudo, media_type="application/octet-stream" if bruto else "application/pdf",
        headers={"Content-Disposition": f'inline; filename="{_nome_arquivo(doc)}"',
                 "X-Content-Type-Options": "nosniff"},
    )


# ---------- rascunho ----------


@router.post("", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED,
             summary="Começa um rascunho (com os dados de quem elabora já preenchidos)")
def criar(dados: DocumentoCriar, db: DbDep, usuario: UsuarioDep):
    oficio = dados.tipo == TipoDocumento.OFICIO
    doc = Documento(
        tipo=dados.tipo, status=StatusDocumento.RASCUNHO, autor_id=usuario.id, assunto="", corpo="",
        vocativo="Prezado (a) Senhor (a)," if oficio else "Prezado(a),", fecho="Atenciosamente,",
        dest_tratamento="A/C sr. (sra.)" if oficio else None,
        registrar_no_planner=oficio and usuario.tem_acesso(Modulo.OFICIOS),
        elaborador_nome=usuario.nome, elaborador_cargo=usuario.cargo, elaborador_ident=usuario.matricula,
    )
    db.add(doc)
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario)


@router.patch("/{documento_id}", response_model=DocumentoOut, summary="Salva o rascunho (só quem elaborou)")
def atualizar(documento_id: int, dados: DocumentoAtualizar, db: DbDep, usuario: UsuarioDep):
    doc = regras.buscar(db, documento_id, usuario)
    regras.exigir_rascunho_do_autor(doc, usuario)
    valores = dados.model_dump(exclude_unset=True)
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
    return _saida(regras.buscar(db, doc.id, usuario), usuario)


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Descarta o rascunho")
def excluir(documento_id: int, db: DbDep, usuario: UsuarioDep):
    doc = regras.buscar(db, documento_id, usuario)
    regras.exigir_rascunho_do_autor(doc, usuario)
    db.delete(doc)
    db.commit()


@router.post("/{documento_id}/duplicar", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED,
             summary="Novo rascunho com o mesmo texto (para corrigir um emitido ou reaproveitar)")
def duplicar(documento_id: int, db: DbDep, usuario: UsuarioDep):
    origem = regras.buscar(db, documento_id, usuario)
    meu = origem.autor_id == usuario.id
    copia = Documento(
        tipo=origem.tipo, status=StatusDocumento.RASCUNHO, autor_id=usuario.id,
        **{c: getattr(origem, c) for c in ("assunto", "vocativo", "corpo", "fecho", "dest_tratamento", "dest_nome",
                                           "dest_cargo", "dest_endereco", "de", "para", "oficio_tipo",
                                           "destinatario_tipo", "destinatario_setor")},
        registrar_no_planner=origem.registrar_no_planner and usuario.tem_acesso(Modulo.OFICIOS),
        elaborador_nome=usuario.nome,
        elaborador_cargo=origem.elaborador_cargo if meu else usuario.cargo,
        elaborador_ident=origem.elaborador_ident if meu else usuario.matricula,
    )
    if origem.validador_nome and origem.validador_id != usuario.id:
        copia.validador_id, copia.validador_nome = origem.validador_id, origem.validador_nome
        copia.validador_cargo, copia.validador_ident = origem.validador_cargo, origem.validador_ident
    db.add(copia)
    db.commit()
    return _saida(regras.buscar(db, copia.id, usuario), usuario)


# ---------- emissão, assinatura e cancelamento ----------


@router.post("/{documento_id}/emitir", response_model=DocumentoOut,
             summary="Emite: dá número, data e código de verificação; o ofício pode ser cadastrado no Planner")
def emitir(documento_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep, agora: AgoraDep):
    doc = regras.buscar(db, documento_id, usuario)
    regras.exigir_rascunho_do_autor(doc, usuario)
    faltas = regras.pendencias_para_emitir(doc)
    if faltas:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Para emitir, preencha " + ", ".join(faltas) + ".")
    integrar = doc.tipo == TipoDocumento.OFICIO and doc.registrar_no_planner
    if integrar and not usuario.tem_acesso(Modulo.OFICIOS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "Você não usa o Planner de Ofícios: desmarque o registro no Planner ou peça o acesso")
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
    db.commit()
    return _saida(regras.buscar(db, doc.id, usuario), usuario)


@router.post("/{documento_id}/assinar", response_model=DocumentoOut,
             summary="Assina eletronicamente (quem elaborou ou quem dá o De acordo), confirmando a senha")
def assinar(documento_id: int, dados: Assinar, request: Request, db: DbDep, usuario: UsuarioDep,
            settings: SettingsDep, agora: AgoraDep):
    doc = regras.buscar(db, documento_id, usuario)
    papel = regras.papel_para_assinar(doc, usuario)
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
    return _saida(regras.buscar(db, doc.id, usuario), usuario)


@router.post("/{documento_id}/cancelar", response_model=DocumentoOut,
             summary="Cancela um documento emitido (quem elaborou ou o administrador), com o motivo")
def cancelar(documento_id: int, dados: Cancelar, db: DbDep, usuario: UsuarioDep, agora: AgoraDep):
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
    return _saida(regras.buscar(db, doc.id, usuario), usuario)


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
        emitido_em=doc.emitido_em, assinaturas=[AssinaturaOut.model_validate(a) for a in doc.assinaturas],
        integro=regras.calcular_hash(doc) == doc.hash_conteudo, hash_conteudo=doc.hash_conteudo,
        cancelado_em=doc.cancelado_em, motivo_cancelamento=doc.motivo_cancelamento,
        unidade=settings.unidade_nome.strip() or None,
    )
