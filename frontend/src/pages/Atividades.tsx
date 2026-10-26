import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { listarAtividades } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { ListaAtividades } from "../components/Atividades";
import { SeletorCliente } from "../components/SeletorCliente";
import { Carregando, ErroBox, Paginacao, Vazio } from "../components/ui";
import type { FiltrosAtividade } from "../types";
import { hojeIso, ROTULO_ACAO } from "../utils/formato";

const POR_PAGINA = 50;

export function Atividades() {
  const { ehAdmin } = useAuth();
  const [sp, setSp] = useSearchParams();
  const filtros: FiltrosAtividade = {
    usuario_id: sp.get("usuario_id") ? Number(sp.get("usuario_id")) : undefined,
    acao: sp.get("acao") || undefined,
    data_inicio: sp.get("data_inicio") || undefined,
    data_fim: sp.get("data_fim") || undefined,
    pagina: sp.get("pagina") ? Number(sp.get("pagina")) : 1,
    por_pagina: POR_PAGINA,
  };
  const consulta = useQuery({
    queryKey: ["atividades", filtros],
    queryFn: () => listarAtividades(filtros),
    placeholderData: keepPreviousData,
  });

  function mudar(novos: Record<string, string | undefined>) {
    const prox = new URLSearchParams(sp);
    for (const [k, v] of Object.entries({ pagina: undefined, ...novos })) {
      if (v) prox.set(k, v);
      else prox.delete(k);
    }
    setSp(prox, { replace: true });
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Atividades</h1>
          <p className="texto-suave">
            {ehAdmin
              ? "Tudo o que foi alterado na plataforma, por quem e quando."
              : "O que você fez e o que foi feito nos seus ofícios."}
          </p>
        </div>
      </header>

      <section className="filtros">
        {ehAdmin && (
          <SeletorCliente valor={filtros.usuario_id} rotuloVazio="Todos os usuários"
            aoMudar={(id) => mudar({ usuario_id: id ? String(id) : undefined })} />
        )}
        <select className="input" aria-label="Tipo de atividade" value={filtros.acao ?? ""}
          onChange={(e) => mudar({ acao: e.target.value || undefined })}>
          <option value="">Todas as atividades</option>
          {Object.entries(ROTULO_ACAO).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        <div className="periodo">
          <input type="date" className="input" aria-label="De" max={hojeIso()} value={filtros.data_inicio ?? ""}
            onChange={(e) => mudar({ data_inicio: e.target.value || undefined })} />
          <span className="texto-suave">até</span>
          <input type="date" className="input" aria-label="Até" max={hojeIso()} value={filtros.data_fim ?? ""}
            onChange={(e) => mudar({ data_fim: e.target.value || undefined })} />
        </div>
        {[...sp.keys()].length > 0 && (
          <button className="btn btn-fantasma" onClick={() => setSp(new URLSearchParams(), { replace: true })}>
            <X size={16} /> Limpar filtros
          </button>
        )}
      </section>

      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : consulta.data.itens.length === 0 ? (
        <Vazio>Nenhuma atividade encontrada.</Vazio>
      ) : (
        <>
          <section className={`painel-bloco ${consulta.isFetching ? "recarregando" : ""}`}>
            <ListaAtividades itens={consulta.data.itens} />
          </section>
          <Paginacao pagina={filtros.pagina ?? 1} total={consulta.data.total} porPagina={POR_PAGINA}
            aoMudar={(p) => mudar({ pagina: String(p) })} />
        </>
      )}
    </>
  );
}
