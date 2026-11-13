import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, CheckCircle2, ClipboardList, Download, FileText, Hand, MessageSquare, PackagePlus, RotateCcw, Stethoscope,
  XCircle,
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  assumirChamado, baixarAnexoOficio, baixarArquivoInteracao, baixarRelatorioPdf, cancelarChamado, concluirChamado, criarRelatorio,
  reabrirChamado, responderChamado, solicitarPecas, tiposSolicitacao, verChamado, type RelatorioForm,
} from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal, StatusBadge } from "../../components/ui";
import type {
  AnexoOficio, ChamadoDetalhe as Detalhe, Destinatario, Interacao, RelatorioTecnico, SituacaoEquipamento,
} from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { data, dataHora, hojeIso, ROTULO_DESTINATARIO, tamanho } from "../../utils/formato";
import { agoraLocal, horas, ROTULO_EQUIPAMENTO, ROTULO_INTERACAO, ROTULO_PAPEL_MANUTENCAO } from "../../utils/manutencao";
import { Dado } from "../oficio/Dados";
import { BadgePrazo, BadgeStatusChamado } from "./comum";

type Janela = "relatorio" | "concluir" | "reabrir" | "cancelar" | "pecas" | null;

export function ChamadoDetalhe() {
  const id = Number(useParams().id);
  const queryClient = useQueryClient();
  const { modulos, usuario, ehAdmin: ehAdminPlanner } = useAuth();
  const temAcessoPlanner = modulos.includes("OFICIOS");
  // O que é feito no Planner (documentos, resposta, entrega) aparece aqui: atualiza sozinho a cada 30 s
  const consulta = useQuery({ queryKey: ["chamado", id], queryFn: () => verChamado(id), refetchInterval: 30_000 });
  const [janela, setJanela] = useState<Janela>(null);

  const atualizar = (c: Detalhe) => {
    queryClient.setQueryData(["chamado", id], c);
    queryClient.invalidateQueries({ queryKey: ["chamados"] });
    queryClient.invalidateQueries({ queryKey: ["manutencao-painel"] });
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
          {c.pode_responder && (
            <button className="btn btn-secundario" onClick={() => setJanela("relatorio")}>
              <ClipboardList size={17} /> Relatório técnico
            </button>
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
          <Dado rotulo={`Prazo do diagnóstico (${c.prazo_horas} h úteis)`} valor={dataHora(c.prazo_em)} />
          <Dado rotulo="Diagnóstico em"
            valor={c.diagnosticado_em
              ? `${dataHora(c.diagnosticado_em)}${c.prazo.horas_ate_diagnostico !== null ? ` · ${horas(c.prazo.horas_ate_diagnostico)} úteis` : ""}`
              : "Aguardando"} />
          {c.execucao_horas_uteis !== null && (
            <Dado rotulo="Em execução desde o diagnóstico" valor={`${horas(c.execucao_horas_uteis)} úteis`} />
          )}
          {c.concluido_em && <Dado rotulo="Concluído em" valor={dataHora(c.concluido_em)} />}
          {c.solucao_horas_uteis !== null && (
            <Dado rotulo="Tempo de solução após o diagnóstico"
              valor={<><strong>{horas(c.solucao_horas_uteis)} úteis</strong>
                {c.solucao_horas_corridas !== null && (
                  <span className="dado-extra"> · {horas(c.solucao_horas_corridas)} corridas</span>
                )}</>} />
          )}
          {c.cancelado_em && <Dado rotulo="Cancelado em" valor={dataHora(c.cancelado_em)} />}
        </dl>
        <h3 className="titulo-descricao">Descrição do problema</h3>
        <p className="texto-livre">{c.descricao}</p>
      </section>

      {(c.oficios.length > 0 || c.pode_solicitar_pecas) && (
        <section className="painel-bloco">
          <div className="bloco-topo">
            <div>
              <h2>Peças e equipamentos</h2>
              <small className="texto-suave">Solicitações registradas como ofício no Planner de Ofícios.</small>
            </div>
            {c.pode_solicitar_pecas && (
              <button className="btn btn-secundario" onClick={() => setJanela("pecas")}>
                <PackagePlus size={17} /> Solicitar peças ou equipamentos
              </button>
            )}
          </div>
          {c.oficios.length === 0 ? (
            <p className="texto-suave">Nenhuma solicitação para este chamado.</p>
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
                    {o.dono_nome && ` · solicitado por ${o.dono_nome}`}
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

      {janela === "relatorio" && <ModalRelatorio chamado={c} aoFechar={() => setJanela(null)} aoSalvar={atualizar} />}
      {janela === "pecas" && <ModalPecas chamado={c} aoFechar={() => setJanela(null)} aoSalvar={atualizar} />}
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
};

function ItemLinhaTempo({ i }: { i: Interacao }) {
  const avisar = useToast();
  const [abrirRelatorio, setAbrirRelatorio] = useState(false);
  const baixar = useMutation({
    mutationFn: () => baixarArquivoInteracao(i),
    onSuccess: (blob) => salvarArquivo(blob, i.arquivo_nome ?? "arquivo"),
    onError: (e) => avisar(e.message),
  });
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
        {i.texto && <p className="texto-livre">{i.texto}</p>}
        {i.arquivo_nome && (
          <button className="arquivo-escolhido arquivo-baixar" onClick={() => baixar.mutate()} disabled={baixar.isPending}>
            <Download size={16} />
            <span className="arquivo-nome">{i.arquivo_nome}</span>
            {i.arquivo_tamanho !== null && <small className="texto-suave">{tamanho(i.arquivo_tamanho)}</small>}
          </button>
        )}
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

function BotaoPdf({ relatorio }: { relatorio: RelatorioTecnico }) {
  const avisar = useToast();
  const pdf = useMutation({
    mutationFn: () => baixarRelatorioPdf(relatorio.id),
    onSuccess: (blob) => salvarArquivo(blob, `relatorio-${relatorio.codigo}.pdf`),
    onError: (e) => avisar(e.message),
  });
  return (
    <Botao className="btn btn-fantasma btn-pequeno" carregando={pdf.isPending} onClick={() => pdf.mutate()}>
      <Download size={15} /> PDF
    </Botao>
  );
}

function VisaoRelatorio({ r }: { r: RelatorioTecnico }) {
  const blocos: [string, string | null][] = [
    ["Diagnóstico", r.diagnostico],
    ["Causa provável", r.causa],
    ["Serviço executado", r.servico_executado],
    ["Peças e materiais", r.pecas],
    ["Recomendações", r.recomendacoes],
  ];
  return (
    <div className="relatorio-visao">
      <dl className="dados dados-chamado">
        <Dado rotulo="Técnico" valor={`${r.tecnico?.nome ?? "—"} · ${r.empresa.nome}`} />
        <Dado rotulo="Atendido em" valor={dataHora(r.atendido_em)} />
        <Dado rotulo="Equipamento" valor={r.equipamento ?? "—"} />
        <Dado rotulo="Patrimônio / nº de série" valor={r.identificacao ?? "—"} />
        <Dado rotulo="Situação do equipamento" valor={ROTULO_EQUIPAMENTO[r.situacao_equipamento]} />
      </dl>
      {blocos.filter(([, v]) => v).map(([t, v]) => (
        <div key={t}>
          <h4>{t}</h4>
          <p className="texto-livre">{v}</p>
        </div>
      ))}
    </div>
  );
}

/** Caixa de resposta: comentário (todos) ou resposta técnica (técnico/admin), com arquivo opcional. */
function Responder({ chamado, aoSalvar }: { chamado: Detalhe; aoSalvar: (c: Detalhe) => void }) {
  const avisar = useToast();
  const [texto, setTexto] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [tecnica, setTecnica] = useState(chamado.pode_responder && !chamado.diagnosticado_em);
  const enviar = useMutation({
    mutationFn: () => responderChamado(chamado.id, { texto: texto.trim(), arquivo, diagnostico: tecnica && chamado.pode_responder }),
    onSuccess: (c) => {
      setTexto("");
      setArquivo(null);
      setTecnica(false);
      aoSalvar(c);
      avisar(tecnica ? "Resposta técnica registrada." : "Comentário enviado.");
    },
  });

  function submeter(e: FormEvent) {
    e.preventDefault();
    if (!texto.trim() && !arquivo) return;
    enviar.mutate();
  }

  return (
    <form className="responder formulario" onSubmit={submeter}>
      <Campo rotulo={tecnica ? "Resposta técnica (diagnóstico)" : "Comentário"}
        dica={tecnica
          ? "Descreva o diagnóstico ou anexe o relatório externo da empresa. A primeira resposta técnica encerra o prazo."
          : undefined}>
        {(id) => <textarea id={id} className="input" rows={3} maxLength={10000} value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder={tecnica ? "Ex.: Fonte de alimentação queimada; substituição necessária." : "Escreva uma mensagem"} />}
      </Campo>
      <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo}
        rotulo={tecnica ? "Anexar relatório externo (opcional)" : "Anexar arquivo (opcional)"} compacto />
      {chamado.pode_responder && (
        <label className="checkbox">
          <input type="checkbox" checked={tecnica} onChange={(e) => setTecnica(e.target.checked)} />
          É uma resposta técnica (diagnóstico do problema)
        </label>
      )}
      {enviar.isError && <div className="alerta-erro">{enviar.error.message}</div>}
      <div className="acoes-form">
        <Botao type="submit" carregando={enviar.isPending} disabled={!texto.trim() && !arquivo}>
          {tecnica ? <><Stethoscope size={16} /> Registrar resposta técnica</> : <><MessageSquare size={16} /> Enviar</>}
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

const VAZIO: RelatorioForm = {
  equipamento: null, identificacao: null, diagnostico: "", causa: null, servico_executado: null, pecas: null,
  situacao_equipamento: "NAO_SE_APLICA", recomendacoes: null,
};

/** Relatório técnico no modelo do sistema (vira PDF). */
function ModalRelatorio({ chamado, aoFechar, aoSalvar }: {
  chamado: Detalhe; aoFechar: () => void; aoSalvar: (c: Detalhe) => void;
}) {
  const avisar = useToast();
  const [f, setF] = useState<RelatorioForm>({ ...VAZIO, equipamento: chamado.equipamento, atendido_em: agoraLocal() });
  const campo = (k: keyof RelatorioForm) => (e: { target: { value: string } }) =>
    setF((v) => ({ ...v, [k]: e.target.value || null }));
  const salvar = useMutation({
    mutationFn: () => criarRelatorio(chamado.id, { ...f, diagnostico: f.diagnostico?.trim() ?? "" }),
    onSuccess: (c) => {
      aoSalvar(c);
      avisar("Relatório técnico registrado. Baixe o PDF na linha do tempo.");
      aoFechar();
    },
  });
  return (
    <Modal titulo={`Relatório técnico · ${chamado.codigo}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <div className="grade-2">
          <Campo rotulo="Data e hora do atendimento *">
            {(id) => <input id={id} className="input" type="datetime-local" required max={agoraLocal()}
              value={f.atendido_em ?? ""} onChange={campo("atendido_em")} />}
          </Campo>
          <Campo rotulo="Situação do equipamento">
            {(id) => (
              <select id={id} className="input" value={f.situacao_equipamento}
                onChange={(e) => setF((v) => ({ ...v, situacao_equipamento: e.target.value as SituacaoEquipamento }))}>
                {Object.entries(ROTULO_EQUIPAMENTO).map(([k, r]) => <option key={k} value={k}>{r}</option>)}
              </select>
            )}
          </Campo>
          <Campo rotulo="Equipamento">
            {(id) => <input id={id} className="input" maxLength={120} value={f.equipamento ?? ""} onChange={campo("equipamento")} />}
          </Campo>
          <Campo rotulo="Patrimônio / nº de série">
            {(id) => <input id={id} className="input" maxLength={120} value={f.identificacao ?? ""} onChange={campo("identificacao")} />}
          </Campo>
        </div>
        <Campo rotulo="Diagnóstico *">
          {(id) => <textarea id={id} className="input" rows={3} required minLength={5} maxLength={10000}
            value={f.diagnostico} onChange={(e) => setF((v) => ({ ...v, diagnostico: e.target.value }))} />}
        </Campo>
        <Campo rotulo="Causa provável">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={5000} value={f.causa ?? ""} onChange={campo("causa")} />}
        </Campo>
        <Campo rotulo="Serviço executado">
          {(id) => <textarea id={id} className="input" rows={3} maxLength={10000} value={f.servico_executado ?? ""}
            onChange={campo("servico_executado")} />}
        </Campo>
        <Campo rotulo="Peças e materiais">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={5000} value={f.pecas ?? ""} onChange={campo("pecas")} />}
        </Campo>
        <Campo rotulo="Recomendações">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={5000} value={f.recomendacoes ?? ""}
            onChange={campo("recomendacoes")} />}
        </Campo>
        <p className="texto-suave">O relatório conta como diagnóstico do chamado e gera um PDF com o modelo do sistema.</p>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Registrar relatório</Botao>
        </div>
      </form>
    </Modal>
  );
}
