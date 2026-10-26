from typing import Annotated

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.deps import DbDep, SettingsDep, UsuarioDep
from app.models import Usuario
from app.schemas import Token, UsuarioOut
from app.seguranca import criar_token, verificar_senha
from app.services import limite_login

log = logging.getLogger("planner.login")

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], request: Request, db: DbDep, settings: SettingsDep
):
    ip = request.client.host if request.client else "?"
    limite_login.verificar(form.username, ip)  # 429 enquanto durar um bloqueio
    usuario = db.scalar(select(Usuario).where(Usuario.login == form.username))
    if usuario is None or not usuario.ativo or not verificar_senha(form.password, usuario.senha_hash):
        if limite_login.registrar_erro(form.username, ip, settings):
            log.warning("Login %r bloqueado por %d min após %d senhas erradas (computador %s)", form.username,
                        settings.login_bloqueio_minutos, settings.login_max_tentativas, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login ou senha incorretos")
    limite_login.registrar_sucesso(form.username, ip)
    return Token(
        access_token=criar_token(usuario.id, usuario.perfil.value, usuario.sessao_versao, settings),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/me", response_model=UsuarioOut)
def eu(usuario: UsuarioDep):
    return usuario
