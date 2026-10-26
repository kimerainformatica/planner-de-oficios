import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  BarChart3,
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  Layers,
  LayoutGrid,
  Percent,
  Search,
  Timer,
  Truck,
  X,
} from "lucide-react";
import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { analise, exportarPainel, listarOficios, prazos as buscarPrazos } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import {
  BarrasHorizontais,
  CartaoGrafico,
  LinhasTempo,
  TabelaMini,
  type LinhaBarra,
  type Serie,
} from "../components/graficos";
import { IconeAguardando, IconeOficios, IconeRecebimento } from "../components/Icones";
import { NumeroAnimado } from "../components/NumeroAnimado";
import { SeletorCliente } from "../components/SeletorCliente";
import { useToast } from "../components/Toast";
import { AlertaBadge, Botao, Carregando, ErroBox, StatusBadge } from "../components/ui";
import type { Destinatario, Filtros, Grupo, NivelAlerta, Prazos, StatusOficio, TipoOficio } from "../types";
import { salvarArquivo } from "../utils/arquivo";
import {
  data,
  decimal,
  diasUteis,
  hojeIso,
  mesCurto,
  porcentagem,
  ROTULO_DESTINATARIO,
  ROTULO_STATUS,
} from "../utils/formato";
import { useTipos } from "../utils/tipos";

// Cores por entidade (fixas, validadas para daltonismo): a mesma situação tem sempre a mesma cor.
// Ordem do empilhamento = caminho do ofício; os pares vizinhos foram validados (azul|amarelo|verde|laranja).
const SITUACAO: Serie[] = [
  { nome: "Pendentes de resposta", cor: "var(--serie-1)" },
  { nome: "Pendentes de recebimento", cor: "var(--serie-4)" },
  { nome: "Concluídos", cor: "var(--serie-3)" }, // recebidos + confirmados sem etapa de entrega
  { nome: "Não confirmados", cor: "var(--serie-2)" },
];
const MENSAL: Serie[] = [
  { nome: "Cadastrados", cor: "var(--serie-1)" },
  { nome: "Respondidos", cor: "var(--serie-2)" },
  { nome: "Recebidos", cor: "var(--serie-3)" },
];
const TEMPO: Serie[] = [{ nome: "Tempo médio (dias úteis)", cor: "var(--serie-1)" }];

const PERIODOS = {
  tudo: "Todo o período",
  mes: "Este mês",
  "3m": "Últimos 3 meses",
  "6m": "Últimos 6 meses",
  ano: "Este ano",
  personalizado: "Personalizado…",
} as const;
type Periodo = keyof typeof PERIODOS;

function inicioDoPeriodo(p: Periodo): string | undefined {
  const hoje = new Date();
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (p === "mes") return iso(new Date(hoje.getFullYear(), hoje.getMonth(), 1));
  if (p === "3m") return iso(new Date(hoje.getFullYear(), hoje.getMonth() - 2, 1));
  if (p === "6m") return iso(new Date(hoje.getFullYear(), hoje.getMonth() - 5, 1));
  if (p === "ano") return iso(new Date(hoje.getFullYear(), 0, 1));
  return undefined;
}

/** "45+ dias úteis", "30 a 44 dias úteis", "até 29 dias úteis" conforme a configuração do servidor. */
function faixa(nivel: NivelAlerta, p: Prazos): string {
  if (nivel === "CRITICO") return `${p.dias_critico}+ dias úteis`;
  if (nivel === "ATENCAO") return `${p.dias_atencao} a ${p.dias_critico - 1} dias úteis`;
  return `até ${p.dias_atencao - 1} dias úteis`;
}

const NOME_NIVEL: Record<NivelAlerta, string> = { CRITICO: "Crítico", ATENCAO: "Atenção", NORMAL: "No prazo" };

/** Visão geral: o que pede ação agora. Análise: gráficos e tabelas para acompanhar o período. */
const ABAS = { geral: "Visão geral", analise: "Análise" } as const;
type Aba = keyof typeof ABAS;

