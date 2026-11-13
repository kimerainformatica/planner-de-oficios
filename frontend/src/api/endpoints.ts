import type {
  AcessoModulo,
  Analise,
  AnexoOficio,
  Anexo,
  AnexoLixeira,
  Atividade,
  Chamado,
  ChamadoDetalhe,
  EmpresaManutencao,
  FiltrosChamado,
  Interacao,
  PainelManutencao,
  QuadroChamados,
  RelatorioTecnico,
  TipoSolicitacao,
  Destinatario,
  Feriado,
  Filtros,
  FiltrosAtividade,
  FiltrosOficio,
  Modulo,
  ModuloDisponivel,
  Oficio,
  OficioDetalhe,
  Pagina,
  Prazos,
  ResumoManutencao,
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

/** `modulo` filtra quem tem acesso a ele (o MASTER sempre tem). */
export const listarUsuarios = (modulo?: Modulo) =>
  api<Usuario[]>(`/usuarios${modulo ? `?modulo=${modulo}` : ""}`);

export const criarUsuario = (dados: {
  nome: string;
  login: string;
  senha: string;
  master?: boolean;
  modulos: AcessoModulo[];
}) => api<Usuario>("/usuarios", { method: "POST", body: json(dados) });

// ---------- módulos ----------

export const listarModulos = () => api<ModuloDisponivel[]>("/modulos");

// ---------- Manutenção Clínica (helpdesk) ----------

export const resumoManutencao = () => api<ResumoManutencao>("/manutencao/resumo");

export const painelManutencao = () => api<PainelManutencao>("/manutencao/painel");

export const listarEmpresas = (ativas = false) =>
  api<EmpresaManutencao[]>("/manutencao/empresas", { params: { ativas: ativas || undefined } });

export const criarEmpresa = (dados: { nome: string; descricao?: string | null; prazo_horas: number }) =>
  api<EmpresaManutencao>("/manutencao/empresas", { method: "POST", body: json(dados) });

export const atualizarEmpresa = (
  id: number,
  dados: Partial<{ nome: string; descricao: string | null; prazo_horas: number; ativo: boolean }>,
) => api<EmpresaManutencao>(`/manutencao/empresas/${id}`, { method: "PATCH", body: json(dados) });

export const excluirEmpresa = (id: number) => api<void>(`/manutencao/empresas/${id}`, { method: "DELETE" });

export const listarChamados = (f: FiltrosChamado) =>
  api<Pagina<Chamado>>("/manutencao/chamados", { params: { ...f, por_pagina: 20 } });

export const verChamado = (id: number) => api<ChamadoDetalhe>(`/manutencao/chamados/${id}`);

export const abrirChamado = (dados: {
  empresa_id: number;
  titulo: string;
  descricao: string;
  local?: string | null;
  equipamento?: string | null;
  ocorrido_em?: string | null;
}) => api<ChamadoDetalhe>("/manutencao/chamados", { method: "POST", body: json(dados) });

export const quadroChamados = (f: { meus?: boolean; empresa_id?: number; dias?: number }) =>
  api<QuadroChamados>("/manutencao/quadro", { params: { meus: f.meus || undefined, empresa_id: f.empresa_id, dias: f.dias } });

export const tiposSolicitacao = () => api<TipoSolicitacao[]>("/manutencao/tipos-solicitacao");

/** Solicitação de peças ou equipamentos: cadastra um ofício no Planner ligado ao chamado. */
export const solicitarPecas = (
  id: number,
  dados: {
    tipo: string;
    numero: string;
    data_oficio: string;
    protocolo?: string | null;
    destinatario_tipo?: Destinatario | null;
    destinatario_setor?: string | null;
    itens: string;
  },
) => api<ChamadoDetalhe>(`/manutencao/chamados/${id}/oficios`, { method: "POST", body: json(dados) });

export const assumirChamado = (id: number) =>
  api<ChamadoDetalhe>(`/manutencao/chamados/${id}/assumir`, { method: "POST" });

/** Comentário ou resposta técnica (diagnóstico), com arquivo opcional. */
export function responderChamado(id: number, dados: { texto?: string; diagnostico?: boolean; arquivo?: File | null }) {
  const corpo = new FormData();
  if (dados.texto) corpo.append("texto", dados.texto);
  if (dados.diagnostico) corpo.append("diagnostico", "true");
  if (dados.arquivo) corpo.append("arquivo", dados.arquivo);
  return api<ChamadoDetalhe>(`/manutencao/chamados/${id}/interacoes`, { method: "POST", body: corpo });
}

export type RelatorioForm = Omit<
  RelatorioTecnico,
  "id" | "codigo" | "chamado_id" | "tecnico" | "empresa" | "criado_em" | "atendido_em"
> & { atendido_em?: string | null };

export const criarRelatorio = (id: number, dados: RelatorioForm) =>
  api<ChamadoDetalhe>(`/manutencao/chamados/${id}/relatorios`, { method: "POST", body: json(dados) });

export const concluirChamado = (id: number, texto?: string) =>
  api<ChamadoDetalhe>(`/manutencao/chamados/${id}/concluir`, { method: "POST", body: json({ texto: texto || null }) });

export const reabrirChamado = (id: number, motivo: string) =>
  api<ChamadoDetalhe>(`/manutencao/chamados/${id}/reabrir`, { method: "POST", body: json({ motivo }) });

export const cancelarChamado = (id: number, motivo: string) =>
  api<ChamadoDetalhe>(`/manutencao/chamados/${id}/cancelar`, { method: "POST", body: json({ motivo }) });

export async function baixarArquivoInteracao(i: Interacao): Promise<Blob> {
  const resposta = await requisicao(`/manutencao/interacoes/${i.id}/arquivo`, { params: { bruto: true } });
  return new Blob([await resposta.arrayBuffer()], { type: i.arquivo_mime ?? "application/octet-stream" });
}

/** Documento do ofício de peças/equipamentos (anexado no Planner), baixado pelo chamado. */
export async function baixarAnexoOficio(chamadoId: number, anexo: AnexoOficio): Promise<Blob> {
  const resposta = await requisicao(`/manutencao/chamados/${chamadoId}/oficios/anexos/${anexo.id}`, { params: { bruto: true } });
  return new Blob([await resposta.arrayBuffer()], { type: anexo.mime_type });
}

export async function baixarRelatorioPdf(relatorioId: number): Promise<Blob> {
  const resposta = await requisicao(`/manutencao/relatorios/${relatorioId}/pdf`, { params: { bruto: true } });
  return new Blob([await resposta.arrayBuffer()], { type: "application/pdf" });
}

export const atualizarUsuario = (
  id: number,
  dados: Partial<{
    nome: string;
    login: string;
    senha: string;
    master: boolean;
    modulos: AcessoModulo[];
    ativo: boolean;
  }>,
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
