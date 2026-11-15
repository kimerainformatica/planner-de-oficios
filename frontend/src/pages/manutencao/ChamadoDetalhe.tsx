import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, CalendarClock, CheckCircle2, ClipboardList, Download, FileText, Hand, Link2, MessageSquare, PackagePlus,
  PencilLine, RotateCcw, Search, Stethoscope, Unlink, XCircle,
} from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  assumirChamado, baixarAnexoOficio, cancelarChamado, concluirChamado, desvincularOficio, oficiosDisponiveis,
  reabrirChamado, responderChamado, solicitarPecas, tiposSolicitacao, verChamado, vincularOficio,
} from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal, StatusBadge } from "../../components/ui";
import type { AnexoOficio, ChamadoDetalhe as Detalhe, Destinatario, Interacao, OficioVinculado } from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { data, dataHora, hojeIso, ROTULO_DESTINATARIO, tamanho } from "../../utils/formato";
import { horas, ROTULO_INTERACAO, ROTULO_PAPEL_MANUTENCAO } from "../../utils/manutencao";
import { Dado } from "../oficio/Dados";
import { BadgePrazo, BadgeStatusChamado } from "./comum";
import { ArquivoExterno, BotaoPdf, SecaoDiagnostico, VisaoRelatorio } from "./Diagnostico";

type Janela = "concluir" | "reabrir" | "cancelar" | "pecas" | "vincular" | null;

