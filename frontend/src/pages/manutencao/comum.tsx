import { useQuery } from "@tanstack/react-query";
import { resumoManutencao } from "../../api/endpoints";
import type { PrazoChamado, StatusChamado } from "../../types";
import { ROTULO_SITUACAO, ROTULO_STATUS_CHAMADO, textoPrazo } from "../../utils/manutencao";

/** Papel do usuário no módulo (operacional, técnico e empresa, administrador). */
export function useResumoManutencao() {
  return useQuery({ queryKey: ["manutencao-resumo"], queryFn: resumoManutencao, staleTime: 60_000 });
}

export function BadgeStatusChamado({ status }: { status: StatusChamado }) {
  return <span className={`badge chamado-status-${status}`}>{ROTULO_STATUS_CHAMADO[status]}</span>;
}

export function BadgePrazo({ prazo, comTexto }: { prazo: PrazoChamado; comTexto?: boolean }) {
  const texto = comTexto ? textoPrazo(prazo.situacao, prazo.horas_restantes, prazo.horas_ate_diagnostico) : "";
  return (
    <span className="prazo-chamado">
      <span className={`badge chamado-prazo-${prazo.situacao}`}>{ROTULO_SITUACAO[prazo.situacao]}</span>
      {texto && <small className="texto-suave">{texto}</small>}
    </span>
  );
}
