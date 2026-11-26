"""Modelos de documento e pastas do módulo Documentos.

O administrador do módulo cadastra os modelos da instituição (declaração, relatório, ata, termo…) e as pastas; todos
os usuários do módulo consultam os ativos. Fica em arquivo próprio e é incluído antes de `documentos.py`, para que
`/modelos` e `/pastas` não sejam lidos como `/{documento_id}`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import DbDep, HojeDep, SettingsDep, UsuarioDep, exige_acesso_ao
from app.models import Documento, ModeloDocumento, Modulo, PastaDocumento, StatusDocumento, Usuario
from app.schemas_documentos import ModeloAtualizar, ModeloEntrada, ModeloOut, PastaAtualizar, PastaEntrada, PastaOut
from app.services import documentos as regras
from app.services import modelos_documento as modelos
from app.services.auditoria import Acao, registrar

router = APIRouter(prefix="/api/documentos", tags=["Documentos"],
                   dependencies=[Depends(exige_acesso_ao(Modulo.DOCUMENTOS))])

NOME_CAMPO = {"nome": "nome", "descricao": "descrição", "estrutura": "estrutura", "digitos": "numeração",
              "recuo_cm": "recuo", "forma_assinatura": "assinatura sugerida", "mostrar_assunto": "linha do assunto",
              "data_no_fim": "posição da data", "rotulo_ident": "rótulo da matrícula", "vocativo": "vocativo",
              "fecho": "fecho", "texto_modelo": "texto do modelo", "ativo": "situação"}
TEXTO_EXEMPLO = ("Este é o primeiro parágrafo do texto, com o recuo do modelo, em Times New Roman 12, justificado e com "
                 "espaçamento 1,5, como sai nos documentos.\n"
                 "Segundo parágrafo do texto.\n"
                 "# Título de uma seção (linha começando com #)\n"
                 "- Item de uma lista (linha começando com -)\n"
                 "- Outro item")


def _exigir_admin(usuario: Usuario) -> None:
    if not regras.eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Só o administrador do módulo Documentos cadastra os modelos e as pastas")


def _texto(valor: str | None) -> str | None:
    return valor.strip() or None if isinstance(valor, str) else None


# ---------- modelos ----------


def _em_uso(db: Session) -> dict[str, int]:
    return dict(db.execute(select(Documento.tipo, func.count()).group_by(Documento.tipo)).all())


def _modelo(db: Session, codigo: str) -> ModeloDocumento:
    modelo = db.get(ModeloDocumento, codigo)
    if modelo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modelo de documento não encontrado")
    return modelo


def _nome_livre(db: Session, nome: str, codigo: str | None = None) -> None:
    outro = db.scalar(select(ModeloDocumento).where(func.lower(ModeloDocumento.nome) == nome.lower()))
    if outro is not None and outro.codigo != codigo:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe o modelo {outro.nome}")


@router.get("/modelos", response_model=list[ModeloOut],
            summary="Modelos de documento (o administrador vê também os desativados e quantos documentos usam cada um)")
def listar_modelos(db: DbDep, usuario: UsuarioDep):
    admin = regras.eh_admin(usuario)
    consulta = select(ModeloDocumento).order_by(ModeloDocumento.sistema.desc(), ModeloDocumento.nome)
    if not admin:
        consulta = consulta.where(ModeloDocumento.ativo.is_(True))
    uso = _em_uso(db) if admin else {}
    return [ModeloOut.model_validate(m).model_copy(update={"em_uso": uso.get(m.codigo, 0)})
            for m in db.scalars(consulta)]


@router.post("/modelos", response_model=ModeloOut, status_code=status.HTTP_201_CREATED,
             summary="Cadastra um modelo de documento da instituição (só o administrador do módulo)")
def criar_modelo(dados: ModeloEntrada, db: DbDep, usuario: UsuarioDep):
    _exigir_admin(usuario)
    valores = dados.model_dump()
    valores["nome"], valores["descricao"] = dados.nome.strip(), _texto(dados.descricao)
    valores["rotulo_ident"] = dados.rotulo_ident.strip()
    _nome_livre(db, valores["nome"])
    modelo = ModeloDocumento(codigo=modelos.gerar_codigo(db, valores["nome"]), sistema=False, **valores)
    db.add(modelo)
    registrar(db, usuario, Acao.MODELO_DOCUMENTO_CRIADO, f"Cadastrou o modelo de documento {modelo.nome}",
              ref=f"Modelo de documento {modelo.nome}")
    db.commit()
    return ModeloOut.model_validate(modelo)


@router.post("/modelos/previa", summary="PDF de exemplo do modelo, sem salvar (para conferir com o da instituição)")
def previa_modelo(dados: ModeloEntrada, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep):
    _exigir_admin(usuario)
    modelo = ModeloDocumento(codigo="PREVIA", sistema=False, **dados.model_dump())
    exemplo = Documento(
        tipo=modelo.codigo, status=StatusDocumento.RASCUNHO, forma_assinatura=dados.forma_assinatura,
        assunto="Assunto do documento", vocativo=dados.vocativo, fecho=dados.fecho,
        corpo=dados.texto_modelo.strip() or TEXTO_EXEMPLO,
        dest_tratamento="A/C sr. (sra.)", dest_nome="Nome do destinatário", dest_cargo="Cargo do destinatário",
        dest_endereco="Órgão ou empresa e endereço", de="Setor de origem", para="Setor de destino",
        elaborador_nome=usuario.nome, elaborador_cargo=usuario.cargo or "Cargo de quem elaborou",
        elaborador_ident=usuario.matricula or "0000", validador_nome="Nome de quem dá o De acordo",
        validador_cargo="Cargo de quem dá o De acordo", validador_ident=None,
    )
    exemplo.modelo = modelo  # nada disto é salvo
    return Response(regras.gerar_pdf(exemplo, settings, hoje), media_type="application/octet-stream",
                    headers={"Content-Disposition": 'inline; filename="exemplo-do-modelo.pdf"',
                             "X-Content-Type-Options": "nosniff"})


@router.patch("/modelos/{codigo}", response_model=ModeloOut,
              summary="Altera um modelo (os documentos já emitidos não mudam: guardam o formato da emissão)")
def alterar_modelo(codigo: Annotated[str, Path(max_length=40)], dados: ModeloAtualizar, db: DbDep,
                   usuario: UsuarioDep):
    _exigir_admin(usuario)
    modelo = _modelo(db, codigo)
    valores = {c: v for c, v in dados.model_dump(exclude_unset=True).items() if v is not None or c == "descricao"}
    if "descricao" in valores:
        valores["descricao"] = _texto(valores["descricao"])
    for campo in ("nome", "rotulo_ident"):
        if campo in valores:
            valores[campo] = valores[campo].strip()
    if "nome" in valores:
        _nome_livre(db, valores["nome"], modelo.codigo)
    if modelo.sistema:
        if any(c in valores and valores[c] != getattr(modelo, c) for c in ("estrutura", "digitos")):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "O ofício e o memorando mantêm a estrutura e a numeração (a do ofício segue o Planner)")
        if valores.get("ativo") is False:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                "O ofício e o memorando vêm com o sistema e não podem ser desativados")
    mudou = [c for c, v in valores.items() if getattr(modelo, c) != v]
    for campo in mudou:
        setattr(modelo, campo, valores[campo])
    if mudou:
        registrar(db, usuario, Acao.MODELO_DOCUMENTO_ALTERADO,
                  f"Alterou o modelo de documento {modelo.nome} ({', '.join(NOME_CAMPO[c] for c in mudou)})",
                  ref=f"Modelo de documento {modelo.nome}")
        db.commit()
    return ModeloOut.model_validate(modelo).model_copy(update={"em_uso": _em_uso(db).get(modelo.codigo, 0)})


@router.delete("/modelos/{codigo}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Apaga um modelo que nunca foi usado (os outros se desativam)")
def excluir_modelo(codigo: Annotated[str, Path(max_length=40)], db: DbDep, usuario: UsuarioDep):
    _exigir_admin(usuario)
    modelo = _modelo(db, codigo)
    if modelo.sistema:
        raise HTTPException(status.HTTP_409_CONFLICT, "O ofício e o memorando vêm com o sistema e não podem ser apagados")
    if _em_uso(db).get(modelo.codigo):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Já há documentos feitos com este modelo: desative-o em vez de apagar")
    registrar(db, usuario, Acao.MODELO_DOCUMENTO_EXCLUIDO, f"Apagou o modelo de documento {modelo.nome}",
              ref=f"Modelo de documento {modelo.nome}")
    db.delete(modelo)
    db.commit()


# ---------- pastas ----------


def _pasta(db: Session, pasta_id: int) -> PastaDocumento:
    pasta = db.get(PastaDocumento, pasta_id)
    if pasta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pasta não encontrada")
    return pasta


def _pasta_livre(db: Session, nome: str, pasta_id: int | None = None) -> None:
    outra = db.scalar(select(PastaDocumento).where(func.lower(PastaDocumento.nome) == nome.lower()))
    if outra is not None and outra.id != pasta_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe a pasta {outra.nome}")


def _contagem(db: Session, usuario: Usuario) -> dict[int, int]:
    """Documentos por pasta, contando só os que o usuário vê."""
    return dict(db.execute(select(Documento.pasta_id, func.count())
                           .where(regras.filtro_visiveis(usuario), Documento.pasta_id.is_not(None))
                           .group_by(Documento.pasta_id)).all())


def _pasta_out(pasta: PastaDocumento, contagem: dict[int, int]) -> PastaOut:
    return PastaOut(id=pasta.id, nome=pasta.nome, descricao=pasta.descricao, ativo=pasta.ativo,
                    documentos=contagem.get(pasta.id, 0))


@router.get("/pastas", response_model=list[PastaOut], summary="Pastas (o administrador vê também as desativadas)")
def listar_pastas(db: DbDep, usuario: UsuarioDep):
    consulta = select(PastaDocumento).order_by(PastaDocumento.nome)
    if not regras.eh_admin(usuario):
        consulta = consulta.where(PastaDocumento.ativo.is_(True))
    contagem = _contagem(db, usuario)
    return [_pasta_out(p, contagem) for p in db.scalars(consulta)]


@router.post("/pastas", response_model=PastaOut, status_code=status.HTTP_201_CREATED,
             summary="Cria uma pasta (só o administrador do módulo)")
def criar_pasta(dados: PastaEntrada, db: DbDep, usuario: UsuarioDep):
    _exigir_admin(usuario)
    nome = dados.nome.strip()
    _pasta_livre(db, nome)
    pasta = PastaDocumento(nome=nome, descricao=_texto(dados.descricao), ativo=True)
    db.add(pasta)
    registrar(db, usuario, Acao.PASTA_DOCUMENTO_CRIADA, f"Criou a pasta de documentos {nome}", ref=f"Pasta {nome}")
    db.commit()
    return _pasta_out(pasta, {})


@router.patch("/pastas/{pasta_id}", response_model=PastaOut, summary="Renomeia, descreve, desativa ou reativa a pasta")
def alterar_pasta(pasta_id: int, dados: PastaAtualizar, db: DbDep, usuario: UsuarioDep):
    _exigir_admin(usuario)
    pasta = _pasta(db, pasta_id)
    valores = dados.model_dump(exclude_unset=True)
    if valores.get("nome"):
        valores["nome"] = valores["nome"].strip()
        _pasta_livre(db, valores["nome"], pasta.id)
    else:
        valores.pop("nome", None)
    if "descricao" in valores:
        valores["descricao"] = _texto(valores["descricao"])
    if valores.get("ativo") is None:
        valores.pop("ativo", None)
    mudou = [c for c, v in valores.items() if getattr(pasta, c) != v]
    for campo in mudou:
        setattr(pasta, campo, valores[campo])
    if mudou:
        registrar(db, usuario, Acao.PASTA_DOCUMENTO_ALTERADA,
                  f"Alterou a pasta de documentos {pasta.nome} ({', '.join(NOME_CAMPO.get(c, c) for c in mudou)})",
                  ref=f"Pasta {pasta.nome}")
        db.commit()
    return _pasta_out(pasta, _contagem(db, usuario))


@router.delete("/pastas/{pasta_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Apaga a pasta; os documentos dela ficam sem pasta")
def excluir_pasta(pasta_id: int, db: DbDep, usuario: UsuarioDep):
    _exigir_admin(usuario)
    pasta = _pasta(db, pasta_id)
    total = db.scalar(select(func.count()).select_from(Documento).where(Documento.pasta_id == pasta.id))
    registrar(db, usuario, Acao.PASTA_DOCUMENTO_EXCLUIDA,
              f"Apagou a pasta de documentos {pasta.nome}" + (f" ({total} documento(s) ficaram sem pasta)" if total else ""),
              ref=f"Pasta {pasta.nome}")
    db.delete(pasta)
    db.commit()
