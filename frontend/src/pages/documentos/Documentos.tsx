import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, LayoutList, Search, Signature, SquareKanban } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  criarDocumento, listarDocumentos, listarModelos, listarPastas, quadroDocumentos, type FiltrosDocumentos,
} from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Carregando, ErroBox, Paginacao } from "../../components/ui";
import type { Documento, DocumentoResumo, EtapaDocumento, QuadroDocumentos } from "../../types";
import { data } from "../../utils/formato";
import { EtiquetaPasta, ModalNovoDocumento, ROTULO_ETAPA, SeloEtapa, SeloPrazo } from "./comum";

type Escopo = "todos" | "meus" | "assinar";
const ESCOPOS: Record<Escopo, string> = { todos: "Todos", meus: "Elaborados por mim", assinar: "Para assinar" };
const PRAZOS = { com_prazo: "Com prazo", alerta: "Vencidos ou vencendo", atrasados: "Atrasados" } as const;
type Prazo = keyof typeof PRAZOS;

/**
 * Planner de documentos: os documentos redigidos no app (de todos os modelos da instituição) em lista ou em quadro
 * por etapa, com filtros por modelo, pasta, etapa e prazo. `?novo=CODIGO` começa um documento do modelo
 * (o Planner de Ofícios usa `?novo=OFICIO`); `?novo=escolher` abre a escolha do modelo.
 */
