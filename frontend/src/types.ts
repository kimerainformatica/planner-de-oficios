// Espelho dos schemas da API (backend/app/schemas.py).

/** TECNICO só existe na Manutenção Clínica; lá o CLIENTE é o "operacional". */
export type Perfil = "MASTER" | "ADMIN" | "CLIENTE" | "TECNICO";
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

export type Modulo = "OFICIOS" | "MANUTENCAO" | "TETOS";

/** Papel do usuário em um módulo (o MASTER aparece como MASTER em todos). */
export interface AcessoModulo {
  modulo: Modulo;
  perfil: Perfil;
  /** Empresa do técnico (só TECNICO). */
  empresa_id?: number | null;
  empresa_nome?: string | null;
  /** Setor do usuário no Controle de Tetos (obrigatório para o usuário do setor). */
  setor_id?: number | null;
  setor_nome?: string | null;
}

export interface Usuario {
  id: number;
  nome: string;
  login: string;
  /** Global: MASTER (acesso total) ou CLIENTE. O papel em cada módulo está em `modulos`. */
  perfil: Perfil;
  ativo: boolean;
  modulos: AcessoModulo[];
}

export interface ModuloDisponivel {
  modulo: Modulo;
  nome: string;
  descricao: string;
  rota: string;
  perfil: Perfil;
}

// ---------- Manutenção Clínica (helpdesk) ----------

export interface Referencia {
  id: number;
  nome: string;
}

export interface ResumoManutencao {
  modulo: Modulo;
  nome: string;
  perfil: Perfil;
  eh_admin: boolean;
  eh_tecnico: boolean;
  empresa: Referencia | null;
}

export interface EmpresaManutencao {
  id: number;
  nome: string;
  descricao: string | null;
  prazo_horas: number;
  ativo: boolean;
  tecnicos: number;
  chamados: number;
}

export type StatusChamado = "ABERTO" | "EM_ATENDIMENTO" | "CONCLUIDO" | "CANCELADO";
export type SituacaoPrazo = "NO_PRAZO" | "VENCENDO" | "ATRASADO" | "CUMPRIDO" | "CUMPRIDO_COM_ATRASO" | "SUSPENSO";
export type TipoInteracao =
  | "ABERTURA"
  | "COMENTARIO"
  | "DIAGNOSTICO"
  | "RELATORIO"
  | "ASSUMIDO"
  | "CONCLUSAO"
  | "REABERTURA"
  | "CANCELAMENTO"
  | "OFICIO"
  | "CORRECAO";
export type SituacaoEquipamento =
  | "OPERANDO"
  | "OPERANDO_COM_RESTRICAO"
  | "PARADO"
  | "AGUARDANDO_PECA"
  | "NAO_SE_APLICA";

export interface PrazoChamado {
  situacao: SituacaoPrazo;
  /** Horas corridas até o prazo (negativo = atrasado); null depois do diagnóstico. */
  horas_restantes: number | null;
  horas_ate_diagnostico: number | null;
}

export interface Chamado {
  id: number;
  codigo: string;
  titulo: string;
  descricao: string;
  local: string | null;
  equipamento: string | null;
  empresa: Referencia;
  solicitante: Referencia;
  tecnico: Referencia | null;
  status: StatusChamado;
  ocorrido_em: string;
  aberto_em: string;
  prazo_horas: number;
  prazo_em: string;
  diagnosticado_em: string | null;
  concluido_em: string | null;
  cancelado_em: string | null;
  atualizado_em: string;
  prazo: PrazoChamado;
  /** Do diagnóstico até a conclusão, gravado ao concluir. */
  solucao_horas_corridas: number | null;
  /** Em aberto e já diagnosticado: horas corridas desde o diagnóstico. */
  execucao_horas: number | null;
  /** Solicitações de peças/equipamentos ainda não entregues. */
  oficios_pendentes: number;
  /** Nº e status de cada ofício de peças/equipamentos (o andamento vem do Planner). */
  oficios_resumo: { id: number; numero: string; status: StatusOficio }[];
}

/** Documento anexado ao ofício no Planner. */
export interface AnexoOficio {
  id: number;
  tipo: TipoAnexo;
  nome_original: string;
  mime_type: string;
  tamanho_bytes: number;
  enviado_em: string;
}

/** Ofício já cadastrado no Planner, ainda sem chamado, que o usuário pode vincular. */
export interface OficioDisponivel {
  id: number;
  numero: string;
  ano: number;
  data_oficio: string;
  tipo_nome: string | null;
  protocolo: string | null;
  status: StatusOficio;
  observacao: string | null;
  dono_nome: string | null;
}

/** Ofício do Planner ligado ao chamado: solicitação feita pelo chamado ou ofício que já existia e foi vinculado. */
export interface OficioVinculado {
  /** Quem consulta pode desfazer o vínculo agora. */
  pode_desvincular: boolean;
  id: number;
  numero: string;
  data_oficio: string;
  tipo: string | null;
  tipo_nome: string | null;
  protocolo: string | null;
  status: StatusOficio;
  data_resposta: string | null;
  data_recebimento: string | null;
  observacao: string | null;
  dono_id: number;
  dono_nome: string | null;
  anexos: AnexoOficio[];
}

