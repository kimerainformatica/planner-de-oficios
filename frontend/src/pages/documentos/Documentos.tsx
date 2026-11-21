import { useMutation, useQuery } from "@tanstack/react-query";
import { FilePen, FileText, Search, Signature } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { criarDocumento, listarDocumentos } from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Carregando, ErroBox, Paginacao } from "../../components/ui";
import type { StatusDocumento, TipoDocumento } from "../../types";
import { data } from "../../utils/formato";
import { NOME_TIPO_DOC, ROTULO_STATUS_DOC, SeloDocumento } from "./comum";

type Escopo = "todos" | "meus" | "assinar";
const ESCOPOS: Record<Escopo, string> = { todos: "Todos", meus: "Elaborados por mim", assinar: "Para assinar" };

/** Ofícios e memorandos redigidos no app: rascunhos, emitidos e os que aguardam a assinatura de quem está vendo. */
export function Documentos() {
  const navegar = useNavigate();
  const avisar = useToast();
  const [params, setParams] = useSearchParams();
  const escopo = (params.get("escopo") as Escopo) || "todos";
  const tipo = (params.get("tipo") as TipoDocumento) || undefined;
  const status = (params.get("status") as StatusDocumento) || undefined;
  const pagina = Number(params.get("pagina") || 1);
  const [busca, setBusca] = useState(params.get("busca") ?? "");

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

  const consulta = useQuery({
    queryKey: ["documentos", escopo, tipo, status, params.get("busca"), pagina],
    queryFn: () => listarDocumentos({ escopo, tipo, status, busca: params.get("busca") || undefined, pagina }),
  });
  const novo = useMutation({
    mutationFn: criarDocumento,
    onSuccess: (d) => navegar(`/documentos/${d.id}`, { replace: true }),
    onError: (e) => avisar(e.message, "erro"),
  });
  const pedido = params.get("novo");
  const pedidoFeito = useRef<string | null>(null);
  useEffect(() => {
    if ((pedido === "OFICIO" || pedido === "MEMORANDO") && pedidoFeito.current !== pedido) {
      pedidoFeito.current = pedido;
      novo.mutate(pedido);
    }
  }, [pedido]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Documentos</h1>
          <p className="texto-suave">
            Ofícios e memorandos redigidos aqui saem no modelo da unidade (timbrado, margens e fontes), com número,
            data e código de verificação. O ofício pode ser registrado no Planner de Ofícios na emissão.
          </p>
        </div>
        <div className="grupo">
          <Botao className="btn btn-secundario" carregando={novo.isPending && novo.variables === "MEMORANDO"}
            onClick={() => novo.mutate("MEMORANDO")}>
            <FileText size={18} /> Novo memorando
          </Botao>
          <Botao carregando={novo.isPending && novo.variables === "OFICIO"} onClick={() => novo.mutate("OFICIO")}>
            <FilePen size={18} /> Novo ofício
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

      <div className="grupo filtros-tetos">
        <div className="busca-tetos">
          <Search size={16} aria-hidden />
          <input className="input" type="search" placeholder="Assunto, destinatário, setor ou código" value={busca}
            aria-label="Buscar documentos" onChange={(e) => setBusca(e.target.value)} />
        </div>
        <select className="input" aria-label="Tipo" value={tipo ?? ""} onChange={(e) => mudar({ tipo: e.target.value || undefined })}>
          <option value="">Ofícios e memorandos</option>
          {(Object.keys(NOME_TIPO_DOC) as TipoDocumento[]).map((t) => <option key={t} value={t}>{NOME_TIPO_DOC[t]}s</option>)}
        </select>
        <select className="input" aria-label="Situação" value={status ?? ""}
          onChange={(e) => mudar({ status: e.target.value || undefined })}>
          <option value="">Todas as situações</option>
          {(Object.keys(ROTULO_STATUS_DOC) as StatusDocumento[]).map((s) => <option key={s} value={s}>{ROTULO_STATUS_DOC[s]}</option>)}
        </select>
      </div>

      {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : consulta.data.total === 0 ? (
        <div className="aviso-vazio" role="status">
          {escopo === "assinar" ? "Nenhum documento aguardando a sua assinatura." : "Nenhum documento por aqui ainda. Comece por um novo ofício ou memorando."}
        </div>
      ) : (
        <>
          <div className="tabela-box">
            <table className="tabela tabela-tetos">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Assunto</th>
                  <th>Para</th>
                  <th>Elaborado por</th>
                  <th>Data</th>
                  <th className="num">Assinaturas no app</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {consulta.data.itens.map((d) => (
                  <tr key={d.id} className="linha-clicavel" onClick={() => navegar(`/documentos/${d.id}`)}>
                    <td>
                      <a href={`/documentos/${d.id}`} className="link-forte" onClick={(e) => { e.preventDefault(); navegar(`/documentos/${d.id}`); }}>
                        {d.titulo}
                      </a>
                    </td>
                    <td>{d.assunto || <span className="texto-suave">Sem assunto</span>}</td>
                    <td>{d.destino ?? <span className="texto-suave">—</span>}</td>
                    <td>{d.elaborador_nome}</td>
                    <td className="sem-quebra">{d.data_documento ? data(d.data_documento) : <span className="texto-suave">—</span>}</td>
                    <td className="num">
                      {d.status === "RASCUNHO" ? <span className="texto-suave">—</span> : `${d.assinaturas} de ${d.assinaturas_previstas}`}
                      {d.minha_assinatura_pendente && <span className="selo-teto selo-teto-ATENCAO selo-assinar">Falta a sua</span>}
                    </td>
                    <td><SeloDocumento status={d.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={pagina} total={consulta.data.total} porPagina={consulta.data.por_pagina}
            aoMudar={(p) => mudar({ pagina: String(p) })} />
        </>
      )}
    </>
  );
}
