import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronRight, FilePlus2, Paperclip, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { listarOficios } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { SeletorCliente } from "../components/SeletorCliente";
import { AlertaBadge, Carregando, ErroBox, Paginacao, StatusBadge, Vazio } from "../components/ui";
import type { Destinatario, FiltrosOficio, NivelAlerta, Oficio, StatusOficio, TipoOficio } from "../types";
import {
  data,
  destinatarioTexto,
  diasUteis,
  ROTULO_ALERTA,
  ROTULO_DESTINATARIO,
  ROTULO_STATUS,
} from "../utils/formato";
import { useTipos } from "../utils/tipos";

const POR_PAGINA = 20;

/** Os filtros ficam na URL: dá para voltar, recarregar e mandar o link para alguém. */
function lerFiltros(sp: URLSearchParams): FiltrosOficio {
  const num = (k: string) => (sp.get(k) ? Number(sp.get(k)) : undefined);
  return {
    status: (sp.get("status") as StatusOficio) || undefined,
    alerta: (sp.get("alerta") as NivelAlerta) || undefined,
    tipo: (sp.get("tipo") as TipoOficio) || undefined,
    destinatario_tipo: (sp.get("destinatario_tipo") as Destinatario) || undefined,
    busca: sp.get("busca") || undefined,
    dono_id: num("dono_id"),
    data_inicio: sp.get("data_inicio") || undefined,
    data_fim: sp.get("data_fim") || undefined,
    ordem: (sp.get("ordem") as FiltrosOficio["ordem"]) || "recentes",
    pagina: num("pagina") ?? 1,
    por_pagina: POR_PAGINA,
  };
}

/** "respondido em 55 dias úteis" seguido de "entregue em 20 dias úteis" (ou da espera pela entrega). */
function TextoPrazo({ oficio: o }: { oficio: Oficio }) {
  if (o.status === "PENDENTE_RESPOSTA") return <small className="celula-sub">{diasUteis(o.dias_uteis_decorridos)}</small>;
  return (
    <>
      {o.dias_resposta !== null && <small className="celula-sub">respondido em {diasUteis(o.dias_resposta)}</small>}
      {o.dias_entrega !== null && <small className="celula-sub">entregue em {diasUteis(o.dias_entrega)}</small>}
      {o.status === "PENDENTE_RECEBIMENTO" && (
        <small className="celula-sub">aguardando entrega há {diasUteis(o.dias_uteis_decorridos)}</small>
      )}
    </>
  );
}

