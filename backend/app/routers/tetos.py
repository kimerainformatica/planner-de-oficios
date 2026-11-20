"""Controle de Tetos: setores, tipos de teto (com os valores por vigência), lançamentos dos gastos e indicadores.

Quem pode o quê (regras em services/tetos.py):
- Administrador do módulo (ou MASTER): cria setores, tipos e define os valores de teto; vê e lança em todos os setores.
- Usuário do setor (CLIENTE, ligado a um setor no cadastro de usuários): lança, corrige e exclui os gastos do
  próprio setor e acompanha os indicadores dele. Não vê os outros setores.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.deps import AgoraDep, DbDep, HojeDep, SettingsDep, UsuarioDep, exige_acesso_ao
from app.models import GastoTeto, Modulo, PeriodoTeto, Setor, TetoVigencia, TipoTeto, Usuario, UsuarioModulo
from app.schemas_manutencao import PessoaOut
from app.schemas_tetos import (
    ConsumoMes,
    ConsumoOut,
    Equivalentes,
    GastoAtualizar,
    GastoOut,
    IndicadoresTipo,
    IndicadorTipo,
    PaginaGastos,
    PainelSetor,
    PainelTetos,
    PontoAnual,
    PontoDiario,
    PontoMensal,
    ResumoTetos,
    SetorAtualizar,
    SetorCriar,
    SetorOut,
    SetorRef,
    TipoAtualizar,
    TipoCriar,
    TipoOut,
    TipoRef,
    TotalTipo,
    TotalUnidade,
    VigenciaCriar,
    VigenciaOut,
)
from app.services import armazenamento
from app.services import tetos as regras
from app.services.auditoria import Acao, registrar
from app.services.tetos import SituacaoTeto, dec

router = APIRouter(prefix="/api/tetos", tags=["Controle de Tetos"],
                   dependencies=[Depends(exige_acesso_ao(Modulo.TETOS))])

VALOR_MAXIMO = Decimal("999999999999.99")


# ---------- montagem das respostas ----------


def _pessoa(u: Usuario | None) -> PessoaOut | None:
    return PessoaOut.model_validate(u) if u else None


def _equivalentes(periodo: PeriodoTeto, valor, referencia: date) -> Equivalentes:
    return Equivalentes(**{k: float(v) for k, v in regras.tetos_equivalentes(periodo, valor, referencia).items()})


def _vigencia_out(v: TetoVigencia, hoje: date) -> VigenciaOut:
    return VigenciaOut(id=v.id, inicio=v.inicio, periodo=v.periodo, valor=float(v.valor), motivo=v.motivo,
                       criado_por=_pessoa(v.criado_por), criado_em=v.criado_em,
                       equivalentes=_equivalentes(v.periodo, v.valor, max(hoje, v.inicio)))


def _tipo_out(tipo: TipoTeto, hoje: date, lancamentos: int = 0, detalhe: bool = False) -> TipoOut:
    atual = regras.vigencia_em(tipo.vigencias, hoje)
    return TipoOut(
        id=tipo.id, setor=SetorRef.model_validate(tipo.setor), nome=tipo.nome, descricao=tipo.descricao,
        unidade=tipo.unidade, alerta_pct=tipo.alerta_pct, ativo=tipo.ativo,
        periodo=atual.periodo if atual else None, valor=float(atual.valor) if atual else None,
        vigente_desde=atual.inicio if atual else None,
        equivalentes=_equivalentes(atual.periodo, atual.valor, hoje) if atual else None,
        lancamentos=lancamentos,
        vigencias=[_vigencia_out(v, hoje) for v in reversed(tipo.vigencias)] if detalhe else [],
    )


def _pode_editar(gasto: GastoTeto, usuario: Usuario) -> bool:
    return regras.setor_visivel(usuario, gasto.setor_id)


def _gasto_out(g: GastoTeto, usuario: Usuario) -> GastoOut:
    return GastoOut(
        id=g.id, tipo=TipoRef.model_validate(g.tipo), setor=SetorRef.model_validate(g.tipo.setor), data=g.data,
        valor=float(g.valor), descricao=g.descricao, documento=g.documento, arquivo_nome=g.arquivo_nome,
        arquivo_tamanho=g.arquivo_tamanho, registrado_por=_pessoa(g.registrado_por), registrado_em=g.registrado_em,
        atualizado_por=_pessoa(g.atualizado_por), atualizado_em=g.atualizado_em, pode_editar=_pode_editar(g, usuario),
    )


def _consumo(c: regras.Consumo) -> ConsumoOut:
    return ConsumoOut(gasto=float(c.gasto), teto=float(c.teto), percentual=c.percentual, restante=float(c.restante),
                      situacao=c.situacao)


def _ref(tipo: TipoTeto) -> str:
    return f"Teto {tipo.nome} · {tipo.setor.nome}"


def _contagem_lancamentos(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    return dict(db.execute(select(GastoTeto.tipo_id, func.count()).where(GastoTeto.tipo_id.in_(ids))
                           .group_by(GastoTeto.tipo_id)).all())


def _gastos_por_dia(db: Session, tipo_ids: list[int], de: date | None, ate: date) -> dict[int, dict[date, Decimal]]:
    """{tipo_id: {data: soma}} dos lançamentos no período."""
    if not tipo_ids:
        return {}
    consulta = (select(GastoTeto.tipo_id, GastoTeto.data, func.sum(GastoTeto.valor))
                .where(GastoTeto.tipo_id.in_(tipo_ids), GastoTeto.data <= ate)
                .group_by(GastoTeto.tipo_id, GastoTeto.data))
    if de is not None:
        consulta = consulta.where(GastoTeto.data >= de)
    resultado: dict[int, dict[date, Decimal]] = {i: {} for i in tipo_ids}
    for tipo_id, dia, soma in db.execute(consulta):
        resultado[tipo_id][dia] = dec(soma)
    return resultado


def _indicador(tipo: TipoTeto, gastos: dict[date, Decimal], ref: date, hoje: date, lancamentos: int) -> IndicadorTipo:
    vig = tipo.vigencias
    inicio_mes, inicio_ano = ref.replace(day=1), date(ref.year, 1, 1)
    gasto_mes = regras.somar(gastos, inicio_mes, ref)
    c_mes = regras.consumo(gasto_mes, regras.teto_entre(vig, inicio_mes, regras.fim_do_mes(ref)), tipo.alerta_pct)
    projecao = regras.projecao_do_mes(gasto_mes, ref, hoje)
    return IndicadorTipo(
        tipo=_tipo_out(tipo, ref, lancamentos),
        dia=_consumo(regras.consumo(gastos.get(ref, Decimal(0)), regras.teto_entre(vig, ref, ref), tipo.alerta_pct)),
        mes=ConsumoMes(**_consumo(c_mes).model_dump(), teto_ate_hoje=float(regras.teto_entre(vig, inicio_mes, ref)),
                       projecao=float(projecao), projecao_estoura=c_mes.teto > 0 and projecao > c_mes.teto),
        ano=_consumo(regras.consumo(regras.somar(gastos, inicio_ano, ref),
                                    regras.teto_entre(vig, inicio_ano, date(ref.year, 12, 31)), tipo.alerta_pct)),
    )


def _totais(indicadores: list[IndicadorTipo]) -> list[TotalUnidade]:
    por_unidade: dict[str, list[IndicadorTipo]] = {}
    for i in indicadores:
        por_unidade.setdefault(i.tipo.unidade, []).append(i)
    totais = []
    for unidade, itens in por_unidade.items():
        def soma(periodo: str, campo: str) -> Decimal:
            return sum((Decimal(str(getattr(getattr(i, periodo), campo))) for i in itens), Decimal(0))

        # O % de alerta do total é o menor entre os tipos (o mais cauteloso)
        alerta = min(i.tipo.alerta_pct for i in itens)
        totais.append(TotalUnidade(
            unidade=unidade,
            mes=_consumo(regras.consumo(soma("mes", "gasto"), soma("mes", "teto"), alerta)),
            ano=_consumo(regras.consumo(soma("ano", "gasto"), soma("ano", "teto"), alerta)),
        ))
    return totais


def _ler_valor(texto: str) -> Decimal:
    """Aceita "1234.56" ou "1.234,56"."""
    t = texto.strip().replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(t)
    except InvalidOperation:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Valor inválido") from None
    if valor <= 0 or valor > VALOR_MAXIMO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O valor precisa ser maior que zero")
    if valor != valor.quantize(Decimal("0.01")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use no máximo duas casas decimais")
    return valor


def _validar_data_gasto(dia: date, hoje: date) -> None:
    if dia > hoje:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A data do gasto não pode estar no futuro")
    if dia < date(2000, 1, 1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Data do gasto inválida")


def _tipo_para_lancar(db: Session, tipo_id: int, usuario: Usuario) -> TipoTeto:
    tipo = regras.buscar_tipo(db, tipo_id, usuario)
    if not tipo.ativo or not tipo.setor.ativo:
        raise HTTPException(status.HTTP_409_CONFLICT, f"O tipo {tipo.nome} está desativado: não recebe lançamentos")
    return tipo


def _setores_do_filtro(usuario: Usuario, setor_id: int | None) -> list[int] | None:
    """None = todos (administrador sem filtro)."""
    if regras.eh_gestor(usuario):
        return [setor_id] if setor_id else None
    meu = regras.setor_do(usuario)
    if meu is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Seu usuário ainda não está ligado a um setor. Peça ao administrador do módulo.")
    if setor_id and setor_id != meu.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Setor não encontrado")
    return [meu.id]


# ---------- resumo ----------


@router.get("/resumo", response_model=ResumoTetos, summary="Papel de quem consulta no módulo e o setor dele")
def resumo(usuario: UsuarioDep):
    setor = regras.setor_do(usuario)
    return ResumoTetos(eh_gestor=regras.eh_gestor(usuario), setor=SetorRef.model_validate(setor) if setor else None)


# ---------- setores ----------


def _setor_out(db: Session, s: Setor) -> SetorOut:
    pessoas = db.scalars(select(Usuario).join(UsuarioModulo).where(
        UsuarioModulo.modulo == Modulo.TETOS, UsuarioModulo.setor_id == s.id).order_by(Usuario.nome)).all()
    tipos = db.scalar(select(func.count()).select_from(TipoTeto).where(TipoTeto.setor_id == s.id)) or 0
    return SetorOut(id=s.id, nome=s.nome, descricao=s.descricao, ativo=s.ativo,
                    usuarios=[PessoaOut.model_validate(p) for p in pessoas], tipos=tipos)


@router.get("/setores", response_model=list[SetorOut],
            summary="Setores (o administrador vê todos; o usuário do setor, só o dele)")
def listar_setores(db: DbDep, usuario: UsuarioDep):
    if regras.eh_gestor(usuario):
        setores = db.scalars(select(Setor).order_by(Setor.nome)).all()
    else:
        meu = regras.setor_do(usuario)
        setores = [meu] if meu else []
    return [_setor_out(db, s) for s in setores]


def _nome_livre(db: Session, nome: str, exceto: int | None = None) -> None:
    consulta = select(Setor.id).where(func.lower(Setor.nome) == nome.lower())
    if exceto:
        consulta = consulta.where(Setor.id != exceto)
    if db.scalar(consulta):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Já existe o setor {nome}")


@router.post("/setores", response_model=SetorOut, status_code=status.HTTP_201_CREATED)
def criar_setor(dados: SetorCriar, db: DbDep, usuario: UsuarioDep):
    regras.exigir_gestor(usuario)
    _nome_livre(db, dados.nome)
    setor = Setor(nome=dados.nome, descricao=dados.descricao, ativo=True)
    db.add(setor)
    registrar(db, usuario, Acao.SETOR_CRIADO, f"Criou o setor {dados.nome}", ref=f"Setor {dados.nome}")
    db.commit()
    return _setor_out(db, setor)


@router.patch("/setores/{setor_id}", response_model=SetorOut)
def atualizar_setor(setor_id: int, dados: SetorAtualizar, db: DbDep, usuario: UsuarioDep):
    regras.exigir_gestor(usuario)
    setor = db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Setor não encontrado")
    novos = dados.model_dump(exclude_unset=True)
    if novos.get("nome"):
        _nome_livre(db, novos["nome"], setor.id)
    for campo, valor in novos.items():
        if campo != "nome" or valor:
            setattr(setor, campo, valor)
    registrar(db, usuario, Acao.SETOR_ALTERADO, f"Alterou o setor {setor.nome}", ref=f"Setor {setor.nome}",
              detalhes={k: v for k, v in novos.items()})
    db.commit()
    return _setor_out(db, setor)


@router.delete("/setores/{setor_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Exclui um setor sem tipos de teto e sem usuários (senão, desative)")
def excluir_setor(setor_id: int, db: DbDep, usuario: UsuarioDep):
    regras.exigir_gestor(usuario)
    setor = db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Setor não encontrado")
    em_uso = db.scalar(select(func.count()).select_from(TipoTeto).where(TipoTeto.setor_id == setor_id)) or db.scalar(
        select(func.count()).select_from(UsuarioModulo).where(UsuarioModulo.setor_id == setor_id))
    if em_uso:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "O setor tem tipos de teto ou usuários: desative-o em vez de excluir")
    registrar(db, usuario, Acao.SETOR_EXCLUIDO, f"Excluiu o setor {setor.nome}", ref=f"Setor {setor.nome}")
    db.delete(setor)
    db.commit()


# ---------- tipos de teto ----------


@router.get("/tipos", response_model=list[TipoOut], summary="Tipos de teto visíveis (filtro por setor)")
def listar_tipos(db: DbDep, usuario: UsuarioDep, hoje: HojeDep, setor_id: int | None = None,
                 incluir_inativos: bool = False):
    setores = _setores_do_filtro(usuario, setor_id)
    consulta = select(TipoTeto).join(Setor).order_by(Setor.nome, TipoTeto.nome)
    if setores is not None:
        consulta = consulta.where(TipoTeto.setor_id.in_(setores))
    if not incluir_inativos:
        consulta = consulta.where(TipoTeto.ativo.is_(True))
    tipos = db.scalars(consulta).unique().all()
    contagem = _contagem_lancamentos(db, [t.id for t in tipos])
    return [_tipo_out(t, hoje, contagem.get(t.id, 0)) for t in tipos]


@router.get("/tipos/{tipo_id}", response_model=TipoOut, summary="Tipo de teto com o histórico dos valores")
def obter_tipo(tipo_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep):
    tipo = regras.buscar_tipo(db, tipo_id, usuario)
    return _tipo_out(tipo, hoje, _contagem_lancamentos(db, [tipo.id]).get(tipo.id, 0), detalhe=True)


@router.post("/tipos", response_model=TipoOut, status_code=status.HTTP_201_CREATED,
             summary="Cria um tipo de teto num setor, já com o valor (período base + valor)")
def criar_tipo(dados: TipoCriar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep):
    regras.exigir_gestor(usuario)
    setor = db.get(Setor, dados.setor_id)
    if setor is None or not setor.ativo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Setor não encontrado ou inativo")
    if db.scalar(select(TipoTeto.id).where(TipoTeto.setor_id == setor.id,
                                           func.lower(TipoTeto.nome) == dados.nome.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, f"O setor {setor.nome} já tem o tipo {dados.nome}")
    tipo = TipoTeto(setor=setor, nome=dados.nome, descricao=dados.descricao, unidade=dados.unidade.strip(),
                    alerta_pct=dados.alerta_pct, ativo=True, criado_por_id=usuario.id)
    tipo.vigencias.append(TetoVigencia(inicio=dados.inicio or hoje.replace(day=1), periodo=dados.periodo,
                                       valor=dados.valor, criado_por=usuario))
    db.add(tipo)
    db.flush()
    registrar(db, usuario, Acao.TETO_TIPO_CRIADO,
              f"Criou o tipo de teto {tipo.nome} no setor {setor.nome}: "
              f"{regras.formatar(dados.valor, tipo.unidade)} {ROTULO_PERIODO[dados.periodo]}",
              ref=_ref(tipo), detalhes={"periodo": dados.periodo.value, "valor": str(dados.valor),
                                        "unidade": tipo.unidade})
    db.commit()
    return _tipo_out(tipo, hoje, 0, detalhe=True)


ROTULO_PERIODO = {PeriodoTeto.DIARIO: "por dia", PeriodoTeto.MENSAL: "por mês", PeriodoTeto.ANUAL: "por ano"}


@router.patch("/tipos/{tipo_id}", response_model=TipoOut, summary="Altera nome, descrição, unidade, alerta ou situação")
def atualizar_tipo(tipo_id: int, dados: TipoAtualizar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep):
    regras.exigir_gestor(usuario)
    tipo = regras.buscar_tipo(db, tipo_id, usuario)
    novos = {k: v for k, v in dados.model_dump(exclude_unset=True).items() if v is not None or k == "descricao"}
    if novos.get("nome") and novos["nome"].lower() != tipo.nome.lower() and db.scalar(
            select(TipoTeto.id).where(TipoTeto.setor_id == tipo.setor_id, func.lower(TipoTeto.nome) == novos["nome"].lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, f"O setor já tem o tipo {novos['nome']}")
    mudancas = {k: {"de": getattr(tipo, k), "para": v} for k, v in novos.items() if getattr(tipo, k) != v}
    for campo, valor in novos.items():
        setattr(tipo, campo, valor.strip() if isinstance(valor, str) and campo == "unidade" else valor)
    if mudancas:
        registrar(db, usuario, Acao.TETO_TIPO_ALTERADO, f"Alterou o tipo de teto {tipo.nome}", ref=_ref(tipo),
                  detalhes=mudancas)
    db.commit()
    return _tipo_out(tipo, hoje, _contagem_lancamentos(db, [tipo.id]).get(tipo.id, 0), detalhe=True)


@router.delete("/tipos/{tipo_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Exclui um tipo sem lançamentos (com lançamentos, desative)")
def excluir_tipo(tipo_id: int, db: DbDep, usuario: UsuarioDep):
    regras.exigir_gestor(usuario)
    tipo = regras.buscar_tipo(db, tipo_id, usuario)
    if _contagem_lancamentos(db, [tipo.id]).get(tipo.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "O tipo já tem lançamentos: desative-o em vez de excluir")
    registrar(db, usuario, Acao.TETO_TIPO_EXCLUIDO, f"Excluiu o tipo de teto {tipo.nome}", ref=_ref(tipo))
    db.delete(tipo)
    db.commit()


@router.post("/tipos/{tipo_id}/vigencias", response_model=TipoOut,
             summary="Define um novo valor de teto a partir de uma data (o passado continua com o valor antigo)")
def definir_valor(tipo_id: int, dados: VigenciaCriar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep):
    regras.exigir_gestor(usuario)
    tipo = regras.buscar_tipo(db, tipo_id, usuario)
    mesma = next((v for v in tipo.vigencias if v.inicio == dados.inicio), None)
    texto = f"{regras.formatar(dados.valor, tipo.unidade)} {ROTULO_PERIODO[dados.periodo]}"
    if mesma:
        antes = f"{regras.formatar(mesma.valor, tipo.unidade)} {ROTULO_PERIODO[mesma.periodo]}"
        mesma.periodo, mesma.valor, mesma.motivo, mesma.criado_por = dados.periodo, dados.valor, dados.motivo, usuario
    else:
        antes = None
        tipo.vigencias.append(TetoVigencia(inicio=dados.inicio, periodo=dados.periodo, valor=dados.valor,
                                           motivo=dados.motivo, criado_por=usuario))
    db.flush()
    db.refresh(tipo)
    registrar(db, usuario, Acao.TETO_VALOR_DEFINIDO,
              f"Definiu o teto de {tipo.nome} em {texto} a partir de {dados.inicio:%d/%m/%Y}",
              ref=_ref(tipo), detalhes={"inicio": dados.inicio.isoformat(), "valor": {"de": antes, "para": texto},
                                        **({"motivo": dados.motivo} if dados.motivo else {})})
    db.commit()
    return _tipo_out(tipo, hoje, _contagem_lancamentos(db, [tipo.id]).get(tipo.id, 0), detalhe=True)


@router.delete("/vigencias/{vigencia_id}", response_model=TipoOut,
               summary="Remove um valor de teto (o tipo precisa ficar com pelo menos um)")
def excluir_valor(vigencia_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep):
    regras.exigir_gestor(usuario)
    vig = db.get(TetoVigencia, vigencia_id)
    if vig is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Valor de teto não encontrado")
    tipo = regras.buscar_tipo(db, vig.tipo_id, usuario)
    if len(tipo.vigencias) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "O tipo precisa ter pelo menos um valor de teto")
    registrar(db, usuario, Acao.TETO_VALOR_EXCLUIDO,
              f"Removeu o teto de {tipo.nome} que valia a partir de {vig.inicio:%d/%m/%Y} "
              f"({regras.formatar(vig.valor, tipo.unidade)} {ROTULO_PERIODO[vig.periodo]})", ref=_ref(tipo))
    tipo.vigencias.remove(vig)
    db.commit()
    db.refresh(tipo)
    return _tipo_out(tipo, hoje, _contagem_lancamentos(db, [tipo.id]).get(tipo.id, 0), detalhe=True)


# ---------- lançamentos ----------


@router.get("/gastos", response_model=PaginaGastos, summary="Lançamentos, com filtros e o total de cada tipo")
def listar_gastos(
    db: DbDep, usuario: UsuarioDep,
    setor_id: int | None = None, tipo_id: int | None = None, de: date | None = None, ate: date | None = None,
    busca: str | None = Query(default=None, max_length=100),
    pagina: int = Query(default=1, ge=1), por_pagina: int = Query(default=50, ge=1, le=200),
):
    setores = _setores_do_filtro(usuario, setor_id)
    filtros = []
    if setores is not None:
        filtros.append(GastoTeto.setor_id.in_(setores))
    if tipo_id:
        filtros.append(GastoTeto.tipo_id == tipo_id)
    if de:
        filtros.append(GastoTeto.data >= de)
    if ate:
        filtros.append(GastoTeto.data <= ate)
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        filtros.append(or_(GastoTeto.descricao.ilike(termo), GastoTeto.documento.ilike(termo)))
    total = db.scalar(select(func.count()).select_from(GastoTeto).where(*filtros)) or 0
    itens = db.scalars(select(GastoTeto).where(*filtros).order_by(GastoTeto.data.desc(), GastoTeto.id.desc())
                       .offset((pagina - 1) * por_pagina).limit(por_pagina)).all()
    somas = db.execute(select(GastoTeto.tipo_id, func.sum(GastoTeto.valor), func.count()).where(*filtros)
                       .group_by(GastoTeto.tipo_id)).all()
    tipos = {t.id: t for t in db.scalars(select(TipoTeto).where(TipoTeto.id.in_([s[0] for s in somas])))}
    totais = sorted((TotalTipo(tipo=TipoRef.model_validate(tipos[tid]), total=float(regras.arredondar(dec(soma))),
                               quantidade=qtd) for tid, soma, qtd in somas), key=lambda x: x.tipo.nome)
    return PaginaGastos(itens=[_gasto_out(g, usuario) for g in itens], total=total, pagina=pagina,
                        por_pagina=por_pagina, totais=totais)


def _descricao_gasto(g: GastoTeto) -> str:
    return f"{regras.formatar(g.valor, g.tipo.unidade)} em {g.data:%d/%m/%Y} ({g.descricao})"


@router.post("/gastos", response_model=GastoOut, status_code=status.HTTP_201_CREATED,
             summary="Lança um gasto (formulário: tipo_id, data, valor, descricao, documento e arquivo opcional)")
def lancar_gasto(
    db: DbDep, usuario: UsuarioDep, settings: SettingsDep, hoje: HojeDep, agora: AgoraDep,
    tipo_id: Annotated[int, Form()],
    data: Annotated[date, Form()],
    valor: Annotated[str, Form(max_length=30)],
    descricao: Annotated[str, Form(min_length=2, max_length=300)],
    documento: Annotated[str | None, Form(max_length=60)] = None,
    arquivo: Annotated[UploadFile | None, File()] = None,
):
    tipo = _tipo_para_lancar(db, tipo_id, usuario)
    _validar_data_gasto(data, hoje)
    numero = _ler_valor(valor)
    if arquivo is not None and not arquivo.filename:
        arquivo = None
    salvo = armazenamento.salvar_upload(arquivo, settings) if arquivo is not None else None
    g = GastoTeto(tipo=tipo, setor_id=tipo.setor_id, data=data, valor=numero, descricao=descricao.strip(),
                  documento=(documento or "").strip() or None, registrado_por=usuario, registrado_em=agora)
    if salvo:
        g.arquivo_nome, g.arquivo_caminho, g.arquivo_mime = salvo.nome_original, salvo.caminho, salvo.mime_type
        g.arquivo_tamanho, g.arquivo_sha256 = salvo.tamanho_bytes, salvo.hash_sha256
    db.add(g)
    registrar(db, usuario, Acao.GASTO_LANCADO, f"Lançou {_descricao_gasto(g)}", ref=_ref(tipo))
    try:
        db.commit()
    except Exception:
        db.rollback()
        if salvo:
            armazenamento.remover_arquivo(salvo.caminho, settings)
        raise
    return _gasto_out(g, usuario)


@router.patch("/gastos/{gasto_id}", response_model=GastoOut, summary="Corrige um lançamento do setor")
def corrigir_gasto(gasto_id: int, dados: GastoAtualizar, db: DbDep, usuario: UsuarioDep, hoje: HojeDep,
                   agora: AgoraDep):
    g = regras.buscar_gasto(db, gasto_id, usuario)
    antes = _descricao_gasto(g)
    novos = dados.model_dump(exclude_unset=True)
    if novos.get("tipo_id") and novos["tipo_id"] != g.tipo_id:
        novo_tipo = _tipo_para_lancar(db, novos["tipo_id"], usuario)
        if novo_tipo.setor_id != g.setor_id and not regras.eh_gestor(usuario):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo de teto não encontrado")
        g.tipo, g.setor_id = novo_tipo, novo_tipo.setor_id
    if novos.get("data"):
        _validar_data_gasto(novos["data"], hoje)
        g.data = novos["data"]
    if novos.get("valor") is not None:
        g.valor = novos["valor"]
    if novos.get("descricao"):
        g.descricao = novos["descricao"].strip()
    if "documento" in novos:
        g.documento = (novos["documento"] or "").strip() or None
    depois = _descricao_gasto(g)
    if depois == antes and "documento" not in novos and "tipo_id" not in novos:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nada foi alterado")
    g.atualizado_por, g.atualizado_em = usuario, agora
    registrar(db, usuario, Acao.GASTO_ALTERADO, f"Corrigiu o lançamento: {depois}", ref=_ref(g.tipo),
              detalhes={"lancamento": {"de": antes, "para": depois}})
    db.commit()
    return _gasto_out(g, usuario)


@router.put("/gastos/{gasto_id}/arquivo", response_model=GastoOut,
            summary="Anexa ou substitui o comprovante do lançamento")
def anexar_comprovante(gasto_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, agora: AgoraDep,
                       arquivo: Annotated[UploadFile, File()]):
    g = regras.buscar_gasto(db, gasto_id, usuario)
    if not arquivo.filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Escolha um arquivo")
    salvo = armazenamento.salvar_upload(arquivo, settings)
    anterior = g.arquivo_caminho
    g.arquivo_nome, g.arquivo_caminho, g.arquivo_mime = salvo.nome_original, salvo.caminho, salvo.mime_type
    g.arquivo_tamanho, g.arquivo_sha256 = salvo.tamanho_bytes, salvo.hash_sha256
    g.atualizado_por, g.atualizado_em = usuario, agora
    registrar(db, usuario, Acao.GASTO_ALTERADO,
              f"{'Substituiu' if anterior else 'Anexou'} o comprovante do lançamento {_descricao_gasto(g)}",
              ref=_ref(g.tipo), detalhes={"comprovante": salvo.nome_original})
    try:
        db.commit()
    except Exception:
        db.rollback()
        armazenamento.remover_arquivo(salvo.caminho, settings)
        raise
    if anterior:
        armazenamento.remover_arquivo(anterior, settings)
    return _gasto_out(g, usuario)


@router.delete("/gastos/{gasto_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Exclui um lançamento do setor")
def excluir_gasto(gasto_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep):
    g = regras.buscar_gasto(db, gasto_id, usuario)
    caminho = g.arquivo_caminho
    registrar(db, usuario, Acao.GASTO_EXCLUIDO, f"Excluiu o lançamento {_descricao_gasto(g)}", ref=_ref(g.tipo))
    db.delete(g)
    db.commit()
    if caminho:
        armazenamento.remover_arquivo(caminho, settings)


@router.get("/gastos/{gasto_id}/arquivo", summary="Baixa o comprovante (inline=true abre no navegador)")
def baixar_comprovante(gasto_id: int, db: DbDep, usuario: UsuarioDep, settings: SettingsDep, inline: bool = False):
    g = regras.buscar_gasto(db, gasto_id, usuario)
    if not g.arquivo_caminho:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lançamento sem comprovante")
    caminho = armazenamento.caminho_absoluto(g.arquivo_caminho, settings)
    if not caminho.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo não encontrado no servidor")
    return FileResponse(caminho, media_type=g.arquivo_mime or "application/octet-stream", filename=g.arquivo_nome,
                        content_disposition_type="inline" if inline else "attachment")


# ---------- indicadores ----------


@router.get("/painel", response_model=PainelTetos,
            summary="Consumo de cada tipo no dia, no mês e no ano da data de referência, por setor")
def painel(db: DbDep, usuario: UsuarioDep, hoje: HojeDep, setor_id: int | None = None, data: date | None = None):
    ref = min(data or hoje, hoje)
    setores = _setores_do_filtro(usuario, setor_id)
    consulta = (select(TipoTeto).join(Setor).where(TipoTeto.ativo.is_(True), Setor.ativo.is_(True))
                .order_by(Setor.nome, TipoTeto.nome))
    if setores is not None:
        consulta = consulta.where(TipoTeto.setor_id.in_(setores))
    tipos = db.scalars(consulta).unique().all()
    ids = [t.id for t in tipos]
    gastos = _gastos_por_dia(db, ids, date(ref.year, 1, 1), ref)
    contagem = _contagem_lancamentos(db, ids)

    grupos: dict[int, PainelSetor] = {}
    for t in tipos:
        ind = _indicador(t, gastos[t.id], ref, hoje, contagem.get(t.id, 0))
        grupos.setdefault(t.setor_id, PainelSetor(setor=SetorRef.model_validate(t.setor), tipos=[], totais=[]))
        grupos[t.setor_id].tipos.append(ind)
    for g in grupos.values():
        g.totais = _totais(g.tipos)
    todos = [i for g in grupos.values() for i in g.tipos]
    return PainelTetos(
        referencia=ref, setores=list(grupos.values()),
        estourados=sum(i.mes.situacao == SituacaoTeto.ESTOURADO for i in todos),
        em_atencao=sum(i.mes.situacao == SituacaoTeto.ATENCAO or (
            i.mes.projecao_estoura and i.mes.situacao != SituacaoTeto.ESTOURADO) for i in todos),
    )


@router.get("/tipos/{tipo_id}/indicadores", response_model=IndicadoresTipo,
            summary="Indicadores de um tipo: dia a dia no mês, mês a mês no ano e ano a ano")
def indicadores(tipo_id: int, db: DbDep, usuario: UsuarioDep, hoje: HojeDep,
                ano: int | None = Query(default=None, ge=2000, le=2100),
                mes: int | None = Query(default=None, ge=1, le=12)):
    tipo = regras.buscar_tipo(db, tipo_id, usuario)
    ano = ano or hoje.year
    mes = mes or (hoje.month if ano == hoje.year else 12)
    # Referência dos cartões: hoje, ou o último dia do mês escolhido (se for um mês passado)
    ref = min(hoje, regras.fim_do_mes(date(ano, mes, 1)))
    gastos = _gastos_por_dia(db, [tipo.id], None, max(ref, hoje))[tipo.id]
    primeiro_ano = min([v.inicio.year for v in tipo.vigencias] + [d.year for d in gastos] + [ano])
    ultimo_ano = max(ano, hoje.year)
    contagem = _contagem_lancamentos(db, [tipo.id]).get(tipo.id, 0)
    return IndicadoresTipo(
        referencia=ref, ano=ano, mes=mes,
        resumo=_indicador(tipo, gastos, ref, hoje, contagem),
        diario=[PontoDiario(**{k: (float(v) if isinstance(v, Decimal) else v) for k, v in p.items()})
                for p in regras.serie_diaria(tipo.vigencias, gastos, ano, mes)],
        mensal=[PontoMensal(mes=p["mes"], gasto=float(p["gasto"]), teto=float(p["teto"]))
                for p in regras.serie_mensal(tipo.vigencias, gastos, ano)],
        anual=[PontoAnual(ano=p["ano"], gasto=float(p["gasto"]), teto=float(p["teto"]))
               for p in regras.serie_anual(tipo.vigencias, gastos, range(primeiro_ano, ultimo_ano + 1))],
    )
