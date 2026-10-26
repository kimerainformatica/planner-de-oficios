"""Inicia a API:  python -m app   (APP_HOST/APP_PORTA no .env; padrão 0.0.0.0:3112, acessível na rede)."""

import argparse
import logging
import socket

import uvicorn

from app.config import get_settings
from app.services.integridade import iniciar_agendamento

settings = get_settings()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--reload", action="store_true", help="Reinicia ao salvar arquivos (desenvolvimento)")
args = parser.parse_args()

if settings.app_host not in ("127.0.0.1", "localhost") and settings.chave_jwt_insegura:
    raise SystemExit(
        "JWT_SECRET padrão ou curta: com a API aberta na rede, qualquer um poderia forjar um login.\n"
        'Gere uma chave com  python -c "import secrets; print(secrets.token_urlsafe(48))"  e coloque no .env.'
    )

if settings.app_host == "0.0.0.0":
    ip = socket.gethostbyname(socket.gethostname())
    print(f"Acesso na rede: http://{ip}:{settings.app_porta}")

# Avisos do sistema (verificação dos arquivos, bloqueios de login) vão para o mesmo log do servidor
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
iniciar_agendamento(settings)
uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_porta, reload=args.reload)
