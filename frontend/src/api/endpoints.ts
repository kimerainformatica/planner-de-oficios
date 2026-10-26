import type {
  Analise,
  Anexo,
  AnexoLixeira,
  Atividade,
  Destinatario,
  Feriado,
  Filtros,
  FiltrosAtividade,
  FiltrosOficio,
  Oficio,
  OficioDetalhe,
  Pagina,
  Perfil,
  Prazos,
  Resumo,
  SolicitacaoExclusao,
  StatusOficio,
  StatusSolicitacao,
  TipoAnexo,
  TipoInfo,
  TipoOficio,
  Token,
  Usuario,
  VerificacaoArquivos,
} from "../types";
import { api, requisicao } from "./client";

const json = (corpo: unknown) => JSON.stringify(corpo);

// ---------- autenticação ----------

export const login = (usuario: string, senha: string) =>
  api<Token>("/auth/login", {
    method: "POST",
    body: new URLSearchParams({ username: usuario, password: senha }),
  });

export const eu = () => api<Usuario>("/auth/me");

// ---------- ofícios ----------

export interface OficioForm {
  numero: string;
  data_oficio: string;
  tipo: TipoOficio;
  protocolo: string | null;
  destinatario_tipo: Destinatario | null;
  destinatario_setor: string | null;
  observacao: string | null;
  dono_id?: number | null;
}

export const listarOficios = (filtros: FiltrosOficio) =>
  api<Pagina<Oficio>>("/oficios", { params: { ...filtros } });

export const buscarOficio = (id: number) => api<OficioDetalhe>(`/oficios/${id}`);

export const criarOficio = (dados: OficioForm) =>
  api<OficioDetalhe>("/oficios", { method: "POST", body: json(dados) });

export const atualizarOficio = (id: number, dados: Partial<OficioForm>) =>
  api<OficioDetalhe>(`/oficios/${id}`, { method: "PATCH", body: json(dados) });

export const alterarStatus = (
  id: number,
  dados: {
    status: StatusOficio;
    data_resposta?: string | null;
    data_recebimento?: string | null;
    observacao?: string | null;
  },
) => api<OficioDetalhe>(`/oficios/${id}/status`, { method: "PATCH", body: json(dados) });

// Correções do admin/master
export const corrigirResposta = (
  id: number,
  dados: { status?: "CONFIRMADO" | "NAO_CONFIRMADO"; data_resposta?: string; observacao?: string | null },
) => api<OficioDetalhe>(`/oficios/${id}/resposta`, { method: "PATCH", body: json(dados) });

export const corrigirRecebimento = (id: number, dados: { data_recebimento?: string; observacao?: string | null }) =>
  api<OficioDetalhe>(`/oficios/${id}/recebimento`, { method: "PATCH", body: json(dados) });

export const desfazerEtapa = (id: number, motivo: string) =>
  api<OficioDetalhe>(`/oficios/${id}/desfazer`, { method: "POST", body: json({ motivo }) });

export const excluirOficio = (id: number) => api<void>(`/oficios/${id}`, { method: "DELETE" });

export const resumo = (dono_id?: number) => api<Resumo>("/dashboard/resumo", { params: { dono_id } });

export const prazos = () => api<Prazos>("/dashboard/prazos");

export const analise = (filtros: Filtros) => api<Analise>("/dashboard/analise", { params: { ...filtros } });

/** Baixa o relatório do painel (mesmos filtros) e devolve o arquivo pronto para salvar. */
export async function exportarPainel(formato: "xlsx" | "pdf", filtros: Filtros) {
  const resposta = await requisicao("/dashboard/exportar", { params: { ...filtros, formato } });
  const nome = /filename="([^"]+)"/.exec(resposta.headers.get("Content-Disposition") ?? "")?.[1];
  const tipo =
    formato === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  return { blob: new Blob([await resposta.arrayBuffer()], { type: tipo }), nome: nome ?? `oficios.${formato}` };
}

// ---------- anexos ----------

/** historicoId é obrigatório para RESPOSTA: liga a evidência ao evento de resposta. */
export function enviarAnexo(oficioId: number, tipo: TipoAnexo, arquivo: File, historicoId?: number) {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  return api<Anexo>(`/oficios/${oficioId}/anexos/${tipo}`, {
    method: "POST",
    body: corpo,
    params: { historico_id: historicoId },
  });
}

export const excluirAnexo = (id: number) => api<void>(`/anexos/${id}`, { method: "DELETE" });

/**
 * Baixa o arquivo com o token e devolve um blob — links <a href> comuns não levam o token.
 * Pede o conteúdo "bruto" (octet-stream) porque o Edge intercepta respostas application/pdf
 * vindas de fetch e entrega corpo vazio; o tipo certo é remontado a partir do cadastro do anexo.
 */
