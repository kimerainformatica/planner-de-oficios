"""Módulos da plataforma: lista o que o usuário pode abrir (a tela inicial depois do login)."""

from fastapi import APIRouter

from app.deps import UsuarioDep
from app.schemas import ModuloDisponivel
from app.services.modulos import CATALOGO

router = APIRouter(prefix="/api/modulos", tags=["Módulos"])


@router.get("", response_model=list[ModuloDisponivel])
def meus_modulos(usuario: UsuarioDep):
    """Módulos habilitados para o usuário (o MASTER vê todos), com o papel dele em cada um."""
    return [
        ModuloDisponivel(
            modulo=a.modulo, nome=CATALOGO[a.modulo].nome, descricao=CATALOGO[a.modulo].descricao,
            rota=CATALOGO[a.modulo].rota, perfil=a.perfil,
        )
        for a in usuario.modulos_efetivos
    ]