export interface TipoSolicitacao {
  codigo: string;
  nome: string;
}

export interface ColunaQuadro {
  chave: "AGUARDANDO_DIAGNOSTICO" | "EM_EXECUCAO" | "AGUARDANDO_PECAS" | "CONCLUIDOS";
  titulo: string;
  descricao: string;
  chamados: Chamado[];
}

export interface QuadroChamados {
  empresa: Referencia | null;
  meus: boolean;
  dias: number;
  resumo: {
    em_aberto: number;
    aguardando_diagnostico: number;
    atrasados: number;
    aguardando_pecas: number;
    concluidos_periodo: number;
    diagnostico_no_prazo_pct: number | null;
    media_horas_diagnostico: number | null;
    media_horas_solucao: number | null;
  };
  colunas: ColunaQuadro[];
}

export interface RelatorioTecnico {
  id: number;
  codigo: string;
  chamado_id: number;
  tecnico: Referencia | null;
  empresa: Referencia;
  criado_em: string;
  atendido_em: string;
  equipamento: string | null;
  identificacao: string | null;
  diagnostico: string;
  causa: string | null;
  servico_executado: string | null;
  pecas: string | null;
  situacao_equipamento: SituacaoEquipamento;
  recomendacoes: string | null;
}

export interface Interacao {
  id: number;
  tipo: TipoInteracao;
  texto: string | null;
  /** Quando foi registrado no sistema. */
  criado_em: string;
  /** Resposta técnica e relatório: data e hora do diagnóstico informadas por quem registrou. */
  ocorrido_em: string | null;
  autor: Referencia | null;
  autor_papel: Perfil | null;
  relatorio: RelatorioTecnico | null;
  arquivo_nome: string | null;
  arquivo_mime: string | null;
  arquivo_tamanho: number | null;
}

export interface ChamadoDetalhe extends Chamado {
  interacoes: Interacao[];
  oficios: OficioVinculado[];
  pode_solicitar_pecas: boolean;
  pode_assumir: boolean;
  pode_responder: boolean;
  pode_comentar: boolean;
  pode_concluir: boolean;
  /** Corrigir a data e a hora do diagnóstico (técnico da empresa ou administrador). */
  pode_corrigir_diagnostico: boolean;
  /** A resposta técnica ou o relatório que contou como diagnóstico. */
  diagnostico_interacao_id: number | null;
  pode_reabrir: boolean;
  pode_cancelar: boolean;
}

export interface FiltrosChamado {
  status?: StatusChamado;
  empresa_id?: number;
  situacao?: SituacaoPrazo;
  busca?: string;
  meus?: boolean;
  pagina?: number;
}

export interface PainelEmpresa {
  empresa: Referencia;
  abertos: number;
  aguardando_diagnostico: number;
  atrasados: number;
  concluidos: number;
  diagnosticados: number;
  no_prazo_pct: number | null;
  media_horas_diagnostico: number | null;
  media_horas_solucao: number | null;
}

