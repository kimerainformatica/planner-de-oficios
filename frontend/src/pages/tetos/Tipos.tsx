import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, CircleDollarSign, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  atualizarTipoTeto, criarTipoTeto, definirValorTeto, excluirTipoTeto, excluirValorTeto, listarSetores, listarTiposTeto,
  obterTipoTeto,
} from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { PeriodoTeto, TipoTeto } from "../../types";
import { data as dataBr, hojeIso } from "../../utils/formato";
import { lerValor, NOME_PERIODO, primeiroDoMes, ROTULO_PERIODO, valorParaCampo, valorTeto } from "../../utils/tetos";

const UNIDADES = ["R$", "litros", "resmas", "unidades", "kWh", "m³", "kg", "pacotes", "impressões"];

/** Administração dos tipos de teto de cada setor (só o administrador do módulo). */
export function TiposTeto() {
  const [params, setParams] = useSearchParams();
  const setorId = params.get("setor") ? Number(params.get("setor")) : undefined;
  const [inativos, setInativos] = useState(false);
  const [modal, setModal] = useState<{ tipo: "novo" } | { tipo: "editar" | "valor" | "excluir"; t: TipoTeto } | null>(null);

  const setores = useQuery({ queryKey: ["setores-tetos"], queryFn: listarSetores });
  const tipos = useQuery({
    queryKey: ["tipos-teto", "admin", setorId, inativos],
    queryFn: () => listarTiposTeto({ setor_id: setorId, incluir_inativos: inativos }),
  });
  const grupos = new Map<number, { nome: string; tipos: TipoTeto[] }>();
  for (const t of tipos.data ?? []) {
    if (!grupos.has(t.setor.id)) grupos.set(t.setor.id, { nome: t.setor.nome, tipos: [] });
    grupos.get(t.setor.id)!.tipos.push(t);
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Tipos de teto</h1>
          <p className="texto-suave">
            O que cada setor mede e o teto de cada um. O valor é definido num período (diário, mensal ou anual) e os
            outros períodos saem por proporção.
          </p>
        </div>
        <button className="btn btn-primario" onClick={() => setModal({ tipo: "novo" })} disabled={!setores.data?.some((s) => s.ativo)}>
          <Plus size={18} /> Novo tipo
        </button>
      </header>

      <div className="grupo filtros-tetos">
        <select className="input" aria-label="Setor" value={setorId ?? ""}
          onChange={(e) => setParams(e.target.value ? { setor: e.target.value } : {}, { replace: true })}>
          <option value="">Todos os setores</option>
          {(setores.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
        </select>
        <label className="checkbox">
          <input type="checkbox" checked={inativos} onChange={(e) => setInativos(e.target.checked)} /> Mostrar desativados
        </label>
      </div>

      {setores.data && setores.data.length === 0 && (
        <div className="aviso-vazio" role="status">
          Cadastre primeiro os setores em <Link to="/tetos/setores">Setores</Link>.
        </div>
      )}
      {tipos.isPending ? <Carregando /> : tipos.isError ? <ErroBox erro={tipos.error} /> : (
        grupos.size === 0 ? (
          setores.data?.length ? <div className="aviso-vazio" role="status">Nenhum tipo de teto ainda. Clique em Novo tipo.</div> : null
        ) : [...grupos.entries()].map(([id, g]) => (
          <section key={id} className="painel-bloco">
            <div className="bloco-topo"><h2>{g.nome}</h2></div>
            <div className="tabela-box">
              <table className="tabela tabela-tetos">
                <thead>
                  <tr>
                    <th>Tipo</th>
                    <th>Teto atual</th>
                    <th>Equivale a</th>
                    <th className="num">Alerta</th>
                    <th className="num">Lançamentos</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {g.tipos.map((t) => (
                    <tr key={t.id} className={t.ativo ? "" : "linha-inativa"}>
                      <td>
                        <strong>{t.nome}</strong> <small className="texto-suave">({t.unidade})</small>
                        {t.descricao && <small className="texto-suave"><br />{t.descricao}</small>}
                        {!t.ativo && <small className="texto-suave"><br />Desativado</small>}
                      </td>
                      <td>
                        {t.valor !== null && t.periodo ? <strong>{valorTeto(t.valor, t.unidade)} {ROTULO_PERIODO[t.periodo]}</strong> : "—"}
                        {t.vigente_desde && <small className="texto-suave"><br />desde {dataBr(t.vigente_desde)}</small>}
                      </td>
                      <td>
                        {t.equivalentes && (
                          <small className="texto-suave equivalentes">
                            <span>{valorTeto(t.equivalentes.diario, t.unidade)}/dia</span>
                            <span>{valorTeto(t.equivalentes.mensal, t.unidade)}/mês</span>
                            <span>{valorTeto(t.equivalentes.anual, t.unidade)}/ano</span>
                          </small>
                        )}
                      </td>
                      <td className="num">{t.alerta_pct}%</td>
                      <td className="num">{t.lancamentos}</td>
                      <td className="num">
                        <div className="grupo grupo-fim acoes-linha">
                          <Link to={`/tetos/tipo/${t.id}`} className="btn btn-fantasma btn-pequeno" title="Indicadores"
                            aria-label={`Indicadores de ${t.nome}`}><BarChart3 size={15} /></Link>
                          <button className="btn btn-secundario btn-pequeno" onClick={() => setModal({ tipo: "valor", t })}>
                            <CircleDollarSign size={15} /> Valor do teto
                          </button>
                          <button className="btn btn-fantasma btn-pequeno" onClick={() => setModal({ tipo: "editar", t })}
                            title="Editar" aria-label={`Editar ${t.nome}`}>
                            <Pencil size={15} />
                          </button>
                          {t.lancamentos === 0 && (
                            <button className="btn btn-fantasma btn-pequeno btn-perigo" onClick={() => setModal({ tipo: "excluir", t })}
                              aria-label={`Excluir ${t.nome}`}><Trash2 size={15} /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}

      {modal?.tipo === "novo" && <ModalNovoTipo setorInicial={setorId} aoFechar={() => setModal(null)} />}
      {modal?.tipo === "editar" && <ModalEditarTipo t={modal.t} aoFechar={() => setModal(null)} />}
      {modal?.tipo === "valor" && <ModalValor id={modal.t.id} aoFechar={() => setModal(null)} />}
      {modal?.tipo === "excluir" && <ModalExcluirTipo t={modal.t} aoFechar={() => setModal(null)} />}
    </>
  );
}

function useAtualizarTipos() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["tipos-teto"] });
    qc.invalidateQueries({ queryKey: ["tipo-teto"] });
    qc.invalidateQueries({ queryKey: ["tetos-painel"] });
    qc.invalidateQueries({ queryKey: ["tetos-indicadores"] });
  };
}

/** Período base + valor, com a prévia dos três tetos (o mês e o dia, no mês corrente). */
function CamposValor({ periodo, setPeriodo, valor, setValor, unidade }: {
  periodo: PeriodoTeto; setPeriodo: (p: PeriodoTeto) => void; valor: string; setValor: (v: string) => void; unidade: string;
}) {
  const n = Number(lerValor(valor) ?? 0);
  const hoje = new Date();
  const diasMes = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0).getDate();
  const mensal = periodo === "MENSAL" ? n : periodo === "ANUAL" ? n / 12 : n * diasMes;
  const diario = periodo === "DIARIO" ? n : mensal / diasMes;
  const anual = periodo === "ANUAL" ? n : periodo === "MENSAL" ? n * 12 : n * 365;
  return (
    <>
      <div className="campo">
        <span className="rotulo">Período em que o teto é definido *</span>
        <div className="segmentado" role="radiogroup" aria-label="Período do teto">
          {(["DIARIO", "MENSAL", "ANUAL"] as PeriodoTeto[]).map((p) => (
            <label key={p} className={`segmento ${periodo === p ? "ativo" : ""}`}>
              <input type="radio" name="periodo" checked={periodo === p} onChange={() => setPeriodo(p)} />
              {NOME_PERIODO[p]}
            </label>
          ))}
        </div>
      </div>
      <Campo rotulo={`Valor do teto ${ROTULO_PERIODO[periodo]} (${unidade}) *`} dica="Ex.: 12.000,00">
        {(id) => <input id={id} className="input" required inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} />}
      </Campo>
      {n > 0 && (
        <p className="previa-teto" role="status">
          Equivale a <strong>{valorTeto(diario, unidade)}</strong> por dia,{" "}
          <strong>{valorTeto(mensal, unidade)}</strong> por mês e <strong>{valorTeto(anual, unidade)}</strong> por ano
          {periodo === "ANUAL" && " (o valor por dia varia com o número de dias do mês)"}
          {periodo === "DIARIO" && " (o valor por mês varia com o número de dias do mês)"}.
        </p>
      )}
    </>
  );
}

function ModalNovoTipo({ setorInicial, aoFechar }: { setorInicial?: number; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarTipos();
  const setores = useQuery({ queryKey: ["setores-tetos"], queryFn: listarSetores });
  const [setorId, setSetorId] = useState<number | "">(setorInicial ?? "");
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [unidade, setUnidade] = useState("R$");
  const [periodo, setPeriodo] = useState<PeriodoTeto>("MENSAL");
  const [valor, setValor] = useState("");
  const [inicio, setInicio] = useState(primeiroDoMes());
  const [alerta, setAlerta] = useState(80);
  const [erro, setErro] = useState<string | null>(null);

  const salvar = useMutation({
    mutationFn: () => {
      const v = lerValor(valor);
      if (!v) throw new Error("Informe o valor do teto (maior que zero, até duas casas decimais).");
      return criarTipoTeto({ setor_id: Number(setorId), nome: nome.trim(), descricao: descricao.trim() || null,
        unidade: unidade.trim() || "R$", alerta_pct: alerta, periodo, valor: v, inicio });
    },
    onSuccess: (t) => { atualizar(); avisar(`Tipo ${t.nome} criado no setor ${t.setor.nome}.`); aoFechar(); },
    onError: (e: Error) => setErro(e.message),
  });

  return (
    <Modal titulo="Novo tipo de teto" aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); setErro(null); salvar.mutate(); }}>
        <div className="grade-2">
          <Campo rotulo="Setor *">
            {(id) => (
              <select id={id} className="input" required value={setorId} onChange={(e) => setSetorId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Selecione…</option>
                {(setores.data ?? []).filter((s) => s.ativo).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            )}
          </Campo>
          <Campo rotulo="Nome *" dica="Ex.: Material de escritório, Combustível, Telefonia">
            {(id) => <input id={id} className="input" required minLength={2} maxLength={120} value={nome} autoFocus onChange={(e) => setNome(e.target.value)} />}
          </Campo>
        </div>
        <Campo rotulo="Descrição">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={2000} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        <div className="grade-2">
          <Campo rotulo="Unidade *" dica="R$ para dinheiro, ou a medida (litros, resmas, kWh…)">
            {(id) => (
              <>
                <input id={id} className="input" required maxLength={20} list="unidades-teto" value={unidade} onChange={(e) => setUnidade(e.target.value)} />
                <datalist id="unidades-teto">{UNIDADES.map((u) => <option key={u} value={u} />)}</datalist>
              </>
            )}
          </Campo>
          <Campo rotulo="Alerta a partir de (%) *" dica="Quando o gasto chega a esse % do teto, o tipo fica em atenção.">
            {(id) => <input id={id} className="input input-curto" type="number" required min={1} max={100} value={alerta}
              onChange={(e) => setAlerta(Number(e.target.value))} />}
          </Campo>
        </div>
        <CamposValor periodo={periodo} setPeriodo={setPeriodo} valor={valor} setValor={setValor} unidade={unidade || "R$"} />
        <Campo rotulo="Vale a partir de *" dica="Normalmente o 1º dia do mês ou do ano. Vale também para os gastos anteriores.">
          {(id) => <input id={id} className="input" type="date" required value={inicio} onChange={(e) => setInicio(e.target.value)} />}
        </Campo>
        {erro && <div className="alerta-erro">{erro}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Criar tipo</Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalEditarTipo({ t, aoFechar }: { t: TipoTeto; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarTipos();
  const [nome, setNome] = useState(t.nome);
  const [descricao, setDescricao] = useState(t.descricao ?? "");
  const [unidade, setUnidade] = useState(t.unidade);
  const [alerta, setAlerta] = useState(t.alerta_pct);
  const [ativo, setAtivo] = useState(t.ativo);
  const salvar = useMutation({
    mutationFn: () => atualizarTipoTeto(t.id, { nome: nome.trim(), descricao: descricao.trim() || null, unidade: unidade.trim(),
      alerta_pct: alerta, ativo }),
    onSuccess: () => { atualizar(); avisar(`Tipo ${nome.trim()} atualizado.`); aoFechar(); },
  });
  return (
    <Modal titulo={`Editar ${t.nome}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); salvar.mutate(); }}>
        <Campo rotulo="Nome *">
          {(id) => <input id={id} className="input" required minLength={2} maxLength={120} value={nome} onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Descrição">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={2000} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        <div className="grade-2">
          <Campo rotulo="Unidade *" dica={t.lancamentos ? "Mudar a unidade não converte os lançamentos já feitos." : undefined}>
            {(id) => <input id={id} className="input" required maxLength={20} list="unidades-teto-e" value={unidade} onChange={(e) => setUnidade(e.target.value)} />}
          </Campo>
          <Campo rotulo="Alerta a partir de (%) *">
            {(id) => <input id={id} className="input input-curto" type="number" required min={1} max={100} value={alerta}
              onChange={(e) => setAlerta(Number(e.target.value))} />}
          </Campo>
        </div>
        <datalist id="unidades-teto-e">{UNIDADES.map((u) => <option key={u} value={u} />)}</datalist>
        <label className="checkbox">
          <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
          Ativo (desativado, sai do painel e não recebe lançamentos; o histórico fica)
        </label>
        <p className="texto-suave">Para mudar o valor do teto, use <strong>Valor do teto</strong>: assim o passado continua com o valor antigo.</p>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Salvar</Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalValor({ id, aoFechar }: { id: number; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarTipos();
  const tipo = useQuery({ queryKey: ["tipo-teto", id], queryFn: () => obterTipoTeto(id) });
  const atual = tipo.data?.vigencias[0];
  const [periodo, setPeriodo] = useState<PeriodoTeto | null>(null);
  const [valor, setValor] = useState<string | null>(null);
  const [inicio, setInicio] = useState(primeiroDoMes());
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const p = periodo ?? atual?.periodo ?? "MENSAL";
  const v = valor ?? (atual ? valorParaCampo(atual.valor) : "");

  const salvar = useMutation({
    mutationFn: () => {
      const numero = lerValor(v);
      if (!numero) throw new Error("Informe o valor do teto (maior que zero, até duas casas decimais).");
      return definirValorTeto(id, { periodo: p, valor: numero, inicio, motivo: motivo.trim() || null });
    },
    onSuccess: (t) => {
      atualizar();
      avisar(`Novo teto de ${t.nome} a partir de ${dataBr(inicio)}.`);
      aoFechar();
    },
    onError: (e: Error) => setErro(e.message),
  });
  const remover = useMutation({
    mutationFn: (vigenciaId: number) => excluirValorTeto(vigenciaId),
    onSuccess: () => { atualizar(); avisar("Valor removido."); },
    onError: (e: Error) => setErro(e.message),
  });

  if (tipo.isPending) return <Modal titulo="Valor do teto" aoFechar={aoFechar}><Carregando /></Modal>;
  if (tipo.isError) return <Modal titulo="Valor do teto" aoFechar={aoFechar}><ErroBox erro={tipo.error} /></Modal>;
  const t = tipo.data;
  return (
    <Modal titulo={`Valor do teto · ${t.nome}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); setErro(null); salvar.mutate(); }}>
        <p className="texto-suave">
          O novo valor vale a partir da data escolhida. Os dias anteriores continuam com o valor que valia neles. Na
          mesma data de um valor existente, ele é substituído.
        </p>
        <CamposValor periodo={p} setPeriodo={setPeriodo} valor={v} setValor={setValor} unidade={t.unidade} />
        <div className="grade-2">
          <Campo rotulo="Vale a partir de *">
            {(fid) => <input id={fid} className="input" type="date" required value={inicio} max={`${new Date().getFullYear() + 1}-12-31`}
              onChange={(e) => setInicio(e.target.value)} />}
          </Campo>
          <Campo rotulo="Motivo" dica="Opcional. Ex.: novo contrato, remanejamento">
            {(fid) => <input id={fid} className="input" maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
          </Campo>
        </div>
        {erro && <div className="alerta-erro">{erro}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Fechar</button>
          <Botao type="submit" carregando={salvar.isPending}>Salvar valor</Botao>
        </div>
      </form>
      <h3 className="titulo-secao">Histórico dos valores</h3>
      <ul className="vigencias">
        {t.vigencias.map((vg) => (
          <li key={vg.id}>
            <strong>{valorTeto(vg.valor, t.unidade)} {ROTULO_PERIODO[vg.periodo]}</strong>
            <span className="texto-suave"> · a partir de {dataBr(vg.inicio)}{vg.inicio > hojeIso() ? " (futuro)" : ""}</span>
            <small className="texto-suave">{vg.criado_por?.nome ?? "—"}{vg.motivo ? ` · ${vg.motivo}` : ""}</small>
            {t.vigencias.length > 1 && (
              <button type="button" className="btn btn-fantasma btn-pequeno btn-perigo" disabled={remover.isPending}
                onClick={() => remover.mutate(vg.id)} aria-label={`Remover o valor de ${dataBr(vg.inicio)}`}>
                <Trash2 size={14} />
              </button>
            )}
          </li>
        ))}
      </ul>
    </Modal>
  );
}

function ModalExcluirTipo({ t, aoFechar }: { t: TipoTeto; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarTipos();
  const excluir = useMutation({
    mutationFn: () => excluirTipoTeto(t.id),
    onSuccess: () => { atualizar(); avisar(`Tipo ${t.nome} excluído.`); aoFechar(); },
  });
  return (
    <Modal titulo={`Excluir ${t.nome}`} aoFechar={aoFechar}>
      <p>O tipo ainda não tem lançamentos e será excluído com os valores de teto dele.</p>
      {excluir.isError && <div className="alerta-erro">{excluir.error.message}</div>}
      <div className="acoes-form">
        <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
        <Botao className="btn btn-perigo" carregando={excluir.isPending} onClick={() => excluir.mutate()}>Excluir</Botao>
      </div>
    </Modal>
  );
}
