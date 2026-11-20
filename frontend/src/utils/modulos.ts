import type { Modulo, Perfil, Usuario } from "../types";

/** Catálogo dos módulos no front (o nome e a rota vêm também de GET /api/modulos; aqui servem para os formulários). */
export const MODULOS: { modulo: Modulo; nome: string; rota: string }[] = [
  { modulo: "OFICIOS", nome: "Planner de Ofícios", rota: "/" },
  { modulo: "MANUTENCAO", nome: "Manutenção Clínica", rota: "/manutencao" },
  { modulo: "TETOS", nome: "Controle de Tetos", rota: "/tetos" },
];

export const NOME_MODULO: Record<Modulo, string> = {
  OFICIOS: "Planner de Ofícios",
  MANUTENCAO: "Manutenção Clínica",
  TETOS: "Controle de Tetos",
};

export function papelNo(usuario: Usuario | null | undefined, modulo: Modulo): Perfil | null {
  if (!usuario) return null;
  if (usuario.perfil === "MASTER") return "MASTER";
  return usuario.modulos.find((a) => a.modulo === modulo)?.perfil ?? null;
}

export const temAcesso = (u: Usuario | null | undefined, m: Modulo) => papelNo(u, m) !== null;

export const ehAdminNo = (u: Usuario | null | undefined, m: Modulo) => {
  const p = papelNo(u, m);
  return p === "ADMIN" || p === "MASTER";
};

/** Módulos em que o usuário é administrador (o MASTER, em todos). */
export const modulosQueAdministra = (u: Usuario | null | undefined): Modulo[] =>
  MODULOS.map((m) => m.modulo).filter((m) => ehAdminNo(u, m));

/** MASTER ou administrador de algum módulo: pode gerir usuários. */
export const ehGestor = (u: Usuario | null | undefined) => modulosQueAdministra(u).length > 0;

/**
 * Nome, login, senha e situação: o próprio usuário, o MASTER, ou o administrador que administra todos os
 * módulos do outro (e o outro não é master nem administrador). Espelha `_pode_gerir_conta` da API.
 */
export function podeGerirConta(eu: Usuario | null | undefined, alvo: Usuario): boolean {
  if (!eu) return false;
  if (eu.id === alvo.id || eu.perfil === "MASTER") return true;
  if (alvo.perfil === "MASTER" || alvo.modulos.some((a) => a.perfil === "ADMIN")) return false;
  const meus = new Set(modulosQueAdministra(eu));
  // O acesso de cliente ao Planner que vem junto com o operacional da Manutenção não conta
  const operacional = alvo.modulos.some((a) => a.modulo === "MANUTENCAO" && (a.perfil === "CLIENTE" || a.perfil === "ADMIN"));
  return alvo.modulos.every(
    (a) => meus.has(a.modulo) || (operacional && a.modulo === "OFICIOS" && a.perfil === "CLIENTE"),
  );
}

/** Pode mexer no acesso do alvo em algum módulo que o editor administra? (não vale para si mesmo) */
export function podeEditarAcesso(eu: Usuario | null | undefined, alvo: Usuario): boolean {
  if (!eu || eu.id === alvo.id) return false;
  if (eu.perfil === "MASTER") return true;
  if (alvo.perfil === "MASTER") return false;
  const meus = new Set(modulosQueAdministra(eu));
  return !alvo.modulos.some((a) => meus.has(a.modulo) && a.perfil === "ADMIN");
}

export function podeEditar(eu: Usuario | null | undefined, alvo: Usuario): boolean {
  return podeGerirConta(eu, alvo) || podeEditarAcesso(eu, alvo);
}
