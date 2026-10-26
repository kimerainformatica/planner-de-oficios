// Espelho dos schemas da API (backend/app/schemas.py).

export type Perfil = "MASTER" | "ADMIN" | "CLIENTE";
export type StatusSolicitacao = "PENDENTE" | "APROVADA" | "RECUSADA" | "CANCELADA";
export type StatusOficio =
  | "PENDENTE_RESPOSTA"
  | "CONFIRMADO"
  | "NAO_CONFIRMADO"
  | "PENDENTE_RECEBIMENTO" // ofício de itens: resposta confirmada, entrega ainda não
  | "RECEBIDO";
export type NivelAlerta = "NORMAL" | "ATENCAO" | "CRITICO";
export type TipoAnexo = "OFICIO" | "REFERENCIA" | "RESPOSTA" | "RECEBIMENTO";
/** Código de um tipo cadastrado (GET /api/tipos). Os tipos são cadastrados pelos administradores. */
export type TipoOficio = string;

export interface TipoInfo {
  codigo: TipoOficio;
  nome: string;
  nome_curto: string | null;
  exige_entrega: boolean;
  ativo: boolean;
  ordem: number;
  em_uso: number;
}
export type Destinatario = "SES" | "ACQUA" | "OUTROS";

export interface Usuario {
  id: number;
  nome: string;
  login: string;
  perfil: Perfil;
  ativo: boolean;
}

export interface Token {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

export interface Anexo {
  id: number;
  tipo: TipoAnexo;
  historico_id: number | null;
  nome_original: string;
  mime_type: string;
  tamanho_bytes: number;
  enviado_em: string;
}

export interface Historico {
  id: number;
  status_anterior: StatusOficio | null;
  status_novo: StatusOficio;
  data_resposta: string | null;
  data_recebimento: string | null;
  observacao: string | null;
  alterado_em: string;
  usuario_nome: string | null;
  evidencia: Anexo | null;
  // Resposta/recebimento desfeito por admin: fica no histórico, mas não vale mais
  anulado_em: string | null;
  anulado_por_nome: string | null;
  anulado_motivo: string | null;
}

export interface Oficio {
  id: number;
  dono: { id: number; nome: string };
  numero: string;
  data_oficio: string;
  tipo: TipoOficio | null;
  protocolo: string | null;
  destinatario_tipo: Destinatario | null;
  destinatario_setor: string | null;
  status: StatusOficio;
  inicio_prazo: string;
  data_resposta: string | null;
  data_recebimento: string | null;
  observacao: string | null;
  criado_em: string;
  atualizado_em: string;
  dias_uteis_decorridos: number; // da etapa atual: aguardando resposta/entrega, ou até a resposta
  dias_resposta: number | null; // do início do prazo até a resposta
  dias_entrega: number | null; // da resposta até a entrega (só recebidos)
  nivel_alerta: NivelAlerta | null;
  anexos: Anexo[];
}

export interface SolicitacaoExclusao {
  id: number;
  oficio_id: number | null;
  referencia: string;
  motivo: string;
  status: StatusSolicitacao;
  resposta: string | null;
  criado_em: string;
  decidido_em: string | null;
  solicitante_nome: string | null;
  decidido_por_nome: string | null;
}

export interface OficioDetalhe extends Oficio {
  historico: Historico[];
  exclusao_pendente: SolicitacaoExclusao | null;
}

export interface Atividade {
  id: number;
  criado_em: string;
  usuario_id: number | null;
  usuario_nome: string | null;
  acao: string;
  descricao: string;
  referencia: string | null;
  oficio_id: number | null;
  detalhes: Record<string, unknown> | null;
}

export interface FiltrosAtividade {
  usuario_id?: number;
  oficio_id?: number;
  acao?: string;
  data_inicio?: string;
  data_fim?: string;
  pagina?: number;
  por_pagina?: number;
}

export interface Pagina<T> {
  itens: T[];
  total: number;
  pagina: number;
  por_pagina: number;
}

export interface Resumo {
  data_referencia: string;
  total: number;
  confirmados: number;
  nao_confirmados: number;
  pendentes: number;
  pendentes_normal: number;
  pendentes_atencao: number;
  pendentes_critico: number;
  pendentes_recebimento: number;
  recebidos: number;
}

export interface Feriado {
  id: number;
  data: string;
  descricao: string;
}

/** Filtros comuns à lista, ao painel e às exportações (FiltrosConsulta na API). */
export interface Filtros {
  status?: StatusOficio;
  alerta?: NivelAlerta;
  busca?: string;
  dono_id?: number;
  tipo?: TipoOficio;
  destinatario_tipo?: Destinatario;
  data_inicio?: string;
  data_fim?: string;
}

export interface FiltrosOficio extends Filtros {
  ordem?: "recentes" | "antigos";
  pagina?: number;
  por_pagina?: number;
}

export interface Indicadores {
  total: number;
  pendentes: number;
  pendentes_normal: number;
  pendentes_atencao: number;
  pendentes_critico: number;
  pendentes_recebimento: number;
  recebimento_normal: number;
  recebimento_atencao: number;
  recebimento_critico: number;
  confirmados: number; // status CONFIRMADO (tipos sem recebimento)
  recebidos: number;
  nao_confirmados: number;
  taxa_confirmacao: number | null;
  tempo_medio_resposta: number | null;
  respondidos_no_prazo: number | null;
  tempo_medio_entrega: number | null;
  entregues_no_prazo: number | null;
  concluidos: number; // recebidos + confirmados sem etapa de entrega
}

export interface Grupo {
  chave: string | null;
  rotulo: string;
  total: number;
  pendentes: number;
  pendentes_recebimento: number;
  confirmados: number;
  recebidos: number;
  nao_confirmados: number;
  atencao: number; // pendentes de resposta ou de recebimento
  criticos: number;
  tempo_medio_resposta: number | null;
  tempo_medio_entrega: number | null;
}

export interface Prazos {
  dias_atencao: number;
  dias_critico: number;
}

export interface Analise {
  data_referencia: string;
  prazos: Prazos;
  indicadores: Indicadores;
  por_tipo: Grupo[];
  por_destinatario: Grupo[];
  por_setor: Grupo[];
  por_cliente: Grupo[];
  por_mes: { mes: string; cadastrados: number; respondidos: number; recebidos: number }[];
}

export interface AnexoLixeira {
  id: number;
  oficio_id: number;
  oficio_numero: string;
  tipo: TipoAnexo;
  historico_id: number | null;
  nome_original: string;
  mime_type: string;
  tamanho_bytes: number;
  enviado_em: string;
  motivo: "SUBSTITUIDO" | "REMOVIDO";
  descartado_em: string;
  descartado_por_nome: string | null;
}

export interface VerificacaoArquivos {
  verificado_em: string;
  arquivos: number;
  problemas: {
    origem: "anexo" | "lixeira";
    id: number;
    oficio_id: number;
    oficio_numero: string;
    nome_original: string;
    problema: "AUSENTE" | "ALTERADO";
  }[];
  sem_registro: number;
}
