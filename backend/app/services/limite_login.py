"""Limite de tentativas de login: depois de N senhas erradas seguidas (por login e computador), bloqueia por
alguns minutos. Fica em memória: reiniciar o servidor zera os contadores.
"""

import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.config import Settings


@dataclass
class _Contagem:
    erros: int = 0
    bloqueado_ate: float = 0.0


_contagens: dict[tuple[str, str], _Contagem] = {}
_trava = threading.Lock()


def _chave(login: str, ip: str) -> tuple[str, str]:
    return login.strip().lower(), ip


def verificar(login: str, ip: str) -> None:
    """Antes de conferir a senha: recusa enquanto o bloqueio durar."""
    with _trava:
        c = _contagens.get(_chave(login, ip))
        restante = c.bloqueado_ate - time.monotonic() if c else 0
    if restante > 0:
        minutos = max(1, round(restante / 60))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Muitas tentativas com senha errada. Tente de novo em {minutos} minuto{'s' if minutos > 1 else ''}.",
            headers={"Retry-After": str(int(restante) + 1)},
        )


def registrar_erro(login: str, ip: str, settings: Settings) -> bool:
    """Devolve True quando este erro iniciou um bloqueio."""
    with _trava:
        c = _contagens.setdefault(_chave(login, ip), _Contagem())
        c.erros += 1
        if c.erros >= settings.login_max_tentativas:
            c.erros = 0
            c.bloqueado_ate = time.monotonic() + settings.login_bloqueio_minutos * 60
            return True
        return False


def registrar_sucesso(login: str, ip: str) -> None:
    with _trava:
        _contagens.pop(_chave(login, ip), None)


def limpar() -> None:
    """Para os testes."""
    with _trava:
        _contagens.clear()