export function ChamadoDetalhe() {
  const id = Number(useParams().id);
  const queryClient = useQueryClient();
  const { modulos, usuario, ehAdmin: ehAdminPlanner } = useAuth();
  const temAcessoPlanner = modulos.includes("OFICIOS");
  // O que é feito no Planner (documentos, resposta, entrega) aparece aqui: atualiza sozinho a cada 30 s
  const consulta = useQuery({ queryKey: ["chamado", id], queryFn: () => verChamado(id), refetchInterval: 30_000 });
  const [janela, setJanela] = useState<Janela>(null);
  const [desvincular, setDesvincular] = useState<OficioVinculado | null>(null);

  const atualizar = (c: Detalhe) => {
    queryClient.setQueryData(["chamado", id], c);
    queryClient.invalidateQueries({ queryKey: ["chamados"] });
    queryClient.invalidateQueries({ queryKey: ["manutencao-painel"] });
  };
  // Vincular ou desvincular um ofício muda também o quadro, a lista do Planner e os ofícios disponíveis
  const atualizarOficios = (c: Detalhe) => {
    atualizar(c);
    for (const chave of ["oficios", "oficio", "manutencao-quadro", "oficios-disponiveis"]) {
      queryClient.invalidateQueries({ queryKey: [chave] });
    }
  };
  const assumir = useMutation({ mutationFn: () => assumirChamado(id), onSuccess: atualizar });

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  const c = consulta.data;

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/manutencao/chamados" className="voltar"><ArrowLeft size={16} /> Chamados</Link>
          <h1>{c.codigo} · {c.titulo}</h1>
          <div className="linha-badges">
            <BadgeStatusChamado status={c.status} />
            <BadgePrazo prazo={c.prazo} comTexto />
          </div>
        </div>
        <div className="grupo acoes-chamado">
          {c.pode_assumir && (
            <Botao className="btn btn-secundario" carregando={assumir.isPending} onClick={() => assumir.mutate()}>
              <Hand size={17} /> Assumir
            </Botao>
          )}
          {c.pode_concluir && (
            <button className="btn btn-primario" onClick={() => setJanela("concluir")}>
              <CheckCircle2 size={17} /> Concluir
            </button>
          )}
          {c.pode_reabrir && (
            <button className="btn btn-secundario" onClick={() => setJanela("reabrir")}>
              <RotateCcw size={17} /> Reabrir
            </button>
          )}
          {c.pode_cancelar && (
            <button className="btn btn-fantasma btn-perigo" onClick={() => setJanela("cancelar")}>
              <XCircle size={17} /> Cancelar chamado
            </button>
          )}
        </div>
      </header>
      {assumir.isError && <div className="alerta-erro">{assumir.error.message}</div>}

      <section className="cartao">
        <dl className="dados dados-chamado">
          <Dado rotulo="Empresa / modalidade" valor={c.empresa.nome} />
          <Dado rotulo="Técnico responsável" valor={c.tecnico?.nome ?? "Ainda não assumido"} />
          <Dado rotulo="Aberto por" valor={c.solicitante.nome} />
          <Dado rotulo="Local / setor" valor={c.local ?? "—"} />
          <Dado rotulo="Equipamento" valor={c.equipamento ?? "—"} />
          <Dado rotulo="Problema ocorrido em" valor={dataHora(c.ocorrido_em)} />
          <Dado rotulo="Aberto em" valor={dataHora(c.aberto_em)} />
          <Dado rotulo={`Prazo do diagnóstico (${c.prazo_horas} h corridas)`} valor={dataHora(c.prazo_em)} />
          <Dado rotulo="Diagnóstico em"
            valor={c.diagnosticado_em ? (
              <span className="dado-diagnostico">
                {dataHora(c.diagnosticado_em)}
                {c.prazo.horas_ate_diagnostico !== null && (
                  <span className="dado-extra"> · {horas(c.prazo.horas_ate_diagnostico)} após a abertura</span>
                )}
              </span>
            ) : <a href="#diagnostico" className="link-forte">Aguardando</a>} />
          {c.execucao_horas !== null && (
            <Dado rotulo="Em execução desde o diagnóstico" valor={horas(c.execucao_horas)} />
          )}
          {c.concluido_em && <Dado rotulo="Concluído em" valor={dataHora(c.concluido_em)} />}
          {c.solucao_horas_corridas !== null && (
            <Dado rotulo="Tempo de solução após o diagnóstico" valor={<strong>{horas(c.solucao_horas_corridas)}</strong>} />
          )}
          {c.cancelado_em && <Dado rotulo="Cancelado em" valor={dataHora(c.cancelado_em)} />}
        </dl>
        <h3 className="titulo-descricao">Descrição do problema</h3>
        <p className="texto-livre">{c.descricao}</p>
      </section>

      <SecaoDiagnostico chamado={c} aoSalvar={atualizar} />

      {(c.oficios.length > 0 || c.pode_solicitar_pecas) && (
        <section className="painel-bloco">
          <div className="bloco-topo">
            <div>
              <h2>Peças e equipamentos</h2>
              <small className="texto-suave">
                Ofícios do Planner de Ofícios ligados a este chamado: solicitações novas e ofícios que já existiam.
              </small>
            </div>
            {c.pode_solicitar_pecas && (
              <div className="grupo">
                <button className="btn btn-secundario" onClick={() => setJanela("vincular")}>
                  <Link2 size={17} /> Vincular ofício existente
                </button>
                <button className="btn btn-secundario" onClick={() => setJanela("pecas")}>
                  <PackagePlus size={17} /> Solicitar peças ou equipamentos
                </button>
              </div>
            )}
          </div>
          {c.oficios.length === 0 ? (
            <p className="texto-suave">Nenhum ofício ligado a este chamado.</p>
          ) : (
            <ul className="oficios-chamado">
              {c.oficios.map((o) => (
                <li key={o.id} className="cartao">
                  <div className="oficio-chamado-topo">
                    <strong>Ofício nº {o.numero}</strong>
                    <StatusBadge status={o.status} />
                  </div>
                  <small className="texto-suave">
                    {o.tipo_nome} · {data(o.data_oficio)}
                    {o.protocolo && ` · protocolo ${o.protocolo}`}
                    {o.dono_nome && ` · de ${o.dono_nome}`}
                  </small>
                  <small className="texto-suave">
                    {o.data_resposta ? `Resposta em ${data(o.data_resposta)}` : "Aguardando resposta"}
                    {o.data_recebimento ? ` · entregue em ${data(o.data_recebimento)}` : o.data_resposta ? " · aguardando entrega" : ""}
                  </small>
                  {/* Os documentos são anexados no Planner e aparecem aqui */}
                  {o.anexos.length > 0 ? (
                    <ul className="anexos-oficio">
                      {o.anexos.map((a) => <AnexoDoOficio key={a.id} chamadoId={c.id} anexo={a} />)}
                    </ul>
                  ) : (
                    <small className="texto-suave">Nenhum documento anexado no Planner ainda.</small>
                  )}
                  {temAcessoPlanner && (o.dono_id === usuario?.id || ehAdminPlanner) && (
                    <Link to={`/oficios/${o.id}`} className="link-forte">
                      {o.anexos.some((a) => a.tipo === "OFICIO") ? "Abrir no Planner de Ofícios" : "Anexar o documento no Planner de Ofícios"}
                    </Link>
                  )}
                  {o.pode_desvincular && (
                    <button className="btn btn-fantasma btn-pequeno btn-desvincular" onClick={() => setDesvincular(o)}>
                      <Unlink size={15} /> Desvincular do chamado
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="painel-bloco">
        <h2>Atendimento</h2>
        <ol className="linha-tempo">
          {c.interacoes.map((i) => <ItemLinhaTempo key={i.id} i={i} />)}
        </ol>
        {c.pode_comentar && <Responder chamado={c} aoSalvar={atualizar} />}
      </section>

      {janela === "pecas" && <ModalPecas chamado={c} aoFechar={() => setJanela(null)} aoSalvar={atualizar} />}
      {janela === "vincular" && <ModalVincular chamado={c} aoFechar={() => setJanela(null)} aoSalvar={atualizarOficios} />}
      {desvincular && (
        <ModalDesvincular chamado={c} oficio={desvincular} aoFechar={() => setDesvincular(null)} aoSalvar={atualizarOficios} />
      )}
      {janela === "concluir" && (
        <ModalTexto titulo="Concluir chamado" rotulo="Resumo da solução" obrigatorio={false} botao="Concluir"
          acao={(t) => concluirChamado(id, t)} aoFechar={() => setJanela(null)} aoSalvar={atualizar} />
      )}
      {janela === "reabrir" && (
        <ModalTexto titulo="Reabrir chamado" rotulo="Motivo da reabertura *" obrigatorio botao="Reabrir"
          acao={(t) => reabrirChamado(id, t)} aoFechar={() => setJanela(null)} aoSalvar={atualizar} />
      )}
      {janela === "cancelar" && (
        <ModalTexto titulo="Cancelar chamado" rotulo="Motivo do cancelamento *" obrigatorio botao="Cancelar chamado"
          acao={(t) => cancelarChamado(id, t)} aoFechar={() => setJanela(null)} aoSalvar={atualizar} perigo />
      )}
    </>
  );
}

const ICONE: Partial<Record<Interacao["tipo"], ReactNode>> = {
  COMENTARIO: <MessageSquare size={16} />,
  DIAGNOSTICO: <Stethoscope size={16} />,
  RELATORIO: <ClipboardList size={16} />,
  CONCLUSAO: <CheckCircle2 size={16} />,
  REABERTURA: <RotateCcw size={16} />,
  CANCELAMENTO: <XCircle size={16} />,
  ASSUMIDO: <Hand size={16} />,
  OFICIO: <PackagePlus size={16} />,
  CORRECAO: <PencilLine size={16} />,
};

function ItemLinhaTempo({ i }: { i: Interacao }) {
  const [abrirRelatorio, setAbrirRelatorio] = useState(false);
  return (
    <li className={`evento evento-${i.tipo}`}>
      <span className="evento-icone" aria-hidden>{ICONE[i.tipo] ?? <FileText size={16} />}</span>
      <div className="evento-corpo">
        <div className="evento-topo">
          <strong>{ROTULO_INTERACAO[i.tipo]}</strong>
          <small className="texto-suave">
            {i.autor?.nome ?? "Sistema"}
            {i.autor_papel && ` · ${ROTULO_PAPEL_MANUTENCAO[i.autor_papel]}`} · {dataHora(i.criado_em)}
          </small>
        </div>
        {i.ocorrido_em && Math.abs(new Date(i.ocorrido_em).getTime() - new Date(i.criado_em).getTime()) >= 60_000 && (
          <small className="evento-ocorrido">
            <CalendarClock size={13} aria-hidden />
            {i.tipo === "RELATORIO" ? "Atendimento" : "Diagnóstico"} em {dataHora(i.ocorrido_em)}
          </small>
        )}
        {i.texto && <p className="texto-livre">{i.texto}</p>}
        {i.arquivo_nome && <ArquivoExterno i={i} />}
        {i.relatorio && (
          <div className="relatorio-resumo">
            <div className="grupo">
              <button className="btn btn-secundario btn-pequeno" onClick={() => setAbrirRelatorio((v) => !v)}>
                <ClipboardList size={15} /> {abrirRelatorio ? "Esconder" : "Ver"} relatório {i.relatorio.codigo}
              </button>
              <BotaoPdf relatorio={i.relatorio} />
            </div>
            {abrirRelatorio && <VisaoRelatorio r={i.relatorio} />}
          </div>
        )}
      </div>
    </li>
  );
}

const ROTULO_ANEXO: Record<AnexoOficio["tipo"], string> = {
  OFICIO: "Documento do ofício",
  REFERENCIA: "Documento de referência",
  RESPOSTA: "Evidência da resposta",
  RECEBIMENTO: "Comprovante de entrega",
};

function AnexoDoOficio({ chamadoId, anexo }: { chamadoId: number; anexo: AnexoOficio }) {
  const avisar = useToast();
  const baixar = useMutation({
    mutationFn: () => baixarAnexoOficio(chamadoId, anexo),
    onSuccess: (blob) => salvarArquivo(blob, anexo.nome_original),
    onError: (e) => avisar(e.message),
  });
  return (
    <li>
      <button className="arquivo-escolhido arquivo-baixar" onClick={() => baixar.mutate()} disabled={baixar.isPending}
        title={`Enviado em ${dataHora(anexo.enviado_em)}`}>
        <Download size={15} />
        <span className="arquivo-nome">
          <small className="texto-suave">{ROTULO_ANEXO[anexo.tipo]}</small> {anexo.nome_original}
        </span>
        <small className="texto-suave">{tamanho(anexo.tamanho_bytes)}</small>
      </button>
    </li>
  );
}

/** Caixa de comentário (todos), com arquivo opcional. O diagnóstico é registrado na seção Diagnóstico técnico. */
function Responder({ chamado, aoSalvar }: { chamado: Detalhe; aoSalvar: (c: Detalhe) => void }) {
  const avisar = useToast();
  const [texto, setTexto] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const enviar = useMutation({
    mutationFn: () => responderChamado(chamado.id, { texto: texto.trim(), arquivo }),
    onSuccess: (c) => {
      setTexto("");
      setArquivo(null);
      aoSalvar(c);
      avisar("Comentário enviado.");
    },
  });

  function submeter(e: FormEvent) {
    e.preventDefault();
    if (!texto.trim() && !arquivo) return;
    enviar.mutate();
  }

  return (
    <form className="responder formulario" onSubmit={submeter}>
      <Campo rotulo="Comentário"
        dica={chamado.pode_responder ? "Para registrar o diagnóstico ou o relatório externo, use a seção Diagnóstico técnico." : undefined}>
        {(id) => <textarea id={id} className="input" rows={3} maxLength={10000} value={texto}
          onChange={(e) => setTexto(e.target.value)} placeholder="Escreva uma mensagem" />}
      </Campo>
      <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} rotulo="Anexar arquivo (opcional)" compacto />
      {enviar.isError && <div className="alerta-erro">{enviar.error.message}</div>}
      <div className="acoes-form">
        <Botao type="submit" carregando={enviar.isPending} disabled={!texto.trim() && !arquivo}>
          <MessageSquare size={16} /> Enviar
        </Botao>
      </div>
    </form>
  );
}

function ModalTexto({ titulo, rotulo, obrigatorio, botao, acao, aoFechar, aoSalvar, perigo }: {
  titulo: string; rotulo: string; obrigatorio: boolean; botao: string; perigo?: boolean;
  acao: (texto: string) => Promise<Detalhe>; aoFechar: () => void; aoSalvar: (c: Detalhe) => void;
}) {
  const [texto, setTexto] = useState("");
  const salvar = useMutation({
    mutationFn: () => acao(texto.trim()),
    onSuccess: (c) => {
      aoSalvar(c);
      aoFechar();
    },
  });
  return (
    <Modal titulo={titulo} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <Campo rotulo={rotulo}>
          {(id) => <textarea id={id} className="input" rows={4} autoFocus required={obrigatorio}
            minLength={obrigatorio ? 3 : undefined} maxLength={5000} value={texto} onChange={(e) => setTexto(e.target.value)} />}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao type="submit" className={`btn ${perigo ? "btn-perigo" : "btn-primario"}`} carregando={salvar.isPending}>{botao}</Botao>
        </div>
      </form>
    </Modal>
  );
}

/** Solicitação de peças ou equipamentos: vira um ofício no Planner de Ofícios, ligado a este chamado. */
function ModalPecas({ chamado, aoFechar, aoSalvar }: {
  chamado: Detalhe; aoFechar: () => void; aoSalvar: (c: Detalhe) => void;
}) {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const tipos = useQuery({ queryKey: ["tipos-solicitacao"], queryFn: tiposSolicitacao });
  const [tipo, setTipo] = useState("PECAS_MANUTENCAO");
  const [numero, setNumero] = useState("");
  const [dataOficio, setDataOficio] = useState(hojeIso());
  const [protocolo, setProtocolo] = useState("");
  const [destino, setDestino] = useState<Destinatario | "">("");
  const [setor, setSetor] = useState("");
  const [itens, setItens] = useState(chamado.equipamento ? `Para o equipamento ${chamado.equipamento}: ` : "");
  const salvar = useMutation({
    mutationFn: () => solicitarPecas(chamado.id, {
      tipo, numero: numero.trim(), data_oficio: dataOficio, protocolo: protocolo.trim() || null,
      destinatario_tipo: destino || null, destinatario_setor: destino ? setor.trim() || null : null, itens: itens.trim(),
    }),
    onSuccess: (c) => {
      aoSalvar(c);
      queryClient.invalidateQueries({ queryKey: ["oficios"] });
      queryClient.invalidateQueries({ queryKey: ["manutencao-quadro"] });
      avisar(`Ofício nº ${numero.trim()} registrado no Planner. Anexe o documento do ofício lá.`);
      aoFechar();
    },
  });
  return (
    <Modal titulo={`Solicitar peças ou equipamentos · ${chamado.codigo}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <p className="texto-suave">
          A solicitação vira um ofício no <strong>Planner de Ofícios</strong>, com o prazo de resposta e de entrega de lá.
          Depois, <strong>anexe o documento do ofício no Planner</strong>: documentos, resposta e entrega aparecem aqui no
          chamado, que fica em "Aguardando peças" até a entrega.
        </p>
        <div className="grade-2">
          <Campo rotulo="Tipo *">
            {(id) => (
              <select id={id} className="input" required value={tipo} onChange={(e) => setTipo(e.target.value)}>
                {(tipos.data ?? []).map((t) => <option key={t.codigo} value={t.codigo}>{t.nome}</option>)}
              </select>
            )}
          </Campo>
          <Campo rotulo="Nº do ofício *">
            {(id) => <input id={id} className="input" required maxLength={30} autoFocus value={numero}
              onChange={(e) => setNumero(e.target.value)} />}
          </Campo>
          <Campo rotulo="Data do ofício *">
            {(id) => <input id={id} className="input" type="date" required max={hojeIso()} value={dataOficio}
              onChange={(e) => setDataOficio(e.target.value)} />}
          </Campo>
          <Campo rotulo="Protocolo">
            {(id) => <input id={id} className="input" maxLength={50} value={protocolo} onChange={(e) => setProtocolo(e.target.value)} />}
          </Campo>
          <Campo rotulo="Destinatário">
            {(id) => (
              <select id={id} className="input" value={destino} onChange={(e) => setDestino(e.target.value as Destinatario | "")}>
                <option value="">Não informado</option>
                {Object.entries(ROTULO_DESTINATARIO).map(([k, r]) => <option key={k} value={k}>{r}</option>)}
              </select>
            )}
          </Campo>
          {destino && (
            <Campo rotulo={destino === "OUTROS" ? "Destino *" : "Setor *"}>
              {(id) => <input id={id} className="input" required maxLength={120} value={setor} onChange={(e) => setSetor(e.target.value)} />}
            </Campo>
          )}
        </div>
        <Campo rotulo="Peças ou equipamentos solicitados *" dica="Quantidade, descrição, modelo. Vai para a observação do ofício.">
          {(id) => <textarea id={id} className="input" rows={4} required minLength={3} maxLength={4000} value={itens}
            onChange={(e) => setItens(e.target.value)} />}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Registrar no Planner</Botao>
        </div>
      </form>
    </Modal>
  );
}

/** Vincula ao chamado um ofício que já existe no Planner (os que o usuário vê lá e ainda não têm chamado). */
function ModalVincular({ chamado, aoFechar, aoSalvar }: {
  chamado: Detalhe; aoFechar: () => void; aoSalvar: (c: Detalhe) => void;
}) {
  const avisar = useToast();
  const [texto, setTexto] = useState("");
  const [busca, setBusca] = useState("");
  // busca com uma pequena espera enquanto digita
  useEffect(() => {
    const t = setTimeout(() => setBusca(texto.trim()), 350);
    return () => clearTimeout(t);
  }, [texto]);
  const consulta = useQuery({
    queryKey: ["oficios-disponiveis", busca], queryFn: () => oficiosDisponiveis(busca), placeholderData: keepPreviousData,
  });
  const vincular = useMutation({
    mutationFn: (oficioId: number) => vincularOficio(chamado.id, oficioId),
    onSuccess: (c, oficioId) => {
      const numero = c.oficios.find((o) => o.id === oficioId)?.numero;
      aoSalvar(c);
      avisar(`Ofício nº ${numero ?? ""} vinculado ao chamado ${chamado.codigo}.`);
      aoFechar();
    },
  });
  const itens = consulta.data ?? [];
  return (
    <Modal titulo={`Vincular ofício existente · ${chamado.codigo}`} aoFechar={aoFechar}>
      <div className="formulario">
        <p className="texto-suave">
          Escolha um ofício <strong>já cadastrado no Planner de Ofícios</strong>. Os documentos, a resposta e a entrega
          registrados lá passam a aparecer neste chamado. Cada ofício fica ligado a um chamado só.
        </p>
        <Campo rotulo="Buscar ofício" dica="Número, protocolo, setor ou um trecho da observação.">
          {(id) => (
            <div className="busca-vincular">
              <Search size={16} aria-hidden />
              <input id={id} className="input" type="search" autoFocus maxLength={80} value={texto}
                onChange={(e) => setTexto(e.target.value)} placeholder="Ex.: 45 ou fonte 12V" />
            </div>
          )}
        </Campo>
        {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : itens.length === 0 ? (
          <p className="texto-suave">
            {busca
              ? "Nenhum ofício disponível com essa busca."
              : "Nenhum ofício disponível: os seus ofícios do Planner já estão ligados a um chamado, ou ainda não há ofícios."}
          </p>
        ) : (
          <ul className="lista-vincular" aria-label="Ofícios disponíveis">
            {itens.map((o) => (
              <li key={o.id}>
                <div className="vincular-dados">
                  <div className="oficio-chamado-topo">
                    <strong>Ofício nº {o.numero}</strong>
                    <StatusBadge status={o.status} curto />
                  </div>
                  <small className="texto-suave">
                    {o.tipo_nome ?? "Sem tipo"} · {data(o.data_oficio)}
                    {o.protocolo && ` · protocolo ${o.protocolo}`}
                    {o.dono_nome && ` · de ${o.dono_nome}`}
                  </small>
                  {o.observacao && <small className="texto-suave vincular-obs">{o.observacao}</small>}
                </div>
                <Botao className="btn btn-secundario btn-pequeno" carregando={vincular.isPending && vincular.variables === o.id}
                  disabled={vincular.isPending} onClick={() => vincular.mutate(o.id)}>
                  <Link2 size={15} /> Vincular
                </Botao>
              </li>
            ))}
          </ul>
        )}
        {itens.length === 20 && <small className="texto-suave">Mostrando os 20 mais recentes. Use a busca para achar outros.</small>}
        {vincular.isError && <div className="alerta-erro">{vincular.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Fechar</button>
        </div>
      </div>
    </Modal>
  );
}

function ModalDesvincular({ chamado, oficio, aoFechar, aoSalvar }: {
  chamado: Detalhe; oficio: OficioVinculado; aoFechar: () => void; aoSalvar: (c: Detalhe) => void;
}) {
  const avisar = useToast();
  const desfazer = useMutation({
    mutationFn: () => desvincularOficio(chamado.id, oficio.id),
    onSuccess: (c) => {
      aoSalvar(c);
      avisar(`Ofício nº ${oficio.numero} desvinculado do chamado.`);
      aoFechar();
    },
  });
  return (
    <Modal titulo={`Desvincular o ofício nº ${oficio.numero}`} aoFechar={aoFechar}>
      <div className="formulario">
        <p>
          O ofício deixa de aparecer no chamado <strong>{chamado.codigo}</strong> e de contar em "Aguardando peças".
          Ele <strong>continua no Planner de Ofícios</strong>, com os documentos e o andamento, e pode ser vinculado de novo.
        </p>
        {desfazer.isError && <div className="alerta-erro">{desfazer.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao className="btn btn-perigo" carregando={desfazer.isPending} onClick={() => desfazer.mutate()}>
            <Unlink size={16} /> Desvincular
          </Botao>
        </div>
      </div>
    </Modal>
  );
}

