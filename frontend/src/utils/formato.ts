import type { Destinatario, NivelAlerta, Oficio, StatusOficio } from "../types";
// Nomes dos tipos de ofício e a regra da entrega vêm do cadastro: ver utils/tipos.ts (useTipos)

export const ROTULO_DESTINATARIO: Record<Destinatario, string> = { SES: "SES", ACQUA: "ACQUA", OUTROS: "Outros" };

/** "SES · Almoxarifado" / "Outros · Prefeitura" / "" */
export function destinatarioTexto(o: Pick<Oficio, "destinatario_tipo" | "destinatario_setor">): string {
  if (!o.destinatario_tipo) return "";
  return `${ROTULO_DESTINATARIO[o.destinatario_tipo]} · ${o.destinatario_setor ?? ""}`;
}

export function porcentagem(v: number | null): string {
  return v === null ? "—" : `${Math.round(v * 100)}%`;
}

export function decimal(v: number | null): string {
  return v === null ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
/** "2026-10" -> "out/26" */
export function mesCurto(m: string): string {
  return `${MESES[Number(m.slice(5, 7)) - 1]}/${m.slice(2, 4)}`;
}

/** "2026-10-20" -> "20/10/2026", sem passar por Date (evita erro de fuso horário). */
export function data(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

/** Data e hora vindas do servidor (horário local do servidor, sem fuso). */
export function dataHora(iso: string): string {
  const [dia, hora = ""] = iso.split("T");
  return `${data(dia)} ${hora.slice(0, 5)}`;
}

/** Hoje no formato yyyy-mm-dd, no fuso local (para <input type="date">). */
export function hojeIso(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function tamanho(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function diasUteis(n: number): string {
  return `${n} ${n === 1 ? "dia útil" : "dias úteis"}`;
}

// A ordem aqui é a ordem dos filtros: segue o caminho do ofício
export const ROTULO_STATUS: Record<StatusOficio, string> = {
  PENDENTE_RESPOSTA: "Pendente de resposta",
  PENDENTE_RECEBIMENTO: "Pendente de recebimento",
  CONFIRMADO: "Confirmado",
  RECEBIDO: "Recebido",
  NAO_CONFIRMADO: "Não confirmado",
};

export const ROTULO_ALERTA: Record<NivelAlerta, string> = {
  NORMAL: "No prazo",
  ATENCAO: "Atenção",
  CRITICO: "Crítico",
};

export const ROTULO_PERFIL: Record<"MASTER" | "ADMIN" | "CLIENTE", string> = {
  MASTER: "Master",
  ADMIN: "Administrador",
  CLIENTE: "Cliente",
};

export const ROTULO_ACAO: Record<string, string> = {
  OFICIO_CRIADO: "Ofício cadastrado",
  OFICIO_EDITADO: "Ofício editado",
  STATUS_ALTERADO: "Status alterado",
  RESPOSTA_CORRIGIDA: "Resposta corrigida",
  RECEBIMENTO_CORRIGIDO: "Recebimento corrigido",
  ETAPA_DESFEITA: "Resposta/recebimento desfeito",
  ANEXO_ENVIADO: "Documento anexado",
  ANEXO_SUBSTITUIDO: "Documento substituído",
  ANEXO_REMOVIDO: "Documento removido",
  EXCLUSAO_SOLICITADA: "Exclusão solicitada",
  EXCLUSAO_CANCELADA: "Pedido de exclusão cancelado",
  EXCLUSAO_APROVADA: "Exclusão aprovada",
  EXCLUSAO_RECUSADA: "Exclusão recusada",
  OFICIO_EXCLUIDO: "Ofício excluído",
  USUARIO_CRIADO: "Usuário criado",
  USUARIO_ALTERADO: "Usuário alterado",
  FERIADO_CRIADO: "Feriado cadastrado",
  FERIADO_EXCLUIDO: "Feriado removido",
};
