from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import AdminDep, DbDep, SettingsDep
from app.models import Anexo, AnexoLixeira
from app.schemas import AnexoLixeiraOut, VerificacaoArquivos
from app.services import armazenamento, integridade
from app.services.auditoria import Acao, registrar
from app.services.oficios import buscar_oficio

NOME_TIPO = {"OFICIO": "documento do ofício", "REFERENCIA": "documento de referência",
             "RESPOSTA": "evidência da resposta", "RECEBIMENTO": "evidência da entrega"}

router = APIRouter(tags=["Lixeira e verificação dos arquivos (admin/master)"])


def _montar(item: AnexoLixeira) -> AnexoLixeiraOut:
    return AnexoLixeiraOut.model_validate(item).model_copy(update={
        "oficio_numero": item.oficio.numero,
        "descartado_por_nome": item.descartado_por.nome if item.descartado_por else None,
    })


def _buscar(db, item_id: int) -> AnexoLixeira:
    item = db.get(AnexoLixeira, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item não encontrado na lixeira")
    return item


@router.get("/api/lixeira", response_model=list[AnexoLixeiraOut],
            summary="Versões anteriores de anexos (substituídos ou removidos), mais recentes primeiro")
def listar(db: DbDep, _: AdminDep, oficio_id: Annotated[int | None, Query()] = None):
    consulta = select(AnexoLixeira).options(selectinload(AnexoLixeira.oficio), selectinload(AnexoLixeira.descartado_por))
    if oficio_id is not None:
        consulta = consulta.where(AnexoLixeira.oficio_id == oficio_id)
    return [_montar(i) for i in db.scalars(consulta.order_by(AnexoLixeira.descartado_em.desc(),
                                                             AnexoLixeira.id.desc()).limit(500))]


@router.get("/api/lixeira/{item_id}/download", summary="Baixa a versão guardada (bruto=true: octet-stream)")
def baixar(item_id: int, db: DbDep, settings: SettingsDep, _: AdminDep, bruto: bool = False):
    item = _buscar(db, item_id)
    caminho = armazenamento.caminho_absoluto(item.caminho, settings)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_410_GONE, "O arquivo desta versão não está mais no servidor")
    return FileResponse(caminho, media_type="application/octet-stream" if bruto else item.mime_type,
                        filename=item.nome_original, headers={"X-Content-Type-Options": "nosniff"})


@router.post("/api/lixeira/{item_id}/restaurar", status_code=status.HTTP_204_NO_CONTENT,
             summary="Volta a versão para o ofício; o anexo atual daquele lugar, se houver, vai para a lixeira")
def restaurar(item_id: int, db: DbDep, admin: AdminDep):
    item = _buscar(db, item_id)
    oficio = buscar_oficio(db, item.oficio_id, admin)
    if item.ciclo != 0 and item.historico_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "O registro de resposta/entrega desta evidência não existe mais")
    atual = next((a for a in oficio.anexos if a.tipo == item.tipo and a.ciclo == item.ciclo), None)
    if atual is not None:
        db.add(armazenamento.para_lixeira(atual, "SUBSTITUIDO", admin))
    else:
        atual = Anexo(oficio_id=oficio.id, tipo=item.tipo, ciclo=item.ciclo)
        db.add(atual)
    for campo in ("historico_id", "nome_original", "caminho", "mime_type", "tamanho_bytes", "hash_sha256",
                  "enviado_por_id", "enviado_em"):
        setattr(atual, campo, getattr(item, campo))
    registrar(db, admin, Acao.ANEXO_RESTAURADO,
              f"Restaurou {NOME_TIPO[item.tipo.value]} do ofício nº {oficio.numero}: {item.nome_original}", oficio,
              detalhes={"arquivo": item.nome_original})
    db.delete(item)
    db.commit()


@router.delete("/api/lixeira/{item_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Apaga a versão de vez (banco e disco)")
def apagar(item_id: int, db: DbDep, settings: SettingsDep, admin: AdminDep):
    item = _buscar(db, item_id)
    oficio = buscar_oficio(db, item.oficio_id, admin)
    registrar(db, admin, Acao.ANEXO_APAGADO,
              f"Apagou de vez da lixeira {NOME_TIPO[item.tipo.value]} do ofício nº {oficio.numero}: {item.nome_original}",
              oficio, detalhes={"arquivo": item.nome_original})
    caminho = item.caminho
    db.delete(item)
    db.commit()
    armazenamento.remover_arquivo(caminho, settings)


@router.get("/api/arquivos/verificacao", response_model=VerificacaoArquivos,
            summary="Resultado da última verificação dos arquivos (roda agora se ainda não houver)")
def ultima_verificacao(db: DbDep, settings: SettingsDep, _: AdminDep):
    return integridade.ultima() or integridade.verificar(db, settings)


@router.post("/api/arquivos/verificacao", response_model=VerificacaoArquivos, summary="Verifica os arquivos agora")
def verificar_agora(db: DbDep, settings: SettingsDep, _: AdminDep):
    return integridade.verificar(db, settings)