export function Oficios() {
  const { ehAdmin } = useAuth();
  const tipos = useTipos();
  const navegar = useNavigate();
  const [sp, setSp] = useSearchParams();
  const filtros = lerFiltros(sp);
  const [busca, setBusca] = useState(filtros.busca ?? "");

  const consulta = useQuery({
    queryKey: ["oficios", filtros],
    queryFn: () => listarOficios(filtros),
    placeholderData: keepPreviousData,
  });

  function mudar(novos: Partial<FiltrosOficio>) {
    const prox = new URLSearchParams(sp);
    for (const [k, v] of Object.entries({ ...novos, pagina: novos.pagina ?? undefined })) {
      if (v === undefined || v === "" || (k === "pagina" && v === 1)) prox.delete(k);
      else prox.set(k, String(v));
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

  const temFiltro = Boolean(
    filtros.status || filtros.alerta || filtros.busca || filtros.dono_id || filtros.data_inicio || filtros.data_fim ||
      filtros.tipo || filtros.destinatario_tipo,
  );

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Ofícios</h1>
          <p className="texto-suave">
            {consulta.data ? `${consulta.data.total} encontrado(s)` : " "}
            {!ehAdmin && " · apenas os ofícios cadastrados por você"}
          </p>
        </div>
        <Link to="/oficios/novo" className="btn btn-primario">
          <FilePlus2 size={18} /> Novo ofício
        </Link>
      </header>

      <section className="filtros">
        <div className="busca">
          <Search size={16} className="busca-icone" />
          <input
            className="input"
            placeholder="Buscar nº, protocolo, setor ou observação"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            aria-label="Buscar por número, protocolo, setor/destino ou observação"
          />
        </div>
        <select
          className="input"
          aria-label="Status"
          value={filtros.status ?? ""}
          onChange={(e) => mudar({ status: (e.target.value as StatusOficio) || undefined })}
        >
          <option value="">Todos os status</option>
          {Object.entries(ROTULO_STATUS).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        <select
          className="input"
          aria-label="Prazo"
          value={filtros.alerta ?? ""}
          onChange={(e) => mudar({ alerta: (e.target.value as NivelAlerta) || undefined })}
        >
          <option value="">Qualquer prazo</option>
          {Object.entries(ROTULO_ALERTA).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        <select
          className="input"
          aria-label="Tipo de ofício"
          value={filtros.tipo ?? ""}
          onChange={(e) => mudar({ tipo: (e.target.value as TipoOficio) || undefined })}
        >
          <option value="">Todos os tipos</option>
          {tipos.todos.map((t) => (
            <option key={t.codigo} value={t.codigo}>
              {t.nome}
            </option>
          ))}
        </select>
        <select
          className="input"
          aria-label="Destinatário"
          value={filtros.destinatario_tipo ?? ""}
          onChange={(e) => mudar({ destinatario_tipo: (e.target.value as Destinatario) || undefined })}
        >
          <option value="">Todos os destinatários</option>
          {Object.entries(ROTULO_DESTINATARIO).map(([v, r]) => (
            <option key={v} value={v}>
              {r}
            </option>
          ))}
        </select>
        {ehAdmin && (
          <SeletorCliente
            valor={filtros.dono_id}
            aoMudar={(dono_id) => mudar({ dono_id })}
            rotuloVazio="Todos os clientes"
          />
        )}
        <div className="periodo">
          <input
            type="date"
            className="input"
            aria-label="Data do ofício a partir de"
            value={filtros.data_inicio ?? ""}
            onChange={(e) => mudar({ data_inicio: e.target.value || undefined })}
          />
          <span className="texto-suave">até</span>
          <input
            type="date"
            className="input"
            aria-label="Data do ofício até"
            value={filtros.data_fim ?? ""}
            onChange={(e) => mudar({ data_fim: e.target.value || undefined })}
          />
        </div>
        <select
          className="input"
          aria-label="Ordem"
          value={filtros.ordem}
          onChange={(e) => mudar({ ordem: e.target.value as FiltrosOficio["ordem"] })}
        >
          <option value="recentes">Mais recentes primeiro</option>
          <option value="antigos">Mais antigos primeiro</option>
        </select>
        {temFiltro && (
          <button
            className="btn btn-fantasma"
            onClick={() => {
              setBusca("");
              setSp(new URLSearchParams(), { replace: true });
            }}
          >
            <X size={16} /> Limpar filtros
          </button>
        )}
      </section>

      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : consulta.data.itens.length === 0 ? (
        <Vazio>
          {temFiltro ? "Nenhum ofício com esses filtros." : "Nenhum ofício cadastrado ainda."}
        </Vazio>
      ) : (
        <>
          <ul className="fila lista-mobile">
            {consulta.data.itens.map((o) => (
              <li key={o.id}>
                <Link to={`/oficios/${o.id}`} className={`fila-item item-${o.nivel_alerta ?? "respondido"}`}>
                  <div>
                    <strong>Ofício nº {o.numero}</strong>
                    <small className="texto-suave">
                      {data(o.data_oficio)} · {tipos.rotulo(o.tipo, true)}
                      {ehAdmin && ` · ${o.dono.nome}`}
                    </small>
                    <TextoPrazo oficio={o} />
                    {destinatarioTexto(o) && <small className="item-destino">Para: {destinatarioTexto(o)}</small>}
                    {o.observacao && <small className="item-obs">{o.observacao}</small>}
                  </div>
                  <div className="fila-dir">
                    <StatusBadge status={o.status} />
                    <AlertaBadge nivel={o.nivel_alerta} />
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
                  <th>Data</th>
                  <th>Tipo · Destinatário</th>
                  {ehAdmin && <th>Cliente</th>}
                  <th>Status</th>
                  <th>Prazo</th>
                  <th>Observação</th>
                  <th aria-label="Anexos" />
                  <th aria-label="Abrir" />
                </tr>
              </thead>
              <tbody>
                {consulta.data.itens.map((o) => (
                  <tr
                    key={o.id}
                    className={`linha-clicavel linha-${o.nivel_alerta ?? "respondido"}`}
                    onClick={() => navegar(`/oficios/${o.id}`)}
                  >
                    <td>
                      <Link to={`/oficios/${o.id}`} className="link-forte" onClick={(e) => e.stopPropagation()}>
                        {o.numero}
                      </Link>
                      {o.protocolo && <small className="celula-sub">Prot. {o.protocolo}</small>}
                    </td>
                    <td>{data(o.data_oficio)}</td>
                    <td className="celula-texto" title={[tipos.rotulo(o.tipo), destinatarioTexto(o)].filter(Boolean).join(" · ")}>
                      {tipos.rotulo(o.tipo, true)}
                      <small className="celula-sub celula-destino">
                        {destinatarioTexto(o) ? `Para: ${destinatarioTexto(o)}` : "Destinatário não informado"}
                      </small>
                    </td>
                    {ehAdmin && <td>{o.dono.nome}</td>}
                    <td>
                      <StatusBadge status={o.status} curto />
                    </td>
                    <td title="Dias úteis: do início do prazo até a resposta, e da resposta até a entrega">
                      {o.nivel_alerta && <AlertaBadge nivel={o.nivel_alerta} />}
                      <TextoPrazo oficio={o} />
                    </td>
                    <td className="celula-obs" title={o.observacao ?? ""}>
                      {o.observacao ? <span>{o.observacao}</span> : <span className="texto-suave">—</span>}
                    </td>
                    <td className="texto-suave" title={o.anexos.map((a) => a.nome_original).join(", ")}>
                      {o.anexos.length > 0 && (
                        <span className="anexo-contador">
                          <Paperclip size={14} /> {o.anexos.length}
                        </span>
                      )}
                    </td>
                    <td className="texto-suave">
                      <ChevronRight size={16} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginacao
            pagina={filtros.pagina ?? 1}
            total={consulta.data.total}
            porPagina={POR_PAGINA}
            aoMudar={(pagina) => mudar({ pagina })}
          />
        </>
      )}
    </>
  );
}
