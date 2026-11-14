import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { PlusCircle, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { listarChamados, listarEmpresas } from "../../api/endpoints";
import { Carregando, ErroBox, Paginacao, Vazio } from "../../components/ui";
import type { FiltrosChamado, SituacaoPrazo, StatusChamado } from "../../types";
import { dataHora } from "../../utils/formato";
import { ROTULO_SITUACAO, ROTULO_STATUS_CHAMADO } from "../../utils/manutencao";
import { BadgePrazo, BadgeStatusChamado, useResumoManutencao } from "./comum";

/** Lista de chamados. Os filtros ficam no endereço (podem ser compartilhados). */
export function Chamados() {
  const [sp, setSp] = useSearchParams();
  const navegar = useNavigate();
  const resumo = useResumoManutencao().data;
  const filtros: FiltrosChamado = {
    status: (sp.get("status") as StatusChamado) || undefined,
    situacao: (sp.get("situacao") as SituacaoPrazo) || undefined,
    empresa_id: sp.get("empresa_id") ? Number(sp.get("empresa_id")) : undefined,
    busca: sp.get("busca") || undefined,
    meus: sp.get("meus") === "1" || undefined,
    pagina: Number(sp.get("pagina") ?? 1),
  };
  const [busca, setBusca] = useState(filtros.busca ?? "");

  function mudar(novos: Partial<FiltrosChamado>) {
    const proximo = { ...filtros, ...novos, pagina: novos.pagina ?? 1 };
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(proximo)) {
      if (v === undefined || v === null || v === "" || v === false || (k === "pagina" && v === 1)) continue;
      params.set(k, v === true ? "1" : String(v));
    }
    setSp(params, { replace: true });
  }

  // busca com uma pequena espera enquanto digita
  useEffect(() => {
    const t = setTimeout(() => {
      if ((filtros.busca ?? "") !== busca.trim()) mudar({ busca: busca.trim() || undefined });
    }, 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busca]);

  const consulta = useQuery({
    queryKey: ["chamados", filtros],
    queryFn: () => listarChamados(filtros),
    placeholderData: keepPreviousData,
  });
  const empresas = useQuery({ queryKey: ["empresas-manutencao"], queryFn: () => listarEmpresas() });
  const temFiltro = Boolean(filtros.status || filtros.situacao || filtros.empresa_id || filtros.busca || filtros.meus);
  const podeAbrir = resumo && (resumo.perfil === "CLIENTE" || resumo.eh_admin);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Chamados</h1>
          <p className="texto-suave">
            {consulta.data ? `${consulta.data.total} encontrado(s)` : " "}
            {resumo?.empresa && ` · chamados da ${resumo.empresa.nome}`}
          </p>
        </div>
        {podeAbrir && (
          <Link to="/manutencao/chamados/novo" className="btn btn-primario">
            <PlusCircle size={18} /> Abrir chamado
          </Link>
        )}
      </header>

      <section className="filtros">
        <div className="busca">
          <Search size={16} className="busca-icone" />
          <input className="input" placeholder="Buscar nº (CH-…), título, local ou equipamento" value={busca}
            onChange={(e) => setBusca(e.target.value)} aria-label="Buscar chamados" />
        </div>
        <select className="input" aria-label="Status" value={filtros.status ?? ""}
          onChange={(e) => mudar({ status: (e.target.value as StatusChamado) || undefined })}>
          <option value="">Todos os status</option>
          {Object.entries(ROTULO_STATUS_CHAMADO).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
        </select>
        <select className="input" aria-label="Prazo" value={filtros.situacao ?? ""}
          onChange={(e) => mudar({ situacao: (e.target.value as SituacaoPrazo) || undefined })}>
          <option value="">Qualquer prazo</option>
          {Object.entries(ROTULO_SITUACAO).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
        </select>
        {!resumo?.eh_tecnico && (
          <select className="input" aria-label="Empresa" value={filtros.empresa_id ?? ""}
            onChange={(e) => mudar({ empresa_id: e.target.value ? Number(e.target.value) : undefined })}>
            <option value="">Todas as empresas</option>
            {(empresas.data ?? []).map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
          </select>
        )}
        <label className="checkbox">
          <input type="checkbox" checked={Boolean(filtros.meus)} onChange={(e) => mudar({ meus: e.target.checked || undefined })} />
          {resumo?.eh_tecnico ? "Só os que assumi" : "Só os que abri"}
        </label>
        {temFiltro && (
          <button className="btn btn-fantasma" onClick={() => { setBusca(""); setSp(new URLSearchParams(), { replace: true }); }}>
            <X size={16} /> Limpar filtros
          </button>
        )}
      </section>

      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : consulta.data.itens.length === 0 ? (
        <Vazio>{temFiltro ? "Nenhum chamado com esses filtros." : "Nenhum chamado aberto ainda."}</Vazio>
      ) : (
        <>
          <ul className="fila lista-mobile">
            {consulta.data.itens.map((c) => (
              <li key={c.id}>
                <Link to={`/manutencao/chamados/${c.id}`} className={`fila-item chamado-item-${c.prazo.situacao}`}>
                  <div>
                    <strong>{c.codigo} · {c.titulo}</strong>
                    <small className="texto-suave">{c.empresa.nome} · {dataHora(c.aberto_em)}{c.local && ` · ${c.local}`}</small>
                  </div>
                  <div className="fila-dir">
                    <BadgeStatusChamado status={c.status} />
                    <BadgePrazo prazo={c.prazo} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <div className="tabela-box tabela-oficios">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nº</th>
                  <th>Chamado</th>
                  <th>Empresa</th>
                  <th>Aberto em</th>
                  <th>Prazo do diagnóstico</th>
                  <th>Status</th>
                  <th>Técnico</th>
                </tr>
              </thead>
              <tbody>
                {consulta.data.itens.map((c) => (
                  <tr key={c.id} className={`linha-clicavel chamado-linha-${c.prazo.situacao}`}
                    onClick={() => navegar(`/manutencao/chamados/${c.id}`)}>
                    <td>
                      <Link to={`/manutencao/chamados/${c.id}`} className="link-forte" onClick={(e) => e.stopPropagation()}>
                        {c.codigo}
                      </Link>
                    </td>
                    <td className="celula-texto" title={c.descricao}>
                      {c.titulo}
                      <small className="celula-sub">
                        {[c.local, c.equipamento].filter(Boolean).join(" · ") || `Aberto por ${c.solicitante.nome}`}
                      </small>
                    </td>
                    <td>{c.empresa.nome}</td>
                    <td>{dataHora(c.aberto_em)}</td>
                    <td>
                      <BadgePrazo prazo={c.prazo} comTexto />
                      <small className="celula-sub">até {dataHora(c.prazo_em)}</small>
                    </td>
                    <td><BadgeStatusChamado status={c.status} /></td>
                    <td>{c.tecnico?.nome ?? <span className="texto-suave">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao pagina={consulta.data.pagina} total={consulta.data.total} porPagina={consulta.data.por_pagina}
            aoMudar={(pagina) => mudar({ pagina })} />
        </>
      )}
    </>
  );
}
