"""Registro de atividades: toda alteração na plataforma fica gravada na conta de quem a fez.

As entradas são adicionadas à mesma sessão da alteração, então só existem se ela for confirmada.
"""

from datetime import date, datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.models import Auditoria, ChamadoInteracao, Oficio, TipoInteracao, Usuario


class Acao(str, Enum):
    OFICIO_CRIADO = "OFICIO_CRIADO"
    OFICIO_EDITADO = "OFICIO_EDITADO"
    STATUS_ALTERADO = "STATUS_ALTERADO"
    RESPOSTA_CORRIGIDA = "RESPOSTA_CORRIGIDA"
    RECEBIMENTO_CORRIGIDO = "RECEBIMENTO_CORRIGIDO"
    ETAPA_DESFEITA = "ETAPA_DESFEITA"
    ANEXO_ENVIADO = "ANEXO_ENVIADO"
    ANEXO_SUBSTITUIDO = "ANEXO_SUBSTITUIDO"
    ANEXO_REMOVIDO = "ANEXO_REMOVIDO"
    EXCLUSAO_SOLICITADA = "EXCLUSAO_SOLICITADA"
    EXCLUSAO_CANCELADA = "EXCLUSAO_CANCELADA"
    EXCLUSAO_APROVADA = "EXCLUSAO_APROVADA"
    EXCLUSAO_RECUSADA = "EXCLUSAO_RECUSADA"
    OFICIO_EXCLUIDO = "OFICIO_EXCLUIDO"
    USUARIO_CRIADO = "USUARIO_CRIADO"
    USUARIO_ALTERADO = "USUARIO_ALTERADO"
    FERIADO_CRIADO = "FERIADO_CRIADO"
    FERIADO_EXCLUIDO = "FERIADO_EXCLUIDO"
    TIPO_CRIADO = "TIPO_CRIADO"
    TIPO_ALTERADO = "TIPO_ALTERADO"
    TIPO_EXCLUIDO = "TIPO_EXCLUIDO"
    ANEXO_RESTAURADO = "ANEXO_RESTAURADO"
    ANEXO_APAGADO = "ANEXO_APAGADO"  # apagado de vez da lixeira
    DOCUMENTO_EMITIDO = "DOCUMENTO_EMITIDO"
    DOCUMENTO_ASSINADO = "DOCUMENTO_ASSINADO"
    DOCUMENTO_CANCELADO = "DOCUMENTO_CANCELADO"
    TIMBRADO_ALTERADO = "TIMBRADO_ALTERADO"


NOME_CAMPO = {
    "numero": "número",
    "data_oficio": "data do ofício",
    "tipo": "tipo",
    "protocolo": "protocolo",
    "destinatario_tipo": "destinatário",
    "destinatario_setor": "setor/destino",
    "observacao": "observação",
    "status": "status",
    "data_resposta": "data da resposta",
    "data_recebimento": "data do recebimento",
    "nome": "nome",
    "login": "login",
    "perfil": "perfil",
    "master": "acesso total (master)",
    "modulos": "acesso aos módulos",
    "ativo": "situação",
    "senha": "senha",
    "cpf": "CPF",
    "nome_curto": "nome curto",
    "exige_entrega": "exige entrega",
    "ordem": "ordem",
    "oficios_ajustados": "ofícios ajustados",
}


def campos_legiveis(mudancas: dict) -> str:
    return ", ".join(NOME_CAMPO.get(c, c) for c in mudancas)


def referencia(oficio: Oficio) -> str:
    dono = oficio.dono.nome if oficio.dono else ""
    return f"Ofício nº {oficio.numero}" + (f" · {dono}" if dono else "")


def _texto(v) -> str | int | float | bool | None:
    """Valor serializável e legível para o JSON de detalhes."""
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, date):
        return v.isoformat()
    return v


def diferencas(antes: dict, depois: dict) -> dict:
    """{"campo": {"de": x, "para": y}} só para o que mudou."""
    return {
        campo: {"de": _texto(antes.get(campo)), "para": _texto(valor)}
        for campo, valor in depois.items()
        if _texto(antes.get(campo)) != _texto(valor)
    }


def registrar(
    db: Session,
    usuario: Usuario,
    acao: Acao,
    descricao: str,
    oficio: Oficio | None = None,
    ref: str | None = None,
    detalhes: dict | None = None,
) -> None:
    """Para ofícios recém-criados, chame db.flush() antes, para o ofício já ter id."""
    db.add(
        Auditoria(
            usuario_id=usuario.id,
            oficio_id=oficio.id if oficio is not None else None,
            referencia=ref or (referencia(oficio) if oficio is not None else None),
            acao=acao.value,
            descricao=descricao[:500],
            detalhes=detalhes or None,
        )
    )
    if oficio is not None and acao != Acao.OFICIO_CRIADO:
        espelhar_no_chamado(db, oficio, usuario, descricao)


def espelhar_no_chamado(db: Session, oficio: Oficio, usuario: Usuario, descricao: str) -> None:
    """Ofício de solicitação de peças/equipamentos: o que acontece com ele no Planner (documentos, resposta,
    entrega, correções, exclusão) aparece também na linha do tempo do chamado das Manutenções Integradas."""
    chamado = oficio.chamado if oficio.chamado_id else None
    if chamado is None:
        return
    agora = datetime.now().replace(microsecond=0)
    db.add(ChamadoInteracao(chamado=chamado, autor=usuario, tipo=TipoInteracao.OFICIO, criado_em=agora,
                            texto=f"Planner de Ofícios · {descricao}"))
    chamado.atualizado_em = agora