// Tela de um ofício: cabeçalho com ações, prazo, dados, documentos, histórico e auditoria.
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, PackageCheck, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import * as ep from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { AlertaBadge, Carregando, ErroBox, StatusBadge } from "../../components/ui";
import { ModalDecisao } from "../Exclusoes";
import { data, dataHora, destinatarioTexto, diasUteis } from "../../utils/formato";
import { useTipos } from "../../utils/tipos";
import { ConteudoEvidencia, LixeiraDoOficio, SlotAnexo } from "./Anexos";
import { BlocoDados, Dado, DataComDias, BarraPrazo } from "./Dados";
import { LinhaDoTempo, RegistroAlteracoes } from "./Historico";
import { ModalCorrigirResposta, ModalCorrigirRecebimento, ModalDesfazer } from "./ModaisCorrecao";
import { ModalEditar, ModalExcluir, AvisoExclusao, ModalPedirExclusao } from "./ModaisOficio";
import { ModalResposta, ModalRecebimento, ModalReabrir } from "./ModaisResposta";
import { type Correcoes, type ModalAberto, ativo, ehResposta, recebimentoAtual, respostaAtual } from "./comum";

export function OficioDetalhe() {
  const id = Number(useParams().id);
  const { ehAdmin } = useAuth();
  const navegar = useNavigate();
  const [modal, setModal] = useState<ModalAberto>(null);
  const consulta = useQuery({ queryKey: ["oficio", id], queryFn: () => ep.buscarOficio(id) });
  const prazos = useQuery({ queryKey: ["prazos"], queryFn: ep.prazos, staleTime: Infinity });
  const tipos = useTipos();

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  const o = consulta.data;

  // Quem enxerga o ofício (dono ou admin) pode fazer tudo nele; só CONFIRMADO e RECEBIDO são finais
  // e a exclusão, para clientes, depende de um admin.
  const podeEditar = true;
  const podeEvidencia = true;
  const pedido = o.exclusao_pendente;
  const reaberto = o.historico.some((h) => h.status_anterior !== null && h.status_novo === "PENDENTE_RESPOSTA");
  const ultimaResposta = [...o.historico].reverse().find((h) => ativo(h) && ehResposta(h));
  const ultimoRecebimento = recebimentoAtual(o);
  const resposta = respostaAtual(o);
  const correcoes: Correcoes | null = ehAdmin
    ? {
        respostaId: resposta?.id,
        recebimentoId: ultimoRecebimento?.id,
        desfazerId: (ultimoRecebimento ?? resposta)?.id,
        abrir: setModal,
      }
    : null;
  const itens = tipos.exigeEntrega(o.tipo);
  const pendente = o.status === "PENDENTE_RESPOSTA" || o.status === "PENDENTE_RECEBIMENTO";
  const slotsEvidencia = (ultimaResposta ? 1 : 0) + (ultimoRecebimento || o.status === "PENDENTE_RECEBIMENTO" ? 1 : 0);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/oficios" className="link voltar">
            <ArrowLeft size={16} /> Ofícios
          </Link>
          <h1>Ofício nº {o.numero}</h1>
          <div className="grupo">
            <StatusBadge status={o.status} />
            {o.nivel_alerta && <AlertaBadge nivel={o.nivel_alerta} />}
            <span className="badge badge-neutro">{tipos.rotulo(o.tipo)}</span>
          </div>
        </div>
        <div className="grupo acoes-topo">
          {o.status === "PENDENTE_RESPOSTA" && (
            <button className="btn btn-primario" onClick={() => setModal("resposta")}>
              <CheckCircle2 size={18} /> Registrar resposta
            </button>
          )}
          {o.status === "PENDENTE_RECEBIMENTO" && (
            <button className="btn btn-primario" onClick={() => setModal("recebimento")}>
              <PackageCheck size={18} /> Confirmar recebimento
            </button>
          )}
          {o.status === "NAO_CONFIRMADO" && (
            <button className="btn btn-primario" onClick={() => setModal("reabrir")}>
              <RotateCcw size={18} /> Reabrir
            </button>
          )}
          {podeEditar && (
            <button className="btn btn-secundario" onClick={() => setModal("editar")}>
              <Pencil size={16} /> Editar
            </button>
          )}
          {ehAdmin ? (
            <button className="btn btn-perigo-suave" onClick={() => setModal("excluir")}>
              <Trash2 size={16} /> Excluir
            </button>
          ) : (
            !pedido && (
              <button className="btn btn-perigo-suave" onClick={() => setModal("pedir-exclusao")}>
                <Trash2 size={16} /> Solicitar exclusão
              </button>
            )
          )}
        </div>
      </header>

      {pedido && (
        <AvisoExclusao oficioId={o.id} pedido={pedido} ehAdmin={ehAdmin} podeCancelar={!ehAdmin}
          aoDecidir={(acao) => setModal(acao)} />
      )}

      {pendente && prazos.data && (
        <BarraPrazo dias={o.dias_uteis_decorridos} reaberto={reaberto} prazos={prazos.data}
          etapa={o.status === "PENDENTE_RECEBIMENTO" ? "recebimento" : "resposta"} />
      )}

      {/* Dados em três blocos, na ordem do caminho do ofício; campos sem valor não aparecem */}
      <section className="cartao">
        <div className="blocos-dados">
          <BlocoDados titulo="Identificação">
            <Dado rotulo="Data do ofício" valor={data(o.data_oficio)} />
            <Dado rotulo="Tipo" valor={tipos.rotulo(o.tipo)} />
            {destinatarioTexto(o) && <Dado rotulo="Destinatário" valor={destinatarioTexto(o)} />}
            {o.protocolo && <Dado rotulo="Protocolo" valor={o.protocolo} />}
            {ehAdmin && <Dado rotulo="Cliente" valor={o.dono.nome} />}
          </BlocoDados>
          <BlocoDados titulo="Resposta">
            <Dado
              rotulo={reaberto ? "Prazo reiniciado em" : "Início do prazo"}
              valor={data(o.inicio_prazo)}
            />
            {o.status === "PENDENTE_RESPOSTA" ? (
              <Dado rotulo="Aguardando resposta há" valor={diasUteis(o.dias_uteis_decorridos)} />
            ) : (
              o.data_resposta && (
                <Dado rotulo={o.status === "NAO_CONFIRMADO" ? "Respondido (não confirmado) em" : "Respondido em"}
                  valor={<DataComDias iso={o.data_resposta} dias={o.dias_resposta} />} />
              )
            )}
          </BlocoDados>
          {(itens || o.data_recebimento) && (
            <BlocoDados titulo="Entrega">
              {o.data_recebimento ? (
                <Dado rotulo="Entregue em" valor={<DataComDias iso={o.data_recebimento} dias={o.dias_entrega} />} />
              ) : o.status === "PENDENTE_RECEBIMENTO" ? (
                <Dado rotulo="Aguardando entrega há" valor={diasUteis(o.dias_uteis_decorridos)} />
              ) : (
                <p className="texto-suave">
                  {o.status === "NAO_CONFIRMADO"
                    ? "Sem entrega: a resposta não foi confirmada."
                    : "Começa quando a resposta for confirmada."}
                </p>
              )}
            </BlocoDados>
          )}
        </div>
        {o.observacao && (
          <div className="observacao">
            <span className="rotulo">Observação</span>
            <p>{o.observacao}</p>
          </div>
        )}
        <p className="dados-rodape texto-suave">
          Cadastrado em {dataHora(o.criado_em)} · atualizado em {dataHora(o.atualizado_em)}
        </p>
      </section>

      <section className="painel-bloco">
        <h2>Documentos</h2>
        <div className={slotsEvidencia === 1 ? "grade-3" : "grade-2"}>
          <SlotAnexo oficio={o} tipo="OFICIO" titulo="Documento do ofício" podeEditar={podeEditar} />
          <SlotAnexo oficio={o} tipo="REFERENCIA" titulo="Documento de referência" podeEditar={podeEditar} />
          {ultimaResposta && (
            <div className="cartao anexo anexo-evidencia">
              <span className="rotulo">
                Evidência da resposta{" "}
                <small className="texto-suave">
                  ({ultimaResposta.status_novo === "NAO_CONFIRMADO" ? "não confirmada" : "confirmada"} em{" "}
                  {data(ultimaResposta.data_resposta)})
                </small>
              </span>
              <ConteudoEvidencia oficioId={o.id} evento={ultimaResposta} tipo="RESPOSTA" podeEditar={podeEvidencia}
                podeRemover={ehAdmin} />
            </div>
          )}
          {ultimoRecebimento ? (
            <div className="cartao anexo anexo-entrega">
              <span className="rotulo">
                Evidência da entrega{" "}
                <small className="texto-suave">(recebido em {data(ultimoRecebimento.data_recebimento)})</small>
              </span>
              <ConteudoEvidencia oficioId={o.id} evento={ultimoRecebimento} tipo="RECEBIMENTO"
                podeEditar={podeEvidencia} podeRemover={ehAdmin} />
            </div>
          ) : (
            o.status === "PENDENTE_RECEBIMENTO" && (
              <div className="cartao anexo anexo-entrega">
                <span className="rotulo">Evidência da entrega</span>
                <p className="texto-suave">
                  Aguardando a entrega (dos itens ou do serviço). Anexe o comprovante (canhoto, termo de
                  recebimento, relatório do serviço, foto…) ao confirmar o recebimento.
                </p>
                <div className="grupo">
                  <button className="btn btn-secundario btn-pequeno" onClick={() => setModal("recebimento")}>
                    <PackageCheck size={15} /> Confirmar recebimento
                  </button>
                </div>
              </div>
            )
          )}
        </div>
        {ehAdmin && <LixeiraDoOficio oficioId={o.id} />}
      </section>

      <LinhaDoTempo oficioId={o.id} historico={o.historico} podeEvidencia={podeEvidencia} correcoes={correcoes} />

      <RegistroAlteracoes oficioId={o.id} />

      {modal === "resposta" && <ModalResposta oficio={o} aoFechar={() => setModal(null)} />}
      {modal === "recebimento" && <ModalRecebimento oficio={o} aoFechar={() => setModal(null)} />}
      {modal === "corrigir-resposta" && resposta && (
        <ModalCorrigirResposta oficio={o} evento={resposta} aoFechar={() => setModal(null)} />
      )}
      {modal === "corrigir-recebimento" && ultimoRecebimento && (
        <ModalCorrigirRecebimento oficio={o} evento={ultimoRecebimento} aoFechar={() => setModal(null)} />
      )}
      {modal === "desfazer" && <ModalDesfazer oficio={o} aoFechar={() => setModal(null)} />}
      {modal === "reabrir" && <ModalReabrir oficio={o} aoFechar={() => setModal(null)} />}
      {modal === "editar" && <ModalEditar oficio={o} aoFechar={() => setModal(null)} />}
      {modal === "excluir" && <ModalExcluir oficio={o} aoFechar={() => setModal(null)} />}
      {modal === "pedir-exclusao" && <ModalPedirExclusao oficio={o} aoFechar={() => setModal(null)} />}
      {(modal === "aprovar" || modal === "recusar") && pedido && (
        <ModalDecisao pedido={pedido} acao={modal} aoFechar={() => setModal(null)}
          aoConcluir={() => modal === "aprovar" && navegar("/oficios")} />
      )}
    </>
  );
}