export function Documentos() {
  const navegar = useNavigate();
  const avisar = useToast();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const escopo = (params.get("escopo") as Escopo) || "todos";
  const visao = params.get("visao") === "quadro" ? "quadro" : "lista";
  const pasta = params.get("pasta");
  const filtros: FiltrosDocumentos = {
    escopo,
    tipo: params.get("tipo") || undefined,
    pasta_id: pasta ? Number(pasta) : undefined,
    prazo: (params.get("prazo") as Prazo) || undefined,
    busca: params.get("busca") || undefined,
  };
  const etapa = (params.get("etapa") as EtapaDocumento) || undefined;
  const ordem = params.get("ordem") === "prazo" ? "prazo" : "recentes";
  const pagina = Number(params.get("pagina") || 1);
  const [busca, setBusca] = useState(params.get("busca") ?? "");
  const [escolhendo, setEscolhendo] = useState(false);

  function mudar(novos: Record<string, string | undefined>) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(novos)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (!("pagina" in novos)) p.delete("pagina");
    setParams(p, { replace: true });
  }

  useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("busca") ?? "") !== busca.trim()) mudar({ busca: busca.trim() || undefined });
    }, 350);
    return () => clearTimeout(t);
  }); // eslint-disable-line react-hooks/exhaustive-deps

  const modelos = useQuery({ queryKey: ["modelos-documento"], queryFn: listarModelos });
  const pastas = useQuery({ queryKey: ["pastas-documento"], queryFn: listarPastas });
  const lista = useQuery({
    queryKey: ["documentos", "lista", filtros, etapa, ordem, pagina],
    queryFn: () => listarDocumentos({ ...filtros, etapa, ordem, pagina }),
    enabled: visao === "lista",
  });
  const quadro = useQuery({
    queryKey: ["documentos", "quadro", filtros],
    queryFn: () => quadroDocumentos(filtros),
    enabled: visao === "quadro",
  });

  const abrir = (d: Documento) => {
    qc.invalidateQueries({ queryKey: ["documentos"] });
    navegar(`/documentos/${d.id}`, { replace: true });
  };
  const novo = useMutation({
    mutationFn: (tipo: string) => criarDocumento(tipo, filtros.pasta_id ? { pasta_id: filtros.pasta_id } : {}),
    onSuccess: abrir,
    onError: (e) => avisar(e.message, "erro"),
  });
  const pedido = params.get("novo");
  const pedidoFeito = useRef<string | null>(null);
  useEffect(() => {
    if (!pedido) {
      pedidoFeito.current = null;
      return;
    }
    if (pedidoFeito.current === pedido) return;
    pedidoFeito.current = pedido;
    if (pedido === "escolher") {
      setEscolhendo(true);
      mudar({ novo: undefined });
    } else {
      novo.mutate(pedido);
    }
  }, [pedido]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtrando = Boolean(filtros.tipo || pasta || filtros.prazo || filtros.busca || etapa);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Documentos</h1>
          <p className="texto-suave">
            Os documentos da instituição, redigidos aqui nos modelos da unidade (timbrado, margens e fontes), com número,
            data e código de verificação. Organize por pasta, acompanhe os prazos e veja em que etapa cada um está.
          </p>
        </div>
        <div className="grupo">
          <div className="alternar-visao" role="group" aria-label="Visão">
            <button type="button" className={visao === "lista" ? "ativo" : ""} aria-pressed={visao === "lista"}
              onClick={() => mudar({ visao: undefined })}>
              <LayoutList size={16} aria-hidden /> Lista
            </button>
            <button type="button" className={visao === "quadro" ? "ativo" : ""} aria-pressed={visao === "quadro"}
              onClick={() => mudar({ visao: "quadro", etapa: undefined, ordem: undefined })}>
              <SquareKanban size={16} aria-hidden /> Quadro
            </button>
          </div>
          <Botao carregando={novo.isPending} onClick={() => setEscolhendo(true)}>
            <FilePlus2 size={18} /> Novo documento
          </Botao>
        </div>
      </header>

      <div className="abas abas-3 abas-documentos" role="tablist" aria-label="Quais documentos"
        style={{ "--i": (Object.keys(ESCOPOS) as Escopo[]).indexOf(escopo) } as CSSProperties}>
        {(Object.keys(ESCOPOS) as Escopo[]).map((chave) => (
          <button key={chave} type="button" role="tab" aria-selected={escopo === chave}
            className={`aba ${escopo === chave ? "ativa" : ""}`}
            onClick={() => mudar({ escopo: chave === "todos" ? undefined : chave })}>
            {chave === "assinar" && <Signature size={16} />} {ESCOPOS[chave]}
          </button>
        ))}
      </div>

      <div className="grupo filtros-documentos">
        <div className="busca-documentos">
          <Search size={16} aria-hidden />
          <input className="input" type="search" placeholder="Assunto, destinatário, setor ou código" value={busca}
            aria-label="Buscar documentos" onChange={(e) => setBusca(e.target.value)} />
        </div>
        <select className="input" aria-label="Modelo" value={filtros.tipo ?? ""}
          onChange={(e) => mudar({ tipo: e.target.value || undefined })}>
          <option value="">Todos os modelos</option>
          {modelos.data?.map((m) => (
            <option key={m.codigo} value={m.codigo}>{m.nome}{m.ativo ? "" : " (desativado)"}</option>
          ))}
        </select>
        <select className="input" aria-label="Pasta" value={pasta ?? ""} onChange={(e) => mudar({ pasta: e.target.value || undefined })}>
          <option value="">Todas as pastas</option>
          <option value="0">Sem pasta</option>
          {pastas.data?.map((p) => <option key={p.id} value={p.id}>{p.nome}{p.ativo ? "" : " (desativada)"}</option>)}
        </select>
        {visao === "lista" && (
          <select className="input" aria-label="Etapa" value={etapa ?? ""} onChange={(e) => mudar({ etapa: e.target.value || undefined })}>
            <option value="">Todas as etapas</option>
            {(Object.keys(ROTULO_ETAPA) as EtapaDocumento[]).map((e) => <option key={e} value={e}>{ROTULO_ETAPA[e]}</option>)}
          </select>
        )}
        <select className="input" aria-label="Prazo" value={filtros.prazo ?? ""} onChange={(e) => mudar({ prazo: e.target.value || undefined })}>
          <option value="">Qualquer prazo</option>
          {(Object.keys(PRAZOS) as Prazo[]).map((p) => <option key={p} value={p}>{PRAZOS[p]}</option>)}
        </select>
        {visao === "lista" && (
          <select className="input" aria-label="Ordem" value={ordem}
            onChange={(e) => mudar({ ordem: e.target.value === "prazo" ? "prazo" : undefined })}>
            <option value="recentes">Mais recentes primeiro</option>
            <option value="prazo">Prazo mais próximo primeiro</option>
          </select>
        )}
      </div>

      {visao === "quadro" ? (
        quadro.isPending ? <Carregando /> : quadro.isError ? <ErroBox erro={quadro.error} /> : (
          <Quadro quadro={quadro.data} aoVerTodos={(e) => mudar({ visao: undefined, etapa: e })} />
        )
      ) : lista.isPending ? <Carregando /> : lista.isError ? <ErroBox erro={lista.error} /> : lista.data.total === 0 ? (
        <div className="aviso-vazio" role="status">
          {escopo === "assinar" && !filtrando ? "Nenhum documento aguardando a sua assinatura."
            : filtrando ? "Nenhum documento com estes filtros." : "Nenhum documento por aqui ainda. Comece por um novo documento."}
        </div>
      ) : (
        <>
          <div className="tabela-box">
            <table className="tabela tabela-documentos">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Assunto</th>
                  <th>Data</th>
                  <th>Prazo</th>
                  <th className="num">Assinaturas</th>
                  <th>Etapa</th>
                </tr>
              </thead>
              <tbody>
                {lista.data.itens.map((d) => (
                  <tr key={d.id} className="linha-clicavel" onClick={() => navegar(`/documentos/${d.id}`)}>
                    <td>
                      <a href={`/documentos/${d.id}`} className="link-forte" onClick={(e) => { e.preventDefault(); navegar(`/documentos/${d.id}`); }}>
                        {d.titulo}
                      </a>
                      <small className="celula-sub">{d.elaborador_nome}</small>
                    </td>
                    <td>
                      {d.assunto || <span className="texto-suave">Sem assunto</span>}
                      {d.destino && <small className="celula-sub">Para: {d.destino}</small>}
                      {d.pasta_nome && <span className="bloco-etiqueta"><EtiquetaPasta nome={d.pasta_nome} /></span>}
                    </td>
                    <td className="sem-quebra">{d.data_documento ? data(d.data_documento) : <span className="texto-suave">—</span>}</td>
                    <td className="sem-quebra">{d.prazo ? <SeloPrazo doc={d} /> : <span className="texto-suave">—</span>}</td>
                    <td className="num">
                      {d.status === "RASCUNHO" ? <span className="texto-suave">—</span> : `${d.assinaturas} de ${d.assinaturas_previstas}`}
                      {d.minha_assinatura_pendente && <span className="selo-doc selo-doc-ATENCAO selo-assinar">Falta a sua</span>}
                    </td>
                    <td><SeloEtapa etapa={d.etapa} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={pagina} total={lista.data.total} porPagina={lista.data.por_pagina}
            aoMudar={(p) => mudar({ pagina: String(p) })} />
        </>
      )}

      {escolhendo && (
        <ModalNovoDocumento pastaId={filtros.pasta_id || undefined} aoFechar={() => setEscolhendo(false)} aoCriar={abrir} />
      )}
    </>
  );
}

/** As etapas lado a lado; em cada coluna, os prazos mais próximos primeiro (concluídos e cancelados: os recentes). */
function Quadro({ quadro, aoVerTodos }: { quadro: QuadroDocumentos; aoVerTodos: (etapa: EtapaDocumento) => void }) {
  return (
    <div className="quadro-documentos">
      {quadro.colunas.map((c) => (
        <section key={c.etapa} className={`coluna-quadro coluna-${c.etapa}`} aria-label={`${ROTULO_ETAPA[c.etapa]}: ${c.total}`}>
          <header className="coluna-quadro-topo">
            <h2>{ROTULO_ETAPA[c.etapa]}</h2>
            <span className="contador-coluna">{c.total}</span>
          </header>
          <div className="coluna-quadro-itens">
            {c.itens.length === 0 ? <p className="texto-suave coluna-vazia">Nenhum documento.</p>
              : c.itens.map((d) => <CartaoDocumento key={d.id} d={d} />)}
            {c.total > c.itens.length && (
              <button type="button" className="btn btn-fantasma btn-pequeno" onClick={() => aoVerTodos(c.etapa)}>
                Ver os {c.total} na lista
              </button>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

function CartaoDocumento({ d }: { d: DocumentoResumo }) {
  return (
    <Link to={`/documentos/${d.id}`} className={`cartao-doc${d.alerta_prazo ? ` prazo-${d.alerta_prazo}` : ""}`}>
      <span className="cartao-doc-titulo">{d.titulo}</span>
      <span className="cartao-doc-assunto">{d.assunto || "Sem assunto"}</span>
      {(d.prazo || d.minha_assinatura_pendente || d.pasta_nome) && (
        <span className="cartao-doc-selos">
          <SeloPrazo doc={d} />
          {d.minha_assinatura_pendente && <span className="selo-doc selo-doc-ATENCAO">Falta a sua</span>}
          <EtiquetaPasta nome={d.pasta_nome} />
        </span>
      )}
      <small className="texto-suave">
        {d.elaborador_nome}
        {d.status !== "RASCUNHO" && ` · ${d.assinaturas} de ${d.assinaturas_previstas} assinatura${d.assinaturas_previstas === 1 ? "" : "s"}`}
      </small>
    </Link>
  );
}
