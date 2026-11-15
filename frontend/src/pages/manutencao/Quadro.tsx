import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock3, Hourglass, PackageSearch, Siren, Timer, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listarEmpresas, quadroChamados } from "../../api/endpoints";
import { Carregando, ErroBox } from "../../components/ui";
import type { Chamado, ColunaQuadro } from "../../types";
import { dataHora, ROTULO_STATUS } from "../../utils/formato";
import { horas } from "../../utils/manutencao";
import { BadgePrazo, useResumoManutencao } from "./comum";

const ICONE_COLUNA: Record<ColunaQuadro["chave"], ReactNode> = {
  AGUARDANDO_DIAGNOSTICO: <Hourglass size={17} />,
  EM_EXECUCAO: <Wrench size={17} />,
  AGUARDANDO_PECAS: <PackageSearch size={17} />,
  CONCLUIDOS: <CheckCircle2 size={17} />,
};

/**
 * Quadro de acompanhamento: cada chamado na etapa em que está (aguardando diagnóstico → em execução →
 * aguardando peças → concluído). É o painel do técnico; os demais também podem usar.
 */
export function Quadro({ titulo = "Quadro de chamados" }: { titulo?: string }) {
  const [sp, setSp] = useSearchParams();
  const resumoPapel = useResumoManutencao().data;
  const meus = sp.get("meus") === "1";
  const dias = Number(sp.get("dias") ?? 30);
  const empresaId = sp.get("empresa_id") ? Number(sp.get("empresa_id")) : undefined;
  const consulta = useQuery({
    queryKey: ["manutencao-quadro", meus, dias, empresaId],
    queryFn: () => quadroChamados({ meus, dias, empresa_id: empresaId }),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000, // reflete o que é feito no Planner (resposta e entrega das peças)
  });
  const empresas = useQuery({
    queryKey: ["empresas-manutencao"], queryFn: () => listarEmpresas(), enabled: resumoPapel?.eh_tecnico === false,
  });

  function mudar(chave: string, valor: string | undefined) {
    const p = new URLSearchParams(sp);
    if (valor) p.set(chave, valor);
    else p.delete(chave);
    setSp(p, { replace: true });
  }

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  const q = consulta.data;
  const r = q.resumo;

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>{titulo}</h1>
          <p className="texto-suave">
            {q.empresa ? `${q.empresa.nome} · ` : ""}cada chamado na etapa em que está, com o andamento das peças no
            Planner. Atualiza sozinho a cada 30 segundos.
          </p>
        </div>
        <div className="grupo filtros-quadro">
          <div className="alternador" role="group" aria-label="Quais chamados">
            <button className={!meus ? "ativo" : ""} onClick={() => mudar("meus", undefined)}>
              {resumoPapel?.eh_tecnico ? "Todos da empresa" : "Todos"}
            </button>
            <button className={meus ? "ativo" : ""} onClick={() => mudar("meus", "1")}>
              {resumoPapel?.eh_tecnico ? "Só os meus" : "Só os que abri"}
            </button>
          </div>
          {resumoPapel?.eh_tecnico === false && (
            <select className="input" aria-label="Empresa" value={empresaId ?? ""}
              onChange={(e) => mudar("empresa_id", e.target.value || undefined)}>
              <option value="">Todas as empresas</option>
              {(empresas.data ?? []).map((e) => <option key={e.id} value={e.id}>{e.nome}</option>)}
            </select>
          )}
          <select className="input" aria-label="Período dos concluídos" value={dias}
            onChange={(e) => mudar("dias", e.target.value === "30" ? undefined : e.target.value)}>
            <option value="7">Últimos 7 dias</option>
            <option value="30">Últimos 30 dias</option>
            <option value="90">Últimos 90 dias</option>
          </select>
        </div>
      </header>

      <div className="cartoes cartoes-helpdesk">
        <Resumo rotulo="Em aberto" valor={String(r.em_aberto)} icone={<Wrench size={20} />} />
        <Resumo rotulo="Atrasados (sem diagnóstico)" valor={String(r.atrasados)} icone={<Siren size={20} />}
          classe={r.atrasados ? "cartao-CRITICO" : ""} />
        <Resumo rotulo="Aguardando peças" valor={String(r.aguardando_pecas)} icone={<PackageSearch size={20} />} />
        <Resumo rotulo={`Diagnóstico no prazo (${q.dias} dias)`}
          valor={r.diagnostico_no_prazo_pct === null ? "—" : `${r.diagnostico_no_prazo_pct.toLocaleString("pt-BR")}%`}
          icone={<Clock3 size={20} />}
          dica={r.media_horas_diagnostico === null ? undefined : `média de ${horas(r.media_horas_diagnostico)}`} />
        <Resumo rotulo={`Tempo médio de solução (${q.dias} dias)`}
          valor={r.media_horas_solucao === null ? "—" : horas(r.media_horas_solucao)} icone={<Timer size={20} />}
          dica="do diagnóstico à conclusão, em horas corridas" />
      </div>

      <div className="quadro">
        {q.colunas.map((col) => (
          <section key={col.chave} className={`quadro-coluna coluna-${col.chave}`} aria-label={col.titulo}>
            <header className="quadro-topo">
              <span className="quadro-icone" aria-hidden>{ICONE_COLUNA[col.chave]}</span>
              <div>
                <h2>{col.titulo} <span className="quadro-total">{col.chamados.length}</span></h2>
                <small className="texto-suave">{col.descricao}</small>
              </div>
            </header>
            <div className="quadro-cartoes">
              {col.chamados.length === 0 ? (
                <p className="quadro-vazio texto-suave">Nenhum chamado.</p>
              ) : (
                col.chamados.map((c) => <CartaoChamado key={c.id} c={c} coluna={col.chave} />)
              )}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

function Resumo({ rotulo, valor, icone, classe = "", dica }: {
  rotulo: string; valor: string; icone: ReactNode; classe?: string; dica?: string;
}) {
  return (
    <div className={`cartao indicador ${classe}`}>
      <span className="indicador-ic" aria-hidden>{icone}</span>
      <span className="cartao-valor">{valor}</span>
      <span className="cartao-rotulo">{rotulo}</span>
      {dica && <small className="texto-suave">{dica}</small>}
    </div>
  );
}

function CartaoChamado({ c, coluna }: { c: Chamado; coluna: ColunaQuadro["chave"] }) {
  return (
    <Link to={`/manutencao/chamados/${c.id}`} className={`quadro-cartao chamado-item-${c.prazo.situacao}`}>
      <div className="quadro-cartao-topo">
        <strong>{c.codigo}</strong>
        <BadgePrazo prazo={c.prazo} />
      </div>
      <span className="quadro-cartao-titulo">{c.titulo}</span>
      {(c.local || c.equipamento) && (
        <small className="texto-suave">{[c.local, c.equipamento].filter(Boolean).join(" · ")}</small>
      )}
      <ul className="quadro-cartao-info">
        {coluna === "AGUARDANDO_DIAGNOSTICO" && c.prazo.horas_restantes !== null && (
          <li>
            <Hourglass size={13} aria-hidden />
            {c.prazo.horas_restantes >= 0
              ? `faltam ${horas(c.prazo.horas_restantes)} · até ${dataHora(c.prazo_em)}`
              : `atrasado há ${horas(c.prazo.horas_restantes)}`}
          </li>
        )}
        {c.execucao_horas !== null && (
          <li><Wrench size={13} aria-hidden />em execução há {horas(c.execucao_horas)}</li>
        )}
        {/* Andamento de cada solicitação de peças, como está no Planner */}
        {c.oficios_resumo.map((o) => (
          <li key={o.id} className={o.status === "PENDENTE_RESPOSTA" || o.status === "PENDENTE_RECEBIMENTO" ? "info-pecas" : ""}>
            <PackageSearch size={13} aria-hidden />Ofício nº {o.numero} · {ROTULO_STATUS[o.status]}
          </li>
        ))}
        {c.solucao_horas_corridas !== null && (
          <li className="info-solucao"><Timer size={13} aria-hidden />
            solucionado em {horas(c.solucao_horas_corridas)} após o diagnóstico</li>
        )}
      </ul>
      <small className="quadro-cartao-rodape texto-suave">
        {c.tecnico ? `Técnico: ${c.tecnico.nome}` : "Ainda não assumido"} · aberto {dataHora(c.aberto_em)}
      </small>
    </Link>
  );
}
