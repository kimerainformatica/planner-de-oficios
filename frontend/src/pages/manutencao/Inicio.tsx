import { useQuery } from "@tanstack/react-query";
import { AlarmClock, CheckCircle2, Hourglass, PlusCircle, Siren, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { painelManutencao } from "../../api/endpoints";
import { Carregando, ErroBox, Vazio } from "../../components/ui";
import { dataHora } from "../../utils/formato";
import { horas, ROTULO_PAPEL_MANUTENCAO } from "../../utils/manutencao";
import { BadgePrazo, BadgeStatusChamado } from "./comum";
import { Quadro } from "./Quadro";

/** Painel do helpdesk: o que está aguardando diagnóstico, o que está perto do prazo e o desempenho por empresa. */
export function InicioManutencao() {
  const consulta = useQuery({ queryKey: ["manutencao-painel"], queryFn: painelManutencao, refetchInterval: 60_000 });

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  const p = consulta.data;
  // O técnico entra direto no quadro de acompanhamento dos chamados da empresa dele
  if (p.papel === "TECNICO") return <Quadro titulo={`Meu painel · ${p.empresa_do_tecnico?.nome ?? "chamados"}`} />;
  const podeAbrir = p.papel === "CLIENTE" || p.eh_admin;

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Helpdesk · Manutenção Clínica</h1>
          <p className="texto-suave">
            {ROTULO_PAPEL_MANUTENCAO[p.papel]}
            {p.empresa_do_tecnico && ` · ${p.empresa_do_tecnico.nome} (você vê os chamados desta empresa)`}
            {" · "}prazo do diagnóstico contado em horas úteis (expediente {p.expediente}, dias úteis)
          </p>
        </div>
        {podeAbrir && (
          <Link to="/manutencao/chamados/novo" className="btn btn-primario">
            <PlusCircle size={18} /> Abrir chamado
          </Link>
        )}
      </header>

      <div className="cartoes cartoes-helpdesk">
        <Indicador rotulo="Aguardando diagnóstico" valor={p.aguardando_diagnostico} icone={<Hourglass size={22} />}
          link="/manutencao/chamados" />
        <Indicador rotulo="Vencendo" valor={p.vencendo} icone={<AlarmClock size={22} />} classe="cartao-ATENCAO"
          link="/manutencao/chamados?situacao=VENCENDO" />
        <Indicador rotulo="Atrasados" valor={p.atrasados} icone={<Siren size={22} />} classe="cartao-CRITICO"
          link="/manutencao/chamados?situacao=ATRASADO" />
        <Indicador rotulo="Em atendimento" valor={p.em_atendimento} icone={<Wrench size={22} />}
          link="/manutencao/chamados?status=EM_ATENDIMENTO" />
        <Indicador rotulo="Concluídos" valor={p.concluidos} icone={<CheckCircle2 size={22} />} classe="cartao-NORMAL"
          link="/manutencao/chamados?status=CONCLUIDO" />
      </div>

      <section className="painel-bloco">
        <div className="bloco-topo">
          <h2>Mais perto do prazo</h2>
          <div className="grupo">
            <Link to="/manutencao/quadro" className="link-forte">Quadro de acompanhamento</Link>
            <Link to="/manutencao/chamados" className="link-forte">Todos os chamados</Link>
          </div>
        </div>
        {p.urgentes.length === 0 ? (
          <Vazio>Nenhum chamado aguardando diagnóstico.</Vazio>
        ) : (
          <ul className="fila">
            {p.urgentes.map((c) => (
              <li key={c.id}>
                <Link to={`/manutencao/chamados/${c.id}`} className={`fila-item chamado-item-${c.prazo.situacao}`}>
                  <div>
                    <strong>{c.codigo} · {c.titulo}</strong>
                    <small className="texto-suave">
                      {c.empresa.nome} · aberto em {dataHora(c.aberto_em)} · prazo {dataHora(c.prazo_em)}
                      {c.local && ` · ${c.local}`}
                    </small>
                  </div>
                  <div className="fila-dir">
                    <BadgeStatusChamado status={c.status} />
                    <BadgePrazo prazo={c.prazo} comTexto />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {p.por_empresa.length > 0 && (
        <section className="painel-bloco">
          <h2>Por empresa</h2>
          <div className="tabela-box">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Empresa</th>
                  <th className="num">Em aberto</th>
                  <th className="num">Sem diagnóstico</th>
                  <th className="num">Atrasados</th>
                  <th className="num">Concluídos</th>
                  <th className="num">Diagnóstico no prazo</th>
                  <th className="num">Tempo médio até o diagnóstico</th>
                  <th className="num">Tempo médio de solução</th>
                </tr>
              </thead>
              <tbody>
                {p.por_empresa.map((e) => (
                  <tr key={e.empresa.id}>
                    <td>
                      <Link to={`/manutencao/chamados?empresa_id=${e.empresa.id}`} className="link-forte">{e.empresa.nome}</Link>
                    </td>
                    <td className="num">{e.abertos}</td>
                    <td className="num">{e.aguardando_diagnostico}</td>
                    <td className={`num ${e.atrasados ? "texto-critico" : ""}`}>{e.atrasados}</td>
                    <td className="num">{e.concluidos}</td>
                    <td className="num">{e.no_prazo_pct === null ? "—" : `${e.no_prazo_pct.toLocaleString("pt-BR")}%`}</td>
                    <td className="num">{e.media_horas_diagnostico === null ? "—" : `${horas(e.media_horas_diagnostico)} úteis`}</td>
                    <td className="num" title="Do diagnóstico à conclusão">
                      {e.media_horas_solucao === null ? "—" : `${horas(e.media_horas_solucao)} úteis`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}

function Indicador({ rotulo, valor, icone, classe = "", link }: {
  rotulo: string; valor: number; icone: ReactNode; classe?: string; link: string;
}) {
  return (
    <Link to={link} className={`cartao cartao-link indicador ${classe}`}>
      <span className="indicador-ic" aria-hidden>{icone}</span>
      <div>
        <span className="cartao-valor">{valor}</span>
        <span className="cartao-rotulo">{rotulo}</span>
      </div>
    </Link>
  );
}
