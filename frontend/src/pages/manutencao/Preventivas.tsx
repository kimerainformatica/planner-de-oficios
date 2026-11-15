import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck, CalendarCheck, ChevronLeft, ChevronRight, ClipboardCheck, Download, Eye, Pencil, Plus, RotateCcw, Trash2,
  XCircle,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import {
  atestarPreventiva, atualizarPlanoPreventiva, baixarEvidenciaPreventiva, criarPlanoPreventiva, excluirPlanoPreventiva,
  listarEmpresas, listarPlanosPreventiva, listarPreventivas, preventivaNaoRealizada, realizarPreventiva, reabrirPreventiva,
} from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { PlanoPreventiva, Preventiva, SituacaoPreventiva, UnidadePeriodo } from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { data, dataHora, hojeIso, tamanho } from "../../utils/formato";
import { CLASSE_PREVENTIVA, ROTULO_PREVENTIVA, ROTULO_UNIDADE_PERIODO, textoDias } from "../../utils/manutencao";
import { Dado } from "../oficio/Dados";

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
  "novembro", "dezembro"];
const SITUACOES: SituacaoPreventiva[] = ["ATRASADA", "NA_JANELA", "PROGRAMADA", "REALIZADA", "REALIZADA_COM_ATRASO",
  "NAO_REALIZADA"];

/** "2026-11" → primeiro e último dia do mês, em ISO. */
function limitesDoMes(mes: string): { de: string; ate: string } {
  const [ano, m] = mes.split("-").map(Number);
  const ultimo = new Date(ano, m, 0).getDate();
  return { de: `${mes}-01`, ate: `${mes}-${String(ultimo).padStart(2, "0")}` };
}

