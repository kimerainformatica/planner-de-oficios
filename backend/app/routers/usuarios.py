"""Gestão de usuários e do acesso deles aos módulos.

Quem pode o quê:
- MASTER: tudo, em todos os módulos (cria e altera masters e administradores).
- ADMIN de um módulo: gerencia o acesso a **esse** módulo (e só a ele). Cria usuários e os habilita como
  CLIENTE nos módulos que administra. Não cria nem altera administradores nem masters.
- Só edita nome, login, senha e situação de um usuário quem administra todos os módulos dele: assim o admin de
  um módulo não consegue assumir a conta de quem também usa outro módulo.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import DbDep, GestorDep
from app.models import EmpresaManutencao, Modulo, Perfil, Usuario, UsuarioModulo
from app.schemas import UsuarioAtualizar, UsuarioCriar, UsuarioOut
from app.seguranca import gerar_hash_senha
from app.services.auditoria import Acao, campos_legiveis, diferencas, registrar
from app.services.modulos import eh_admin_em_algum, modulos_que_administra, nome_modulo

router = APIRouter(prefix="/api/usuarios", tags=["Usuários e acesso aos módulos"])

ROTULO = {Perfil.MASTER: "master", Perfil.ADMIN: "administrador", Perfil.CLIENTE: "cliente",
          Perfil.TECNICO: "técnico"}


def _rotulo_acesso(a: UsuarioModulo) -> str:
    if a.perfil == Perfil.TECNICO:
        return f"técnico · {a.empresa.nome}" if a.empresa else "técnico"
    if a.modulo == Modulo.MANUTENCAO and a.perfil == Perfil.CLIENTE:
        return "operacional"  # na Manutenção Clínica o cliente é quem abre os chamados
    if a.modulo == Modulo.DOCUMENTOS and a.perfil == Perfil.CLIENTE:
        return "redator"  # em Documentos o cliente redige e assina
    return ROTULO[a.perfil]


def _texto_acessos(usuario: Usuario) -> str:
    if usuario.eh_master:
        return "todos os módulos (master)"
    if not usuario.modulos:
        return "nenhum módulo"
    return ", ".join(f"{nome_modulo(a.modulo)} ({_rotulo_acesso(a)})" for a in usuario.modulos)


def _pode_gerir_conta(quem: Usuario, alvo: Usuario) -> bool:
    """Nome, login, senha e situação: o próprio usuário, o MASTER, ou o admin que administra TODOS os módulos
    do alvo (e o alvo não é master nem administrador)."""
    if quem.id == alvo.id or quem.eh_master:
        return True
    if alvo.eh_master or eh_admin_em_algum(alvo):
        return False
    meus = modulos_que_administra(quem)
    # O acesso de cliente ao Planner que vem junto com o operacional da Manutenção não tira a conta do admin da
    # Manutenção (é parte do mesmo papel)
    implicito = eh_operacional_manutencao(alvo)
    return all(
        a.modulo in meus or (implicito and a.modulo == Modulo.OFICIOS and a.perfil == Perfil.CLIENTE)
        for a in alvo.modulos
    )


def _aplicar_modulos(db, editor: Usuario, alvo: Usuario, pedidos: list) -> None:
    """Troca o acesso do alvo nos módulos que o editor administra. O resto não é tocado."""
    escopo = modulos_que_administra(editor)
    desejado = {a.modulo: a.perfil for a in pedidos}
    empresas: dict[Modulo, EmpresaManutencao | None] = {}
    for a in pedidos:
        empresa = None
        if a.empresa_id is not None:
            empresa = db.get(EmpresaManutencao, a.empresa_id)
            atual = alvo.acesso_no(a.modulo)
            mesma = atual is not None and atual.empresa_id == a.empresa_id
            if empresa is None or (not empresa.ativo and not mesma):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empresa do técnico não encontrada ou inativa")
        empresas[a.modulo] = empresa

    fora = [m for m in desejado if m not in escopo]
    if fora:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"Você não administra o módulo {nome_modulo(fora[0])}"
        )
    if not editor.eh_master:
        if any(p == Perfil.ADMIN for p in desejado.values()):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o MASTER cria ou promove administradores")
        if any(a.modulo in escopo and a.perfil == Perfil.ADMIN for a in alvo.modulos):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o MASTER altera o acesso de administradores")

    tinha_planner = alvo.acesso_no(Modulo.OFICIOS) is not None
    atuais = {a.modulo: a for a in alvo.modulos}
    for modulo in escopo:
        if modulo in desejado:
            if modulo in atuais:
                atuais[modulo].perfil = desejado[modulo]
                atuais[modulo].empresa = empresas[modulo]
            else:
                alvo.modulos.append(UsuarioModulo(modulo=modulo, perfil=desejado[modulo], empresa=empresas[modulo]))
        elif modulo in atuais:
            alvo.modulos.remove(atuais[modulo])  # delete-orphan apaga a linha
    _garantir_planner_do_operacional(alvo, tinha_planner)


def eh_operacional_manutencao(usuario: Usuario) -> bool:
    """Cliente ou administrador da Manutenção Clínica (o técnico das empresas não conta)."""
    acesso = usuario.acesso_no(Modulo.MANUTENCAO)
    return not usuario.eh_master and acesso is not None and acesso.perfil in (Perfil.CLIENTE, Perfil.ADMIN)


def _garantir_planner_do_operacional(alvo: Usuario, tinha_planner: bool) -> None:
    """Regra: todo operacional da Manutenção Clínica também usa o Planner de Ofícios (as solicitações de peças e
    equipamentos viram ofícios lá). Quem ainda não tem o Planner ganha acesso de cliente; o papel em cada
    módulo (admin ou cliente) continua independente."""
    if not eh_operacional_manutencao(alvo) or alvo.acesso_no(Modulo.OFICIOS) is not None:
        return
    if tinha_planner:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "O operacional da Manutenção Clínica precisa ter acesso ao Planner de Ofícios (como cliente ou administrador)",
        )
    alvo.modulos.append(UsuarioModulo(modulo=Modulo.OFICIOS, perfil=Perfil.CLIENTE))


@router.get("", response_model=list[UsuarioOut])
def listar(db: DbDep, quem: GestorDep, modulo: Modulo | None = None):
    """MASTER vê todos; admin vê quem tem acesso a algum módulo que ele administra (e ele mesmo).
    `modulo` filtra por quem tem acesso a ele (o MASTER sempre tem)."""
    usuarios = db.scalars(select(Usuario).order_by(Usuario.nome)).all()
    if not quem.eh_master:
        meus = modulos_que_administra(quem)
        usuarios = [
            u for u in usuarios if u.id == quem.id or (not u.eh_master and any(a.modulo in meus for a in u.modulos))
        ]
    if modulo is not None:
        usuarios = [u for u in usuarios if u.tem_acesso(modulo)]
    return usuarios


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioCriar, db: DbDep, quem: GestorDep):
    if dados.master and not quem.eh_master:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o MASTER pode criar masters")
    if not quem.eh_master and not dados.modulos:
        raise HTTPException(422, "Habilite o usuário em pelo menos um módulo")
    if db.scalar(select(Usuario.id).where(func.lower(Usuario.login) == dados.login.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, f"O login {dados.login} já está em uso")

    usuario = Usuario(
        nome=dados.nome, login=dados.login, senha_hash=gerar_hash_senha(dados.senha),
        perfil=Perfil.MASTER if dados.master else Perfil.CLIENTE,
        cargo=dados.cargo or None, matricula=dados.matricula or None,
    )
    if not dados.master:
        _aplicar_modulos(db, quem, usuario, dados.modulos)
    db.add(usuario)
    registrar(
        db, quem, Acao.USUARIO_CRIADO,
        f"Criou o usuário {dados.nome} ({dados.login}) com acesso a: {_texto_acessos(usuario)}",
        ref=f"Usuário {dados.login}", detalhes={"acessos": _texto_acessos(usuario)},
    )
    db.commit()
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def atualizar(usuario_id: int, dados: UsuarioAtualizar, db: DbDep, quem: GestorDep):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    proprio = usuario.id == quem.id
    mexe_na_conta = any(v is not None for v in (dados.nome, dados.login, dados.senha, dados.ativo, dados.cargo,
                                                 dados.matricula)) or (
        dados.modulos is not None and usuario.eh_master  # o acesso de um master só o MASTER muda
    )
    if mexe_na_conta and not _pode_gerir_conta(quem, usuario):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não pode alterar esta conta: ela é de um administrador ou usa módulos que você não administra",
        )
    if dados.master is not None and not quem.eh_master:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o MASTER concede ou retira o acesso total")
    if proprio and (
        dados.ativo is False
        or (dados.master is not None and dados.master != usuario.eh_master)
        or dados.modulos is not None
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Você não pode se desativar nem mudar o próprio acesso"
        )

    vai_deixar_de_ser_master = usuario.eh_master and (dados.ativo is False or dados.master is False)
    if vai_deixar_de_ser_master:
        outros = db.scalar(
            select(func.count()).select_from(Usuario).where(
                Usuario.perfil == Perfil.MASTER, Usuario.ativo.is_(True), Usuario.id != usuario.id
            )
        )
        if not outros:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "A plataforma precisa de pelo menos um MASTER ativo")

    if dados.login is not None and dados.login.lower() != usuario.login.lower():
        if db.scalar(
            select(Usuario.id).where(func.lower(Usuario.login) == dados.login.lower(), Usuario.id != usuario.id)
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, f"O login {dados.login} já está em uso")

    acessos_antes = _texto_acessos(usuario)
    novos = dados.model_dump(exclude_unset=True, exclude_none=True, exclude={"senha", "master", "modulos"})
    for campo in ("cargo", "matricula"):  # texto vazio apaga
        if campo in novos and not novos[campo]:
            novos[campo] = None
    mudancas = diferencas({c: getattr(usuario, c) for c in novos}, novos)
    for campo, valor in novos.items():
        setattr(usuario, campo, valor)

    if dados.master is not None and dados.master != usuario.eh_master:
        usuario.perfil = Perfil.MASTER if dados.master else Perfil.CLIENTE
    if dados.modulos is not None and not usuario.eh_master:
        _aplicar_modulos(db, quem, usuario, dados.modulos)
    if _texto_acessos(usuario) != acessos_antes:
        mudancas["modulos"] = {"de": acessos_antes, "para": _texto_acessos(usuario)}

    if dados.senha is not None:
        usuario.senha_hash = gerar_hash_senha(dados.senha)
        usuario.sessao_versao += 1  # encerra as sessões abertas com a senha antiga (em todos os computadores)
        mudancas["senha"] = {"de": None, "para": "redefinida"}
    if mudancas:
        registrar(db, quem, Acao.USUARIO_ALTERADO, f"Alterou o usuário {usuario.nome} ({campos_legiveis(mudancas)})",
                  ref=f"Usuário {usuario.login}", detalhes=mudancas)
    db.commit()
    return usuario
