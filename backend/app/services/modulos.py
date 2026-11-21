"""Catálogo dos módulos da plataforma e regras de quem pode gerenciar o acesso a eles."""

from dataclasses import dataclass

from app.models import Modulo, Perfil, Usuario


@dataclass(frozen=True)
class InfoModulo:
    modulo: Modulo
    nome: str
    descricao: str
    rota: str  # onde o módulo abre no front-end


CATALOGO: dict[Modulo, InfoModulo] = {
    Modulo.OFICIOS: InfoModulo(
        Modulo.OFICIOS, "Planner de Ofícios", "Cadastro, prazos e entregas dos ofícios.", "/"
    ),
    Modulo.MANUTENCAO: InfoModulo(
        Modulo.MANUTENCAO, "Manutenção Clínica", "Gestão da manutenção de equipamentos clínicos.", "/manutencao"
    ),
    Modulo.TETOS: InfoModulo(
        Modulo.TETOS, "Controle de Tetos", "Tetos de gastos por setor, com indicadores diários, mensais e anuais.",
        "/tetos"
    ),
    Modulo.DOCUMENTOS: InfoModulo(
        Modulo.DOCUMENTOS, "Documentos",
        "Ofícios e memorandos no modelo da unidade, com assinatura e verificação; integrado ao Planner.", "/documentos"
    ),
}


def nome_modulo(modulo: Modulo) -> str:
    return CATALOGO[modulo].nome


def modulos_que_administra(usuario: Usuario) -> set[Modulo]:
    """Módulos em que o usuário é ADMIN (o MASTER, em todos)."""
    return {m for m in Modulo if usuario.eh_admin_no(m)}


def eh_gestor(usuario: Usuario) -> bool:
    """MASTER ou admin de pelo menos um módulo: pode abrir a gestão de usuários."""
    return bool(modulos_que_administra(usuario))


def eh_admin_em_algum(usuario: Usuario) -> bool:
    """Tem papel ADMIN em algum módulo (o MASTER não entra: ele é tratado à parte)."""
    return any(a.perfil == Perfil.ADMIN for a in usuario.modulos)
