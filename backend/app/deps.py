from datetime import date, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Feriado, Modulo, Perfil, Usuario
from app.seguranca import ler_token
from app.services.modulos import eh_gestor, nome_modulo
from app.services.prazos import CalendarioUtil

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_hoje() -> date:
    return date.today()


def get_agora() -> datetime:
    """Data e hora local, sem segundos fracionários (os testes trocam por um horário fixo)."""
    return datetime.now().replace(microsecond=0)


DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
HojeDep = Annotated[date, Depends(get_hoje)]
AgoraDep = Annotated[datetime, Depends(get_agora)]


def get_calendario(db: DbDep) -> CalendarioUtil:
    return CalendarioUtil(db.scalars(select(Feriado.data)))


CalendarioDep = Annotated[CalendarioUtil, Depends(get_calendario)]


def usuario_atual(token: Annotated[str, Depends(oauth2)], db: DbDep, settings: SettingsDep) -> Usuario:
    lido = ler_token(token, settings)
    usuario = db.get(Usuario, lido[0]) if lido else None
    # Sessão aberta antes de uma troca de senha não vale mais
    if usuario is None or not usuario.ativo or usuario.sessao_versao != lido[1]:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sessão inválida ou expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario


def eh_admin(usuario: Usuario) -> bool:
    """Admin do **Planner de Ofícios** (ADMIN do módulo ou MASTER): vê todos os ofícios e tem os poderes
    administrativos. Os outros módulos têm as próprias checagens (`exige_admin_do`)."""
    return usuario.eh_admin_no(Modulo.OFICIOS)


def exige_admin(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    if not eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação permitida apenas para administradores")
    return usuario


def exige_acesso_ao(modulo: Modulo):
    """Dependência para as rotas de um módulo: só entra quem foi habilitado nele (o MASTER sempre)."""

    def verificar(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
        if not usuario.tem_acesso(modulo):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Você não tem acesso ao módulo {nome_modulo(modulo)}")
        return usuario

    return verificar


def exige_admin_do(modulo: Modulo):
    def verificar(usuario: Annotated[Usuario, Depends(exige_acesso_ao(modulo))]) -> Usuario:
        if not usuario.eh_admin_no(modulo):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Ação permitida apenas para administradores do módulo {nome_modulo(modulo)}"
            )
        return usuario

    return verificar


def exige_gestor(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    """Gestão de usuários: MASTER ou admin de algum módulo."""
    if not eh_gestor(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação permitida apenas para administradores")
    return usuario


def exige_master(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    if usuario.perfil != Perfil.MASTER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação permitida apenas para o MASTER")
    return usuario


# Para `APIRouter(dependencies=...)`: todas as rotas do Planner de Ofícios exigem acesso ao módulo
ACESSO_OFICIOS = [Depends(exige_acesso_ao(Modulo.OFICIOS))]

UsuarioDep = Annotated[Usuario, Depends(usuario_atual)]  # qualquer usuário autenticado (sem olhar módulo)
AdminDep = Annotated[Usuario, Depends(exige_admin)]  # admin do Planner de Ofícios
MasterDep = Annotated[Usuario, Depends(exige_master)]
GestorDep = Annotated[Usuario, Depends(exige_gestor)]  # MASTER ou admin de algum módulo