/** Filtros na URL: o painel pode ser recarregado e compartilhado com os mesmos filtros. */
function lerFiltros(sp: URLSearchParams): { periodo: Periodo; filtros: Filtros } {
  const periodo = (sp.get("periodo") as Periodo) in PERIODOS ? (sp.get("periodo") as Periodo) : "tudo";
  const personalizado = periodo === "personalizado";
  return {
    periodo,
    filtros: {
      data_inicio: personalizado ? sp.get("data_inicio") || undefined : inicioDoPeriodo(periodo),
      data_fim: personalizado ? sp.get("data_fim") || undefined : undefined,
      tipo: (sp.get("tipo") as TipoOficio) || undefined,
      destinatario_tipo: (sp.get("destinatario_tipo") as Destinatario) || undefined,
      status: (sp.get("status") as StatusOficio) || undefined,
      alerta: (sp.get("alerta") as NivelAlerta) || undefined,
      busca: sp.get("busca") || undefined,
      dono_id: sp.get("dono_id") ? Number(sp.get("dono_id")) : undefined,
    },
  };
}

function paraQuery(f: Filtros, extra: Record<string, string> = {}): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...f, ...extra })) if (v !== undefined && v !== "") qs.set(k, String(v));
  return qs.toString();
}

export function Painel() {
  const { ehAdmin, usuario } = useAuth();
  const tipos = useTipos();
  const avisar = useToast();
  const navegar = useNavigate();
  const [sp, setSp] = useSearchParams();
  const { periodo, filtros } = lerFiltros(sp);
  const aba: Aba = sp.get("aba") === "analise" ? "analise" : "geral";
  const [busca, setBusca] = useState(filtros.busca ?? "");
  const [exportando, setExportando] = useState<"xlsx" | "pdf" | null>(null);
  const prazos = useQuery({ queryKey: ["prazos"], queryFn: buscarPrazos, staleTime: Infinity });

  const consulta = useQuery({
    queryKey: ["analise", filtros],
    queryFn: () => analise(filtros),
    placeholderData: keepPreviousData, // ao trocar filtro, mantém o desenho anterior esmaecido
  });

  function mudar(novos: Record<string, string | undefined>) {
    const prox = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(novos)) {
      if (v) prox.set(k, v);
      else prox.delete(k);
    }
    setSp(prox, { replace: true });
  }

  // Busca com pequena espera para não consultar a cada tecla.
  useEffect(() => {
    const t = setTimeout(() => {
      if ((filtros.busca ?? "") !== busca.trim()) mudar({ busca: busca.trim() || undefined });
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busca]);

  async function exportar(formato: "xlsx" | "pdf") {
    setExportando(formato);
    try {
      const { blob, nome } = await exportarPainel(formato, filtros);
      salvarArquivo(blob, nome);
      avisar(`Relatório ${formato === "pdf" ? "PDF" : "Excel"} gerado.`);
    } catch (e) {
      avisar(e instanceof Error ? e.message : "Não foi possível exportar", "erro");
    } finally {
      setExportando(null);
    }
  }

  /** Clique num gráfico abre a lista de ofícios já filtrada por aquele grupo. */
  const abrirLista = (extra: Record<string, string>) => navegar(`/oficios?${paraQuery(filtros, extra)}`);

  const temFiltro = [...sp.keys()].some((k) => k !== "aba");
  function limparFiltros() {
    setBusca("");
    setSp(aba === "geral" ? new URLSearchParams() : new URLSearchParams({ aba }), { replace: true });
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Painel</h1>
          <p className="texto-suave">
            {ehAdmin ? "Todos os ofícios" : `Ofícios de ${usuario?.nome}`}
            {consulta.data && ` · situação em ${data(consulta.data.data_referencia)}`}
            {prazos.data &&
              ` · atenção a partir de ${prazos.data.dias_atencao} e crítico a partir de ${prazos.data.dias_critico} dias úteis`}
          </p>
        </div>
        <div className="grupo">
          <Botao className="btn btn-secundario" carregando={exportando === "xlsx"} onClick={() => exportar("xlsx")}>
            <FileSpreadsheet size={17} /> Exportar Excel
          </Botao>
          <Botao className="btn btn-secundario" carregando={exportando === "pdf"} onClick={() => exportar("pdf")}>
            <FileText size={17} /> Exportar PDF
          </Botao>
        </div>
      </header>

      <section className="filtros" aria-label="Filtros do painel">
        <div className="busca">
          <Search size={16} className="busca-icone" />
          <input className="input" placeholder="Buscar nº, protocolo, setor ou observação" value={busca}
            onChange={(e) => setBusca(e.target.value)}
            aria-label="Buscar por número, protocolo, setor/destino ou observação" />
        </div>
        <select className="input" aria-label="Período (data do ofício)" value={periodo}
          onChange={(e) => mudar({ periodo: e.target.value === "tudo" ? undefined : e.target.value,
            data_inicio: undefined, data_fim: undefined })}>
          {Object.entries(PERIODOS).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        {periodo === "personalizado" && (
          <div className="periodo">
            <input type="date" className="input" aria-label="De" max={hojeIso()} value={filtros.data_inicio ?? ""}
              onChange={(e) => mudar({ data_inicio: e.target.value || undefined })} />
            <span className="texto-suave">até</span>
            <input type="date" className="input" aria-label="Até" max={hojeIso()} value={filtros.data_fim ?? ""}
              onChange={(e) => mudar({ data_fim: e.target.value || undefined })} />
          </div>
        )}
        <select className="input" aria-label="Tipo de ofício" value={filtros.tipo ?? ""}
          onChange={(e) => mudar({ tipo: e.target.value || undefined })}>
          <option value="">Todos os tipos</option>
          {tipos.todos.map((t) => (
            <option key={t.codigo} value={t.codigo}>
              {t.nome}
            </option>
          ))}
        </select>
        <select className="input" aria-label="Destinatário" value={filtros.destinatario_tipo ?? ""}
          onChange={(e) => mudar({ destinatario_tipo: e.target.value || undefined })}>
          <option value="">Todos os destinatários</option>
          {Object.entries(ROTULO_DESTINATARIO).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        <select className="input" aria-label="Status" value={filtros.status ?? ""}
          onChange={(e) => mudar({ status: e.target.value || undefined })}>
          <option value="">Todos os status</option>
          {Object.entries(ROTULO_STATUS).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        <select className="input" aria-label="Prazo (pendentes de resposta ou de entrega)" value={filtros.alerta ?? ""}
          onChange={(e) => mudar({ alerta: e.target.value || undefined })}>
          <option value="">Qualquer prazo</option>
          {(["NORMAL", "ATENCAO", "CRITICO"] as const).map((n) => (
            <option key={n} value={n}>
              {NOME_NIVEL[n]}
              {prazos.data && ` (${faixa(n, prazos.data)})`}
            </option>
          ))}
        </select>
        {ehAdmin && (
          <SeletorCliente valor={filtros.dono_id} aoMudar={(id) => mudar({ dono_id: id ? String(id) : undefined })}
            rotuloVazio="Todos os clientes" />
        )}
        {temFiltro && (
          <button className="btn btn-fantasma" onClick={limparFiltros}>
            <X size={16} /> Limpar filtros
          </button>
        )}
      </section>

      <div className="abas" role="tablist" aria-label="Seções do painel"
        style={{ "--i": (Object.keys(ABAS) as Aba[]).indexOf(aba) } as CSSProperties}>
        {(Object.keys(ABAS) as Aba[]).map((chave) => (
          <button key={chave} type="button" role="tab" id={`aba-${chave}`} aria-selected={aba === chave}
            aria-controls="painel-aba" className={`aba ${aba === chave ? "ativa" : ""}`}
            onClick={() => mudar({ aba: chave === "geral" ? undefined : chave })}>
            {chave === "geral" ? <LayoutGrid size={16} /> : <BarChart3 size={16} />} {ABAS[chave]}
          </button>
        ))}
      </div>

      <div id="painel-aba" role="tabpanel" aria-labelledby={`aba-${aba}`}>
        {consulta.isPending ? (
          <Carregando />
        ) : consulta.isError ? (
          <ErroBox erro={consulta.error} />
        ) : aba === "geral" ? (
          <VisaoGeral a={consulta.data} recarregando={consulta.isFetching} filtros={filtros} />
        ) : (
          <Analise a={consulta.data} recarregando={consulta.isFetching} abrirLista={abrirLista} />
        )}
      </div>
    </>
  );
}

type DadosAnalise = Awaited<ReturnType<typeof analise>>;

function VisaoGeral({ a, recarregando, filtros }: { a: DadosAnalise; recarregando: boolean; filtros: Filtros }) {
  const i = a.indicadores;
  const qs = paraQuery(filtros);

  return (
    <div className={`painel-conteudo ${recarregando ? "recarregando" : ""}`}>
      <section className="indicadores indicadores-etapas">
        <CartaoEtapa titulo="Pendentes de resposta" subtitulo="Aguardando a resposta do destinatário"
          status="PENDENTE_RESPOSTA" total={i.pendentes} prazos={a.prazos} filtros={filtros}
          niveis={{ CRITICO: i.pendentes_critico, ATENCAO: i.pendentes_atencao, NORMAL: i.pendentes_normal }} />
        <CartaoEtapa titulo="Pendentes de recebimento" subtitulo="Resposta confirmada, entrega ainda não"
          status="PENDENTE_RECEBIMENTO" total={i.pendentes_recebimento} prazos={a.prazos} filtros={filtros}
          niveis={{ CRITICO: i.recebimento_critico, ATENCAO: i.recebimento_atencao, NORMAL: i.recebimento_normal }} />
        <div className="mosaico mosaico-2">
          <Indicador rotulo="Ofícios no filtro" valor={String(i.total)} link={`/oficios?${qs}`}
            icone={<Layers size={19} />} />
          <Indicador rotulo="Concluídos" valor={String(i.concluidos)} icone={<CheckCircle2 size={19} />}
            dica={`${i.recebidos} ${i.recebidos === 1 ? "recebido" : "recebidos"} · ${i.confirmados} ${
              i.confirmados === 1 ? "confirmado" : "confirmados"} sem entrega`}
            link={`/oficios?${paraQuery(filtros, { status: "RECEBIDO" })}`} />
          <Indicador rotulo="Não confirmados" valor={String(i.nao_confirmados)} dica="Podem ser reabertos"
            link={`/oficios?${paraQuery(filtros, { status: "NAO_CONFIRMADO" })}`} icone={<Ban size={19} />}
            neutro />
          <Indicador rotulo="Taxa de confirmação" valor={porcentagem(i.taxa_confirmacao)}
            dica="Respostas confirmadas ÷ respondidos" icone={<Percent size={19} />} />
          <Indicador rotulo="Tempo médio de resposta" icone={<Timer size={19} />}
            valor={i.tempo_medio_resposta === null ? "—" : decimal(i.tempo_medio_resposta)}
            unidade={i.tempo_medio_resposta === null ? undefined : "dias úteis"}
            dica={`${porcentagem(i.respondidos_no_prazo)} respondidos antes da atenção`} />
          <Indicador rotulo="Tempo médio de entrega" icone={<Truck size={19} />}
            valor={i.tempo_medio_entrega === null ? "—" : decimal(i.tempo_medio_entrega)}
            unidade={i.tempo_medio_entrega === null ? undefined : "dias úteis"}
            dica={`${porcentagem(i.entregues_no_prazo)} entregues antes da atenção`} />
        </div>
      </section>

      <div className="duas-colunas">
        <Fila nivel="CRITICO" titulo="Críticos — mais antigos primeiro" filtros={filtros} prazos={a.prazos} />
        <Fila nivel="ATENCAO" titulo="Em atenção — mais antigos primeiro" filtros={filtros} prazos={a.prazos} />
      </div>
    </div>
  );
}

function Analise({
  a,
  recarregando,
  abrirLista,
}: {
  a: DadosAnalise;
  recarregando: boolean;
  abrirLista: (extra: Record<string, string>) => void;
}) {
  const { ehAdmin } = useAuth();
  // Nos gráficos e tabelas o tipo aparece pelo rótulo curto (o nome completo de Peças não cabe no eixo)
  const tipos = useTipos();
  const porTipo = a.por_tipo.map((g) => ({ ...g, rotulo: g.chave ? tipos.rotulo(g.chave, true) : g.rotulo }));

  const situacao = (g: Grupo): LinhaBarra => ({
    chave: g.chave ?? "",
    rotulo: g.rotulo,
    valores: [g.pendentes, g.pendentes_recebimento, g.confirmados + g.recebidos, g.nao_confirmados],
  });
  const tabelaGrupos = (rotulo: string, grupos: Grupo[]) => (
    <TabelaMini
      cabecalho={[rotulo, "Total", "Pend. resposta", "Pend. receb.", "Atenção", "Críticos", "Recebidos", "Confirmados",
        "Não conf.", "Tempo resposta", "Tempo entrega"]}
      linhas={grupos.map((g) => [g.rotulo, g.total, g.pendentes, g.pendentes_recebimento, g.atencao, g.criticos,
        g.recebidos, g.confirmados, g.nao_confirmados, decimal(g.tempo_medio_resposta), decimal(g.tempo_medio_entrega)])}
    />
  );
  const respondidos = (g: Grupo) => g.confirmados + g.pendentes_recebimento + g.recebidos + g.nao_confirmados;
  const tempoPorTipo = (campo: "tempo_medio_resposta" | "tempo_medio_entrega"): LinhaBarra[] =>
    porTipo
      .filter((g) => g[campo] !== null)
      .map((g) => ({ chave: g.chave ?? "", rotulo: g.rotulo, valores: [g[campo] ?? 0], total: `${decimal(g[campo])} dias úteis` }));

  return (
    <div className={`painel-conteudo ${recarregando ? "recarregando" : ""}`}>
      <div className="duas-colunas">
        <CartaoGrafico titulo="Ofícios por tipo" subtitulo="Situação atual · clique numa barra para ver os ofícios"
          series={SITUACAO} carregando={recarregando} tabela={tabelaGrupos("Tipo", porTipo)}>
          <BarrasHorizontais linhas={porTipo.map(situacao)} series={SITUACAO}
            aoClicar={(chave) => chave && abrirLista({ tipo: chave })} />
        </CartaoGrafico>
        <CartaoGrafico titulo="Ofícios por destinatário" subtitulo="Situação atual · clique numa barra para ver os ofícios"
          series={SITUACAO} carregando={recarregando} tabela={tabelaGrupos("Destinatário", a.por_destinatario)}>
          <BarrasHorizontais linhas={a.por_destinatario.map(situacao)} series={SITUACAO}
            aoClicar={(chave) => chave && abrirLista({ destinatario_tipo: chave })} />
        </CartaoGrafico>
      </div>

      <CartaoGrafico titulo="Evolução mensal"
        subtitulo="Cadastrados pela data do ofício · respondidos pela data da resposta · recebidos pela data da entrega"
        series={MENSAL} carregando={recarregando} legendaLinha
        tabela={<TabelaMini cabecalho={["Mês", "Cadastrados", "Respondidos", "Recebidos"]}
          linhas={a.por_mes.map((m) => [mesCurto(m.mes), m.cadastrados, m.respondidos, m.recebidos])} />}>
        <LinhasTempo rotulos={a.por_mes.map((m) => mesCurto(m.mes))}
          dados={[a.por_mes.map((m) => m.cadastrados), a.por_mes.map((m) => m.respondidos),
            a.por_mes.map((m) => m.recebidos)]} series={MENSAL} />
      </CartaoGrafico>

      <div className="duas-colunas">
        <CartaoGrafico titulo="Tempo médio de resposta por tipo" subtitulo="Dias úteis do início do prazo até a resposta"
          carregando={recarregando}
          tabela={<TabelaMini cabecalho={["Tipo", "Respondidos", "Tempo médio (dias úteis)"]}
            linhas={porTipo.map((g) => [g.rotulo, respondidos(g), decimal(g.tempo_medio_resposta)])} />}>
          <BarrasHorizontais linhas={tempoPorTipo("tempo_medio_resposta")} series={TEMPO}
            rotuloVazio="Nenhum ofício respondido nos filtros escolhidos." formatar={(v) => decimal(v)}
            aoClicar={(chave) => chave && abrirLista({ tipo: chave })} />
        </CartaoGrafico>
        <CartaoGrafico titulo="Tempo médio de entrega por tipo" subtitulo="Dias úteis da resposta até o recebimento"
          carregando={recarregando}
          tabela={<TabelaMini cabecalho={["Tipo", "Recebidos", "Tempo médio (dias úteis)"]}
            linhas={porTipo.map((g) => [g.rotulo, g.recebidos, decimal(g.tempo_medio_entrega)])} />}>
          <BarrasHorizontais linhas={tempoPorTipo("tempo_medio_entrega")} series={TEMPO}
            rotuloVazio="Nenhuma entrega confirmada nos filtros escolhidos." formatar={(v) => decimal(v)}
            aoClicar={(chave) => chave && abrirLista({ tipo: chave, status: "RECEBIDO" })} />
        </CartaoGrafico>
      </div>

      <section className="painel-bloco">
        <h2>Principais setores e destinos</h2>
        {a.por_setor.length === 0 ? (
          <p className="texto-suave">Nenhum ofício com destinatário informado.</p>
        ) : (
          <div className="tabela-mini-box">{tabelaGrupos("Setor / destino", a.por_setor)}</div>
        )}
      </section>
      {ehAdmin && (
        <section className="painel-bloco">
          <h2>Por cliente</h2>
          {a.por_cliente.length === 0 ? (
            <p className="texto-suave">Nenhum ofício nos filtros escolhidos.</p>
          ) : (
            <div className="tabela-mini-box">{tabelaGrupos("Cliente", a.por_cliente)}</div>
          )}
        </section>
      )}
    </div>
  );
}

/** Uma etapa pendente (resposta ou entrega): total, distribuição por prazo e atalhos para a lista. */
function CartaoEtapa({
  titulo,
  subtitulo,
  status,
  total,
  niveis,
  prazos,
  filtros,
}: {
  titulo: string;
  subtitulo: string;
  status: StatusOficio;
  total: number;
  niveis: Record<NivelAlerta, number>;
  prazos: Prazos;
  filtros: Filtros;
}) {
  const link = (extra: Record<string, string> = {}) =>
    `/oficios?${paraQuery({ ...filtros, alerta: undefined }, { status, ordem: "antigos", ...extra })}`;
  const ordem: NivelAlerta[] = ["CRITICO", "ATENCAO", "NORMAL"];
  return (
    <div className="cartao destaque">
      <div className="destaque-topo">
        <span className={`destaque-ic destaque-ic-${status}`} aria-hidden>
          {status === "PENDENTE_RECEBIMENTO" ? <IconeRecebimento tamanho={24} /> : <IconeAguardando tamanho={24} />}
        </span>
        <div>
          <span className="cartao-rotulo">{titulo}</span>
          <small className="texto-suave bloco">{subtitulo}</small>
        </div>
        <Link to={link()} className="numero-heroi numero-link" aria-label={`${total}: ver os ofícios`}>
          <NumeroAnimado valor={String(total)} />
        </Link>
      </div>
      {total > 0 ? (
        <>
          <div className="barra-distribuicao" role="img"
            aria-label={ordem.map((n) => `${niveis[n]} ${NOME_NIVEL[n].toLowerCase()}`).join(", ")}>
            {ordem.map((n) => niveis[n] > 0 && <span key={n} className={`seg seg-${n}`} style={{ flexGrow: niveis[n] }} />)}
          </div>
          <ul className="legenda legenda-alerta legenda-vertical">
            {ordem.map((n) => (
              <li key={n}>
                <Link to={link({ alerta: n })}>
                  <span className={`chave-barra seg-${n}`} aria-hidden /> <strong>{niveis[n]}</strong>{" "}
                  {NOME_NIVEL[n].toLowerCase()} <small className="texto-suave">({faixa(n, prazos)})</small>
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="texto-suave">Nenhum ofício nesta etapa.</p>
      )}
    </div>
  );
}

function Indicador({
  rotulo,
  valor,
  unidade,
  dica,
  link,
  icone,
  neutro,
}: {
  rotulo: string;
  valor: string;
  unidade?: string;
  dica?: string;
  link?: string;
  icone?: ReactNode;
  neutro?: boolean;
}) {
  const corpo = (
    <>
      {icone && <span className={`indicador-ic ${neutro ? "neutro" : ""}`} aria-hidden>{icone}</span>}
      <span className="cartao-rotulo">{rotulo}</span>
      <span className="cartao-valor">
        <NumeroAnimado valor={valor} /> {unidade && <small className="unidade">{unidade}</small>}
      </span>
      {dica && <small className="texto-suave">{dica}</small>}
    </>
  );
  return link ? (
    <Link to={link} className="cartao indicador cartao-link">
      {corpo}
    </Link>
  ) : (
    <div className="cartao indicador">{corpo}</div>
  );
}

function Fila({ nivel, titulo, filtros, prazos }: { nivel: NivelAlerta; titulo: string; filtros: Filtros; prazos: Prazos }) {
  const { ehAdmin } = useAuth();
  const consultaFiltros = { ...filtros, alerta: nivel, ordem: "antigos" as const, por_pagina: 6 };
  const consulta = useQuery({
    queryKey: ["oficios", consultaFiltros],
    queryFn: () => listarOficios(consultaFiltros),
  });

  return (
    <section className={`painel-bloco fila-bloco fila-${nivel}`}>
      <div className="bloco-topo">
        <div className="fila-titulo">
          <span className="fila-ic" aria-hidden>
            <AlertTriangle size={18} />
          </span>
          <h2>{titulo}</h2>
          <small className="texto-suave">Pendentes de resposta ou de entrega · {faixa(nivel, prazos)}</small>
        </div>
        <Link to={`/oficios?${paraQuery(filtros, { alerta: nivel, ordem: "antigos" })}`} className="link">
          Ver todos <ArrowRight size={14} />
        </Link>
      </div>
      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : consulta.data.itens.length === 0 ? (
        <p className="texto-suave fila-vazia">Nenhum ofício neste nível.</p>
      ) : (
        <ul className="fila">
          {consulta.data.itens.map((o) => (
            <li key={o.id}>
              <Link to={`/oficios/${o.id}`} className="fila-item">
                <span className="fila-doc" aria-hidden>
                  <IconeOficios />
                </span>
                <div>
                  <strong>Ofício nº {o.numero}</strong>
                  <small className="texto-suave">
                    {data(o.data_oficio)}
                    {o.destinatario_tipo && ` · ${ROTULO_DESTINATARIO[o.destinatario_tipo]} ${o.destinatario_setor ?? ""}`}
                    {ehAdmin && ` · ${o.dono.nome}`}
                  </small>
                </div>
                <div className="fila-dir">
                  <span className="texto-suave">{diasUteis(o.dias_uteis_decorridos)}</span>
                  <StatusBadge status={o.status} curto />
                  <AlertaBadge nivel={o.nivel_alerta} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
