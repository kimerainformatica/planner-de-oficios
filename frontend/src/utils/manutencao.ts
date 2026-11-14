import type { Perfil, SituacaoEquipamento, SituacaoPrazo, StatusChamado, TipoInteracao } from "../types";

export const ROTULO_STATUS_CHAMADO: Record<StatusChamado, string> = {
  ABERTO: "Aberto",
  EM_ATENDIMENTO: "Em atendimento",
  CONCLUIDO: "Concluído",
  CANCELADO: "Cancelado",
};

export const ROTULO_SITUACAO: Record<SituacaoPrazo, string> = {
  NO_PRAZO: "No prazo",
  VENCENDO: "Vencendo",
  ATRASADO: "Atrasado",
  CUMPRIDO: "Diagnóstico no prazo",
  CUMPRIDO_COM_ATRASO: "Diagnóstico com atraso",
  SUSPENSO: "Sem prazo (cancelado)",
};

export const ROTULO_INTERACAO: Record<TipoInteracao, string> = {
  ABERTURA: "Chamado aberto",
  COMENTARIO: "Comentário",
  DIAGNOSTICO: "Resposta técnica",
  RELATORIO: "Relatório técnico",
  ASSUMIDO: "Chamado assumido",
  CONCLUSAO: "Chamado concluído",
  REABERTURA: "Chamado reaberto",
  CANCELAMENTO: "Chamado cancelado",
  OFICIO: "Solicitação de peças / equipamentos",
};

export const ROTULO_EQUIPAMENTO: Record<SituacaoEquipamento, string> = {
  OPERANDO: "Operando normalmente",
  OPERANDO_COM_RESTRICAO: "Operando com restrição",
  PARADO: "Parado / fora de operação",
  AGUARDANDO_PECA: "Aguardando peça",
  NAO_SE_APLICA: "Não se aplica",
};

/** Papel na Manutenção Clínica: o cliente é o "operacional". */
export const ROTULO_PAPEL_MANUTENCAO: Record<Perfil, string> = {
  MASTER: "Master",
  ADMIN: "Administrador",
  CLIENTE: "Operacional",
  TECNICO: "Técnico",
};

/** 1,5 → "1 h 30 min"; 26 → "26 h" */
export function horas(h: number): string {
  const total = Math.round(Math.abs(h) * 60);
  const hh = Math.floor(total / 60);
  const mm = total % 60;
  if (hh === 0) return `${mm} min`;
  return mm ? `${hh} h ${mm} min` : `${hh} h`;
}

/** Texto curto do prazo de um chamado ainda sem diagnóstico. */
export function textoPrazo(situacao: SituacaoPrazo, restantes: number | null, diagnostico: number | null): string {
  if (situacao === "ATRASADO" && restantes !== null) return `atrasado há ${horas(restantes)} úteis`;
  if ((situacao === "NO_PRAZO" || situacao === "VENCENDO") && restantes !== null) return `restam ${horas(restantes)} úteis`;
  if ((situacao === "CUMPRIDO" || situacao === "CUMPRIDO_COM_ATRASO") && diagnostico !== null)
    return `diagnóstico em ${horas(diagnostico)} úteis`;
  return "";
}

/** Data e hora local no formato do <input type="datetime-local"> (yyyy-mm-ddThh:mm). */
export function agoraLocal(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
