"""Hash de senha (PBKDF2, biblioteca padrão) e token JWT."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings

ITERACOES = 600_000


def gerar_hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, ITERACOES)
    return f"pbkdf2_sha256${ITERACOES}${salt.hex()}${h.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        _, iteracoes, salt, h = armazenado.split("$")
        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(salt), int(iteracoes))
    except ValueError:
        return False
    return hmac.compare_digest(calculado.hex(), h)


def criar_token(usuario_id: int, perfil: str, sessao_versao: int, settings: Settings) -> str:
    agora = datetime.now(UTC)
    payload = {
        "sub": str(usuario_id),
        "perfil": perfil,
        "sv": sessao_versao,  # trocar a senha muda a versão e invalida os tokens antigos
        "iat": agora,
        "exp": agora + timedelta(minutes=settings.jwt_expira_minutos),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algoritmo)


def ler_token(token: str, settings: Settings) -> tuple[int, int] | None:
    """(id do usuário, versão da sessão) ou None se o token for inválido ou expirado."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algoritmo])
        return int(payload["sub"]), int(payload.get("sv", 0))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
