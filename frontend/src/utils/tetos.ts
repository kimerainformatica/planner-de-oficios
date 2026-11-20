import type { PeriodoTeto, SituacaoTeto } from "../types";

export const ROTULO_PERIODO: Record<PeriodoTeto, string> = { DIARIO: "por dia", MENSAL: "por mês", ANUAL: "por ano" };
export const NOME_PERIODO: Record<PeriodoTeto, string> = { DIARIO: "Diário", MENSAL: "Mensal", ANUAL: "Anual" };

export const ROTULO_SITUACAO_TETO: Record<SituacaoTeto, string> = {
  NORMAL: "Dentro do teto",
  ATENCAO: "Atenção",
  ESTOURADO: "Acima do teto",
  SEM_TETO: "Sem teto",
};

/** Classe de cor (reaproveita as cores de prazo: normal, atenção, crítico). */
export const CLASSE_SITUACAO_TETO: Record<SituacaoTeto, string> = {
  NORMAL: "NORMAL",
  ATENCAO: "ATENCAO",
  ESTOURADO: "CRITICO",
  SEM_TETO: "NEUTRO",
};

export const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
export const MESES_LONGOS = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
  "dezembro",
];

const ehReal = (unidade: string) => unidade.trim().toUpperCase() === "R$";

/** R$ 1.234,56 · 12,5 litros */
export function valorTeto(v: number, unidade: string, compacto = false): string {
  if (ehReal(unidade)) {
    return v.toLocaleString("pt-BR", {
      style: "currency", currency: "BRL", ...(compacto && Math.abs(v) >= 10000 ? { notation: "compact" } : {}),
    });
  }
  const n = v.toLocaleString("pt-BR", { maximumFractionDigits: 2, ...(compacto && Math.abs(v) >= 10000 ? { notation: "compact" } : {}) });
  return `${n} ${unidade}`;
}

export function percentualTeto(p: number | null): string {
  return p === null ? "—" : `${p.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

/** Converte "1.234,56" ou "1234.56" para o texto que a API aceita ("1234.56"); null se inválido. */
export function lerValor(texto: string): string | null {
  let t = texto.trim().replace(/\s|R\$/g, "");
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(t) || Number(t) <= 0) return null;
  return t;
}

/** Valor do banco (número) para o campo de texto do formulário: 1234.5 → "1.234,50" */
export function valorParaCampo(v: number): string {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function primeiroDoMes(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

/** Nome do papel no Controle de Tetos: o cliente é o "usuário do setor". */
export const ROTULO_PAPEL_TETOS: Record<"MASTER" | "ADMIN" | "CLIENTE" | "TECNICO", string> = {
  MASTER: "Master",
  ADMIN: "Administrador",
  CLIENTE: "Usuário do setor",
  TECNICO: "Técnico",
};
