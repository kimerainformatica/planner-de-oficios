from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy import extract, select

from app.deps import AdminDep, DbDep, UsuarioDep
from app.models import Feriado
from app.schemas import FeriadoCriar, FeriadoOut
from app.services.auditoria import Acao, registrar
from app.services.prazos import feriados_nacionais

router = APIRouter(prefix="/api/feriados", tags=["Feriados (dias não úteis)"])


@router.get("", response_model=list[FeriadoOut])
def listar(db: DbDep, _: UsuarioDep, ano: int | None = None):
    consulta = select(Feriado).order_by(Feriado.data)
    if ano is not None:
        consulta = consulta.where(extract("year", Feriado.data) == ano)
    return db.scalars(consulta).all()


@router.post("", response_model=FeriadoOut, status_code=status.HTTP_201_CREATED)
def criar(dados: FeriadoCriar, db: DbDep, admin: AdminDep):
    if db.scalar(select(Feriado.id).where(Feriado.data == dados.data)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um feriado cadastrado nesta data")
    feriado = Feriado(**dados.model_dump())
    db.add(feriado)
    registrar(db, admin, Acao.FERIADO_CRIADO, f"Cadastrou o feriado {dados.data:%d/%m/%Y} ({dados.descricao})",
              ref="Feriados")
    db.commit()
    return feriado


@router.post(
    "/nacionais/{ano}",
    response_model=list[FeriadoOut],
    summary="Cadastra os feriados nacionais do ano (ignora datas já cadastradas)",
)
def gerar_nacionais(ano: Annotated[int, Path(ge=2000, le=2100)], db: DbDep, admin: AdminDep):
    existentes = set(db.scalars(select(Feriado.data).where(extract("year", Feriado.data) == ano)))
    novos = [Feriado(data=d, descricao=desc) for d, desc in feriados_nacionais(ano) if d not in existentes]
    db.add_all(novos)
    if novos:
        registrar(db, admin, Acao.FERIADO_CRIADO, f"Cadastrou {len(novos)} feriado(s) nacional(is) de {ano}",
                  ref="Feriados", detalhes={"datas": [f.data.isoformat() for f in novos]})
    db.commit()
    return novos


@router.delete("/{feriado_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir(feriado_id: int, db: DbDep, admin: AdminDep):
    feriado = db.get(Feriado, feriado_id)
    if feriado is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feriado não encontrado")
    registrar(db, admin, Acao.FERIADO_EXCLUIDO, f"Removeu o feriado {feriado.data:%d/%m/%Y} ({feriado.descricao})",
              ref="Feriados")
    db.delete(feriado)
    db.commit()