export async function baixarAnexo(anexo: Anexo): Promise<Blob> {
  const resposta = await requisicao(`/anexos/${anexo.id}/download`, { params: { bruto: true } });
  return new Blob([await resposta.arrayBuffer()], { type: anexo.mime_type });
}

// ---------- lixeira de anexos e verificação dos arquivos (admin/master) ----------

export const listarLixeira = (oficioId?: number) =>
  api<AnexoLixeira[]>("/lixeira", { params: { oficio_id: oficioId } });

export const restaurarDaLixeira = (id: number) => api<void>(`/lixeira/${id}/restaurar`, { method: "POST" });

export const apagarDaLixeira = (id: number) => api<void>(`/lixeira/${id}`, { method: "DELETE" });

export async function baixarDaLixeira(item: AnexoLixeira): Promise<Blob> {
  const resposta = await requisicao(`/lixeira/${item.id}/download`, { params: { bruto: true } });
  return new Blob([await resposta.arrayBuffer()], { type: item.mime_type });
}

export const ultimaVerificacao = () => api<VerificacaoArquivos>("/arquivos/verificacao");

export const verificarArquivos = () => api<VerificacaoArquivos>("/arquivos/verificacao", { method: "POST" });

// ---------- tipos de ofício ----------

export const listarTipos = () => api<TipoInfo[]>("/tipos");

export const criarTipo = (dados: { nome: string; nome_curto: string | null; exige_entrega: boolean }) =>
  api<TipoInfo>("/tipos", { method: "POST", body: json(dados) });

export const atualizarTipo = (
  codigo: string,
  dados: Partial<Pick<TipoInfo, "nome" | "nome_curto" | "exige_entrega" | "ativo" | "ordem">>,
) => api<TipoInfo>(`/tipos/${codigo}`, { method: "PATCH", body: json(dados) });

export const excluirTipo = (codigo: string) => api<void>(`/tipos/${codigo}`, { method: "DELETE" });

/** Setores/destinos já usados com esse destinatário, para sugerir ao digitar. */
export const sugestoesSetor = (destinatario: Destinatario) =>
  api<string[]>("/oficios/setores", { params: { destinatario_tipo: destinatario } });

// ---------- usuários ----------

export const listarUsuarios = () => api<Usuario[]>("/usuarios");

export const criarUsuario = (dados: { nome: string; login: string; senha: string; perfil: Perfil }) =>
  api<Usuario>("/usuarios", { method: "POST", body: json(dados) });

export const atualizarUsuario = (
  id: number,
  dados: Partial<{ nome: string; login: string; senha: string; perfil: Perfil; ativo: boolean }>,
) => api<Usuario>(`/usuarios/${id}`, { method: "PATCH", body: json(dados) });

// ---------- feriados ----------

export const listarFeriados = (ano?: number) => api<Feriado[]>("/feriados", { params: { ano } });

export const criarFeriado = (dados: { data: string; descricao: string }) =>
  api<Feriado>("/feriados", { method: "POST", body: json(dados) });

export const gerarFeriadosNacionais = (ano: number) =>
  api<Feriado[]>(`/feriados/nacionais/${ano}`, { method: "POST" });

export const excluirFeriado = (id: number) => api<void>(`/feriados/${id}`, { method: "DELETE" });

// ---------- pedidos de exclusão ----------

export const solicitarExclusao = (oficioId: number, motivo: string) =>
  api<SolicitacaoExclusao>(`/oficios/${oficioId}/exclusao`, { method: "POST", body: json({ motivo }) });

export const cancelarExclusao = (oficioId: number) =>
  api<void>(`/oficios/${oficioId}/exclusao`, { method: "DELETE" });

export const listarExclusoes = (status?: StatusSolicitacao) =>
  api<SolicitacaoExclusao[]>("/exclusoes", { params: { status } });

export const exclusoesPendentes = () => api<{ total: number }>("/exclusoes/pendentes");

export const aprovarExclusao = (id: number, resposta?: string) =>
  api<void>(`/exclusoes/${id}/aprovar`, { method: "POST", body: json({ resposta: resposta || null }) });

export const recusarExclusao = (id: number, resposta: string) =>
  api<SolicitacaoExclusao>(`/exclusoes/${id}/recusar`, { method: "POST", body: json({ resposta }) });

// ---------- registro de atividades ----------

export const listarAtividades = (filtros: FiltrosAtividade) =>
  api<Pagina<Atividade>>("/auditoria", { params: { ...filtros } });
