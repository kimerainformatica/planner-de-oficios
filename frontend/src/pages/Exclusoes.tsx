import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { aprovarExclusao, listarExclusoes, recusarExclusao } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal, Vazio } from "../components/ui";
import type { SolicitacaoExclusao, StatusSolicitacao } from "../types";
import { dataHora } from "../utils/formato";

const ROTULO: Record<StatusSolicitacao, string> = {
  PENDENTE: "Aguardando",
  APROVADA: "Aprovada · ofício excluído",
  RECUSADA: "Recusada",
  CANCELADA: "Cancelada",
};

export function Exclusoes() {
  const { ehAdmin } = useAuth();
  const [aba, setAba] = useState<"PENDENTE" | "TODAS">("PENDENTE");
  const [decidindo, setDecidindo] = useState<{ pedido: SolicitacaoExclusao; acao: "aprovar" | "recusar" } | null>(
    null,
  );
  const consulta = useQuery({
    queryKey: ["exclusoes", aba],
    queryFn: () => listarExclusoes(aba === "PENDENTE" ? "PENDENTE" : undefined),
  });

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Pedidos de exclusão</h1>
          <p className="texto-suave">
            {ehAdmin
              ? "Clientes não excluem ofícios diretamente: o pedido chega aqui para aprovação."
              : "Seus pedidos de exclusão e a decisão dos administradores."}
          </p>
        </div>
        <div className="segmentado" role="tablist">
          {(["PENDENTE", "TODAS"] as const).map((a) => (
            <button key={a} role="tab" aria-selected={aba === a} className={`segmento ${aba === a ? "ativo" : ""}`}
              onClick={() => setAba(a)}>
              {a === "PENDENTE" ? "Aguardando decisão" : "Todos"}
            </button>
          ))}
        </div>
      </header>

      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : consulta.data.length === 0 ? (
        <Vazio>{aba === "PENDENTE" ? "Nenhum pedido aguardando decisão." : "Nenhum pedido de exclusão."}</Vazio>
      ) : (
        <ul className="pedidos">
          {consulta.data.map((p) => (
            <li key={p.id} className={`cartao pedido pedido-${p.status}`}>
              <div className="pedido-topo">
                <div>
                  <strong>
                    {p.oficio_id ? <Link to={`/oficios/${p.oficio_id}`} className="link-forte">{p.referencia}</Link> : p.referencia}
                  </strong>
                  <small className="texto-suave">
                    Pedido por {p.solicitante_nome ?? "—"} em {dataHora(p.criado_em)}
                  </small>
                </div>
                <span className={`badge badge-pedido-${p.status}`}>{ROTULO[p.status]}</span>
              </div>
              <p className="pedido-motivo">
                <span className="rotulo">Motivo:</span> {p.motivo}
              </p>
              {p.status !== "PENDENTE" && p.decidido_em && (
                <p className="texto-suave pedido-decisao">
                  {p.status === "CANCELADA" ? "Cancelado" : "Decidido"} por {p.decidido_por_nome ?? "—"} em{" "}
                  {dataHora(p.decidido_em)}
                  {p.resposta && <> · “{p.resposta}”</>}
                </p>
              )}
              {ehAdmin && p.status === "PENDENTE" && (
                <div className="acoes-form">
                  <button className="btn btn-secundario" onClick={() => setDecidindo({ pedido: p, acao: "recusar" })}>
                    <X size={16} /> Recusar
                  </button>
                  <button className="btn btn-perigo" onClick={() => setDecidindo({ pedido: p, acao: "aprovar" })}>
                    <Check size={16} /> Aprovar e excluir
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {decidindo && (
        <ModalDecisao pedido={decidindo.pedido} acao={decidindo.acao} aoFechar={() => setDecidindo(null)} />
      )}
    </>
  );
}

export function ModalDecisao({
  pedido,
  acao,
  aoFechar,
  aoConcluir,
}: {
  pedido: SolicitacaoExclusao;
  acao: "aprovar" | "recusar";
  aoFechar: () => void;
  aoConcluir?: () => void;
}) {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const [resposta, setResposta] = useState("");
  const decidir = useMutation({
    mutationFn: async () => {
      if (acao === "aprovar") await aprovarExclusao(pedido.id, resposta.trim());
      else await recusarExclusao(pedido.id, resposta.trim());
    },
    onSuccess: () => {
      for (const chave of ["exclusoes", "exclusoes-pendentes", "oficios", "oficio", "resumo", "analise", "atividades"]) {
        queryClient.invalidateQueries({ queryKey: [chave] });
      }
      avisar(acao === "aprovar" ? `Pedido aprovado: ${pedido.referencia} foi excluído.` : "Pedido recusado.");
      aoFechar();
      aoConcluir?.();
    },
  });
  const aprovar = acao === "aprovar";

  return (
    <Modal
      titulo={aprovar ? "Aprovar e excluir o ofício" : "Recusar pedido de exclusão"}
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao className={aprovar ? "btn btn-perigo" : "btn btn-primario"} carregando={decidir.isPending}
            disabled={!aprovar && !resposta.trim()} onClick={() => decidir.mutate()}>
            {aprovar ? "Excluir definitivamente" : "Recusar pedido"}
          </Botao>
        </>
      }
    >
      <p>
        <strong>{pedido.referencia}</strong> · pedido por {pedido.solicitante_nome}: “{pedido.motivo}”
      </p>
      {aprovar && <p>O ofício, seus documentos e o histórico serão apagados. O registro de atividades guarda a exclusão.</p>}
      <Campo rotulo={aprovar ? "Observação (opcional)" : "Motivo da recusa *"}>
        {(id) => (
          <textarea id={id} className="input" rows={3} maxLength={1000} value={resposta}
            onChange={(e) => setResposta(e.target.value)} />
        )}
      </Campo>
      {decidir.isError && <div className="alerta-erro">{decidir.error.message}</div>}
    </Modal>
  );
}
