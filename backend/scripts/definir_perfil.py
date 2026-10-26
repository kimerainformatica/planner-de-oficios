"""Define o perfil de um usuário direto no banco (ex.: tornar a conta "admin" MASTER).

Uso (dentro de backend/):
    python -m scripts.definir_perfil --login admin --perfil MASTER
Serve também para recuperar o acesso caso nenhum MASTER consiga entrar.
"""

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Auditoria, Perfil, Usuario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--login", required=True)
    parser.add_argument("--perfil", required=True, choices=[p.value for p in Perfil])
    args = parser.parse_args()

    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.login == args.login))
        if usuario is None:
            raise SystemExit(f"Usuário '{args.login}' não encontrado.")
        anterior = usuario.perfil.value
        usuario.perfil = Perfil(args.perfil)
        usuario.ativo = True
        db.add(Auditoria(
            usuario_id=None, referencia=f"Usuário {usuario.login}", acao="USUARIO_ALTERADO",
            descricao=f"Perfil de {usuario.nome} alterado de {anterior} para {args.perfil} pela linha de comando",
            detalhes={"perfil": {"de": anterior, "para": args.perfil}},
        ))
        db.commit()
        print(f"'{usuario.login}' ({usuario.nome}): {anterior} -> {args.perfil}")


if __name__ == "__main__":
    main()
