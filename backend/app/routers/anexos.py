from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import DbDep, SettingsDep, UsuarioDep, eh_admin
from app.models import Anexo, HistoricoStatus, Oficio, StatusOficio, TipoAnexo, Usuario
from app.schemas import AnexoOut
from app.services import armazenamento
from app.services.auditoria import Acao, referencia, registrar
from app.services.oficios import buscar_oficio, escopo

NOME_TIPO = {TipoAnexo.OFICIO: "documento do ofício", TipoAnexo.REFERENCIA: "documento de referência",
             TipoAnexo.RESPOSTA: "evidência da resposta", TipoAnexo.RECEBIMENTO: "evidência da entrega"}

router = APIRouter(tags=["Anexos"])


def _buscar_anexo(db: Session, anexo_id: int, usuario: Usuario) -> Anexo:
    anexo = db.scalar(select(Anexo).join(Oficio).where(Anexo.id == anexo_id, escopo(usuario)))
    if anexo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anexo não encontrado")
    return anexo


# Eventos do histórico que aceitam evidência, por tipo de anexo. A resposta confirmada de um ofício com
# entrega vai para PENDENTE_RECEBIMENTO (esse status também nasce de troca de tipo; aí não é resposta).
EVENTOS = {
    TipoAnexo.RESPOSTA: {StatusOficio.CONFIRMADO, StatusOficio.NAO_CONFIRMADO, StatusOficio.PENDENTE_RECEBIMENTO},
    TipoAnexo.RECEBIMENTO: {StatusOficio.RECEBIDO},
}
MENSAGEM_EVENTO = {
    TipoAnexo.RESPOSTA: "Informe a resposta registrada à qual a evidência pertence",
    TipoAnexo.RECEBIMENTO: "Informe o recebimento registrado ao qual a evidência da entrega pertence",
}


def _aceita_evidencia(tipo: TipoAnexo, evento: HistoricoStatus | None) -> bool:
    if evento is None or evento.anulado_em is not None or evento.status_novo not in EVENTOS[tipo]:
        return False
    return tipo != TipoAnexo.RESPOSTA or evento.status_anterior == StatusOficio.PENDENTE_RESPOSTA


@router.post(
    "/api/oficios/{oficio_id}/anexos/{tipo}",
    response_model=AnexoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Envia o documento do ofício, o de referência ou a evidência de uma resposta (substitui se já existir)",
)
def enviar(
    oficio_id: int,
    tipo: TipoAnexo,
    arquivo: UploadFile,
    db: DbDep,
    settings: SettingsDep,
    usuario: UsuarioDep,
    historico_id: Annotated[
        int | None, Query(description="Obrigatório para RESPOSTA e RECEBIMENTO: o evento no histórico")
    ] = None,
):
    oficio = buscar_oficio(db, oficio_id, usuario, detalhe=True)
    evento = None
    if tipo in EVENTOS:
        # Evidência pode ser anexada a qualquer momento pelo dono ou admin, inclusive após confirmar.
        evento = next((h for h in oficio.historico if h.id == historico_id), None)
        if not _aceita_evidencia(tipo, evento):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, MENSAGEM_EVENTO[tipo])
    ciclo = evento.id if evento else 0

    salvo = armazenamento.salvar_upload(arquivo, settings)
    anexo = next((a for a in oficio.anexos if a.tipo == tipo and a.ciclo == ciclo), None)
    caminho_antigo = anexo.caminho if anexo else None
    if anexo is not None:
        db.add(armazenamento.para_lixeira(anexo, "SUBSTITUIDO", usuario))  # a versão anterior pode ser restaurada
    else:
        anexo = Anexo(oficio_id=oficio_id, tipo=tipo, ciclo=ciclo, historico_id=evento.id if evento else None)
        db.add(anexo)

    anexo.caminho = salvo.caminho
    anexo.nome_original = salvo.nome_original
    anexo.mime_type = salvo.mime_type
    anexo.tamanho_bytes = salvo.tamanho_bytes
    anexo.hash_sha256 = salvo.hash_sha256
    anexo.enviado_por_id = usuario.id
    acao = Acao.ANEXO_SUBSTITUIDO if caminho_antigo else Acao.ANEXO_ENVIADO
    verbo = "Substituiu" if caminho_antigo else "Anexou"
    registrar(db, usuario, acao, f"{verbo} {NOME_TIPO[tipo]} do ofício nº {oficio.numero}: {salvo.nome_original}",
              oficio, detalhes={"arquivo": salvo.nome_original, "tamanho_bytes": salvo.tamanho_bytes,
                                "sha256": salvo.hash_sha256})
    try:
        db.commit()
    except Exception:
        db.rollback()
        armazenamento.remover_arquivo(salvo.caminho, settings)
        raise

    db.refresh(anexo)
    return anexo


@router.get("/api/anexos/{anexo_id}/download", summary="Baixa o anexo (inline=true para abrir no navegador)")
def baixar(
    anexo_id: int,
    db: DbDep,
    settings: SettingsDep,
    usuario: UsuarioDep,
    inline: bool = False,
    bruto: Annotated[
        bool, Query(description="Responde como application/octet-stream (usado pelo front-end)")
    ] = False,
):
    anexo = _buscar_anexo(db, anexo_id, usuario)
    caminho = armazenamento.caminho_absoluto(anexo.caminho, settings)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_410_GONE, "O arquivo deste anexo não está mais no servidor")
    return FileResponse(
        caminho,
        # O Edge intercepta respostas que reconhece como PDF (pelo tipo ou pelos bytes "%PDF") mesmo
        # quando pedidas via fetch, e entrega corpo vazio. O front pede "bruto" (octet-stream), o
        # nosniff impede o navegador de adivinhar o tipo, e o tipo real é remontado com anexo.mime_type.
        media_type="application/octet-stream" if bruto else anexo.mime_type,
        filename=anexo.nome_original,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/api/anexos/{anexo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(anexo_id: int, db: DbDep, usuario: UsuarioDep):
    anexo = _buscar_anexo(db, anexo_id, usuario)
    if anexo.tipo in EVENTOS and not eh_admin(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só administradores removem evidências de resposta ou entrega")
    oficio = anexo.oficio
    registrar(db, usuario, Acao.ANEXO_REMOVIDO,
              f"Removeu {NOME_TIPO[anexo.tipo]} do ofício nº {oficio.numero}: {anexo.nome_original}",
              oficio, ref=referencia(oficio), detalhes={"arquivo": anexo.nome_original})
    # Vai para a lixeira: um admin pode restaurar (o arquivo só sai do disco quando apagado de lá)
    db.add(armazenamento.para_lixeira(anexo, "REMOVIDO", usuario))
    db.delete(anexo)
    db.commit()
