from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminDep, DbDep, UsuarioDep
from app.models import Oficio, StatusOficio, TipoOficio
from app.schemas import TipoOficioAtualizar, TipoOficioCriar, TipoOficioOut
from app.services import tipos
from app.services.auditoria import Acao, campos_legiveis, diferencas, registrar
from app.services.oficios import ajustar_etapa_recebimento

router = APIRouter(prefix="/api/tipos", tags=["Tipos de ofício"])


def _montar(db, tipo: TipoOficio) -> TipoOficioOut:
    em_uso = db.scalar(select(func.count()).select_from(Oficio).where(Oficio.tipo == tipo.codigo)) or 0
    return TipoOficioOut.model_validate(tipo).model_copy(update={"em_uso": em_uso})


def _buscar(db, codigo: str) -> TipoOficio:
    tipo = db.get(TipoOficio, codigo)
    if tipo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo de ofício não encontrado")
    return tipo


@router.get("", response_model=list[TipoOficioOut], summary="Todos os tipos, na ordem de exibição (inclui inativos)")
def listar(db: DbDep, _: UsuarioDep):
    usos = dict(db.execute(select(Oficio.tipo, func.count()).where(Oficio.tipo.is_not(None)).group_by(Oficio.tipo)).all())
    return [TipoOficioOut.model_validate(t).model_copy(update={"em_uso": usos.get(t.codigo, 0)})
            for t in tipos.listar(db)]


@router.post("", response_model=TipoOficioOut, status_code=status.HTTP_201_CREATED)
def criar(dados: TipoOficioCriar, db: DbDep, admin: AdminDep):
    if db.scalar(select(TipoOficio.codigo).where(func.lower(TipoOficio.nome) == dados.nome.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe o tipo {dados.nome}")
    ordem = (db.scalar(select(func.max(TipoOficio.ordem))) or 0) + 1
    tipo = TipoOficio(codigo=tipos.gerar_codigo(db, dados.nome), ordem=ordem, ativo=True, **dados.model_dump())
    db.add(tipo)
    registrar(db, admin, Acao.TIPO_CRIADO, f"Criou o tipo de ofício {tipo.nome}", ref=f"Tipo {tipo.nome}",
              detalhes={"codigo": tipo.codigo, "exige_entrega": tipo.exige_entrega})
    db.commit()
    return _montar(db, tipo)


@router.patch("/{codigo}", response_model=TipoOficioOut,
              summary="Altera o tipo. Mudar 'exige entrega' ajusta a etapa dos ofícios já respondidos desse tipo")
def atualizar(codigo: str, dados: TipoOficioAtualizar, db: DbDep, admin: AdminDep):
    tipo = _buscar(db, codigo)
    novos = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None or k == "nome_curto"}
    if "nome" in novos and db.scalar(select(TipoOficio.codigo).where(
            func.lower(TipoOficio.nome) == novos["nome"].lower(), TipoOficio.codigo != codigo)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe o tipo {novos['nome']}")
    mudancas = diferencas({c: getattr(tipo, c) for c in novos}, novos)
    for campo, valor in novos.items():
        setattr(tipo, campo, valor)

    if "exige_entrega" in mudancas:
        # Mesma regra da troca de tipo de um ofício: confirmados entram na etapa de entrega, ou saem dela
        afetados = db.scalars(
            select(Oficio).where(Oficio.tipo == codigo, Oficio.status.in_(
                [StatusOficio.CONFIRMADO, StatusOficio.PENDENTE_RECEBIMENTO, StatusOficio.RECEBIDO]))
            .options(selectinload(Oficio.dono))
        ).all()
        ajustados = 0
        for oficio in afetados:
            if (antes := ajustar_etapa_recebimento(db, oficio, admin)) is not None:
                ajustados += 1
                registrar(db, admin, Acao.OFICIO_EDITADO,
                          f"Etapa de entrega do ofício nº {oficio.numero} ajustada pela regra do tipo {tipo.nome}",
                          oficio, detalhes={"status": {"de": antes.value, "para": oficio.status.value}})
        mudancas["oficios_ajustados"] = {"de": None, "para": ajustados}

    if mudancas:
        registrar(db, admin, Acao.TIPO_ALTERADO, f"Alterou o tipo de ofício {tipo.nome} ({campos_legiveis(mudancas)})",
                  ref=f"Tipo {tipo.nome}", detalhes=mudancas)
    db.commit()
    return _montar(db, tipo)


@router.delete("/{codigo}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Apaga um tipo que nenhum ofício usa (em uso: desative)")
def excluir(codigo: str, db: DbDep, admin: AdminDep):
    tipo = _buscar(db, codigo)
    if db.scalar(select(func.count()).select_from(Oficio).where(Oficio.tipo == codigo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Há ofícios deste tipo: desative-o em vez de apagar")
    registrar(db, admin, Acao.TIPO_EXCLUIDO, f"Apagou o tipo de ofício {tipo.nome}", ref=f"Tipo {tipo.nome}")
    db.delete(tipo)
    db.commit()
