from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import AdminDep, DbDep
from app.models import PERFIS_ADMIN, Perfil, Usuario
from app.schemas import UsuarioAtualizar, UsuarioCriar, UsuarioOut
from app.seguranca import gerar_hash_senha
from app.services.auditoria import Acao, campos_legiveis, diferencas, registrar

router = APIRouter(prefix="/api/usuarios", tags=["Usuários (admin/master)"])

ROTULO = {Perfil.MASTER: "master", Perfil.ADMIN: "administrador", Perfil.CLIENTE: "cliente"}


def _exige_master_para(perfil: Perfil | None, quem: Usuario, acao: str) -> None:
    if perfil in PERFIS_ADMIN and quem.perfil != Perfil.MASTER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Só o MASTER pode {acao} administradores")


@router.get("", response_model=list[UsuarioOut])
def listar(db: DbDep, _: AdminDep):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, db: DbDep, admin: AdminDep):
    _exige_master_para(dados.perfil, admin, "criar")
    if db.scalar(select(Usuario.id).where(Usuario.login == dados.login)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"O login {dados.login} já está em uso")
    usuario = Usuario(
        nome=dados.nome, login=dados.login, senha_hash=gerar_hash_senha(dados.senha), perfil=dados.perfil
    )
    db.add(usuario)
    registrar(db, admin, Acao.USUARIO_CRIADO,
              f"Criou o usuário {dados.nome} ({dados.login}) como {ROTULO[dados.perfil]}",
              ref=f"Usuário {dados.login}", detalhes={"perfil": dados.perfil.value})
    db.commit()
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def atualizar(usuario_id: int, dados: UsuarioAtualizar, db: DbDep, admin: AdminDep):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    proprio = usuario.id == admin.id
    if not proprio:
        _exige_master_para(usuario.perfil, admin, "alterar contas de")
    _exige_master_para(dados.perfil, admin, "promover usuários a")
    if proprio and (dados.ativo is False or (dados.perfil is not None and dados.perfil != usuario.perfil)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Você não pode desativar nem mudar o perfil do próprio usuário")

    deixa_de_ser_master = usuario.perfil == Perfil.MASTER and (
        dados.ativo is False or (dados.perfil is not None and dados.perfil != Perfil.MASTER)
    )
    if deixa_de_ser_master:
        outros = db.scalar(select(func.count()).select_from(Usuario).where(
            Usuario.perfil == Perfil.MASTER, Usuario.ativo.is_(True), Usuario.id != usuario.id))
        if not outros:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A plataforma precisa de pelo menos um MASTER ativo")

    if dados.login is not None and dados.login.lower() != usuario.login.lower():
        if db.scalar(select(Usuario.id).where(func.lower(Usuario.login) == dados.login.lower(), Usuario.id != usuario.id)):
            raise HTTPException(status.HTTP_409_CONFLICT, f"O login {dados.login} já está em uso")

    novos = dados.model_dump(exclude_unset=True, exclude_none=True, exclude={"senha"})
    mudancas = diferencas({c: getattr(usuario, c) for c in novos}, novos)
    for campo, valor in novos.items():
        setattr(usuario, campo, valor)
    if dados.senha is not None:
        usuario.senha_hash = gerar_hash_senha(dados.senha)
        usuario.sessao_versao += 1  # encerra as sessões abertas com a senha antiga (em todos os computadores)
        mudancas["senha"] = {"de": None, "para": "redefinida"}
    if mudancas:
        registrar(db, admin, Acao.USUARIO_ALTERADO, f"Alterou o usuário {usuario.nome} ({campos_legiveis(mudancas)})",
                  ref=f"Usuário {usuario.login}", detalhes=mudancas)
    db.commit()
    return usuario
