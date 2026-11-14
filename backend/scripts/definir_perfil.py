"""Define o perfil de um usuário direto no banco. Serve para recuperar o acesso caso nenhum MASTER consiga entrar.

Uso (dentro de backend/):
    python -m scripts.definir_perfil --login admin --perfil MASTER
    python -m scripts.definir_perfil --login ana --modulo MANUTENCAO --papel ADMIN

- `--perfil MASTER`: acesso total a todos os módulos. `--perfil CLIENTE`: tira o acesso total (o papel em cada
  módulo é definido com `--modulo` e `--papel`).
- `--modulo` com `--papel ADMIN|CLIENTE`: habilita o usuário no módulo com esse papel. `--papel NENHUM` retira.
"""

import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Auditoria, Modulo, Perfil, Usuario, UsuarioModulo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--login", required=True)
    parser.add_argument("--perfil", choices=[Perfil.MASTER.value, Perfil.CLIENTE.value])
    parser.add_argument("--modulo", choices=[m.value for m in Modulo])
    parser.add_argument("--papel", choices=[Perfil.ADMIN.value, Perfil.CLIENTE.value, "NENHUM"])
    args = parser.parse_args()
    if not args.perfil and not (args.modulo and args.papel):
        parser.error("informe --perfil, ou --modulo junto com --papel")

    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.login == args.login))
        if usuario is None:
            raise SystemExit(f"Usuário '{args.login}' não encontrado.")
        usuario.ativo = True
        mensagens = []

        if args.perfil:
            anterior = usuario.perfil.value
            usuario.perfil = Perfil(args.perfil)
            mensagens.append(f"perfil {anterior} -> {args.perfil}")

        if args.modulo and args.papel:
            modulo = Modulo(args.modulo)
            atual = next((a for a in usuario.modulos if a.modulo == modulo), None)
            antes = atual.perfil.value if atual else "NENHUM"
            if args.papel == "NENHUM":
                if atual:
                    usuario.modulos.remove(atual)
            elif atual:
                atual.perfil = Perfil(args.papel)
            else:
                usuario.modulos.append(UsuarioModulo(modulo=modulo, perfil=Perfil(args.papel)))
            mensagens.append(f"{modulo.value}: {antes} -> {args.papel}")

        resumo = "; ".join(mensagens)
        db.add(Auditoria(
            usuario_id=None, referencia=f"Usuário {usuario.login}", acao="USUARIO_ALTERADO",
            descricao=f"Acesso de {usuario.nome} alterado pela linha de comando ({resumo})",
            detalhes={"acesso": resumo},
        ))
        db.commit()
        print(f"'{usuario.login}' ({usuario.nome}): {resumo}")


if __name__ == "__main__":
    main()