export interface PainelManutencao {
  papel: Perfil;
  eh_admin: boolean;
  empresa_do_tecnico: Referencia | null;
  abertos: number;
  em_atendimento: number;
  aguardando_diagnostico: number;
  vencendo: number;
  atrasados: number;
  concluidos: number;
  cancelados: number;
  por_empresa: PainelEmpresa[];
  urgentes: Chamado[];
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
  /** Chamado da Manutenção Clínica que originou o ofício (solicitação de peças/equipamentos). */
  chamado: { id: number; codigo: string; titulo: string } | null;
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
  dias_decorridos: number; // dias corridos da etapa atual: aguardando resposta/entrega, ou até a resposta
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

// ---------- Manutenção preventiva e avisos internos ----------

export type UnidadePeriodo = "DIAS" | "SEMANAS" | "MESES";
export type StatusPreventiva = "PROGRAMADA" | "REALIZADA" | "NAO_REALIZADA";
export type SituacaoPreventiva =
  | "PROGRAMADA"
  | "NA_JANELA"
  | "ATRASADA"
  | "REALIZADA"
  | "REALIZADA_COM_ATRASO"
  | "NAO_REALIZADA";

/** Rotina de preventiva de uma empresa técnica, com a periodicidade definida pelo administrador. */
export interface PlanoPreventiva {
  id: number;
  empresa: Referencia;
  titulo: string;
  descricao: string | null;
  local: string | null;
  equipamento: string | null;
  intervalo: number;
  unidade: UnidadePeriodo;
  /** "mensal", "a cada 45 dias"… */
  periodicidade: string;
  inicio: string;
  tolerancia_dias: number;
  ativo: boolean;
  proxima: string | null;
  previstas: number;
  realizadas: number;
  atrasadas: number;
}

/** Uma data prevista do plano, com o registro da realização e o ateste. */
export interface Preventiva {
  id: number;
  codigo: string;
  plano: Pick<PlanoPreventiva, "id" | "titulo" | "descricao" | "local" | "equipamento" | "tolerancia_dias" | "periodicidade">;
  empresa: Referencia;
  data_prevista: string;
  /** Último dia para contar como feita no prazo. */
  limite: string;
  status: StatusPreventiva;
  situacao: SituacaoPreventiva;
  /** Dias até a data prevista (negativo: já passou). */
  dias: number;
  realizada_em: string | null;
  executor: string | null;
  observacao: string | null;
  registrada_em: string | null;
  registrada_por: Referencia | null;
  arquivo_nome: string | null;
  arquivo_mime: string | null;
  arquivo_tamanho: number | null;
  motivo: string | null;
  atestada_em: string | null;
  atestada_por: Referencia | null;
  ateste_obs: string | null;
  pode_realizar: boolean;
  pode_atestar: boolean;
  pode_nao_realizar: boolean;
  pode_reabrir: boolean;
}

/** Previsto x realizado de uma empresa no período. */
export interface ResumoPreventivas {
  empresa: Referencia;
  previstas: number;
  realizadas: number;
  no_prazo: number;
  com_atraso: number;
  atrasadas: number;
  nao_realizadas: number;
  aguardando_ateste: number;
  atestadas: number;
  cumprimento_pct: number | null;
}

export interface PaginaPreventivas {
  de: string | null;
  ate: string | null;
  itens: Preventiva[];
  resumo: ResumoPreventivas[];
}

export interface FiltrosPreventiva {
  de?: string;
  ate?: string;
  empresa_id?: number;
  plano_id?: number;
  situacao?: SituacaoPreventiva;
  aguardando_ateste?: boolean;
}

export interface Aviso {
  chave: string;
  nivel: "CRITICO" | "ATENCAO" | "INFO";
  quantidade: number;
  titulo: string;
  link: string;
}

export interface Avisos {
  total: number;
  itens: Aviso[];
}

/** Unidade atendida por este servidor (UNIDADE_NOME e UNIDADE_DESCRICAO no .env). */
export interface Unidade {
  nome: string | null;
  descricao: string | null;
}

// ================= Controle de Tetos =================

export type PeriodoTeto = "DIARIO" | "MENSAL" | "ANUAL";
export type SituacaoTeto = "NORMAL" | "ATENCAO" | "ESTOURADO" | "SEM_TETO";

export interface SetorRef {
  id: number;
  nome: string;
}

export interface Setor extends SetorRef {
  descricao: string | null;
  ativo: boolean;
  usuarios: Referencia[];
  tipos: number;
}

export interface Equivalentes {
  diario: number;
  mensal: number;
  anual: number;
}

export interface VigenciaTeto {
  id: number;
  inicio: string;
  periodo: PeriodoTeto;
  valor: number;
  motivo: string | null;
  criado_por: Referencia | null;
  criado_em: string;
  equivalentes: Equivalentes;
}

export interface TipoTetoRef {
  id: number;
  nome: string;
  unidade: string;
}

export interface TipoTeto extends TipoTetoRef {
  setor: SetorRef;
  descricao: string | null;
  alerta_pct: number;
  ativo: boolean;
  periodo: PeriodoTeto | null;
  valor: number | null;
  vigente_desde: string | null;
  equivalentes: Equivalentes | null;
  lancamentos: number;
  vigencias: VigenciaTeto[];
}

export interface GastoTeto {
  id: number;
  tipo: TipoTetoRef;
  setor: SetorRef;
  data: string;
  valor: number;
  descricao: string;
  documento: string | null;
  arquivo_nome: string | null;
  arquivo_tamanho: number | null;
  registrado_por: Referencia | null;
  registrado_em: string;
  atualizado_por: Referencia | null;
  atualizado_em: string | null;
  pode_editar: boolean;
}

export interface PaginaGastos {
  itens: GastoTeto[];
  total: number;
  pagina: number;
  por_pagina: number;
  totais: { tipo: TipoTetoRef; total: number; quantidade: number }[];
}

export interface ConsumoTeto {
  gasto: number;
  teto: number;
  percentual: number | null;
  restante: number;
  situacao: SituacaoTeto;
}

export interface ConsumoMes extends ConsumoTeto {
  teto_ate_hoje: number;
  projecao: number;
  projecao_estoura: boolean;
}

export interface IndicadorTipo {
  tipo: TipoTeto;
  dia: ConsumoTeto;
  mes: ConsumoMes;
  ano: ConsumoTeto;
}

export interface PainelTetos {
  referencia: string;
  setores: { setor: SetorRef; tipos: IndicadorTipo[]; totais: { unidade: string; mes: ConsumoTeto; ano: ConsumoTeto }[] }[];
  estourados: number;
  em_atencao: number;
}

export interface IndicadoresTipo {
  referencia: string;
  ano: number;
  mes: number;
  resumo: IndicadorTipo;
  diario: { data: string; gasto: number; teto: number; acumulado: number; teto_acumulado: number }[];
  mensal: { mes: number; gasto: number; teto: number }[];
  anual: { ano: number; gasto: number; teto: number }[];
}

export interface ResumoTetos {
  eh_gestor: boolean;
  setor: SetorRef | null;
}
