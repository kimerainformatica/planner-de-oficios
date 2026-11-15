import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BellRing, CheckCircle2, ChevronRight, Info, Siren } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { avisosManutencao } from "../../api/endpoints";
import { Carregando, ErroBox } from "../../components/ui";
import type { Aviso } from "../../types";

const ICONE: Record<Aviso["nivel"], ReactNode> = {
  CRITICO: <Siren size={20} />,
  ATENCAO: <AlertTriangle size={20} />,
  INFO: <Info size={20} />,
};
const ROTULO: Record<Aviso["nivel"], string> = { CRITICO: "Urgente", ATENCAO: "Atenção", INFO: "Para acompanhar" };

/** A mesma consulta alimenta o número no menu (LayoutManutencao). */
export function useAvisos() {
  return useQuery({ queryKey: ["manutencao-avisos"], queryFn: avisosManutencao, refetchInterval: 60_000 });
}

/**
 * Avisos internos: o sistema não envia e-mail, então as pendências de cada pessoa ficam aqui e no número do menu.
 * São calculados na hora (não há "lido / não lido"): o aviso some quando a pendência é resolvida.
 */
export function Avisos() {
  const consulta = useAvisos();
  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Avisos</h1>
          <p className="texto-suave">
            O que precisa da sua atenção agora. Cada aviso leva à tela com os itens e some quando a pendência é resolvida.
          </p>
        </div>
      </header>
      {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : consulta.data.itens.length === 0 ? (
        <div className="estado">
          <CheckCircle2 size={22} /> Nenhuma pendência no momento.
        </div>
      ) : (
        <ul className="avisos" aria-label="Avisos">
          {consulta.data.itens.map((a) => (
            <li key={a.chave}>
              <Link to={a.link} className={`aviso aviso-${a.nivel}`}>
                <span className="aviso-icone" aria-hidden>{ICONE[a.nivel]}</span>
                <span className="aviso-texto">
                  <small>{ROTULO[a.nivel]}</small>
                  <strong>{a.titulo}</strong>
                </span>
                <ChevronRight size={18} aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
      <p className="texto-suave aviso-rodape">
        <BellRing size={14} aria-hidden /> Os avisos ficam só dentro do sistema e se atualizam a cada minuto.
      </p>
    </>
  );
}
