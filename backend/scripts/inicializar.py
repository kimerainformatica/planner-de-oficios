"""Cria o primeiro administrador e cadastra os feriados nacionais.

Uso (dentro de backend/):
    python -m scripts.inicializar --login admin --nome "Administrador"
A senha é pedida no terminal.
"""

import argparse
import getpass
import secrets
from datetime import date

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Feriado, Perfil, Usuario
from app.seguranca import gerar_hash_senha
from app.services.prazos import feriados_nacionais


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--login", default="admin")
    parser.add_argument("--nome", default="Administrador")
    parser.add_argument("--anos", type=int, nargs="*", help="Anos dos feriados (padrão: ano atual e seguinte)")
    parser.add_argument("--gerar-senha", action="store_true", help="Gera e mostra uma senha aleatória em vez de perguntar")
    args = parser.parse_args()

    anos = args.anos or [date.today().year, date.today().year + 1]

    with SessionLocal() as db:
        if db.scalar(select(Usuario.id).where(Usuario.login == args.login)):
            print(f"Usuário '{args.login}' já existe; nada a fazer.")
        else:
            if args.gerar_senha:
                senha = secrets.token_urlsafe(9)
                print(f"Senha gerada para '{args.login}': {senha}  (troque depois em Usuários)")
            else:
                senha = getpass.getpass(f"Senha para '{args.login}' (mín. 8 caracteres): ")
                if len(senha) < 8 or senha != getpass.getpass("Confirme a senha: "):
                    raise SystemExit("Senha inválida ou confirmação diferente.")
            db.add(Usuario(nome=args.nome, login=args.login, senha_hash=gerar_hash_senha(senha), perfil=Perfil.MASTER))
            print(f"Administrador '{args.login}' criado.")

        existentes = set(db.scalars(select(Feriado.data)))
        novos = [Feriado(data=d, descricao=desc) for ano in anos for d, desc in feriados_nacionais(ano) if d not in existentes]
        db.add_all(novos)
        db.commit()
        print(f"{len(novos)} feriado(s) nacional(is) cadastrado(s) para {', '.join(map(str, anos))}.")


if __name__ == "__main__":
    main()