function somarMes(mes: string, n: number): string {
  const [ano, m] = mes.split("-").map(Number);
  const d = new Date(ano, m - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function nomeDoMes(mes: string): string {
  const [ano, m] = mes.split("-").map(Number);
  return `${MESES[m - 1]} de ${ano}`;
}

type Acao = { tipo: "realizar" | "atestar" | "detalhes"; preventiva: Preventiva } | null;

/**
 * Manutenção preventiva: a agenda (o que cada empresa tem para fazer, o que fez e o ateste de quem fiscaliza) e os
 * planos (a periodicidade de cada rotina, definida pelo administrador).
 */
export function Preventivas() {
  const [sp, setSp] = useSearchParams();
  const { papelNo, ehAdminNo } = useAuth();
  const tecnico = papelNo("MANUTENCAO") === "TECNICO";
  const admin = ehAdminNo("MANUTENCAO");
  const aba = sp.get("aba") === "planos" ? "planos" : "agenda";
  const [novoPlano, setNovoPlano] = useState(false);

  function mudar(novos: Record<string, string | undefined>) {
    const p = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(novos)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setSp(p, { replace: true });
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Preventivas</h1>
          <p className="texto-suave">
            {tecnico
              ? "As preventivas da sua empresa. Registre cada uma quando for feita, com o checklist ou a ordem de serviço."
              : "O que cada empresa tem para fazer, o que já fez e o que falta atestar. A periodicidade fica nos planos."}
          </p>
        </div>
        <div className="grupo filtros-quadro">
          <div className="alternador" role="group" aria-label="Visão">
            <button className={aba === "agenda" ? "ativo" : ""} onClick={() => mudar({ aba: undefined })}>Agenda</button>
            <button className={aba === "planos" ? "ativo" : ""} onClick={() => mudar({ aba: "planos" })}>Planos</button>
          </div>
          {admin && (
            <button className="btn btn-primario" onClick={() => setNovoPlano(true)}>
              <Plus size={18} /> Novo plano
            </button>
          )}
        </div>
      </header>

      {aba === "agenda" ? <Agenda sp={sp} mudar={mudar} tecnico={tecnico} /> : <Planos admin={admin} />}
      {novoPlano && <ModalPlano plano={null} aoFechar={() => setNovoPlano(false)} />}
    </>
  );
}

// ---------- agenda ----------

function Agenda({ sp, mudar, tecnico }: {
  sp: URLSearchParams; mudar: (novos: Record<string, string | undefined>) => void; tecnico: boolean;
}) {
  const todos = sp.get("todos") === "1";
  const mes = sp.get("mes") ?? hojeIso().slice(0, 7);
  const situacao = (sp.get("situacao") as SituacaoPreventiva | null) ?? undefined;
  const ateste = sp.get("ateste") === "1";
  const empresaId = sp.get("empresa_id") ? Number(sp.get("empresa_id")) : undefined;
  const periodo = todos ? {} : limitesDoMes(mes);
  const filtros = { ...periodo, empresa_id: empresaId, situacao, aguardando_ateste: ateste };
  const consulta = useQuery({
    queryKey: ["preventivas", filtros], queryFn: () => listarPreventivas(filtros), placeholderData: keepPreviousData,
  });
  const empresas = useQuery({ queryKey: ["empresas-manutencao"], queryFn: () => listarEmpresas(), enabled: !tecnico });
  const [acao, setAcao] = useState<Acao>(null);

  return (
    <>
      <div className="grupo filtros-preventivas">
        <div className="navegador-mes" aria-label="Período">
          <button className="btn-icone" disabled={todos} onClick={() => mudar({ mes: somarMes(mes, -1) })} aria-label="Mês anterior">
            <ChevronLeft size={18} />
          </button>
          <strong>{todos ? "Todos os meses" : nomeDoMes(mes)}</strong>
          <button className="btn-icone" disabled={todos} onClick={() => mudar({ mes: somarMes(mes, 1) })} aria-label="Próximo mês">
            <ChevronRight size={18} />
          </button>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={todos} onChange={(e) => mudar({ todos: e.target.checked ? "1" : undefined })} />
          Todos os meses
        </label>
        {!tecnico && (
          <select className="input" aria-label="Empresa" value={empresaId ?? ""}
            onChange={(e) => mudar({ empresa_id: e.target.value || undefined })}>
            <option value="">Todas as empresas</option>
            {(empresas.data ?? []).map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
          </select>
        )}
        <select className="input" aria-label="Situação" value={ateste ? "ATESTE" : situacao ?? ""}
          onChange={(e) => mudar({
            situacao: e.target.value && e.target.value !== "ATESTE" ? e.target.value : undefined,
            ateste: e.target.value === "ATESTE" ? "1" : undefined,
          })}>
          <option value="">Todas as situações</option>
          {SITUACOES.map((s) => <option key={s} value={s}>{ROTULO_PREVENTIVA[s]}</option>)}
          <option value="ATESTE">Realizadas aguardando ateste</option>
        </select>
      </div>

      {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : (
        <>
          {consulta.data.resumo.length > 0 && (
            <section className="painel-bloco">
              <h2>Previsto x realizado {todos ? "" : `em ${nomeDoMes(mes)}`}</h2>
              <div className="tabela-box">
                <table className="tabela">
                  <thead>
                    <tr>
                      <th>Empresa</th>
                      <th className="num">Previstas</th>
                      <th className="num">Realizadas</th>
                      <th className="num">Atrasadas</th>
                      <th className="num">Não realizadas</th>
                      <th className="num">Aguardando ateste</th>
                      <th className="num">Cumprimento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consulta.data.resumo.map((r) => (
                      <tr key={r.empresa.id}>
                        <td>{r.empresa.nome}</td>
                        <td className="num">{r.previstas}</td>
                        <td className="num">
                          {r.realizadas}
                          {r.com_atraso > 0 && <small className="celula-sub">{r.com_atraso} com atraso</small>}
                        </td>
                        <td className={`num ${r.atrasadas ? "valor-critico" : ""}`}>{r.atrasadas}</td>
                        <td className="num">{r.nao_realizadas}</td>
                        <td className={`num ${r.aguardando_ateste ? "valor-atencao" : ""}`}>{r.aguardando_ateste}</td>
                        <td className="num">
                          {r.cumprimento_pct === null ? "—" : `${r.cumprimento_pct.toLocaleString("pt-BR")}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <small className="texto-suave">
                O cumprimento considera o que já deveria ter sido feito: realizadas ÷ (realizadas + atrasadas + não realizadas).
              </small>
            </section>
          )}

          {consulta.data.itens.length === 0 ? (
            <div className="estado">
              {situacao || ateste || empresaId
                ? "Nenhuma preventiva com esses filtros."
                : "Nenhuma preventiva neste período. As datas são criadas a partir dos planos (aba Planos)."}
            </div>
          ) : (
            <div className="tabela-box">
              <table className="tabela">
                <thead>
                  <tr>
                    <th>Data prevista</th>
                    <th>Preventiva</th>
                    {!tecnico && <th>Empresa</th>}
                    <th>Situação</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {consulta.data.itens.map((p) => (
                    <tr key={p.id}>
                      <td>
                        {data(p.data_prevista)}
                        {p.status === "PROGRAMADA" && <small className="celula-sub">{textoDias(p.dias)}</small>}
                      </td>
                      <td>
                        {p.plano.titulo}
                        <small className="celula-sub">
                          {[p.plano.periodicidade, p.plano.local, p.plano.equipamento].filter(Boolean).join(" · ")}
                        </small>
                      </td>
                      {!tecnico && <td>{p.empresa.nome}</td>}
                      <td><SeloPreventiva p={p} /></td>
                      <td className="num">
                        <div className="grupo grupo-fim acoes-linha">
                          {p.pode_realizar && p.situacao !== "PROGRAMADA" && (
                            <button className="btn btn-secundario btn-pequeno" onClick={() => setAcao({ tipo: "realizar", preventiva: p })}>
                              <ClipboardCheck size={15} /> Registrar
                            </button>
                          )}
                          {p.pode_atestar && (
                            <button className="btn btn-primario btn-pequeno" onClick={() => setAcao({ tipo: "atestar", preventiva: p })}>
                              <BadgeCheck size={15} /> Atestar
                            </button>
                          )}
                          <button className="btn btn-fantasma btn-pequeno" title="Detalhes" aria-label={`Detalhes da ${p.codigo}`}
                            onClick={() => setAcao({ tipo: "detalhes", preventiva: p })}>
                            <Eye size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {acao?.tipo === "realizar" && <ModalRealizar p={acao.preventiva} aoFechar={() => setAcao(null)} />}
      {acao?.tipo === "atestar" && <ModalAtestar p={acao.preventiva} aoFechar={() => setAcao(null)} />}
      {acao?.tipo === "detalhes" && (
        <ModalDetalhes p={acao.preventiva} aoFechar={() => setAcao(null)}
          aoPedir={(tipo) => setAcao({ tipo, preventiva: acao.preventiva })} />
      )}
    </>
  );
}

function SeloPreventiva({ p }: { p: Preventiva }) {
  return (
    <span className="linha-badges">
      <span className={`badge ${CLASSE_PREVENTIVA[p.situacao]}`}>{ROTULO_PREVENTIVA[p.situacao]}</span>
      {p.status === "REALIZADA" && (
        <span className={`badge ${p.atestada_em ? "chamado-prazo-CUMPRIDO" : "chamado-prazo-VENCENDO"}`}>
          {p.atestada_em ? "Atestada" : "Aguardando ateste"}
        </span>
      )}
    </span>
  );
}

/** Depois de qualquer registro: a agenda, os planos e os avisos mudam. */
function useAtualizarPreventivas() {
  const queryClient = useQueryClient();
  return () => {
    for (const chave of ["preventivas", "planos-preventiva", "manutencao-avisos"]) {
      queryClient.invalidateQueries({ queryKey: [chave] });
    }
  };
}

function Evidencia({ p }: { p: Preventiva }) {
  const avisar = useToast();
  const baixar = useMutation({
    mutationFn: () => baixarEvidenciaPreventiva(p),
    onSuccess: (blob) => salvarArquivo(blob, p.arquivo_nome ?? "evidencia"),
    onError: (e) => avisar(e.message),
  });
  if (!p.arquivo_nome) return <small className="texto-suave">Sem arquivo de evidência.</small>;
  return (
    <button type="button" className="arquivo-escolhido arquivo-baixar" onClick={() => baixar.mutate()} disabled={baixar.isPending}>
      <Download size={16} />
      <span className="arquivo-nome">{p.arquivo_nome}</span>
      {p.arquivo_tamanho !== null && <small className="texto-suave">{tamanho(p.arquivo_tamanho)}</small>}
    </button>
  );
}

function DadosPreventiva({ p }: { p: Preventiva }) {
  return (
    <>
      <dl className="dados dados-chamado">
        <Dado rotulo="Empresa" valor={p.empresa.nome} />
        <Dado rotulo="Periodicidade" valor={p.plano.periodicidade} />
        <Dado rotulo="Data prevista" valor={data(p.data_prevista)} />
        <Dado rotulo={`No prazo até (tolerância de ${p.plano.tolerancia_dias} dias)`} valor={data(p.limite)} />
        {p.plano.local && <Dado rotulo="Local / setor" valor={p.plano.local} />}
        {p.plano.equipamento && <Dado rotulo="Equipamento" valor={p.plano.equipamento} />}
      </dl>
      {p.plano.descricao && (
        <>
          <h3 className="titulo-descricao">O que deve ser feito</h3>
          <p className="texto-livre">{p.plano.descricao}</p>
        </>
      )}
    </>
  );
}

function ModalRealizar({ p, aoFechar }: { p: Preventiva; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarPreventivas();
  const { usuario, papelNo } = useAuth();
  const [dia, setDia] = useState(hojeIso());
  const [executor, setExecutor] = useState(papelNo("MANUTENCAO") === "TECNICO" ? usuario?.nome ?? "" : "");
  const [observacao, setObservacao] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const salvar = useMutation({
    mutationFn: () => realizarPreventiva(p.id, { realizada_em: dia, executor: executor.trim(), observacao: observacao.trim(), arquivo }),
    onSuccess: () => {
      atualizar();
      avisar(`Realização da ${p.codigo} registrada. Falta o ateste de quem fiscaliza.`);
      aoFechar();
    },
  });
  return (
    <Modal titulo={`Registrar realização · ${p.plano.titulo}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); salvar.mutate(); }}>
        <DadosPreventiva p={p} />
        <div className="grade-2">
          <Campo rotulo="Realizada em *">
            {(id) => <input id={id} className="input" type="date" required max={hojeIso()} value={dia}
              onChange={(e) => setDia(e.target.value)} />}
          </Campo>
          <Campo rotulo="Quem executou" dica="Técnico ou equipe da empresa.">
            {(id) => <input id={id} className="input" maxLength={120} value={executor} onChange={(e) => setExecutor(e.target.value)} />}
          </Campo>
        </div>
        <Campo rotulo="O que foi feito" dica="Resumo do serviço, pendências e recomendações.">
          {(id) => <textarea id={id} className="input" rows={3} maxLength={5000} value={observacao}
            onChange={(e) => setObservacao(e.target.value)} />}
        </Campo>
        <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} rotulo="Evidência: checklist, ordem de serviço ou relatório (opcional)" compacto />
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}><ClipboardCheck size={16} /> Registrar realização</Botao>
        </div>
      </form>
    </Modal>
  );
}

function Realizacao({ p }: { p: Preventiva }) {
  return (
    <>
      <dl className="dados dados-chamado">
        <Dado rotulo="Realizada em" valor={data(p.realizada_em)} />
        <Dado rotulo="Quem executou" valor={p.executor ?? "—"} />
        <Dado rotulo="Registrada por"
          valor={`${p.registrada_por?.nome ?? "—"}${p.registrada_em ? ` · ${dataHora(p.registrada_em)}` : ""}`} />
      </dl>
      {p.observacao && <p className="texto-livre">{p.observacao}</p>}
      <Evidencia p={p} />
    </>
  );
}

function ModalAtestar({ p, aoFechar }: { p: Preventiva; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarPreventivas();
  const [observacao, setObservacao] = useState("");
  const salvar = useMutation({
    mutationFn: () => atestarPreventiva(p.id, observacao.trim()),
    onSuccess: () => {
      atualizar();
      avisar(`Preventiva ${p.codigo} atestada.`);
      aoFechar();
    },
  });
  return (
    <Modal titulo={`Atestar · ${p.plano.titulo}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); salvar.mutate(); }}>
        <p className="texto-suave">
          O ateste confirma que o serviço foi feito pela <strong>{p.empresa.nome}</strong>. Depois dele, o registro não pode
          mais ser desfeito.
        </p>
        <Realizacao p={p} />
        <Campo rotulo="Observação do ateste" dica="Opcional. Ex.: conferido no local com a equipe.">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={2000} value={observacao}
            onChange={(e) => setObservacao(e.target.value)} />}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao type="submit" carregando={salvar.isPending}><BadgeCheck size={16} /> Atestar</Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalDetalhes({ p, aoFechar, aoPedir }: {
  p: Preventiva; aoFechar: () => void; aoPedir: (tipo: "realizar" | "atestar") => void;
}) {
  const avisar = useToast();
  const atualizar = useAtualizarPreventivas();
  const [motivo, setMotivo] = useState<string | null>(null);
  const aoConcluir = (texto: string) => () => {
    atualizar();
    avisar(texto);
    aoFechar();
  };
  const naoRealizada = useMutation({
    mutationFn: () => preventivaNaoRealizada(p.id, (motivo ?? "").trim()),
    onSuccess: aoConcluir(`Preventiva ${p.codigo} marcada como não realizada.`),
  });
  const reabrir = useMutation({
    mutationFn: () => reabrirPreventiva(p.id),
    onSuccess: aoConcluir(`Registro da ${p.codigo} desfeito.`),
  });
  const erro = naoRealizada.error ?? reabrir.error;
  return (
    <Modal titulo={`${p.codigo} · ${p.plano.titulo}`} aoFechar={aoFechar}>
      <div className="formulario">
        <SeloPreventiva p={p} />
        <DadosPreventiva p={p} />
        {p.status === "REALIZADA" && (
          <>
            <h3 className="titulo-descricao">Realização</h3>
            <Realizacao p={p} />
            <h3 className="titulo-descricao">Ateste</h3>
            {p.atestada_em ? (
              <p className="texto-livre">
                Atestada por {p.atestada_por?.nome ?? "—"} em {dataHora(p.atestada_em)}.
                {p.ateste_obs && <><br />{p.ateste_obs}</>}
              </p>
            ) : <small className="texto-suave">Aguardando o ateste do operacional ou do administrador.</small>}
          </>
        )}
        {p.status === "NAO_REALIZADA" && (
          <>
            <h3 className="titulo-descricao">Não realizada</h3>
            <p className="texto-livre">{p.motivo}</p>
            <small className="texto-suave">
              Registrado por {p.registrada_por?.nome ?? "—"}{p.registrada_em ? ` em ${dataHora(p.registrada_em)}` : ""}.
            </small>
          </>
        )}
        {motivo !== null && (
          <Campo rotulo="Motivo de não ter sido realizada *">
            {(id) => <textarea id={id} className="input" rows={2} autoFocus minLength={3} maxLength={2000} value={motivo}
              onChange={(e) => setMotivo(e.target.value)} />}
          </Campo>
        )}
        {erro && <div className="alerta-erro">{erro.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Fechar</button>
          {p.pode_reabrir && (
            <Botao className="btn btn-fantasma" carregando={reabrir.isPending}
              onClick={() => window.confirm("Desfazer o registro desta preventiva? A evidência anexada é apagada.") && reabrir.mutate()}>
              <RotateCcw size={16} /> Desfazer registro
            </Botao>
          )}
          {p.pode_nao_realizar && (motivo === null ? (
            <button type="button" className="btn btn-fantasma btn-perigo" onClick={() => setMotivo("")}>
              <XCircle size={16} /> Não foi realizada
            </button>
          ) : (
            <Botao className="btn btn-perigo" carregando={naoRealizada.isPending} disabled={motivo.trim().length < 3}
              onClick={() => naoRealizada.mutate()}>
              Confirmar não realizada
            </Botao>
          ))}
          {p.pode_atestar && (
            <button type="button" className="btn btn-primario" onClick={() => aoPedir("atestar")}>
              <BadgeCheck size={16} /> Atestar
            </button>
          )}
          {p.pode_realizar && motivo === null && (
            <button type="button" className="btn btn-primario" onClick={() => aoPedir("realizar")}>
              <ClipboardCheck size={16} /> Registrar realização
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}

// ---------- planos ----------

function Planos({ admin }: { admin: boolean }) {
  const avisar = useToast();
  const atualizar = useAtualizarPreventivas();
  const consulta = useQuery({ queryKey: ["planos-preventiva"], queryFn: listarPlanosPreventiva });
  const [editando, setEditando] = useState<PlanoPreventiva | null>(null);
  const excluir = useMutation({
    mutationFn: (p: PlanoPreventiva) => excluirPlanoPreventiva(p.id),
    onSuccess: () => {
      atualizar();
      avisar("Plano excluído.");
    },
    onError: (e) => avisar(e.message),
  });

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  if (consulta.data.length === 0) {
    return (
      <div className="estado">
        <CalendarCheck size={22} />
        {admin
          ? "Nenhum plano ainda. Crie um plano para cada rotina de preventiva, com a empresa e a periodicidade."
          : "Nenhum plano de preventiva cadastrado. O administrador do módulo define os planos."}
      </div>
    );
  }
  return (
    <>
      <div className="tabela-box">
        <table className="tabela">
          <thead>
            <tr>
              <th>Plano</th>
              <th>Empresa</th>
              <th>Periodicidade</th>
              <th>Próxima</th>
              <th className="num">Realizadas / devidas</th>
              <th className="num">Atrasadas</th>
              <th>Situação</th>
              {admin && <th aria-label="Ações" />}
            </tr>
          </thead>
          <tbody>
            {consulta.data.map((p) => (
              <tr key={p.id} className={p.ativo ? "" : "linha-inativa"}>
                <td>
                  {p.titulo}
                  <small className="celula-sub">{[p.local, p.equipamento].filter(Boolean).join(" · ")}</small>
                </td>
                <td>{p.empresa.nome}</td>
                <td>
                  {p.periodicidade}
                  <small className="celula-sub">tolerância de {p.tolerancia_dias} dias</small>
                </td>
                <td>{p.proxima ? data(p.proxima) : "—"}</td>
                <td className="num">{p.realizadas} / {p.previstas}</td>
                <td className={`num ${p.atrasadas ? "valor-critico" : ""}`}>{p.atrasadas}</td>
                <td>{p.ativo ? "Ativo" : "Inativo"}</td>
                {admin && (
                  <td className="num">
                    <div className="grupo grupo-fim">
                      <button className="btn btn-fantasma btn-pequeno" onClick={() => setEditando(p)}>
                        <Pencil size={15} /> Editar
                      </button>
                      {p.previstas === 0 && (
                        <button className="btn btn-fantasma btn-pequeno" disabled={excluir.isPending}
                          onClick={() => window.confirm(`Excluir o plano ${p.titulo}?`) && excluir.mutate(p)}>
                          <Trash2 size={15} /> Excluir
                        </button>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editando && <ModalPlano plano={editando} aoFechar={() => setEditando(null)} />}
    </>
  );
}

function ModalPlano({ plano, aoFechar }: { plano: PlanoPreventiva | null; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarPreventivas();
  const empresas = useQuery({ queryKey: ["empresas-manutencao", "ativas"], queryFn: () => listarEmpresas(true) });
  const [empresaId, setEmpresaId] = useState<number | "">(plano?.empresa.id ?? "");
  const [titulo, setTitulo] = useState(plano?.titulo ?? "");
  const [descricao, setDescricao] = useState(plano?.descricao ?? "");
  const [local, setLocal] = useState(plano?.local ?? "");
  const [equipamento, setEquipamento] = useState(plano?.equipamento ?? "");
  const [intervalo, setIntervalo] = useState(plano?.intervalo ?? 1);
  const [unidade, setUnidade] = useState<UnidadePeriodo>(plano?.unidade ?? "MESES");
  // Ao editar, a data é a da próxima preventiva: as datas futuras são refeitas a partir dela
  const [inicio, setInicio] = useState(plano ? plano.proxima ?? plano.inicio : hojeIso());
  const [tolerancia, setTolerancia] = useState(plano?.tolerancia_dias ?? 5);
  const [ativo, setAtivo] = useState(plano?.ativo ?? true);
  const salvar = useMutation({
    mutationFn: () => {
      const dados = {
        titulo: titulo.trim(), descricao: descricao.trim() || null, local: local.trim() || null,
        equipamento: equipamento.trim() || null, intervalo, unidade, inicio, tolerancia_dias: tolerancia,
      };
      return plano
        ? atualizarPlanoPreventiva(plano.id, { ...dados, ativo })
        : criarPlanoPreventiva({ ...dados, empresa_id: Number(empresaId) });
    },
    onSuccess: (p) => {
      atualizar();
      avisar(plano ? `Plano ${p.titulo} atualizado.` : `Plano ${p.titulo} criado (${p.periodicidade}).`);
      aoFechar();
    },
  });
  return (
    <Modal titulo={plano ? `Editar plano · ${plano.titulo}` : "Novo plano de preventiva"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); salvar.mutate(); }}>
        <div className="grade-2">
          <Campo rotulo="Empresa técnica *">
            {(id) => plano ? <input id={id} className="input" value={plano.empresa.nome} disabled /> : (
              <select id={id} className="input" required value={empresaId} onChange={(e) => setEmpresaId(Number(e.target.value) || "")}>
                <option value="">Selecione</option>
                {(empresas.data ?? []).map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
              </select>
            )}
          </Campo>
          <Campo rotulo="Rotina *" dica="Ex.: Preventiva dos compressores, Limpeza dos filtros do ar.">
            {(id) => <input id={id} className="input" required minLength={3} maxLength={150} autoFocus value={titulo}
              onChange={(e) => setTitulo(e.target.value)} />}
          </Campo>
          <Campo rotulo="Local / setor">
            {(id) => <input id={id} className="input" maxLength={120} value={local} onChange={(e) => setLocal(e.target.value)} />}
          </Campo>
          <Campo rotulo="Equipamento">
            {(id) => <input id={id} className="input" maxLength={120} value={equipamento} onChange={(e) => setEquipamento(e.target.value)} />}
          </Campo>
        </div>
        <Campo rotulo="O que deve ser feito" dica="O escopo combinado com a empresa. Aparece para o técnico e para quem atesta.">
          {(id) => <textarea id={id} className="input" rows={3} maxLength={5000} value={descricao}
            onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        <div className="grade-2">
          <Campo rotulo="Repetir a cada *">
            {(id) => (
              <div className="grupo">
                <input id={id} className="input input-curto" type="number" required min={1} max={120} value={intervalo}
                  onChange={(e) => setIntervalo(Number(e.target.value))} />
                <select className="input" aria-label="Unidade do período" value={unidade}
                  onChange={(e) => setUnidade(e.target.value as UnidadePeriodo)}>
                  {Object.entries(ROTULO_UNIDADE_PERIODO).map(([k, r]) => <option key={k} value={k}>{r}</option>)}
                </select>
              </div>
            )}
          </Campo>
          <Campo rotulo={plano ? "Próxima preventiva em *" : "Primeira preventiva em *"}
            dica={plano ? "Mudar a data ou o período refaz só as datas futuras." : "As seguintes contam a partir desta data."}>
            {(id) => <input id={id} className="input" type="date" required value={inicio} onChange={(e) => setInicio(e.target.value)} />}
          </Campo>
          <Campo rotulo="Tolerância (dias) *" dica="Dias depois da data em que ainda conta como feita no prazo.">
            {(id) => <input id={id} className="input" type="number" required min={0} max={60} value={tolerancia}
              onChange={(e) => setTolerancia(Number(e.target.value))} />}
          </Campo>
        </div>
        {plano && (
          <label className="checkbox">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
            Ativo (desmarque para parar de gerar novas datas; o histórico fica)
          </label>
        )}
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>{plano ? "Salvar" : "Criar plano"}</Botao>
        </div>
      </form>
    </Modal>
  );
}
