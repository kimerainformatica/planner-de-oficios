// Regras do histórico (resposta/recebimento que valem) e utilidades compartilhadas da tela do ofício.
import { useQueryClient } from "@tanstack/react-query";
import type { Historico, OficioDetalhe as Detalhe, TipoAnexo } from "../../types";

export type ModalAberto =
  | "resposta"
  | "recebimento"
  | "corrigir-resposta"
  | "corrigir-recebimento"
  | "desfazer"
  | "reabrir"
  | "editar"
  | "excluir"
  | "pedir-exclusao"
  | "aprovar"
  | "recusar"
  | null;

export type TipoEvidencia = Extract<TipoAnexo, "RESPOSTA" | "RECEBIMENTO">;

// Resposta registrada: sempre sai de PENDENTE_RESPOSTA. Ofício de itens confirmado vai para PENDENTE_RECEBIMENTO
// (esse status também surge ao trocar o tipo, e aí não é resposta).
export const ehResposta = (h: Historico) =>
  h.status_anterior === "PENDENTE_RESPOSTA" &&
  (h.status_novo === "CONFIRMADO" || h.status_novo === "NAO_CONFIRMADO" || h.status_novo === "PENDENTE_RECEBIMENTO");

export const ehRecebimento = (h: Historico) => h.status_novo === "RECEBIDO";

export const tipoEvidencia = (h: Historico): TipoEvidencia | null =>
  ehResposta(h) ? "RESPOSTA" : ehRecebimento(h) ? "RECEBIMENTO" : null;

// Evento desfeito por um admin: continua no histórico, mas não vale mais
export const ativo = (h: Historico) => h.anulado_em === null;

/** Resposta que vale no ciclo atual (espelho de evento_resposta_atual no backend). */
export function respostaAtual(o: Detalhe): Historico | undefined {
  if (o.status === "PENDENTE_RESPOSTA") return undefined;
  for (const h of [...o.historico].reverse().filter(ativo)) {
    if (ehResposta(h)) return h;
    if (h.status_novo === "PENDENTE_RESPOSTA") return undefined;
  }
  return undefined;
}

export function recebimentoAtual(o: Detalhe): Historico | undefined {
  return o.status === "RECEBIDO" ? [...o.historico].reverse().find((h) => ativo(h) && ehRecebimento(h)) : undefined;
}

/** Ações de correção do admin/master na linha do tempo. */
export interface Correcoes {
  respostaId?: number;
  recebimentoId?: number;
  desfazerId?: number; // o evento que "Desfazer" anula: o recebimento, ou a resposta se não houver
  abrir: (m: ModalAberto) => void;
}

export function useAtualizarOficio(id: number) {
  const queryClient = useQueryClient();
  return (novo?: Detalhe) => {
    if (novo) queryClient.setQueryData(["oficio", id], novo);
    else queryClient.invalidateQueries({ queryKey: ["oficio", id] });
    queryClient.invalidateQueries({ queryKey: ["oficios"] });
    queryClient.invalidateQueries({ queryKey: ["resumo"] });
    queryClient.invalidateQueries({ queryKey: ["analise"] });
    queryClient.invalidateQueries({ queryKey: ["atividades"] });
    queryClient.invalidateQueries({ queryKey: ["lixeira"] }); // substituir ou remover manda a versão anterior para lá
  };
}
