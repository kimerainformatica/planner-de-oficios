from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import PERFIS_ADMIN, Feriado, Perfil, Usuario
from app.seguranca import ler_token
from app.services.prazos import CalendarioUtil

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_hoje() -> date:
    return date.today()


DbDep = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
HojeDep = Annotated[date, Depends(get_hoje)]


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
    """ADMIN e MASTER: veem todos os ofícios e têm os poderes administrativos."""
    return usuario.perfil in PERFIS_ADMIN


def exige_admin(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    if not eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação permitida apenas para administradores")
    return usuario


def exige_master(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    if usuario.perfil != Perfil.MASTER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ação permitida apenas para o MASTER")
    return usuario


UsuarioDep = Annotated[Usuario, Depends(usuario_atual)]
AdminDep = Annotated[Usuario, Depends(exige_admin)]
MasterDep = Annotated[Usuario, Depends(exige_master)]
